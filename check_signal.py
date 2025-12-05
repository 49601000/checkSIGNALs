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
# 安全な yfinance アクセス
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
# 銘柄名取得（fast_info → info fallback）
# ============================================================
def get_company_name(ticker):
    try:
        tk = yf.Ticker(ticker)
        name = tk.fast_info.get("longName")
        if name:
            return name

        info = tk.info
        if "longName" in info:
            return info["longName"]
        if "shortName" in info:
            return info["shortName"]

        return ticker
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
# テクニカル計算
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
# 押し目判定（あなたの judge_signal）
# ============================================================
def judge_signal(price, ma25, ma50, ma75, bb_l1, bb_u1, bb_l2,
                 rsi, per, pbr, div, high52, low52):

    if rsi is None:
        return "RSI不明", "⚪️", 0

    if price <= ma75 and rsi < 40 and price <= bb_l1:
        return "バーゲン（強い押し目）", "🔴", 3

    elif (price <= ma75 and price < bb_l1) or (rsi < 30 and price < bb_l1):
        return "そこそこ押し目", "🟠", 2

    elif price < ma25 * 0.97 and rsi < 37.5 and price <= bb_l1:
        return "軽い押し目", "🟡", 1

    elif is_high_price_zone(price, ma25, ma50, bb_u1, rsi, per, pbr, high52) <= 40:
        return "高値圏（要注意）", "🔥", 0

    else:
        return "押し目シグナルなし", "🟢", 0


# ============================================================
# 順張り／逆張りスコア
# ============================================================
def is_flat(ma25, ma50, ma75, tol=0.03):
    return (max([ma25, ma50, ma75]) - min([ma25, ma50, ma75])) / max([ma25, ma50, ma75]) <= tol


def within(x, y, tol=0.03):
    return abs(x - y) / y <= tol


def is_downtrend(ma25, ma50, ma75):
    cond1 = (ma75 >= ma50) or within(ma75, ma50)
    cond2 = (ma50 >= ma25) or within(ma50, ma25)
    return cond1 and cond2


def is_high_price_zone(price, ma25, ma50, bb_u1, rsi, per, pbr, high52):
    score = 0
    if price <= ma25 * 1.10 and price <= ma50 * 1.10: score += 20
    if price <= bb_u1: score += 20
    if rsi < 70: score += 15
    if per and per < 20: score += 15
    if pbr and pbr < 2.0: score += 15
    if high52 and price < high52 * 0.95: score += 15
    return score


def is_low_price_zone(price, ma25, ma50, bb_l1, bb_l2, rsi, per, pbr, low52):
    score = 0
    if price < ma25 * 0.90 and price < ma50 * 0.90: score += 20
    if price < bb_l1: score += 15
    if price < bb_l2: score += 20
    if rsi < 30: score += 15
    if per and per < 10: score += 15
    if pbr and pbr < 1.0: score += 15
    if low52 and price <= low52 * 1.05: score += 15
    return score


# ============================================================
# 裁量範囲
# ============================================================
def trend_buy_range(ma25, ma50, ma75, bb_l1, high_score):
    if not (ma75 < ma50 < ma25 or is_flat(ma25, ma50, ma75)):
        return None
    slope = (ma25 - ma50) / ma50 * 100
    if not (0 <= slope <= 0.3):
        return None
    if high_score < 60:
        return None
    center = (ma25 + ma50) / 2
    return {
        "center": center,
        "upper": center * 1.03,
        "lower": max(center * 0.95, bb_l1)
    }


def contrarian_buy_range(ma25, ma50, ma75, bb_l1, low_score, rsi_slope, pbr, div):
    if not is_downtrend(ma25, ma50, ma75):
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

tk = safe_ticker(ticker)
info = safe_fast_info(tk)

# ---- 銘柄名表示 ----
name = get_company_name(ticker)
st.subheader(f"📌 {ticker} / {name}")

exchange = get_exchange(info, ticker)
st.write(f"🕒 市場状態：**{exchange}（{market_state(exchange)}）**")

df = get_price_cached(ticker)
close_col = [c for c in df.columns if "Close" in c][0]


# ============================================================
# テクニカル計算
# ============================================================
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

# スコア算出
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
# ② 順張り or 逆張り自動判定
# ============================================================
is_mid_uptrend = ma25 > ma50 and ma25 > ma75

trend_range = trend_buy_range(ma25, ma50, ma75, bb_l1, high_score)
contrarian_range = contrarian_buy_range(
    ma25, ma50, ma75, bb_l1,
    low_score, rsi_slope, pbr, div
)


# ============================================================
# ③ 裁量レンジ（先に表示）
# ============================================================
st.markdown("---")
st.subheader("📌 裁量買いレンジ")

if is_mid_uptrend and trend_range:
    st.success("📈 順張り裁量買い")
    st.write(f"- 中心価格：{trend_range['center']:.2f}")
    st.write(f"- 買いレンジ：{trend_range['lower']:.2f} ～ {trend_range['upper']:.2f}")

elif not is_mid_uptrend and contrarian_range:
    st.success("🧮 逆張り裁量買い")
    st.write(f"- 中心値：{contrarian_range['center']:.2f}")
    st.write(f"- 買いレンジ：{contrarian_range['lower']:.2f} ～ {contrarian_range['upper']:.2f}")
    if contrarian_range["tag"]:
        st.write(f"- タグ：{contrarian_range['tag']}")

