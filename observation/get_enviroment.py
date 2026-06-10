import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import datetime
import sqlite3
import pandas as pd
import random

# Matplotlib（グラフ描画用）のインポート
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# Vernier Go Direct センサー用ライブラリ
try:
    import gdx
    gdx_available = True
except ImportError:
    gdx_available = False

class WeatherObservationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("天体観測 気象データ収集システム (128Hzサンプリング)")
        self.root.geometry("800x700")
        
        # --- システム変数 ---
        self.db_path = tk.StringVar(value="solar_observation.db")
        self.channels = tk.StringVar(value="1, 2, 3")  # デフォルトのセンサーチャネル
        self.is_observing = False
        self.observation_thread = None
        self.device = None
        
        self.sampling_rate = 128
        self.interval = 1.0 / self.sampling_rate
        
        # グラフ描画用のデータバッファ（最新の1秒分）
        self.latest_time = []
        self.latest_wind = []
        self.latest_hum = []
        self.latest_press = []
        
        # --- GUIの構築 ---
        self._build_gui()
        self._init_db()

    def _build_gui(self):
        # 1. コントロールパネル（上部）
        control_frame = ttk.LabelFrame(self.root, text="観測設定・コントロール", padding=10)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 1-1. 保存場所の設定
        ttk.Label(control_frame, text="保存先 DB:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(control_frame, textvariable=self.db_path, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(control_frame, text="参照...", command=self.browse_file).grid(row=0, column=2)
        
        # 1-2. センサーチャネルの選択
        ttk.Label(control_frame, text="使用チャネル (カンマ区切り):").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(control_frame, textvariable=self.channels, width=20).grid(row=1, column=1, sticky=tk.W, padx=5)
        ttk.Label(control_frame, text="※Vernierの仕様に合わせて入力 (例: 風速,湿度,気圧)").grid(row=1, column=1, sticky=tk.E)
        
        # 1-3. 操作ボタン
        btn_frame = ttk.Frame(control_frame)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=10)
        
        self.btn_start = ttk.Button(btn_frame, text="▶ 観測開始", command=self.start_observation, width=15)
        self.btn_start.pack(side=tk.LEFT, padx=10)
        
        self.btn_stop = ttk.Button(btn_frame, text="■ 観測終了", command=self.stop_observation, state=tk.DISABLED, width=15)
        self.btn_stop.pack(side=tk.LEFT, padx=10)
        
        self.status_label = ttk.Label(btn_frame, text="ステータス: 待機中", foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=20)

        # 2. グラフパネル（下部）
        graph_frame = ttk.LabelFrame(self.root, text="リアルタイム観測データ (最新1秒間 / 128サンプリング)", padding=5)
        graph_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # MatplotlibのFigureを作成し、3つのサブプロット（行）を配置
        self.fig = Figure(figsize=(8, 5), dpi=100)
        self.ax1 = self.fig.add_subplot(311)
        self.ax2 = self.fig.add_subplot(312)
        self.ax3 = self.fig.add_subplot(313)
        self.fig.tight_layout(pad=3.0)
        
        # TkinterのキャンバスにMatplotlibを埋め込む
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def browse_file(self):
        """保存場所をダイアログで選択"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")],
            title="データベースの保存先を選択"
        )
        if filepath:
            self.db_path.set(filepath)
            self._init_db() # 保存先が変わったのでテーブルを初期化

    def _init_db(self):
        """データベースとテーブルの初期化"""
        conn = sqlite3.connect(self.db_path.get())
        cursor = conn.cursor()
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

    def start_observation(self):
        """観測の開始（別スレッドで裏側で動かす）"""
        if self.is_observing: return
        
        self._init_db()
        
        # センサー初期化とチャネル選択
        if gdx_available:
            try:
                # GUIで入力された "1, 2, 3" のような文字列を数値のリストに変換
                ch_list = [int(c.strip()) for c in self.channels.get().split(',')]
                self.device = gdx.gdx()
                self.device.open(connection='usb')
                self.device.select_sensors(ch_list)  # ここでGUIの設定を適用
                self.device.start(period=8)  # 128Hz (約8ms)
            except Exception as e:
                messagebox.showwarning("センサー警告", f"センサーの初期化に失敗しました。デモモード（模擬データ）で動作します。\n詳細: {e}")
                self.device = None
        else:
            self.device = None
            
        # UIの表示切り替え
        self.is_observing = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_label.config(text="ステータス: 観測中 (128Hz)", foreground="red")
        
        # 観測ループを「別スレッド」で開始（画面をフリーズさせないため）
        self.observation_thread = threading.Thread(target=self.observation_loop, daemon=True)
        self.observation_thread.start()
        
        # グラフ更新のループを「メインスレッド」で開始
        self.update_graph()

    def stop_observation(self):
        """観測の終了"""
        self.is_observing = False
        
        if self.device:
            try:
                self.device.stop()
                self.device.close()
            except:
                pass
            self.device = None
            
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_label.config(text="ステータス: 待機中", foreground="blue")

    def observation_loop(self):
        """1秒ごとにデータを集めてDBに保存するループ（裏側のスレッドで動作）"""
        while self.is_observing:
            start_time, wind, hum, press = self.collect_one_second_data()
            self.save_to_db(start_time, wind, hum, press)
            
            # グラフ描画用に、最新の1秒分のデータをクラス変数にコピー
            self.latest_time = list(range(self.sampling_rate)) # X軸は0〜127のサンプル番号
            self.latest_wind = wind
            self.latest_hum = hum
            self.latest_press = press

    def collect_one_second_data(self):
        """1秒間（128回）の高速サンプリング"""
        wind_list, hum_list, press_list = [], [], []
        start_time = pd.Timestamp.now()
        
        for _ in range(self.sampling_rate):
            t_start = time.perf_counter()
            
            if self.device:
                measurements = self.device.read()
                w = measurements[0] if len(measurements) > 0 else 0.0
                h = measurements[1] if len(measurements) > 1 else 0.0
                p = measurements[2] if len(measurements) > 2 else 0.0
            else:
                # デモモード
                w = 2.5 + random.uniform(-0.4, 0.4)
                h = 55.0 + random.uniform(-1.0, 1.0)
                p = 1013.2 + random.uniform(-0.1, 0.1)
            
            wind_list.append(w)
            hum_list.append(h)
            press_list.append(p)
            
            t_elapsed = time.perf_counter() - t_start
            t_sleep = self.interval - t_elapsed
            if t_sleep > 0:
                time.sleep(t_sleep)
                
        return start_time, wind_list, hum_list, press_list

    def save_to_db(self, start_time, wind, humidity, pressure):
        """Pandasによる一括バルクインサート"""
        timestamps = pd.date_range(start=start_time, periods=self.sampling_rate, freq='7.8125ms')
        df = pd.DataFrame({
            'sample_time': timestamps,
            'wind_speed': wind,
            'humidity': humidity,
            'pressure': pressure
        })
        df['sample_time'] = df['sample_time'].dt.strftime('%Y-%m-%d %H:%M:%S.%f').str[:-3]
        
        conn = sqlite3.connect(self.db_path.get())
        df.to_sql('weather_samples', con=conn, if_exists='append', index=False)
        conn.close()

    def update_graph(self):
        """1秒おきにグラフを再描画する（表側のメインスレッドで動作）"""
        if not self.is_observing:
            return
            
        # 最新データが存在する場合のみ描画
        if self.latest_wind:
            self.ax1.clear()
            self.ax2.clear()
            self.ax3.clear()
            
            self.ax1.plot(self.latest_time, self.latest_wind, color='blue', linewidth=1)
            self.ax1.set_title("Wind Speed (m/s)", fontsize=10, pad=3)
            
            self.ax2.plot(self.latest_time, self.latest_hum, color='green', linewidth=1)
            self.ax2.set_title("Humidity (%)", fontsize=10, pad=3)
            
            self.ax3.plot(self.latest_time, self.latest_press, color='red', linewidth=1)
            self.ax3.set_title("Pressure (hPa)", fontsize=10, pad=3)
            
            self.canvas.draw()
            
        # 1000ミリ秒（1秒）後に自分自身をもう一度呼び出す
        self.root.after(1000, self.update_graph)

if __name__ == "__main__":
    root = tk.Tk()
    app = WeatherObservationApp(root)
    # ウィンドウを閉じた時に安全に終了させる処理
    root.protocol("WM_DELETE_WINDOW", lambda: (app.stop_observation(), root.destroy()))
    root.mainloop()