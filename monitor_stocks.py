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
    """RCI(順位相関指数)を計算"""
    n = period
    rank_period = pd.Series(range(n, 0, -1))
    def rci_func(x):
        d = ((pd.Series(x).rank(ascending=False) - rank_period)**2).sum()
        return (1 - (6 * d) / (n * (n**2 - 1))) * 100
    return series.rolling(window=n).apply(rci_func)

def get_prime_tickers():
    """監視対象の取得"""
    if os.path.exists('prime_list.csv'):
        df = pd.read_csv('prime_list.csv')
        return {f"{str(c).split('.')[0]}.T": n for c, n in zip(df['コード'], df['銘柄名'])}
    # デフォルトリスト（テスト用）
    return {"9101.T": "日本郵船", "8035.T": "東エレク", "9984.T": "SBG", "7203.T": "トヨタ"}

def analyze_stock(ticker, name):
    try:
        tkr = yf.Ticker(ticker)
        df = tkr.history(period="1y", interval="1d")
        if len(df) < 26: return None

        # --- 指標計算 ---
        # 25日移動平均線と乖離率
        df['MA25'] = df['Close'].rolling(window=25).mean()
        curr_price = df['Close'].iloc[-1]
        kairi = ((curr_price - df['MA25'].iloc[-1]) / df['MA25'].iloc[-1]) * 100
        
        # RCI (短期9日, 長期26日)
        df['RCI9'] = calculate_rci(df['Close'], 9)
        df['RCI26'] = calculate_rci(df['Close'], 26)

        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # --- 判定ロジック ---
        signal_type = None
        
        # 1. 買いシグナル：25日乖離が -10%以下 ＋ RCIゴールデンクロス
        if kairi <= -10.0 and (curr['RCI9'] > curr['RCI26']) and (curr['RCI9'] > prev['RCI9']):
            signal_type = "BUY"
            
        # 2. 売りシグナル：25日乖離が +10%以上 ＋ RCIデッドクロス(短期が下向き)
        elif kairi >= 10.0 and (curr['RCI9'] < curr['RCI26']) and (curr['RCI9'] < prev['RCI9']):
            signal_type = "SELL"

        # --- PBR評価 (情報として扱う) ---
        pbr = tkr.info.get('priceToBook', 0)
        if pbr == 0: pbr_eval = "取得不能"
        elif pbr < 1.0: pbr_eval = "✅割安 (1.0倍以下)"
        else: pbr_eval = f"基準超 ({round(pbr, 2)}倍)"

        if signal_type:
            return {
                "type": signal_type,
                "name": name, "code": ticker, "price": int(curr_price),
                "kairi": round(kairi, 1), "pbr": round(pbr, 2), "pbr_eval": pbr_eval,
                "rci_s": round(curr['RCI9'], 1), "rci_l": round(curr['RCI26'], 1)
            }
        return None
    except:
        return None

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    now_str = datetime.now(jst).strftime('%H:%M')
    print(f"🕵️ 大引け前 両方向哨戒開始: {now_str}")
    
    targets = get_prime_tickers()
    found_buy = 0
    found_sell = 0
    
    for ticker, name in targets.items():
        res = analyze_stock(ticker, name)
        if res:
            if res['type'] == "BUY":
                found_buy += 1
                emoji, title, comment = "⚡", "【反発期待・買い検討】", "売られすぎからの反発シグナルです。"
            else:
                found_sell += 1
                emoji, title, comment = "🚀", "【高値警戒・利益確定】", "買われすぎからの天井打ちシグナルです。"

            content = (
                f"🦅 **AI監視レポート: {title}**\n"
                f"{emoji} **{res['name']}({res['code']})**\n"
                f"└ 価格: {res['price']}円 / **25日乖離: {res['kairi']}%**\n"
                f"└ PBR評価: {res['pbr_eval']}\n"
                f"└ RCI短期: {res['rci_s']} / 長期: {res['rci_l']}\n"
                f"📢 {comment}"
            )
            requests.post(DISCORD_WEBHOOK_URL, json={"username": "株監視AI教授", "content": content})
            time.sleep(1)

    # --- 完了報告 ---
    summary = (
        f"✅ **大引け前スキャン完了** ({now_str})\n"
        f"└ スキャン数: {len(targets)}件\n"
        f"└ 買合致: **{found_buy}件** / 売合致: **{found_sell}件**\n"
        f"{'📢 注目銘柄があります。取引の参考にしてください。' if (found_buy + found_sell) > 0 else '📢 強いシグナルが出ている銘柄は見つかりませんでした。'}"
    )
    requests.post(DISCORD_WEBHOOK_URL, json={"username": "株監視AI教授", "content": summary})
