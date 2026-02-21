import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import os
from datetime import datetime, timedelta, timezone

# --- 設定 ---
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

def load_watchlist_from_excel():
    """エクセル(list.xlsx)から監視リストを読み込む"""
    try:
        # openpyxlが必要（requirements.txtに追加済み）
        df = pd.read_excel('list.xlsx')
        watchlist = {}
        for _, row in df.iterrows():
            code = str(row['code']).strip()
            # 数字のみの場合は .T を付与
            full_code = f"{code}.T" if code.isdigit() else code
            watchlist[full_code] = str(row['name']).strip()
        return watchlist
    except Exception as e:
        print(f"❌ エクセル読み込みエラー: {e}")
        return {}

def calculate_heikin_ashi(df):
    ha_df = df.copy()
    ha_df['HA_Close'] = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4
    ha_df['HA_Open'] = 0.0
    ha_df.iloc[0, ha_df.columns.get_loc('HA_Open')] = (df.iloc[0]['Open'] + df.iloc[0]['Close']) / 2
    for i in range(1, len(df)):
        ha_df.iloc[i, ha_df.columns.get_loc('HA_Open')] = (ha_df.iloc[i-1]['HA_Open'] + ha_df.iloc[i-1]['HA_Close']) / 2
    return ha_df

def analyze_stock(ticker, name):
    try:
        tkr = yf.Ticker(ticker)
        df_d = tkr.history(period="6mo", interval="1d")
        df_w = tkr.history(period="2y", interval="1wk")
        if df_d.empty or df_w.empty: return None

        # 指標計算
        price = df_d.iloc[-1]['Close']
        df_w['MA20'] = df_w['Close'].rolling(20).mean()
        target_p = int(df_w['MA20'].iloc[-1])
        
        ha_w = calculate_heikin_ashi(df_w); w_l = ha_w.iloc[-1]
        ha_d = calculate_heikin_ashi(df_d); d_l = ha_d.iloc[-1]
        
        is_w_up = w_l['HA_Close'] > w_l['HA_Open']
        is_d_up = d_l['HA_Close'] > d_l['HA_Open']
        rsi_w = ta.rsi(df_w['Close'], length=14).iloc[-1]
        dev_w = (price - target_p) / target_p * 100

        # 反発・トレンド判定
        is_oversold = rsi_w < 35 or dev_w < -15
        if is_oversold:
            rebound_msg = f"🎯 反発開始 (目標:{target_p})" if is_d_up else f"⏳ 底打ち模索中 ({target_p})"
            color = 3066993 if is_d_up else 15105570 # 緑色 or オレンジ
        else:
            rebound_msg = "📈 巡航中" if is_d_up else "📉 調整中"
            color = 3447003 if is_d_up else 10070709 # 青色 or 灰色

        score = (50 if is_w_up else -50) + (40 if is_oversold else 0) + (30 if is_d_up else -30)

        return {
            "code": ticker.replace(".T",""), "name": name, "price": int(price),
            "msg": rebound_msg, "color": color, "score": int(score),
            "target": target_p, "rsi": round(rsi_w, 1)
        }
    except: return None

def send_discord(data, session_name):
    payload = {
        "username": "最強株哨戒機 🦅",
        "embeds": [{
            "title": f"【{session_name}】{data['name']} ({data['code']})",
            "description": f"**現在値: {data['price']}円**\n判定: {data['msg']}",
            "color": data['color'],
            "fields": [
                {"name": "🧠 スコア", "value": f"{data['score']}点", "inline": True},
                {"name": "🌊 週RSI", "value": f"{data['rsi']}", "inline": True},
                {"name": "🎯 目標(20週線)", "value": f"{data['target']}円", "inline": True}
            ],
            "footer": {"text": f"観測時刻: {(datetime.now(timezone(timedelta(hours=9)))).strftime('%H:%M')}"}
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

if __name__ == "__main__":
    # 日本時間を取得
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    h = now.hour
    
    if 9 <= h < 11: session = "前場・観測"
    elif 13 <= h < 15: session = "後場・観測"
    elif 15 <= h < 18: session = "大引け・報告"
    else: session = "時間外・特別哨戒"

    watchlist = load_watchlist_from_excel()
    for t, n in watchlist.items():
        res = analyze_stock(t, n)
        if res: send_discord(res, session)
