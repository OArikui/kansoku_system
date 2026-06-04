import glob
import os
import cv2
import numpy as np
import pandas as pd
import sqlite3
from picture_analysis import get_cam_status ,min2 ,get_west_direction ,get_size

def get_pic_info(pic_path):
    cam_status = get_cam_status(pic_path)#これは辞書型
    min2_value = min2(pic_path)
    west_direction = get_west_direction(pic_path)
    size = get_size(pic_path)
    return list(cam_status.values()) + [min2_value, west_direction, size]

if __name__ == "__main__":
    setting={i.split("=")[0] : i.split("=")[1] for i in open(__file__.replace("edit_database.py","setting.txt"),mode="r",encoding="UTF-8").read().split("\n")}
    pictfolders=os.listdir(setting["current_pic_path"])
    DB_FILE = setting["database_path"]
    columns = setting["camstat_colums"].split(",") + setting["otherphoto_columns"].split(",")
    for pictfolder in pictfolders:
        pic_pathes = glob.glob(os.path.join(setting["current_pic_path"],pictfolder,f"*.{setting['pic_extension']}"))
        databases={c:[] for c in columns}
        for pic_path in pic_pathes:
            pic=cv2.imread(pic_path,cv2.IMREAD_UNCHANGED)
            pic_info = get_pic_info(pic_path)
            for i, column in enumerate(columns):
                databases[column].append(pic_info[i])
        df = pd.DataFrame(databases)
        conn = sqlite3.connect(DB_FILE)
        df.to_sql("photos", conn, if_exists="append", index=False        )
        conn.close()
    for weather_path in glob.glob(os.path.join(setting["verniers_path"],"*.db")):
        df = pd.read_sql("SELECT * FROM verniers", sqlite3.connect(weather_path))
        conn = sqlite3.connect(DB_FILE)
        df.to_sql("verniers", conn, if_exists="append", index=False)
        conn.close()
    print("データベースへの保存が完了しました。")
    print(f"DBファイルは{DB_FILE}に保存されました。")