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
    """RCIの計算（精密版）"""
    n = period
    def rci_func(x):
        if len(x) < n: return np.nan
        price_ranks = pd.Series(x).rank(ascending=False).values
        time_ranks = np.arange(n, 0, -1)
        d2 = np.sum((price_ranks - time_ranks)**2)
        return (1 - (6 * d2) / (n * (n**2 - 1))) * 100
    return series.rolling(window=n).apply(rci_func)

def get_latest_prime_list():
    """JPXからプライム銘柄リストを高速取得"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        url = "https://www.jpx.co.jp/markets/statistics-banner/quote/01_data_j.xls"
        resp = requests.get(url, headers=headers, timeout=10)
        df = pd.read_excel(io.BytesIO(resp.content), dtype={'コード': str})
        prime_df = df[df['市場・商品区分'].str.contains('プライム', na=False)]
        return {f"{row['コード']}.T": row['銘柄名'] for _, row in prime_df.iterrows()}
    except:
        # 取得失敗時のフォールバック
        return {"5016.T": "ＪＸ金属", "6481.T": "THK"}

def send_discord(title, stock_list):
    """Discordへの通知送信（長文分割対応）"""
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
    now_str = datetime.now(jst).strftime('%H:%M')
    ticker_map = get_latest_prime_list()
    ticker_list = list(ticker_map.keys())
    
    print(f"Patrol started at {now_str}")

    up_signals, down_signals = [], []
    total_scanned = 0

    # 500件ずつ一括ダウンロード（速度と安定のバランス）
    chunk_size = 500
    all_data = pd.DataFrame()
    for i in range(0, len(ticker_list), chunk_size):
        chunk = ticker_list[i : i + chunk_size]
        data_chunk = yf.download(chunk, period="2y", interval="1d", group_by='ticker', threads=True, progress=False)
        all_data = pd.concat([all_data, data_chunk], axis=1)
        time.sleep(3)

    for ticker in ticker_list:
        try:
            df = all_data[ticker].dropna()
            if len(df) < 201: continue
            
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            price = int(curr['Close'])

            # 1. 母集団フィルター（3k-30k / 15億以上 / ボラ2%以上）
            if not (3000 < price <= 30000): continue
            avg_value = (df['Close'] * df['Volume']).tail(25).mean()
            if avg_value < 1_500_000_000: continue
            avg_volatility = ((df['High'] - df['Low']) / df['Close']).tail(25).mean()
            if avg_volatility < 0.020: continue

            total_scanned += 1

            # 2. テクニカル指標計算
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['RCI9'] = calculate_rci(df['Close'], 9)
            df['MA5'] = ta.sma(df['Close'], length=5)
            df['MA20'] = ta.sma(df['Close'], length=20)
            df['MA60'] = ta.sma(df['Close'], length=60)
            df['MA200'] = ta.sma(df['Close'], length=200)
            
            curr = df.iloc[-1]
            prev = df.iloc[-2]

            # 3. トレンド判定（パーフェクトオーダー）
            is_uptrend = curr['MA5'] > curr['MA20'] > curr['MA60'] > curr['MA200']
            is_downtrend = curr['MA5'] < curr['MA20'] < curr['MA60'] < curr['MA200']

            # 4. シグナル判定
            tokubai = (curr['RSI'] <= 10 and curr['RCI9'] <= -70)
            kaimashi = ((curr['RSI'] <= 20 and curr['RCI9'] <= -50) or (prev['RSI'] <= 20 and prev['RCI9'] <= -50))
            rikaku = (curr['RCI9'] >= 95 and curr['RSI'] >= 80)

            if tokubai or kaimashi or rikaku:
                # 出来高急増チェック
                vol_spike = curr['Volume'] > (df['Volume'].tail(5).mean() * 1.2)
                spike_mark = "⚡" if vol_spike else ""
                
                sig_tag = f"🚨{spike_mark}【特買い】" if tokubai else (f"✨{spike_mark}【買い増し】" if kaimashi else f"💰{spike_mark}【利確】")
                
                info = f"{sig_tag} {ticker_map[ticker]}({ticker}) : {price}円 [RCI:{int(curr['RCI9'])} RSI:{int(curr['RSI'])}]\n└ [📈 チャート](https://finance.yahoo.co.jp/quote/{ticker})"
                
                if is_uptrend:
                    up_signals.append(f"📈上昇中 ➔ {info}")
                elif is_downtrend:
                    down_signals.append(f"📉下降中 ➔ {info}")

        except:
            continue

    # 最終報告
    summary = f"📊 **精密哨戒完了 ({now_str})**\n母集団: {total_scanned} 社 / 合致: {len(up_signals) + len(down_signals)} 件"
    requests.post(DISCORD_WEBHOOK_URL, json={"content": summary})

    send_discord("🔥 強上昇トレンド × シグナル合致", up_signals)
    send_discord("🌪️ 強下降トレンド × シグナル合致", down_signals)
