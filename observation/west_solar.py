import time
import matplotlib.pyplot as plt
import matplotlib.collections 
import numpy as np
from pathlib import Path
import os
import sys
import time
import cv2
import numpy as np
import zwoasi as asi
from collections import deque
from ..lib.MIN2_ver1 import MIN2_ignore_sunspots as MIN2  # pyright: ignore[reportMissingImports]
from ..lib.RANSAC import calculate_west_angle_robust as west_angle
from ..lib.open_circle_arrow import OpenCircleArrow

acceptable = 1#太陽の西について画像上の真西とどのくらいの誤差を許すか
# ==========================================
# 1. SDKの初期化
# ==========================================
# 環境に合わせてASICamera2のライブラリパスを指定してください
# ここではカレントディレクトリに配置している前提です
env_filename =  "..\\lib\\ASICamera2.dll"  # Windowsの場合
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


#MIN2_retuen一時保存用
buffer = deque(maxlen=500)

#処理のおぷしょｎ
plt_drow_waittime=0.05#グラフの描画にかかる時間,小さければfpsが上がるが、描画に不具合の可能性

def plturn(n):#あとどのくらい時計回りに回してほしいか
    if n<0:
        g=1
    else:
        g=-1
    c=1
    n=abs(n)
    nn=n+n
    while True:
        if nn >= 180 :
            return ((180)%(n)+n*(c-1))*g
        else:
            c+=1
            nn=n*c
# ==========================================
# 3. リアルタイム処理ループ
# ==========================================
try:
    print("roading...")
    #リアルタイム描画用にaxを作成
    plt.ion()
    fig,ax = plt.subplot()
    #一枚だけ取得
    frame = camera.capture_video_frame(timeout=500)
    img = np.frombuffer(frame, dtype=np.uint8).reshape(height, width)
    ax_img=ax.imshow(img,cv2.IMREAD_GRAYSCALE)#画像
    circle = plt.Circle((0, 0), 0, fill=True, color='skyblue', linewidth=2)
    ax_min2 = ax.add_patch(circle,label="localizeed sun")#検出した太陽
    ax_shdw_c = ax.scatter(buffer[:][0],buffer[:][1],color="cyan",s=3,alpha=0.4,label="circle center track")#円の中心の軌跡(過去100こくらいを想定)
    #$+alpha:後ろのデータほどalphaが小さくしたい
    uxc=("red","purple")#ずれが許容値以内かどうかを直観的に伝えるいろ,User eXperiense Color
    ax_grid= ax.plot([0,width]*4,np.repeat([height/i for i in range(4)],2),c=uxc[0],linewigth=3,alpha=0.4)#横線のグリッド.回転誤差が許容値以内ならgreenにする$+task:グリッドを追加する関数はないのか
    sunline=min([width,height])*3/4/2
    ax_sunline = ax.plot([np.linspace(0,sunline,100)],[0]*100,color=uxc[1],linewight=3)#太陽の移動直線,前5回分くらいのMIN2を参考に算出,回転誤差が許容値以内ならemeraldgreenにする
    fig_text = fig.text(0.01, 0.5, f'turn camera_{0}°', ha='right', fontsize=20, color=uxc[0])#画面上に出る、cameraの回転指示Left,rghitを_の後に入れる.回転誤差が許容値以内ならgreenにする
    arrow = OpenCircleArrow(ax, center=(0, 0.5), radius=100, gap_angle=90,edgecolor=uxc[1],tri_color=uxc[1])
    print("complete roading")

    print("リアルタイム処理を開始します。'q' キーで終了します。")
    while True:
        try:
            frame = camera.capture_video_frame(timeout=500)
        except asi.ZWO_CaptureError:
            continue

        # 取得した height と width を使って numpy 配列に変形
        img = np.frombuffer(frame, dtype=np.uint8).reshape(height, width)

        # ------------------------------------------
        # 【ここにリアルタイム処理を記述】
        (cx,cy),r=MIN2(img)
        buffer.append([cx,cy])

        #pltのデータ更新
        ax_img.set_data(img)
        ax_min2.set_data(plt.Circle((cx, cy), r, fill=True, color='skyblue', linewidth=2))
        ax_shdw_c.set_xdata(buffer[-1:-100:-1][0])
        ax_shdw_c.set_ydata(buffer[-1:-100:-1][1])
        #$+alpha:cv2.imshow("ASI Camera Live", img_resized) cv2のほうがwindowかっこいいです。こっちがいい...
        calculate=west_angle(buffer[-1:-100:-1])
        if 180-abs(calculate) < acceptable:
            uxc=("lime green","emerald green")
        else:
            uxc=("red","purple")
        ax_sunline.set_xdata(np.linspace(int(cx-sunline*np.tan(calculate)),int(cx+sunline*np.tan(calculate)),100))
        ax_sunline.set_ydata(np.linspace(int(cy-sunline/np.tan(calculate)),int(cy+sunline/np.tan(calculate)),100))
        need_cl=plturn(calculate)
        fig_text.set_text(f'turn camera_{need_cl}° clockwise')
        clockwi=True if need_cl>0 else False
        arrow.update(gapangle=abs(need_cl),clockwise=clockwi,edgecolor=uxc[1],tri_color=uxc[1])
        ax_grid.set_color(uxc[0])
        ax_sunline.set_color(uxc[1])
        fig_text.set_color(uxc[0])


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