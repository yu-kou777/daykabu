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
    """JPXの公式サイトから最新のプライム市場銘柄リストを取得"""
    try:
        url = "https://www.jpx.co.jp/markets/statistics-banner/quote/tvdivq0000001vg2-att/data_j.xls"
        df = pd.read_excel(url)
        # 「市場・商品区分」が「プライム（内国株）」のものを抽出
        prime_df = df[df['市場・商品区分'].str.contains('プライム', na=False)]
        # コードを 1234.T 形式に変換
        return {f"{row['コード']}.T": row['銘柄名'] for _, row in prime_df.iterrows()}
    except Exception as e:
        print(f"銘柄リストの取得に失敗しました: {e}")
        # 失敗時は最小限のリストを返す
        return {"9101.T": "日本郵船", "8035.T": "東エレク"}

def analyze_stock(ticker, name):
    try:
        tkr = yf.Ticker(ticker)
        # 25日移動平均と26日RCIのため最低限の期間で取得
        df = tkr.history(period="6mo", interval="1d")
        if len(df) < 26: return None

        # --- テクニカル指標計算 ---
        df['MA25'] = df['Close'].rolling(window=25).mean()
        curr_price = df['Close'].iloc[-1]
        kairi = ((curr_price - df['MA25'].iloc[-1]) / df['MA25'].iloc[-1]) * 100
        
        df['RCI9'] = calculate_rci(df['Close'], 9)
        df['RCI26'] = calculate_rci(df['Close'], 26)
        curr, prev = df.iloc[-1], df.iloc[-2]
        
        signal_type = None
        # 条件判定 (乖離率 ±10% かつ RCIクロス)
        if kairi <= -10.0 and (curr['RCI9'] > curr['RCI26']) and (curr['RCI9'] > prev['RCI9']):
            signal_type = "BUY"
        elif kairi >= 10.0 and (curr['RCI9'] < curr['RCI26']) and (curr['RCI9'] < prev['RCI9']):
            signal_type = "SELL"

        # シグナルが出た時だけ重いPBR取得処理を行う (高速化)
        if signal_type:
            pbr = tkr.info.get('priceToBook', 0)
            if pbr == 0: pbr_eval = "不明"
            elif pbr < 1.0: pbr_eval = "✅割安(1倍割れ)"
            else: pbr_eval = f"{round(pbr, 2)}倍"

            return {
                "type": signal_type, "name": name, "code": ticker, "price": int(curr_price),
                "kairi": round(kairi, 1), "pbr_eval": pbr_eval,
                "rci_s": round(curr['RCI9'], 1), "rci_l": round(curr['RCI26'], 1)
            }
        return None
    except:
        return None

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    now_str = datetime.now(jst).strftime('%H:%M')
    
    # 銘柄リスト取得
    print("📋 プライム市場銘柄リストを取得中...")
    targets = get_prime_tickers()
    total_count = len(targets)
    
    # 開始通知
    requests.post(DISCORD_WEBHOOK_URL, json={
        "username": "株監視AI教授", 
        "content": f"📡 **プライム市場 全 {total_count} 社の哨戒を開始します** ({now_str})"
    })
    
    found_buy, found_sell = 0, 0
    
    # 全件スキャン
    for i, (ticker, name) in enumerate(targets.items()):
        if i % 100 == 0: print(f"進捗: {i}/{total_count} 件完了...")
        
        res = analyze_stock(ticker, name)
        if res:
            if res['type'] == "BUY":
                found_buy += 1
                emoji, title, comment = "⚡", "【反発期待】", "売られすぎからの反発シグナルです。"
            else:
                found_sell += 1
                emoji, title, comment = "🚀", "【高値警戒】", "買われすぎからの調整シグナルです。"

            content = (
                f"🦅 **AI監視レポート: {title}**\n"
                f"{emoji} **{res['name']}({res['code']})**\n"
                f"└ 価格: {res['price']}円 / 25日乖離: {res['kairi']}%\n"
                f"└ PBR評価: {res['pbr_eval']}\n"
                f"└ RCI短期: {res['rci_s']} / 長期: {res['rci_l']}\n"
                f"📢 {comment}"
            )
            requests.post(DISCORD_WEBHOOK_URL, json={"username": "株監視AI教授", "content": content})
            time.sleep(1) # Discordへの連続投稿制限対策

    # 完了報告
    summary = (
        f"✅ **プライム市場 全件スキャン完了** ({now_str})\n"
        f"└ スキャン対象: {total_count}件\n"
        f"└ 反発候補(買): **{found_buy}件** / 調整候補(売): **{found_sell}件**\n"
        f"{'📢 合致する銘柄がありました。大引けでの判断を推奨します。' if (found_buy + found_sell) > 0 else '📢 本日は強いシグナルが出ている銘柄はありませんでした。'}"
    )
    requests.post(DISCORD_WEBHOOK_URL, json={"username": "株監視AI教授", "content": summary})
