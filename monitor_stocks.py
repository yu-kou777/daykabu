import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import os
from datetime import datetime, timedelta, timezone

# --- 設定 ---
# 以前のコードから抽出したWebhook URL
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

# 📖 和名データベース
NAME_MAP = {
    "8035.T": "東京エレクトロン", "6920.T": "レーザーテック", "6857.T": "アドバンテスト",
    "6723.T": "ルネサス", "6758.T": "ソニーグループ", "6501.T": "日立製作所",
    "7203.T": "トヨタ自動車", "7267.T": "ホンダ", "7270.T": "SUBARU",
    "8306.T": "三菱UFJ", "9101.T": "日本郵船", "9104.T": "商船三井", "9107.T": "川崎汽船",
    "9984.T": "ソフトバンクG", "6330.T": "東洋エンジニアリング", "4385.T": "メルカリ",
    "4755.T": "楽天グループ", "6701.T": "日本電気", "5016.T": "ＪＸ金属", "7280.T": "ミツバ"
}

def load_watchlist():
    watchlist = {}
    try:
        if os.path.exists('list.xlsx'):
            df = pd.read_excel('list.xlsx')
            df.columns = [str(c).strip().lower() for c in df.columns]
            code_col = next((c for c in ['code', 'コード', '銘柄コード'] if c in df.columns), None)
            if code_col:
                for c in df[code_col]:
                    code_str = str(c).split('.')[0].strip()
                    if code_str.isdigit():
                        ticker = f"{code_str}.T"
                        watchlist[ticker] = NAME_MAP.get(ticker, f"銘柄:{code_str}")
        if not watchlist:
            watchlist = {k: v for k, v in NAME_MAP.items()}
    except:
        watchlist = {"9101.T": "日本郵船", "6330.T": "東洋エンジ"}
    return watchlist

def analyze_stock(ticker, name):
    try:
        tkr = yf.Ticker(ticker)
        df = tkr.history(period="6mo", interval="1d")
        if len(df) < 30: return None
        
        # 指標計算
        df['MA25'] = df['Close'].rolling(window=25).mean()
        df['Kairi'] = ((df['Close'] - df['MA25']) / df['MA25']) * 100
        df.ta.rsi(length=14, append=True)
        macd = ta.macd(df['Close'])
        df = pd.concat([df, macd], axis=1)
        
        price = int(df['Close'].iloc[-1])
        rsi = df['RSI_14'].iloc[-1]
        kairi = df['Kairi'].iloc[-1]
        macd_h = df['MACDh_12_26_9'].iloc[-1] # 需給判定用
        
        # --- 画像を参考にした「簡単な説明」の生成 ---
        # 需給判定
        if macd_h > 0: jugyu = "📈 買い優勢"
        elif macd_h < 0: jugyu = "📉 売り優勢"
        else: jugyu = "☁️ 拮抗"

        # 判定とコメント
        if rsi <= 30:
            status = "🐢✨ 買いサイン"
            comment = "📊⚡ 【RSI売られすぎ】反発の臨界点に到達！"
            color = 3066993 # 緑
        elif rsi >= 70:
            status = "🐇📉 売りサイン"
            comment = "⚠️ 【RSI買われすぎ】利確・調整の警戒ゾーンです。"
            color = 15158332 # 赤
        else:
            return None # どちらでもなければ通知しない（ノイズカット）

        return {
            "name": name, "code": ticker, "price": f"{price:,}",
            "rsi": round(rsi, 1), "jugyu": jugyu, "status": status,
            "comment": comment, "color": color
        }
    except: return None

def send_discord(data):
    # 画像の「AI監視レポート」風のフォーマット
    content = (
        f"🦅 **AI監視レポート**\n"
        f"{data['status']} **{data['name']}({data['code']})**\n"
        f"(RSI: {data['rsi']})\n"
        f"└ 価格: {data['price']}円 / 需給: {data['jugyu']}\n"
        f"📢 {data['comment']}"
    )
    
    payload = {"username": "株監視AI教授", "content": content}
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

if __name__ == "__main__":
    watchlist = load_watchlist()
    for ticker, name in watchlist.items():
        res = analyze_stock(ticker, name)
        if res:
            send_discord(res)
