import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import time
import io
import os
from datetime import datetime, timedelta, timezone

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
    """JPXから最新の名簿を取得（エラー報告付き）"""
    # JPXの最新URL候補
    urls = [
        "https://www.jpx.co.jp/markets/statistics-banner/quote/01_data_j.xls",
        "https://www.jpx.co.jp/markets/statistics-banner/quote/tvdivq0000001vg2-att/data_j.xls"
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    last_error = ""
    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                df_jpx = pd.read_excel(io.BytesIO(resp.content))
                # 「プライム」という文字が含まれる銘柄を抽出
                prime_df = df_jpx[df_jpx['市場・商品区分'].str.contains('プライム', na=False)]
                tickers = {f"{int(row['コード'])}.T": row['銘柄名'] for _, row in prime_df.iterrows()}
                if len(tickers) > 100:
                    return tickers
        except Exception as e:
            last_error = str(e)
            continue
    
    # 失敗した場合はDiscordに原因を報告
    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🚨 **名簿取得エラー**: {last_error}\nURLが古いか、ライブラリ(openpyxl)が不足しています。"})
    return None

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    now_str = datetime.now(jst).strftime('%H:%M')
    
    ticker_map = get_latest_prime_list()
    
    if not ticker_map:
        # 3銘柄で無理やり動かさず、ここで終了させる
        exit()

    ticker_list = list(ticker_map.keys())
    
    # 開始通知
    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🚀 **プライム市場({len(ticker_list)}社) 高精度哨戒を開始** ({now_str})"})

    # データ一括取得（1600件は数分かかります）
    # threads=True で高速化
    try:
        all_data = yf.download(ticker_list, period="6mo", interval="1d", group_by='ticker', threads=True)
    except Exception as e:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🚨 **データ取得エラー**: {e}"})
        exit()

    found_count = 0
    for ticker in ticker_list:
        try:
            # yfinanceのデータ形式に対応
            df = all_data[ticker].dropna()
            if df.empty or len(df) < 30: continue

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
                name = ticker_map.get(ticker, "不明")
                content = (
                    f"🦅 **{signal}**\n**{name}({ticker})**\n"
                    f"└ 価格: {int(curr['Close'])}円 / RSI: {round(curr['RSI_14'], 1)}\n"
                    f"└ 理由: {' / '.join(reason)}"
                )
                requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
                time.sleep(1) 
        except:
            continue

    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"✅ **哨戒完了** 合致: {found_count}件"})
