import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import time
import os  # ファイル確認に必要
from datetime import datetime, timedelta, timezone

# --- 設定 ---
# ご指定のDiscord Webhook URLを統合済み
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
    # 実行フォルダに prime_list.csv がある場合はそれを読み込む
    if os.path.exists('prime_list.csv'):
        df = pd.read_csv('prime_list.csv')
        return {f"{str(c).split('.')[0]}.T": n for c, n in zip(df['コード'], df['銘柄名'])}
    
    # CSVがない場合のテスト用リスト
    return {
        "9101.T": "日本郵船", "8035.T": "東エレク", 
        "9984.T": "ソフトバンクG", "7203.T": "トヨタ",
        "5401.T": "日本製鉄", "8306.T": "三菱UFJ"
    }

def analyze_stock(ticker, name):
    try:
        tkr = yf.Ticker(ticker)
        # 指標計算に必要な期間（200日移動平均のため1年以上）
        df = tkr.history(period="1y", interval="1d")
        if len(df) < 200: return None

        # --- テクニカル指標計算 ---
        # 1. 移動平均線 (60日, 200日)
        df['MA60'] = df['Close'].rolling(window=60).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()
        
        # 2. RSI (14日)
        df.ta.rsi(length=14, append=True)
        
        # 3. RCI (短期9日, 長期26日)
        df['RCI9'] = calculate_rci(df['Close'], 9)
        df['RCI26'] = calculate_rci(df['Close'], 26)

        # 最新データ取得
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # --- 判定ロジック ---
        
        # A. 低PBR判定 (1.0以下)
        pbr = tkr.info.get('priceToBook', 99.0)
        is_low_pbr = pbr <= 1.0
        
        # B. 日足で3日前から現在までにRSI・RCI共に90以上
        # tail(3)の期間内で、RSIの最大値が90以上 かつ RCIの最大値が90以上
        recent_window = df.tail(3)
        is_overheated = (recent_window['RSI_14'].max() >= 90) and (recent_window['RCI9'].max() >= 90)

        # C. RCIゴールデンクロス (短期が長期を上回る かつ 短期が前日より上向き)
        rci_gc = (curr['RCI9'] > curr['RCI26']) and (curr['RCI9'] > prev['RCI9'])

        # D. MAトレンド判定
        ma60_trend = "上昇📈" if curr['MA60'] > prev['MA60'] else "下降📉"
        ma200_trend = "上昇📈" if curr['MA200'] > prev['MA200'] else "下降📉"

        # --- 総合フィルター ---
        if is_low_pbr and is_overheated and rci_gc:
            return {
                "name": name, "code": ticker, "price": int(curr['Close']),
                "pbr": round(pbr, 2), "rsi": round(curr['RSI_14'], 1), 
                "rci_s": round(curr['RCI9'], 1),
                "ma60_trend": ma60_trend, "ma200_trend": ma200_trend
            }
        return None
    except:
        return None

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    print(f"🕵️ プライム市場 大引け前哨戒開始: {datetime.now(jst).strftime('%H:%M')}")
    
    targets = get_prime_tickers()
    sent_count = 0
    
    for ticker, name in targets.items():
        res = analyze_stock(ticker, name)
        if res:
            content = (
                f"🦅 **AI監視レポート: プライム急騰候補**\n"
                f"🎯 **{res['name']}({res['code']})**\n"
                f"└ 価格: {res['price']}円 / PBR: {res['pbr']}倍\n"
                f"└ RSI: {res['rsi']} / RCI短期: {res['rci_s']}\n"
                f"└ MA60: {res['ma60_trend']} / MA200: {res['ma200_trend']}\n"
                f"└ **RCIゴールデンクロス検知！**\n"
                f"📢 **大引け買い検討条件に合致。極めて強いモメンタムです。**"
            )
            requests.post(DISCORD_WEBHOOK_URL, json={"username": "株監視AI教授", "content": content})
            sent_count += 1
            time.sleep(1.5) # API負荷制限対策
            
    print(f"🏁 哨戒完了。{sent_count} 件を通知しました。")
