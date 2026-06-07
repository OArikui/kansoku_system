import time
import matplotlib.pyplot as plt
import numpy as np

import os
import sys
import time
import cv2
import numpy as np
import zwoasi as asi

# ==========================================
# 1. SDKの初期化
# ==========================================
# 環境に合わせてASICamera2のライブラリパスを指定してください
# ここではカレントディレクトリに配置している前提です
env_filename = ".//ASICamera2.dll"  # Windowsの場合
# env_filename = './libASICamera2.so'  # Linuxの場合

if not os.path.exists(env_filename):
    print(f"エラー: {env_filename} が見つかりません。")
    print("ZWOのSDKからライブラリファイルをこのスクリプトと同じフォルダに配置してください。")
    sys.exit(1)

asi.init(env_filename)

# ==========================================
# 2. カメラの接続と設定
# ==========================================
num_cameras = asi.get_num_cameras()
if num_cameras == 0:
    print("カメラが接続されていません。")
    sys.exit(1)

# 最初に見つかったカメラをオープン
camera_id = 0
camera = asi.Camera(camera_id)
camera_info = camera.get_camera_property()
print(f"接続されたカメラ: {camera_info['Name']}")

# カメラの初期設定 (露出時間やゲインなど)
# 露出時間はマイクロ秒(μs)単位。ここでは30ms（30000μs）に設定
camera.set_control_value(asi.ASI_EXPOSURE, 30000)
camera.set_control_value(asi.ASI_GAIN, 150)
camera.set_control_value(asi.ASI_BANDWIDTHOVERLOAD, 40)  # 転送帯域（必要に応じて調整）

# 画像フォーマットの設定 (RAW8モード)
camera.set_image_type(asi.ASI_IMG_RAW8)

# キャプチャ（動画モード）の開始
camera.start_video_capture()

# ★追加：カメラから現在設定されている正確な解像度（幅、高さ、ビン、画像タイプ）を取得
width, height, binning, img_type = camera.get_roi_format()

print("リアルタイム処理を開始します。'q' キーで終了します。")

# ==========================================
# 3. リアルタイム処理ループ
# ==========================================
try:
    while True:
        try:
            frame = camera.capture_video_frame(timeout=500)
        except asi.ZWO_CaptureError:
            continue

        # 取得した height と width を使って numpy 配列に変形
        img = np.frombuffer(frame, dtype=np.uint8).reshape(height, width)

        # ------------------------------------------
        # 【ここにリアルタイム処理を記述】
        # 画像を1/2に縮小して表示しやすくする
        img_resized = cv2.resize(img, (width // 2, height // 2))

        # 例2：カラーカメラ（Bayer配列）の場合のカラーデモザイク処理
        # ※モノクロカメラの場合は不要です。カメラのBayerパターンに合わせて変更してください。
        # if camera_info['IsColorCam']:
        #     img_color = cv2.cvtColor(img_resized, cv2.COLOR_BAYER_BG2BGR)
        #     cv2.imshow('ASI Camera Live', img_color)
        # else:
        #     cv2.imshow('ASI Camera Live', img_resized)
        # ------------------------------------------
        # 画面に表示
        cv2.imshow("ASI Camera Live", img_resized)

        # 'q' キーが押されたらループを抜ける
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    # ==========================================
    # 4. 後処理（クリーンアップ）
    # ==========================================
    camera.stop_video_capture()
    camera.close()
    cv2.destroyAllWindows()
    print("カメラを安全に切断しました。")