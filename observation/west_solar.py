import os
import sys
from pathlib import Path
import time
from collections import deque
import cv2
import matplotlib.pyplot as plt
import numpy as np

# ==========================================
# 0. 階層エラー対策 (パスの自動追加)
# ==========================================
# スクリプトの場所から見て、2階層上の「kansoku_system」を検索パスに追加
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent  # kansoku_system ディレクトリ
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 相対インポートを絶対インポート（lib.〜）に変更
from lib.MIN2_ver1 import MIN2_ignore_sunspots as MIN2
from lib.RANSAC import calculate_west_angle_robust as west_angle
from lib.open_circle_arrow import OpenCircleArrow

# zwoasiのインポート（警告抑制のため環境変数を先にセット）
env_filename = project_root / "lib" / "ASICamera2.dll"
os.environ['ZWO_ASI_LIB'] = str(env_filename) # SDKの事前警告対策

import zwoasi as asi

acceptable = 1  # 太陽の西について画像上の真西とどのくらいの誤差を許すか

# ==========================================
# 1. SDKの初期化
# ==========================================
if not env_filename.exists():
    print(f"エラー: {env_filename} が見つかりません。")
    print("ZWOのSDKからライブラリファイルを lib フォルダに配置してください。")
    sys.exit(1)

asi.init(str(env_filename))

# ==========================================
# 2. カメラの接続と設定
# ==========================================
num_cameras = asi.get_num_cameras()
if num_cameras == 0:
    print("カメラが接続されていません。")
    sys.exit(1)

camera_id = 0
camera = asi.Camera(camera_id)
camera_info = camera.get_camera_property()
print(f"接続されたカメラ: {camera_info['Name']}")

camera.set_control_value(asi.ASI_EXPOSURE, 30000)
camera.set_control_value(asi.ASI_GAIN, 150)
camera.set_control_value(asi.ASI_BANDWIDTHOVERLOAD, 40)

camera.set_image_type(asi.ASI_IMG_RAW8)
camera.start_video_capture()

width, height, binning, img_type = camera.get_roi_format()

buffer = deque(maxlen=500)
plt_drow_waittime = 0.05

def plturn(n):
    if n == 0:
        return 0
    if n < 0:
        g = 1
    else:
        g = -1
    c = 1
    n = abs(n)
    nn = n + n
    while True:
        if nn >= 180:
            return ((180) % (n) + n * (c - 1)) * g
        else:
            c += 1
            nn = n * c

# ==========================================
# 3. リアルタイム処理ループ
# ==========================================
try:
    print("loading...")
    plt.ion()
    fig, ax = plt.subplots()

    frame = camera.capture_video_frame(timeout=500)
    img = np.frombuffer(frame, dtype=np.uint8).reshape(height, width)
    
    ax_img = ax.imshow(img, cmap='gray', vmin=0, vmax=255)
    
    circle = plt.Circle((0, 0), 0, fill=True, color='skyblue', linewidth=2)
    ax_min2 = ax.add_patch(circle)
    
    ax_shdw_c, = ax.plot([], [], 'o', color="cyan", markersize=3, alpha=0.4, label="circle center track")
    
    uxc = ("red", "purple")
    
    grid_lines = []
    for y_val in np.linspace(0, height, 5)[1:-1]:
        line, = ax.plot([0, width], [y_val, y_val], color=uxc[0], linewidth=3, alpha=0.4)
        grid_lines.append(line)
        
    sunline = min(width, height) * 3 / 4 / 2
    ax_sunline, = ax.plot([], [], color=uxc[1], linewidth=3)
    
    fig_text = fig.text(0.01, 0.5, f'turn camera_0°', ha='left', fontsize=20, color=uxc[0])
    arrow = OpenCircleArrow(ax, center=(0, 0.5), radius=100, gap_angle=90, edgecolor=uxc[1], tri_color=uxc[1])
    
    print("complete loading")
    print("リアルタイム処理を開始します。'q' キーで終了するか、グラフウィンドウを閉じてください。")
    
    while True:
        try:
            frame = camera.capture_video_frame(timeout=500)
        except asi.ZWO_CaptureError:
            continue

        img = np.frombuffer(frame, dtype=np.uint8).reshape(height, width)

        (cx, cy), r = MIN2(img)
        buffer.append([cx, cy])

        buf_arr = np.array(buffer)
        recent_pts = buf_arr[-100:]

        ax_img.set_data(img)
        ax_min2.set_center((cx, cy))
        ax_min2.set_radius(r)
        
        ax_shdw_c.set_data(recent_pts[:, 0], recent_pts[:, 1])

        calculate = west_angle(recent_pts)
        
        if 180 - abs(calculate) < acceptable:
            uxc = ("limegreen", "mediumseagreen")
        else:
            uxc = ("red", "purple")

        calc_rad = np.radians(calculate)
        tan_val = np.tan(calc_rad) if abs(np.tan(calc_rad)) > 1e-5 else 1e-5
        
        ax_sunline.set_xdata(np.linspace(cx - sunline * tan_val, cx + sunline * tan_val, 100))
        ax_sunline.set_ydata(np.linspace(cy - sunline / tan_val, cy + sunline / tan_val, 100))
        
        need_cl = plturn(calculate)
        fig_text.set_text(f'turn camera_{need_cl}° clockwise')
        clockwi = True if need_cl > 0 else False
        
        arrow.update(gapangle=abs(need_cl), clockwise=clockwi, edgecolor=uxc[1], tri_color=uxc[1])
        
        for gl in grid_lines:
            gl.set_color(uxc[0])
        ax_sunline.set_color(uxc[1])
        fig_text.set_color(uxc[0])

        plt.pause(0.001)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
        
        if not plt.fignum_exists(fig.number):
            break

finally:
    camera.stop_video_capture()
    camera.close()
    cv2.destroyAllWindows()
    plt.close('all')
    print("カメラを安全に切断しました。")