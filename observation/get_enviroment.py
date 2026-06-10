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
        self.root.geometry("800x720") # 高さをわずかに調整
        
        # --- システム変数 ---
        self.db_path = tk.StringVar(value="solar_observation.db")
        self.table_name = tk.StringVar(value="weather_samples")
        self.device_setting = tk.StringVar(value="")  # 【追加】デバイスID指定用の変数
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
        ttk.Entry(control_frame, textvariable=self.db_path, width=45).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Button(control_frame, text="参照...", command=self.browse_file).grid(row=0, column=2, sticky=tk.W)
        
        # 1-2. テーブル名の設定（クイック切替機能）
        ttk.Label(control_frame, text="テーブル名:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.entry_table = ttk.Entry(control_frame, textvariable=self.table_name, width=30)
        self.entry_table.grid(row=1, column=1, sticky=tk.W, padx=5)
        self.btn_switch_table = ttk.Button(control_frame, text="切替 / 新規作成", command=self.switch_table)
        self.btn_switch_table.grid(row=1, column=2, sticky=tk.W)
        
        # 1-3. 【追加】観測デバイスの指定
        ttk.Label(control_frame, text="接続デバイスID:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.entry_device = ttk.Entry(control_frame, textvariable=self.device_setting, width=30)
        self.entry_device.grid(row=2, column=1, sticky=tk.W, padx=5)
        ttk.Label(control_frame, text="※空欄でUSB自動検出 (例: GDX-ACC 01100123)").grid(row=2, column=2, sticky=tk.W)
        
        # 1-4. センサーチャネルの選択
        ttk.Label(control_frame, text="使用チャネル:").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(control_frame, textvariable=self.channels, width=20).grid(row=3, column=1, sticky=tk.W, padx=5)
        ttk.Label(control_frame, text="※例: 1, 2, 3 (風速,湿度,気圧)").grid(row=3, column=2, sticky=tk.W)
        
        # 1-5. 操作ボタン
        btn_frame = ttk.Frame(control_frame)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=10)
        
        self.btn_start = ttk.Button(btn_frame, text="▶ 観測開始", command=self.start_observation, width=15)
        self.btn_start.pack(side=tk.LEFT, padx=10)
        
        self.btn_stop = ttk.Button(btn_frame, text="■ 観測終了", command=self.stop_observation, state=tk.DISABLED, width=15)
        self.btn_stop.pack(side=tk.LEFT, padx=10)
        
        self.status_label = ttk.Label(btn_frame, text="ステータス: 待機中", foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=20)

        # 2. グラフパネル（中央部）
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

        # 3. ステータスバー用のフレームを最下部に配置
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", side="bottom", padx=10, pady=5)

        # ① 擬似アクセスランプ
        self.lamp_canvas = tk.Canvas(status_frame, width=16, height=16, bg=self.root.cget("bg"), bd=0, highlightthickness=0)
        self.lamp_canvas.pack(side="left", padx=5)
        self.lamp = self.lamp_canvas.create_oval(2, 2, 14, 14, fill="gray", outline="")

        # ② ステータスラベル
        self.log_label = ttk.Label(status_frame, text="観測データ収集 待機中...", anchor="w")
        self.log_label.pack(side="left", fill="x", expand=True, padx=5)

        # ③ 総保存件数カウンター
        self.counter_label = ttk.Label(status_frame, text=f"総保存件数: {self.total_saved_count} 件")
        self.counter_label.pack(side="right", padx=5)

        # ④ 【追加】使用デバイス表示ラベル
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
            messagebox.showwarning("警告", "観測中はテーブルの変更ができません。先に観測を停止してください。")
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
        """観測の開始（別スレッドで裏側で動かす）"""
        if self.is_observing: return
        
        self._init_db()
        disp_device_name = "未接続"
        
        # センサー初期化とチャネル選択
        if gdx_available:
            try:
                ch_list = [int(c.strip()) for c in self.channels.get().split(',')]
                self.device = gdx.gdx()
                
                # 【修正】デバイス指定の判定
                target_device = self.device_setting.get().strip()
                if target_device:
                    # デバイスIDが指定されている場合
                    self.device.open(connection='usb', device_to_open=target_device)
                    disp_device_name = target_device
                else:
                    # 空欄の場合は自動検出
                    self.device.open(connection='usb')
                    disp_device_name = "USB自動検出デバイス"
                    
                self.device.select_sensors(ch_list)
                self.device.start(period=8)
            except Exception as e:
                messagebox.showwarning("センサー警告", f"センサーの初期化に失敗しました。デモモード（模擬データ）で動作します。\n詳細: {e}")
                self.device = None
                disp_device_name = "デモモード（模擬データ）"
        else:
            self.device = None
            disp_device_name = "デモモード（非サポート環境）"
            
        # UIの表示切り替え（各種設定をロック）
        self.is_observing = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.entry_table.config(state=tk.DISABLED)
        self.btn_switch_table.config(state=tk.DISABLED)
        self.entry_device.config(state=tk.DISABLED) # デバイス指定欄をロック
        
        self.status_label.config(text="ステータス: 観測中 (128Hz)", foreground="red")
        self.log_label.config(text=f"テーブル '{self.table_name.get()}' に保存を開始しました...")
        
        # 【追加】ステータスバーに現在のデバイス名を表示
        self.device_label.config(text=f"デバイス: {disp_device_name}", foreground="green")
        
        # 観測ループを「別スレッド」で開始
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
            
        # UIのロック解除
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.entry_table.config(state=tk.NORMAL)
        self.btn_switch_table.config(state=tk.NORMAL)
        self.entry_device.config(state=tk.NORMAL) # デバイス指定欄のロック解除
        
        self.status_label.config(text="ステータス: 待機中", foreground="blue")
        self.log_label.config(text="観測を停止しました。")
        
        # 【追加】デバイス表示を未接続に戻す
        self.device_label.config(text="デバイス: 未接続", foreground="darkorange")

    def observation_loop(self):
        """1秒ごとにデータを集めてDBに保存するループ（裏側のスレッドで動作）"""
        while self.is_observing:
            start_time, wind, hum, press = self.collect_one_second_data()
            self.save_to_db(start_time, wind, hum, press)
            
            # グラフ描画用に、最新の1秒分のデータをクラス変数にコピー
            self.latest_time = list(range(self.sampling_rate))
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