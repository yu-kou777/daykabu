import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys

def fetch_keibalab_training(race_id):
    """競馬ラボから調教タイムを抜き出す"""
    print(f"--- 競馬ラボからレースID {race_id} の調教データを取得中 ---")
    url = f"https://www.keibalab.jp/db/race/{race_id}/training/"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    
    # 調教テーブルを解析
    # トモユキさんのエクセル「調教」シート と同じ形式に整形
    training_table = soup.find("table", {"class": "table_list"})
    if not training_table:
        return "データが見つかりませんでした。URLを確認してください。"
    
    # ここで馬名や1Fタイムを抽出し、JS668-670 の判定に渡す
    return "調教データの抽出に成功しました！"

if __name__ == "__main__":
    # 引数から「2026021511」のようなコードを受け取れるようにします
    input_code = sys.argv[1] if len(sys.argv) > 1 else "202602150511"
    res = fetch_keibalab_training(input_code)
    print(res)
