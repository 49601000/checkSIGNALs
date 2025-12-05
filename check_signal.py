import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
from datetime import datetime, time as t
import pytz


# ============================================================
# Streamlit 基本設定
# ============================================================
st.set_page_config(page_title="買いシグナルチェッカー", page_icon="📊")
st.title("🔍 買いシグナルチェッカー（押し目 × 順張り × 逆張り 自動判定 完全版）")


# ============================================================
# yfinance RateLimit無敵化（fast_info ベース）
# ============================================================
def safe_ticker(ticker, retries=5, wait=1):
    """fast_infoでTicker取得（軽量でRateLimitされにくい）"""
    for _ in range(retries):
        try:
            tk = yf.Ticker(ticker)
            _ = tk.fast_info
            return tk
        except:
            time.sleep(wait)
            wait *= 2
    raise Exception("Ticker取得失敗（RateLimit）")


def safe_fast_info(tk, retries=5, wait=1):
    """fast_info の安全取得"""
    for _ in range(retries):
        try:
            return tk.fast_info
        except:
            time.sleep(wait)
            wait *= 2
    raise Exception("fast_info取得失敗")


@st.cache_data(ttl=900)
def get_price_cached(ticker):
    return yf.download(ticker, period="120d", interval="1d")


# ============================================================
# ティッカー変換
# ============================================================
def convert_ticker(t):
    t = t.strip().upper()
    if t.endswith(".T") or not t.isdigit():
        return t
    return t + ".T"


# ============================================================
# 市場状態
# ============================================================
def get_exchange(info, ticker):
    if ticker.endswith(".T") or ticker.isdigit():
        return "東証"

    exch = str(info.get("exchange", "")).upper()
    if "NASDAQ" in exch or "NMS" in exch:
        return "NASDAQ"
    if "NYSE" in exch or "NYQ" in exch:
        return "NYSE"
    return "不明"


def market_state(exchange):
    now = datetime.now(pytz.timezone("Asia/Tokyo")).time()

    if exchange == "東証":
        op, close = t(9, 0), t(15, 30)
    else:
        op, close = t(22, 30), t(5, 0)

    if op < close:
        is_open = op <= now <= close
    else:
        is_open = now >= op or now <= close

    return "取引中" if is_open else "取引終了"


# ============================================================
# テクニカル指標
# ============================================================
def calc_rsi(df, col="Close", period=14):
    d = df[col].diff()
    up = d.clip(lower=0)
    down = -d.clip(upper=0)

    ag = up.rolling(period).mean()
    al = down.rolling(period).mean().replace(0, 1e-10)

    rs = ag / al
    return 100 - (100 / (1 + rs))


# ============================================================
# あなたの押し目ロジック（judge_signal）
# ============================================================
def judge_signal(price, ma25, ma50, ma75, bb_lower1, bb_upper1, bb_lower2,
                 rsi, per, pbr, dividend_yield, high_52w, low_52w):

    if rsi is None:
        return "RSI不明", "⚪️", 0

    # 🔴 強い押し目
    if price <= ma75 and rsi < 40 and price <= bb_lower1:
        return "バーゲン（強い押し目）", "🔴", 3

    # 🟠 そこそこ押し目
    elif (price <= ma75 and price < bb_lower1) or (rsi < 30 and price < bb_lower1):
        return "そこそこ押し目", "🟠", 2

    # 🟡 軽い押し目
    elif price < ma25 * 0.97 and rsi < 37.5 and price <= bb_lower1:
        return "軽い押し目", "🟡", 1

    # 🔥 割高圏（順張りスコア40以下）
    elif is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w) <= 40:
        return "高値圏（要注意）", "🔥", 0

    # 🟢 シグナルなし
    else:
        return "押し目シグナルなし", "🟢", 0


# ============================================================
# 順張り・逆張りスコア
# ============================================================
def is_flat(ma25, ma50, ma75, tol=0.03):
    arr = [ma25, ma50, ma75]
    return (max(arr) - min(arr)) / max(arr) <= tol


def is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w):
    score = 0
    if price <= ma25 * 1.10 and price <= ma50 * 1.10: score += 20
    if price <= bb_upper1: score += 20
    if rsi < 70: score += 15
    if per and per < 20: score += 15
    if pbr and pbr < 2.0: score += 15
    if high_52w and price < high_52w * 0.95: score += 15
    return score


def is_low_price_zone(price, ma25, ma50, bb_l1, bb_l2, rsi, per, pbr, low_52w):
    score = 0
    if price < ma25 * 0.90 and price < ma50 * 0.90: score += 20
    if price < bb_l1: score += 15
    if price < bb_l2: score += 20
    if rsi < 30: score += 15
    if per and per < 10: score += 15
    if pbr and pbr < 1.0: score += 15
    if low_52w and price <= low_52w * 1.05: score += 15
    return score


def trend_buy_range(ma25, ma50, ma75, bb_l1, highscore):
    if not (ma75 < ma50 < ma25 or is_flat(ma25, ma50, ma75)):
        return None
    slope = (ma25 - ma50) / ma50 * 100
    if not (0 <= slope <= 0.3):
        return None
    if highscore < 60:
        return None

    center = (ma25 + ma50) / 2
    upper = center * 1.03
    lower = max(center * 0.95, bb_l1)
    return {"center": center, "upper": upper, "lower": lower}


