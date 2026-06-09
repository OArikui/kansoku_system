from collections import deque
import time
import random

# 過去3秒分（450要素）だけを保持するキューを作成
buffer = deque(maxlen=450)

# ダミーのリアルタイムデータ注入ループ
print("データ蓄積を開始します...")
for i in range(500):  # 試しに450を超える500個のデータを入れてみる
    # リアルタイムデータを取得したと仮定
    new_data = random.random() 
    
    # キューに追加（450個を超えると、古いものから自動で消える）
    buffer.append(new_data)
    
    # 状態の確認（最初の450個までは増え続け、その後は450で固定される）
    if (i + 1) % 100 == 0:
        print(f"{i+1}個目のデータを追加。現在の保持数: {len(buffer)}")

# 最終的なバッファの長さを確認
print(f"最終的なバッファの要素数: {len(buffer)}") # 必ず450になります

# 解析時など、必要に応じて通常のリストやNumPy配列に変換も可能
# data_list = list(buffer)