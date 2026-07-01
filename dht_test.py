import time
import adafruit_dht
import board

# GPIO 4 (物理7番) を使用
# 5Vに繋いだので、改めてDHT22として定義します
dht_device = adafruit_dht.DHT22(board.D4)

print("--- 温湿度センサー 5V共有テスト ---")

while True:
    try:
        temp = dht_device.temperature
        humi = dht_device.humidity
        
        if temp is not None:
            print(f"温度: {temp:.1f}℃ | 湿度: {humi:.1f}%")
        
    except RuntimeError as error:
        # 通信エラーはよく出るので無視
        print("読み取り中...")
        time.sleep(2.0)
        continue
        
    time.sleep(2.0)