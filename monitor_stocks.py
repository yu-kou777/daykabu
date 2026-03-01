import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import time
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

def get_prime_tickers():
    """JPXからプライム市場銘柄を自動取得"""
    try:
        url = "https://www.jpx.co.jp/markets/statistics-banner/quote/tvdivq0000001vg2-att/data_j.xls"
        df = pd.read_excel(url)
        prime_df = df[df['市場・商品区分'].str.contains('プライム', na=False)]
        return {f"{row['コード']}.T": row['銘柄名'] for _, row in prime_df.iterrows()}
    except Exception as e:
        print(f"銘柄取得エラー: {e}")
        return {"9101.T": "日本郵船", "8035.T": "東エレク", "9984.T": "SBG", "7203.T": "トヨタ"}

def analyze_stock(ticker, name):
    try:
        tkr = yf.Ticker(ticker)
        df = tkr.history(period="6mo", interval="1d")
        if len(df) < 26: return None

        # 指標計算
        df['MA25'] = df['Close'].rolling(window=25).mean()
        curr_price = df['Close'].iloc[-1]
        kairi = ((curr_price - df['MA25'].iloc[-1]) / df['MA25'].iloc[-1]) * 100
        
        df['RCI9'] = calculate_rci(df['Close'], 9)
        df['RCI26'] = calculate_rci(df['Close'], 26)
        curr, prev = df.iloc[-1], df.iloc[-2]
        
        signal_type = None
        # 乖離率 ±10%〜15% かつ RCIクロス
        if kairi <= -10.0 and (curr['RCI9'] > curr['RCI26']) and (curr['RCI9'] > prev['RCI9']):
            signal_type = "BUY"
        elif kairi >= 10.0 and (curr['RCI9'] < curr['RCI26']) and (curr['RCI9'] < prev['RCI9']):
            signal_type = "SELL"

        if signal_type:
            pbr = tkr.info.get('priceToBook', 0)
            pbr_eval = "🌟割安" if (pbr > 0 and pbr <= 1.0) else f"{round(pbr, 2)}倍"
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
    
    print("📋 プライム市場リスト取得中...")
    targets = get_prime_tickers()
    
    requests.post(DISCORD_WEBHOOK_URL, json={
        "username": "株監視AI教授", 
        "content": f"📡 **プライム市場({len(targets)}社) 哨戒開始** ({now_str})"
    })
    
    found_list = []
    for i, (ticker, name) in enumerate(targets.items()):
        res = analyze_stock(ticker, name)
        if res:
            found_list.append(res)
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

    summary = (
        f"✅ **哨戒完了** ({now_str})\n"
        f"└ スキャン: {len(targets)}件 / 合致: {len(found_list)}件"
    )
    requests.post(DISCORD_WEBHOOK_URL, json={"username": "株監視AI教授", "content": summary})
