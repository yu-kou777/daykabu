import yfinance as yf
import pandas as pd
import requests
import time
import os
import io
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

def update_and_load_list():
    """リストがなければネットから取得して保存、あれば読み込む"""
    if os.path.exists(LIST_FILE):
        print(f"📁 保存済みの {LIST_FILE} を読み込みます...")
        df = pd.read_csv(LIST_FILE)
        return {f"{int(row['コード'])}.T": row['銘柄名'] for _, row in df.iterrows()}
    
    print("📡 リストが存在しません。JPXから最新データを取得して作成します...")
    url = "https://www.jpx.co.jp/markets/statistics-banner/quote/01_data_j.xls"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        df_jpx = pd.read_excel(io.BytesIO(resp.content))
        prime_df = df_jpx[df_jpx['市場・商品区分'].str.contains('プライム', na=False)]
        save_df = prime_df[['コード', '銘柄名']].copy()
        save_df.to_csv(LIST_FILE, index=False)
        print(f"✅ {LIST_FILE} を作成・保存しました。")
        return {f"{int(row['コード'])}.T": row['銘柄名'] for _, row in save_df.iterrows()}
    except Exception as e:
        print(f"❌ リスト作成失敗: {e}")
        return {"9101.T": "日本郵船", "6481.T": "THK"} # 最終バックアップ

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    now_str = datetime.now(jst).strftime('%H:%M')
    
    # 1. リストの自動管理
    ticker_map = update_and_load_list()
    ticker_list = list(ticker_map.keys())
    
    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🚀 **哨戒開始(全{len(ticker_list)}銘柄)** ({now_str})"})

    # 2. 一括ダウンロード（これが一番速い）
    all_data = yf.download(ticker_list, period="6mo", interval="1d", group_by='ticker', threads=True)

    found_count = 0
    for ticker in ticker_list:
        try:
            df = all_data[ticker].dropna()
            if len(df) < 26: continue

            # テクニカル解析
            df['MA25'] = df['Close'].rolling(window=25).mean()
            curr_p = df['Close'].iloc[-1]
            kairi = ((curr_p - df['MA25'].iloc[-1]) / df['MA25'].iloc[-1]) * 100
            df['RCI9'] = calculate_rci(df['Close'], 9)
            df['RCI26'] = calculate_rci(df['Close'], 26)
            curr, prev = df.iloc[-1], df.iloc[-2]

            # 判定条件（±10%乖離 ＋ RCIクロス）
            if (kairi <= -10.0 and curr['RCI9'] > curr['RCI26'] and curr['RCI9'] > prev['RCI9']) or \
               (kairi >= 10.0 and curr['RCI9'] < curr['RCI26'] and curr['RCI9'] < prev['RCI9']):
                
                found_count += 1
                type_str = "⚡【反発期待】" if kairi < 0 else "🚀【高値警戒】"
                content = (
                    f"🦅 **{type_str}**\n**{ticker_map[ticker.replace('.T','')]}({ticker})**\n"
                    f"└ 価格: {int(curr_p)}円 / 乖離: {round(kairi, 1)}%\n"
                    f"└ RCI9: {round(curr['RCI9'], 1)}"
                )
                requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
                time.sleep(1)
        except:
            continue

    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"✅ **哨戒完了** ({now_str}) 合致: {found_count}件"})
