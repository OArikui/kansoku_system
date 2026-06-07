import glob
import os

def get_cam_status(text,contents):
    # ここにカメラの状態を取得するコードを実装してください
    if type(text) == str:
        txt = {line.split("=")[0]: line.split("=")[1] for line in open(text, "r").read().split("\n") if "=" in line}
    elif type(text) == 'TextIOWrapper':
        txt = {line.split("=")[0]: line.split("=")[1] for line in text.read().split("\n") if "=" in line}
    re={}
    for c in contents:
        re[c] = txt.get(c, "cant_find")  # カラムに対応する値を取得、存在しない場合は"N/A"を返す
    return re

def min2(pic):#ver1.0 https://github.com/fujitenmon-coder/seeing/releases/tag/MIN2_ver1.0

def seeing():

def get_west_direction(pic):#多重露光による事後解析系太陽東西取得を採択する場合
    pass
