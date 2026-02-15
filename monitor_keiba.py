import sys
import requests
from bs4 import BeautifulSoup

def start_monitor(race_id):
    print(f"ターゲットレース: {race_id}")
    # ここに競馬ラボ等の解析コードが入ります
    print("データ収集を開始します...")
    # テスト用の出力
    print("【2/15 東京11R】JS軸馬: 13, 3, 12 を抽出しました（シミュレーション）")

if __name__ == "__main__":
    # 実行時にレースIDを受け取る
    race_id = sys.argv[1] if len(sys.argv) > 1 else "なし"
    start_monitor(race_id)
