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
st.title("🔍 買いシグナルチェッカー（完全統合版）")


# ============================================================
# RateLimitに強い fast_info ベース
# ============================================================
def safe_ticker(ticker, retries=5, wait=1):
    for _ in range(retries):
        try:
            tk = yf.Ticker(ticker)
            _ = tk.fast_info
            return tk
        except:
            time.sleep(wait)
            wait *= 2
    raise Exception("Ticker取得失敗")


def safe_fast_info(tk, retries=5, wait=1):
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
# 銘柄名取得
# ============================================================
def get_company_name(ticker):
    try:
        tk = yf.Ticker(ticker)
        name = tk.fast_info.get("longName")
        if name:
            return name
        return tk.info.get("longName", ticker)
    except:
        return ticker


# ============================================================
# Ticker整形
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
# RSI 計算
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
# 押し目判定 judge_signal（あなたのロジック100%）
# ============================================================
def judge_signal(price, ma25, ma50, ma75, bb_lower1, bb_upper1, bb_lower2,
                 rsi, per, pbr, dividend_yield, high_52w, low_52w):

    if rsi is None:
        return "RSI不明", "⚪️", 0

    if price <= ma75 and rsi < 40 and price <= bb_lower1:
        return "バーゲン（強い押し目）", "🔴", 3

    elif (price <= ma75 and price < bb_lower1) or (rsi < 30 and price < bb_lower1):
        return "そこそこ押し目", "🟠", 2

    elif price < ma25 * 0.97 and rsi < 37.5 and price <= bb_lower1:
        return "軽い押し目", "🟡", 1

    elif is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w) <= 40:
        return "高値圏（要注意）", "🔥", 0

    else:
        return "押し目シグナルなし", "🟢", 0


# ============================================================
# 順張り / 逆張りスコア
# ============================================================
def is_flat(ma25, ma50, ma75, tol=0.03):
    return (max([ma25, ma50, ma75]) - min([ma25, ma50, ma75])) / max([ma25, ma50, ma75]) <= tol


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


# ============================================================
# 裁量範囲（順張り / 逆張り）
# ============================================================
def trend_buy_range(ma25, ma50, ma75, bb_l1, highscore):
    if not (ma75 < ma50 < ma25 or is_flat(ma25, ma50, ma75)):
        return None
    slope = (ma25 - ma50) / ma50 * 100
    if not (0 <= slope <= 0.3):
        return None
    if highscore < 60:
        return None

    center = (ma25 + ma50) / 2
    return {
        "center": center,
        "upper": center * 1.03,
        "lower": max(center * 0.95, bb_l1)
    }


def contrarian_buy_range(ma25, ma50, ma75, bb_l1, low_score, rsi_slope, pbr, div):
    if not (ma75 > ma50 > ma25 or is_flat(ma25, ma50, ma75)):
        return None
    if rsi_slope >= 0:
        return None
    if low_score < 60:
        return None

    center = (ma25 + bb_l1) / 2
    tag = []
    if pbr and pbr < 1.0: tag.append("PBR割安")
    if div and div > 3.0: tag.append("高配当")

    return {
        "center": center,
        "upper": center * 1.08,
        "lower": center * 0.97,
        "tag": " ".join(tag)
    }


# ============================================================
# メイン処理
# ============================================================
ticker_input = st.text_input("ティッカー（例: AAPL / 7203 / 8306.T）", "")
ticker = convert_ticker(ticker_input)

if not ticker:
    st.stop()

# ---- info ----
tk = safe_ticker(ticker)
info = safe_fast_info(tk)

# ---- 銘柄名 ----
name = get_company_name(ticker)
st.subheader(f"📌 {ticker} / {name}")


# ---- 取引所 ----
exchange = get_exchange(info, ticker)
st.write(f"🕒 市場状態：**{exchange}（{market_state(exchange)}）**")


# ---- price ----
df = get_price_cached(ticker)
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

high52 = info.get("yearHigh")
low52 = info.get("yearLow")
per = info.get("peRatio")
pbr = info.get("priceToBook")
div = info.get("dividendYield")

# ---- スコア ----
high_score = is_high_price_zone(price, ma25, ma50, bb_u1, rsi, per, pbr, high52)
low_score = is_low_price_zone(price, ma25, ma50, bb_l1, bb_l2, rsi, per, pbr, low52)
rsi_slope = df["RSI"].iloc[-1] - df["RSI"].iloc[-5]


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
# ② 順張り or 逆張りの自動分岐
# ============================================================
is_mid_uptrend = ma25 > ma50 and ma25 > ma75

trend_range = trend_buy_range(ma25, ma50, ma75, bb_l1, high_score)
contrarian_range = contrarian_buy_range(ma25, ma50, ma75, bb_l1,
                                        low_score, rsi_slope, pbr, div)


# ============================================================
# 裁量レンジの表示（先に出す）
# ============================================================
st.markdown("---")
st.subheader("📌 裁量買いレンジ")

