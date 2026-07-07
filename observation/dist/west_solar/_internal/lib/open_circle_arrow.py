import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Polygon
from matplotlib.transforms import Affine2D  
from matplotlib.widgets import Slider  # インタラクティブ操作用

__all__ = ['OpenCircleArrow']

class OpenCircleArrow:
    def __init__(self, ax, center=(0,0), radius=1.0,
                 gap_angle=90, start_angle=180, clockwise=True,
                 edgecolor='C0', lw=3, tri_size=0.12, tri_color='C0'):
        """
        インタラクティブにパラメーターを更新できる矢印付き円弧オブジェクト
        """
        self.ax = ax
        self.center = center
        self.radius = radius
        self.gap_angle = gap_angle
        self.start_angle = start_angle
        self.clockwise = clockwise
        self.edgecolor = edgecolor
        self.lw = lw
        self.tri_size = tri_size
        self.tri_color = tri_color
        
        # 描画したパッチを保持する変数
        self.arc_patch = None
        self.tri_patch = None
        
        # 初回描画
        self.draw()

    def draw(self):
        """現在保持しているパラメーターで再描画を行う内部メソッド"""
        # すでに描画されている古いパッチがあれば削除する
        if self.arc_patch is not None:
            self.arc_patch.remove()
        if self.tri_patch is not None:
            self.tri_patch.remove()

        cx, cy = self.center
        theta1 = self.start_angle 
        theta2 = self.start_angle - (360 - self.gap_angle)   
        
        # 円弧の生成
        self.arc_patch = Arc((cx, cy), 2*self.radius, 2*self.radius,
                             angle=0, theta1=theta2, theta2=theta1,
                             linewidth=self.lw, edgecolor=self.edgecolor, linestyle='solid')
        self.ax.add_patch(self.arc_patch)

        # 矢じりの計算
        tip_rad = np.deg2rad(theta1)
        ex = cx + self.radius * np.cos(tip_rad)
        ey = cy + self.radius * np.sin(tip_rad)

        tangent_angle = theta1 + 90
        t_rad = np.deg2rad(tangent_angle)

        s = self.tri_size * self.radius
        tri = np.array([[0.0, 0.0],   
                        [-s,  s/2],
                        [-s, -s/2]])
        
        R = np.array([[np.cos(t_rad), -np.sin(t_rad)],
                      [np.sin(t_rad),  np.cos(t_rad)]])
        tri_rot = (tri @ R.T) + np.array([ex, ey])

        # 矢じり（多角形）の生成
        self.tri_patch = Polygon(tri_rot, closed=True, color=self.tri_color)
        self.ax.add_patch(self.tri_patch)

        # 時計回りの反転処理
        if self.clockwise:
            flip = Affine2D().scale(1, -1).translate(0, 2*cy)
            self.arc_patch.set_transform(flip + self.ax.transData)
            self.tri_patch.set_transform(flip + self.ax.transData)
            
        # 画面の更新を促す
        if self.ax.figure and self.ax.figure.canvas:
            self.ax.figure.canvas.draw_idle()

    def update(self, **kwargs):
        """
        外部から変数を更新するためのメソッド。
        例: arrow.update(radius=1.5, gap_angle=45)
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.draw()


# このスクリプトを直接実行した場合、スライダー付きのデモが動きます
if __name__ == "__main__":
    fig, ax = plt.subplots(figsize=(5, 6))
    # 下部にスライダー用のスペースを空ける
    plt.subplots_adjust(bottom=0.25)

    # クラスのインスタンスを作成（描画される）
    arrow = OpenCircleArrow(ax, center=(0,0), radius=1.0, gap_angle=90, clockwise=True)

    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.5, 1.5)
    ax.set_aspect('equal')
    ax.axis('off')

    # スライダーの配置設定 [左, 下, 幅, 高さ]
    ax_gap = plt.axes([0.2, 0.14, 0.6, 0.03])
    ax_radius = plt.axes([0.2, 0.09, 0.6, 0.03])
    ax_start = plt.axes([0.2, 0.04, 0.6, 0.03])

    slider_gap = Slider(ax_gap, 'Gap Angle', 0, 360, valinit=90)
    slider_radius = Slider(ax_radius, 'Radius', 0.1, 1.4, valinit=1.0)
    slider_start = Slider(ax_start, 'Start Angle', 0, 360, valinit=180)

    # スライダーが動いたときに実行する関数
    def handle_update(val):
        arrow.update(
            gap_angle=slider_gap.val,
            radius=slider_radius.val,
            start_angle=slider_start.val
        )

    slider_gap.on_changed(handle_update)
    slider_radius.on_changed(handle_update)
    slider_start.on_changed(handle_update)

    plt.show()