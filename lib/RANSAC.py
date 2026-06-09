import numpy as np
from sklearn.linear_model import RANSACRegressor
import math

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

# --- テスト実行 ---
if __name__ == "__main__":
    # 理想的な直線移動データ (右斜め上 45度方向) に、極端なノイズを混ぜたもの
    noisy_trajectory = [
        [0.0, 0.0],
        [1.1, 0.9],
        [2.0, 2.1],
        [10.0, -5.0], # 完全に外れた巨大なノイズ！
        [4.2, 3.8],
        [4.9, 5.1],
        [-3.0, 12.0], # もう一つの巨大なノイズ！
        [7.0, 7.1]
    ]

    # 単純な始点と終点の計算（ノイズの影響を受けやすい）
    start_p = noisy_trajectory[0]
    end_p = noisy_trajectory[-1]
    simple_angle = math.degrees(math.atan2(end_p[1] - start_p[1], end_p[0] - start_p[0]))

    # 今回のロバストな計算
    robust_angle = calculate_robust_angle(noisy_trajectory)

    print(f"単純計算の角度: {simple_angle:.2f} 度")
    print(f"RANSACによるロバストな角度: {robust_angle:.2f} 度")