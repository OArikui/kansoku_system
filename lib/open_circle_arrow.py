import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Polygon
from matplotlib.transforms import Affine2D  

def solid_arc_with_triangle(ax, center=(0,0), radius=1.0,
                            gap_angle=90,   # 円周の長さ（度）...負の値にすると、隙間の角度になります
                            start_angle=180, # 円弧開始角度（度, 0=右, 90=上）
                            clockwise=True, #回転を時計回りにするか
                            edgecolor='C0', lw=3,
                            tri_size=0.12,  # 三角形サイズ（半径比）
                            tri_color='C0'): 
    cx, cy = center
    # 円周全体は 360deg。gap_angle を空ける -> arc 長は 360 - gap_angle
    theta1 = start_angle 
    theta2 = start_angle - gap_angle   # 反時計回りを正とする場合の終点
    tri_outward=True
    # Arc は theta1->theta2 の範囲を描く（度）
    arc = Arc((cx, cy), 2*radius, 2*radius,
              angle=0, theta1=theta2, theta2=theta1,
              linewidth=lw, edgecolor=edgecolor, linestyle='solid')
    ax.add_patch(arc)

    # 終点（theta1 側を矢じりにする）
    tip_angle = theta1  # 矢じりを置く角度（度）
    tip_rad = np.deg2rad(tip_angle)
    ex = cx + radius * np.cos(tip_rad)
    ey = cy + radius * np.sin(tip_rad)

    # 接線方向（円周に沿った向き）: theta + 90deg (外向きに矢を向ける)
    if tri_outward:
        tangent_angle = tip_angle + 90
    else:
        tangent_angle = tip_angle - 90
    t_rad = np.deg2rad(tangent_angle)

    # 三角形の基本形（先端が原点にある形、x方向が先端方向）
    s = tri_size * radius
    tri = np.array([[0.0, 0.0],    # 先端（これを終点に合わせる）
                    [-s,  s/2],
                    [-s, -s/2]])
    # 回転行列で向きを合わせ、終点に平行移動
    R = np.array([[np.cos(t_rad), -np.sin(t_rad)],
                  [np.sin(t_rad),  np.cos(t_rad)]])
    tri_rot = (tri @ R.T) + np.array([ex, ey])

    polygon = Polygon(tri_rot, closed=True, color=tri_color)
    if clockwise:
        # 1) パッチ単体を上下反転（中心 cy を軸に反転）
        flip = Affine2D().scale(1, -1).translate(0, 2*cy)

        # 2) パッチの既存のデータ変換に合成して適用
        arc.set_transform(flip + ax.transData)
        polygon.set_transform(flip + ax.transData)
    ax.add_patch(polygon)
  
if __name__=="__main__":
    # 描画例
    from time import time
    st=time()
    fig, ax = plt.subplots(figsize=(4,4))
    solid_arc_with_triangle(ax,
                            center=(0,0), radius=1.0,
                            gap_angle=90, 
                            edgecolor='C1', lw=4,
                            tri_size=0.14, tri_color='C1',
                            clockwise=True)

    ax.set_xlim(-1.4, 1.4); ax.set_ylim(-1.4, 1.4)
    ax.set_aspect('equal')
    ax.axis('off')
    plt.show()
    print(f"実行時間:{time()-st}")
