import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import datetime
import sqlite3
import pandas as pd
import random
import re
import logging
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# ログ設定: ファイルに保存
logging.basicConfig(
    filename='observation.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

try:
    import gdx
    gdx_available = True
except ImportError:
    gdx_available = False

class WeatherObservationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("天体観測 気象データ収集システム")
        self.root.geometry("850x800")
        
        self.db_path = tk.StringVar(value="solar_observation.db")
        self.table_name = tk.StringVar(value="weather_samples")
        self.device_setting = tk.StringVar(value="")
        self.sampling_rate_var = tk.StringVar(value="128 Hz")
        self.is_observing = False
        self.device = None
        self.ch_vars = {}
        self.ch_info_map = {}
        self.total_saved_count = 0
        
        # GUIと初期化の呼び出しを一本化
        self._build_gui()
        self.setup_initial_channels()
        self._init_db()
        
        logging.info("--- システムが正常に起動しました ---")
        self.log_event("システム起動完了")

    def log_event(self, message):
        """画面表示とログファイル記録を両立"""
        logging.info(message)
        self.log_label.config(text=message)

    def browse_file(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".db", filetypes=[("SQLite Database", "*.db")])
        if filepath:
            self.db_path.set(filepath)
            self.log_event(f"データベースファイルを読み込み/設定しました: {filepath}")

    def connect_device(self):
        """デバイス接続処理"""
        if gdx_available:
            try:
                if self.device: self.device.close()
                self.device = gdx.gdx()
                target = self.device_setting.get().strip()
                self.device.open(connection='usb', device_to_open=target if target else None)
                
                info_list = self.device.sensor_info()
                self.device_label.config(text=f"デバイス接続済み: {target or 'Auto'}", foreground="green")
                self.log_event(f"デバイスに接続しました: {target or 'Auto'}")
                self.build_dynamic_checkboxes(info_list)
            except Exception as e:
                self.log_event(f"デバイス接続失敗: {e}")
                messagebox.showerror("接続エラー", str(e))
        else:
            self.log_event("gdxライブラリ非対応のためデモモードで動作します")
            self.setup_initial_channels()

    def _init_db(self, target_table=None):
        """テーブル作成・選択処理"""
        table = target_table or self.table_name.get().strip()
        conn = sqlite3.connect(self.db_path.get())
        
        selected_cols = []
        for ch_num, var in self.ch_vars.items():
            if var.get():
                name = self.to_valid_column_name(self.ch_info_map[ch_num])
                selected_cols.append(f"{name} REAL")
        
        if not selected_cols: selected_cols = ["ch_default REAL"]
        
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} (sample_time TEXT PRIMARY KEY, {', '.join(selected_cols)})")
        conn.close()
        self.log_event(f"テーブル '{table}' を作成/選択しました。")

    def switch_table(self):
        """クイックテーブル切り替え処理"""
        new_table = self.table_name.get().strip()
        if not new_table:
            messagebox.showwarning("警告", "テーブル名を入力してください。")
            return
        self._init_db(new_table)
        self.total_saved_count = 0
        self.counter_label.config(text=f"総保存件数: 0 件")








    def __init__(self, root):
        self.root = root
        self.root.title("天体観測 気象データ収集システム")
        self.root.geometry("850x800")
        
        # --- システム変数 ---
        self.db_path = tk.StringVar(value="solar_observation.db")
        self.table_name = tk.StringVar(value="weather_samples")
        self.device_setting = tk.StringVar(value="")
        self.sampling_rate_var = tk.StringVar(value="128 Hz")
        
        self.is_observing = False
        self.observation_thread = None
        self.device = None
        
        # チャンネル管理用変数
        self.ch_vars = {}     
        self.ch_info_map = {} 
        self.selected_channels = []
        
        self.sampling_rate = 128
        self.interval = 1.0 / self.sampling_rate
        
        self.latest_time = []
        self.latest_buffers = {}
        self.total_saved_count = 0
        
        # GUI構築
        self._build_gui()
        self.setup_initial_channels()
        self._init_db()


    def _build_gui(self):
        # (前回のUI構築コードと同じ内容です)
        control_frame = ttk.LabelFrame(self.root, text="観測設定・コントロール", padding=10)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(control_frame, text="保存先 DB:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(control_frame, textvariable=self.db_path, width=35).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Button(control_frame, text="参照...", command=self.browse_file).grid(row=0, column=2, sticky=tk.W, padx=5)
        
        ttk.Label(control_frame, text="テーブル名:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.entry_table = ttk.Entry(control_frame, textvariable=self.table_name, width=35)
        self.entry_table.grid(row=1, column=1, sticky=tk.W, padx=5)
        self.btn_switch_table = ttk.Button(control_frame, text="切替 / 新規作成", command=self.switch_table)
        self.btn_switch_table.grid(row=1, column=2, sticky=tk.W, padx=5)
        
        ttk.Label(control_frame, text="接続デバイスID:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.entry_device = ttk.Entry(control_frame, textvariable=self.device_setting, width=35)
        self.entry_device.grid(row=2, column=1, sticky=tk.W, padx=5)
        self.btn_connect = ttk.Button(control_frame, text="接続 & チャネル取得", command=self.connect_device)
        self.btn_connect.grid(row=2, column=2, sticky=tk.W, padx=5)
        
        ttk.Label(control_frame, text="サンプリング周波数:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.combo_rate = ttk.Combobox(control_frame, textvariable=self.sampling_rate_var, values=["1 Hz", "10 Hz", "50 Hz", "100 Hz", "128 Hz"], width=15, state="readonly")
        self.combo_rate.grid(row=3, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(control_frame, text="使用チャネル:").grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.ch_frame = ttk.Frame(control_frame)
        self.ch_frame.grid(row=4, column=1, columnspan=3, sticky=tk.W, padx=5, pady=5)
        
        btn_frame = ttk.Frame(control_frame)
        btn_frame.grid(row=5, column=0, columnspan=4, pady=10)
        
        self.btn_start = ttk.Button(btn_frame, text="▶ 観測開始", command=self.start_observation, width=15)
        self.btn_start.pack(side=tk.LEFT, padx=10)
        
        self.btn_stop = ttk.Button(btn_frame, text="■ 観測終了", command=self.stop_observation, state=tk.DISABLED, width=15)
        self.btn_stop.pack(side=tk.LEFT, padx=10)
        
        self.status_label = ttk.Label(btn_frame, text="ステータス: 待機中", foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=20)

        # グラフとステータスバーの設定は省略（前回のコードと同じです）
        self.graph_label_frame = ttk.LabelFrame(self.root, text="リアルタイム観測データ", padding=5)
        self.graph_label_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.fig = Figure(figsize=(8, 4.5), dpi=100)
        self.ax1 = self.fig.add_subplot(311)
        self.ax2 = self.fig.add_subplot(312)
        self.ax3 = self.fig.add_subplot(313)
        self.fig.tight_layout(pad=2.5)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_label_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", side="bottom", padx=10, pady=5)
        self.lamp_canvas = tk.Canvas(status_frame, width=16, height=16, bg=self.root.cget("bg"), bd=0, highlightthickness=0)
        self.lamp_canvas.pack(side="left", padx=5)
        self.lamp = self.lamp_canvas.create_oval(2, 2, 14, 14, fill="gray", outline="")
        self.log_label = ttk.Label(status_frame, text="準備完了", anchor="w")
        self.log_label.pack(side="left", fill="x", expand=True, padx=5)
        self.counter_label = ttk.Label(status_frame, text=f"総保存件数: {self.total_saved_count} 件")
        self.counter_label.pack(side="right", padx=5)
        self.device_label = ttk.Label(status_frame, text="デバイス: 未接続", foreground="darkorange", font=("", 9, "bold"))
        self.device_label.pack(side="right", padx=15)

    def setup_initial_channels(self):
        """起動時のデフォルト候補（擬似気象センサー構成）を表示"""
        default_info = [
            "1 - Wind Speed (m/s)",
            "2 - Relative Humidity (%)",
            "3 - Barometric Pressure (hPa)",
            "4 - Temperature (°C)"
        ]
        self.build_dynamic_checkboxes(default_info)

    def build_dynamic_checkboxes(self, info_list):
        """取得したチャンネル文字列リストからチェックボックス群を動的生成（2列マトリックス配置）"""
        for widget in self.ch_frame.winfo_children():
            widget.destroy()
            
        self.ch_info_map.clear()
        self.ch_vars.clear()
        
        for i, info in enumerate(info_list):
            try:
                # "1 - Wind Speed" から先頭の数字をチャンネルIDとして抽出
                ch_num = int(info.split('-')[0].strip())
            except:
                continue
                
            # 最初の3つのセンサーをデフォルトでチェック状態にする
            default_state = True if i < 3 else False
            var = tk.BooleanVar(value=default_state)
            
            self.ch_vars[ch_num] = var
            self.ch_info_map[ch_num] = info
            
            cb = ttk.Checkbutton(self.ch_frame, text=info, variable=var)
            row = i // 2  # 2列構成で見やすく配置
            col = i % 2
            cb.grid(row=row, column=col, sticky=tk.W, padx=10, pady=2)
            
        self.log_label.config(text=f"デバイスから {len(self.ch_info_map)} 個の利用可能なチャンネルをマッピングしました。")

    def to_valid_column_name(self, text):
        """チャンネル情報文字列をSQLiteで安全に使えるカラム名に変換"""
        match = re.match(r"(\d+)\s*-\s*([^(\n]+)", text)
        if match:
            ch = match.group(1)
            name = match.group(2).strip().replace(" ", "_")
            name = re.sub(r'[^a-zA-Z0-9_]', '', name)
            return f"ch{ch}_{name}"
        else:
            return re.sub(r'[^a-zA-Z0-9_]', '_', text)



    def start_observation(self):
        """観測開始処理"""
        self.selected_channels = [ch for ch, var in self.ch_vars.items() if var.get()]
        if not self.selected_channels:
            messagebox.showwarning("警告", "チャネルを選択してください")
            return

        self.log_event(f"観測を開始しました。対象テーブル: {self.table_name.get()}")
        # 選択されたチャンネルを確定
        self.selected_channels = [ch for ch, var in self.ch_vars.items() if var.get()]
        if not self.selected_channels:
            messagebox.showwarning("警告", "少なくとも1つのチャネルにチェックを入れてください。")
            return

        # 周波数の計算
        try:
            self.sampling_rate = int(self.sampling_rate_var.get().split()[0])
            self.interval = 1.0 / self.sampling_rate
        except:
            self.sampling_rate = 128
            self.interval = 1.0 / 128

        # 確定したチャンネルでDBを初期化・接続確認
        self._init_db()
        disp_device_name = "未接続"
        
        # 事前に接続ボタンを押さずに開始した場合の自動検出フォールバック
        if gdx_available and self.device is None:
            try:
                self.device = gdx.gdx()
                target_device = self.device_setting.get().strip()
                if target_device:
                    self.device.open(connection='usb', device_to_open=target_device)
                    disp_device_name = target_device
                else:
                    self.device.open(connection='usb')
                    disp_device_name = "USB自動検出デバイス"
            except:
                self.device = None
        elif self.device is not None:
            disp_device_name = self.device_setting.get().strip() or "USB接続デバイス"
            
        if self.device:
            try:
                self.device.select_sensors(self.selected_channels)
                period_ms = max(1, int(1000 / self.sampling_rate))
                self.device.start(period=period_ms)
                self.device_label.config(text=f"デバイス: {disp_device_name} (観測中)", foreground="green")
            except Exception as e:
                messagebox.showwarning("センサーエラー", f"センサーの同期開始に失敗しました。デモ動作へ移行します。\n詳細: {e}")
                self.device = None
                disp_device_name = "デモモード（エラー回避）"
                self.device_label.config(text="デバイス: デモモード", foreground="darkorange")
        else:
            disp_device_name = "デモモード"
            self.device_label.config(text="デバイス: デモモード", foreground="darkorange")
            
        # UIロックの実行
        self.is_observing = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.entry_table.config(state=tk.DISABLED)
        self.btn_switch_table.config(state=tk.DISABLED)
        self.entry_device.config(state=tk.DISABLED)
        self.btn_connect.config(state=tk.DISABLED)
        self.combo_rate.config(state=tk.DISABLED)
        
        for widget in self.ch_frame.winfo_children():
            if isinstance(widget, ttk.Checkbutton):
                widget.config(state=tk.DISABLED)
        
        self.status_label.config(text=f"ステータス: 観測中 ({self.sampling_rate}Hz)", foreground="red")
        self.graph_label_frame.config(text=f"リアルタイム観測データ (最新1秒間 / {self.sampling_rate}サンプリング)")
        self.log_label.config(text=f"テーブル '{self.table_name.get()}' へストリーミング中...")
        
        # 描画用データバッファの初期化
        self.latest_buffers = {ch: [] for ch in self.selected_channels}
        
        # 観測処理スレッドの起動
        self.observation_thread = threading.Thread(target=self.observation_loop, daemon=True)
        self.observation_thread.start()
        self.update_graph()

    def stop_observation(self):
        """観測終了処理"""
        self.is_observing = False
        self.log_event("観測を終了しました。")
            
        # UIロックの解除
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.entry_table.config(state=tk.NORMAL)
        self.btn_switch_table.config(state=tk.NORMAL)
        self.entry_device.config(state=tk.NORMAL)
        self.btn_connect.config(state=tk.NORMAL)
        self.combo_rate.config(state="readonly")
        
        for widget in self.ch_frame.winfo_children():
            if isinstance(widget, ttk.Checkbutton):
                widget.config(state=tk.NORMAL)
        
        self.status_label.config(text="ステータス: 待機中", foreground="blue")
        self.log_label.config(text="観測を停止しました。データは安全にSQLiteへ書き込まれました。")
        if self.device:
            self.device_label.config(text="デバイス: 接続維持 (待機中)", foreground="green")
        else:
            self.device_label.config(text="デバイス: 未接続", foreground="darkorange")

    def observation_loop(self):
        """バックグラウンドの高速サンプリングループ"""
        while self.is_observing:
            start_time, data_dict = self.collect_one_second_data()
            self.save_to_db(start_time, data_dict)
            
            self.latest_time = list(range(self.sampling_rate))
            self.latest_buffers = data_dict

    def collect_one_second_data(self):
        """1秒分のデータを収集"""
        data_dict = {ch: [] for ch in self.selected_channels}
        start_time = pd.Timestamp.now()
        
        for _ in range(self.sampling_rate):
            t_start = time.perf_counter()
            
            if self.device:
                try:
                    measurements = self.device.read()
                except:
                    measurements = []
                for idx, ch in enumerate(self.selected_channels):
                    val = measurements[idx] if idx < len(measurements) else 0.0
                    data_dict[ch].append(val)
            else:
                # デモモード用のスマートモックデータ
                for ch in self.selected_channels:
                    if ch == 1: val = 2.5 + random.uniform(-0.4, 0.4)
                    elif ch == 2: val = 55.0 + random.uniform(-1.0, 1.0)
                    elif ch == 3: val = 1013.2 + random.uniform(-0.1, 0.1)
                    else: val = 18.5 + random.uniform(-0.2, 0.2)
                    data_dict[ch].append(val)
            
            t_elapsed = time.perf_counter() - t_start
            t_sleep = self.interval - t_elapsed
            if t_sleep > 0:
                time.sleep(t_sleep)
                
        return start_time, data_dict

    def save_to_db(self, start_time, data_dict):
        """動的カラムによる一括バルクインサート"""
        freq_str = f"{self.interval * 1000:.4f}ms"
        timestamps = pd.date_range(start=start_time, periods=self.sampling_rate, freq=freq_str)
        
        df_data = {'sample_time': timestamps}
        for ch in self.selected_channels:
            info = self.ch_info_map[ch]
            col_name = self.to_valid_column_name(info)
            df_data[col_name] = data_dict[ch]
            
        df = pd.DataFrame(df_data)
        df['sample_time'] = df['sample_time'].dt.strftime('%Y-%m-%d %H:%M:%S.%f').str[:-3]
        
        current_table = self.table_name.get().strip()
        
        conn = sqlite3.connect(self.db_path.get())
        df.to_sql(current_table, con=conn, if_exists='append', index=False)
        conn.close()

        self.total_saved_count += self.sampling_rate
        self.root.after(0, self._update_status_bar)

    def _update_status_bar(self):
        """アクセスランプと保存カウンタの同期"""
        self.lamp_canvas.itemconfig(self.lamp, fill="lime green")
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_label.config(text=f"[{now_str}] テーブル '{self.table_name.get()}' へ {self.sampling_rate} 件一括保存完了")
        self.counter_label.config(text=f"総保存件数: {self.total_saved_count} 件")
        self.root.after(150, lambda: self.lamp_canvas.itemconfig(self.lamp, fill="gray"))

    def update_graph(self):
        """3連マルチプロットへのリアルタイムマッピング"""
        if not self.is_observing:
            return
            
        if self.latest_buffers and any(self.latest_buffers.values()):
            self.ax1.clear()
            self.ax2.clear()
            self.ax3.clear()
            
            axes = [self.ax1, self.ax2, self.ax3]
            colors = ['blue', 'green', 'red']
            
            # 選択されたチャンネルのうち、最初の3つを上から順にグラフへプロット
            for idx, ch in enumerate(self.selected_channels[:3]):
                ax = axes[idx]
                y_data = self.latest_buffers.get(ch, [])
                title_text = self.ch_info_map.get(ch, f"Channel {ch}")
                
                if y_data:
                    ax.plot(self.latest_time, y_data, color=colors[idx], linewidth=1)
                    ax.set_title(title_text, fontsize=10, pad=3)
            
            # 選択数が3に満たない空きスロットの処理
            for idx in range(len(self.selected_channels[:3]), 3):
                axes[idx].text(0.5, 0.5, "- 未選択スロット -", ha='center', va='center', color='gray')
                
            self.canvas.draw()
            
        self.root.after(1000, self.update_graph)

    def close_app(self):
        self.stop_observation()
        if self.device: self.device.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = WeatherObservationApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close_app)
    root.mainloop()