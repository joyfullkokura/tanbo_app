from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageSendMessage
from gpiozero import DistanceSensor
import adafruit_dht
import board
import requests
import base64
import os
import time
import threading
import csv
from datetime import datetime
import subprocess

app = Flask(__name__)

# --- 設定項目 ---
IMGBB_API_KEY = 'ab250c8eaac9837d4f72adaf47dca037'
LINE_CHANNEL_ACCESS_TOKEN = '+dZlN1Iek3mdg3aBNq1HcfgDphe69iLy1CrnCR+Y+dlnkqS5Y0Rsp/rLI4Em51hkQTwRbgxlPhwssUhKOAg5Ko2hZLKAZa3/p26JBQpIO6COQTLHQDc3YaoYyoDI1TzeNAnXchKvU2ScUCC1m2EnIwdB04t89/1O/w1cDnyilFU='
LINE_CHANNEL_SECRET = '5daf13110b8182feecaaf76a38fe73f4'

# センサー設定
sensor = DistanceSensor(echo=27, trigger=17, max_distance=2.0, queue_len=10)
dht_device = adafruit_dht.DHT22(board.D4)

SENSOR_FIXED_HEIGHT = 50.0 
CSV_FILE = "water_history.csv"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- センサー読み取り関数 ---

def get_env_data():
    """温度と湿度を取得する（リトライ機能付き）"""
    for _ in range(3):
        try:
            t = dht_device.temperature
            h = dht_device.humidity
            if t is not None and h is not None:
                return t, h
        except RuntimeError:
            time.sleep(2.0)
    return 25.0, 50.0

def get_water_level(temp):
    """温度補正をして水位を測る関数"""
    v = 331.5 + 0.6 * temp
    sensor.speed_of_sound = v
    dist = sensor.distance * 100
    level = SENSOR_FIXED_HEIGHT - dist
    return dist, level

# --- 定期記録スレッド ---

def logging_loop():
    while True:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        temp, hum = get_env_data()
        dist, level = get_water_level(temp)
        
        # ヘッダーの整合性を保つため、上書きではなく追記
        file_exists = os.path.isfile(CSV_FILE)
        try:
            with open(CSV_FILE, mode='a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["timestamp", "dist_cm", "level_cm", "temp", "hum"])
                writer.writerow([now, f"{dist:.1f}", f"{level:.1f}", f"{temp:.1f}", f"{hum:.1f}"])
            print(f"Saved Log: {level:.1f}cm, {temp:.1f}C")
            git_push()
        except Exception as e:
            print(f"Logging error: {e}")
            
        time.sleep(1800) # 30分
def git_push():
    """CSVをGitHubに自動アップロードする関数"""
    try:
        # 1. 変更されたCSVをステージング
        subprocess.run(["git", "add", CSV_FILE], check=True)
        # 2. コミット（メッセージに時刻を入れると管理しやすい）
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        subprocess.run(["git", "commit", "-m", f"Auto-update: {now_str}"], check=True)
        # 3. アップロード実行
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print(f"GitHub push success at {now_str}")
    except subprocess.CalledProcessError:
        # 変更がない場合などはエラーになるのでスルー
        print("No changes to push or Git error.")
    except Exception as e:
        print(f"Git Push Unexpected Error: {e}")
# --- LINE Webhook ---

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_text = event.message.text
    user_id = event.source.user_id

    # 1. 写真のリクエスト
    if user_text == "写真":
        try:
            # まず即座にリプライで返事
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="撮影を開始します。少々お待ちください..."))
            
            # 重い処理（アップロード）
            target_image = "S__32571415_0.jpg"
            if os.path.exists(target_image):
                url = upload_to_imgbb(target_image)
                # 結果はプッシュで送る
                image_message = ImageSendMessage(original_content_url=url, preview_image_url=url)
                line_bot_api.push_message(user_id, image_message)
            else:
                line_bot_api.push_message(user_id, TextSendMessage(text="画像が見つかりません。"))
        except Exception as e:
            print(f"Photo Error: {e}")

# 2. 水位のリクエスト
    elif user_text == "水位":
        try:
            # センサーから温度と湿度を両方取得
            temp, hum = get_env_data()
            dist, level = get_water_level(temp)
            
            reply_msg = f"📏 水位情報 (温度補正済)\n\n推定水位: {level:.1f}cm\n(水面まで: {dist:.1f}cm)\n計測時の気温: {temp:.1f}℃"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))

            # --- 【修正】保存と送信のロジック ---
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(CSV_FILE, mode='a', newline='') as f:
                writer = csv.writer(f)
                # 湿度の 0.0 を止めて、実測値の hum を書き込むように変更
                writer.writerow([now, f"{dist:.1f}", f"{level:.1f}", f"{temp:.1f}", f"{hum:.1f}"])
            
            # GitHubへ送る（これでおじいちゃんがボタンを押した瞬間にグラフも更新される）
            git_push() 
            # ----------------------------------

        except Exception as e:
            print(f"Water Error: {e}")

    # 3. 温度湿度のリクエスト
    elif user_text == "温度湿度":
        try:
            temp, hum = get_env_data()
            reply_msg = f"🌡 現在の環境\n\n温度: {temp:.1f}℃\n湿度: {hum:.1f}％"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))
        except Exception as e:
            print(f"Env Error: {e}")

    # 4. その他
    else:
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="「写真」「水位」「温度湿度」から選んでね！"))
        except:
            pass

def upload_to_imgbb(image_path):
    url = "https://api.imgbb.com/1/upload"
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    payload = {"key": IMGBB_API_KEY, "image": image_data}
    response = requests.post(url, data=payload)
    return response.json()["data"]["url"]

if __name__ == "__main__":
    t = threading.Thread(target=logging_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000)