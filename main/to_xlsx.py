import tkinter as tk
from tkinter import filedialog, messagebox
import sqlite3
import pandas as pd

def convert_db_to_xlsx():
    # Tkinterのメインウィンドウを非表示にする
    root = tk.Tk()
    root.withdraw()

    # 1. askopenfile でDBファイルを選択
    # ※ sqlite3.connectにはファイルパスが必要なため、開いたファイルの .name 属性からパスを取得します
    db_file = filedialog.askopenfile(
        title="変換するDBファイルを選択してください",
        filetypes=[("Database Files", "*.db *.sqlite *.sqlite3"), ("All Files", "*.*")]
    )
    
    # キャンセルされた場合は処理を終了
    if not db_file:
        return  

    db_path = db_file.name
    db_file.close()  # askopenfileで開かれたファイルオブジェクトを一旦閉じます

    # 2. 保存先のエクセルファイル名を指定
    xlsx_path = filedialog.asksaveasfilename(
        title="保存先のエクセルファイルを指定してください",
        defaultextension=".xlsx",
        filetypes=[("Excel Files", "*.xlsx")]
    )

    if not xlsx_path:
        return  # キャンセルされた場合は処理を終了

    try:
        # 3. データベースに接続してテーブル名の一覧を取得
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        if not tables:
            messagebox.showwarning("警告", "データベース内にテーブルが見つかりませんでした。")
            conn.close()
            return

        # 4. Pandasを使って各テーブルをExcelのシートに書き出す
        with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
            for table_name in tables:
                # テーブルデータをDataFrameとして読み込む
                df = pd.read_sql_query(f"SELECT * FROM [{table_name}]", conn)
                
                # Excelのシート名は最大31文字の制限があるため切り詰め
                sheet_name = table_name[:31]
                
                # インデックス（行番号）なしで書き出し
                df.to_excel(writer, sheet_name=sheet_name, index=False)

        conn.close()
        messagebox.showinfo("成功", f"変換が完了しました！\n保存先: {xlsx_path}")

    except Exception as e:
        messagebox.showerror("エラー", f"処理中にエラーが発生しました:\n{e}")

if __name__ == "__main__":
    convert_db_to_xlsx()