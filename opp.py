import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# 🛡️ 銘柄マスタ (トモユキさんの監視リスト)
# ==========================================
NAME_MAP = {
    "6701.T": "NEC", "4901.T": "富士フイルム", "5406.T": "神戸鋼", "7049.T": "識学",
    "8306.T": "三菱UFJ", "7203.T": "トヨタ", "9984.T": "SBG", "8035.T": "東エレク",
    "6330.T": "東洋エンジ", "4063.T": "信越化学", "7974.T": "任天堂", "8151.T": "東陽テク"
}

# ==========================================
# 🌐 決算日チェック (株探連携)
# ==========================================
def scrape_earnings_date(code):
    clean_code = code.replace(".T", "")
    url = f"https://kabutan.jp/stock/finance?code={clean_code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        target = soup.find(string=re.compile(r"決算発表予定日"))
        if target:
            match = re.search(r"(\d{2}/\d{2}/\d{2})", str(target.parent.get_text()))
            if match: return datetime.strptime("20" + match.group(1), "%Y/%m/%d").date()
    except: pass
    return None

# ==========================================
# 🕯️ パターン検知ロジック (MACD, RSI, 平均足)
# ==========================================
def detect_patterns(df, rsi):
    if len(df) < 30: return None, 0, "neutral"
    close, high, low, open_p = df['Close'], df['High'], df['Low'], df['Open']
    curr_price = close.iloc[-1]
    
    # 1. 継続サイン：フラッグ
    if all(high.iloc[i] < high.iloc[i-1] for i in range(-3, 0)) and \
       (high.tail(5).max() - low.tail(5).min()) < (curr_price * 0.04):
        return "🚩上昇フラッグ", 75, "buy"

    # 2. 反転サイン：明けの明星
    if rsi < 50:
        if (close.iloc[-3] < open_p.iloc[-3] and close.iloc[-1] > open_p.iloc[-1]):
            return "🌅明けの明星", 90, "buy"
        l_vals = low.tail(15).values
        if l_vals.min() == l_vals[5:10].min() and l_vals[0:5].min() > l_vals[5:10].min():
            return "💎逆三尊", 80, "buy"

    # 3. 売りサイン：三尊
    if rsi > 50:
        h_vals = high.tail(15).values
        if h_vals.max() == h_vals[5:10].max() and h_vals[0:5].max() < h_vals[5:10].max():
            return "💀三尊(天井)", 85, "sell"

    return None, 0, "neutral"

# ==========================================
# 🧠 精密分析エンジン (スイング・決算・戦略)
# ==========================================
def get_analysis(ticker, name):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        if len(hist) < 60: return None
        curr_price = int(hist["Close"].iloc[-1])

        # 指標計算
        ema12 = hist['Close'].ewm(span=12, adjust=False).mean()
        ema26 = hist['Close'].ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]

        # 床の計算 (ボリンジャー-2σ & 60日安値)
        ma20 = hist['Close'].rolling(20).mean()
        std20 = hist['Close'].rolling(20).std()
        # LaTeX: 反転フロアの算出式
        # $$Floor = \max(MA_{20} - 2\sigma, \min(Low_{60}))$$
        floor = max(int(ma20.iloc[-1] - (std20.iloc[-1] * 2)), int(hist['Low'].tail(60).min()))

        # 決算チェック
        earn_date = scrape_earnings_date(ticker)
        days = (earn_date - datetime.now().date()).days if earn_date else 999
        is_risk = (0 <= days <= 3) # 盾
        is_earn_short = (0 <= days <= 14) and (rsi > 70) # 矛

        p_name, p_score, sig_type = detect_patterns(hist, rsi)

        return {
            "コード": ticker.replace(".T", ""), "銘柄名": name, "現在値": curr_price,
            "RSI": round(rsi, 1), "MACD": "GC" if macd.iloc[-1] > signal.iloc[-1] else "DC",
            "フロア": floor, "指値目安": int(floor * 1.01),
            "パターン": p_name if p_name else "なし", "利確": int(hist['High'].tail(25).max()),
            "損切": int(floor * 0.97), "決算": earn_date if earn_date else "未定",
            "is_risk": is_risk, "is_earn_short": is_earn_short
        }
    except: return None

# ==========================================
# 📱 画面レイアウト
# ==========================================
st.set_page_config(page_title="最強株スキャナー・最終版", layout="wide")
st.title("🦅 最強株スキャナー (全機能・全シグナル統合版)")

code_in = st.text_input("銘柄コードを入力 (例: 6701)", "").strip()
if code_in:
    full_c = code_in + ".T" if ".T" not in code_in else code_in
    res = get_analysis(full_c, NAME_MAP.get(full_c, code_in))
    if res:
        if res["is_risk"]: st.error(f"🛑 取引禁止：決算({res['決算']})直前につき防御発動中")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("現在値", f"{res['現在値']}円")
            st.warning(f"🛡️ 反転予想フロア: {res['フロア']}円")
        with col2:
            st.success(f"指値目安: {res['指値目安']}円")
            st.write(f"🎯 利確: {res['利確']}円 / 🛑 損切: {res['損切']}円")
        with col3:
            st.write(f"出現サイン: **{res['パターン']}**")
            st.write(f"MACD: {res['MACD']} / RSI: {res['RSI']}")

st.divider()

if st.button("全銘柄を一斉スキャニング", use_container_width=True):
    with ThreadPoolExecutor(max_workers=5) as ex:
        ds = [ex.submit(get_analysis, t, n).result() for t, n in NAME_MAP.items()]
    ds = [d for d in ds if d]
    if ds:
        df = pd.DataFrame(ds)
        st.subheader("🔥 買い推奨 (現物・信用買い)")
        st.dataframe(df[df["RSI"] < 50][["コード","銘柄名","現在値","RSI","MACD","パターン","指値目安","利確","損切"]], hide_index=True)
        
        st.subheader("📉 空売り推奨 (信用売り)")
        st.dataframe(df[df["RSI"] > 60][["コード","銘柄名","現在値","RSI","MACD","パターン","決算"]], hide_index=True)