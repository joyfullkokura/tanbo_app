import streamlit as st
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go

# ページの設定
st.set_page_config(page_title="じいじの田んぼ見守り", layout="wide")

# --- おじいちゃん専用・微調整版デザイン ---
st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-family: "Meiryo", sans-serif;
        font-size: 1.2rem !important; /* 全体を少しだけ小さく */
    }
    h1 {
        font-size: 2.5rem !important; /* タイトルを少し控えめに */
        color: #2e7d32;
        text-align: center;
    }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 2px solid #2e7d32; /* 線を少し細く */
        padding: 10px; /* 余白を減らして中身を広く */
        border-radius: 15px;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2.6rem !important; /* 4remから2.8remへ。これで「…」が消えます */
        font-weight: bold;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 1.2rem !important; /* ラベルも少し小さく */
        color: #333333;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🌾 じいじの田んぼ 監視画面")

CSV_FILE = "water_history.csv"

if os.path.exists(CSV_FILE):
    df = pd.read_csv(CSV_FILE)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    latest = df.iloc[-1]
    
    st.write("### 📢 いまの様子（最新データ）")
    
    col1, col2, col3 = st.columns(3)
    # 英語を一切使わず、日本語だけで表示
    col1.metric("水の深さ", f"{float(latest['level_cm']):.1f} cm")
    col2.metric("いまの温度", f"{float(latest['temp']):.1f} 度")
    col3.metric("いまの湿度", f"{float(latest['hum']):.1f} ％")

    st.markdown("---")

    # --- 水位グラフの改良 ---
    st.subheader("📈 水の深さの変化（グラフ）")
    
    fig_water = px.line(df, x='timestamp', y='level_cm', 
                        markers=True, 
                        template='plotly_white')
    
    # 線を太く(width=6)、点を大きく(size=12)して見やすく
    fig_water.update_traces(
        line_shape='spline', 
        line_smoothing=1.3, 
        line=dict(width=6, color='#1f77b4'),
        marker=dict(size=12)
    )
    
    fig_water.update_layout(
        font=dict(size=20), # グラフ内の文字も大きく
        xaxis_title="時間",
        yaxis_title="水の深さ (センチ)",
        hovermode="x unified"
    )
    st.plotly_chart(fig_water, use_container_width=True)

    # --- 温湿度グラフの改良 ---
    st.subheader("🌡 温度と湿度の変化")
    
    fig_env = go.Figure()
    # 温度（太い赤線）
    fig_env.add_trace(go.Scatter(x=df['timestamp'], y=df['temp'], 
                                 mode='lines+markers', name='温度（度）',
                                 line=dict(shape='spline', color='#ff4b4b', width=6),
                                 marker=dict(size=10)))
    # 湿度（太い青線）
    fig_env.add_trace(go.Scatter(x=df['timestamp'], y=df['hum'], 
                                 mode='lines+markers', name='湿度（％）',
                                 line=dict(shape='spline', color='#00aaff', width=6),
                                 marker=dict(size=10)))
    
    fig_env.update_layout(
        font=dict(size=20),
        template='plotly_white',
        xaxis_title="時間",
        yaxis_title="値",
        hovermode="x unified"
    )
    st.plotly_chart(fig_env, use_container_width=True)

    # 詳細データもおじいちゃん向けに
    with st.expander("もっと詳しく見たいときはここを押してね"):
        st.write("これまでの全ての記録です：")
        st.dataframe(df.sort_values(by="timestamp", ascending=False).rename(
            columns={'timestamp':'時間', 'level_cm':'深さ', 'temp':'温度', 'hum':'湿度'}
        ))

else:
    st.warning("まだ記録がありません。ラズパイが動き出すのを待っています。")