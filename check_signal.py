import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz
from datetime import time

# -----------------------------------------------------------
# Streamlit 基本設定
# -----------------------------------------------------------
st.set_page_config(page_title="買いシグナルチェッカー", page_icon="📊")
st.title("🔍買いシグナルチェッカー")

# -----------------------------------------------------------
# ティッカー補正
# -----------------------------------------------------------
def convert_ticker(ticker):
    ticker = ticker.strip().upper()
    if ticker.endswith('.T') or not ticker.isdigit():
        return ticker
    return ticker + ".T"

# -----------------------------------------------------------
# RSI・BB・MA 判定関数
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

def is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w):
    score = 0
    if price <= ma25 * 1.10 and price <= ma50 * 1.10: score += 20
    if price <= bb_upper1: score += 20
    if rsi < 70: score += 15
    if high_52w != 0 and price < high_52w * 0.95: score += 15
    return score

def is_low_price_zone(price, ma25, ma50, bb_lower1, bb_lower2, rsi, per, pbr, low_52w):
    score = 0
    if price < ma25 * 0.90 and price < ma50 * 0.90: score += 20
    if price < bb_lower1: score += 15
    if price < bb_lower2: score += 20
    if rsi < 30: score += 15
    if price <= low_52w * 1.05: score += 15
    return score

def is_flat_ma(ma25, ma50, ma75, tolerance=0.03):
    ma_values = [ma25, ma50, ma75]
    ma_max, ma_min = max(ma_values), min(ma_values)
    return (ma_max - ma_min) / ma_max <= tolerance

def calc_discretionary_buy_range(df, ma25, ma50, ma75, bb_lower, highprice_score, is_flat_or_gentle_up):
    is_mid_uptrend = ma75 < ma50 < ma25
    is_pullback = highprice_score <= 60
    if not (is_mid_uptrend and is_flat_or_gentle_up and is_pullback):
        return None
    
    center = (ma25 + ma50) / 2
    return {
        "center_price": round(center, 2),
        "upper_price": round(center * 1.03, 2),
        "lower_price": round(max(center * 0.95, bb_lower), 2)
    }

def calc_discretionary_buy_range_contrarian(df, price, ma25, ma50, ma75,
                                            bb_lower1, bb_lower2, rsi,
                                            per, pbr, dividend_yield,
                                            low_52w, slope_ok):

    is_downtrend = ma75 > ma50 > ma25
    is_flattrend = is_flat_ma(ma25, ma50, ma75)

    if not (is_downtrend or is_flattrend):
        return None
    if not slope_ok:
        return None

    low_score = is_low_price_zone(price, ma25, ma50, bb_lower1, bb_lower2,
                                  rsi, None, None, low_52w)
    if low_score < 60:
        return None

    center = (ma25 + bb_lower1) / 2
    return {
        "center_price": round(center, 2),
        "upper_price": round(center * 1.08, 2),
        "lower_price": round(center * 0.97, 2),
        "fundamentals": None
    }

# -----------------------------------------------------------
# 入力
# -----------------------------------------------------------
user_input = st.text_input("ティッカー（例: 7203, 8306.T, AAPL）", value="")
ticker = convert_ticker(user_input)
if not ticker:
    st.stop()

# -----------------------------------------------------------
# 株価データ（download のみ）
# -----------------------------------------------------------
df = yf.download(ticker, period="120d", interval="1d")

if df.empty:
    st.error("株価データを取得できませんでした。")
    st.stop()

if isinstance(df.columns, pd.MultiIndex):
    df.columns = ["_".join(col).strip() for col in df.columns]

close_col = next(c for c in df.columns if "Close" in c)
close = df[close_col].iloc[-1]
previous_close = df[close_col].iloc[-2]

# -----------------------------------------------------------
# 配当（dividends）
# -----------------------------------------------------------
ticker_obj = yf.Ticker(ticker)
divs = ticker_obj.dividends
dividend_yield = None

if isinstance(divs, pd.Series) and len(divs) > 0:
    divs.index = pd.to_datetime(divs.index, errors="coerce").dropna().tz_localize(None)
    one_year_ago = datetime.now().replace(tzinfo=None) - timedelta(days=365)
    last_year_divs = divs[divs.index >= one_year_ago]
    if len(last_year_divs) > 0:
        annual_div = last_year_divs.sum()
        dividend_yield = (annual_div / close) * 100

# -----------------------------------------------------------
# テクニカル計算
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

df_valid = df.dropna()
last = df_valid.iloc[-1]

ma25, ma50, ma75 = last["25MA"], last["50MA"], last["75MA"]
rsi = last["RSI"]

bb_upper1, bb_upper2 = last["BB_+1σ"], last["BB_+2σ"]
bb_lower1, bb_lower2 = last["BB_-1σ"], last["BB_-2σ"]

high_52w = df[close_col].max()
low_52w = df[close_col].min()

ma25_slope = (df["25MA"].iloc[-1] - df["25MA"].iloc[-5]) / df["25MA"].iloc[-5] * 100
is_flat_or_gentle_up = abs(ma25_slope) <= 0.3 and ma25_slope >= 0
slope_ok = ma25_slope < 0

highprice_score = is_high_price_zone(close, ma25, ma50, bb_upper1, rsi, None, None, high_52w)

# -----------------------------------------------------------
# BB 判定
# -----------------------------------------------------------
bb_signal_text, bb_icon, bb_strength = judge_bb_signal(close, bb_upper1, bb_upper2, bb_lower1, bb_lower2)

