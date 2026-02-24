import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import os
from datetime import datetime, timedelta, timezone

# --- 設定 ---
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

# 強化版・和名データベース
NAME_MAP = {
    "8035.T": "東京エレクトロン", "6920.T": "レーザーテック", "6857.T": "アドバンテスト",
    "6723.T": "ルネサス", "6758.T": "ソニーグループ", "6501.T": "日立製作所",
    "7203.T": "トヨタ自動車", "7267.T": "ホンダ", "7270.T": "SUBARU",
    "8306.T": "三菱UFJ", "9101.T": "日本郵船", "9104.T": "商船三井", "9107.T": "川崎汽船",
    "9984.T": "ソフトバンクG", "6330.T": "東洋エンジニアリング", "4385.T": "メルカリ",
    "4755.T": "楽天グループ", "9983.T": "ファストリ", "9432.T": "NTT", "1605.T": "INPEX"
}

def load_watchlist():
    """エクセルから銘柄コードを取得し、和名を紐付ける"""
    watchlist = {}
    try:
        if os.path.exists('list.xlsx'):
            df = pd.read_excel('list.xlsx')
            df.columns = [str(c).strip().lower() for c in df.columns]
            code_col = next((c for c in ['code', 'コード', '銘柄コード'] if c in df.columns), None)
            
            if code_col:
                for c in df[code_col]:
                    code_str = str(c).strip().split('.')[0]
                    if code_str.isdigit():
                        ticker = f"{code_str}.T"
                        watchlist[ticker] = NAME_MAP.get(ticker, f"銘柄:{code_str}")
        
        # エクセルが空、または読み込めない場合のバックアップ
        if not watchlist:
            watchlist = {k: v for k, v in NAME_MAP.items()}
            
    except Exception as e:
        print(f"Watchlist Load Error: {e}")
        watchlist = {"9984.T": "ソフトバンクG", "9101.T": "日本郵船"}
    
    return watchlist

def analyze_stock(ticker, name):
    try:
        tkr = yf.Ticker(ticker)
        df = tkr.history(period="6mo", interval="1d")
        if df.empty or len(df) < 60: return None
        
        # 指標計算
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA60'] = df['Close'].rolling(60).mean()
        macd = ta.macd(df['Close'])
        df = pd.concat([df, macd], axis=1)
        rsi = ta.rsi(df['Close'], length=14).iloc[-1]
        price = int(df['Close'].iloc[-1])
        
        # 物理的な節目算出
        std20 = df['Close'].rolling(20).std().iloc[-1]
        low_60 = df['Low'].tail(60).min()
        high_60 = df['High'].tail(60).max()
        floor = int((df['MA20'].iloc[-1] - (std20 * 2) + low_60) / 2)
        ceiling = int((df['MA20'].iloc[-1] + (std20 * 2) + high_60) / 2)
        
        # --- 判定ロジック ---
        score = 0
        direction = "☁️ 様子見"
        color = 10070709 # グレー

        # 買いの根拠
        if price <= floor * 1.015: score += 40
        if rsi < 35: score += 30
        if df['MACDh_12_26_9'].iloc[-1] > 0: score += 20

        # 売りの根拠
        if price >= ceiling * 0.985: score -= 40
        if rsi > 65: score -= 30
        if df['MACDh_12_26_9'].iloc[-1] < 0: score -= 20

        if score >= 60:
            direction = "🚀 買い推奨 (強気)"; color = 3066993 # 緑
        elif score >= 20:
            direction = "✨ 買い検討 (押し目待ち)"; color = 15105570 # オレンジ
        elif score <= -60:
            direction = "📉 売り推奨 (強気)"; color = 15158332 # 赤
        elif score <= -20:
            direction = "☔ 売り検討 (戻り売り待ち)"; color = 12370112 # 紫

        return {
            "name": name, "code": ticker.replace(".T",""),
            "price": price, "floor": floor, "ceiling": ceiling,
            "target1": int(df['MA20'].iloc[-1]), "target2": int(df['MA60'].iloc[-1]),
            "score": score, "rsi": round(rsi, 1), "direction": direction, "color": color
        }
    except: return None

def send_discord(data, session):
    # 指値の表示を判定に合わせる
    entry_label = "🔵 戻り売り目安" if data['score'] < 0 else "🔵 指値目安"
    entry_price = data['ceiling'] if data['score'] < 0 else data['floor']

    payload = {
        "username": "Stock Sniper 🦅",
        "embeds": [{
            "title": f"【{session}】{data['name']} ({data['code']})",
            "description": f"## 判定: {data['direction']}\n**現在値: {data['price']}円**",
            "color": data['color'],
            "fields": [
                {"name": entry_label, "value": f"**{entry_price}円**", "inline": True},
                {"name": "🟢 利確目標1", "value": f"{data['target1']}円", "inline": True},
                {"name": "🔴 利確目標2", "value": f"{data['target2']}円", "inline": True},
                {"name": "🧠 スコア", "value": f"{data['score']}点", "inline": True},
                {"name": "🌊 RSI", "value": f"{data['rsi']}", "inline": True}
            ],
            "footer": {"text": f"観測時刻: {datetime.now(timezone(timedelta(hours=9))).strftime('%H:%M')}"}
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    h = datetime.now(jst).hour
    session = "前場観測" if h < 11 else "後場観測" if h < 15 else "大引け報告"
    
    watchlist = load_watchlist()
    for ticker, name in watchlist.items():
        res = analyze_stock(ticker, name)
        # 注目すべき動きがある場合のみ通知
        if res and abs(res['score']) >= 20:
            send_discord(res, session)
