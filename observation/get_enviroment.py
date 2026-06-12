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
        # ログ: プログラムが実行されたことをログに記録
        logging.info("--- プログラムが実行されました (システム起動開始) ---")
        
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
        
        # ★ カウンター制御用変数（10から0まで0.1秒刻みで減算し誤差を回避）
        self.countdown_ticks = 10
        
        # GUI構築と初期化
        self._build_gui()
        self.setup_initial_channels()
        self._init_db()
        
        logging.info("--- システムが正常に起動しました ---")
        self.log_event("システム起動完了")
        
        # ログ: 初期状態のデモモード表示を適用
        self.update_device_status_display()

    def log_event(self, message):
        """画面表示とログファイル記録を両立"""
        logging.info(message)
        self.log_label.config(text=message)

    def update_device_status_display(self):
        """デモモードの場合はGUIにデモモードとわかるように表示"""
        if self.device is None:
            if self.is_observing:
                self.device_label.config(text="【デモモード】擬似データ観測中", foreground="darkorange")
                self.root.title("天体観測 気象データ収集システム (デモモード稼働中)")
            else:
                self.device_label.config(text="【デモモード】デバイス未接続", foreground="darkorange")
                self.root.title("天体観測 気象データ収集システム (デモモード)")
        else:
            if self.is_observing:
                self.device_label.config(text="【本番モード】デバイス接続・観測中", foreground="green")
                self.root.title("天体観測 気象データ収集システム (本番観測中)")
            else:
                self.device_label.config(text="【本番モード】デバイス接続・待機中", foreground="green")
                self.root.title("天体観測 気象データ収集システム")

    def browse_file(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".db", filetypes=[("SQLite Database", "*.db")])
        if filepath:
            self.db_path.set(filepath)
            # ログ: 保存先を指定したさいにログに記録
            logging.info(f"保存先データベースファイルが指定されました: {filepath}")
            self.log_event(f"データベースファイルを読み込み/設定しました: {filepath}")

    def connect_device(self):
        """デバイス接続処理"""
        if gdx_available:
            try:
                if self.device: 
                    self.device.close()
                self.device = gdx.gdx()
                target = self.device_setting.get().strip()
                self.device.open(connection='usb', device_to_open=target if target else None)
                
                info_list = self.device.sensor_info()
                logging.info(f"デバイスに正常に接続しました。ターゲット: {target or 'Auto'}")
                self.log_event(f"デバイスに接続しました: {target or 'Auto'}")
                self.build_dynamic_checkboxes(info_list)
                self.update_device_status_display()
            except Exception as e:
                # ログ: エラーをログに記録
                logging.error(f"デバイス接続失敗: {e}", exc_info=True)
                self.log_event(f"デバイス接続失敗: {e}")
                messagebox.showerror("接続エラー", str(e))
                self.device = None
                self.update_device_status_display()
        else:
            # ログ: デモモード開始時にログに記録
            logging.info("gdxライブラリ非対応のため、デモモード動作として準備します。")
            self.log_event("gdxライブラリ非対応のためデモモードで動作します")
            self.setup_initial_channels()
            self.update_device_status_display()

    def _init_db(self, target_table=None):
        """テーブル作成・選択処理"""
        table = target_table or self.table_name.get().strip()
        try:
            conn = sqlite3.connect(self.db_path.get())
            
            selected_cols = []
            for ch_num, var in self.ch_vars.items():
                if var.get():
                    name = self.to_valid_column_name(self.ch_info_map[ch_num])
                    selected_cols.append(f"{name} REAL")
            
            if not selected_cols: 
                selected_cols = ["ch_default REAL"]
            
            # ログ: テーブルの作成をログに記録
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table} (sample_time TEXT PRIMARY KEY, {', '.join(selected_cols)})")
            conn.close()
            
            logging.info(f"SQLiteテーブル '{table}' の作成/存在確認が完了しました。")
            self.log_event(f"テーブル '{table}' を作成/選択しました。")
        except Exception as e:
            # ログ: エラーをログに記録
            logging.error(f"データベース初期化エラー (テーブル: {table}): {e}", exc_info=True)
            self.log_event(f"DB初期化エラー: {e}")

    def switch_table(self):
        """クイックテーブル切り替え処理"""
        new_table = self.table_name.get().strip()
        if not new_table:
            messagebox.showwarning("警告", "テーブル名を入力してください。")
            return
        # ログ: テーブルの選択をログに記録
        logging.info(f"テーブルの切り替え/選択が指定されました: {new_table}")
        self._init_db(new_table)
        self.total_saved_count = 0
        self.counter_label.config(text=f"総保存件数: 0 件")

    def _build_gui(self):
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
        
        # ★ カウンター表示用ラベルを追加 (右側ステータスに配置)
        self.timer_label = ttk.Label(status_frame, text="次回更新まで: - 秒", foreground="purple", font=("", 9, "bold"))
        self.timer_label.pack(side="right", padx=10)
        
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
        """取得したチャンネル文字列リストからチェックボックス群を動的生成"""
        for widget in self.ch_frame.winfo_children():
            widget.destroy()
            
        self.ch_info_map.clear()
        self.ch_vars.clear()
        
        for i, info in enumerate(info_list):
            try:
                ch_num = int(info.split('-')[0].strip())
            except Exception as e:
                logging.error(f"チャンネル情報解析エラー ({info}): {e}", exc_info=True)
                continue
                
            default_state = True if i < 3 else False
            var = tk.BooleanVar(value=default_state)
            
            self.ch_vars[ch_num] = var
            self.ch_info_map[ch_num] = info
            
            cb = ttk.Checkbutton(self.ch_frame, text=info, variable=var)
            row = i // 2
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
            messagebox.showwarning("警告", "少なくとも1つのチャネルにチェックを入れてください。")
            return

        # ログ: 観測開始時にアクティブなセンサーチャネルをログに記録
        active_channels_log = [self.ch_info_map[ch] for ch in self.selected_channels]
        logging.info(f"観測開始要求 - アクティブチャネル: {active_channels_log} | 対象テーブル: {self.table_name.get()}")
        self.log_event(f"観測を開始しました。対象テーブル: {self.table_name.get()}")

        try:
            self.sampling_rate = int(self.sampling_rate_var.get().split()[0])
            self.interval = 1.0 / self.sampling_rate
        except Exception as e:
            logging.error(f"周波数設定の解析エラー: {e}。128Hzにフォールバックします。", exc_info=True)
            self.sampling_rate = 128
            self.interval = 1.0 / 128

        self._init_db()
        
        if gdx_available and self.device is None:
            try:
                self.device = gdx.gdx()
                target_device = self.device_setting.get().strip()
                if target_device:
                    self.device.open(connection='usb', device_to_open=target_device)
                else:
                    self.device.open(connection='usb')
            except Exception as e:
                logging.error(f"自動デバイス接続フォールバック失敗: {e}。デモモードで継続します。", exc_info=True)
                self.device = None
            
        if self.device:
            try:
                self.device.select_sensors(self.selected_channels)
                period_ms = max(1, int(1000 / self.sampling_rate))
                self.device.start(period=period_ms)
                logging.info("本番デバイス接続でデータ取得を開始しました。")
            except Exception as e:
                logging.error(f"センサー同期開始エラー: {e}。デモ動作へ移行します。", exc_info=True)
                messagebox.showwarning("センサーエラー", f"センサーの同期開始に失敗しました。デモ動作へ移行します。\n詳細: {e}")
                self.device = None
        
        # ログ: デモモード開始時にログに記録
        if self.device is None:
            logging.info("デモモード（擬似データ生成ループ）で観測を開始しました。")
            
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
        
        self.update_device_status_display()
        
        self.latest_buffers = {ch: [] for ch in self.selected_channels}
        
        # ★ カウンタ（1.0秒＝10個の0.1秒単位）を初期化してループ開始
        self.countdown_ticks = 10
        
        self.observation_thread = threading.Thread(target=self.observation_loop, daemon=True)
        self.observation_thread.start()
        
        # ★ カウントダウンおよびグラフ描画を管理するループを開始
        self.update_timer_loop()

    def stop_observation(self):
        """観測終了処理"""
        if not self.is_observing:
            return
        self.is_observing = False
        logging.info("観測停止処理が呼び出されました。")
        self.log_event("観測を終了しました。")
            
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
        
        # ★ カウンター表示をクリア
        self.timer_label.config(text="次回更新まで: - 秒")
        
        self.update_device_status_display()

    def update_timer_loop(self):
        """★ 1秒間の更新時間を0.1秒単位で正確に減算表示するループ"""
        if not self.is_observing:
            return
            
        # UI上のカウンター表示を更新 (例: 1.0秒, 0.9秒 ...)
        self.timer_label.config(text=f"次回更新まで: {self.countdown_ticks / 10.0:.1f} 秒")
        
        # 0秒に達したら、データを描画（リフレッシュ）してカウントを10に戻す
        if self.countdown_ticks <= 0:
            self.refresh_graph_display()
            self.countdown_ticks = 10
        else:
            self.countdown_ticks -= 1
            
        # 100ミリ秒（0.1秒）後に再帰呼び出し
        self.root.after(100, self.update_timer_loop)

    def refresh_graph_display(self):
        """★ 3連マルチプロットへのリアルタイムマッピング（描画実行）"""
        if self.latest_buffers and any(self.latest_buffers.values()):
            self.ax1.clear()
            self.ax2.clear()
            self.ax3.clear()
            
            axes = [self.ax1, self.ax2, self.ax3]
            colors = ['blue', 'green', 'red']
            
            for idx, ch in enumerate(self.selected_channels[:3]):
                ax = axes[idx]
                y_data = self.latest_buffers.get(ch, [])
                title_text = self.ch_info_map.get(ch, f"Channel {ch}")
                
                if y_data:
                    ax.plot(self.latest_time, y_data, color=colors[idx], linewidth=1)
                    ax.set_title(title_text, fontsize=10, pad=3)
            
            for idx in range(len(self.selected_channels[:3]), 3):
                axes[idx].text(0.5, 0.5, "- 未選択スロット -", ha='center', va='center', color='gray')
                
            self.canvas.draw()

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
                except Exception as e:
                    logging.error(f"デバイスからのデータ読み込みエラー: {e}", exc_info=True)
                    measurements = []
                for idx, ch in enumerate(self.selected_channels):
                    val = measurements[idx] if idx < len(measurements) else 0.0
                    data_dict[ch].append(val)
            else:
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
        try:
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
        except Exception as e:
            logging.error(f"データベース一括保存エラー: {e}", exc_info=True)

    def _update_status_bar(self):
        """アクセスランプと保存カウンタの同期"""
        self.lamp_canvas.itemconfig(self.lamp, fill="lime green")
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_label.config(text=f"[{now_str}] テーブル '{self.table_name.get()}' へ {self.sampling_rate} 件一括保存完了")
        self.counter_label.config(text=f"総保存件数: {self.total_saved_count} 件")
        self.root.after(150, lambda: self.lamp_canvas.itemconfig(self.lamp, fill="gray"))

    def close_app(self):
        # ログ: プログラムが終了したことをログに記録
        logging.info("--- プログラムの終了処理が呼び出されました ---")
        self.stop_observation()
        if self.device: 
            try:
                self.device.close()
            except Exception as e:
                logging.error(f"デバイス切断時のエラー: {e}", exc_info=True)
        logging.info("--- プログラムが正常に終了しました ---")
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = WeatherObservationApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close_app)
    root.mainloop()