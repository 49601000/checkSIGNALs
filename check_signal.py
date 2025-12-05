# ===========================================================
# Part 1 : データ取得 & テクニカル指標計算
# ===========================================================

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# -----------------------------------------------------------
# Streamlit UI 基本設定
# -----------------------------------------------------------
st.set_page_config(page_title="買いシグナルチェッカー", page_icon="📊")
st.title("🔍買いシグナルチェッカー（完全版）")

# -----------------------------------------------------------
# ティッカー補正（日本株は自動 .T 付与）
# -----------------------------------------------------------
def convert_ticker(ticker):
    ticker = ticker.strip().upper()
    # 日本株：4桁で .T が付いていない場合に自動付与
    if ticker.isdigit() and len(ticker) <= 5 and not ticker.endswith(".T"):
        return ticker + ".T"
    return ticker

# -----------------------------------------------------------
# MA の矢印判定：上昇 ↗ / 下降 ↘ / 横ばい →
# -----------------------------------------------------------
def slope_arrow(series, window=3):
    # series: pandas Series
    if len(series) < window + 1:
        return "→"
    recent = series.iloc[-window:]
    diff = recent.iloc[-1] - recent.iloc[0]

    if diff > 0:
        return "↗"
    elif diff < 0:
        return "↘"
    else:
        return "→"

# -----------------------------------------------------------
# 入力
# -----------------------------------------------------------
user_input = st.text_input("ティッカーを入力（例：7203, 8306.T, AAPL）", value="")
ticker = convert_ticker(user_input)

if not ticker:
    st.stop()

# -----------------------------------------------------------
# 株価データ取得
# -----------------------------------------------------------
try:
    df = yf.download(ticker, period="180d", interval="1d")
except Exception:
    st.error("データ取得エラー。ティッカーを確認してください。")
    st.stop()

if df.empty:
    st.error("株価データが取得できません。")
    st.stop()

# yfinance のカラム処理（マルチカラム対応）
if isinstance(df.columns, pd.MultiIndex):
    df.columns = ["_".join(col).strip() for col in df.columns]

close_col = next(c for c in df.columns if "Close" in c)
close = df[close_col].iloc[-1]
previous_close = df[close_col].iloc[-2]

# -----------------------------------------------------------
# テクニカル指標の計算
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
df["RSI"] = 100 - (100 / (1 + (avg_gain / avg_loss)))

# 有効データ（dropna）
df_valid = df.dropna()
last = df_valid.iloc[-1]

# 最終計算値
ma25, ma50, ma75 = last["25MA"], last["50MA"], last["75MA"]
rsi = last["RSI"]
bb_upper1, bb_upper2 = last["BB_+1σ"], last["BB_+2σ"]
bb_lower1, bb_lower2 = last["BB_-1σ"], last["BB_-2σ"]

# 52週高値・安値（取得期間内で代用）
high_52w = df[close_col].max()
low_52w = df[close_col].min()

# -----------------------------------------------------------
# MA の傾き（判定基準）
# -----------------------------------------------------------
ma25_slope = (df["25MA"].iloc[-1] - df["25MA"].iloc[-4]) / df["25MA"].iloc[-4] * 100
slope_ok = ma25_slope < 0  # 逆張り向け条件

is_flat_or_gentle_up = abs(ma25_slope) <= 0.3 and ma25_slope >= 0  # 順張り向け条件

# -----------------------------------------------------------
# MA の矢印
# -----------------------------------------------------------
arrow25 = slope_arrow(df["25MA"])
arrow50 = slope_arrow(df["50MA"])
arrow75 = slope_arrow(df["75MA"])

# -----------------------------------------------------------
# 配当利回り算出（dividends）
# -----------------------------------------------------------
ticker_obj = yf.Ticker(ticker)
divs = ticker_obj.dividends

dividend_yield = None
if isinstance(divs, pd.Series) and len(divs) > 0:
    divs.index = pd.to_datetime(divs.index, errors="coerce").dropna()
    one_year_ago = datetime.now() - timedelta(days=365)
    last_year_divs = divs[divs.index >= one_year_ago]

    if len(last_year_divs) > 0:
        annual_div = last_year_divs.sum()
        dividend_yield = (annual_div / close) * 100

