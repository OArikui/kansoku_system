import numpy as np
from sklearn.linear_model import RANSACRegressor
import math
import matplotlib.pyplot as plt

def calculate_west_angle_robust(p_lst):
    """
    時系列の座標リストから、誤差に強い移動方向（角度）を算出する関数。
    デカルト座標系(上が正、下が負で右が0,左が180°の座標系です。)
    Parameters:
        p_lst (list): [[x1, y1], [x2, y2], ...] のような2次元座標のリスト
        
    Returns:
        float: 移動方向の角度（度数法: -180 ~ 180度）
               ※ データが不足している場合はNoneを返す
    """
    points = np.array(p_lst)
    if len(points) < 2:
        return None  # 角度を計算するには最低2点必要

    # 時間インデックス t を作成 (0, 1, 2, ..., N-1)
    # scikit-learnの入力形式に合わせて2次元配列にする
    t = np.arange(len(points)).reshape(-1, 1)

    # x座標とy座標を分離
    x = points[:, 0]
    y = points[:, 1]

    # x方向の速度(傾き)をRANSACで推定
    ransac_x = RANSACRegressor(random_state=42)
    ransac_x.fit(t, x)
    vx = ransac_x.estimator_.coef_[0]

    # y方向の速度(傾き)をRANSACで推定
    ransac_y = RANSACRegressor(random_state=42)
    ransac_y.fit(t, y)
    vy = ransac_y.estimator_.coef_[0]

    # 速度ベクトル (vx, vy) から角度を計算 (ラジアン)
    angle_rad = math.atan2(vy, vx)
    
    # ラジアンから度数法(Degree)に変換
    angle_deg = math.degrees(angle_rad)

    return angle_deg

# --- テスト実行と描画 ---
if __name__ == "__main__":
    # 理想的な直線移動データ (右斜め上 45度方向) に、極端なノイズを混ぜたもの
    noisy_trajectory = [
        [0.0, 0.0],
        [1.1, 0.9],
        [2.0, 2.1],
        [10.0, -5.0], # 外れ値1
        [4.2, 3.8],
        [4.9, 5.1],
        [-3.0, 12.0], # 外れ値2
        [7.0, 7.1]
    ]

    points = np.array(noisy_trajectory)
    x_vals = points[:, 0]
    y_vals = points[:, 1]

    # 1. 単純な始点と終点の計算
    dx_simple = x_vals[-1] - x_vals[0]
    dy_simple = y_vals[-1] - y_vals[0]
    simple_angle = math.degrees(math.atan2(dy_simple, dx_simple))

    # 2. RANSACによるロバストな計算
    robust_angle, vx, vy = calculate_west_angle_robust(noisy_trajectory)

    print(f"単純計算の角度: {simple_angle:.2f} 度")
    print(f"RANSACによるロバストな角度: {robust_angle:.2f} 度")



    # --- matplotlib による描画処理 ---
    plt.figure(figsize=(8, 8))
    
    # データの散布図と時系列の軌跡プロット
    plt.plot(x_vals, y_vals, color='gray', linestyle='--', alpha=0.5, label='Trajectory line')
    plt.scatter(x_vals, y_vals, color='blue', zorder=5, label='Data points (with Noise)')
    
    # 始点(Start)と終点(End)を強調
    plt.scatter(x_vals[0], y_vals[0], color='green', s=150, zorder=6, label='Start point')
    plt.scatter(x_vals[-1], y_vals[-1], color='red', s=150, zorder=6, label='End point')

    # 矢印を描画するための基準点（データの中心付近）
    center_x = np.median(x_vals)
    center_y = np.median(y_vals)

    # 【修正箇所】 単純計算の方向ベクトルを矢印で描画
    # エラー回避のため linestyle ではなく、widthを細くし、alphaを薄くして表現します
    len_simple = math.hypot(dx_simple, dy_simple)
    plt.quiver(center_x, center_y, (dx_simple/len_simple)*3, (dy_simple/len_simple)*3, 
               angles='xy', scale_units='xy', scale=1, color='red', width=0.004, alpha=0.5,
               label=f'Simple Vector ({simple_angle:.1f}°)')

    # RANSACで推定した方向ベクトルを矢印で描画 (青太線)
    len_robust = math.hypot(vx, vy)
    plt.quiver(center_x, center_y, (vx/len_robust)*3, (vy/len_robust)*3, 
               angles='xy', scale_units='xy', scale=1, color='darkblue', width=0.008,
               label=f'RANSAC Vector ({robust_angle:.1f}°)')

    # グラフの設定
    plt.title('Comparison of Direction Vector Estimation', fontsize=14)
    plt.xlabel('X coordinate')
    plt.ylabel('Y coordinate')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend(loc='upper left')
    
    # 縦横比を1:1にして角度を正確に見せる
    plt.gca().set_aspect('equal', adjustable='box')
    
    # 表示
    plt.show()