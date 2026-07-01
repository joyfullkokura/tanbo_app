import time
from gpiozero import DistanceSensor

# --- 設定項目 ---
# Trig=17 (物理11番), Echo=27 (物理13番)
# queue_len=5 とすることで、直近5回の平均値を自動で計算し、ノイズを減らします
sensor = DistanceSensor(echo=27, trigger=17, max_distance=2.0, queue_len=5)

# センサーを設置した高さ（地面からセンサーまでの距離：cm）
# あとで実際の設置に合わせて調整してください
SENSOR_FIXED_HEIGHT = 50.0 

def get_water_level():
    """距離を測定し、水位（深さ）に変換して返す"""
    try:
        # センサーから水面までの距離（cmに変換）
        distance_to_water = sensor.distance * 100
        
        # 水位 = センサーの高さ - 水面までの距離
        water_level = SENSOR_FIXED_HEIGHT - distance_to_water
        
        return water_level, distance_to_water
    except Exception as e:
        print(f"計測エラー: {e}")
        return None, None

print("--- 田んぼ水位計測テスト開始 ---")
print(f"設定上のセンサー高さ: {SENSOR_FIXED_HEIGHT} cm")

try:
    while True:
        level, dist = get_water_level()
        
        if level is not None:
            print(f"【計測】 水面までの距離: {dist:5.1f}cm | 推定水位: {level:5.1f}cm")
        
        # 2秒おきに表示
        time.sleep(2)

except KeyboardInterrupt:
    print("\n計測を停止しました。")