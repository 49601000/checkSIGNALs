import streamlit as st
import yfinance as yf
import pandas as pd
import math
from datetime import datetime, time
import pytz

# -----------------------------------------------------------
# Streamlit 基本設定
# -----------------------------------------------------------
st.set_page_config(page_title="✅任意銘柄の買いシグナルをチェック", page_icon="📊")
st.title("🔍買いシグナルチェッカー")


# -----------------------------------------------------------
# ティッカー変換（東証銘柄は自動で .T を付ける）
# -----------------------------------------------------------
def convert_ticker(ticker):
    ticker = ticker.strip().upper()
    if ticker.endswith('.T') or not ticker.isdigit():
        return ticker
    return ticker + ".T"


# -----------------------------------------------------------
# 市場コード → 正規化
# -----------------------------------------------------------
def normalize_exchange(exchange_code: str) -> str:
    mapping = {
        "NMS": "NASDAQ",
        "NAS": "NASDAQ",
        "NASDAQ": "NASDAQ",
        "NYQ": "NYSE",
        "NYA": "NYSE",
        "NYSE": "NYSE",
        "TSE": "東証",
        "JPX": "東証",
        "東証": "東証"
    }
    return mapping.get(exchange_code.upper(), "不明")


# -----------------------------------------------------------
# 市場オープン判定
# -----------------------------------------------------------
def is_market_open(now, open_time, close_time):
    # 日本 → 米国市場のまたぎ対応
    if open_time < close_time:
        return open_time <= now <= close_time
    else:
        return now >= open_time or now <= close_time


# -----------------------------------------------------------
# 市場ステータス生成
# -----------------------------------------------------------
def get_market_status(exchange: str, state: str, status_text: dict = None) -> str:
    exchange = normalize_exchange(exchange)
    now_jst = datetime.now(pytz.timezone("Asia/Tokyo")).time()

    status_map = {
        "NASDAQ": ("NASDAQ", time(22,30), time(5,0)),
        "NYSE":   ("NYSE",   time(22,30), time(5,0)),
        "東証":   ("東証",   time(9,0),   time(15,30))
    }

    label, open_time, close_time = status_map.get(exchange, ("不明", None, None))
    if not open_time or not close_time:
        return f"{label}: 不明"

    is_open = is_market_open(now_jst, open_time, close_time)

    if status_text:
        labels = status_text
    else:
        labels = {"OPEN": "取引中", "CLOSED": "取引終了", "HOLIDAY": "休場中"}

    if state == "REGULAR":
        status = labels["OPEN"] if is_open else labels["CLOSED"]
    else:
        status = labels["HOLIDAY"]

    return f"{label}: {status}"


# -----------------------------------------------------------
# yfinance の info をできるだけ 1 回だけ読むためのヘルパー
# -----------------------------------------------------------
def get_stock_info(ticker_obj):
    """
    info() を一度だけ呼び、必要な項目をまとめて返す。
    """
    info = ticker_obj.info  # ← ★ API 1回目

    return {
        "name_raw": info.get("shortName", ""),
        "industry": info.get("industry", "業種不明"),
        "dividend_yield": info.get("dividendYield", None),
        "per": info.get("trailingPE", None),
        "pbr": info.get("priceToBook", None),
        "market_price": info.get("regularMarketPrice", None),
        "close_price": info.get("previousClose", None),
        "high_52w": info.get("fiftyTwoWeekHigh", None),
        "low_52w": info.get("fiftyTwoWeekLow", None),
        "market_state": info.get("marketState", "UNKNOWN"),
        "exchange": info.get("exchange", "UNKNOWN")
    }

# ===========================================================
# Part 2 — テクニカル計算（RSI / BB / MA）＋判定ロジック
# ===========================================================


# -----------------------------------------------------------
# ボリンジャーバンド シグナル判定
# -----------------------------------------------------------
def judge_bb_signal(price, bb_upper1, bb_upper2, bb_lower1, bb_lower2):
    if price >= bb_upper2:
        return "非常に割高（+2σ以上）", "🔥", 3
    elif price >= bb_upper1:
        return "やや割高（+1σ以上）", "📈", 2
    elif price <= bb_lower2:
        return "過度な売られすぎ（-2σ以下）", "🧊", 3
    elif price <= bb_lower1:
        return "やや売られ気味（-1σ以下）", "📉", 2
    else:
        return "平均圏（±1σ内）", "⚪️", 1


