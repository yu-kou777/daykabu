import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import time
import os  # ファイル確認に必要
from datetime import datetime, timedelta, timezone

# --- 設定 ---
# ご指定のDiscord Webhook URLを統合済み
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

def calculate_rci(series, period):
    """RCI(順位相関指数)を計算する関数"""
    n = period
    rank_period = pd.Series(range(n, 0, -1))
    def rci_func(x):
        d = ((pd.Series(x).rank(ascending=False) - rank_period)**2).sum()
        return (1 - (6 * d) / (n * (n**2 - 1))) * 100
    return series.rolling(window=n).apply(rci_func)

def get_prime_tickers():
    """プライム市場の銘柄リストを取得"""
    # 実行フォルダに prime_list.csv がある場合はそれを読み込む
    if os.path.exists('prime_list.csv'):
        df = pd.read_csv('prime_list.csv')
        return {f"{str(c).split('.')[0]}.T": n for c, n in zip(df['コード'], df['銘柄名'])}
    
    # CSVがない場合のテスト用リスト
    return {
        "9101.T": "日本郵船", "8035.T": "東エレク", 
        "9984.T": "ソフトバンクG", "7203.T": "トヨタ",
        "5401.T": "日本製鉄", "8306.T": "三菱UFJ"
    }

def analyze_stock(ticker, name):
    try:
        tkr = yf.Ticker(ticker)
        # 指標計算に必要な期間（200日移動平均のため1年以上）
        df = tkr.
