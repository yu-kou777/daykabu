import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import re
import time
import io
from datetime import datetime, timedelta, timezone

# --- 設定 ---
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

def calculate_rci(series, period):
    """RCI(順位相関指数)を計算"""
    n = period
    rank_period = pd.Series(range(n, 0, -1))
    def rci_func(x):
        d = ((pd.Series(x).rank(ascending=False) - rank_period)**2).sum()
        return (1 - (6 * d) / (n * (n**2 - 1))) * 100
    return series.rolling(window=n).apply(rci_func)

def get_prime_tickers():
    """JPXのページを解析して、最新のdata_j.xlsのURLを自動で探す"""
    base_url = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    try:
        # 1. ページ本体を読み込み
        res = requests.get(base_url, headers=headers, timeout=15)
        res.raise_for_status()
        
        # 2. 最新の data_j.xls への相対パスを正規表現で探す
        match = re.search(r'href="(/[^"]+/data_j\.xls)"', res.text)
        if not match:
            raise Exception("Excelのダウンロードリンクが見つかりません。")
        
        file_url = "https://www.jpx.co.jp" + match.group(1)
        print(f"📡 最新のリストをダウンロード中: {file_url}")
        
        # 3. Excelファイルをダウンロードして解析
        excel_res = requests.get(file_url, headers=headers, timeout=15)
        df = pd.read_excel(io.BytesIO(excel_res.content))
        
        # プライム市場のみ抽出
        prime_df = df[df['市場・商品区分'].str.contains('プライム', na=False)]
        return {f"{int(row['コード'])}": row['銘柄名'] for _, row in prime_df.iterrows()}
        
    except Exception as e:
        print(f"❌ 銘柄取得エラー: {e}")
        return None

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    now_str = datetime.now(jst).strftime('%H:%M')
    
    # 銘柄リスト取得
    ticker_map = get_prime_tickers()
    if not ticker_map:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": "🚨 銘柄リストの取得に失敗しました。JPXのサイト構成が大幅に変更された可能性があります。"})
        exit()

    ticker_list = [f"{c}.T" for c in ticker_map.keys()]
    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🚀 **プライム市場({len(ticker_list)}社) 高速巡回を開始** ({now_str})"})

    # 一括ダウンロードで高速化
    print(f"Downloading {len(ticker_list)} stocks...")
    all_data = yf.download(ticker_list, period="6mo", interval="1d", group_by='ticker', threads=True)

    found_count = 0
    for code in ticker_map.keys():
        code_t = f"{code}.T"
        try:
            df = all_data[code_t].dropna()
            if len(df) < 26: continue

            # テクニカル指標
            df['MA25'] = df['Close'].rolling(window=25).mean()
            curr_price = df['Close'].iloc[-1]
            kairi = ((curr_price - df['MA25'].iloc[-1]) / df['MA25'].iloc[-1]) * 100
            df['RCI9'] = calculate_rci(df['Close'], 9)
            df['RCI26'] = calculate_rci(df['Close'], 26)
            curr, prev = df.iloc[-1], df.iloc[-2]

            signal = None
            # 買い：乖離率 -10%以下 ＋ RCIゴールデンクロス
            if kairi <= -10.0 and (curr['RCI9'] > curr['RCI26']) and (curr['RCI9'] > prev['RCI9']):
                signal = "⚡【反発期待】"
            # 売り：乖離率 +10%以上 ＋ RCIデッドクロス
            elif kairi >= 10.0 and (curr['RCI9'] < curr['RCI26']) and (curr['RCI9'] < prev['RCI9']):
                signal = "🚀【高値警戒】"

            if signal:
                found_count += 1
                content = (
                    f"🦅 **AI監視レポート: {signal}**\n"
                    f"**{ticker_map[code]}({code_t})**\n"
                    f"└ 価格: {int(curr_price)}円 / 25日乖離: {round(kairi, 1)}%\n"
                    f"└ RCI短期: {round(curr['RCI9'], 1)} / 長期: {round(curr['RCI26'], 1)}"
                )
                requests.post(DISCORD_WEBHOOK_URL, json={"username": "株監視AI教授", "content": content})
                time.sleep(0.5)
        except:
            continue

    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"✅ **巡回完了** ({now_str})\n└ スキャン: {len(ticker_list)}件 / 合致: {found_count}件"})
