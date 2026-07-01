import requests
import base64
from linebot import LineBotApi
from linebot.models import ImageSendMessage

# --- 【設定】あなたの情報 ---
IMGBB_API_KEY = 'ab250c8eaac9837d4f72adaf47dca037'
LINE_CHANNEL_ACCESS_TOKEN = '+dZlN1Iek3mdg3aBNq1HcfgDphe69iLy1CrnCR+Y+dlnkqS5Y0Rsp/rLI4Em51hkQTwRbgxlPhwssUhKOAg5Ko2hZLKAZa3/p26JBQpIO6COQTLHQDc3YaoYyoDI1TzeNAnXchKvU2ScUCC1m2EnIwdB04t89/1O/w1cDnyilFU='
LINE_USER_ID = 'U5e854cee0f76b0aca3b391bca45b8e4e'
# ---------------------------

def upload_to_imgbb(image_path):
    url = "https://api.imgbb.com/1/upload"
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')
    payload = {"key": IMGBB_API_KEY, "image": image_data}
    response = requests.post(url, data=payload)
    return response.json()["data"]["url"]

def send_line_image(image_url):
    line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
    image_message = ImageSendMessage(
        original_content_url=image_url,
        preview_image_url=image_url
    )
    line_bot_api.push_message(LINE_USER_ID, image_message)

if __name__ == "__main__":
    # ここに送りたい画像の名前を入れる
    target_image = "S__32571415_0.jpg" 
    try:
        print("1. クラウドへアップロード中...")
        url = upload_to_imgbb(target_image)
        print(f"   URL取得成功: {url}")
        print("2. LINEへ送信中...")
        send_line_image(url)
        print("--- 送信完了！ ---")
    except Exception as e:
        print(f"エラー発生: {e}")