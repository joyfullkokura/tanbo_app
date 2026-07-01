import streamlit as st
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go

# ページの設定
st.set_page_config(page_title="田んぼ監視ダッシュボード", layout="wide")

# カスタムCSSでおじいちゃんが見やすいフォントサイズに
st.markdown("""
    <style>
    .main { font-size: 1.2rem; }
    stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    </style>
    """, unsafe_allow_stdio=True)

st.title("🌾 じいじの田んぼ監視システム")

CSV_FILE = "water_history.csv"

if os.path.exists(CSV_FILE):
    # CSVを読み込む
    df = pd.read_csv(CSV_FILE)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 最新のデータを表示
    latest = df.iloc[-1]
    
    # 現在の値を大きなカードで表示
    col1, col2, col3 = st.columns(3)
    col1.metric("現在の水位", f"{float(latest['level_cm']):.1f} cm")
    col2.metric("現在の気温", f"{float(latest['temp']):.1f} ℃")
    col3.metric("現在の湿度", f"{float(latest['hum']):.1f} ％")

    # --- 水位グラフ (Plotly) ---
    st.subheader("📊 水位の推移 (点と曲線)")
    
    # 滑らかな曲線(spline)とマーカーを表示
    fig_water = px.line(df, x='timestamp', y='level_cm', 
                        markers=True, # 点を表示
                        title='水位の推移 [cm]',
                        template='plotly_white')
    
    # 曲線にするための設定
    fig_water.update_traces(line_shape='spline', line_smoothing=1.3)
    
    # おじいちゃんが触っても分かりやすいようにツールチップ（ホバー）を設定
    fig_water.update_layout(hovermode="x unified", 
                          xaxis_title="時間", 
                          yaxis_title="水位 [cm]")
    
    st.plotly_chart(fig_water, use_container_width=True)

    # --- 温湿度グラフ ---
    st.subheader("🌡 温度・湿度の推移")
    
    fig_env = go.Figure()
    # 温度
    fig_env.add_trace(go.Scatter(x=df['timestamp'], y=df['temp'], 
                                 mode='lines+markers', name='温度 [℃]',
                                 line=dict(shape='spline', color='#ff4b4b')))
    # 湿度
    fig_env.add_trace(go.Scatter(x=df['timestamp'], y=df['hum'], 
                                 mode='lines+markers', name='湿度 [％]',
                                 line=dict(shape='spline', color='#1f77b4')))
    
    fig_env.update_layout(template='plotly_white', hovermode="x unified")
    st.plotly_chart(fig_env, use_container_width=True)

    # 履歴データの表
    with st.expander("詳細なデータ履歴を表示"):
        st.write(df.sort_values(by="timestamp", ascending=False))

else:
    st.warning("まだデータが記録されていません。しばらくお待ちください。")