def contrarian_buy_range(ma25, ma50, ma75, bb_l1, low_score, rsi_slope, pbr, div):
    if not (ma75 > ma50 > ma25 or is_flat(ma25, ma50, ma75)):
        return None
    if rsi_slope >= 0:
        return None
    if low_score < 60:
        return None

    center = (ma25 + bb_l1) / 2
    upper = center * 1.08
    lower = center * 0.97

    tag = []
    if pbr and pbr < 1.0: tag.append("PBR割安")
    if div and div > 3.0: tag.append("高配当")

    return {"center": center, "upper": upper, "lower": lower, "tag": " ".join(tag)}


# ============================================================
# メイン処理
# ============================================================
ticker_input = st.text_input("ティッカー（例: AAPL / 7203 / 8306.T）", "")
ticker = convert_ticker(ticker_input)

if not ticker:
    st.stop()

# ---- info ----
try:
    tk = safe_ticker(ticker)
    info = safe_fast_info(tk)
except Exception as e:
    st.error(f"info取得エラー: {e}")
    st.stop()

exchange = get_exchange(info, ticker)
st.write(f"🕒 市場状態：**{exchange}（{market_state(exchange)}）**")

# ---- price ----
df = get_price_cached(ticker)
if df.empty:
    st.error("株価データが取得できません")
    st.stop()

close_col = [c for c in df.columns if "Close" in c][0]

df["25MA"] = df[close_col].rolling(25).mean()
df["50MA"] = df[close_col].rolling(50).mean()
df["75MA"] = df[close_col].rolling(75).mean()
df["20MA"] = df[close_col].rolling(20).mean()
df["20STD"] = df[close_col].rolling(20).std()

df["BB_u1"] = df["20MA"] + df["20STD"]
df["BB_l1"] = df["20MA"] - df["20STD"]
df["BB_l2"] = df["20MA"] - 2 * df["20STD"]

df["RSI"] = calc_rsi(df, close_col)

last = df.dropna().iloc[-1]

price = float(last[close_col])
ma25 = float(last["25MA"])
ma50 = float(last["50MA"])
ma75 = float(last["75MA"])
rsi = float(last["RSI"])
bb_u1 = float(last["BB_u1"])
bb_l1 = float(last["BB_l1"])
bb_l2 = float(last["BB_l2"])

high52 = info.get("yearHigh", None)
low52 = info.get("yearLow", None)
per = info.get("peRatio", None)
pbr = info.get("priceToBook", None)
div = info.get("dividendYield", None)

# スコア
high_score = is_high_price_zone(price, ma25, ma50, bb_u1, rsi, per, pbr, high52)
low_score = is_low_price_zone(price, ma25, ma50, bb_l1, bb_l2, rsi, per, pbr, low52)
rsi_slope = df["RSI"].iloc[-1] - df["RSI"].iloc[-5]

# -------------------------------------------------------------
# 🔍 順張り or 逆張りの自動判定（あなたの指定ロジック）
# -------------------------------------------------------------
is_mid_uptrend = ma25 > ma50 and ma25 > ma75


# ============================================================
# ① 押し目シグナル
# ============================================================
oshime_label, oshime_icon, oshime_level = judge_signal(
    price, ma25, ma50, ma75,
    bb_l1, bb_u1, bb_l2,
    rsi, per, pbr, div,
    high52, low52
)

st.markdown("---")
st.subheader("🎯 押し目シグナル（短期判定）")
st.write(f"### {oshime_icon} **{oshime_label}**")


# ============================================================
# ② 順張り / 逆張りの自動分岐スコア表示
# ============================================================
st.markdown("---")
st.subheader("📊 裁量スコア（自動判定）")

# ======== 順張り表示 ========
if is_mid_uptrend:
    st.write("### 📈 トレンド上昇中 → 順張りスコア優先")
    st.write(f"**順張りスコア：{high_score} / 100**")

    trend_range = trend_buy_range(ma25, ma50, ma75, bb_l1, high_score)
    if trend_range:
        st.success("✔ **順張りの裁量買い候補**")
        st.write(f"- 中心価格：{trend_range['center']:.2f}")
        st.write(f"- 買いレンジ：{trend_range['lower']:.2f} ～ {trend_range['upper']:.2f}")
    else:
        st.warning("✖ 順張り裁量条件なし")

    # 参考として逆張りスコア
    st.markdown("---")
    st.write("🧮（参考）逆張りスコア")
    st.write(f"{low_score} / 100")


# ======== 逆張り表示 ========
else:
    st.write("### 🧮 トレンド弱い/不明 → 逆張りスコア優先")
    st.write(f"**逆張りスコア：{low_score} / 100**")

    contrarian_range = contrarian_buy_range(
        ma25, ma50, ma75, bb_l1,
        low_score, rsi_slope, pbr, div
    )

    if contrarian_range:
        st.success("✔ **逆張りの裁量買い候補**")
        st.write(f"- 中心値：{contrarian_range['center']:.2f}")
        st.write(f"- 買いレンジ：{contrarian_range['lower']:.2f} ～ {contrarian_range['upper']:.2f}")
        if contrarian_range["tag"]:
            st.write(f"- タグ：**{contrarian_range['tag']}**")
    else:
        st.warning("✖ 逆張り裁量条件なし")

    # 参考として順張りスコア
    st.markdown("---")
    st.write("📈（参考）順張りスコア")
    st.write(f"{high_score} / 100")
