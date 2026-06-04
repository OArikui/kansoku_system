import openxl
import os
import sqlite3
import pandas as pd
from tkinter.filedialog import askopenfilename


def db_to_csv(db_path, table_name, csv_path):
    """SQLiteのDBから指定したテーブルを読み込み、CSVファイルに保存する関数"""
    #1. データベースに接続
    conn = sqlite3.connect(db_path)
    
    #2. SQLクエリでテーブルの全データを取得
    query = f"SELECT * FROM {table_name}"
    df = pd.read_sql_query(query, conn)
    
    #3. データフレームをCSVファイルに保存
    df.to_csv(csv_path, index=False)
    
    #4. データベース接続を閉じる
    conn.close()
    print(f"{table_name}テーブルのデータを{csv_path}に保存しました")

if __name__ == "__main__":
    db_path = askopenfilename(title="Select SQLite Database", filetypes=[("SQLite Files", "*.db")])
    table_name = input("Enter the table name: ")
    db_to_csv(db_path, table_name, db_path.replace(".db", f"_{table_name}.csv"))
    print("処理が完了しました。")
    print(f"CSVファイルは{db_path.replace('.db', f'_{table_name}.csv')}に保存されました。")