import streamlit as st
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ページの設定
st.set_page_config(page_title="じいじの田んぼ見守り", layout="wide")

# --- デザイン設定 (CSS) ---
st.markdown("""
    <style>
    html, body, [class*="css"] { font-family: "Meiryo", sans-serif; }
    h1 { font-size: 2.5rem !important; color: #2e7d32; text-align: center; }
    h2 { font-size: 1.8rem !important; color: #1b5e20; border-bottom: 2px solid #a5d6a7; }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 2px solid #2e7d32;
        padding: 10px;
        border-radius: 15px;
    }
    div[data-testid="stMetricValue"] { font-size: 2.6rem !important; font-weight: bold; }
    div[data-testid="stMetricLabel"] { font-size: 1.2rem !important; color: #333333; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌾 じいじの田んぼ 監視画面")

CSV_FILE = "water_history.csv"

# --- データ読み込みと不足列の補完ロジック ---
if os.path.exists(CSV_FILE):
    df = pd.read_csv(CSV_FILE)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 将来追加する列がなければ、0やNaNで埋める（エラー防止）
    for col in ['water_temp', 'solar_w', 'wind_w', 'solar_wh', 'wind_wh']:
        if col not in df.columns:
            df[col] = 0.0
            
    latest = df.iloc[-1]

    # --- セクション1：田んぼの状態 ---
    st.header("📢 いまの田んぼの様子")
    col1, col2, col3 = st.columns(3)
    col1.metric("水の深さ", f"{float(latest['level_cm']):.1f} cm")
    # 水温が実装されたらここが出る
    col2.metric("水の温度", f"{float(latest.get('water_temp', 0)):.1f} 度")
    col3.metric("外の気温", f"{float(latest['temp']):.1f} 度")

    # --- セクション2：エネルギーの状態 ---
    st.header("⚡ 自給自足のパワー（自然エネルギー）")
    col4, col5 = st.columns(2)
    # 今日の積算電力量（Wh）を表示するイメージ
    col4.metric("太陽からの電気", f"{float(latest.get('solar_wh', 0)):.1f} Wh", help="今日1日の合計")
    col5.metric("風からの電気", f"{float(latest.get('wind_wh', 0)):.1f} Wh", help="今日1日の合計")

    st.markdown("---")

    # --- セクション3：グラフ表示 ---
    tab1, tab2, tab3 = st.tabs(["📏 水位・水温", "🌡 気温・湿度", "⚡ 発電量"])

    with tab1:
        st.subheader("水の変化")
        fig_water = go.Figure()
        fig_water.add_trace(go.Scatter(x=df['timestamp'], y=df['level_cm'], mode='lines+markers', name='水の深さ [cm]', line=dict(width=4, shape='spline')))
        fig_water.add_trace(go.Scatter(x=df['timestamp'], y=df['water_temp'], mode='lines+markers', name='水の温度 [度]', line=dict(width=4, shape='spline')))
        fig_water.update_layout(template='plotly_white', hovermode="x unified")
        st.plotly_chart(fig_water, use_container_width=True)

    with tab2:
        st.subheader("空気の変化")
        fig_env = px.line(df, x='timestamp', y=['temp', 'hum'], markers=True, template='plotly_white')
        fig_env.update_traces(line_shape='spline', line_smoothing=1.3, line=dict(width=4))
        st.plotly_chart(fig_env, use_container_width=True)

    with tab3:
        st.subheader("発電パワーの推移（ワット）")
        fig_power = go.Figure()
        fig_power.add_trace(go.Scatter(x=df['timestamp'], y=df['solar_w'], name='太陽光発電', fill='tozeroy', line=dict(color='orange')))
        fig_power.add_trace(go.Scatter(x=df['timestamp'], y=df['wind_w'], name='風力発電', fill='tozeroy', line=dict(color='skyblue')))
        fig_power.update_layout(template='plotly_white', yaxis_title="発電量 [W]")
        st.plotly_chart(fig_power, use_container_width=True)

    # 詳細データ
    with st.expander("もっと詳しく見たいときはここを押してね"):
        st.dataframe(df.sort_values(by="timestamp", ascending=False))
else:
    st.warning("まだ記録がありません。ラズパイが動き出すのを待っています。")