else:
    st.warning("裁量買い条件なし")


# ============================================================
# ④ 評価（4段階）
# ============================================================

# ---- 順張り判定 ----
if is_mid_uptrend:
    ok = 0
    if ma25 > ma50 > ma75 or is_flat(ma25, ma50, ma75): ok += 1
    if 0 <= rsi_slope <= 0.3: ok += 1
    if high_score >= 60: ok += 1

    if ok == 3:
        trend_comment = "買い候補として非常に魅力的です。"
    elif ok == 2:
        trend_comment = "買い検討の余地があります。"
    elif ok == 1:
        trend_comment = "慎重に検討すべき状況です。"
    else:
        trend_comment = "現時点では見送りが妥当です。"

# ---- 逆張り判定 ----
else:
    ok = 0
    if is_downtrend(ma25, ma50, ma75): ok += 1
    if rsi_slope < 0: ok += 1
    if low_score >= 60: ok += 1

    if ok == 3:
        contrarian_comment = "買い候補として非常に魅力的です。"
    elif ok == 2:
        contrarian_comment = "買い検討の余地があります。"
    elif ok == 1:
        contrarian_comment = "慎重に検討すべき状況です。"
    else:
        contrarian_comment = "現時点では見送りが妥当です。"


# ============================================================
# ⑤ HTMLテーブル
# ============================================================

# ---- 順張りテーブル ----
trend_mark = "〇" if (ma25 > ma50 > ma75 or is_flat(ma25, ma50, ma75)) else "×"
slope_mark = "〇" if 0 <= rsi_slope <= 0.3 else "×"

center_price_text = f"{(ma25 + ma50) / 2:.2f}"
upper_bound_text2 = f"{((ma25 + ma50) / 2) * 1.03:.2f}"
lower_bound_text2 = f"{max(((ma25 + ma50) / 2) * 0.95, bb_l1):.2f}"
bb_adjusted_text = f"{bb_l1:.2f}"

# ---- 逆張りテーブル ----
trend_mark2 = "〇" if is_downtrend(ma25, ma50, ma75) else "×"
slope_mark2 = "〇" if rsi_slope < 0 else "×"

center_price_text2 = f"{(ma25 + bb_l1) / 2:.2f}"
upper_bound_text = f"{((ma25 + bb_l1) / 2) * 1.08:.2f}"
lower_bound_text = f"{((ma25 + bb_l1) / 2) * 0.97:.2f}"


# ============================================================
# ⑥ テーブル出力（順張り or 逆張り）
# ============================================================

if is_mid_uptrend:

    st.markdown(f"""
    <div style="margin-top:4em; font-size:24px; font-weight:bold;">📈 <順張り>裁量買いの検討</div>
    <table>
        <tr><th>項目</th><th>内容</th><th>判定</th></tr>
        <tr><td>中期トレンド</td><td>25MA ≥ 50MA ≥ 75MA（上昇または横ばい）</td><td>{trend_mark}</td></tr>
        <tr><td>短期傾向</td><td>25MAの傾き（5日）が ±0.3%以内</td><td>{slope_mark}</td></tr>
        <tr><td>順張りスコア</td><td>ブルスコア（60点以上で押し目）</td><td>{high_score}</td></tr>
        <tr><td>中心価格</td><td>25MAと50MAの平均</td><td>{center_price_text}</td></tr>
        <tr><td>上側許容幅</td><td>中心×1.03</td><td>{upper_bound_text2}</td></tr>
        <tr><td>下側許容幅</td><td>中心×0.95 or BB-1σ</td><td>{lower_bound_text2}</td></tr>
        <tr><td>BB調整下限</td><td>BB-1σ</td><td>{bb_adjusted_text}</td></tr>
        <tr><td>判定</td><td>総合評価（4段階）</td><td><strong>{trend_comment}</strong></td></tr>
    </table>
    """, unsafe_allow_html=True)

else:

    st.markdown(f"""
    <div style="margin-top:4em; font-size:24px; font-weight:bold;">🧮 <逆張り>裁量買いの検討</div>
    <table>
        <tr><th>項目</th><th>内容</th><th>判定</th></tr>
        <tr><td>中期トレンド</td><td>75MA ≥ 50MA ≥ 25MA（下降または横ばい・±3%許容）</td><td>{trend_mark2}</td></tr>
        <tr><td>短期傾向</td><td>25MAの傾き（5日）がマイナス</td><td>{slope_mark2}</td></tr>
        <tr><td>割安判定</td><td>ベアスコア（60点以上で割安）</td><td>{low_score}</td></tr>
        <tr><td>中心価格</td><td>25MAとBB-1σの平均</td><td>{center_price_text2}</td></tr>
        <tr><td>上側許容幅</td><td>中心×1.08</td><td>{upper_bound_text}</td></tr>
        <tr><td>下側許容幅</td><td>中心×0.97</td><td>{lower_bound_text}</td></tr>
        <tr><td>判定</td><td>総合評価（4段階）</td><td><strong>{contrarian_comment}</strong></td></tr>
    </table>
    """, unsafe_allow_html=True)
