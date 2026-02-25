import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- 設定 ---
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

def load_targets():
    """JPX400のCSVがあればそれを読み込み、なければデフォルトを返す"""
    if os.path.exists('jpx400.csv'):
        df = pd.read_csv('jpx400.csv')
        return {f"{str(c).split('.')[0]}.T": n for c, n in zip(df['コード'], df['銘柄名'])}
    return {"9101.T": "日本郵船", "6330.T": "東洋エンジ"}

def analyze_stock(ticker, name):
    try:
        # 高速化のため期間を3ヶ月に限定
        tkr = yf.Ticker(ticker)
        df = tkr.history(period="3mo", interval="1d")
        if len(df) < 25: return None

        # テクニカル指標計算
        df['MA25'] = df['Close'].rolling(window=25).mean()
        df['Kairi'] = ((df['Close'] - df['MA25']) / df['MA25']) * 100
        df.ta.rsi(length=14, append=True)
        macd = ta.macd(df['Close'])
        df = pd.concat([df, macd], axis=1)
        
        price = int(df['Close'].iloc[-1])
        rsi = df['RSI_14'].iloc[-1]
        kairi = df['Kairi'].iloc[-1]
        macd_h = df['MACDh_12_26_9'].iloc[-1]
        
        # 需給判定
        jugyu = "📈 買い優勢" if macd_h > 0 else "📉 売り優勢"

        # --- 広域哨戒用の厳格なフィルター ---
        # RSIが30以下（売られすぎ）または70以上（買われすぎ）のみ
        if rsi <= 30 or kairi <= -10:
            status = "🐢✨ 買いチャンス"
            comment = "📊⚡ 【物理的限界】反発の臨界点に到達しました！"
            color = 3066993
        elif rsi >= 70 or kairi >= 10:
            status = "🐇📉 売り警戒"
            comment = "⚠️ 【過熱感注意】利確・調整の警戒ゾーンです。"
            color = 15158332
        else:
            return None # 条件に合わなければスルー

        return {
            "name": name, "code": ticker, "price": f"{price:,}",
            "rsi": round(rsi, 1), "kairi": round(kairi, 1),
            "jugyu": jugyu, "status": status, "comment": comment
        }
    except:
        return None

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    print(f"🚀 JPX400 広域哨戒ミッション開始: {datetime.now(jst).strftime('%H:%M')}")
    
    targets = load_targets()
    sent_count = 0
    
    for ticker, name in targets.items():
        res = analyze_stock(ticker, name)
        if res:
            # AI監視レポート形式での送信
            content = (
                f"🦅 **AI監視レポート (広域哨戒)**\n"
                f"{res['status']} **{res['name']}({res['code']})**\n"
                f"(RSI: {res['rsi']} / 乖離: {res['kairi']}%)\n"
                f"└ 価格: {res['price']}円 / 需給: {res['jugyu']}\n"
                f"📢 {res['comment']}"
            )
            requests.post(DISCORD_WEBHOOK_URL, json={"username": "株監視AI教授", "content": content})
            sent_count += 1
            time.sleep(1) # API負荷とDiscord制限対策
            
    print(f"🏁 哨戒完了。厳選された {sent_count} 件を報告しました。")
