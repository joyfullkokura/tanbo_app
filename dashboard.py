import streamlit as st
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go

# ページの設定
st.set_page_config(page_title="じいじの田んぼ見守り", layout="wide")

# --- おじいちゃん専用・見やすいデザイン設定 (CSS) ---
st.markdown("""
    <style>
    /* 全体の文字を大きく、読みやすいフォントに */
    html, body, [class*="css"] {
        font-family: "Meiryo", "MS PGothic", sans-serif;
        font-size: 1.5rem !important; /* 標準よりかなり大きく */
    }
    /* タイトルを特大に */
    h1 {
        font-size: 3.5rem !important;
        color: #2e7d32; /* 安心する緑色 */
        text-align: center;
    }
    /* 数字のカード(Metric)を強調 */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 3px solid #2e7d32;
        padding: 20px;
        border-radius: 20px;
        box-shadow: 5px 5px 15px rgba(0,0,0,0.1);
    }
    /* 数字そのものを大きく */
    div[data-testid="stMetricValue"] {
        font-size: 4rem !important;
        font-weight: bold;
    }
    /* ラベル(タイトル)を大きく */
    div[data-testid="stMetricLabel"] {
        font-size: 2rem !important;
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
    col1.metric("水の深さ", f"{float(latest['level_cm']):.1f} センチ")
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