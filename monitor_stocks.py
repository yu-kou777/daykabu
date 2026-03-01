import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import time
import io
import os
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# --- 設定 ---
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

def calculate_rci(series, period):
    n = period
    rank_period = pd.Series(range(n, 0, -1))
    def rci_func(x):
        d = ((pd.Series(x).rank(ascending=False) - rank_period)**2).sum()
        return (1 - (6 * d) / (n * (n**2 - 1))) * 100
    return series.rolling(window=n).apply(rci_func)

def is_peak_down(series):
    if len(series) < 4: return False
    return (series.iloc[-2] > series.iloc[-3]) and (series.iloc[-2] > series.iloc[-1])

def is_trough_up(series):
    if len(series) < 4: return False
    return (series.iloc[-2] < series.iloc[-3]) and (series.iloc[-2] < series.iloc[-1])

def get_latest_prime_list():
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        base_url = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
        res = requests.get(base_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        xls_path = ""
        for a in soup.find_all('a', href=True):
            if 'data_j.xls' in a['href']:
                xls_path = a['href']
                break
        if not xls_path: raise Exception("Excelリンク未検出")
        full_url = "https://www.jpx.co.jp" + xls_path
        resp = requests.get(full_url, headers=headers)
        df = pd.read_excel(io.BytesIO(resp.content), dtype={'コード': str})
        prime_df = df[df['市場・商品区分'].str.contains('プライム', na=False)]
        return {f"{row['コード']}.T": row['銘柄名'] for _, row in prime_df.iterrows()}
    except:
        return {"9101.T": "日本郵船", "6481.T": "THK"}

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    now_str = datetime.now(jst).strftime('%H:%M')
    ticker_map = get_latest_prime_list()
    ticker_list = list(ticker_map.keys())
    
    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🚀 **哨戒開始({len(ticker_list)}社)** ({now_str})"})

    # --- 改良：分割ダウンロード ---
    chunk_size = 400
    all_data = pd.DataFrame()
    for i in range(0, len(ticker_list), chunk_size):
        chunk = ticker_list[i : i + chunk_size]
        print(f"📦 スキャン中... {i} ～ {i+len(chunk)}")
        data_chunk = yf.download(chunk, period="6mo", interval="1d", group_by='ticker', threads=True)
        all_data = pd.concat([all_data, data_chunk], axis=1)
        time.sleep(5) # 5秒休憩してBANを防ぐ

    found_count = 0
    for ticker in ticker_list:
        try:
            df = all_data[ticker].dropna()
            if len(df) < 30: continue
            df.ta.rsi(length=14, append=True)
            df['RCI9'] = calculate_rci(df['Close'], 9)
            df['RCI26'] = calculate_rci(df['Close'], 26)
            curr, prev = df.iloc[-1], df.iloc[-2]

            peak_down = is_peak_down(df['RSI_14']) and is_peak_down(df['RCI9'])
            trough_up = is_trough_up(df['RSI_14']) and is_trough_up(df['RCI9'])
            gc = (prev['RCI9'] <= prev['RCI26']) and (curr['RCI9'] > curr['RCI26'])
            dc = (prev['RCI9'] >= prev['RCI26']) and (curr['RCI9'] < curr['RCI26'])

            signal = None
            reason = []
            if peak_down or dc:
                signal = "🔻【売り警戒】"
                if peak_down: reason.append("RSI/RCI同期山")
                if dc: reason.append("RCIデッドクロス")
            elif trough_up or gc:
                signal = "🔥【買い検討】"
                if trough_up: reason.append("RSI/RCI同期谷")
                if gc: reason.append("RCIゴールデンクロス")

            if signal:
                found_count += 1
                content = f"🦅 **{signal}**\n**{ticker_map[ticker]}({ticker})**\n└ 価格: {int(curr['Close'])}円 / RSI: {round(curr['RSI_14'], 1)}\n└ 理由: {' / '.join(reason)}"
                requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
                time.sleep(1)
        except:
            continue

    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"✅ **哨戒完了** 合致: {found_count}件"})