if is_mid_uptrend and trend_range:
    st.success("📈 順張り裁量買いレンジ")
    st.write(f"- 中心価格：{trend_range['center']:.2f}")
    st.write(f"- 買いレンジ：{trend_range['lower']:.2f} ～ {trend_range['upper']:.2f}")

elif not is_mid_uptrend and contrarian_range:
    st.success("🧮 逆張り裁量買いレンジ")
    st.write(f"- 中心価格：{contrarian_range['center']:.2f}")
    st.write(f"- 買いレンジ：{contrarian_range['lower']:.2f} ～ {contrarian_range['upper']:.2f}")
    if contrarian_range["tag"]:
        st.write(f"- タグ：{contrarian_range['tag']}")

else:
    st.warning("裁量買い条件なし")


# ============================================================
# ③ HTMLテーブル（順張り or 逆張り）
# ============================================================

# ====== 順張り用変数 ======
trend_mark = "✔" if (ma25 > ma50 > ma75 or is_flat(ma25, ma50, ma75)) else "✖"
slope_mark = "✔" if 0 <= rsi_slope <= 0.3 else "✖"
high_score_text = f"{high_score} 点"
center_price_text = f"{(ma25 + ma50) / 2:.2f}"
upper_bound_text2 = f"{((ma25 + ma50) / 2) * 1.03:.2f}"
lower_bound_text2 = f"{max(((ma25 + ma50) / 2) * 0.95, bb_l1):.2f}"
bb_adjusted_text = f"{bb_l1:.2f}"
trend_comment = "順張り裁量買いOK" if trend_range else "条件不足"

# ====== 逆張り用変数 ======
trend_mark2 = "✔" if (ma75 > ma50 > ma25 or is_flat(ma25, ma50, ma75)) else "✖"
slope_mark2 = "✔" if rsi_slope < 0 else "✖"
score_text = f"{low_score} 点"
center_price_text2 = f"{(ma25 + bb_l1) / 2:.2f}"
upper_bound_text = f"{((ma25 + bb_l1) / 2) * 1.08:.2f}"
lower_bound_text = f"{((ma25 + bb_l1) / 2) * 0.97:.2f}"
contrarian_comment = "逆張り裁量買いOK" if contrarian_range else "条件不足"


# ============================================================
# ④ テーブル表示（順張り or 逆張り）
# ============================================================

if is_mid_uptrend:

    st.markdown(f"""
    <div style="margin-top:4em; font-size:24px; font-weight:bold;">📈 <順張り>裁量買いの検討（25MA>50MA∧25MA>75MA）</div>
    <table>
        <tr><th align="left">項目</th><th align="left">内容</th><th align="left">判定</th></tr>
        <tr><td>中期トレンド</td><td>25MA(±3%) ≧ 50MA(±3%) ≧ 75MA(±3%)（上昇または横ばい）</td><td>{trend_mark}</td></tr>
        <tr><td>短期傾向</td><td>25MAの傾きが過去5日で ±0.3%以内（横ばい〜緩やかな上昇）</td><td>{slope_mark}</td></tr>
        <tr><td>順張り押し目判定</td><td>ブルスコア60点以上で順張り押し目候補</td><td>{high_score_text}</td></tr>
        <tr><td>中心価格</td><td>25MAと50MAの平均</td><td>{center_price_text}</td></tr>
        <tr><td>上側許容幅</td><td>中心価格×1.03</td><td>{upper_bound_text2}</td></tr>
        <tr><td>下側許容幅</td><td>中心価格×0.95 または BB−1σの高い方</td><td>{lower_bound_text2}</td></tr>
        <tr><td>BB調整下限</td><td>BB−1σ</td><td>{bb_adjusted_text}</td></tr>
        <tr><td>判定</td><td>順張り裁量評価</td><td><strong>{trend_comment}</strong></td></tr>
    </table>
    """, unsafe_allow_html=True)

else:

    st.markdown(f"""
    <div style="margin-top:4em; font-size:24px; font-weight:bold;">🧮 <逆張り>裁量買いの検討</div>
    <table>
        <tr><th align="left">項目</th><th align="left">内容</th><th align="left">判定</th></tr>
        <tr><td>中期トレンド</td><td>75MA(±3%) ≧ 50MA(±3%) ≧ 25MA(±3%)（下降または横ばい）</td><td>{trend_mark2}</td></tr>
        <tr><td>短期傾向</td><td>25MAの傾きが過去5日でマイナス（下落傾向）</td><td>{slope_mark2}</td></tr>
        <tr><td>割安圏判定</td><td>ベアスコア60点以上で割安候補</td><td>{score_text}</td></tr>
        <tr><td>中心価格</td><td>25MAとBB−1σの平均</td><td>{center_price_text2}</td></tr>
        <tr><td>上側許容幅</td><td>中心価格×1.08</td><td>{upper_bound_text}</td></tr>
        <tr><td>下側許容幅</td><td>中心価格×0.97</td><td>{lower_bound_text}</td></tr>
        <tr><td>判定</td><td>逆張り裁量評価</td><td><strong>{contrarian_comment}</strong></td></tr>
    </table>
    """, unsafe_allow_html=True)