# -----------------------------------------------------------
# 順張り側の割高度スコア
# -----------------------------------------------------------
def is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w):
    if None in [price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w]:
        return 0
    score = 0
    if price <= ma25 * 1.10 and price <= ma50 * 1.10: score += 20
    if price <= bb_upper1: score += 20
    if rsi < 70: score += 15
    if per < 20: score += 15
    if pbr < 2.0: score += 15
    if price < high_52w * 0.95: score += 15
    return score


# -----------------------------------------------------------
# 逆張り側の割安スコア
# -----------------------------------------------------------
def is_low_price_zone(price, ma25, ma50, bb_lower1, bb_lower2, rsi, per, pbr, low_52w):
    if None in [price, ma25, ma50, bb_lower1, bb_lower2, rsi, per, pbr, low_52w]:
        return 0
    score = 0
    if price < ma25 * 0.90 and price < ma50 * 0.90: score += 20
    if price < bb_lower1: score += 15
    if price < bb_lower2: score += 20
    if rsi < 30: score += 15
    if per < 10: score += 15
    if pbr < 1.0: score += 15
    if price <= low_52w * 1.05: score += 15
    return score


# -----------------------------------------------------------
# 順張りの押し目判定
# -----------------------------------------------------------
def judge_signal(price, ma25, ma50, ma75, bb_lower1, bb_upper1, bb_lower2, rsi, per, pbr, dividend_yield, high_52w, low_52w):
    highprice_score = is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w)

    if rsi is None:
        return "RSI不明", "⚪️", 0

    if price <= ma75 and rsi < 40 and price <= bb_lower1:
        return "バーゲン（強い押し目）", "🔴", 3
    elif (price <= ma75 and price < bb_lower1) or (rsi < 30 and price < bb_lower1):
        return "そこそこ押し目", "🟠", 2
    elif price < ma25 * 0.97 and rsi < 37.5 and price <= bb_lower1:
        return "軽い押し目", "🟡", 1
    elif highprice_score <= 40:
        return "高値圏（要注意！）", "🔥", 0
    else:
        return "押し目シグナルなし", "🟢", 0


# -----------------------------------------------------------
# 3本のMAが±3%以内 → 横ばい判定
# -----------------------------------------------------------
def is_flat_ma(ma25, ma50, ma75, tolerance=0.03):
    ma_values = [ma25, ma50, ma75]
    ma_max = max(ma_values)
    ma_min = min(ma_values)
    return (ma_max - ma_min) / ma_max <= tolerance


# -----------------------------------------------------------
# ★ A方式：順張り裁量買いレンジ（関数外の変数に依存せず引数で受け取る）
# -----------------------------------------------------------
def calc_discretionary_buy_range(df, ma25, ma50, ma75, bb_lower, highprice_score, is_flat_or_gentle_up):
    # 中期トレンド
    is_mid_uptrend = ma75 < ma50 < ma25

    # 割高否定（押し目スコア）
    is_pullback = highprice_score <= 60

    # 条件満たさないなら終了
    if not (is_mid_uptrend and is_flat_or_gentle_up and is_pullback):
        return None

    # 中心価格
    center_price = (ma25 + ma50) / 2
    upper_price = center_price * 1.03
    lower_price = max(center_price * 0.95, bb_lower)

    return {
        "center_price": round(center_price, 2),
        "upper_price": round(upper_price, 2),
        "lower_price": round(lower_price, 2)
    }


# -----------------------------------------------------------
# ★ A方式：逆張り裁量買いレンジ
# -----------------------------------------------------------
def calc_discretionary_buy_range_contrarian(df, price, ma25, ma50, ma75,
                                            bb_lower1, bb_lower2, rsi, per, pbr,
                                            dividend_yield, low_52w, slope_ok):
    # 下降 or 横ばい
    is_downtrend = ma75 > ma50 > ma25
    is_flattrend = is_flat_ma(ma25, ma50, ma75, tolerance=0.03)
    if not (is_downtrend or is_flattrend):
        return None

    # 短期傾向
    if not slope_ok:
        return None

    # 割安スコア
    low_score = is_low_price_zone(price, ma25, ma50, bb_lower1, bb_lower2, rsi, per, pbr, low_52w)
    if low_score < 60:
        return None

    # レンジ計算
    center_price = (ma25 + bb_lower1) / 2
    upper_price = center_price * 1.08
    lower_price = center_price * 0.97

    fundamentals = ""
    if pbr < 1.0: fundamentals += "PBR割安 "
    if dividend_yield and dividend_yield > 3.0: fundamentals += "高配当 "

    return {
        "center_price": round(center_price, 2),
        "upper_price": round(upper_price, 2),
        "lower_price": round(lower_price, 2),
        "fundamentals": fundamentals.strip() if fundamentals else None
    }

