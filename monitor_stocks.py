import io
import time
from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import requests
import yfinance as yf

# ==============================================================================
# --- 設定項目 ---
# ==============================================================================
# 取得したDiscordのWebhook URLを設定してください
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1472281747000393902/Fbclh0R3R55w6ZnzhenJ24coaUPKy42abh3uPO-fRjfQulk9OwAq-Cf8cJQOe2U4SFme"

# パトロール巡回タイミングの設定 (11:00時点の中間巡回なら True, 大引け後なら False)
IS_MIDDAY_PATROL = False  # Trueにすると、当日出来高のフィルター倍率が「2.0倍」から「0.6倍」に緩和されます

# ==============================================================================
# --- テクニカル指標計算関数群（高速ベクトル演算ベース） ---
# ==============================================================================
def calculate_rci(df_close, period):
    """
    RCI (Rank Correlation Index) を計算する関数
    Rolling.applyは低速なため、可能な限り最適化した計算を行います
    """
    def _rci_calc(window):
        n = len(window)
        if n < period:
            return np.nan
        price_ranks = pd.Series(window).rank(ascending=False, method='max').values
        time_ranks = np.arange(n, 0, -1)
        d2 = np.sum((price_ranks - time_ranks) ** 2)
        return (1 - (6 * d2) / (n * (n**2 - 1))) * 100

    return df_close.rolling(window=period).apply(_rci_calc, raw=True)


def calculate_psy(df_close, period=12):
    """サイコロジカルラインを計算する関数"""
    diff = df_close.diff()
    up_days = (diff > 0).astype(int)
    return (up_days.rolling(window=period).sum() / period) * 100


def calculate_dmi(df_high, df_low, df_close, di_period=14, adx_period=9):
    """
    DMI (+DI, -DI, ADX) を計算する関数
    マスピ2仕様：ADX期間を「9」にカスタムして初動検知を爆速化
    """
    up_move = df_high.diff()
    down_move = df_low.diff() * -1

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    # トゥルー・レンジ (TR) の計算
    tr1 = df_high - df_low
    tr2 = (df_high - df_close.shift(1)).abs()
    tr3 = (df_low - df_close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # 期間平滑化
    tr_smooth = tr.rolling(window=di_period).sum()
    plus_dm_smooth = pd.Series(plus_dm, index=df_close.index).rolling(window=di_period).sum()
    minus_dm_smooth = pd.Series(minus_dm, index=df_close.index).rolling(window=di_period).sum()

    plus_di = (plus_dm_smooth / (tr_smooth + 1e-9)) * 100
    minus_di = (minus_dm_smooth / (tr_smooth + 1e-9)) * 100

    # DX および ADX (期間=9)
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9) * 100
    adx = dx.rolling(window=adx_period).mean()

    return plus_di, minus_di, adx


