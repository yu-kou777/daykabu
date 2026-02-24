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
    "9101.T": "日本郵船", "9984.T": "ソフトバンクG", "6330.T": "東洋エンジ"
}

def load_watchlist():
    """エクセルから銘柄を読み込む"""
    try:
        if not os.path.exists('list.xlsx'): return ["9984.T", "6330.T"]
        df = pd.read_excel('list.xlsx')
        df.columns = [str(c).strip().lower() for c in df.columns]
        code_col = next((c for c in ['code', 'コード', '銘柄コード'] if c in df.columns), None)
        if not code_col: return ["9984.T", "6330.T"]
        return [f"{str(c).strip().split('.')[0]}.T" for c in df[code_col]]
    except: return ["9984.T", "6330.T"]

def analyze_stock(ticker):
    try:
        tkr = yf.Ticker(ticker)
        df = tkr.history(period="6mo", interval="1d")
        if df.empty or len(df) < 60: return None
        
        # 精密解析
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        rsi = ta.rsi(df['Close'], length=14).iloc[-1]
        price = int(df['Close'].iloc[-1])
        
        # 精密指値の算出
        std20 = df['Close'].rolling(20).std().iloc[-1]
        low_60 = df['Low'].tail(60).min()
        floor = int((df['MA20'].iloc[-1] - (std20 * 2) + low_60) / 2)
        
        # スコア (買い寄り)
        score = 0
        if price <= floor * 1.02: score += 50
        if rsi < 35: score += 30

        return {
            "name": NAME_MAP.get(ticker, ticker),
            "price": price,
            "floor": floor,
            "target": int(df['MA20'].iloc[-1]),
            "score": score
        }
    except: return None

def send_discord(data, session):
    payload = {
        "username": "最強株哨戒機 🦅",
        "embeds": [{
            "title": f"【{session}】{data['name']}",
            "description": f"**現在値: {data['price']}円**",
            "color": 3066993 if data['score'] > 30 else 10070709,
            "fields": [
                {"name": "🔵 指値目安", "value": f"{data['floor']}円", "inline": True},
                {"name": "🟢 利確目標", "value": f"{data['target']}円", "inline": True},
                {"name": "🧠 スコア", "value": f"{data['score']}点", "inline": True}
            ]
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    h = datetime.now(jst).hour
    session = "前場観測" if h < 11 else "後場観測" if h < 15 else "大引け報告"
    
    codes = load_watchlist()
    for code in codes:
        res = analyze_stock(code)
        if res and res['score'] > 20: # 動きがある銘柄のみ通知
            send_discord(res, session)
