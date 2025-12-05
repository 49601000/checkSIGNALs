import streamlit as st
import yfinance as yf
import pandas as pd
import time
from datetime import datetime, time as t
import pytz

# ============================================================
# Streamlit 基本設定
# ============================================================
st.set_page_config(page_title="買いシグナルチェッカー", page_icon="📊")
st.title("🔍 買いシグナルチェッカー（高速×安定版）")


# ============================================================
# yfinance 安全アクセス（Rate limit 対策）
# ============================================================
def safe_info(ticker, retries=3, wait=2):
    """yfinance の .info を安全取得"""
    for i in range(retries):
        try:
            return yf.Ticker(ticker).info
        except Exception as e:
            if "Too Many Requests" in str(e):
                time.sleep(wait)
                wait *= 2
            else:
                raise
    raise Exception("Rate Limit により info 取得失敗")


@st.cache_data(ttl=1800)
def get_info_cached(ticker):
    return safe_info(ticker)


@st.cache_data(ttl=1800)
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
# 市場状態判定（ローカル計算）
# ============================================================
def get_exchange(info, ticker):
    if ticker.endswith(".T") or ticker.isdigit():
        return "東証"

    ex = info.get("exchange", "").upper()
    if ex in ["NMS", "NASDAQ"]:
        return "NASDAQ"
    if ex in ["NYQ", "NYSE"]:
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
# 裁量買いロジック（あなたの元コードを忠実に反映）
# ============================================================
def is_flat(ma25, ma50, ma75, tol=0.03):
    arr = [ma25, ma50, ma75]
    return (max(arr) - min(arr)) / max(arr) <= tol


# ----- 順張り：割高否定スコア -----
def is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w):
    score = 0
    if price <= ma25 * 1.10 and price <= ma50 * 1.10:
        score += 20
    if price <= bb_upper1:
        score += 20
    if rsi < 70:
        score += 15
    if per and per < 20:
        score += 15
    if pbr and pbr < 2.0:
        score += 15
    if price < high_52w * 0.95:
        score += 15
    return score


# ----- 逆張り：割安スコア -----
def is_low_price_zone(price, ma25, ma50, bb_l1, bb_l2, rsi, per, pbr, low_52w):
    score = 0
    if price < ma25 * 0.90 and price < ma50 * 0.90:
        score += 20
    if price < bb_l1:
        score += 15
    if price < bb_l2:
        score += 20
    if rsi < 30:
        score += 15
    if per and per < 10:
        score += 15
    if pbr and pbr < 1.0:
        score += 15
    if price <= low_52w * 1.05:
        score += 15
    return score


# ------ 順張り裁量買い ------
def trend_buy_range(ma25, ma50, ma75, bb_l1, highscore):
    is_trend = ma75 < ma50 < ma25 or is_flat(ma25, ma50, ma75)
    if not is_trend:
        return None

    slope = (ma25 - ma50) / ma50 * 100
    is_slope_ok = abs(slope) <= 0.3 and slope >= 0

    if not is_slope_ok:
        return None

    if highscore < 60:
        return None

    center = (ma25 + ma50) / 2
    upper = center * 1.03
    lower = max(center * 0.95, bb_l1)

    return {"center": center, "upper": upper, "lower": lower}


# ------ 逆張り裁量買い ------
def contrarian_buy_range(ma25, ma50, ma75, bb_l1, low_score, rsi_slope, pbr, div):
    is_trend = ma75 > ma50 > ma25 or is_flat(ma25, ma50, ma75)
    if not is_trend:
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

# ----- info -----
try:
    info = get_info_cached(ticker)
except Exception as e:
    st.error(f"info取得エラー: {e}")
    st.stop()

exchange = get_exchange(info, ticker)
st.write(f"🕒 市場状態：**{exchange}（{market_state(exchange)}）**")


# ----- price -----
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
df["BB_u2"] = df["20MA"] + 2 * df["20STD"]
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
bb_u2 = float(last["BB_u2"])
bb_l1 = float(last["BB_l1"])
bb_l2 = float(last["BB_l2"])

high52 = info.get("fiftyTwoWeekHigh", None)
low52 = info.get("fiftyTwoWeekLow", None)
per = info.get("trailingPE", None)
pbr = info.get("priceToBook", None)
div = info.get("dividendYield", None)


# ============================================================
# スコア計算
# ============================================================
high_score = is_high_price_zone(price, ma25, ma50, bb_u1, rsi, per, pbr, high52)
low_score = is_low_price_zone(price, ma25, ma50, bb_l1, bb_l2, rsi, per, pbr, low52)

ma25_slope = (df["25MA"].iloc[-1] - df["25MA"].iloc[-5]) / df["25MA"].iloc[-5] * 100


# ============================================================
# 裁量買いレンジ
# ============================================================
trend_range = trend_buy_range(ma25, ma50, ma75, bb_l1, high_score)
contrarian_range = contrarian_buy_range(ma25, ma50, ma75, bb_l1, low_score, ma25_slope, pbr, div)


# ============================================================
# 表示
# ============================================================
st.subheader(f"📌 {ticker}")
st.write(f"現値：**{price:.2f}**")
st.write(f"RSI：**{rsi:.1f}**")
st.write(f"25MA：{ma25:.2f} / 50MA：{ma50:.2f} / 75MA：{ma75:.2f}")

st.markdown("---")

# ------ 順張り ------
st.subheader("📈 順張り・裁量買い判定")

if trend_range:
    st.write("### ✔ この銘柄は **順張りの裁量買い候補** です。")
    st.write(f"中心価格：**{trend_range['center']:.2f}**")
    st.write(f"買いレンジ：**{trend_range['lower']:.2f} ～ {trend_range['upper']:.2f}**")
else:
    st.write("### ✖ 順張り条件を満たしていません。")

st.markdown("---")

# ------ 逆張り ------
st.subheader("🧮 逆張り・裁量買い判定")

if contrarian_range:
    st.write("### ✔ この銘柄は **逆張りの裁量買い候補** です。")
    st.write(f"中心価格：**{contrarian_range['center']:.2f}**")
    st.write(f"買いレンジ：**{contrarian_range['lower']:.2f} ～ {contrarian_range['upper']:.2f}**")
    if contrarian_range["tag"]:
        st.write(f"補正タグ：**{contrarian_range['tag']}**")
else:
    st.write("### ✖ 逆張り条件を満たしていません。")
