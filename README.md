# 🌾 Smart Paddy Monitor
### 完全自律型・スマート田んぼ監視システム

> **「毎日の見回りをなくしたい。」**
>
> 高齢の祖父が管理する田んぼの負担軽減を目的に開発したIoTシステムです。
>
> 水位・水温・気温・湿度・カメラ画像を遠隔監視し、
> LINE通知・AI画像診断・作業日誌管理までを一つのシステムとして実現しています。
>
> 現在も実運用を続けながら改善を重ねています。

---

# 主な機能

-  水位・水温・気温・湿度の遠隔監視
-  カメラによる定点撮影
-  Geminiによる稲の健康状態診断
-  LINEから現在状況を取得
-  異常時のLINE通知
-  Streamlitダッシュボード
-  作業日誌管理
-  ソーラー発電による24時間自律運転

---

# 技術スタック

|分類|技術|
|---|---|
|Language|Python|
|Edge Device|Raspberry Pi Zero 2 WH|
|Framework|Flask・Streamlit|
|Database|Google Sheets API|
|AI|Gemini API|
|Image Hosting|ImgBB API|
|Notification|LINE Messaging API|
|Network|Cloudflare Tunnel・4G LTE|
|Version Control|Git・GitHub|

---

# 開発背景

祖父は自宅から約2〜3km離れた田んぼを管理しています。

毎日の

- 水位確認
- 高温時の水温確認
- 病気、害虫の見回り

を続けることが大きな負担となっていました。

そこで

「遠隔から田んぼの状態を確認できれば見回り回数を減らせる」

と考え、このシステムを開発しました。

また、大学で学んでいる知能制御工学を実際の農業へ応用し、

熟練農家の暗黙知をデータとして蓄積・可視化することも目的としています。

---

# システム構成

```
センサー
(水位・水温・温湿度)
        │
        ▼
Raspberry Pi Zero2 WH
        │
        ├── カメラ撮影
        ├── LINE応答
        ├── Gemini診断
        └── Google Sheets更新
                │
                ▼
Cloudflare Tunnel
                │
        ┌───────┴────────┐
        ▼                ▼
Streamlit         LINE Bot
Dashboard         Push通知
```

---

# ハードウェア構成

|部品|用途|
|---|---|
|Raspberry Pi Zero2 WH|システム制御|
|Camera Module3|画像取得|
|JSN-SR04T|水位測定|
|DS18B20|水温測定|
|DHT22|気温・湿度|
|42Wソーラーパネル|独立電源|
|12V LiFePO4 Battery|夜間運転|
|4G LTE Router|インターネット接続|
|防水ボックス|屋外設置|

---

# システム画面

（ここにスクリーンショット）

- LINE画面
- ダッシュボード
- AI診断画面
- 作業日誌
- センサー表示

---

# 技術的な工夫

## ① Raspberry Pi Zero2の512MBメモリ対策

Zero2は512MBしかメモリがないため、

- Flask
- Camera
- Gemini
- LINE SDK

を同時に動かすとOOMで停止してしまいます。

そのため

- Workerプロセス分離
- Lazy Import
- 非同期処理
- スワップ領域2.2GB

を採用し、安定稼働を実現しました。

---

## ② 超省電力設計

超音波センサーは測定時のみ電源を投入。

測定終了後は即座に停止させ、

待機電力を削減しています。

これによりソーラー駆動時間を大きく延ばしています。

---

## ③ 高齢者向けUI設計

祖父が利用することを前提に、

- 大きな文字
- 大きなボタン
- 専門用語を使わない画面

を意識して設計しました。

---

# デバッグで苦労した点

## LINE APIのリトライ問題

### 問題

カメラ撮影に15秒程度かかるため、

LINEがWebhookの応答タイムアウトと判断し、

同じイベントを自動再送していました。

結果としてReplyTokenエラーが発生しました。

### 解決

- Workerを非同期化
- ReplyToken重複使用防止
- 重複イベントの無視

を実装し解決しました。

---

## Streamlit + Google Sheets認証エラー

### 問題

gspreadオブジェクトをキャッシュしたことで、

シリアライズエラーが発生。

### 解決

- キャッシュ解除
- private_key改行コード補正

を実装し、

Cloud環境でも安定動作するよう改善しました。

---

# 使用コード

|ファイル|役割|
|---|---|
|line_receiver.py|LINE Webhook受付・Worker起動|
|worker.py|センサー取得・AI診断・通知|
|dashboard.py|Streamlitダッシュボード|

---

# ディレクトリ構成

```
Paddy-Monitor/

├── dashboard.py
├── worker.py
├── line_receiver.py
├── sensor/
├── camera/
├── images/
├── config/
└── README.md
```

---

# 今後の展望

- Watchdogによる通信障害自動復旧
- Cloudflare Named Tunnel導入
- 独自ドメイン化
- AIによる水管理レコメンド
- センサレス推定を用いた高度な制御
- 自動給水システムとの連携

---

# 成果

- 高齢農家の見回り負担軽減を目的として開発
- 現在も実運用を継続
- 実環境で発生した通信・クラウド・組み込みの課題を解決
- 大学で学んだ知能制御工学を実システムへ応用

---

# 開発者

**九州工業大学 工学部 機械知能工学科（知能制御コース）**

本プロジェクトでは、

「技術を作ること」ではなく、

**実際に使い続けてもらえるシステムを作ること**

を最も重視して開発しています。
