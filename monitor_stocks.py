import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import time
import io
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

def send_discord(title, stock_list):
    if not stock_list: return
    header = f"【{title}】\n"
    content = ""
    for item in stock_list:
        if len(content + header + item) > 1900:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": header + content})
            content = ""
        content += item + "\n"
    if content:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": header + content})

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    now_str = datetime.now(jst).strftime('%Y/%m/%d %H:%M')
    ticker_map = get_latest_prime_list()
    ticker_list = list(ticker_map.keys())
    
    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🕵️ **スイング特化型・厳選パトロール開始** ({now_str})"})

    buy_signals, strong_uptrend, profit_take, strong_downtrend = [], [], [], []
    total_scanned = 0

    chunk_size = 400
    all_data = pd.DataFrame()
    for i in range(0, len(ticker_list), chunk_size):
        chunk = ticker_list[i : i + chunk_size]
        data_chunk = yf.download(chunk, period="2y", interval="1d", group_by='ticker', threads=True)
        all_data = pd.concat([all_data, data_chunk], axis=1)
        time.sleep(5)

    for ticker in ticker_list:
        try:
            df = all_data[ticker].dropna()
            if len(df) < 201: continue
            
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            price = int(curr['Close'])

            # --- スイング向け厳選フィルター ---
            # 1. 価格帯（3,001円～30,000円）
            if not (3000 < price <= 30000): continue
            
            # 2. 流動性（直近25日平均売買代金が15億円以上）
            avg_value = (df['Close'] * df['Volume']).tail(25).mean()
            if avg_value < 1_500_000_000: continue
            
            # 3. ボラティリティ（直近25日の平均値幅が2.0%以上）
            avg_volatility = ((df['High'] - df['Low']) / df['Close']).tail(25).mean()
            if avg_volatility < 0.020: continue

            total_scanned += 1 # 厳選フィルターを通過した銘柄をカウント

            # 指標計算
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['RCI9'] = calculate_rci(df['Close'], 9)
            df['MA5'] = ta.sma(df['Close'], length=5)
            df['MA20'] = ta.sma(df['Close'], length=20)
            df['MA60'] = ta.sma(df['Close'], length=60)
            df['MA200'] = ta.sma(df['Close'], length=200)
            
            curr, prev = df.iloc[-1], df.iloc[-2]
            name = ticker_map[ticker]

            is_uptrend = curr['MA5'] > curr['MA20'] > curr['MA60'] > curr['MA200']
            is_downtrend = curr['MA5'] < curr['MA20'] < curr['MA60'] < curr['MA200']

            # シグナル判定
            if is_uptrend and curr['RSI'] < 45 and curr['RCI9'] < -50:
                buy_signals.append(f"✨ {name}({ticker}) : {price}円 (RSI:{round(curr['RSI'],1)})")
            elif curr['RCI9'] > 90 and curr['RSI'] > 80:
                profit_take.append(f"💰 {name}({ticker}) : {price}円 (過熱)")
            elif is_uptrend and curr['MA5'] > prev['MA5']:
                strong_uptrend.append(f"🔥 {name}({ticker}) : {price}円")
            elif is_downtrend:
                strong_downtrend.append(f"💀 {name}({ticker}) : {price}円")

        except:
            continue

    # 最初に件数を報告
    summary = f"📊 **スイング厳選結果**\n対象1,600社中、フィルター通過: **{total_scanned}** 社"
    requests.post(DISCORD_WEBHOOK_URL, json={"content": summary})

    send_discord("✨ 押し目買い候補 (上昇トレンド×安値圏)", buy_signals)
    send_discord("🔥 強い上昇トレンド", strong_uptrend)
    send_discord("💰 利確検討", profit_take)
    send_discord("💀 強い下降トレンド", strong_downtrend)
