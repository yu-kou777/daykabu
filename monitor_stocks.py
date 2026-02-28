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
    """RCI(順位相関指数)を計算する関数"""
    n = period
    rank_period = pd.Series(range(n, 0, -1))
    def rci_func(x):
        d = ((pd.Series(x).rank(ascending=False) - rank_period)**2).sum()
        return (1 - (6 * d) / (n * (n**2 - 1))) * 100
    return series.rolling(window=n).apply(rci_func)

def get_prime_tickers():
    """プライム市場の銘柄リストを取得"""
    if os.path.exists('prime_list.csv'):
        df = pd.read_csv('prime_list.csv')
        return {f"{str(c).split('.')[0]}.T": n for c, n in zip(df['コード'], df['銘柄名'])}
    
    # テスト用リスト
    return {
        "9101.T": "日本郵船", "8035.T": "東エレク", 
        "9984.T": "ソフトバンクG", "7203.T": "トヨタ",
        "5401.T": "日本製鉄", "8306.T": "三菱UFJ"
    }

def analyze_stock(ticker, name):
    try:
        tkr = yf.Ticker(ticker)
        df = tkr.history(period="1y", interval="1d")
        if len(df) < 200: return None

        # 指標計算
        df['MA60'] = df['Close'].rolling(window=60).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()
        df.ta.rsi(length=14, append=True)
        df['RCI9'] = calculate_rci(df['Close'], 9)
        df['RCI26'] = calculate_rci(df['Close'], 26)

        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 判定ロジック
        pbr = tkr.info.get('priceToBook', 99.0)
        is_low_pbr = pbr <= 1.0
        
        # RSI・RCI 3日以内に90以上
        recent_window = df.tail(3)
        is_overheated = (recent_window['RSI_14'].max() >= 90) and (recent_window['RCI9'].max() >= 90)

        # RCIゴールデンクロス
        rci_gc = (curr['RCI9'] > curr['RCI26']) and (curr['RCI9'] > prev['RCI9'])

        if is_low_pbr and is_overheated and rci_gc:
            return {
                "name": name, "code": ticker, "price": int(curr['Close']),
                "pbr": round(pbr, 2), "rsi": round(curr['RSI_14'], 1), 
                "rci_s": round(curr['RCI9'], 1),
                "ma60": "上昇📈" if curr['MA60'] > prev['MA60'] else "下降📉"
            }
        return None
    except:
        return None

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    now_str = datetime.now(jst).strftime('%H:%M')
    print(f"🕵️ プライム市場 大引け前哨戒開始: {now_str}")
    
    targets = get_prime_tickers()
    total_targets = len(targets)
    found_list = []
    
    for ticker, name in targets.items():
        res = analyze_stock(ticker, name)
        if res:
            found_list.append(res)
            # 合致銘柄の個別通知
            content = (
                f"🦅 **AI監視レポート: ヒット銘柄**\n"
                f"🎯 **{res['name']}({res['code']})**\n"
                f"└ 価格: {res['price']}円 / PBR: {res['pbr']}倍\n"
                f"└ RSI: {res['rsi']} / RCI短期: {res['rci_s']}\n"
                f"└ MA60トレンド: {res['ma60']}\n"
                f"📢 **大引け買い検討条件に合致。**"
            )
            requests.post(DISCORD_WEBHOOK_URL, json={"username": "株監視AI教授", "content": content})
            time.sleep(1.5)

    # --- 0件でも届く完了報告 ---
    status_emoji = "✅" if len(found_list) > 0 else "💤"
    summary_content = (
        f"{status_emoji} **大引け前スキャン完了報告** ({now_str})\n"
        f"└ スキャン銘柄数: {total_targets}件\n"
        f"└ 条件合致数: **{len(found_list)}件**\n"
        f"{'---' if len(found_list) > 0 else '📢 本日、条件に合致する極めて強い低PBR銘柄は見つかりませんでした。'}"
    )
    requests.post(DISCORD_WEBHOOK_URL, json={"username": "株監視AI教授", "content": summary_content})
    
    print(f"🏁 哨戒完了。合致 {len(found_list)} 件。")
