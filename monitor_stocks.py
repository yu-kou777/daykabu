import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import os
from datetime import datetime, timedelta, timezone

# --- 設定 ---
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

# 和名データベース
NAME_MAP = {
    "8035.T": "東京エレクトロン", "6920.T": "レーザーテック", "6857.T": "アドバンテスト",
    "6723.T": "ルネサス", "6758.T": "ソニーグループ", "6501.T": "日立製作所",
    "7203.T": "トヨタ自動車", "7267.T": "ホンダ", "7270.T": "SUBARU",
    "8306.T": "三菱UFJ", "9101.T": "日本郵船", "9104.T": "商船三井", "9107.T": "川崎汽船",
    "9984.T": "ソフトバンクG", "6330.T": "東洋エンジニアリング", "4385.T": "メルカリ"
}

def load_watchlist():
    """エクセルから銘柄を読み込み、和名を補完する"""
    try:
        if not os.path.exists('list.xlsx'):
            return {code: NAME_MAP.get(code, code) for code in NAME_MAP.keys()}
        
        df = pd.read_excel('list.xlsx')
        df.columns = [str(c).strip().lower() for c in df.columns]
        code_col = next((c for c in ['code', 'コード', '銘柄コード'] if c in df.columns), None)
        
        watchlist = {}
        for c in df[code_col]:
            code = f"{str(c).strip().split('.')[0]}.T"
            watchlist[code] = NAME_MAP.get(code, f"銘柄:{code}")
        return watchlist
    except:
        return {code: NAME_MAP.get(code, code) for code in ["9984.T", "6330.T", "9101.T"]}

def analyze_stock(ticker, name):
    try:
        tkr = yf.Ticker(ticker)
        df = tkr.history(period="6mo", interval="1d")
        if df.empty or len(df) < 60: return None
        
        # 指標計算
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        rsi = ta.rsi(df['Close'], length=14).iloc[-1]
        price = int(df['Close'].iloc[-1])
        
        # 精密指値と利確目標の算出 (Sniper Pro ロジック)
        std20 = df['Close'].rolling(20).std().iloc[-1]
        low_60 = df['Low'].tail(60).min()
        floor = int((df['MA20'].iloc[-1] - (std20 * 2) + low_60) / 2)
        target1 = int(df['MA20'].iloc[-1])
        target2 = int(df['MA60'].iloc[-1])
        
        # スコア判定
        score = 0
        if price <= floor * 1.02: score += 50
        if rsi < 35: score += 30

        return {
            "name": name, "code": ticker.replace(".T",""),
            "price": price, "floor": floor, "target1": target1, "target2": target2,
            "score": score, "rsi": round(rsi, 1)
        }
    except: return None

def send_discord(data, session):
    payload = {
        "username": "Stock Sniper 🦅",
        "embeds": [{
            "title": f"【{session}】{data['name']} ({data['code']})",
            "description": f"**現在値: {data['price']}円**",
            "color": 3066993 if data['score'] > 30 else 10070709,
            "fields": [
                {"name": "🔵 指値目安", "value": f"**{data['floor']}円**", "inline": True},
                {"name": "🟢 利確目標1", "value": f"{data['target1']}円", "inline": True},
                {"name": "🔴 利確目標2", "value": f"{data['target2']}円", "inline": True},
                {"name": "🧠 スコア", "value": f"{data['score']}点", "inline": True},
                {"name": "🌊 RSI", "value": f"{data['rsi']}", "inline": True}
            ],
            "footer": {"text": f"観測: {datetime.now(timezone(timedelta(hours=9))).strftime('%H:%M')}"}
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    h = datetime.now(jst).hour
    session = "前場観測" if h < 11 else "後場観測" if h < 15 else "大引け報告"
    
    watchlist = load_watchlist()
    for code, name in watchlist.items():
        res = analyze_stock(code, name)
        # スコアがある程度高い（チャンスがある）銘柄のみ通知
        if res and res['score'] >= 20:
            send_discord(res, session)
