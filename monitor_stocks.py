import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import os
from datetime import datetime, timedelta, timezone

# --- 設定 ---
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
            print("📂 list.xlsx を発見。解析中...")
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
            print("⚠️ リストが空のため、デフォルト設定を使用します。")
            watchlist = {k: v for k, v in NAME_MAP.items()}
    except Exception as e:
        print(f"❌ リスト読み込み失敗: {e}")
        watchlist = {"9101.T": "日本郵船", "6330.T": "東洋エンジ"}
    return watchlist

def analyze_stock(ticker, name):
    try:
        tkr = yf.Ticker(ticker)
        df = tkr.history(period="6mo", interval="1d")
        if len(df) < 30: 
            print(f"⏩ {name}: データ不足")
            return None
        
        # 指標計算
        df.ta.rsi(length=14, append=True)
        macd = ta.macd(df['Close'])
        df = pd.concat([df, macd], axis=1)
        
        price = int(df['Close'].iloc[-1])
        rsi = df['RSI_14'].iloc[-1]
        macd_h = df['MACDh_12_26_9'].iloc[-1]
        
        # 需給判定
        jugyu = "📈 買い優勢" if macd_h > 0 else "📉 売り優勢" if macd_h < 0 else "☁️ 拮抗"

        # 判定条件（テストのため一旦 RSI 40/60 に緩和しています）
        if rsi <= 40: # ★動作確認のため 30 -> 40 に緩和
            status = "🐢✨ 買いサイン"
            comment = "📊⚡ 【RSI低位】反発のチャンスを伺うゾーンです。"
            color = 3066993
        elif rsi >= 60: # ★動作確認のため 70 -> 60 に緩和
            status = "🐇📉 売りサイン"
            comment = "⚠️ 【RSI高位】利確を検討すべき警戒ゾーンです。"
            color = 15158332
        else:
            print(f"➖ {name}: 判定外 (RSI: {rsi:.1f})")
            return None

        return {
            "name": name, "code": ticker, "price": f"{price:,}",
            "rsi": round(rsi, 1), "jugyu": jugyu, "status": status,
            "comment": comment, "color": color
        }
    except Exception as e:
        print(f"❌ {ticker} 解析エラー: {e}")
        return None

def send_discord(data):
    # 画像の「AI監視レポート」風フォーマット
    content = (
        f"🦅 **AI監視レポート**\n"
        f"{data['status']} **{data['name']}({data['code']})**\n"
        f"(RSI: {data['rsi']})\n"
        f"└ 価格: {data['price']}円 / 需給: {data['jugyu']}\n"
        f"📢 {data['comment']}"
    )
    
    payload = {"username": "株監視AI教授", "content": content}
    res = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    if res.status_code == 204:
        print(f"✅ {data['name']} 送信成功")
    else:
        print(f"❌ {data['name']} 送信失敗 (Code: {res.status_code})")

if __name__ == "__main__":
    print(f"🚀 哨戒ミッション開始: {datetime.now().strftime('%H:%M:%S')}")
    watchlist = load_watchlist()
    sent_count = 0
    for ticker, name in watchlist.items():
        res = analyze_stock(ticker, name)
        if res:
            send_discord(res)
            sent_count += 1
    print(f"🏁 哨戒完了。{sent_count} 件の通知を送信しました。")