def calculate_atr(df_high, df_low, df_close, period=14):
    """常時5ポイント以上の値動きを計測するためのATR (Average True Range)"""
    tr1 = df_high - df_low
    tr2 = (df_high - df_close.shift(1)).abs()
    tr3 = (df_low - df_close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


# ==============================================================================
# --- 酒田五法・ローソク足パターン判定関数 ---
# ==============================================================================
def detect_sakata_candlestick(open_p, high_p, low_p, close_p):
    """
    直近のローソク足から酒田五法のエッセンス（下ヒゲ・十字線・上ヒゲなど）を判定する関数
    戻り値: (is_bullish_pattern, is_bearish_pattern, pattern_name)
    """
    body = abs(close_p - open_p)
    total_range = high_p - low_p
    if total_range == 0:
        total_range = 1e-9

    upper_shaved = high_p - max(open_p, close_p)
    lower_shaved = min(open_p, close_p) - low_p

    # 1. 十字線 (同時線) - 売り買い拮抗・トレンド転換暗示
    if body <= (total_range * 0.1):
        return True, True, "十字線(転換暗示)"

    # 2. 下ヒゲ（カラカサ・タクリ足）- 底打ち・強烈な買い支え
    if lower_shaved >= (body * 2.0) and upper_shaved <= (body * 0.5):
        return True, False, "下ヒゲ(底打ちシグナル)"

    # 3. 上ヒゲ（流れ星）- 天井圏での売り圧力
    if upper_shaved >= (body * 2.0) and lower_shaved <= (body * 0.5):
        return False, True, "上ヒゲ(天井警戒シグナル)"

    return False, False, ""


# ==============================================================================
# --- 東証上場銘柄リストの取得 ---
# ==============================================================================
def get_ticker_list():
    """JPX公式からプライム・スタンダード銘柄のコードと銘柄名マッピングを取得"""
    headers = {"User-Agent": "Mozilla/5.0"}
    url = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
    try:
        res = requests.get(url, headers=headers, timeout=20)
        df = pd.read_excel(io.BytesIO(res.content))
        target_df = df[df['市場・商品区分'].str.contains('プライム|スタンダード', na=False)]
        return {f"{row['コード']}.T": row['銘柄名'] for _, row in target_df.iterrows()}
    except Exception as e:
        print(f"銘柄リスト取得失敗、バックアップを適用します: {e}")
        return {"7203.T": "トヨタ自動車", "9984.T": "ソフトバンクG", "8306.T": "三菱UFJ"}


# ==============================================================================
# --- Discord 通知管理 ---
# ==============================================================================
def send_discord(content):
    """Discordの2000文字制限を回避しながら安全に分割送信する関数"""
    if not content:
        return
    for i in range(0, len(content), 1900):
        try:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": content[i:i+1900]}, timeout=10)
        except Exception as e:
            print(f"Discord送信エラー: {e}")
        time.sleep(1)


# ==============================================================================
# --- メインロジック ---
# ==============================================================================
def main():
    jst = timezone(timedelta(hours=9))
    current_time_str = datetime.now(jst).strftime('%Y/%m/%d %H:%M')
    print(f"[{current_time_str}] パトロールを開始します...")

    ticker_map = get_ticker_list()
    tickers = list(ticker_map.keys())

    # 結果格納用フォルダー
    results = {
        "🏹 ルールA：【最優先】大底からの反転初動（即買い・鉄板）": [],
        "📈 ルールB：反転予兆（監視強化フラグ・マイフォルダー登録）": [],
        "🛑 ルールC：利益確定・下落警戒": []
    }
    copy_lists = {"A": [], "B": [], "C": []}

    # yfinanceへの負荷とエラーを抑えるため、100銘柄ずつのチャンクで一括ダウンロード
    chunk_size = 100
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i+chunk_size]
        print(f"スキャン進行中: {i}/{len(tickers)} 銘柄...")
        try:
            # トリプルフィルター判定（3ヶ月平均=60営業日）のため、余裕を持って「1年分」取得
            data = yf.download(chunk, period="1y", interval="1d", progress=False, group_by='ticker')
            
            for ticker in chunk:
                try:
                    if ticker not in data.columns.get_level_values(0):
                        continue
                    
                    df = data[ticker].dropna()
                    # 指標計算に必要な最低限のローソク足本数（60日以上）を確保
                    if len(df) < 65:
                        continue

                    # --- 基本データの抽出 ---
                    close_s = df['Close']
                    high_s = df['High']
                    low_s = df['Low']
                    vol_s = df['Volume']

                    curr_price = close_s.iloc[-1]

                    # 🔹 デイトレ・スイング最適化フィルター（低位株排除：500円以上）
                    if curr_price < 500:
                        continue

                    # 🔹 デイトレ・スイング最適化フィルター（常時5ポイント以上の値動き：ATR14が5円以上）
                    atr_s = calculate_atr(high_s, low_s, close_s, period=14)
                    if atr_s.iloc[-1] < 5.0:
                        continue

                    # ==========================================
                    # 🛑 必須前提：出来高トリプルフィルター
                    # ==========================================
                    # 1. 最低流動性: 3ヶ月（60営業日）平均出来高が 50万株以上
                    avg_vol_3m = vol_s.tail(60).mean()
                    if avg_vol_3m < 500000:
                        continue

                    # 2. エネルギー: 当日出来高が3ヶ月平均の 2.0倍以上 (中間巡回時は0.6倍以上)
                    required_ratio = 0.6 if IS_MIDDAY_PATROL else 2.0
                    if vol_s.iloc[-1] < (avg_vol_3m * required_ratio):
                        continue

                    # 3. 資金の定着: 直近5日間の移動平均出来高が3ヶ月平均の 1.2倍以上
                    avg_vol_5d = vol_s.tail(5).mean()
                    if avg_vol_5d < (avg_vol_3m * 1.2):
                        continue

                    # ==========================================
                    # --- テクニカルインジケーター計算（マスピ2仕様） ---
                    # ==========================================
                    rci9 = calculate_rci(close_s, 9)
                    rci27 = calculate_rci(close_s, 27)
                    psy12 = calculate_psy(close_s, 12)
                    plus_di, minus_di, _ = calculate_dmi(high_s, low_s, close_s, di_period=14, adx_period=9)

                    # 直近値(当日)および前日・前々日値の抽出
                    c_rci9, p_rci9 = rci9.iloc[-1], rci9.iloc[-2]
                    c_rci27, p_rci27 = rci27.iloc[-1], rci27.iloc[-2]
                    c_psy, p_psy = psy12.iloc[-1], psy12.iloc[-2]
                    c_pdi, c_mdi = plus_di.iloc[-1], minus_di.iloc[-1]
                    p_pdi, p_mdi = plus_di.iloc[-2], minus_di.iloc[-2]

                    # 25日VWAPの計算（出来高加重移動平均）
                    vwap25 = (close_s * vol_s).rolling(25).sum() / vol_s.rolling(25).sum()
                    c_vwap = vwap25.iloc[-1]

                    # ==========================================
                    # --- 酒田五法・最終ローソク足判定 ---
                    # ==========================================
                    is_bull_candle, is_bear_candle, candle_name = detect_sakata_candlestick(
                        df['Open'].iloc[-1], high_s.iloc[-1], low_s.iloc[-1], curr_price
                    )
                    
                    # 包み足 (抱き線) の判定
                    is_engulfing_bull = (close_s.iloc[-1] > df['Open'].iloc[-1]) and \
                                        (df['Open'].iloc[-1] <= close_s.iloc[-2]) and \
                                        (close_s.iloc[-1] >= df['Open'].iloc[-2]) and \
                                        (close_s.iloc[-2] < df['Open'].iloc[-2])
                                        
                    is_engulfing_bear = (close_s.iloc[-1] < df['Open'].iloc[-1]) and \
                                        (df['Open'].iloc[-1] >= close_s.iloc[-2]) and \
                                        (close_s.iloc[-1] <= df['Open'].iloc[-2]) and \
                                        (close_s.iloc[-2] > df['Open'].iloc[-2])

                    if is_engulfing_bull:
                        is_bull_candle, candle_name = True, "陽線の包み足(抱き線)"
                    if is_engulfing_bear:
                        is_bear_candle, candle_name = True, "陰線の包み足(抱き線)"

                    # 通知用の基本銘柄情報テキスト作成
                    candle_info = f" 【酒田五法: {candle_name}】" if candle_name else ""
                    vwap_status = " (VWAP下乖離)" if curr_price < c_vwap else " (VWAP上抜け)"
                    info_text = f"・{ticker_map[ticker]}({ticker}) {int(curr_price)}円 [RCI9:{int(c_rci9)}/RCI27:{int(c_rci27)} PSY:{int(c_psy)}]{vwap_status}{candle_info}"
                    code_raw = ticker.replace(".T", "")

                    # ==========================================
                    # 🎯 売買ルール判定ロジック
                    # ==========================================
                    
                    # --- 🏹 ルールA：【最優先】大底からの反転初動（即買い・鉄板） ---
                    # 条件1: 長期RCI(27)が -50 以上の位置をキープ
                    # 条件2: 短期RCI(9)が -90 付近から上向き、または -80から-50を明確に上抜いた
                    # 条件3: サイコロ(12)が 25付近から上向き、または 30付近の停滞から上放れ
                    # 条件4: DMIが強烈に接近、またはクロス（前日より距離縮小 or クロス完了）
                    cond_a_rci27 = (c_rci27 >= -50)
                    cond_a_rci9 = (p_rci9 <= -85 and c_rci9 > p_rci9) or (p_rci9 < -50 and c_rci9 >= -50)
                    cond_a_psy = (p_psy <= 26 and c_psy > p_psy) or (p_psy <= 34 and c_psy > p_psy)
                    cond_a_dmi = (abs(c_pdi - c_mdi) < abs(p_pdi - p_mdi)) or (p_pdi < p_mdi and c_pdi >= c_mdi)

                    if cond_a_rci27 and cond_a_rci9 and cond_a_psy and cond_a_dmi:
                        # 酒田五法フィルターによる最終合格の可視化
                        if is_bull_candle:
                            info_text += " ✨[酒田五法・最終判定一致]"
                        results["🏹 ルールA：【最優先】大底からの反転初動（即買い・鉄板）"].append(info_text)
                        copy_lists["A"].append(code_raw)
                        continue  # 重複登録を防ぐため合致したら次へ

                    # --- 📈 ルールB：反転予兆（監視強化フラグ） ---
                    # 条件1: 短期RCI(9)が -80 以下の底圏にへばりついている
                    # 条件2: サイコロ(12)が 25~35 の底圏で停滞中
                    # 条件3: DMIの距離が前日より縮まり、お互いに接近を開始した初日
                    cond_b_rci9 = (c_rci9 <= -80)
                    cond_b_psy = (25 <= c_psy <= 35)
                    cond_b_dmi = (abs(c_pdi - c_mdi) < abs(p_pdi - p_mdi)) and (p_pdi - p_mdi > 0 if c_pdi < c_mdi else p_mdi - p_pdi > 0)

                    if cond_b_rci9 and cond_b_psy and cond_b_dmi:
                        results["📈 ルールB：反転予兆（監視強化フラグ・マイフォルダー登録）"].append(info_text)
                        copy_lists["B"].append(code_raw)
                        continue

                    # --- 🛑 ルールC：利益確定・下落警戒 ---
                    # 条件1: 短期RCI(9)が +90 付近の過熱圏に到達し、下向きに折れた瞬間
                    # 条件2: 短期RCIが長期RCIを上でDCし、その数値が +70 以上
                    # 条件3: サイコロが 75 以上の過熱圏から下向きに反転したとき
                    # 条件4: (補足条件) 長期RCI(27)が90付近から下向きに折れた時も逃げ足速く売り
                    cond_c_rci9_turn = (p_rci9 >= 85 and c_rci9 < p_rci9)
                    cond_c_dc = (p_rci9 > p_rci27 and c_rci9 <= c_rci27 and c_rci9 >= 70)
                    cond_c_psy = (p_psy >= 75 and c_psy < p_psy)
                    cond_c_rci27_turn = (p_rci27 >= 90 and c_rci27 < p_rci27)

                    if cond_c_rci9_turn or cond_c_dc or cond_c_psy or cond_c_rci27_turn:
                        if is_bear_candle:
                            info_text += " ⚠️[酒田五法・天井警戒一致]"
                        results["🛑 ルールC：利益確定・下落警戒"].append(info_text)
                        copy_lists["C"].append(code_raw)

                except Exception as e:
                    # 個別銘柄の計算エラーはスキップして継続
                    continue
        except Exception as e:
            print(f"チャンクダウンロードエラー: {e}")
        time.sleep(1)

    # ==========================================
    # --- Discord 送信メッセージの構築 ---
    # ==========================================
    patrol_type = "【前場・中間巡回】" if IS_MIDDAY_PATROL else "【大引け後・確定巡回】"
    msg = f"📋 **テス流・ハイブリッド投資戦略パトロール (マスピ2仕様)**\n"
    msg += f"巡回種別: {patrol_type}\n"
    msg += f"実行日時: {current_time_str}\n"
    msg += f"📌 *フィルター基準: 株価500円以上、ATR5円以上、3ヶ月平均出来高50万株以上、当日の出来高急増クリア銘柄のみ*\n\n"

    has_any_result = False
    for cat, items in results.items():
        if items:
            has_any_result = True
            msg += f"**{cat}**\n" + "\n".join(items) + "\n\n"

    # コピペ用セクションの追加
    msg += "--- 📋 マスピ2一括登録用コードリスト ---\n"
    for key, label in [("A", "ルールA（即買い）"), ("B", "ルールB（監視登録）"), ("C", "ルールC（利確・空売り）")]:
        if copy_lists[key]:
            codes_str = ",".join(sorted(list(set(copy_lists[key]))))
            msg += f"**【{label} 用】**\n```\n{codes_str}\n```\n"

    if not has_any_result:
        msg += "🔍 本日は「出来高トリプルフィルター」および「厳格売買ルール」のすべてを満たすスクリーニング合致銘柄はありませんでした（静観推奨）。"

    # Discordに送信
    send_discord(msg)
    print(f"[{datetime.now(jst).strftime('%Y/%m/%d %H:%M')}] パトロール完了・通知を送信しました。")


if __name__ == "__main__":
    main()
