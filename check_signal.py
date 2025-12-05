import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, time as t
import pytz

# ============================================================
# Streamlit 基本設定
# ============================================================
st.set_page_config(page_title="買いシグナルチェッカー", page_icon="📊")
st.title("🔍 買いシグナルチェッカー（高速×安定版）")


# ============================================================
# Yahoo Japan Finance スクレイピング（日本株用）
# ============================================================
def fetch_yahoo_japan_fundamentals(ticker):
    """
    日本株の以下の項目を Yahoo! JAPAN から取得
    ・企業名
    ・業種
    ・PER
    ・PBR
    ・配当利回り
    """
    url = f"https://finance.yahoo.co.jp/quote/{ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")

        # 企業名
        name_tag = soup.select_one("h1")
        company_name = name_tag.text.strip() if name_tag else "N/A"

        # テーブル（PER/PBR/配当利回りがある）
        table = soup.select("table tr")

        per = pbr = dividend = "N/A"
        industry = "N/A"

        for row in table:
            cols = row.text.strip().split("\n")
            if len(cols) < 2:
                continue

            label, val = cols[0], cols[1]

            if "PER" in label:
                per = val.replace("倍", "")
            if "PBR" in label:
                pbr = val.replace("倍", "")
            if "配当利回り" in label:
                dividend = val.replace("%", "")
            if "業種" in label:
                industry = val

        return {
            "name": company_name,
            "industry": industry,
            "per": per,
            "pbr": pbr,
            "dividend": dividend
        }

    except Exception:
        return None


# ============================================================
# yfinance の安全取得（Rate limit 対策）
# ============================================================
def safe_info(ticker, retries=3, wait=1):
    for _ in range(retries):
        try:
            return yf.Ticker(ticker).info
        except Exception:
            time.sleep(wait)
            wait *= 2
    return {}


@st.cache_data(ttl=1800)
def get_info_cached(t):
    return safe_info(t)


@st.cache_data(ttl=900)
def get_price_cached(t):
    return yf.download(t, period="180d", interval="1d")


# ============================================================
# ティッカー変換（数字 → .T）
# ============================================================
def convert_ticker(t):
    t = t.strip().upper()
    if t.endswith(".T") or not t.isdigit():
        return t
    return t + ".T"


# ============================================================
# テクニカル指標
# ============================================================
def calc_rsi(df, col="Close", period=14):
    diff = df[col].diff()
    gain = diff.clip(lower=0)
    loss = -diff.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean().replace(0, 1e-10)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ============================================================
# ボリンジャーバンド判定
# ============================================================
def judge_bb_signal(price, bb_u1, bb_u2, bb_l1, bb_l2):
    if price >= bb_u2:
        return "非常に割高（+2σ以上）", "🔥"
    elif price >= bb_u1:
        return "やや割高（+1σ以上）", "📈"
    elif price <= bb_l2:
        return "過度な売られすぎ（-2σ以下）", "🧊"
    elif price <= bb_l1:
        return "やや売られ気味（-1σ以下）", "📉"
    else:
        return "平均圏（±1σ内）", "⚪️"


# ============================================================
# 押し目シグナル
# ============================================================
def judge_signal(price, ma25, ma50, ma75, bb_l1, bb_u1, bb_l2, rsi, per, pbr, high52, low52):
    if rsi is None:
        return "RSI不明", "⚪️"

    if price <= ma75 and rsi < 40 and price <= bb_l1:
        return "バーゲン（強い押し目）", "🔴"

    elif (price <= ma75 and price < bb_l1) or (rsi < 30 and price < bb_l1):
        return "そこそこ押し目", "🟠"

    elif price < ma25 * 0.97 and rsi < 37.5 and price <= bb_l1:
        return "軽い押し目", "🟡"

    elif price >= bb_u1:
        return "高値圏（要注意）", "🔥"

    return "押し目シグナルなし", "🟢"


# ============================================================
# 順張りスコア／逆張りスコア
# ============================================================
def is_high_price_zone(price, ma25, ma50, bb_u1, rsi, per, pbr, high52):
    score = 0
    if price <= ma25 * 1.10 and price <= ma50 * 1.10:
        score += 20
    if price <= bb_u1:
        score += 20
    if rsi < 70:
        score += 15
    if per not in ["N/A", None] and float(per) < 20:
        score += 15
    if pbr not in ["N/A", None] and float(pbr) < 2.0:
        score += 15
    if high52 and price < high52 * 0.95:
        score += 15
    return score


def is_low_price_zone(price, ma25, ma50, bb_l1, bb_l2, rsi, per, pbr, low52):
    score = 0
    if price < ma25 * 0.90 and price < ma50 * 0.90:
        score += 20
    if price < bb_l1:
        score += 15
    if price < bb_l2:
        score += 20
    if rsi < 30:
        score += 15
    if per not in ["N/A", None] and float(per) < 10:
        score += 15
    if pbr not in ["N/A", None] and float(pbr) < 1.0:
        score += 15
    if low52 and price <= low52 * 1.05:
        score += 15
    return score