# ===========================================================
# Part 3 — API は download() + dividends の2回だけ
# ===========================================================

from datetime import timedelta

# 🟦 ユーザー入力
user_input = st.text_input(
    "ティッカーシンボルを入力してください（例: AAPL, 7203, MSFT, 8306.T など）",
    value=""
)

ticker = convert_ticker(user_input)
if not ticker:
    st.warning("ティッカーを入力してください。")
    st.stop()

# -----------------------------------------------------------
# API 1回目：download による株価取得
# -----------------------------------------------------------
df = yf.download(ticker, period="120d", interval="1d")

if df.empty:
    st.warning("株価データが取得できませんでした。")
    st.stop()

if isinstance(df.columns, pd.MultiIndex):
    df.columns = ["_".join(col).strip() for col in df.columns]

close_col = next(c for c in df.columns if "Close" in c)
close = df[close_col].iloc[-1]
previous_close = df[close_col].iloc[-2]

# =======================================================
# 配当利回り 安全計算（どんな銘柄でも落ちない）
# =======================================================

dividend_yield = None  # デフォルト

ticker_obj = yf.Ticker(ticker)
divs = ticker_obj.dividends

# 配当データが Series であり、要素がある場合
if isinstance(divs, pd.Series) and len(divs) > 0:

    # index を DatetimeIndex に変換（失敗してもエラーにならない）
    try:
        divs.index = pd.to_datetime(divs.index, errors="coerce")
        divs = divs.dropna()  # 変換できなかった index を除去
    except Exception:
        divs = pd.Series(dtype=float)  # 空にして安全化

    # 過去1年だけ抽出
    if len(divs) > 0:
        one_year_ago = datetime.now() - timedelta(days=365)
        mask = divs.index > one_year_ago

        # インデックス比較の安全条件
        if mask.any():
            annual_div = divs[mask].sum()
            if annual_div > 0 and close > 0:
                dividend_yield = (annual_div / close) * 100

# -----------------------------------------------------------
# テクニカル計算（すべてローカル）
# -----------------------------------------------------------
df["25MA"] = df[close_col].rolling(25).mean()
df["50MA"] = df[close_col].rolling(50).mean()
df["75MA"] = df[close_col].rolling(75).mean()

df["20MA"] = df[close_col].rolling(20).mean()
df["20STD"] = df[close_col].rolling(20).std()

df["BB_+1σ"] = df["20MA"] + df["20STD"]
df["BB_+2σ"] = df["20MA"] + 2 * df["20STD"]
df["BB_-1σ"] = df["20MA"] - df["20STD"]
df["BB_-2σ"] = df["20MA"] - 2 * df["20STD"]

# RSI
delta = df[close_col].diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)
avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean().replace(0, 1e-10)
rs = avg_gain / avg_loss
df["RSI"] = 100 - (100 / (1 + rs))

# 有効データ
df_valid = df.dropna()
last = df_valid.iloc[-1]

ma25 = last["25MA"]
ma50 = last["50MA"]
ma75 = last["75MA"]
rsi = last["RSI"]
bb_upper1 = last["BB_+1σ"]
bb_upper2 = last["BB_+2σ"]
bb_lower1 = last["BB_-1σ"]
bb_lower2 = last["BB_-2σ"]

# 52週高値/安値（downloadのデータから算出）
high_52w = df[close_col].max()
low_52w = df[close_col].min()

# スロープ
ma25_slope = (df["25MA"].iloc[-1] - df["25MA"].iloc[-5]) / df["25MA"].iloc[-5] * 100
is_flat_or_gentle_up = abs(ma25_slope) <= 0.3 and ma25_slope >= 0
slope_ok = ma25_slope < 0

# 順張りスコア
highprice_score = is_high_price_zone(
    close, ma25, ma50, bb_upper1, rsi, None, None, high_52w
)

