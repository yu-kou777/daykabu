import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import time
import os
from datetime import datetime, timedelta, timezone

# --- 設定 ---
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"
LIST_FILE = "prime_list.csv"

def calculate_rci(series, period):
    n = period
    rank_period = pd.Series(range(n, 0, -1))
    def rci_func(x):
        d = ((pd.Series(x).rank(ascending=False) - rank_period)**2).sum()
        return (1 - (6 * d) / (n * (n**2 - 1))) * 100
    return series.rolling(window=n).apply(rci_func)

def is_peak_down(series):
    """
    山(ピークダウン)の判定
    昨日(-2)が、その前日(-3)と当日(-1)より高いこと
    または一昨日(-3)が山であること
    """
    if len(series) < 4: return False
    # 昨日がピークの場合
    p1 = (series.iloc[-2] > series.iloc[-3]) and (series.iloc[-2] > series.iloc[-1])
    # 一昨日がピークの場合
    p2 = (series.iloc[-3] > series.iloc[-4]) and (series.iloc[-3] > series.iloc[-2])
    return p1 or p2

def is_trough_up(series):
    """
    谷(ボトムアップ)の判定
    昨日(-2)が、その前日(-3)と当日(-1)より低いこと
    または一昨日(-3)が谷であること
    """
    if len(series) < 4: return False
    t1 = (series.iloc[-2] < series.iloc[-3]) and (series.iloc[-2] < series.iloc[-1])
    t2 = (series.iloc[-3] < series.iloc[-4]) and (series.iloc[-3] < series.iloc[-2])
    return t1 or t2

def load_local_list():
    if os.path.exists(LIST_FILE):
        df = pd.read_csv(LIST_FILE)
        return {f"{int(row['コード'])}.T": row['銘柄名'] for _, row in df.iterrows()}
    return None

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    now_str = datetime.now(jst).strftime('%H:%M')
    
    ticker_map = load_local_list()
    if not ticker_map:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": "🚨 prime_list.csv が見つかりません。"})
        exit()

    ticker_list = list(ticker_map.keys())
    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🚀 **ダブル・ピーク/クロス哨戒開始** ({now_str})"})

    all_data = yf.download(ticker_list, period="6mo", interval="1d", group_by='ticker', threads=True)

    found_count = 0
    for ticker in ticker_list:
        try:
            df = all_data[ticker].dropna()
            if len(df) < 30: continue

            # 指標計算
            df.ta.rsi(length=14, append=True)
            df['RCI9'] = calculate_rci(df['Close'], 9)
            df['RCI26'] = calculate_rci(df['Close'], 26)
            
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            # --- 複合条件判定 ---
            signal = None
            reason = []

            # 1. ダブル・ピークダウン (RSI山 AND RCI山) -> 売り警戒
            if is_peak_down(df['RSI_14']) and is_peak_down(df['RCI9']):
                signal = "🔻【ダブルピーク/売り警戒】"
                reason.append("RSI & RCI 同期山")
            
            # 2. ダブル・ボトムアップ (RSI谷 AND RCI谷) -> 買い検討
            elif is_trough_up(df['RSI_14']) and is_trough_up(df['RCI9']):
                signal = "🔥【ダブルボトム/買い検討】"
                reason.append("RSI & RCI 同期谷")
            
            # 3. RCIクロス (単独でも検知)
            if (prev['RCI9'] <= prev['RCI26']) and (curr['RCI9'] > curr['RCI26']):
                if not signal: signal = "✨【RCIゴールデンクロス】"
                reason.append("RCI GC")
            elif (prev['RCI9'] >= prev['RCI26']) and (curr['RCI9'] < curr['RCI26']):
                if not signal: signal = "⚠️【RCIデッドクロス】"
                reason.append("RCI DC")

            if signal:
                found_count += 1
                content = (
                    f"🦅 **{signal}**\n"
                    f"**{ticker_map[ticker.replace('.T','')]}({ticker})**\n"
                    f"└ 価格: {int(curr['Close'])}円 / RSI: {round(curr['RSI_14'], 1)}\n"
                    f"└ RCI短期: {round(curr['RCI9'], 1)} / 長期: {round(curr['RCI26'], 1)}\n"
                    f"└ 検知理由: {' / '.join(reason)}"
                )
                requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
                time.sleep(1)
        except:
            continue

    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"✅ **哨戒完了** ({now_str}) 合致: {found_count}件"})