# ============================================================
# 裁量買いレンジ（順張り・逆張り）
# ============================================================
def trend_buy_range(ma25, ma50, ma75, bb_l1, score):
    # 75 < 50 < 25 かフラット
    arr = [ma25, ma50, ma75]
    if not (ma25 > ma50 > ma75 or (max(arr)-min(arr))/max(arr) <= 0.03):
        return None

    slope = (ma25 - ma50) / ma50 * 100
    if not (0 <= slope <= 0.3):
        return None

    if score < 60:
        return None

    center = (ma25 + ma50) / 2
    return {
        "center": center,
        "upper": center * 1.03,
        "lower": max(center * 0.95, bb_l1)
    }


def contrarian_range(ma25, ma50, ma75, bb_l1, score, slope):
    # 75 > 50 > 25 かフラット
    arr = [ma25, ma50, ma75]
    if not (ma75 > ma50 > ma25 or (max(arr)-min(arr))/max(arr) <= 0.03):
        return None

    if slope >= 0:
        return None

    if score < 60:
        return None

    center = (ma25 + bb_l1) / 2
    return {
        "center": center,
        "upper": center * 1.08,
        "lower": center * 0.97
    }


# ============================================================
# 入力欄
# ============================================================
ticker_input = st.text_input("ティッカー（例: AAPL / 7203 / 8306.T）", "")

ticker = convert_ticker(ticker_input)
if not ticker:
    st.stop()

# ------------------- info 取得 -------------------
info = get_info_cached(ticker)
df = get_price_cached(ticker)

if df.empty:
    st.error("価格データが取得できません")
    st.stop()

# ------------------- 日本株ファンダ取得 -------------------
yj = fetch_yahoo_japan_fundamentals(ticker)

company_name = (yj["name"] if yj else None) or info.get("longName") or ticker
industry = (yj["industry"] if yj else "N/A")
per = (yj["per"] if yj else "N/A")
pbr = (yj["pbr"] if yj else "N/A")
dividend = (yj["dividend"] if yj else "N/A")

# ------------------- 価格・テクニカル -------------------
df["25MA"] = df["Close"].rolling(25).mean()
df["50MA"] = df["Close"].rolling(50).mean()
df["75MA"] = df["Close"].rolling(75).mean()
df["20MA"] = df["Close"].rolling(20).mean()
df["20STD"] = df["Close"].rolling(20).std()

df["BB_+1σ"] = df["20MA"] + df["20STD"]
df["BB_+2σ"] = df["20MA"] + 2 * df["20STD"]
df["BB_-1σ"] = df["20MA"] - df["20STD"]
df["BB_-2σ"] = df["20MA"] - 2 * df["20STD"]

df["RSI"] = calc_rsi(df)

last = df.dropna().iloc[-1]
prev = df.dropna().iloc[-2]

price = float(last["Close"])
close_yest = float(prev["Close"])

# 値動き色判定
color = "red" if price > close_yest else ("green" if price < close_yest else "white")

# ------------------- 基本表示 -------------------
st.subheader(f"📌 {ticker} / {company_name}")

st.markdown(f"📊 **業種**: {industry}")
st.markdown(f"💰 **配当利回り**: {dividend}%｜📐 **PER**: {per}｜🧮 **PBR**: {pbr}")
st.markdown(
    f"<span style='color:{color}; font-size:22px;'>■ 現値 {price:.2f} （前日比 {price-close_yest:+.2f}）</span><br>"
    f"25MA: {last['25MA']:.2f}｜50MA: {last['50MA']:.2f}｜75MA: {last['75MA']:.2f}",
    unsafe_allow_html=True
)

bb_text, bb_icon = judge_bb_signal(price, last["BB_+1σ"], last["BB_+2σ"], last["BB_-1σ"], last["BB_-2σ"])
st.markdown(f"📏 **RSI**: {last['RSI']:.1f}｜**BB判定**: {bb_icon} {bb_text}")


# ============================================================
# 押し目シグナル
# ============================================================
st.markdown("---")
st.subheader("🎯 押し目シグナル（短期判定）")

signal_text, signal_icon = judge_signal(
    price, last["25MA"], last["50MA"], last["75MA"],
    last["BB_-1σ"], last["BB_+1σ"], last["BB_-2σ"],
    last["RSI"], per, pbr,
    info.get("fiftyTwoWeekHigh"), info.get("fiftyTwoWeekLow")
)

st.write(f"{signal_icon} {signal_text}")


# ============================================================
# 順張り or 逆張り 自動分岐
# ============================================================
is_uptrend = last["25MA"] > last["50MA"] and last["25MA"] > last["75MA"]

high_score = is_high_price_zone(
    price, last["25MA"], last["50MA"], last["BB_+1σ"],
    last["RSI"], per, pbr, info.get("fiftyTwoWeekHigh")
)

low_score = is_low_price_zone(
    price, last["25MA"], last["50MA"],
    last["BB_-1σ"], last["BB_-2σ"], last["RSI"],
    per, pbr, info.get("fiftyTwoWeekLow")
)

