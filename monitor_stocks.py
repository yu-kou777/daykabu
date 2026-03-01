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
    """リスト形式でDiscordに送信（2000文字制限対策）"""
    if not stock_list:
        return
    
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
    
    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🔎 **パトロール開始** ({now_str})\n対象: プライム市場 {len(ticker_list)}社 / 株価3,001円～30,000円"})

    # 結果格納用
    buy_signals = []      # 押し目買い候補
    strong_uptrend = []   # 強い上昇トレンド
    profit_take = []     # 利確・過熱警戒
    strong_downtrend = [] # 強い下降トレンド

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
            
            curr_price = df['Close'].iloc[-1]
            if not (3000 < curr_price <= 30000): continue

            # 指標計算
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['RCI9'] = calculate_rci(df['Close'], 9)
            df['MA5'] = ta.sma(df['Close'], length=5)
            df['MA20'] = ta.sma(df['Close'], length=20)
            df['MA60'] = ta.sma(df['Close'], length=60)
            df['MA200'] = ta.sma(df['Close'], length=200)
            
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            name = ticker_map[ticker]
            price = int(curr_price)

            # トレンド判定
            is_uptrend = curr['MA5'] > curr['MA20'] > curr['MA60'] > curr['MA200']
            is_downtrend = curr['MA5'] < curr['MA20'] < curr['MA60'] < curr['MA200']

            # --- カテゴリ分け ---
            
            # 1. 【最優先】上昇トレンド中の押し目買い (RSI < 50 かつ RCI底打ち)
            if is_uptrend and curr['RSI'] < 50 and curr['RCI9'] < -50:
                buy_signals.append(f"✨ {name}({ticker}) : {price}円 (RSI:{round(curr['RSI'],1)} RCI:{round(curr['RCI9'],1)})")
            
            # 2. 過熱・利確警戒
            elif curr['RCI9'] > 90 and curr['RSI'] > 80:
                profit_take.append(f"💰 {name}({ticker}) : {price}円 (過熱)")

            # 3. 強い上昇 (パーフェクトオーダー)
            elif is_uptrend:
                # 前日比でMAが伸びているもの
                if curr['MA5'] > prev['MA5']:
                    strong_uptrend.append(f"🔥 {name}({ticker}) : {price}円")

            # 4. 強い下降
            elif is_downtrend:
                strong_downtrend.append(f"💀 {name}({ticker}) : {price}円")

        except:
            continue

    # --- まとめて通知 ---
    send_discord("✨ 押し目買い候補 (上昇トレンド×安値圏)", buy_signals)
    send_discord("🔥 強い上昇トレンド (パーフェクトオーダー)", strong_uptrend)
    send_discord("💰 利確検討 (高値圏)", profit_take)
    send_discord("💀 強い下降トレンド (三役下降)", strong_downtrend)

    requests.post(DISCORD_WEBHOOK_URL, json={"content": "✅ **パトロール完了**"})
