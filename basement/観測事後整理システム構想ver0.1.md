# 観測後自動整理システムの設計ver0.1

実用できる最低ライン(観測写真のフォルダパスを受け取って、その写真についての各種情報を整理する)





### 〇基本使用形態

#### 使用手順



(0.)観測時に独自作成の気象条件観測システムで気象条件を観測

1. after\_kansoku.exeを実行
2. 観測データパスの取得※
3. 保存先を設定※
4. 実行
5. 保存先にデータベースが保存される(SQL形式)
6. 必要に応じてdb→xslxに複製変換してエンドユーザーも閲覧できるようにします。(foolproofのために一方通行です)



after\_kansoku.exeではMIN2,seeing\_allframeの実行も行います。

※については、その内容をsetting.txtで設定できるようにします。

#### 

#### 生データの構成

**E:.**

└─observed\_result

&#x20;   │  environ\_yy-mm-dd-tt.txt

&#x20;   │  weather\_results.db

&#x20;   │

&#x20;   └─pictures

&#x20;       ├─001

&#x20;       │      00001.tiff

&#x20;       │      00002.tiff

&#x20;       │      00001.txt

&#x20;       │      00002.txt

&#x20;       │

&#x20;       └─002

&#x20;               00001.txt

&#x20;               00001.tiff

&#x20;               00002.tiff

&#x20;               00002.txt

この形式を想定して作製します。



### 〇データベースの構造

###### photos:写真準拠のデータを写真に紐づけて保管(観測は、各写真の撮影データが必要なのでtiff撮影でおこなう)

* camera\_stat(撮影時に生成されるtxtfile)
* 写真のパス
* 撮影時刻(time stomp)
* 解析結果(MIN2,seeing\_allframe)



###### verniers:気象条件のデータを保管(観測写真と、fps,タイミングが微妙に異なるため。また、気象条件のみに焦点を当てる場合もあるため)

* 観測時刻(time stomp)
* 各種数値(湿度、気圧...etc)



→写真と気象条件を組み合わせるときは、time stompでbetween検索する。



### 〇コードの構造

**E:.**

**├─basement**

**│      sql\_sample.py**

**│      pandas\_sample.py**

**│      testDB.db**

**│      実装したいこと.md**

**│      観測事後整理システム構想ver0.1.md**

**│**

**├─observation**

**│      get\_enviroment.py**

**│      west\_solar.py**

**│**

**└─main**

&#x20;       **picture\_analysis.py**

&#x20;       **setting.txt**

&#x20;       **edit\_database.py**

##### **main**

* ###### setting.txt

savepathやpicpath,ゆくゆくはoptionを保存しています。これらはデータの読み書きの際に使われます。

* ###### picture\_analysis.py

camera\_statやMIN2,allframeの処理を行います。モジュール化します

* ###### edit\_database.py

一番メインですヨ

全体の司令塔の役割になります。



##### **observation**

* ###### get\_envioment.py

気象条件の観測をします。一時できなDBに書き込んで保存し、あとで吸い上げてもらって保存するつもりです。デバイスや時刻を保存します。

* ###### west\_solar.py

撮影時に、太陽の東西を検出するために使います。之については、多重露光をするものとどちらが良いかは要検討です。(afterだとピクセルが汚い)



##### **basement**

* ###### sql\_sample.py

pythonでsqlを用いた初歩的なデータベース操作です。デモなので実際の処理系とは異なる場合があります。

* ###### pandas\_sample.py

pythonでpandasを用いた初歩的なデータベース操作です。デモなので実際の処理系とは異なる場合があります。

* ###### testDB.db

上記pandas\_sample.pyで作られるdbfileです

* ###### 実装したいこと.md\*\*

追加したい機能や修正したいことを書きます。主にUI,UXについてです。

* ###### 観測事後整理システム構想ver0.1.md\*\*

本文ですが、ほぼREADMEに近いです。実装したいこと.md を参考にしながら構想を練ります。



### 〇たすく

* 画像解析ソフトの作成(MIN2,seeing\_allframe内包でＳＱＬを吐き出す)
* camera\_statの展開ソフトの作成
* vernierのデータ収集ソフトの作成(観測機器、観測時間などを詳細に記録)
* db\_to\_xslsの複製変換ソフトの作成
* 太陽の東西検出ソフトの作成

