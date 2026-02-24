import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import os
from datetime import datetime, timedelta, timezone

# --- 設定 ---
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

# 主要銘柄の和名データベース（エクセルに名前がない場合のバックアップ）
NAME_MAP = {
    "8035.T": "東京エレクトロン", "6920.T": "レーザーテック", "6857.T": "アドバンテスト",
    "6723.T": "ルネサス", "6758.T": "ソニーグループ", "6501.T": "日立製作所",
    "7203.T": "トヨタ自動車", "7267.T": "ホンダ", "7270.T": "SUBARU",
    "8306.T": "三菱UFJ", "9101.T": "日本郵船", "9104.T": "商船三井", "9107.T": "川崎汽船",
    "9984.T": "ソフトバンクG", "6330.T": "東洋エンジ", "4755.T": "楽天グループ"
}

def load_watchlist_from_excel():
    """エクセルから監視リストを読み込む（和名の補完付き）"""
    try:
        if not os.path.exists('list.xlsx'):
            print("⚠️ list.xlsx が見つかりません。")
            return {k: v for k, v in NAME_MAP.items()} # ファイルがない時はDBを返す

        df = pd.read_excel('list.xlsx')
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        code_candidates = ['code', 'コード', '銘柄コード', '証券コード']
        code_col = next((c for c in code_candidates if c in df.columns), None)
        name_candidates = ['name', '銘柄名', '名前', '会社名']
        name_col = next((c for c in name_candidates if c in df.columns), None)

        if code_col is None: return {}

        watchlist = {}
        for _, row in df.iterrows():
            code = str(row[code_col]).strip().split('.')[0]
            full_code = f"{code}.T" if code.isdigit() else code
            
            # 1. エクセルに名前があればそれを使う
            # 2. なければ NAME_MAP から探す
            # 3. どちらもなければコードを表示
            name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else NAME_MAP.get(full_code, f"銘柄:{code}")
            watchlist[full_code] = name
            
        return watchlist
    except Exception as e:
        print(f"❌ エラー: {e}")
        return {}

def analyze_stock(ticker, name):
    try:
        tkr = yf.Ticker(ticker)
        df_d = tkr.history(period="6mo", interval="1d")
        df_w = tkr.history(period="2y", interval="1wk")
        if df_d.empty or df_w.empty: return None

        price = df_d.iloc[-1]['Close']
        
        # 指標計算
        df_d['MA20'] = df_d['Close'].rolling(20).mean()
        df_w['MA20'] = df_w['Close'].rolling(20).mean()
        target_p = int(df_w['MA20'].iloc[-1])
        rsi_w = ta.rsi(df_w['Close'], length=14).iloc[-1]
        dev_w = (price - target_p) / target_p * 100

        # トレンド判定
        is_w_up = df_w['Close'].iloc[-1] > df_w['Open'].iloc[-1]
        is_d_up = df_d['Close'].iloc[-1] > df_d['Open'].iloc[-1]
        
        # スコアリング
        score = (50 if is_w_up else -50) + (30 if is_d_up else -30)
        is_oversold = rsi_w < 35 or dev_w < -15
        if is_oversold: score += 40

        # 判定メッセージと色
        if score >= 60:
            msg = "🚀 特級買 (上昇一致)"; color = 3066993 # 緑
        elif score <= -60:
            msg = "📉 特級売 (下落一致)"; color = 15158332 # 赤
        elif is_oversold:
            msg = "🎯 反発狙い (売られすぎ)"; color = 15105570 # オレンジ
        else:
            msg = "☁️ 様子見"; color = 10070709 # グレー

        return {
            "code": ticker.replace(".T",""), "name": name, "price": int(price),
            "msg": msg, "color": color, "score": int(score),
            "target": target_p, "rsi": round(rsi_w, 1)
        }
    except: return None

def send_discord(data, session_name):
    """Discordへの通知をより見やすく整形"""
    payload = {
        "username": "Stock Sniper 🦅",
        "embeds": [{
            "title": f"【{session_name}】{data['name']} ({data['code']})",
            "description": f"**現在値: {data['price']}円**\n判定: **{data['msg']}**",
            "color": data['color'],
            "fields": [
                {"name": "🧠 スコア", "value": f"{data['score']}点", "inline": True},
                {"name": "🌊 週RSI", "value": f"{data['rsi']}", "inline": True},
                {"name": "🎯 利確目標", "value": f"{data['target']}円", "inline": True}
            ],
            "footer": {"text": f"観測時刻: {datetime.now(timezone(timedelta(hours=9))).strftime('%Y/%m/%d %H:%M')}"}
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

if __name__ == "__main__":
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    h = now.hour
    m = now.minute

    # セッション判定の微調整
    if 9 <= h < 11: session = "前場・観測"
    elif 11 <= h < 13: session = "昼休み・分析"
    elif 13 <= h < 15: session = "後場・観測"
    elif 15 <= h < 16: session = "大引け・報告"
    else: session = "夜間・特別哨戒"

    watchlist = load_watchlist_from_excel()
    for t, n in watchlist.items():
        res = analyze_stock(t, n)
        # スコアが一定以上/以下の「動いている銘柄」だけ通知するとノイズが減ります
        if res:
            send_discord(res, session)