# -----------------------------------------------------------
# メインシグナル
# -----------------------------------------------------------
def judge_signal(price, ma25, ma50, ma75, bb_lower1, bb_upper1, bb_lower2, rsi):
    if price <= ma75 and rsi < 40 and price <= bb_lower1:
        return "バーゲン（強い押し目）", "🔴", 3
    elif (price <= ma75 and price < bb_lower1) or (rsi < 30 and price < bb_lower1):
        return "そこそこ押し目", "🟠", 2
    elif price < ma25 * 0.97 and rsi < 37.5 and price <= bb_lower1:
        return "軽い押し目", "🟡", 1
    elif highprice_score <= 40:
        return "高値圏（要注意）", "🔥", 0
    else:
        return "押し目シグナルなし", "🟢", 0

signal_text, signal_icon, signal_strength = judge_signal(
    close, ma25, ma50, ma75, bb_lower1, bb_upper1, bb_lower2, rsi
)

# -----------------------------------------------------------
# 順張りレンジ・逆張りレンジ
# -----------------------------------------------------------
buy_range_trend = calc_discretionary_buy_range(
    df_valid, ma25, ma50, ma75, bb_lower1, highprice_score, is_flat_or_gentle_up
)

buy_range_contrarian = calc_discretionary_buy_range_contrarian(
    df_valid, close, ma25, ma50, ma75, bb_lower1, bb_lower2,
    rsi, None, None, dividend_yield, low_52w, slope_ok
)

# -----------------------------------------------------------
# 表示（Part4 再現）
# -----------------------------------------------------------
st.markdown(f"---\n### 💡 {ticker} - {ticker}")
st.markdown(f"**🏭 業種**: —")

div_text = f"{dividend_yield:.2f}%" if dividend_yield else "—"
st.markdown(f"**💰 配当利回り**: {div_text}｜**📐 PER**: —｜**🧮 PBR**: —")

# 価格色
color = "red" if close > previous_close else "green" if close < previous_close else "black"

st.markdown(
    f"""
📊 現在価格: <span style='color:{color}; font-weight:bold;'>{close:.2f}</span>  
（前日終値: {previous_close:.2f}）
｜25MA: {ma25:.2f}｜50MA: {ma50:.2f}｜75MA: {ma75:.2f}
""",
    unsafe_allow_html=True
)

st.markdown(f"**📊 RSI**: {rsi:.1f}｜**📏 BB判定(20日)**: {bb_signal_text}")
st.markdown(f"### {signal_icon} {signal_text}")
st.progress(signal_strength / 3)

# -----------------------------------------------------------
# テーブル再現（順張り / 逆張り）
# -----------------------------------------------------------
def safe(v):
    return f"{v:.2f}" if isinstance(v, (int, float)) else "—"

trend_center = safe(buy_range_trend["center_price"] if buy_range_trend else None)
trend_upper = safe(buy_range_trend["upper_price"] if buy_range_trend else None)
trend_lower = safe(buy_range_trend["lower_price"] if buy_range_trend else None)

contr_center = safe(buy_range_contrarian["center_price"] if buy_range_contrarian else None)
contr_upper = safe(buy_range_contrarian["upper_price"] if buy_range_contrarian else None)
contr_lower = safe(buy_range_contrarian["lower_price"] if buy_range_contrarian else None)

# 順張り条件
trend_conditions = [
    ma75 < ma50 < ma25,
    is_flat_or_gentle_up,
    highprice_score >= 60
]
trend_ok = sum(trend_conditions)
trend_comment = ["見送り", "慎重に", "検討の余地", "非常に魅力"][trend_ok]

# 逆張り条件
low_score = is_low_price_zone(close, ma25, ma50, bb_lower1, bb_lower2, rsi, None, None, low_52w)
contr_conditions = [
    ma75 > ma50 > ma25 or is_flat_ma(ma25, ma50, ma75),
    slope_ok,
    low_score >= 60
]
contr_ok = sum(contr_conditions)
contr_comment = ["見送り", "慎重に", "検討の余地", "非常に魅力"][contr_ok]

# -----------------------------------------------------------
# 表示：順張り or 逆張りテーブル
# -----------------------------------------------------------
if ma75 < ma50 < ma25:
    st.markdown("## 📈 <順張り>裁量買いレンジ")
    st.markdown(f"""
| 項目 | 内容 | 判定 |
|---|---|---|
| 中期トレンド | 25 > 50 > 75 | {"○" if trend_conditions[0] else "×"} |
| 短期傾向 | MA25 が横ばい〜緩やか上昇 | {"○" if trend_conditions[1] else "×"} |
| 割高否定 | スコア>=60 | {highprice_score} |
| 中心価格 | 25MAと50MAの平均 | {trend_center} |
| 上側許容 | ×1.03 | {trend_upper} |
| 下側許容 | ×0.95 or BB-1σ | {trend_lower} |
| 判定 | — | **{trend_comment}** |
""")
else:
    st.markdown("## 🧮 <逆張り>裁量買いレンジ")
    st.markdown(f"""
| 項目 | 内容 | 判定 |
|---|---|---|
| 中期トレンド | 下降 or 横ばい | {"○" if contr_conditions[0] else "×"} |
| 短期傾向 | MA25 が下降 | {"○" if contr_conditions[1] else "×"} |
| 割安判定 | スコア>=60 | {low_score} |
| 中心価格 | 25MAとBB-1σの平均 | {contr_center} |
| 上側許容 | ×1.08 | {contr_upper} |
| 下側許容 | ×0.97 | {contr_lower} |
| 判定 | — | **{contr_comment}** |
""")