# -----------------------------------------------------------
# 現在価格の色付け
# -----------------------------------------------------------
if close > previous_close:
    price_color = "red"
elif close < previous_close:
    price_color = "green"
else:
    price_color = "black"


# ===========================================================
# Part 2 : 押し目判定・RSI・BB 判定
# ===========================================================

# -----------------------------------------------------------
# BB 判定テキスト
# -----------------------------------------------------------
def judge_bb_signal(price, bb1, bb2, bbm1, bbm2):
    if price >= bb2:
        return "非常に割高（+2σ以上）", "🔥", 3
    elif price >= bb1:
        return "やや割高（+1σ以上）", "📈", 2
    elif price <= bbm2:
        return "過度に売られすぎ（-2σ以下）", "🧊", 3
    elif price <= bbm1:
        return "売られ気味（-1σ以下）", "📉", 2
    else:
        return "平均圏（±1σ内）", "⚪️", 1

bb_text, bb_icon, bb_strength = judge_bb_signal(
    close, bb_upper1, bb_upper2, bb_lower1, bb_lower2
)

# -----------------------------------------------------------
# 押し目判定ロジック（あなた仕様100%そのまま）
# -----------------------------------------------------------

def is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w):
    score = 0
    if price <= ma25 * 1.10 and price <= ma50 * 1.10:
        score += 20
    if price <= bb_upper1:
        score += 20
    if rsi < 70:
        score += 15
    if high_52w != 0 and price < high_52w * 0.95:
        score += 15
    return score


def judge_signal(price, ma25, ma50, ma75, bb_lower1, bb_upper1, bb_lower2,
                 rsi, high_52w, low_52w):

    if rsi is None:
        return "RSI不明", "⚪️", 0

    # --- 強い押し目（バーゲン） ---
    if price <= ma75 and rsi < 40 and price <= bb_lower1:
        return "バーゲン（強い押し目）", "🔴", 3

    # --- そこそこ押し目 ---
    elif (price <= ma75 and price < bb_lower1) or (rsi < 30 and price < bb_lower1):
        return "そこそこ押し目", "🟠", 2

    # --- 軽い押し目 ---
    elif price < ma25 * 0.97 and rsi < 37.5 and price <= bb_lower1:
        return "軽い押し目", "🟡", 1

    # --- 🔥 高値圏（要注意！）←あなたが超重要と言った分岐 ---
    elif is_high_price_zone(price, ma25, ma50, bb_upper1, rsi,
                            None, None, high_52w) <= 40:
        return "高値圏（要注意！）", "🔥", 0

    # --- 押し目なし ---
    else:
        return "押し目シグナルなし", "🟢", 0


signal_text, signal_icon, signal_strength = judge_signal(
    close, ma25, ma50, ma75,
    bb_lower1, bb_upper1, bb_lower2,
    rsi, high_52w, low_52w
)

# -----------------------------------------------------------
# UI 表示（Part1の直後に配置）
# -----------------------------------------------------------

st.markdown("---")
st.markdown("## 📊 現在価格 ＋ MA（トレンド矢印付き）")

st.markdown(
    f"""
**現在価格**: <span style='color:{price_color}; font-weight:bold;'>{close:.2f}</span>  
（前日終値: {previous_close:.2f}）

- **25MA**: {ma25:.2f} {arrow25}  
- **50MA**: {ma50:.2f} {arrow50}  
- **75MA**: {ma75:.2f} {arrow75}  
    """,
    unsafe_allow_html=True
)

# RSI / BB 表示
st.markdown("## 📉 RSI / ボリンジャーバンド 判定")
st.markdown(f"**RSI**: {rsi:.1f}")
st.markdown(f"**BB判定**: {bb_icon} {bb_text}")

# 押し目判定表示
st.markdown("## 🎯 押し目判定（システム判定）")
st.markdown(f"### {signal_icon} {signal_text}")
st.progress(signal_strength / 3)

# -----------------------------------------------------------
# 追加：順張り用スコア（高値圏）計算
# -----------------------------------------------------------
highprice_score = is_high_price_zone(
    close, ma25, ma50, bb_upper1, rsi, None, None, high_52w
)

