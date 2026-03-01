import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
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
    """JPXから最新のプライム銘柄リストを取得。失敗時は代替手段を試行。"""
    # 2026年現在の最新候補URL（JPXはURLを動的に変えるため複数用意）
    urls = [
        "https://www.jpx.co.jp/markets/statistics-banner/quote/01_data_j.xls",
        "https://www.jpx.co.jp/markets/statistics-banner/quote/tvdivq0000001vg2-att/data_j.xls"
    ]
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    
    for url in urls:
        try:
            print(f"📡 リスト取得中: {url}")
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                df = pd.read_excel(io.BytesIO(resp.content))
                # 市場区分が「プライム」の銘柄を抽出
                prime_df = df[df['市場・商品区分'].str.contains('プライム', na=False)]
                tickers = {f"{row['コード']}.T": row['銘柄名'] for _, row in prime_df.iterrows()}
                if tickers:
                    return tickers
        except Exception as e:
            print(f"⚠️ URL {url} でエラー: {e}")
            continue
            
    # 全滅した場合のみ、最小限の銘柄でなくエラーを出すように変更
    raise Exception("❌ JPXから銘柄リストを取得できませんでした。URLが変更されている可能性があります。")

def analyze_stock(ticker, name):
    try:
        tkr = yf.Ticker(ticker)
        df = tkr.history(period="6mo", interval="1d")
        if len(df) < 26: return None

        # 25日移動平均線と乖離率
        df['MA25'] = df['Close'].rolling(window=25).mean()
        curr_price = df['Close'].iloc[-1]
        kairi = ((curr_price - df['MA25'].iloc[-1]) / df['MA25'].iloc[-1]) * 100
        
        # RCI (短期9日, 長期26日)
        df['RCI9'] = calculate_rci(df['Close'], 9)
        df['RCI26'] = calculate_rci(df['Close'], 26)
        curr, prev = df.iloc[-1], df.iloc[-2]
        
        signal_type = None
        # 1. 買い: 乖離 -10%以下 ＋ RCIゴールデンクロス
        if kairi <= -10.0 and (curr['RCI9'] > curr['RCI26']) and (curr['RCI9'] > prev['RCI9']):
            signal_type = "BUY"
        # 2. 売り: 乖離 +10%以上 ＋ RCIデッドクロス
        elif kairi >= 10.0 and (curr['RCI9'] < curr['RCI26']) and (curr['RCI9'] < prev['RCI9']):
            signal_type = "SELL"

        if signal_type:
            # PBRは情報として取得
            pbr = tkr.info.get('priceToBook', 0)
            pbr_eval = "🌟1倍割れ" if (0 < pbr <= 1.0) else f"{round(pbr, 2)}倍"
            return {
                "type": signal_type, "name": name, "code": ticker, "price": int(curr_price),
                "kairi": round(kairi, 1), "pbr": pbr_eval,
                "rci_s": round(curr['RCI9'], 1), "rci_l": round(curr['RCI26'], 1)
            }
        return None
    except:
        return None

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    now_str = datetime.now(jst).strftime('%H:%M')
    
    try:
        targets = get_prime_tickers()
    except Exception as e:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🚨 エラー: {e}"})
        exit()
    
    requests.post(DISCORD_WEBHOOK_URL, json={
        "username": "株監視AI教授", 
        "content": f"🚀 **プライム市場({len(targets)}社) 巡回開始** ({now_str})"
    })
    
    found_count = 0
    for i, (ticker, name) in enumerate(targets.items()):
        res = analyze_stock(ticker, name)
        if res:
            found_count += 1
            emoji = "⚡" if res['type'] == "BUY" else "🚀"
            title = "【反発期待】" if res['type'] == "BUY" else "【高値警戒】"
            content = (
                f"🦅 **AI監視レポート: {title}**\n"
                f"{emoji} **{res['name']}({res['code']})**\n"
                f"└ 価格: {res['price']}円 / 25日乖離: {res['kairi']}%\n"
                f"└ PBR: {res['pbr']} / RCI短期: {res['rci_s']}"
            )
            requests.post(DISCORD_WEBHOOK_URL, json={"username": "株監視AI教授", "content": content})
            time.sleep(1)

    requests.post(DISCORD_WEBHOOK_URL, json={
        "username": "株監視AI教授", 
        "content": f"✅ **巡回完了** ({now_str})\n└ スキャン: {len(targets)}件 / 合致: {found_count}件"
    })
