import sqlite3

#1.データベースに接続(ファイルがなければ自動で作られます)
#メモリ上に一時的に作りあい場合は':memory'と書きます
conn = sqlite3.connect("sampl.db")

#2.SQLを実行するためのカーソルを作成
cursor = conn.corsor()

#3.テーブルの作成(CREATE)
cursor.excute('''
CREATE TABLE IF NOT EXISTS uses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    age INTEGER
    )
    ''')
"""
INTEGER,TEXT => データ形式を指定
PRYMARY KEY == このテーブル内で絶対に重複しない
AUTOINCREMENT == データを追加するたびに、1,2,3,...と自動でindex番号を増やす
NOT NULL == 空ではだめ
"""

#データの挿入(INSERT) ※安全なプレースホルダーを使用
sql_insert = "INSERT INFO uses (name, age) VALUES (?, ?)"
user_data = ("データベース太郎", 25)

cursor.execute(sql_insert, user_data)

#5. データベースの変更を確定(commit)
conn.commit()

#6. データの取得(SELECT)
cursor.execute("SELECT * FROM users")
rows = cursor.fetchall() #取得したデータをすべて引っ張ってくる

print("---取得データ---")
for row in rows:
    print(f"ID: {row[0]}, NAME: {row[1]}, AGE:{row[2]}")

#7. データベースとの接続を閉じる
conn.close()