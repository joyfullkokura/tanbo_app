import os
import json
import numpy as np
import pandas as pd
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.graph_objects as go
from datetime import datetime, date, timedelta

# --- ページ基本設定 ---
st.set_page_config(page_title="田んぼ監視システム", layout="wide")

# デバッグログを格納するセッションステートの初期化
if 'debug_logs' not in st.session_state:
    st.session_state['debug_logs'] = []

def log_debug(msg):
    st.session_state['debug_logs'].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# --- CSS設定 ---
st.markdown("""
    <style>
    html, body, [class*="css"] { font-family: "Meiryo", sans-serif !important; }
    .header-container {
        display: flex; justify-content: space-between; align-items: center;
        background-color: #f1f8e9; padding: 20px 30px; border-radius: 18px;
        border-left: 10px solid #2e7d32; margin-bottom: 25px;
    }
    .header-title { font-size: 2.3rem !important; font-weight: bold; color: #1b5e20; margin: 0; }
    .header-battery {
        font-size: 1.4rem !important; font-weight: bold; background-color: #ffffff;
        padding: 10px 20px; border-radius: 12px; border: 3px solid #2e7d32; color: #2e7d32;
    }
    h2 { font-size: 1.8rem !important; color: #1b5e20; border-bottom: 3px solid #c5e1a5; padding-bottom: 8px; }
    div[data-testid="stMetric"] {
        background-color: #ffffff; border: 3px solid #2e7d32; padding: 22px !important; border-radius: 18px;
    }
    div[data-testid="stMetricValue"] { font-size: 3.2rem !important; font-weight: 900 !important; color: #1b5e20 !important; }
    div[data-testid="stMetricLabel"] { font-size: 1.3rem !important; font-weight: bold !important; color: #333333 !important; }
    div.stButton > button {
        font-size: 1.4rem !important; font-weight: bold !important; padding: 18px 20px !important;
        border-radius: 15px !important; border: 3px solid #2e7d32 !important; background-color: #f1f8e9 !important;
        color: #1b5e20 !important; width: 100%; min-height: 80px;
    }
    div.stButton > button:hover { background-color: #2e7d32 !important; color: #ffffff !important; }
    div[data-testid="stRadio"] label { font-size: 1.4rem !important; font-weight: bold !important; color: #1b5e20 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- Google Sheets API 認証 ---
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    key_path = "/home/pi/tanbo_app/secret_key.json"
    
    log_debug("ーー 認証処理を開始します ーー")
    try:
        if os.path.exists(key_path):
            log_debug(f"JSONファイルをローカルパスから読み込みます: {key_path}")
            creds = ServiceAccountCredentials.from_json_keyfile_name(key_path, scope)
        elif "gcp_service_account" in st.secrets:
            log_debug("Streamlit Secrets から gcp_service_account を読み込みます。")
            creds_info = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        else:
            log_debug("【警告】ローカルファイルも Streamlit Secrets も見つかりませんでした。")
            return None
        
        client = gspread.authorize(creds)
        log_debug("Google Sheets API 認証の確立に成功しました。")
        return client
    except Exception as e:
        log_debug(f"【エラー】認証中に例外が発生しました: {e}")
        return None

# --- 各種データの取得 ---
@st.cache_data(ttl=15)  # デバッグのためにキャッシュ時間を15秒に短縮
def load_data_from_sheets():
    client = get_gspread_client()
    if client is None:
        log_debug("接続クライアントが空のため、データ取得をスキップしました。")
        return pd.DataFrame(), pd.DataFrame()
        
    try:
        sh = client.open("Tanbo-Monitor")
        log_debug("スプレッドシート『Tanbo-Monitor』を開くことに成功しました。")
        
        # 1. 環境データの読み込み
        try:
            env_sheet = sh.worksheet("環境データ")
            log_debug("シート『環境データ』からデータを取得します。")
            env_raw = env_sheet.get_all_values()
        except Exception as sheet_err:
            log_debug(f"『環境データ』シートの取得に失敗しました。1枚目のシートにフォールバックします: {sheet_err}")
            env_sheet = sh.sheet1
            env_raw = env_sheet.get_all_values()
            
        log_debug(f"環境データをスプレッドシートから {len(env_raw)} 行取得しました。")

        # 2. 作業日誌の読み込み
        try:
            work_sheet = sh.worksheet("作業日誌")
            work_raw = work_sheet.get_all_values()
            log_debug(f"作業日誌データをスプレッドシートから {len(work_raw)} 行取得しました。")
        except Exception as work_err:
            log_debug(f"作業日誌のシートが存在しないか、読み取れませんでした: {work_err}")
            work_raw = []

        df_env = process_env_data(env_raw)
        df_work = process_work_data(work_raw)
        
        return df_env, df_work
    except Exception as e:
        log_debug(f"【エラー】スプレッドシートからのロード全体の例外: {e}")
        return pd.DataFrame(), pd.DataFrame()

# --- 環境データのクレンジング ---
def process_env_data(raw):
    expected_cols = [
        'timestamp', 'reserve', 'level_cm', 'temp', 'hum', 'water_temp', 
        'photo_url', 'battery_v', 'solar_v', 'solar_ma', 'wind_v', 'wind_ma'
    ]
    
    if not raw or len(raw) == 0:
        log_debug("process_env_data: 生データが空です。")
        return pd.DataFrame(columns=expected_cols)
        
    df = pd.DataFrame(raw)
    current_col_count = len(df.columns)
    log_debug(f"クレンジング前の元データの列数: {current_col_count} 列")
    
    # 読み込んだデータの列数に合わせてヘッダーを安全に割り当て
    new_cols = []
    for i in range(current_col_count):
        if i < len(expected_cols):
            new_cols.append(expected_cols[i])
        else:
            new_cols.append(f"col_{i}")
    df.columns = new_cols

    # 1行目がヘッダー（英語や日本語タイトル）なら除外
    if 'timestamp' in str(df.iloc[0, 0]).lower() or '時刻' in str(df.iloc[0, 0]):
        log_debug("ヘッダー行を検出したため、1行目を除外しました。")
        df = df.iloc[1:].reset_index(drop=True)

    # 不足列を NaN で補完
    for col in expected_cols:
        if col not in df.columns:
            df[col] = np.nan

    # 日時変換
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    original_len = len(df)
    df = df.dropna(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
    log_debug(f"日時パース完了。有効な行数: {len(df)} / 元行数: {original_len}")
    
    # 各数値列を安全に数値化
    num_cols = ['level_cm', 'temp', 'hum', 'water_temp', 'battery_v', 'solar_v', 'solar_ma', 'wind_v', 'wind_ma']
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    df['photo_url'] = df['photo_url'].fillna("なし").astype(str).str.strip().replace("", "なし")
    
    # パラメータ計算
    df = calculate_secondary_parameters(df)
    return df

def process_work_data(raw):
    expected_cols = ['timestamp', 'action', 'notes']
    if not raw or len(raw) == 0 or (len(raw) == 1 and (not raw[0] or raw[0] == [''])):
        return pd.DataFrame(columns=expected_cols)
        
    df = pd.DataFrame(raw)
    current_col_count = len(df.columns)
    
    new_cols = []
    for i in range(current_col_count):
        if i < len(expected_cols):
            new_cols.append(expected_cols[i])
        else:
            new_cols.append(f"col_{i}")
    df.columns = new_cols

    if 'timestamp' in str(df.iloc[0, 0]).lower() or '時刻' in str(df.iloc[0, 0]):
        df = df.iloc[1:].reset_index(drop=True)

    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""

    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
    return df

def calculate_secondary_parameters(df):
    if len(df) == 0:
        return df
    # 電池残量変換 (3.0V〜4.2V)
    def v_to_pct(v):
        if pd.isna(v) or v <= 0.1:
            return np.nan
        pct = ((v - 3.0) / (4.2 - 3.0)) * 100
        return float(np.clip(pct, 0, 100))
    df['battery_pct'] = df['battery_v'].apply(v_to_pct)

    df['solar_w'] = (df['solar_v'] * df['solar_ma']) / 1000.0
    df['wind_w'] = (df['wind_v'] * df['wind_ma']) / 1000.0
    df['solar_w'] = df['solar_w'].clip(lower=0.0)
    df['wind_w'] = df['wind_w'].clip(lower=0.0)

    df['solar_wh'] = 0.0
    df['wind_wh'] = 0.0
    if len(df) >= 2:
        dt = df['timestamp'].diff().dt.total_seconds() / 3600.0
        dt = dt.fillna(0.0)
        df['solar_wh'] = (df['solar_w'] * dt).cumsum()
        df['wind_wh'] = (df['wind_w'] * dt).cumsum()

    def calc_wind_speed(w):
        if w <= 0.001: return 0.0
        return float((w ** (1/3)) * 2.2)
    df['wind_speed_est'] = df['wind_w'].apply(calc_wind_speed)
    return df

# --- スプレッドシートへの作業追加 ---
def add_work_log_to_sheet(action, current_level, current_water_temp):
    client = get_gspread_client()
    if client is None:
        st.error("スプレッドシートへの接続認証に失敗しました。")
        return False
    try:
        sh = client.open("Tanbo-Monitor")
        try:
            work_sheet = sh.worksheet("作業日誌")
        except:
            work_sheet = sh.add_worksheet(title="作業日誌", rows="1000", cols="3")
            work_sheet.append_row(["timestamp", "action", "notes"])
            
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        notes = f"（作業時測定：水位 {current_level:.1f} cm / 水温 {current_water_temp:.1f} 度）"
        work_sheet.append_row([now_str, action, notes])
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"書き込みエラーが発生しました: {e}")
        return False


# --- データロードの実行 ---
df_env, df_work = load_data_from_sheets()

# デフォルト補完用
is_dummy_data = False
if df_env.empty:
    log_debug("【注意】シートからデータが取得できなかったため、ダミーデータを適用しました。")
    is_dummy_data = True
    df_env = pd.DataFrame([{
        'timestamp': datetime.now(), 'reserve': '', 'level_cm': 0.0, 'temp': 0.0, 'hum': 0.0, 'water_temp': 0.0,
        'photo_url': 'なし', 'battery_v': 0.0, 'solar_v': 0.0, 'solar_ma': 0.0, 'wind_v': 0.0, 'wind_ma': 0.0,
        'battery_pct': np.nan, 'solar_w': 0.0, 'wind_w': 0.0, 'solar_wh': 0.0, 'wind_wh': 0.0, 'wind_speed_est': 0.0
    }])
    df_env['timestamp'] = pd.to_datetime(df_env['timestamp'])

if 'timestamp' not in df_work.columns:
    df_work = pd.DataFrame(columns=['timestamp', 'action', 'notes'])

df_env['date_only'] = df_env['timestamp'].dt.date
if not df_work.empty:
    df_work['date_only'] = df_work['timestamp'].dt.date
else:
    df_work['date_only'] = pd.Series(dtype='object')

latest = df_env.iloc[-1]
battery_val = latest.get('battery_pct', np.nan)
battery_str = f"{int(battery_val)} %" if not pd.isna(battery_val) and battery_val > 0 else "測定中"

# --- UI表示 ---
st.markdown(f"""
    <div class="header-container">
        <div class="header-title">🌾 田んぼ監視システム</div>
        <div class="header-battery">🔋 バッテリー残量: {battery_str}</div>
    </div>
    """, unsafe_allow_html=True)

if is_dummy_data:
    st.warning("⚠️ 現在、Googleスプレッドシートへの接続ができていない、またはデータがありません。デバッグログを確認してください。")

selected_tab = st.radio(
    "選択してください", ["📊 本日の状況と作業記録", "📈 履歴とデータ分析"], horizontal=True, label_visibility="collapsed"
)

st.write("---")

if selected_tab == "📊 本日の状況と作業記録":
    st.header("📋 本日の最新データ")
    col1, col2, col3 = st.columns(3)
    col1.metric("水の深さ", f"{float(latest['level_cm']):.1f} cm")
    col2.metric("水の温度", f"{float(latest['water_temp']):.1f} 度")
    col3.metric("外の気温・湿度", f"{float(latest['temp']):.1f} 度  /  {float(latest['hum']):.1f} %")

    solar_val = latest.get('solar_w', 0.0)
    solar_status = "十分（快晴）" if solar_val > 6.0 else ("適度（薄曇り）" if solar_val > 1.5 else "微弱")
    wind_spd = latest.get('wind_speed_est', 0.0)
    wind_status = "強風" if wind_spd > 4.5 else ("順風" if wind_spd > 1.0 else "微風")

    col4, col5 = st.columns(2)
    col4.metric("日照状況（太陽光）", f"{solar_status}", f"発電: {solar_val:.1f} W")
    col5.metric("風況（風力）", f"{wind_status}", f"発電: {latest.get('wind_w', 0.0):.1f} W")

    st.header("📸 現地の状況と健康診断")
    img_col, ai_col = st.columns([1, 1])

    with img_col:
        st.subheader("📷 最新の現地の様子")
        p_url = latest['photo_url']
        if p_url and p_url != "なし":
            try: st.image(p_url, use_container_width=True, caption=f"撮影: {latest['timestamp'].strftime('%m/%d %H:%M')}")
            except: st.warning("📷 画像の読み込みに失敗しました。")
        else:
            st.info("📷 新しい写真は現在登録されていません。")

    with ai_col:
        st.subheader("🤖 AIによる診断")
        recent_data = df_env[df_env['timestamp'] > (datetime.now() - timedelta(hours=24))]
        avg_temp = recent_data['temp'].mean() if len(recent_data) > 0 else latest['temp']
        avg_hum = recent_data['hum'].mean() if len(recent_data) > 0 else latest['hum']

        risks = []
        if 20.0 <= avg_temp <= 25.0 and avg_hum > 80.0:
            risks.append("【いもち病注意】 高温多湿の状態が続いています。発生リスクに注意してください。")
        if latest['temp'] > 35.0:
            risks.append("【高温障害警戒】 気温が35度を超えています。水の入れ替えをおすすめします。")
        if latest['level_cm'] < 2.0:
            risks.append("【干ばつ注意】 水位が非常に低くなっています。給水作業をおすすめします。")

        if risks:
            for r in risks: st.error(r)
        else:
            st.success("✅ 田んぼの環境条件は極めて良好です。病害リスクは最小限に抑えられています。")

    st.header("✍ 作業日誌（本日の作業記録）")
    b1, b2, b3, b4, b5 = st.columns(5)
    with b1:
        if st.button("🚰 水を入れた"):
            if add_work_log_to_sheet("水を入れた（給水）", latest['level_cm'], latest['water_temp']):
                st.success("記録完了！")
    with b2:
        if st.button("🛑 水を抜いた"):
            if add_work_log_to_sheet("水を抜いた（落水）", latest['level_cm'], latest['water_temp']):
                st.success("記録完了！")
    with b3:
        if st.button("🌾 肥料をまいた"):
            if add_work_log_to_sheet("肥料をまいた", latest['level_cm'], latest['water_temp']):
                st.success("記録完了！")
    with b4:
        if st.button("✂️ 草を刈った"):
            if add_work_log_to_sheet("あぜの草を刈った", latest['level_cm'], latest['water_temp']):
                st.success("記録完了！")
    with b5:
        if st.button("🧪 消毒を行った"):
            if add_work_log_to_sheet("病害虫の防除（消毒）", latest['level_cm'], latest['water_temp']):
                st.success("記録完了！")

elif selected_tab == "📈 履歴とデータ分析":
    st.header("📅 日付を指定して振り返る")
    selected_date = st.date_input("確認したい日付を選択してください", date.today())

    day_data = df_env[df_env['date_only'] == selected_date]
    day_works = df_work[df_work['date_only'] == selected_date] if not df_work.empty else pd.DataFrame()

    if day_data.empty or is_dummy_data:
        st.info(f"選択された日付（{selected_date.strftime('%Y年%m月%d日')}）の測定データがありません。")
    else:
        st.subheader(f"📈 {selected_date.strftime('%Y年%m月%d日')} のデータ推移グラフ")
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=day_data['timestamp'], y=day_data['level_cm'], mode='lines+markers', name='水位 (cm)', line=dict(width=4, shape='spline', color='#1b5e20')))
        fig1.add_trace(go.Scatter(x=day_data['timestamp'], y=day_data['water_temp'], mode='lines+markers', name='水温 (度)', line=dict(width=4, shape='spline', color='#d32f2f')))
        fig1.update_layout(title="● 水位と水の温度の変化", xaxis_title="時間", yaxis_title="測定値", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig1, use_container_width=True, config={'displayModeBar': False})

    st.write("---")
    st.subheader(f"📝 {selected_date.strftime('%Y年%m月%d日')} の作業履歴")
    if day_works.empty:
        st.write("この日の作業記録はありません。")
    else:
        for idx, row in day_works.iterrows():
            time_str = row['timestamp'].strftime('%H時%M分') if not pd.isna(row['timestamp']) else "時間不明"
            st.markdown(f"""
            <div style="background-color: #f1f8e9; padding: 15px; border-radius: 10px; border-left: 6px solid #2e7d32; margin-bottom: 10px;">
                <span style="font-size: 1.1rem; font-weight: bold; color: #1b5e20;">🕒 {time_str}</span> &nbsp;
                <span style="font-size: 1.2rem; font-weight: bold; color: #333333;">👉 【{row['action']}】</span><br>
                <span style="color: #666666;">{row['notes']}</span>
            </div>
            """, unsafe_allow_html=True)


# ==========================================
# 🛠 システム開発者用デバッグエリア（最下部）
# ==========================================
st.write("---")
with st.expander("🛠 開発者用システムデバッグ情報（タップで開閉）"):
    st.subheader("📝 接続・動作ログ")
    for log in st.session_state['debug_logs']:
        st.text(log)
        
    st.subheader("📊 環境データフレームの概要 (df_env)")
    st.write(f"取得した有効行数: {len(df_env)} 行")
    st.write("カラム一覧とデータ型:", df_env.dtypes)
    st.write("最新の生データ:", df_env.tail(5))