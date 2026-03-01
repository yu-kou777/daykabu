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
    
    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🚀 **厳選・長期トレンド哨戒開始({len(ticker_list)}社)** ({now_str})"})

    chunk_size = 400
    all_data = pd.DataFrame()
    for i in range(0, len(ticker_list), chunk_size):
        chunk = ticker_list[i : i + chunk_size]
        # MA200計算のため期間を2年に延長
        data_chunk = yf.download(chunk, period="2y", interval="1d", group_by='ticker', threads=True)
        all_data = pd.concat([all_data, data_chunk], axis=1)
        time.sleep(5)

    found_count = 0
    for ticker in ticker_list:
        try:
            df = all_data[ticker].dropna()
            if len(df) < 201: continue

            curr_price = df['Close'].iloc[-1]
            
            # 【追加条件】5円刻みの価格帯（3,001円〜30,000円）に絞り込み
            if not (3000 < curr_price <= 30000):
                continue

            # 指標計算
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['RCI9'] = calculate_rci(df['Close'], 9)
            df['MA5'] = ta.sma(df['Close'], length=5)
            df['MA20'] = ta.sma(df['Close'], length=20)
            df['MA60'] = ta.sma(df['Close'], length=60)
            df['MA200'] = ta.sma(df['Close'], length=200)
            
            curr = df.iloc[-1]
            prev = df.iloc[-2]

            signal = None
            reason = []

            # 1. 逆張り/過熱条件
            if curr['RCI9'] <= -50:
                signal = "🔵【買い検討(安値圏)】"
                reason.append("RCI -50以下")
            elif curr['RCI9'] >= 95 and curr['RSI'] >= 90:
                signal = "💰【利確準備(過熱)】"
                reason.append("RCI95以上 & RSI90以上")
            
            # 2. 長期トレンド判定（MA200を含むパーフェクトオーダーの上昇/下降）
            else:
                # すべてのMAが前日より上昇
                ma_rising = all([curr[ma] > prev[ma] for ma in ['MA5', 'MA20', 'MA60', 'MA200']])
                # すべてのMAが前日より下降
                ma_falling = all([curr[ma] < prev[ma] for ma in ['MA5', 'MA20', 'MA60', 'MA200']])
                
                if ma_rising:
                    signal = "💎【極・買い(200日込上昇)】"
                    reason.append("全MA(5/20/60/200)上昇")
                elif ma_falling:
                    signal = "🌪️【極・売り(200日込下降)】"
                    reason.append("全MA(5/20/60/200)下降")

            if signal:
                found_count += 1
                content = (
                    f"🦅 **{signal}**\n"
                    f"**{ticker_map[ticker]}({ticker})**\n"
                    f"└ 価格: {int(curr_price)}円 / RSI: {round(curr['RSI'], 1)}\n"
                    f"└ 理由: {' / '.join(reason)}"
                )
                requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
                time.sleep(1)
        except:
            continue

    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"✅ **厳選哨戒完了** 合致: {found_count}件"})
