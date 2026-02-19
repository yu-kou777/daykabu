import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import datetime

# ==========================================
# ⚙️ 設定：ここにDiscordのWebhook URLを貼ってください
# ==========================================
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

# 監視リスト
WATCH_LIST = [
    "8035.T", "6920.T", "6857.T", "6758.T", "9984.T",
    "7203.T", "7267.T", "7011.T", "8306.T", "8316.T",
    "8001.T", "8031.T", "8058.T", "9101.T", "9104.T",
    "9107.T", "5401.T", "9501.T", "4502.T"
]

def flatten_data(df):
    """データ形式を安定させる魔法の関数"""
    if isinstance(df.columns, pd.MultiIndex):
        try: df.columns = df.columns.droplevel(1)
        except: pass
    return df

def send_discord(data):
    """Discordに分析結果をカード形式で送る"""
    if "http" not in DISCORD_WEBHOOK_URL: return
    color = 15158332 if "買い" in data['判定'] else 3447003
    payload = {
        "username": "最強株スキャナー🤖",
        "embeds": [{
            "title": f"🔔 {data['判定']}検知: {data['銘柄']}",
            "description": f"**現在値: {data['現在値']}円**\nスコア: {data['スコア']}点",
            "color": color,
            "fields": [
                {"name": "📉 根拠", "value": data['根拠'], "inline": False},
                {"name": "🎯 利確目安", "value": data['利確'], "inline": True},
                {"name": "🛡️ 損切目安", "value": data['損切'], "inline": True}
            ],
            "footer": {"text": f"判定: {datetime.datetime.now().strftime('%H:%M')}"}
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

def analyze(ticker):
    """1つの銘柄を精密に分析する"""
    try:
        # 5分足データ取得
        df = yf.download(ticker, period="5d", interval="5m", progress=False)
        if len(df) < 50: return

        df = flatten_data(df) # 成功したapp.pyと同じ防御
        
        # 指標計算
        df['HA_Close'] = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4
        df['HA_Open'] = (df['Open'].shift(1) + df['Close'].shift(1)) / 2 
        df['RSI'] = ta.rsi(df['Close'], length=14)
        macd_df = ta.macd(df['Close'])
        if macd_df is None: return
        df = pd.concat([df, macd_df], axis=1)
        df['MA75'] = ta.sma(df['Close'], length=75)

        latest = df.iloc[-1]
        price = float(latest['Close'])
        
        score = 0
        reasons = []

        # 酒田五法・平均足判定
        ha_close = float(latest['HA_Close'])
        ha_open = float(latest['HA_Open'])
        if ha_close > ha_open:
            if (ha_open - float(latest['Low'])) < (abs(ha_close - ha_open) * 0.1):
                score += 30; reasons.append("平均足:最強")
        elif ha_close < ha_open:
            if (float(latest['High']) - ha_open) < (abs(ha_close - ha_open) * 0.1):
                score -= 30; reasons.append("平均足:最弱")

        # テクニカル判定
        if price > float(latest['MA75']): score += 10
        if float(latest.get('RSI', 50)) < 30: score += 20; reasons.append("RSI底")
        
        # MACDゴールデンクロス
        hist_col = 'MACDh_12_26_9'
        if hist_col in df.columns:
            if float(latest[hist_col]) > 0 and float(df.iloc[-2][hist_col]) < 0:
                score += 30; reasons.append("MACD好転")

        # 通知の決定
        judgement = ""
        if score >= 50: judgement = "🔥 買い推奨"
        elif score <= -40: judgement = "📉 売り推奨"
        
        if judgement:
            target = int(price * 1.02) if "買い" in judgement else int(price * 0.98)
            stop = int(price * 0.99) if "買い" in judgement else int(price * 1.01)
            send_discord({
                "銘柄": ticker.replace(".T", ""), "現在値": int(price),
                "判定": judgement, "スコア": score, "根拠": ", ".join(reasons),
                "利確": f"{target}", "損切": f"{stop}"
            })
    except Exception as e:
        print(f"Skipping {ticker} due to error: {e}")

if __name__ == "__main__":
    print("🚀 偵察ドローン、出撃します！")
    for t in WATCH_LIST:
        analyze(t)
    print("🏁 全銘柄の巡回を完了しました。")

