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

    /* 作業ボタンの巨大化とホバーアニメーション */
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

    /* 警告・成功表示の視認性強化 */
    .alert-box {
        padding: 15px;
        border-radius: 12px;
        font-size: 1.2rem;
        font-weight: bold;
        margin-bottom: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Google Sheets API 認証クライアントの取得（両対応フォールバック設計） ---
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    key_path = "/home/pi/tanbo_app/secret_key.json"
    
    try:
        if os.path.exists(key_path):
            # ラズパイローカル環境用
            creds = ServiceAccountCredentials.from_json_keyfile_name(key_path, scope)
        elif "gcp_service_account" in st.secrets:
            # Streamlit Cloud環境用（SecretsからJSONを辞書復元）
            creds_info = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        else:
            return None
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Googleスプレッドシートへの接続認証に失敗しました。認証キーの設定を確認してください。 ({e})")
        return None

# --- 各種データの取得と徹底したエラーハンドリング ---
@st.cache_data(ttl=60)  # 1分間のキャッシュでAPIへの過度な負荷を防止
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
            env_sheet = sh.sheet1  # シートが見つからない場合は1枚目
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
    expected_cols = [
        'timestamp', 'reserve', 'level_cm', 'temp', 'hum', 'water_temp', 
        'photo_url', 'battery_v', 'solar_v', 'solar_ma', 'wind_v', 'wind_ma'
    ]
    if not raw or len(raw) == 0:
        return pd.DataFrame(columns=expected_cols)
        
    # ヘッダー行の判定と処理
    first_row = raw[0]
    if first_row and 'timestamp' in str(first_row[0]).lower():
        df = pd.DataFrame(raw[1:])
        cols_count = min(len(df.columns), len(first_row))
        df = df.iloc[:, :cols_count]
        df.columns = first_row[:cols_count]
    else:
        df = pd.DataFrame(raw)
        cols_count = min(len(df.columns), len(expected_cols))
        df = df.iloc[:, :cols_count]
        df.columns = expected_cols[:cols_count]

    # 不足列の安全な自動補完
    for col in expected_cols:
        if col not in df.columns:
            df[col] = np.nan

    # 日時をパースし、破損行（解析不能な行）を除外
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
    
    # 全ての数値列に対して安全に数値化。Noneやエラーは0.0で穴埋め
    num_cols = ['level_cm', 'temp', 'hum', 'water_temp', 'battery_v', 'solar_v', 'solar_ma', 'wind_v', 'wind_ma']
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    # 文字列データの補完
    df['photo_url'] = df['photo_url'].fillna("なし").replace("", "なし")
    
    # 物理生データからの二次パラメータ計算処理
    df = calculate_secondary_parameters(df)
    
    return df

# --- 作業日誌データの堅牢なクリーニング ---
def process_work_data(raw):
    expected_cols = ['timestamp', 'action', 'notes']
    if not raw or len(raw) == 0:
        return pd.DataFrame(columns=expected_cols)
        
    first_row = raw[0]
    if first_row and 'timestamp' in str(first_row[0]).lower():
        df = pd.DataFrame(raw[1:])
        cols_count = min(len(df.columns), len(first_row))
        df = df.iloc[:, :cols_count]
        df.columns = first_row[:cols_count]
    else:
        df = pd.DataFrame(raw)
        cols_count = min(len(df.columns), len(expected_cols))
        df = df.iloc[:, :cols_count]
        df.columns = expected_cols[:cols_count]

    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""

    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df = df.dropna(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
    return df

# --- 二次パラメータ計算ロジック（案B：生データからの変換） ---
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
    
    # ゼロ・マイナスクリップ（異常値回避）
    df['solar_w'] = df['solar_w'].clip(lower=0.0)
    df['wind_w'] = df['wind_w'].clip(lower=0.0)

    # 3. 発電量 Wh（時間差分による台形近似積算）
    df['solar_wh'] = 0.0
    df['wind_wh'] = 0.0
    if len(df) >= 2:
        dt = df['timestamp'].diff().dt.total_seconds() / 3600.0  # 時間単位（時間幅）
        dt = dt.fillna(0.0)
        df['solar_wh'] = (df['solar_w'] * dt).cumsum()
        df['wind_wh'] = (df['wind_w'] * dt).cumsum()

    # 4. 風速推定 (Wの3乗根に比例するモデル。風車特性の簡易近似)
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
        st.error("認証に失敗したため、スプレッドシートへの保存ができませんでした。")
        return False
    try:
        sh = client.open("Tanbo-Monitor")
        work_sheet = sh.worksheet("作業日誌")
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        notes = f"（作業時の測定値 - 水位: {current_level:.1f} cm / 水温: {current_water_temp:.1f} 度）"
        work_sheet.append_row([now_str, action, notes])
        st.cache_data.clear()  # キャッシュをクリアして即時再読み込み
        return True
    except Exception as e:
        st.error(f"書き込みエラーが発生しました: {e}")
        return False


# --- データロードの実行 ---
df_env, df_work = load_data_from_sheets()

# デフォルトデータの補完（データが全く取得できなかった場合のフェールセーフ）
if df_env.empty:
    df_env = pd.DataFrame([{
        'timestamp': datetime.now(), 'reserve': '', 'level_cm': 0.0, 'temp': 0.0, 'hum': 0.0, 'water_temp': 0.0,
        'photo_url': 'なし', 'battery_v': 0.0, 'solar_v': 0.0, 'solar_ma': 0.0, 'wind_v': 0.0, 'wind_ma': 0.0,
        'battery_pct': np.nan, 'solar_w': 0.0, 'wind_w': 0.0, 'solar_wh': 0.0, 'wind_wh': 0.0, 'wind_speed_est': 0.0
    }])
    df_env['timestamp'] = pd.to_datetime(df_env['timestamp'])

latest = df_env.iloc[-1]

# 最新のバッテリー残量の取得と表示文字列化
battery_val = latest['battery_pct']
battery_str = f"{int(battery_val)} %" if not pd.isna(battery_val) else "測定中"

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

    # 発電量に基づく大人の分かりやすい表現
    solar_val = latest['solar_w']
    solar_status = "十分（快晴）" if solar_val > 6.0 else ("適度（薄曇り）" if solar_val > 1.5 else "微弱（曇天・日没）")
    
    wind_spd = latest['wind_speed_est']
    wind_status = "強風" if wind_spd > 4.5 else ("順風（そよ風）" if wind_spd > 1.0 else "微風")

    col4, col5 = st.columns(2)
    col4.metric("日照状況（太陽光）", f"{solar_status}", f"発電電力: {solar_val:.1f} W")
    col5.metric("風況（風力）", f"{wind_status}", f"発電電力: {latest['wind_w']:.1f} W")

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
                st.warning("📷 写真の読み込みに失敗しました。リンク切れ、またはネットワーク制限の可能性があります。")
        else:
            st.info("📷 現在、新しい写真は登録されていません。")

    with ai_col:
        st.subheader("🤖 AIによる診断")
        
        # 簡易的な環境ルールベース判定と直近AIログの引き継ぎ
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
    st.header("✍️ 作業日誌（本日の作業記録）")
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
    
    # 選択カレンダー（デフォルトは本日。2026年想定でも対応できるよう動的に設定）
    today_val = date.today()
    selected_date = st.date_input("確認したい日付を選択してください", today_val)

    # 選択日の環境データをフィルタリング
    df_env['date_only'] = df_env['timestamp'].dt.date
    day_data = df_env[df_env['date_only'] == selected_date]

    # 選択日の作業データをフィルタリング
    df_work['date_only'] = df_work['timestamp'].dt.date
    day_works = df_work[df_work['date_only'] == selected_date]

    if day_data.empty:
        st.info(f"選択された日付（{selected_date.strftime('%Y年%m月%d日')}）のデータは存在しません。別の日付を選択してください。")
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

        # グラフ2: 発電電力の推移
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

    # --- その日の作業日誌の紐付け表示 ---
    st.write("---")
    st.subheader(f"📝 {selected_date.strftime('%Y年%m月%d日')} の作業履歴")
    
    if day_works.empty:
        st.write("この日は作業の記録はありません。")
    else:
        for index, row in day_works.iterrows():
            time_str = row['timestamp'].strftime('%H時%M分')
            action_name = row['action']
            notes_text = row['notes']
            st.markdown(f"""
            <div style="background-color: #f1f8e9; padding: 15px; border-radius: 10px; border-left: 6px solid #2e7d32; margin-bottom: 10px;">
                <span style="font-size: 1.2rem; font-weight: bold; color: #1b5e20;">🕒 {time_str}</span> &nbsp;&nbsp; 
                <span style="font-size: 1.3rem; font-weight: bold; color: #333333;">👉 【{action_name}】</span><br>
                <span style="color: #666666; font-size: 1.0rem;">{notes_text}</span>
            </div>
            """, unsafe_allow_html=True)