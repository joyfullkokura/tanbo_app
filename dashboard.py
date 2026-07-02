import streamlit as st
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- ページ設定 ---
st.set_page_config(page_title="じいじの田んぼ見守り", layout="wide")

# --- おじいちゃん専用デザイン (CSS) ---
st.markdown("""
    <style>
    html, body, [class*="css"] { font-family: "Meiryo", sans-serif; }
    .title-container { display: flex; justify-content: space-between; align-items: center; }
    .battery-icon { font-size: 1.5rem; background: #e0e0e0; padding: 5px 15px; border-radius: 10px; border: 2px solid #333; }
    h1 { font-size: 2.2rem !important; color: #2e7d32; margin: 0; }
    h2 { font-size: 1.5rem !important; color: #1b5e20; background: #f1f8e9; padding: 10px; border-radius: 10px; }
    div[data-testid="stMetric"] { background-color: #ffffff; border: 2px solid #2e7d32; padding: 15px; border-radius: 15px; }
    div[data-testid="stMetricValue"] { font-size: 2.2rem !important; font-weight: bold; }
    div[data-testid="stMetricLabel"] { font-size: 1.1rem !important; color: #333; }
    .risk-high { color: #d32f2f; font-weight: bold; background: #ffebee; padding: 5px; border-radius: 5px; }
    .risk-low { color: #388e3c; }
    </style>
    """, unsafe_allow_html=True)

# --- ヘッダー（タイトルとバッテリー） ---
battery_level = 85  # 将来的にセンサーから取得
st.markdown(f"""
    <div class="title-container">
        <h1>🌾 じいじの田んぼ監視</h1>
        <div class="battery-icon">🔋 電池あと {battery_level}%</div>
    </div>
    """, unsafe_allow_html=True)

CSV_FILE = "water_history.csv"

if os.path.exists(CSV_FILE):
    df = pd.read_csv(CSV_FILE)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 不足列の補完
    for col in ['water_temp', 'solar_w', 'wind_w', 'solar_wh', 'wind_wh']:
        if col not in df.columns: df[col] = 0.0
            
    latest = df.iloc[-1]

    # --- 数値表示セクション ---
    st.header("📢 いまの状態")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("水の深さ", f"{float(latest['level_cm']):.1f} cm")
    c2.metric("水の温度", f"{float(latest['water_temp']):.1f} 度")
    c3.metric("外の気温・湿度", f"{float(latest['temp']):.1f}度 / {float(latest['hum']):.1f}%")

    c4, c5 = st.columns(2)
    # 発電量から推定した日照量・風量（ロジックは将来INA219で実装）
    sun_status = "強い" if latest['solar_w'] > 5 else "弱い"
    c4.metric("お日さまの光", f"{sun_status}", f"({latest['solar_wh']:.1f} Wh)")
    
    wind_speed_est = (latest['wind_w'] ** (1/3)) * 2 # 風速は電力の3乗根に比例する近似
    wind_status = "強風" if wind_speed_est > 5 else "そよ風"
    c5.metric("風の強さ", f"{wind_status}", f"({latest['wind_wh']:.1f} Wh)")

    # --- 🌾 病害虫・環境予測セクション ---
    st.header("⚠️ 田んぼの健康診断")
    
    # 知能制御：直近24時間のデータを分析
    recent_df = df[df['timestamp'] > (datetime.now() - timedelta(hours=24))]
    avg_temp = recent_df['temp'].mean()
    avg_hum = recent_df['hum'].mean()
    
    # 危険予測ロジック
    risks = []
    if avg_temp > 20 and avg_temp < 25 and avg_hum > 80:
        risks.append(("いもち病", "高", "高温多湿が続いています！"))
    if latest['temp'] > 35:
        risks.append(("高温障害", "高", "気温が35度を超えました。"))
    if latest['level_cm'] < 2:
        risks.append(("干ばつ", "高", "水がほとんどありません！"))
    
    if risks:
        for name, level, reason in risks:
            st.error(f"【{name}】 危険度：{level}（原因：{reason}）")
    else:
        st.success("✅ 今のところ大きな病気の心配はありません。")

    # --- グラフ表示セクション ---
    st.header("📈 グラフで確認")
    tab1, tab2, tab3, tab4 = st.tabs(["📏 水位・水温", "🌡 気温・湿度", "☀️ 日照・風量", "⚡ 発電量"])

    with tab1:
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=df['timestamp'], y=df['level_cm'], mode='lines+markers', name='水の深さ', line=dict(width=5, shape='spline')))
        fig1.add_trace(go.Scatter(x=df['timestamp'], y=df['water_temp'], mode='lines+markers', name='水の温度', line=dict(width=5, shape='spline')))
        st.plotly_chart(fig1, use_container_width=True)

    with tab2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df['timestamp'], y=df['temp'], mode='lines+markers', name='気温', line=dict(width=5, shape='spline', color='red')))
        fig2.add_trace(go.Scatter(x=df['timestamp'], y=df['hum'], mode='lines+markers', name='湿度', line=dict(width=5, shape='spline', color='blue')))
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        # 発電量から推定した仮想の日照量・風量グラフ
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=df['timestamp'], y=df['solar_w']*10, name='日照量(推定)', fill='tozeroy'))
        fig3.add_trace(go.Scatter(x=df['timestamp'], y=df['wind_w']*5, name='風量(推定)', fill='tozeroy'))
        st.plotly_chart(fig3, use_container_width=True)

    with tab4:
        fig4 = go.Figure()
        fig4.add_trace(go.Bar(x=df['timestamp'], y=df['solar_wh'], name='太陽光発電 [Wh]'))
        fig4.add_trace(go.Bar(x=df['timestamp'], y=df['wind_wh'], name='風力発電 [Wh]'))
        st.plotly_chart(fig4, use_container_width=True)

else:
    st.warning("まだデータがありません。")