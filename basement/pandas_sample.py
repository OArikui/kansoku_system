import sqlite3
from datetime import datetime,timedelta
import pandas as pd

#これはデモなので、実際の処理構造とは全く異なります。


#データベース名(実行すると自動生成)
DB_FILE = "solar_observation.db"
sampleDBpath=__file__.replace("pandas_sample.py","testDB.db")
print(sampleDBpath)
DB_FILE=sampleDBpath

def save_weather_data_128Hz(shot_time_str):
    """1秒間分の気象データ(128回サンプリング)を疑似的に生成してDBに保存する関数"""
    print("---気象データ(128Hz)の保存処理---")

    #1.1秒間に128回サンプリングした高精度のtimestampを作成
    # ex) 2026-06-02 12:00:00.000から7.8125ms刻みで128個
    time_indices = pd.date_range(
        start=shot_time_str, periods=128, freq="7.8125ms"
    )

    #2.センサーから取得したと仮定した気象データ
    weather_data = {
        "sample_time": time_indices,
        "wind_speed": [2.4 + (i * 0.01) for i in range(128)],
        "humidity": [55.0] * 128,
    }

    #3.pandasのDataFrame(テーブル)に変換
    df_weather = pd.DataFrame(weather_data)
    #4.データベースに接続して一括保存
    conn = sqlite3.connect(DB_FILE)
    #'if_exists='append''で、既存のデータの後ろにどんどん追記していきます。
    df_weather.to_sql(
        "weather_samples", conn, if_exists="append", index=False
    )
    conn.close()
    print("気象データを'weathe_samples'テーブルに保存しました")

def save_photo_analysis(shot_time_str):
    """ASIstudioのtxt情報と自作programの太陽解析結果をDBに保存する関数"""
    print("--- 写真解析データの保存処理を実行 ---")
    #1. 解析結果データの準備(1行/sなのでデータはそれぞれ１個ずつのリスト)
    photo_data={
        "shot_time":[pd.to_datetime(shot_time_str)], #撮影時刻
        "image_path":["path/solar_photo_12000.tiff"], #保存画像のパス
        "sun_radius":[960.5],#自作プログラムで検出した太陽の半径
        "center_x":[1024.0],
        "center_y":[1024.0],
        "img_seeing":[2.1,]
    }

    #2.pandasのDataFrame(テーブル)に変換
    df_photo = pd.DataFrame(photo_data)

    #3.データベースに接続して保存
    conn = sqlite3.connect(DB_FILE)
    df_photo.to_sql("photos", conn, if_exists="append", index=False)
    conn.close()
    print("saved_a_photo_and_its_analysis_results")

def get_data_by_time(target_time_str):
    """指定した「写真の撮影時刻」に紐づく、前後1秒間の気象データ128件をDBから呼び出す関数。(sampling=128Hzの場合)"""
    print("--- データの検索と読み込み(紐づけ確認) ---")
    
    #基準となる時間(12:00:00)とその1秒後(12:00:01)を計算
    start_time = pd.to_datetime(target_time_str)
    end_time = start_time + timedelta(seconds=1)
     
    #データベースに接続
    conn = sqlite3.connect(DB_FILE)

    #1.写真データの読み込み
    #SQLを書く代わりに「特定の時間の写真データをちょうだい」と指示を出す。
    query_photo = f"SELECT * FROM photos WHERE shot_time = '{start_time}'"
    df_photo_res = pd.read_sql_query(query_photo, conn)

    #2.気象データ(128件)の範囲の読み込み
    # BETWEENを使って、その一秒間に含まれるミリ秒データをごそっと取得する
    query_weather = f"SELECT * FROM weather_samples WHERE sample_time BETWEEN '{start_time}' AND '{end_time}'"
    df_wheather_res = pd.read_sql_query(query_weather,conn)
    
    conn.close()

    #3.結果の表示(pandasのDataFrameなのでキレイに表形式で出力されます。)
    print("[取得結果]　写真解析テーブル")#1行
    print(df_photo_res)
    print("\n[取得結果]　対応する気象テーブル(128件のうち最初の5行だけ抜粋)")
    print(df_wheather_res.head(5))

#--- メイン処理の実行テスト ---
if __name__ == "__main__":
    #テストする観測時刻
    test_time = '2026-06-02 12:00:00'

    #データの保存のリスト
    save_weather_data_128Hz(test_time)
    save_photo_analysis(test_time)

    #データ運用テスト(写真の時間から気象でーたを引っ張る)
    get_data_by_time(test_time)