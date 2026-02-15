import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# 📊 判定ロジック：MACD, RSI, 平均足
# ==========================================
def get_analysis(ticker, name):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        if len(hist) < 60: return None
        curr_price = int(hist["Close"].iloc[-1])

        # MACD
        ema12 = hist['Close'].ewm(span=12, adjust=False).mean()
        ema26 = hist['Close'].ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        
        # RSI
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]

        # 反転フロア予測
        ma20 = hist['Close'].rolling(20).mean()
        std20 = hist['Close'].rolling(20).std()
        floor = max(int(ma20.iloc[-1] - (std20.iloc[-1] * 2)), int(hist['Low'].tail(60).min()))

        return {
            "コード": ticker.replace(".T", ""), "銘柄名": name, "現在値": curr_price,
            "RSI": round(rsi, 1), "MACD": "GC(上昇)" if macd.iloc[-1] > signal.iloc[-1] else "DC(下落)",
            "フロア": floor, "指値目安": int(floor * 1.01),
            "利確目標": int(hist['High'].tail(25).max()), "損切目安": int(floor * 0.97)
        }
    except: return None

# ==========================================
# 🦅 画面表示 (日本語・高精度モデル)
# ==========================================
st.set_page_config(page_title="最強株スキャナー", layout="wide")
st.title("🦅 最強株スキャナー (全機能・全シグナル統合版)")

# 翻訳エラー回避用の設定
st.markdown('<meta name="google" content="notranslate">', unsafe_allow_html=True)

code_in = st.text_input("銘柄コードを入力 (例: 6701)", "").strip()
if code_in:
    full_c = code_in + ".T" if ".T" not in code_in else code_in
    res = get_analysis(full_c, code_in)
    if res:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("現在値", f"{res['現在値']}円")
            st.info(f"🛡️ 反転予想フロア: {res['フロア']}円")
        with c2:
            st.success(f"指値目安: {res['指値目安']}円")
            st.write(f"🎯 利確: {res['利確目標']}円 / 🛑 損切: {res['損切目安']}円")
        with c3:
            st.write(f"MACD状態: **{res['MACD']}**")
            st.write(f"RSI(14): **{res['RSI']}**")
