import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import time
from datetime import datetime, timedelta, timezone

# --- 設定 ---
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme" # ここにURLを貼り付け

def calculate_rci(series, period):
    """RCI(順位相関指数)を計算する関数"""
    n = period
    rank_period = pd.Series(range(n, 0, -1))
    def rci_func(x):
        d = ((pd.Series(x).rank(ascending=False) - rank_period)**2).sum()
        return (1 - (6 * d) / (n * (n**2 - 1))) * 100
    return series.rolling(window=n).apply(rci_func)

def get_prime_tickers():
    """プライム市場の銘柄リストを取得（簡易版：JPX400をベースに拡張または手動リスト）"""
    # 本来はJPXの公式サイトから全銘柄取得が理想ですが、ここでは主要なプライム銘柄の例
    # 運用時は jpx400.csv をプライム全銘柄(約1600社)のCSVに差し替えてください
    if os.path.exists('prime_list.csv'):
        df = pd.read_csv('prime_list.csv')
        return {f"{str(c).split('.')[0]}.T": n for c, n in zip(df['コード'], df['銘柄名'])}
    return {"9101.T": "日本郵船", "8035.T": "東レク", "9984.T": "ソフトバンクG", "7203.T": "トヨタ"}

def analyze_stock(ticker, name):
    try:
        tkr = yf.Ticker(ticker)
        # 指標計算に必要な期間（200日移動平均のため1年以上）
        df = tkr.history(period="1y", interval="1d")
        if len(df) < 200: return None

        # --- テクニカル指標 ---
        # 1. 移動平均線 (60日, 200日)
        df['MA60'] = df['Close'].rolling(window=60).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()
        ma_trend = "上昇" if df['MA60'].iloc[-1] > df['MA60'].iloc[-2] else "下降"

        # 2. RSI (14日)
        df.ta.rsi(length=14, append=True)
        rsi = df['RSI_14'].iloc[-1]

        # 3. RCI (短期9日, 長期26日)
        df['RCI9'] = calculate_rci(df['Close'], 9)
        df['RCI26'] = calculate_rci(df['Close'], 26)
        rci_short = df['RCI9'].iloc[-1]
        rci_long = df['RCI26'].iloc[-1]

        # 4. PBR取得 (info APIは重いため候補絞り込み後でも良いが今回は含める)
        pbr = tkr.info.get('priceToBook', 99.0)

        # --- 判定ロジック ---
        # A. 低PBR判定 (1.0以下)
        is_low_pbr = pbr <= 1.0
        
        # B. 3日前から現在までにRSIとRCIが90以上になったことがあるか
        recent_max_rsi = df['RSI_14'].tail(3).max()
        recent_max_rci = df['RCI9'].tail(3).max()
        is_overheated = recent_max_rsi >= 90 and recent_max_rci >= 90

        # C. RCIゴールデンクロス (短期が長期を上回る or 短期が上向き)
        rci_gc = rci_short > rci_long and df['RCI9'].iloc[-1] > df['RCI9'].iloc[-2]

        # --- 総合フィルター ---
        if is_low_pbr and is_overheated and rci_gc:
            return {
                "name": name, "code": ticker, "price": int(df['Close'].iloc[-1]),
                "pbr": round(pbr, 2), "rsi": round(rsi, 1), 
                "rci_s": round(rci_short, 1), "ma_trend": ma_trend
            }
        return None
    except Exception as e:
        return None

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    print(f"🕵️ プライム市場 大引け前哨戒開始: {datetime.now(jst).strftime('%H:%M')}")
    
    targets = get_prime_tickers()
    for ticker, name in targets.items():
        res = analyze_stock(ticker, name)
        if res:
            content = (
                f"🦅 **AI監視レポート: プライム急騰候補**\n"
                f"🎯 **{res['name']}({res['code']})**\n"
                f"└ 価格: {res['price']}円 / PBR: {res['pbr']}倍\n"
                f"└ RSI: {res['rsi']} / RCI短期: {res['rci_s']}\n"
                f"└ MAトレンド: {res['ma_trend']} / RCIゴールデンクロス検知\n"
                f"📢 **大引け買い検討ゾーン。極めて強いモメンタムです。**"
            )
            requests.post(DISCORD_WEBHOOK_URL, json={"username": "株監視AI教授", "content": content})
            time.sleep(1.5) # 大量スキャン時の制限回避
