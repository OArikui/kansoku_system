import time
import matplotlib.pyplot as plt
import numpy as np

# ==========================================================
# 1. リアルタイム描画の準備
# ==========================================================
# インタラクティブモードをONにする（これがないとplt.show()でブロックされます）
plt.ion()

# グラフの土台（FigureとAxes）を作成
fig, ax = plt.subplots()

# 空のリストでデータを初期化
x_data = []
y_data = []

# 最初に空のラインオブジェクトを作成（後からデータを更新するため）
# 引数の「line,」は、戻り値のリストから最初の要素を取り出すためのPythonの書き方です
(line,) = ax.plot(x_data, y_data, marker="o", linestyle="-", color="b")

# グラフの軸範囲やラベルの初期設定
ax.set_xlim(0, 50)  # X軸の表示範囲を0〜50に固定
ax.set_ylim(-1.5, 1.5)  # Y軸の表示範囲を-1.5〜1.5に固定
ax.set_xlabel("Time steps")
ax.set_ylabel("Value")
ax.set_title("Real-time Data Simulation")
ax.grid(True)

# ==========================================================
# 2. リアルタイム描画のループ処理
# ==========================================================
print("リアルタイム描画を開始します...")

try:
    for i in range(50):
        # 新しいデータを生成（例：サイン波にランダムノイズを加えたもの）
        new_x = i
        new_y = np.sin(i * 0.2) + np.random.normal(0, 0.05)

        # データを配列に追加
        x_data.append(new_x)
        y_data.append(new_y)

        # 既存のラインオブジェクトに新しいデータをセット（高速化のポイント！）
        line.set_xdata(x_data)
        line.set_ydata(y_data)

        # もしX軸をデータに合わせて動かしたい（スクロールさせたい）場合は以下を有効化
        if i > 40:
            ax.set_xlim(i - 40, i + 10)

        # グラフを再描画して、指定した秒数だけ一時停止する
        # ※plt.pause() は内部で描画イベントを処理するため、これだけで更新されます
        plt.pause(0.1)

except KeyboardInterrupt:
    # 途中でCtrl+Cを押して終了した場合の処理
    print("\n描画が中断されました。")

# ==========================================================
# 3. 終了処理
# ==========================================================
# インタラクティブモードをOFFにする
plt.ioff()

print("描画が完了しました。グラフを閉じるまでプログラムは待機します。")
# 最後にグラフを画面に保持するために明示的に表示
plt.show()