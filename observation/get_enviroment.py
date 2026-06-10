import time
import datetime
import sqlite3
import pandas as pd

# Vernier Go Direct センサー用ライブラリのインポート
try:
    import gdx  # Vernier公式のラッパーモジュール
    gdx_available = True
except ImportError:
    gdx_available = False
    print("【INFO】'gdx' モジュールが見つからないため、模擬データ（デモモード）で動作します。")

class WeatherObservationSystem:
    def __init__(self, db_path="solar_observation.db"):
        self.db_path = db_path
        self.sampling_rate = 128  # 128Hzサンプリング
        self.interval = 1.0 / self.sampling_rate  # サンプリング周期（約7.8125ms）
        
        # 1. データベースとテーブルの初期化
        self._init_db()
        
        # 2. Vernierセンサーの初期化
        self.device = None
        if gdx_available:
            try:
                self.device = gdx.gdx()
                # USB接続でデバイスを開く（Bluetoothの場合は connection='ble'）
                self.device.open(connection='usb')
                # センサーチャンネルを自動または対話式で選択
                self.device.select_sensors()
                # 128Hz（約8ms周期）で計測スタート
                self.device.start(period=8)
                print("Vernier Go Direct センサーの接続に成功しました。")
            except Exception as e:
                print(f"センサー初期化エラー: {e}。デモモードに切り替えます。")
                self.device = None

    def _init_db(self):
        """SQLiteデータベース内にweather_samplesテーブルを作成する"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # 1秒に128行保存される高頻度気象データテーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weather_samples (
                sample_time TEXT PRIMARY KEY,
                wind_speed REAL,
                humidity REAL,
                pressure REAL
            )
        """)
        conn.commit()
        conn.close()

    def collect_one_second_data(self):
        """
        1秒間（128回分）のデータをメモリ上に超高速でバッファリング（蓄積）する
        """
        wind_speed_list = []
        humidity_list = []
        pressure_list = []
        
        # この1秒間の「正確な開始時刻」を記録（タイムスタンプの基準点）
        start_time = pd.Timestamp.now()
        
        for _ in range(self.sampling_rate):
            t_start = time.perf_counter()
            
            if gdx_available and self.device:
                # センサーから現在の値（1Dリスト形式）を取得
                measurements = self.device.read()  # 例: [風速, 湿度, 気圧] の順と想定
                if measurements:
                    w = measurements[0] if len(measurements) > 0 else 0.0
                    h = measurements[1] if len(measurements) > 1 else 0.0
                    p = measurements[2] if len(measurements) > 2 else 0.0
                else:
                    w, h, p = 0.0, 0.0, 0.0
            else:
                # センサー未接続時のデモ用模擬データ（微細な揺らぎを再現）
                import random
                w = 2.5 + random.uniform(-0.4, 0.4)    # 風速 (m/s)
                h = 55.0 + random.uniform(-1.0, 1.0)   # 湿度 (%)
                p = 1013.2 + random.uniform(-0.1, 0.1) # 気圧 (hPa)
            
            wind_speed_list.append(w)
            humidity_list.append(h)
            pressure_list.append(p)
            
            # 128Hz (7.8125ms間隔) の正確な周期を維持するための厳密なウェイト制御
            t_elapsed = time.perf_counter() - t_start
            t_sleep = self.interval - t_elapsed
            if t_sleep > 0:
                time.sleep(t_sleep)
                
        return start_time, wind_speed_list, humidity_list, pressure_list

    def save_to_db(self, start_time, wind, humidity, pressure):
        """
        蓄積した1秒分（128行）のデータを、Pandasを用いて一括バルクインサートする
        """
        # 1. 128Hz（7.8125ms間隔）のズレのないミリ秒タイムスタンプを128個自動生成
        timestamps = pd.date_range(start=start_time, periods=self.sampling_rate, freq='7.8125ms')
        
        # 2. DataFrameの組み立て
        df = pd.DataFrame({
            'sample_time': timestamps,
            'wind_speed': wind,
            'humidity': humidity,
            'pressure': pressure
        })
        
        # SQLite用にタイムスタンプをテキスト形式（ミリ秒含む文字列）にフォーマット
        df['sample_time'] = df['sample_time'].dt.strftime('%Y-%m-%d %H:%M:%S.%f').str[:-3]
        
        # 3. .to_sql() を用いた一括保存（バルクインサート）
        conn = sqlite3.connect(self.db_path)
        df.to_sql('weather_samples', con=conn, if_exists='append', index=False)
        conn.close()
        
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 1秒分 ({self.sampling_rate}行) の気象データを一括保存しました。")

    def run(self):
        """メインのループ処理（1秒ごとにデータを吸い上げて保存）"""
        print("==================================================")
        print("太陽観測システム: 気象データ収集ソフトが起動しました。")
        print(f"保存先DB: {self.db_path}")
        print("終了するには [Ctrl + C] を押してください。")
        print("==================================================")
        
        try:
            while True:
                # ① 1秒間データを高速サンプリングして溜める
                start_time, wind, hum, press = self.collect_one_second_data()
                
                # ② 溜まった1秒分のデータを一括保存（ディスク負荷極小）
                self.save_to_db(start_time, wind, hum, press)
                
        except KeyboardInterrupt:
            print("\nユーザー操作により気象観測を安全に停止しました。")
        finally:
            # 終了時のセーフティクローズ処理
            if gdx_available and self.device:
                self.device.stop()
                self.device.close()
                print("センサー接続を正常にクローズしました。")

if __name__ == "__main__":
    # システムの起動
    # メインプログラムと同じ場所に「solar_observation.db」として保存されます
    system = WeatherObservationSystem(db_path="solar_observation.db")
    system.run()