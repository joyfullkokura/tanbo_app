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
LINE_USER_ID = 'U5e854cee0f76b0aca3b391bca45b8e4e' # 送信用
LINE_CHANNEL_SECRET = '5daf13110b8182feecaaf76a38fe73f4'

# センサー設定
# 注意: 起動コマンドで env GPIOZERO_PIN_FACTORY=lgpio を使うこと
sensor = DistanceSensor(echo=27, trigger=17, max_distance=2.0, queue_len=10)
dht_device = adafruit_dht.DHT22(board.D4)

SENSOR_FIXED_HEIGHT = 50.0 
CSV_FILE = "water_history.csv"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- 補助関数 ---

def get_env_data():
    """温度と湿度を取得（失敗してもプログラムを止めない）"""
    for _ in range(3):
        try:
            t = dht_device.temperature
            h = dht_device.humidity
            if t is not None and h is not None:
                return t, h
        except:
            time.sleep(2.0)
    return 25.0, 50.0 # 失敗時の代替値

def get_water_level(temp):
    """温度補正をして水位を測る"""
    v = 331.5 + 0.6 * temp
    sensor.speed_of_sound = v
    dist = sensor.distance * 100
    level = SENSOR_FIXED_HEIGHT - dist
    return dist, level

def git_push():
    """GitHubへ送信（非常に重いので別スレッドで動かす）"""
    try:
        subprocess.run("rm -f .git/index.lock", shell=True) # ロック解除
        subprocess.run(["git", "add", CSV_FILE], check=True)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        subprocess.run(["git", "commit", "-m", f"Auto-update: {now_str}"], capture_output=True)
        # PullしてからPush（競合防止）
        subprocess.run(["git", "pull", "origin", "main", "--rebase"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print(f"GitHub push success: {now_str}")
    except Exception as e:
        print(f"Git Push Error: {e}")

def async_photo_task(user_id):
    """画像アップロードとプッシュ送信を別スレッドで実行"""
    try:
        target_image = "S__32571415_0.jpg"
        if os.path.exists(target_image):
            url = upload_to_imgbb(target_image)
            image_message = ImageSendMessage(original_content_url=url, preview_image_url=url)
            line_bot_api.push_message(user_id, image_message)
    except Exception as e:
        print(f"Photo task error: {e}")

# --- 定期計測スレッド ---
def logging_loop():
    while True:
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            temp, hum = get_env_data()
            dist, level = get_water_level(temp)
            
            with open(CSV_FILE, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([now, f"{dist:.1f}", f"{level:.1f}", f"{temp:.1f}", f"{hum:.1f}"])
            print(f"Saved Log: {level:.1f}cm")
            git_push() # ここはバックグラウンドスレッドなので直接呼んでOK
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(1800) # 30分

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

    if user_text == "写真":
        # まず即座に返信（これでLINEサーバーを安心させる）
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="今の田んぼを撮影します。少々お待ちを..."))
        # 重い処理は別スレッドに丸投げ
        threading.Thread(target=async_photo_task, args=(user_id,)).start()

    elif user_text == "水位":
        temp, hum = get_env_data()
        dist, level = get_water_level(temp)
        reply_msg = f"📏 水位情報 (温度補正済)\n\n推定水位: {level:.1f}cm\n(水面まで: {dist:.1f}cm)\n計測時の気温: {temp:.1f}℃"
        # 即座に返信
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))
        
        # 保存とGit送信は別スレッドで行う
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(CSV_FILE, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([now, f"{dist:.1f}", f"{level:.1f}", f"{temp:.1f}", f"{hum:.1f}"])
        threading.Thread(target=git_push).start()

    elif user_text == "温度湿度":
        temp, hum = get_env_data()
        dist, level = get_water_level(temp) # 念のため水位もセットで保存
        reply_msg = f"🌡 現在の環境\n\n温度: {temp:.1f}℃\n湿度: {hum:.1f}％"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))
        
        # 保存とGit送信は別スレッドで行う
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(CSV_FILE, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([now, f"{dist:.1f}", f"{level:.1f}", f"{temp:.1f}", f"{hum:.1f}"])
        threading.Thread(target=git_push).start()

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