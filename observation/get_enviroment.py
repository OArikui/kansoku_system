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
        self.root.title("天体観測 気象データ収集システム")
        self.root.geometry("820x780") # UI追加に伴いサイズを微調整
        
        # --- システム変数 ---
        self.db_path = tk.StringVar(value="solar_observation.db")
        self.table_name = tk.StringVar(value="weather_samples")
        self.device_setting = tk.StringVar(value="")
        self.is_observing = False
        self.observation_thread = None
        self.device = None
        
        # 【追加】サンプリング周波数とチャンネル選択用の変数
        self.sampling_rate_var = tk.StringVar(value="128 Hz")
        self.ch1_var = tk.BooleanVar(value=True)  # Ch 1: 風速
        self.ch2_var = tk.BooleanVar(value=True)  # Ch 2: 湿度
        self.ch3_var = tk.BooleanVar(value=True)  # Ch 3: 気圧
        self.ch4_var = tk.BooleanVar(value=False) # Ch 4: 気温
        
        # 内部計算用変数（デフォルト値）
        self.sampling_rate = 128
        self.interval = 1.0 / self.sampling_rate
        
        # グラフ描画用のデータバッファ（最新の1秒分）
        self.latest_time = []
        self.latest_wind = []
        self.latest_hum = []
        self.latest_press = []
        
        # 累計件数を記憶する変数
        self.total_saved_count = 0
        
        # --- GUIの構築 ---
        self._build_gui()
        self._init_db()

    def _build_gui(self):
        # 1. コントロールパネル（上部）
        control_frame = ttk.LabelFrame(self.root, text="観測設定・コントロール", padding=10)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 1-1. 保存場所の設定
        ttk.Label(control_frame, text="保存先 DB:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(control_frame, textvariable=self.db_path, width=45).grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=5)
        ttk.Button(control_frame, text="参照...", command=self.browse_file).grid(row=0, column=3, sticky=tk.W)
        
        # 1-2. テーブル名の設定
        ttk.Label(control_frame, text="テーブル名:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.entry_table = ttk.Entry(control_frame, textvariable=self.table_name, width=30)
        self.entry_table.grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=5)
        self.btn_switch_table = ttk.Button(control_frame, text="切替 / 新規作成", command=self.switch_table)
        self.btn_switch_table.grid(row=1, column=3, sticky=tk.W)
        
        # 1-3. 観測デバイスの指定
        ttk.Label(control_frame, text="接続デバイスID:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.entry_device = ttk.Entry(control_frame, textvariable=self.device_setting, width=30)
        self.entry_device.grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=5)
        ttk.Label(control_frame, text="※空欄でUSB自動検出").grid(row=2, column=3, sticky=tk.W)
        
        # 1-4. 【追加】サンプリング周波数の設定
        ttk.Label(control_frame, text="サンプリング周波数:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.combo_rate = ttk.Combobox(control_frame, textvariable=self.sampling_rate_var, values=["1 Hz", "10 Hz", "50 Hz", "100 Hz", "128 Hz"], width=12, state="readonly")
        self.combo_rate.grid(row=3, column=1, sticky=tk.W, padx=5)
        
        # 1-5. 【追加】センサーチャネルの選択（日本語/英語併記）
        ttk.Label(control_frame, text="使用チャネル:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.ch_frame = ttk.Frame(control_frame)
        self.ch_frame.grid(row=4, column=1, columnspan=3, sticky=tk.W, padx=5)
        
        self.cb_ch1 = ttk.Checkbutton(self.ch_frame, text="Ch 1: 風速 / Wind Speed", variable=self.ch1_var)
        self.cb_ch1.pack(side=tk.LEFT, padx=5)
        self.cb_ch2 = ttk.Checkbutton(self.ch_frame, text="Ch 2: 湿度 / Relative Humidity", variable=self.ch2_var)
        self.cb_ch2.pack(side=tk.LEFT, padx=5)
        self.cb_ch3 = ttk.Checkbutton(self.ch_frame, text="Ch 3: 気圧 / Barometric Pressure", variable=self.ch3_var)
        self.cb_ch3.pack(side=tk.LEFT, padx=5)
        self.cb_ch4 = ttk.Checkbutton(self.ch_frame, text="Ch 4: 気温 / Temperature", variable=self.ch4_var)
        self.cb_ch4.pack(side=tk.LEFT, padx=5)
        
        # 1-6. 操作ボタン
        btn_frame = ttk.Frame(control_frame)
        btn_frame.grid(row=5, column=0, columnspan=4, pady=10)
        
        self.btn_start = ttk.Button(btn_frame, text="▶ 観測開始", command=self.start_observation, width=15)
        self.btn_start.pack(side=tk.LEFT, padx=10)
        
        self.btn_stop = ttk.Button(btn_frame, text="■ 観測終了", command=self.stop_observation, state=tk.DISABLED, width=15)
        self.btn_stop.pack(side=tk.LEFT, padx=10)
        
        self.status_label = ttk.Label(btn_frame, text="ステータス: 待機中", foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=20)

        # 2. グラフパネル（中央部）
        self.graph_label_frame = ttk.LabelFrame(self.root, text="リアルタイム観測データ (最新1秒間)", padding=5)
        self.graph_label_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.fig = Figure(figsize=(8, 4.5), dpi=100)
        self.ax1 = self.fig.add_subplot(311)
        self.ax2 = self.fig.add_subplot(312)
        self.ax3 = self.fig.add_subplot(313)
        self.fig.tight_layout(pad=3.0)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame if 'graph_frame' in locals() else self.graph_label_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 3. ステータスバー用のフレームを最下部に配置
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", side="bottom", padx=10, pady=5)

        self.lamp_canvas = tk.Canvas(status_frame, width=16, height=16, bg=self.root.cget("bg"), bd=0, highlightthickness=0)
        self.lamp_canvas.pack(side="left", padx=5)
        self.lamp = self.lamp_canvas.create_oval(2, 2, 14, 14, fill="gray", outline="")

        self.log_label = ttk.Label(status_frame, text="観測データ収集 待機中...", anchor="w")
        self.log_label.pack(side="left", fill="x", expand=True, padx=5)

        self.counter_label = ttk.Label(status_frame, text=f"総保存件数: {self.total_saved_count} 件")
        self.counter_label.pack(side="right", padx=5)

        self.device_label = ttk.Label(status_frame, text="デバイス: 未接続", foreground="darkorange", font=("", 9, "bold"))
        self.device_label.pack(side="right", padx=15)

    def browse_file(self):
        """保存場所をダイアログで選択"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")],
            title="データベースの保存先を選択"
        )
        if filepath:
            self.db_path.set(filepath)
            self._init_db()

    def _init_db(self, target_table=None):
        """データベースとテーブルの初期化"""
        if target_table is None:
            target_table = self.table_name.get().strip()
            
        if not target_table:
            target_table = "weather_samples"
            self.table_name.set(target_table)

        conn = sqlite3.connect(self.db_path.get())
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {target_table} (
                sample_time TEXT PRIMARY KEY,
                wind_speed REAL,
                humidity REAL,
                pressure REAL
            )
        """)
        conn.commit()
        conn.close()

    def switch_table(self):
        """テーブルを切り替えて件数をリセットする"""
        if self.is_observing:
            messagebox.showwarning("警告", "観測中はテーブルの変更ができません。")
            return
            
        new_table = self.table_name.get().strip()
        if not new_table:
            messagebox.showwarning("警告", "テーブル名を入力してください。")
            return
            
        try:
            self._init_db(new_table)
            self.total_saved_count = 0
            self.counter_label.config(text=f"総保存件数: {self.total_saved_count} 件")
            self.log_label.config(text=f"保存先テーブルを '{new_table}' に切り替えました。")
        except Exception as e:
            messagebox.showerror("エラー", f"テーブルの作成/切り替えに失敗しました。\n{e}")

    def start_observation(self):
        """観測の開始"""
        if self.is_observing: return
        
        # 【追加】選択されたチャンネルリストの構築
        ch_list = []
        if self.ch1_var.get(): ch_list.append(1)
        if self.ch2_var.get(): ch_list.append(2)
        if self.ch3_var.get(): ch_list.append(3)
        if self.ch4_var.get(): ch_list.append(4)
        
        if not ch_list:
            messagebox.showwarning("警告", "少なくとも1つのチャネルを選択してください。")
            return

        # 【追加】周波数の取得とインターバルの動的計算
        try:
            self.sampling_rate = int(self.sampling_rate_var.get().split()[0])
            self.interval = 1.0 / self.sampling_rate
        except Exception:
            self.sampling_rate = 128
            self.interval = 1.0 / 128

        self._init_db()
        disp_device_name = "未接続"
        
        # センサー初期化とチャネル選択
        if gdx_available:
            try:
                self.device = gdx.gdx()
                target_device = self.device_setting.get().strip()
                if target_device:
                    self.device.open(connection='usb', device_to_open=target_device)
                    disp_device_name = target_device
                else:
                    self.device.open(connection='usb')
                    disp_device_name = "USB自動検出デバイス"
                    
                self.device.select_sensors(ch_list)
                
                # サンプリングレートに合わせて周期（ミリ秒）を計算
                period_ms = max(1, int(1000 / self.sampling_rate))
                self.device.start(period=period_ms)
            except Exception as e:
                messagebox.showwarning("センサー警告", f"センサーの初期化に失敗しました。デモモードで動作します。\n詳細: {e}")
                self.device = None
                disp_device_name = "デモモード（模擬データ）"
        else:
            self.device = None
            disp_device_name = "デモモード（非サポート環境）"
            
        # UIの表示切り替え（各種設定のロック）
        self.is_observing = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.entry_table.config(state=tk.DISABLED)
        self.btn_switch_table.config(state=tk.DISABLED)
        self.entry_device.config(state=tk.DISABLED)
        self.combo_rate.config(state=tk.DISABLED) # 周波数コンボボックスをロック
        
        # チャンネルチェックボックスのロック
        self.cb_ch1.config(state=tk.DISABLED)
        self.cb_ch2.config(state=tk.DISABLED)
        self.cb_ch3.config(state=tk.DISABLED)
        self.cb_ch4.config(state=tk.DISABLED)
        
        self.status_label.config(text=f"ステータス: 観測中 ({self.sampling_rate}Hz)", foreground="red")
        self.graph_label_frame.config(text=f"リアルタイム観測データ (最新1秒間 / {self.sampling_rate}サンプリング)")
        self.log_label.config(text=f"テーブル '{self.table_name.get()}' に保存を開始しました...")
        self.device_label.config(text=f"デバイス: {disp_device_name}", foreground="green")
        
        # 観測ループを別スレッドで開始
        self.observation_thread = threading.Thread(target=self.observation_loop, daemon=True)
        self.observation_thread.start()
        
        # グラフ更新のループをメインスレッドで開始
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
            
        # UIのロック解除
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.entry_table.config(state=tk.NORMAL)
        self.btn_switch_table.config(state=tk.NORMAL)
        self.entry_device.config(state=tk.NORMAL)
        self.combo_rate.config(state="readonly") # 周波数コンボボックスを解除
        
        # チャンネルチェックボックスの解除
        self.cb_ch1.config(state=tk.NORMAL)
        self.cb_ch2.config(state=tk.NORMAL)
        self.cb_ch3.config(state=tk.NORMAL)
        self.cb_ch4.config(state=tk.NORMAL)
        
        self.status_label.config(text="ステータス: 待機中", foreground="blue")
        self.log_label.config(text="観測を停止しました。")
        self.device_label.config(text="デバイス: 未接続", foreground="darkorange")

    def observation_loop(self):
        """1秒ごとにデータを集めてDBに保存するループ"""
        while self.is_observing:
            start_time, wind, hum, press = self.collect_one_second_data()
            self.save_to_db(start_time, wind, hum, press)
            
            # グラフ描画用に、最新の1秒分のデータをクラス変数にコピー
            self.latest_time = list(range(self.sampling_rate))
            self.latest_wind = wind
            self.latest_hum = hum
            self.latest_press = press

    def collect_one_second_data(self):
        """1秒間指定された周波数分（サンプリングレート回）の高速サンプリング"""
        wind_list, hum_list, press_list = [], [], []
        start_time = pd.Timestamp.now()
        
        for _ in range(self.sampling_rate):
            t_start = time.perf_counter()
            
            if self.device:
                measurements = self.device.read()
                # 選択状態によって配列インデックスが変わるのを防ぐため安全に取得
                w = measurements[0] if len(measurements) > 0 else 0.0
                h = measurements[1] if len(measurements) > 1 else 0.0
                p = measurements[2] if len(measurements) > 2 else 0.0
            else:
                # デモモード用の模擬データ
                w = 2.5 + random.uniform(-0.4, 0.4) if self.ch1_var.get() else 0.0
                h = 55.0 + random.uniform(-1.0, 1.0) if self.ch2_var.get() else 0.0
                p = 1013.2 + random.uniform(-0.1, 0.1) if self.ch3_var.get() else 0.0
            
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
        # 選択された周波数(サンプリングレート)に基づいて正確な時間軸を生成
        freq_str = f"{self.interval * 1000:.4f}ms"
        timestamps = pd.date_range(start=start_time, periods=self.sampling_rate, freq=freq_str)
        
        df = pd.DataFrame({
            'sample_time': timestamps,
            'wind_speed': wind,
            'humidity': humidity,
            'pressure': pressure
        })
        df['sample_time'] = df['sample_time'].dt.strftime('%Y-%m-%d %H:%M:%S.%f').str[:-3]
        
        current_table = self.table_name.get().strip()
        
        conn = sqlite3.connect(self.db_path.get())
        df.to_sql(current_table, con=conn, if_exists='append', index=False)
        conn.close()

        self.total_saved_count += self.sampling_rate
        self.root.after(0, self._update_status_bar)

    def _update_status_bar(self):
        """ステータスバーの表示を更新"""
        self.lamp_canvas.itemconfig(self.lamp, fill="lime green")
        
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_label.config(text=f"[{now_str}] テーブル '{self.table_name.get()}' へ {self.sampling_rate} 件保存しました")
        self.counter_label.config(text=f"総保存件数: {self.total_saved_count} 件")
        
        self.root.after(150, lambda: self.lamp_canvas.itemconfig(self.lamp, fill="gray"))

    def update_graph(self):
        """1秒おきにグラフを再描画する"""
        if not self.is_observing:
            return
            
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
            
        self.root.after(1000, self.update_graph)


if __name__ == "__main__":
    root = tk.Tk()
    app = WeatherObservationApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.stop_observation(), root.destroy()))
    root.mainloop()