import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import requests
import time
import io
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# --- 設定 ---
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

def calculate_rci(series, period):
    n = period
    def rci_func(x):
        if len(x) < n: return np.nan
        price_ranks = pd.Series(x).rank(ascending=False).values
        time_ranks = np.arange(n, 0, -1)
        d2 = np.sum((price_ranks - time_ranks)**2)
        return (1 - (6 * d2) / (n * (n**2 - 1))) * 100
    return series.rolling(window=n).apply(rci_func)

def get_latest_prime_list():
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        base_url = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
        res = requests.get(base_url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        xls_url = next(("https://www.jpx.co.jp" + a['href'] for a in soup.find_all('a', href=True) if 'data_j.xls' in a['href']), "")
        resp = requests.get(xls_url or "https://www.jpx.co.jp/markets/statistics-banner/quote/01_data_j.xls", headers=headers, timeout=20)
        df = pd.read_excel(io.BytesIO(resp.content), dtype={'コード': str})
        prime_df = df[df['市場・商品区分'].str.contains('プライム', na=False)]
        return {f"{row['コード']}.T": row['銘柄名'] for _, row in prime_df.iterrows()}
    except:
        return {"5016.T": "ＪＸ金属", "6481.T": "THK"}

def send_discord(title, stock_list):
    if not stock_list: return
    header = f"**【{title}】**\n"
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
    
    # 開始通知
    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🚀 **高速パトロール開始** ({len(ticker_list)}銘柄)"})

    up_signals, down_signals = [], []
    total_scanned = 0

    # 【改善1】チャンクサイズを800に拡大
    chunk_size = 800
    all_data = pd.DataFrame()
    for i in range(0, len(ticker_list), chunk_size):
        chunk = ticker_list[i : i + chunk_size]
        try:
            # 【改善2】threads=True に戻して並列ダウンロード
            data_chunk = yf.download(chunk, period="2y", interval="1d", group_by='ticker', threads=True, progress=False)
            if not data_chunk.empty:
                all_data = pd.concat([all_data, data_chunk], axis=1)
        except Exception as e:
            print(f"Error: {e}")
        # 【改善3】待機時間を2秒に短縮
        time.sleep(2)

    for ticker in ticker_list:
        try:
            if ticker not in all_data.columns.get_level_values(0): continue
            df = all_data[ticker].dropna()
            if len(df) < 201: continue
            
            curr = df.iloc[-1]
            price = int(curr['Close'])

            # 厳選フィルター（条件は維持）
            if not (3000 < price <= 30000): continue
            avg_value = (df['Close'] * df['Volume']).tail(25).mean()
            if avg_value < 1_500_000_000: continue
            avg_volatility = ((df['High'] - df['Low']) / df['Close']).tail(25).mean()
            if avg_volatility < 0.020: continue

            total_scanned += 1

            # テクニカル指標（精密計算は維持）
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['RCI9'] = calculate_rci(df['Close'], 9)
            df['MA5'] = ta.sma(df['Close'], length=5)
            df['MA20'] = ta.sma(df['Close'], length=20)
            df['MA60'] = ta.sma(df['Close'], length=60)
            df['MA200'] = ta.sma(df['Close'], length=200)
            
            curr, prev = df.iloc[-1], df.iloc[-2]

            is_uptrend = curr['MA5'] > curr['MA20'] > curr['MA60'] > curr['MA200']
            is_downtrend = curr['MA5'] < curr['MA20'] < curr['MA60'] < curr['MA200']

            tokubai = (curr['RSI'] <= 10 and curr['RCI9'] <= -70)
            kaimashi = ((curr['RSI'] <= 20 and curr['RCI9'] <= -50) or (prev['RSI'] <= 20 and prev['RCI9'] <= -50))
            rikaku = (curr['RCI9'] >= 95 and curr['RSI'] >= 90)

            if tokubai or kaimashi or rikaku:
                vol_spike = curr['Volume'] > (df['Volume'].tail(5).mean() * 1.2)
                spike = "⚡" if vol_spike else ""
                tag = f"🚨{spike}【特買い】" if tokubai else (f"✨{spike}【買い増し】" if kaimashi else f"💰{spike}【利確】")
                
                info = f"{tag} {ticker_map[ticker]}({ticker}) : {price}円 [RCI:{int(curr['RCI9'])} RSI:{int(curr['RSI'])}]\n└ [📈 チャート](https://finance.yahoo.co.jp/quote/{ticker})"
                
                if is_uptrend: up_signals.append(f"📈上昇中 ➔ {info}")
                elif is_downtrend: down_signals.append(f"📉下降中 ➔ {info}")

        except:
            continue

    final_msg = f"📊 **哨戒完了**\n厳選通過: {total_scanned} 社 / 合致: {len(up_signals) + len(down_signals)} 件"
    requests.post(DISCORD_WEBHOOK_URL, json={"content": final_msg})

    send_discord("🔥 強上昇トレンド × シグナル", up_signals)
    send_discord("🌪️ 強下降トレンド × シグナル", down_signals)