# シグナル
signal_text, signal_icon, signal_strength = judge_signal(
    close, ma25, ma50, ma75, bb_lower1, bb_upper1, bb_lower2,
    rsi, None, None, dividend_yield, high_52w, low_52w
)

# 裁量レンジ（順張り）
buy_range_trend = calc_discretionary_buy_range(
    df_valid, ma25, ma50, ma75, bb_lower1,
    highprice_score,
    is_flat_or_gentle_up
)

# 裁量レンジ（逆張り）
buy_range_contrarian = calc_discretionary_buy_range_contrarian(
    df_valid, close, ma25, ma50, ma75,
    bb_lower1, bb_lower2, rsi, None, None,
    dividend_yield, low_52w, slope_ok
)

# ===========================================================
# Part 4 — Streamlit 表示ロジック
# ===========================================================

# -----------------------------------------------------------
# 数値安全整形
# -----------------------------------------------------------
def safe_format(value, digits=2):
    return f"{value:.{digits}f}" if isinstance(value, (int, float)) else "—"


# -----------------------------------------------------------
# 名称マップ
# -----------------------------------------------------------
name_map = {
    "TOYOTA MOTOR CORP": "トヨタ自動車",
    "MITSUBISHI UFJ FINANCIAL GROUP": "三菱UFJフィナンシャル・グループ",
    "SONY GROUP CORP": "ソニーグループ",
}
name = name_map.get(name_raw.upper(), name_raw)


# -----------------------------------------------------------
# 上部 基礎情報 表示
# -----------------------------------------------------------
st.markdown(f"---\n### 💡 {ticker} - {name}")
st.markdown(f"**🏭 業種**: {industry}")

div_text = f"{dividend_yield:.2f}%" if dividend_yield else "—"
per_text = f"{per:.2f}" if per else "—"
pbr_text = f"{pbr:.2f}" if pbr else "—"

st.markdown(f"**💰 配当利回り**: {div_text}｜**📐 PER**: {per_text}｜**🧮 PBR**: {pbr_text}")


# -----------------------------------------------------------
# 現在値の色付け表示
# -----------------------------------------------------------
price_label = "現在価格" if market_price else "終値"
ref_price = close_price

if close > ref_price:
    color = "red"
elif close < ref_price:
    color = "green"
else:
    color = "black"

st.markdown(
    f"""
📊 {price_label}: <span style='color:{color}; font-weight:bold;'>{close:.2f}</span>
（前日終値: {ref_price:.2f}）
｜25MA: {ma25:.2f}｜50MA: {ma50:.2f}｜75MA: {ma75:.2f}
    """,
    unsafe_allow_html=True
)


# -----------------------------------------------------------
# RSI・BB 判定
# -----------------------------------------------------------
bb_signal_text, bb_icon, bb_strength = judge_bb_signal(close, bb_upper1, bb_upper2, bb_lower1, bb_lower2)

st.markdown(f"**📊 RSI**: {rsi:.1f}｜**📏 BB判定(20日)**: {bb_signal_text}")


# -----------------------------------------------------------
# メインシグナル表示
# -----------------------------------------------------------
st.markdown(f"### {signal_icon} {signal_text}")
st.progress(signal_strength / 3)


# -----------------------------------------------------------
# テーブル表示に使う値を整形
# -----------------------------------------------------------
trend_center_text = safe_format(
    buy_range_trend["center_price"] if buy_range_trend else None
)
trend_upper_text = safe_format(
    buy_range_trend["upper_price"] if buy_range_trend else None
)
trend_lower_text = safe_format(
    buy_range_trend["lower_price"] if buy_range_trend else None
)

contrarian_center_text = safe_format(
    buy_range_contrarian["center_price"] if buy_range_contrarian else None
)
contrarian_upper_text = safe_format(
    buy_range_contrarian["upper_price"] if buy_range_contrarian else None
)
contrarian_lower_text = safe_format(
    buy_range_contrarian["lower_price"] if buy_range_contrarian else None
)

lowprice_score = is_low_price_zone(close, ma25, ma50, bb_lower1, bb_lower2, rsi, per, pbr, low_52w)


# -----------------------------------------------------------
# 順張り条件達成度のコメント
# -----------------------------------------------------------
trend_conditions = [
    ma75 < ma50 < ma25 or is_flat_ma(ma25, ma50, ma75),
    is_flat_or_gentle_up,
    highprice_score >= 60
]
trend_ok_count = sum(trend_conditions)

