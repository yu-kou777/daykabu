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
    
    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🚀 **トレンド＆反転哨戒開始({len(ticker_list)}社)** ({now_str})"})

    # 分割ダウンロードでBAN対策
    chunk_size = 400
    all_data = pd.DataFrame()
    for i in range(0, len(ticker_list), chunk_size):
        chunk = ticker_list[i : i + chunk_size]
        data_chunk = yf.download(chunk, period="6mo", interval="1d", group_by='ticker', threads=True)
        all_data = pd.concat([all_data, data_chunk], axis=1)
        time.sleep(5)

    found_count = 0
    for ticker in ticker_list:
        try:
            df = all_data[ticker].dropna()
            if len(df) < 61: continue # MA60のために長めのデータが必要

            # 指標計算
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['RCI9'] = calculate_rci(df['Close'], 9)
            df['MA5'] = ta.sma(df['Close'], length=5)
            df['MA20'] = ta.sma(df['Close'], length=20)
            df['MA60'] = ta.sma(df['Close'], length=60)
            
            curr = df.iloc[-1]
            prev = df.iloc[-2]

            signal = None
            reason = []

            # 1. 逆張り/過熱条件 (優先)
            if curr['RCI9'] <= -50:
                signal = "🔵【買い検討(安値圏)】"
                reason.append("RCI -50以下")
            elif curr['RCI9'] >= 95 and curr['RSI'] >= 90:
                signal = "💰【利確準備(過熱)】"
                reason.append("RCI95以上 & RSI90以上")
            
            # 2. 上記に当てはまらない場合、トレンドを判定
            else:
                ma_rising = (curr['MA5'] > prev['MA5']) and (curr['MA20'] > prev['MA20']) and (curr['MA60'] > prev['MA60'])
                ma_falling = (curr['MA5'] < prev['MA5']) and (curr['MA20'] < prev['MA20']) and (curr['MA60'] < prev['MA60'])
                
                if ma_rising:
                    signal = "🔥【強い買い(三役上昇)】"
                    reason.append("MA5/20/60 すべて上昇")
                elif ma_falling:
                    signal = "💀【強い売り(三役下降)】"
                    reason.append("MA5/20/60 すべて下降")

            if signal:
                found_count += 1
                content = (
                    f"🦅 **{signal}**\n"
                    f"**{ticker_map[ticker]}({ticker})**\n"
                    f"└ 価格: {int(curr['Close'])}円 / RSI: {round(curr['RSI'], 1)}\n"
                    f"└ 理由: {' / '.join(reason)}"
                )
                requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
                time.sleep(1)
        except:
            continue

    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"✅ **哨戒完了** 合致: {found_count}件"})
