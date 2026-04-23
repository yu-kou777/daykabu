import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
import io
from datetime import datetime, timedelta, timezone

# --- 設定 ---
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"
MIN_TRADING_VALUE = 800_000_000 

def calculate_rci(series, period):
    def rci_func(x):
        n = len(x)
        if n < period: return np.nan
        price_ranks = pd.Series(x).rank(ascending=False).values
        time_ranks = np.arange(n, 0, -1)
        d2 = np.sum((price_ranks - time_ranks)**2)
        return (1 - (6 * d2) / (n * (n**2 - 1))) * 100
    return series.rolling(window=period).apply(rci_func)

def calculate_rsi(series, period=14):
    """自作RSI関数（pandas-ta不要）"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_ticker_list():
    headers = {"User-Agent": "Mozilla/5.0"}
    url = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
    try:
        res = requests.get(url, headers=headers, timeout=20)
        df = pd.read_excel(io.BytesIO(res.content))
        target_df = df[df['市場・商品区分'].str.contains('プライム|スタンダード', na=False)]
        return {f"{row['コード']}.T": row['銘柄名'] for _, row in target_df.iterrows()}
    except:
        return {"7203.T": "トヨタ", "9984.T": "ソフトバンクG"}

def send_discord(content):
    if not content: return
    for i in range(0, len(content), 1900):
        requests.post(DISCORD_WEBHOOK_URL, json={"content": content[i:i+1900]})
        time.sleep(1)

def main():
    jst = timezone(timedelta(hours=9))
    ticker_map = get_ticker_list()
    tickers = list(ticker_map.keys())
    
    results = {
        "🚨【即買い・大底】": [],
        "💎【鉄板・同時GC】": [],
        "🎯【仕込み・GC直前】": [],
        "🌀【VWAP回帰狙い】": []
    }
    hit_codes = []

    # 一括ダウンロード
    chunk_size = 100
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i+chunk_size]
        try:
            data = yf.download(chunk, period="1y", interval="1d", progress=False, group_by='ticker')
            for ticker in chunk:
                try:
                    if ticker not in data.columns.get_level_values(0): continue
                    df = data[ticker].dropna()
                    if len(df) < 50: continue
                    
                    curr_price = df['Close'].iloc[-1]
                    trading_value = (df['Close'] * df['Volume']).tail(5).mean()
                    if trading_value < MIN_TRADING_VALUE: continue

                    # 指標計算（自作関数を使用）
                    rsi = calculate_rsi(df['Close'], 14)
                    rci9 = calculate_rci(df['Close'], 9)
                    rci27 = calculate_rci(df['Close'], 27)
                    psy = ((df['Close'].diff() > 0).astype(int).rolling(window=12).sum() / 12) * 100
                    vwap25 = (df['Close'] * df['Volume']).rolling(25).sum() / df['Volume'].rolling(25).sum()

                    c_rsi = rsi.iloc[-1]
                    c_rci9, p_rci9 = rci9.iloc[-1], rci9.iloc[-2]
                    c_rci27, p_rci27 = rci27.iloc[-1], rci27.iloc[-2]
                    c_psy = psy.iloc[-1]
                    c_vwap = vwap25.iloc[-1]

                    is_hit = False
                    info = f"・{ticker_map[ticker]}({ticker}) {int(curr_price)}円 [RSI:{int(c_rsi)} RCI9:{int(c_rci9)}]"

                    if c_rci9 <= -90 and c_rsi <= 10:
                        results["🚨【即買い・大底】"].append(info); is_hit = True
                    elif c_rsi <= 50 and (p_rci9 < p_rci27 and c_rci9 >= c_rci27) and c_rci9 <= -50:
                        results["💎【鉄板・同時GC】"].append(info); is_hit = True
                    elif c_rci9 <= -50 and c_rci9 > p_rci9 and (30 <= c_psy <= 50):
                        results["🎯【仕込み・GC直前】"].append(info); is_hit = True
                    elif curr_price < c_vwap and (c_rsi <= 20 or c_rci9 <= -70):
                        results["🌀【VWAP回帰狙い】"].append(info); is_hit = True

                    if is_hit: hit_codes.append(ticker.replace(".T", ""))
                except: continue
        except: continue
        time.sleep(1)

    msg = f"📋 **テス流・ハイブリッド投資戦略パトロール**\n({datetime.now(jst).strftime('%Y/%m/%d %H:%M')} 実行)\n\n"
    found_any = False
    for cat, items in results.items():
        if items:
            msg += f"**{cat}**\n" + "\n".join(items) + "\n\n"
            found_any = True
    
    if hit_codes:
        msg += "📋 **Streamlit診断用リスト**\n"
        msg += f"```text\n{','.join(sorted(list(set(hit_codes))))}\n```"
    elif not found_any:
        msg += "🔍 本日は厳選条件に合致する銘柄はありませんでした。"

    send_discord(msg)

if __name__ == "__main__":
    main()
