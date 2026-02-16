import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import datetime

# ==========================================
# ⚙️ 設定：ここにWebhook URLを貼ってください
# ==========================================
DISCORD_WEBHOOK_URL = "ここにDiscordのWebhook URLを貼り付けてください"

# 監視対象（市場全体から厳選した主要株）
WATCH_LIST = [
    "8035.T", "6920.T", "6857.T", "6758.T", "9984.T", # 半導体・ハイテク
    "7203.T", "7267.T", "7011.T", # 自動車・重工
    "8306.T", "8316.T", "8591.T", # 金融
    "8001.T", "8031.T", "8058.T", # 商社
    "9101.T", "9104.T", "9107.T", # 海運
    "5401.T", "9501.T", "4502.T"  # 鉄鋼・電力・医薬
]

def send_discord(data):
    """Discordにリッチな通知を送る"""
    if "http" not in DISCORD_WEBHOOK_URL: return

    color = 15158332 if "買い" in data['判定'] else 3066993 # 赤か青
    
    payload = {
        "username": "最強株スキャナー🤖",
        "embeds": [{
            "title": f"🔔 {data['判定']}シグナル検知: {data['銘柄']} ",
            "description": f"**現在値: {data['現在値']}**\nスコア: {data['スコア']}点",
            "color": color,
            "fields": [
                {"name": "📈 根拠", "value": data['根拠'], "inline": False},
                {"name": "🎯 利確目標", "value": data['利確'], "inline": True},
                {"name": "🛡️ 損切目安", "value": data['損切'], "inline": True}
            ],
            "footer": {"text": f"判定時刻: {datetime.datetime.now().strftime('%H:%M')}"}
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

def analyze(ticker):
    try:
        # デイトレモード(5分足)で解析
        df = yf.download(ticker, period="5d", interval="5m", progress=False)
        if len(df) < 50: return

        # データ整形
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
        
        # テクニカル計算
        df['HA_Close'] = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4
        # 平均足Openの簡易計算
        df['HA_Open'] = (df['Open'].shift(1) + df['Close'].shift(1)) / 2 
        
        df['RSI'] = ta.rsi(df['Close'], length=14)
        macd = ta.macd(df['Close'])
        df = pd.concat([df, macd], axis=1)
        df['MA75'] = ta.sma(df['Close'], length=75)

        latest = df.iloc[-1]
        price = float(latest['Close'])
        
        # --- 判定ロジック (Hybrid-X) ---
        score = 0
        reasons = []

        # 平均足判定
        ha_close = latest['HA_Close']; ha_open = latest['HA_Open']
        if ha_close > ha_open: # 陽線
            if (ha_open - latest['Low']) < (abs(ha_close - ha_open) * 0.1):
                score += 30; reasons.append("平均足:最強(下ヒゲなし)")
            else:
                score += 10
        elif ha_close < ha_open: # 陰線
             if (latest['High'] - ha_open) < (abs(ha_close - ha_open) * 0.1):
                score -= 30; reasons.append("平均足:最弱(上ヒゲなし)")
             else:
                score -= 10

        # テクニカル判定
        if price > latest['MA75']: score += 10
        else: score -= 10
        
        if latest['RSI'] < 30: score += 20; reasons.append("RSI底値圏")
        elif latest['RSI'] > 70: score -= 20; reasons.append("RSI過熱圏")
        
        if latest['MACDh_12_26_9'] > 0 and df.iloc[-2]['MACDh_12_26_9'] < 0:
            score += 30; reasons.append("MACD好転")

        # 通知判定（強いサインのみ通知）
        judgement = ""
        if score >= 50: judgement = "🔥 買い推奨"
        elif score <= -40: judgement = "📉 売り推奨"
        
        if judgement: # チャンスがあれば通知
            target = int(price * 1.02) if "買い" in judgement else int(price * 0.98)
            stop = int(price * 0.99) if "買い" in judgement else int(price * 1.01)
            
            send_discord({
                "銘柄": ticker.replace(".T", ""),
                "現在値": f"{int(price)}円",
                "判定": judgement,
                "スコア": score,
                "根拠": ", ".join(reasons),
                "利確": f"{target}円",
                "損切": f"{stop}円"
            })

    except Exception as e:
        print(f"Error {ticker}: {e}")

# --- 実行 ---
if __name__ == "__main__":
    print("巡回開始...")
    for t in WATCH_LIST:
        analyze(t)
    print("巡回終了")