# -----------------------------------------------------------
# 追加：逆張り用の割安スコア関数
# -----------------------------------------------------------
def is_low_price_zone(price, ma25, ma50, bb_lower1, bb_lower2, rsi, per, pbr, low_52w):
    score = 0
    if price < ma25 * 0.90 and price < ma50 * 0.90:
        score += 20
    if price < bb_lower1:
        score += 15
    if price < bb_lower2:
        score += 20
    if rsi < 30:
        score += 15
    if price <= low_52w * 1.05:
        score += 15
    return score

# -----------------------------------------------------------
# 追加：MA が横ばいかを判定する関数
# -----------------------------------------------------------
def is_flat_ma(ma25, ma50, ma75, tolerance=0.03):
    ma_values = [ma25, ma50, ma75]
    ma_max = max(ma_values)
    ma_min = min(ma_values)
    return (ma_max - ma_min) / ma_max <= tolerance


# ===========================================================
# Part 3 : 裁量買いレンジ（順張り or 逆張り）
# ===========================================================

# -------------------------------
# 順張り条件の評価
# -------------------------------
trend_conditions = [
    ma75 < ma50 < ma25,         # 中期トレンド 良好
    is_flat_or_gentle_up,       # 短期の傾き（MA25）
    highprice_score >= 60       # 割高否定判定
]
trend_ok = sum(trend_conditions)

trend_comment = [
    "現時点では見送りが妥当です。",
    "慎重に検討すべき状況です。",
    "買い検討の余地があります。",
    "買い候補として非常に魅力的です。"
][trend_ok]


# -------------------------------
# 逆張り条件の評価
# -------------------------------
low_score = is_low_price_zone(
    close, ma25, ma50, bb_lower1, bb_lower2, rsi,
    None, None, low_52w
)

contrarian_conditions = [
    (ma75 > ma50 > ma25) or is_flat_ma(ma25, ma50, ma75),  # 中期トレンド
    slope_ok,                                              # 短期傾向
    low_score >= 60                                        # 割安判定
]
contr_ok = sum(contrarian_conditions)

contr_comment = [
    "現時点では見送りが妥当です。",
    "慎重に検討すべき状況です。",
    "買い検討の余地があります。",
    "買い候補として非常に魅力的です。"
][contr_ok]


# ===========================================================
# UI 出力：順張り or 逆張りレンジ
# ===========================================================
st.markdown("---")
st.markdown("## 🎯 裁量買いレンジ（トレンド別）")


# -------------------------------
# 順張り（25 > 50 > 75）
# -------------------------------
if ma75 < ma50 < ma25:

    center_price = (ma25 + ma50) / 2
    upper_price = center_price * 1.03
    lower_price = max(center_price * 0.95, bb_lower1)

    st.markdown("### 📈 ＜順張り＞裁量買いレンジ")

    st.markdown(f"""
| 項目 | 内容 | 判定 |
|---|---|---|
| 中期トレンド | 25MA ＞ 50MA ＞ 75MA | {"○" if trend_conditions[0] else "×"} |
| 短期傾向 | MA25 が横ばい〜緩やか上昇 | {"○" if trend_conditions[1] else "×"} |
| 割高否定 | スコア ≥ 60 | {highprice_score} |
| 中心価格 | 25MA と 50MA の平均 | {center_price:.2f} |
| 上側許容 | ×1.03 | {upper_price:.2f} |
| 下側許容 | ×0.95 または BB-1σ | {lower_price:.2f} |
| 判定 | — | **{trend_comment}** |
""")

# -------------------------------
# 逆張り（下降 or 横ばい）
# -------------------------------
else:

    center_price = (ma25 + bb_lower1) / 2
    upper_price = center_price * 1.08
    lower_price = center_price * 0.97

    st.markdown("### 🧮 ＜逆張り＞裁量買いレンジ")

    st.markdown(f"""
| 項目 | 内容 | 判定 |
|---|---|---|
| 中期トレンド | 下降 or 横ばい | {"○" if contrarian_conditions[0] else "×"} |
| 短期傾向 | MA25 が下降 | {"○" if contrarian_conditions[1] else "×"} |
| 割安判定 | スコア ≥ 60 | {low_score} |
| 中心価格 | 25MA と BB−1σ の平均 | {center_price:.2f} |
| 上側許容 | ×1.08 | {upper_price:.2f} |
| 下側許容 | ×0.97 | {lower_price:.2f} |
| 判定 | — | **{contr_comment}** |
""")