slope25 = (df["25MA"].iloc[-1] - df["25MA"].iloc[-5]) / df["25MA"].iloc[-5] * 100


# ============================================================
# 順張りテーブル or 逆張りテーブル
# ============================================================
st.markdown("---")

# ----------------------- 順張り -----------------------
if is_uptrend:

    st.markdown("<h3>📈 <順張り> 裁量買いの検討</h3>", unsafe_allow_html=True)

    # 裁量レンジ
    tr = trend_buy_range(last["25MA"], last["50MA"], last["75MA"], last["BB_-1σ"], high_score)

    center_text = f"{tr['center']:.2f}" if tr else "—"
    upper_text = f"{tr['upper']:.2f}" if tr else "—"
    lower_text = f"{tr['lower']:.2f}" if tr else "—"

    trend_ok = sum([
        1 if (last["25MA"] > last["50MA"] > last["75MA"]) else 0,
        1 if (0 <= slope25 <= 0.3) else 0,
        1 if high_score >= 60 else 0
    ])

    if trend_ok == 3:
        trend_comment = "買い候補として非常に魅力的です。"
    elif trend_ok == 2:
        trend_comment = "買い検討の余地があります。"
    elif trend_ok == 1:
        trend_comment = "慎重に検討すべき状況です。"
    else:
        trend_comment = "現時点では見送りが妥当です。"

    trend_mark = "◯" if (last["25MA"] > last["50MA"] > last["75MA"]) else "×"
    slope_mark = "◯" if (0 <= slope25 <= 0.3) else "×"

    st.markdown(
        f"""
        <table>
            <tr><th>項目</th><th>内容</th><th>判定</th></tr>

            <tr><td>中期トレンド</td>
                <td>25MA ＞ 50MA ＞ 75MA（上昇または横ばい）</td>
                <td>{trend_mark}</td></tr>

            <tr><td>短期傾向</td>
                <td>25MAの傾きが過去5日で ±0.3%以内</td>
                <td>{slope_mark}</td></tr>

            <tr><td>順張り評価スコア</td>
                <td>60点以上で順張り押し目と判定</td>
                <td>{high_score}点</td></tr>

            <tr><td>中心価格</td><td>25MAと50MAの平均</td><td>{center_text}</td></tr>
            <tr><td>上側許容幅</td><td>中心価格×1.03</td><td>{upper_text}</td></tr>
            <tr><td>下側許容幅</td><td>中心価格×0.95 または BB−1σの高い方</td><td>{lower_text}</td></tr>

            <tr><td>裁量評価</td><td colspan='2'><strong>{trend_comment}</strong></td></tr>
        </table>
        """,
        unsafe_allow_html=True,
    )

# ----------------------- 逆張り -----------------------
else:

    st.markdown("<h3>🧮 <逆張り> 裁量買いの検討</h3>", unsafe_allow_html=True)

    cr = contrarian_range(
        last["25MA"], last["50MA"], last["75MA"],
        last["BB_-1σ"], low_score, slope25
    )

    center_text = f"{cr['center']:.2f}" if cr else "—"
    upper_text = f"{cr['upper']:.2f}" if cr else "—"
    lower_text = f"{cr['lower']:.2f}" if cr else "—"

    trend_mark = "◯" if (last["75MA"] > last["50MA"] > last["25MA"]) else "×"
    slope_mark = "◯" if slope25 < 0 else "×"

    trend_ok = sum([
        1 if (last["75MA"] > last["50MA"] > last["25MA"]) else 0,
        1 if (slope25 < 0) else 0,
        1 if low_score >= 60 else 0
    ])

    if trend_ok == 3:
        contrarian_comment = "割安で逆張り候補として魅力的です。"
    elif trend_ok == 2:
        contrarian_comment = "買い検討の余地があります。"
    elif trend_ok == 1:
        contrarian_comment = "慎重に検討すべき状況です。"
    else:
        contrarian_comment = "現時点では見送りが妥当です。"

    st.markdown(
        f"""
        <table>
            <tr><th>項目</th><th>内容</th><th>判定</th></tr>

            <tr><td>中期トレンド</td>
                <td>75MA ≥ 50MA ≥ 25MA（下降または横ばい）</td>
                <td>{trend_mark}</td></tr>

            <tr><td>短期傾向</td>
                <td>25MA傾きが過去5日でマイナス</td>
                <td>{slope_mark}</td></tr>

            <tr><td>割安圏スコア</td>
                <td>60点以上で割安判定</td>
                <td>{low_score}点</td></tr>

            <tr><td>中心価格</td><td>25MAとBB−1σの平均</td><td>{center_text}</td></tr>
            <tr><td>上側許容幅</td><td>中心価格×1.08</td><td>{upper_text}</td></tr>
            <tr><td>下側許容幅</td><td>中心価格×0.97</td><td>{lower_text}</td></tr>

            <tr><td>裁量評価</td><td colspan='2'><strong>{contrarian_comment}</strong></td></tr>
        </table>
        """,
        unsafe_allow_html=True,
    )
