import streamlit as st
import pandas as pd
import os

# ページの設定
st.set_page_config(page_title="田んぼ監視ダッシュボード", layout="wide")

st.title("🌾 じいじの田んぼ監視システム")

CSV_FILE = "water_history.csv"

# データがあるか確認
if os.path.exists(CSV_FILE):
    # CSVを読み込む
    df = pd.read_csv(CSV_FILE)
    
    # 最新のデータを表示
    latest = df.iloc[-1]
    
    # 3列に分けて現在の値を表示（メトリクス）
    col1, col2, col3 = st.columns(3)
    col1.metric("現在の水位", f"{float(latest['level_cm']):.1f} cm")
    col2.metric("現在の気温", f"{float(latest['temp']):.1f} ℃")
    col3.metric("現在の湿度", f"{float(latest['hum']):.1f} ％")

    # グラフ表示
    st.subheader("📊 水位の推移 (過去24時間)")
    # timestampを時間として認識させる
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    st.line_chart(data=df, x='timestamp', y='level_cm')

    st.subheader("🌡 温度・湿度の推移")
    st.line_chart(data=df, x='timestamp', y=['temp', 'hum'])

    # 履歴データの表
    with st.expander("詳細なデータ履歴を表示"):
        st.write(df.sort_values(by="timestamp", ascending=False))

else:
    st.warning("まだデータが記録されていません。しばらくお待ちください。")