if trend_ok_count == 3:
    trend_comment = "買い候補として非常に魅力的です。"
elif trend_ok_count == 2:
    trend_comment = "買い検討の余地があります。"
elif trend_ok_count == 1:
    trend_comment = "慎重に検討すべき状況です。"
else:
    trend_comment = "現時点では見送りが妥当です。"


# -----------------------------------------------------------
# 逆張り条件達成度のコメント
# -----------------------------------------------------------
contrarian_conditions = [
    ma75 > ma50 > ma25 or is_flat_ma(ma25, ma50, ma75),
    slope_ok,
    lowprice_score >= 60
]
contrarian_ok_count = sum(contrarian_conditions)

if contrarian_ok_count == 3:
    contrarian_comment = "買い候補として非常に魅力的です。"
elif contrarian_ok_count == 2:
    contrarian_comment = "買い検討の余地があります。"
elif contrarian_ok_count == 1:
    contrarian_comment = "慎重に検討すべき状況です。"
else:
    contrarian_comment = "現時点では見送りが妥当です。"


# -----------------------------------------------------------
# ★ 順張り or 逆張りのテーブル表示
# -----------------------------------------------------------
is_mid_uptrend = ma75 < ma50 < ma25

if is_mid_uptrend:
    # ★ 順張りテーブル
    st.markdown(f"""
    <div style="margin-top:4em; font-size:24px; font-weight:bold;">
    📈 <順張り>裁量買いの検討（25MA＞50MA＞75MA）
    </div>
    <table>
        <tr><th align="left">項目</th><th align="left">内容</th><th align="left">判定</th></tr>
        <tr><td>中期トレンド</td><td>25MA ＞ 50MA ＞ 75MA（上昇または横ばい）</td>
            <td>{"○" if trend_conditions[0] else "×"}</td></tr>
        <tr><td>短期傾向</td><td>25MAの傾きが ±0.3%以内（横ばい〜緩やかな上昇）</td>
            <td>{"○" if is_flat_or_gentle_up else "×"}</td></tr>
        <tr><td>順張り押し目判定</td><td>割高否定スコア 60点以上</td>
            <td>{highprice_score}点</td></tr>
        <tr><td>中心価格</td><td>25MA と 50MA の平均</td>
            <td>{trend_center_text}</td></tr>
        <tr><td>上側許容幅</td><td>中心価格 × 1.03</td>
            <td>{trend_upper_text}</td></tr>
        <tr><td>下側許容幅</td><td>中心価格 × 0.95 または BB−1σ</td>
            <td>{trend_lower_text}</td></tr>
        <tr><td>判定</td><td>順張り評価</td>
            <td><strong>{trend_comment}</strong></td></tr>
    </table>
    """, unsafe_allow_html=True)

else:
    # ★ 逆張りテーブル
    st.markdown(f"""
    <div style="margin-top:4em; font-size:24px; font-weight:bold;">
    🧮 <逆張り>裁量買いの検討
    </div>
    <table>
        <tr><th align="left">項目</th><th align="left">内容</th><th align="left">判定</th></tr>
        <tr><td>中期トレンド</td><td>75MA ＞ 50MA ＞ 25MA（下降または横ばい）</td>
            <td>{"○" if contrarian_conditions[0] else "×"}</td></tr>
        <tr><td>短期傾向</td><td>25MAの傾きが負</td>
            <td>{"○" if slope_ok else "×"}</td></tr>
        <tr><td>割安圏判定</td><td>割安スコア 60点以上</td>
            <td>{lowprice_score}点</td></tr>
        <tr><td>中心価格</td><td>25MA と BB−1σ の平均</td>
            <td>{contrarian_center_text}</td></tr>
        <tr><td>上側許容幅</td><td>中心価格 × 1.08</td>
            <td>{contrarian_upper_text}</td></tr>
        <tr><td>下側許容幅</td><td>中心価格 × 0.97</td>
            <td>{contrarian_lower_text}</td></tr>
        <tr><td>判定</td><td>逆張り評価</td>
            <td><strong>{contrarian_comment}</strong></td></tr>
    </table>
    """, unsafe_allow_html=True)

  # ===========================================================
# Part 5 — エラー処理・終了処理（ここで完了）
# ===========================================================

try:
    # すべての処理は Part1〜4 で完了済み
    pass

except Exception as e:
    st.error(f"処理中に予期せぬエラーが発生しました: {e}")
