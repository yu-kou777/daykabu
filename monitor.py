import yfinance as yf
import pandas as pd
import time
import requests
from datetime import datetime, time as dt_time, timezone, timedelta

# ==========================================
# 🛠️ 設定：ExcelとDiscord
# ==========================================
EXCEL_FILE = "list.xlsx"
COLUMN_NAME = "銘柄コード"
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme
"

notified_history = {}

def load_tickers():
    try:
        df = pd.read_excel(EXCEL_FILE)
        return [str(t) + ".T" if ".T" not in str(t) else str(t) for t in df[COLUMN_NAME].dropna()]
    except: return []

def is_market_open():
    """日本株の開催時間（前場・後場）か判定"""
    now = datetime.now(timezone(timedelta(hours=9))).time()
    # 前場: 09:00 - 12:00
    zenba = (now >= dt_time(9, 0) and now <= dt_time(12, 0))
    # 後場: 12:30 - 15:00
    goba = (now >= dt_time(12, 30) and now <= dt_time(15, 0))
    return zenba or goba

def monitor():
    print("🦅 1分足・デイトレ監視ボット稼働中...")
    
    while True:
        if not is_market_open():
            print("💤 市場時間外または昼休みのため待機中...")
            time.sleep(60)
            continue

        tickers = load_tickers()
        for ticker in tickers:
            try:
                # 🚀 1分足データを取得 (yfinanceの制限で直近7日分のみ取得可能)
                df = yf.Ticker(ticker).history(period="1d", interval="1m")
                if len(df) < 20: continue
                
                curr_p = df['Close'].iloc[-1]
                
                # --- 1分足専用判定ロジック ---
                # 1. 10分間の騰落率 (急騰 > 1.2%, 急落 < -1.2%)
                change = (df['Close'].iloc[-1] - df['Close'].iloc[-10]) / df['Close'].iloc[-10]
                
                # 2. 3分間のヨコヨコ判定 (値幅が0.2%以内)
                is_square = (df['High'].tail(3).max() - df['Low'].tail(3).min()) / curr_p < 0.002
                
                # 3. MACD判定
                ema12, ema26 = df['Close'].ewm(span=12).mean(), df['Close'].ewm(span=26).mean()
                macd = ema12 - ema26
                signal = macd.ewm(span=9).mean()

                # --- 通知 ---
                msg = ""
                key = ""
                
                # 買いチャンス：急騰 ＋ ヨコヨコ ＋ MACD上向き
                if change > 0.012 and is_square and macd.iloc[-1] > signal.iloc[-1]:
                    msg = f"🚀 **【1分足・急騰】 {ticker}**\nヨコヨコで力を溜めています。ブレイク間近！\n現在値: {int(curr_p)}円"
                    key = "BUY"
                
                # 空売りチャンス：急落 ＋ ヨコヨコ ＋ MACD下向き
                elif change < -0.012 and is_square and macd.iloc[-1] < signal.iloc[-1]:
                    msg = f"📉 **【1分足・急落】 {ticker}**\n下げ止まりからの続落予兆。空売り準備！\n現在値: {int(curr_p)}円"
                    key = "SELL"

                if msg:
                    hist_key = f"{ticker}_{key}"
                    last_time = notified_history.get(hist_key)
                    if last_time is None or (datetime.now() - last_time) > timedelta(minutes=30):
                        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg})
                        notified_history[hist_key] = datetime.now()
                        print(f"✅ 通知: {ticker}")

            except Exception as e:
                print(f"エラー ({ticker}): {e}")

        # 1分ごとにループ
        time.sleep(60)

if __name__ == "__main__":
    monitor()