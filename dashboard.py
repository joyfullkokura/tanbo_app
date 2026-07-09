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

# --- おじいちゃん専用：尊厳と視認性を両立したデザイン (CSS) ---
st.markdown("""
    <style>
    /* 全体フォントを視認性の高いメイリオに統一 */
    html, body, [class*="css"] { 
        font-family: "Meiryo", "MS PGothic", "Hiragino Kaku Gothic Pro", sans-serif !important; 
    }
    
    /* 上部ヘッダーのデザイン */
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background-color: #f1f8e9;
        padding: 20px 30px;
        border-radius: 18px;
        border-left: 10px solid #2e7d32;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .header-title {
        font-size: 2.3rem !important;
        font-weight: bold;
        color: #1b5e20;
        margin: 0;
    }
    .header-battery {
        font-size: 1.4rem !important;
        font-weight: bold;
        background-color: #ffffff;
        padding: 10px 20px;
        border-radius: 12px;
        border: 3px solid #2e7d32;
        color: #2e7d32;
    }

    /* 各種セクションの見出し */
    h2 {
        font-size: 1.8rem !important;
        color: #1b5e20;
        border-bottom: 3px solid #c5e1a5;
        padding-bottom: 8px;
        margin-top: 30px !important;
    }

    /* 数値メーター (st.metric) の巨大化と枠線強化 */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 3px solid #2e7d32;
        padding: 22px !important;
        border-radius: 18px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.05);
        text-align: center;
    }
    div[data-testid="stMetricValue"] {
        font-size: 3.2rem !important; /* 老眼対策の極大フォント */
        font-weight: 900 !important;
        color: #1b5e20 !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 1.3rem !important;
        font-weight: bold !important;
        color: #333333 !important;
    }

    /* 作業ボタンの巨大化 */
    div.stButton > button {
        font-size: 1.4rem !important;
        font-weight: bold !important;
        padding: 18px 20px !important;
        border-radius: 15px !important;
        border: 3px solid #2e7d32 !important;
        background-color: #f1f8e9 !important;
        color: #1b5e20 !important;
        width: 100%;
        min-height: 80px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: all 0.2s ease-in-out;
    }
    div.stButton > button:hover {
        background-color: #2e7d32 !important;
        color: #ffffff !important;
        border-color: #1b5e20 !important;
        transform: translateY(-2px);
    }
    
    /* ラジオボタン選択肢の巨大化 */
    div[data-testid="stRadio"] label {
        font-size: 1.4rem !important;
        font-weight: bold !important;
        color: #1b5e20 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Google Sheets API 認証クライアントの取得 ---
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    key_path = "/home/pi/tanbo_app/secret_key.json"
    
    try:
        if os.path.exists(key_path):
            creds = ServiceAccountCredentials.from_json_keyfile_name(key_path, scope)
        elif "gcp_service_account" in st.secrets:
            creds_info = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        else:
            return None
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Googleスプレッドシートへの接続認証に失敗しました。 ({e})")
        return None

# --- 各種データの取得と徹底したエラーハンドリング ---
@st.cache_data(ttl=30)  # キャッシュを30秒に設定
def load_data_from_sheets():
    client = get_gspread_client()
    if client is None:
        return pd.DataFrame(), pd.DataFrame()
        
    try:
        sh = client.open("Tanbo-Monitor")
        
        # 1. 環境データの読み込み
        try:
            env_sheet = sh.worksheet("環境データ")
            env_raw = env_sheet.get_all_values()
        except:
            env_sheet = sh.sheet1  # シート名が違っていた場合は1枚目のシートを使用
            env_raw = env_sheet.get_all_values()
            
        # 2. 作業日誌の読み込み
        try:
            work_sheet = sh.worksheet("作業日誌")
            work_raw = work_sheet.get_all_values()
        except:
            work_raw = []

        df_env = process_env_data(env_raw)
        df_work = process_work_data(work_raw)
        
        return df_env, df_work
    except Exception as e:
        st.error(f"スプレッドシートの読み込み中にエラーが発生しました: {e}")
        return pd.DataFrame(), pd.DataFrame()

# --- 環境データの堅牢なクリーニング ---
def process_env_data(raw):
    # フルスペック時の想定列順定義
    expected_cols = [
        'timestamp', 'reserve', 'level_cm', 'temp', 'hum', 'water_temp', 
        'photo_url', 'battery_v', 'solar_v', 'solar_ma', 'wind_v', 'wind_ma'
    ]
    
    # 生データが完全に空、または壊れている場合
    if not raw or len(raw) == 0 or (len(raw) == 1 and not raw[0]):
        return pd.DataFrame(columns=expected_cols)
        
    df = pd.DataFrame(raw)
    current_col_count = len(df.columns)
    
    # 読み込んだデータの列数に合わせて安全に初期ヘッダーを割り当て
    if current_col_count > 0:
        new_cols = []
        for i in range(current_col_count):
            if i < len(expected_cols):
                new_cols.append(expected_cols[i])
            else:
                new_cols.append(f"col_{i}")
        df.columns = new_cols
    else:
        return pd.DataFrame(columns=expected_cols)

    # 1行目がヘッダー（'timestamp'や'時刻'など）だった場合はデータ行から除外
    if 'timestamp' in str(df.iloc[0, 0]).lower() or '時刻' in str(df.iloc[0, 0]):
        df = df.iloc[1:].reset_index(drop=True)

    # 将来用の不足している列を NaN で安全に補完（クラッシュ防止）
    for col in expected_cols:
        if col not in df.columns:
            df[col] = np.nan

    # 日時をパースし、パース失敗行（空行など）を除外
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
    
    # 各数値列を安全に数値化
    num_cols = ['level_cm', 'temp', 'hum', 'water_temp', 'battery_v', 'solar_v', 'solar_ma', 'wind_v', 'wind_ma']
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    # 文字列データの補完
    df['photo_url'] = df['photo_url'].fillna("なし").astype(str).str.strip().replace("", "なし")
    
    # 物理生データからの二次パラメータ計算処理
    df = calculate_secondary_parameters(df)
    
    return df

# --- 作業日誌データの堅牢なクリーニング（空シート対策） ---
def process_work_data(raw):
    expected_cols = ['timestamp', 'action', 'notes']
    
    # 生データが完全に空、または空文字セルのみの場合
    if not raw or len(raw) == 0 or (len(raw) == 1 and (not raw[0] or raw[0] == [''])):
        return pd.DataFrame(columns=expected_cols)
        
    df = pd.DataFrame(raw)
    current_col_count = len(df.columns)
    
    if current_col_count > 0:
        new_cols = []
        for i in range(current_col_count):
            if i < len(expected_cols):
                new_cols.append(expected_cols[i])
            else:
                new_cols.append(f"col_{i}")
        df.columns = new_cols
    else:
        return pd.DataFrame(columns=expected_cols)

    # ヘッダー行の除外処理
    if 'timestamp' in str(df.iloc[0, 0]).lower() or '時刻' in str(df.iloc[0, 0]):
        df = df.iloc[1:].reset_index(drop=True)

    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""

    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
    return df

# --- 二次パラメータ計算ロジック（未実装データでもエラーにしない） ---
def calculate_secondary_parameters(df):
    if len(df) == 0:
        return df

    # 1. バッテリー残量 (3.0V -> 0%, 4.2V -> 100%)
    def v_to_pct(v):
        if pd.isna(v) or v <= 0.1:
            return np.nan
        pct = ((v - 3.0) / (4.2 - 3.0)) * 100
        return float(np.clip(pct, 0, 100))
    df['battery_pct'] = df['battery_v'].apply(v_to_pct)

    # 2. 発電量 W
    df['solar_w'] = (df['solar_v'] * df['solar_ma']) / 1000.0
    df['wind_w'] = (df['wind_v'] * df['wind_ma']) / 1000.0
    
    df['solar_w'] = df['solar_w'].clip(lower=0.0)
    df['wind_w'] = df['wind_w'].clip(lower=0.0)

    # 3. 発電量 Wh
    df['solar_wh'] = 0.0
    df['wind_wh'] = 0.0
    if len(df) >= 2:
        dt = df['timestamp'].diff().dt.total_seconds() / 3600.0
        dt = dt.fillna(0.0)
        df['solar_wh'] = (df['solar_w'] * dt).cumsum()
        df['wind_wh'] = (df['wind_w'] * dt).cumsum()

    # 4. 風速推定
    def calc_wind_speed(w):
        if w <= 0.001:
            return 0.0
        return float((w ** (1/3)) * 2.2)
    df['wind_speed_est'] = df['wind_w'].apply(calc_wind_speed)

    return df

# --- スプレッドシートへの作業追加関数 ---
def add_work_log_to_sheet(action, current_level, current_water_temp):
    client = get_gspread_client()
    if client is None:
        st.error("認証失敗のため、スプレッドシートへの接続ができませんでした。")
        return False
    try:
        sh = client.open("Tanbo-Monitor")
        try:
            work_sheet = sh.worksheet("作業日誌")
        except:
            # 「作業日誌」ワークシートがなければ自動作成する
            work_sheet = sh.add_worksheet(title="作業日誌", rows="1000", cols="5")
            work_sheet.append_row(["timestamp", "action", "notes"])
            
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        notes = f"（作業時の測定値 - 水位: {current_level:.1f} cm / 水温: {current_water_temp:.1f} 度）"
        work_sheet.append_row([now_str, action, notes])
        st.cache_data.clear()  # キャッシュクリアで即時再ロード
        return True
    except Exception as e:
        st.error(f"書き込みエラーが発生しました: {e}")
        return False


# --- データロードの実行 ---
df_env, df_work = load_data_from_sheets()

# デフォルトデータの補完（完全にデータがない場合の極めて頑健なフェールセーフ）
if df_env.empty:
    df_env = pd.DataFrame([{
        'timestamp': datetime.now(), 'reserve': '', 'level_cm': 0.0, 'temp': 0.0, 'hum': 0.0, 'water_temp': 0.0,
        'photo_url': 'なし', 'battery_v': 0.0, 'solar_v': 0.0, 'solar_ma': 0.0, 'wind_v': 0.0, 'wind_ma': 0.0,
        'battery_pct': np.nan, 'solar_w': 0.0, 'wind_w': 0.0, 'solar_wh': 0.0, 'wind_wh': 0.0, 'wind_speed_est': 0.0
    }])
    df_env['timestamp'] = pd.to_datetime(df_env['timestamp'])

# 作業日誌データのKeyError対策
if 'timestamp' not in df_work.columns:
    df_work = pd.DataFrame(columns=['timestamp', 'action', 'notes'])

# 日付処理用の列作成
df_env['date_only'] = df_env['timestamp'].dt.date

if not df_work.empty:
    df_work['date_only'] = df_work['timestamp'].dt.date
else:
    df_work['date_only'] = pd.Series(dtype='object')

latest = df_env.iloc[-1]

# バッテリー残量の取得と表示文字列化
battery_val = latest.get('battery_pct', np.nan)
battery_str = f"{int(battery_val)} %" if not pd.isna(battery_val) and battery_val > 0 else "測定中"

# --- システムヘッダー表示 ---
st.markdown(f"""
    <div class="title-container">
        <div class="header-title">🌾 田んぼ監視システム</div>
        <div class="header-battery">🔋 バッテリー残量: {battery_str}</div>
    </div>
    """, unsafe_allow_html=True)


# --- 押しやすい大ボタンタブ切り替え ---
selected_tab = st.radio(
    "表示する内容を選択してください",
    ["📊 本日の状況と作業記録", "📈 履歴とデータ分析"],
    horizontal=True,
    label_visibility="collapsed"
)

st.write("---")

# ==========================================
# タブ1: 本日の状況と作業記録
# ==========================================
if selected_tab == "📊 本日の状況と作業記録":
    
    st.header("📋 本日の最新データ")
    
    # 3列の極大数値メーター
    col1, col2, col3 = st.columns(3)
    col1.metric("水の深さ", f"{float(latest['level_cm']):.1f} cm")
    col2.metric("水の温度", f"{float(latest['water_temp']):.1f} 度")
    col3.metric("外の気温・湿度", f"{float(latest['temp']):.1f} 度  /  {float(latest['hum']):.1f} %")

    # 未実装データ（発電量）の安全な表示
    solar_val = latest.get('solar_w', 0.0)
    if solar_val > 0.1:
        solar_status = "十分（快晴）" if solar_val > 6.0 else ("適度（薄曇り）" if solar_val > 1.5 else "微弱（曇天・日没）")
    else:
        solar_status = "未計測（準備中）"
        
    wind_spd = latest.get('wind_speed_est', 0.0)
    if wind_spd > 0.1:
        wind_status = "強風" if wind_spd > 4.5 else ("順風（そよ風）" if wind_spd > 1.0 else "微風")
    else:
        wind_status = "未計測（準備中）"

    col4, col5 = st.columns(2)
    col4.metric("日照状況（太陽光）", f"{solar_status}", f"発電電力: {solar_val:.1f} W")
    col5.metric("風況（風力）", f"{wind_status}", f"発電電力: {latest.get('wind_w', 0.0):.1f} W")

    # --- 田んぼの写真 ＆ AI健康診断の横並びエリア ---
    st.header("📸 現地の状況と健康診断")
    img_col, ai_col = st.columns([1, 1])

    with img_col:
        st.subheader("📷 最新の現地の様子")
        p_url = latest['photo_url']
        if p_url and p_url != "なし":
            try:
                st.image(p_url, use_container_width=True, caption=f"撮影日時: {latest['timestamp'].strftime('%m月%d日 %H時%M分')}")
            except Exception:
                st.warning("📷 写真の読み込みに失敗しました。URLを確認してください。")
        else:
            st.info("📷 現在、新しい写真は登録されていません。")

    with ai_col:
        st.subheader("🤖 AIによる診断")
        
        # 直近24時間の環境データを取得して分析
        recent_cutoff = datetime.now() - timedelta(hours=24)
        recent_data = df_env[df_env['timestamp'] > recent_cutoff]
        avg_temp = recent_data['temp'].mean() if len(recent_data) > 0 else latest['temp']
        avg_hum = recent_data['hum'].mean() if len(recent_data) > 0 else latest['hum']

        risks = []
        if 20.0 <= avg_temp <= 25.0 and avg_hum > 80.0:
            risks.append("【いもち病注意】 高温多湿の状態が継続しており、いもち病の発生リスクが上昇しています。")
        if latest['temp'] > 35.0:
            risks.append("【高温障害警戒】 気温が35度を超え、極めて高温です。可能であれば水の入れ替えをおすすめします。")
        if latest['level_cm'] < 2.0:
            risks.append("【干ばつ注意】 水位が非常に低くなっています。給水作業の検討をお願いします。")

        # 診断メッセージの出力
        if risks:
            for r in risks:
                st.error(r)
        else:
            st.success("✅ 現在のデータに基づくと、田んぼの環境条件は良好に保たれています。病害虫リスクは低水準です。")

        st.markdown("""
        <div style="background-color: #f9f9f9; padding: 15px; border-radius: 12px; border-left: 5px solid #1b5e20;">
            <strong>ℹ️ システム補助メッセージ:</strong><br>
            ラズパイ側で撮影された画像は自動的に解析されます。おじいちゃんが「写真」ボタンをLINEで押した際、数分後に最新のAI診断コメントが反映されます。
        </div>
        """, unsafe_allow_html=True)


    # --- おじいちゃん専用：作業日誌の登録（極大ボタン） ---
    st.header("✍ Black 作業日誌（本日の作業記録）")
    st.write("今日、田んぼで行った作業を下のボタンから選んで押してください。自動的に記録が残ります。")

    b_col1, b_col2, b_col3, b_col4, b_col5 = st.columns(5)

    with b_col1:
        if st.button("🚰 水を入れた"):
            if add_work_log_to_sheet("水を入れた（給水）", latest['level_cm'], latest['water_temp']):
                st.success("「水を入れた」作業を保存しました。")
    with b_col2:
        if st.button("🛑 水を抜いた"):
            if add_work_log_to_sheet("水を抜いた（落水）", latest['level_cm'], latest['water_temp']):
                st.success("「水を抜いた」作業を保存しました。")
    with b_col3:
        if st.button("🌾 肥料をまいた"):
            if add_work_log_to_sheet("肥料をまいた（追肥）", latest['level_cm'], latest['water_temp']):
                st.success("「肥料をまいた」作業を保存しました。")
    with b_col4:
        if st.button("✂️ 草を刈った"):
            if add_work_log_to_sheet("あぜの草を刈った", latest['level_cm'], latest['water_temp']):
                st.success("「草を刈った」作業を保存しました。")
    with b_col5:
        if st.button("🧪 消毒を行った"):
            if add_work_log_to_sheet("病害虫の防除（消毒）", latest['level_cm'], latest['water_temp']):
                st.success("「消毒を行った」作業を保存しました。")


# ==========================================
# タブ2: 履歴とデータ分析
# ==========================================
elif selected_tab == "📈 履歴とデータ分析":
    
    st.header("📅 日付を指定して振り返る")
    
    # 選択カレンダー（本日の日付が初期値。データ内最新日付にフォールバックも可能）
    today_val = date.today()
    selected_date = st.date_input("確認したい日付を選択してください", today_val)

    # 選択日の環境・作業データをフィルタリング
    day_data = df_env[df_env['date_only'] == selected_date]
    
    if not df_work.empty and 'date_only' in df_work.columns:
        day_works = df_work[df_work['date_only'] == selected_date]
    else:
        day_works = pd.DataFrame()

    if day_data.empty:
        st.info(f"選択された日付（{selected_date.strftime('%Y年%m月%d日')}）の環境測定データはまだありません。カレンダーから別の日付を選択してください。")
    else:
        st.subheader(f"📈 {selected_date.strftime('%Y年%m月%d日')} のデータ推移グラフ")
        
        # グラフ1: 水位と水温の推移 (Plotly)
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=day_data['timestamp'], y=day_data['level_cm'],
            mode='lines+markers', name='水位 (cm)',
            line=dict(width=4, shape='spline', color='#1b5e20')
        ))
        fig1.add_trace(go.Scatter(
            x=day_data['timestamp'], y=day_data['water_temp'],
            mode='lines+markers', name='水温 (度)',
            line=dict(width=4, shape='spline', color='#d32f2f')
        ))
        fig1.update_layout(
            title="● 水位と水の温度の変化",
            xaxis_title="時間",
            yaxis_title="測定値",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=60, b=20)
        )
        st.plotly_chart(fig1, use_container_width=True, config={'displayModeBar': False})

        # グラフ2: 発電電力の推移（データが存在する場合のみ表示、すべて0.0の場合は未計測メッセージを出す）
        has_power_data = (day_data['solar_w'].sum() > 0.1) or (day_data['wind_w'].sum() > 0.1)
        
        if has_power_data:
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=day_data['timestamp'], y=day_data['solar_w'],
                mode='lines', name='太陽光発電 (W)', fill='tozeroy',
                line=dict(width=3, color='#f57c00')
            ))
            fig2.add_trace(go.Scatter(
                x=day_data['timestamp'], y=day_data['wind_w'],
                mode='lines', name='風力発電 (W)', fill='tozeroy',
                line=dict(width=3, color='#0288d1')
            ))
            fig2.update_layout(
                title="● 自立電源システムの発電力（ソーラー・風力）",
                xaxis_title="時間",
                yaxis_title="発電電力 (W)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=20, r=20, t=60, b=20)
            )
            st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("⚡ 自立電源システム（太陽光・風力）のデータは現在準備中です。")

    # --- その日の作業日誌の表示 ---
    st.write("---")
    st.subheader(f"📝 {selected_date.strftime('%Y年%m月%d日')} の作業履歴")
    
    if day_works.empty:
        st.write("この日の作業記録はありません。")
    else:
        for index, row in day_works.iterrows():
            time_str = row['timestamp'].strftime('%H時%M分') if not pd.isna(row['timestamp']) else "時刻不明"
            action_name = row['action']
            notes_text = row['notes']
            st.markdown(f"""
            <div style="background-color: #f1f8e9; padding: 15px; border-radius: 10px; border-left: 6px solid #2e7d32; margin-bottom: 10px;">
                <span style="font-size: 1.2rem; font-weight: bold; color: #1b5e20;">🕒 {time_str}</span> &nbsp;&nbsp; 
                <span style="font-size: 1.3rem; font-weight: bold; color: #333333;">👉 【{action_name}】</span><br>
                <span style="color: #666666; font-size: 1.0rem;">{notes_text}</span>
            </div>
            """, unsafe_allow_html=True)