# ===========================================================
# 📊 Streamlit：買いシグナル チェッカー（プロ版）
# ===========================================================

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# -----------------------------------------------------------
# Streamlit UI
# -----------------------------------------------------------
st.set_page_config(page_title="買いシグナルチェッカー", page_icon="📈")
st.title("🔍 買いシグナル チェッカー（プロ版）")


# ===========================================================
# 1. Utility
# ===========================================================
def convert_ticker(ticker: str) -> str:
    """数字だけなら .T を付ける。"""
    ticker = ticker.strip().upper()
    if ticker.isdigit():
        return ticker + ".T"
    return ticker


def safe(v, digits=2):
    """None を — に整形。"""
    return f"{v:.{digits}f}" if isinstance(v, (int, float)) else "—"


# ===========================================================
# 2. Data Fetching（APIは download + dividends のみ）
# ===========================================================
def fetch_price_data(ticker: str) -> pd.DataFrame:
    """120日間の株価データを返す。"""
    df = yf.download(ticker, period="120d", interval="1d")
    if df.empty:
        return pd.DataFrame()

    # MultiIndex → 単層化
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["_".join(col).strip() for col in df.columns]

    return df


def fetch_dividend_yield(ticker_obj, current_price: float):
    """過去1年の配当から配当利回りを計算。"""
    divs = ticker_obj.dividends

    if not isinstance(divs, pd.Series) or len(divs) == 0:
        return None

    # index 整形
    divs.index = pd.to_datetime(divs.index, errors="coerce")
    divs = divs.dropna()
    divs.index = divs.index.tz_localize(None)

    one_year_ago = datetime.now().replace(tzinfo=None) - timedelta(days=365)
    last_year = divs[divs.index >= one_year_ago]

    if len(last_year) == 0:
        return None

    annual_div = last_year.sum()
    return (annual_div / current_price) * 100 if current_price > 0 else None


# ===========================================================
# 3. Technical Indicator Calculations
# ===========================================================
def compute_technicals(df: pd.DataFrame, close_col: str):
    """MA / BB / RSI をすべて計算して返す。"""

    df["25MA"] = df[close_col].rolling(25).mean()
    df["50MA"] = df[close_col].rolling(50).mean()
    df["75MA"] = df[close_col].rolling(75).mean()

    df["20MA"] = df[close_col].rolling(20).mean()
    df["20STD"] = df[close_col].rolling(20).std()

    df["BB_+1"] = df["20MA"] + df["20STD"]
    df["BB_+2"] = df["20MA"] + 2 * df["20STD"]
    df["BB_-1"] = df["20MA"] - df["20STD"]
    df["BB_-2"] = df["20MA"] - 2 * df["20STD"]

    # RSI
    delta = df[close_col].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean().replace(0, 1e-10)
    df["RSI"] = 100 - (100 / (1 + (avg_gain / avg_loss)))

    return df.dropna()


# ===========================================================
# 4. Judgement Logic（高値・安値・BB 判定）
# ===========================================================
def judge_bb(price, bb1, bb2, bbl1, bbl2):
    if price >= bb2:  return "非常に割高", "🔥", 3
    if price >= bb1:  return "やや割高", "📈", 2
    if price <= bbl2: return "過度な売られすぎ", "🧊", 3
    if price <= bbl1: return "売られ気味", "📉", 2
    return "平均圏", "⚪️", 1


def high_price_score(price, ma25, ma50, bb1, rsi, high52):
    """高値圏スコア（割高否定）"""
    score = 0
    if price <= ma25 * 1.10 and price <= ma50 * 1.10: score += 20
    if price <= bb1: score += 20
    if rsi < 70: score += 15
    if price < high52 * 0.95: score += 15
    return score


def low_price_score(price, ma25, ma50, bbl1, bbl2, rsi, low52):
    score = 0
    if price < ma25 * 0.90 and price < ma50 * 0.90: score += 20
    if price < bbl1: score += 15
    if price < bbl2: score += 20
    if rsi < 30: score += 15
    if price <= low52 * 1.05: score += 15
    return score


# ===========================================================
# 5. Range Calculations（裁量レンジはいつでも表示）
# ===========================================================
def calc_trend_range(ma25, ma50, ma75, bb_lower):
    """順張りレンジ。条件に関係なく計算して返す。"""
    center = (ma25 + ma50) / 2
    return {
        "center": round(center, 2),
        "upper": round(center * 1.03, 2),
        "lower": round(max(center * 0.95, bb_lower), 2)
    }


def calc_contrarian_range(ma25, bb_lower1):
    """逆張りレンジ。常に計算する。"""
    center = (ma25 + bb_lower1) / 2
    return {
        "center": round(center, 2),
        "upper": round(center * 1.08, 2),
        "lower": round(center * 0.97, 2)
    }


# ===========================================================
# 6. UI Rendering
# ===========================================================
# -----------------------------------------------------------
# 入力
# -----------------------------------------------------------
user = st.text_input("ティッカー（例: AAPL, 7203, 8306.T）", value="")
ticker = convert_ticker(user)

if not ticker:
    st.stop()

# -----------------------------------------------------------
# 株価データ取得
# -----------------------------------------------------------
df = fetch_price_data(ticker)

if df.empty:
    st.error("データ取得に失敗しました")
    st.stop()

close_col = next(c for c in df.columns if "Close" in c)
close = df[close_col].iloc[-1]
prev_close = df[close_col].iloc[-2]

ticker_obj = yf.Ticker(ticker)
div_yield = fetch_dividend_yield(ticker_obj, close)

# -----------------------------------------------------------
# テクニカル計算
# -----------------------------------------------------------
df2 = compute_technicals(df.copy(), close_col)
last = df2.iloc[-1]

ma25, ma50, ma75 = last["25MA"], last["50MA"], last["75MA"]
bb1, bb2 = last["BB_+1"], last["BB_+2"]
bbl1, bbl2 = last["BB_-1"], last["BB_-2"]
rsi = last["RSI"]

high52 = df[close_col].max()
low52 = df[close_col].min()

ma25_slope = (df["25MA"].iloc[-1] - df["25MA"].iloc[-5]) / df["25MA"].iloc[-5] * 100
is_gentle_up = abs(ma25_slope) <= 0.3 and ma25_slope >= 0
is_slope_down = ma25_slope < 0

# -----------------------------------------------------------
# 判定
# -----------------------------------------------------------
bb_text, bb_icon, bb_strength = judge_bb(close, bb1, bb2, bbl1, bbl2)

high_score = high_price_score(close, ma25, ma50, bb1, rsi, high52)
low_score = low_price_score(close, ma25, ma50, bbl1, bbl2, rsi, low52)

trend_cond = [ma75 < ma50 < ma25, is_gentle_up, high_score >= 60]
contr_cond = [ma75 > ma50 > ma25 or True, is_slope_down, low_score >= 60]

trend_judge = ["見送るべき", "慎重に買い増すべき", "検討の余地あり", "非常に魅力的"][sum(trend_cond)]
contr_judge = ["見送るべき", "慎重に買い増すべき", "検討の余地あり", "非常に魅力的"][sum(contr_cond)]

# -----------------------------------------------------------
# レンジ計算（常に表示）
# -----------------------------------------------------------
trend_range = calc_trend_range(ma25, ma50, ma75, bbl1)
contr_range = calc_contrarian_range(ma25, bbl1)


# ===========================================================
# 7. UI 表示
# ===========================================================

st.markdown(f"---\n## 💡 {ticker}")

st.markdown(f"""
**💰 配当利回り**: {safe(div_yield)}%  
**📐 PER / PBR**: — / —  
""")

color = "red" if close > prev_close else "green" if close < prev_close else "black"

st.markdown(
    f"""
📊 **現在価格**: <span style='color:{color}; font-weight:bold;'>{close:.2f}</span>  
（前日終値: {prev_close:.2f}）  
- 25MA: {safe(ma25)}  
- 50MA: {safe(ma50)}  
- 75MA: {safe(ma75)}
""",
    unsafe_allow_html=True
)

st.markdown(f"**RSI**: {safe(rsi)}｜**BB判定**: {bb_icon} {bb_text}")

# -----------------------------------------------------------
# 🟦 順張りテーブル or 逆張りテーブル
# -----------------------------------------------------------
if ma75 < ma50 < ma25:
    st.markdown("## 📈 <順張り>裁量買いレンジ")
    st.markdown(f"""
| 項目 | 内容 | 判定 |
|---|---|---|
| 中期トレンド | 25 > 50 > 75 | {"○" if trend_cond[0] else "×"} |
| 短期傾向 | MA25 が横ばい〜上昇 | {"○" if trend_cond[1] else "×"} |
| 割高否定 | スコア >= 60 | {high_score} |
| 中心価格 | (25MA＋50MA)/2 | {safe(trend_range["center"])} |
| 上側許容 | ×1.03 | {safe(trend_range["upper"])} |
| 下側許容 | ×0.95 or BB-1σ | {safe(trend_range["lower"])} |
| 判定 | — | **{trend_judge}** |
""")
else:
    st.markdown("## 🧮 <逆張り>裁量買いレンジ")
    st.markdown(f"""
| 項目 | 内容 | 判定 |
|---|---|---|
| 中期トレンド | 下降 or 横ばい | {"○" if contr_cond[0] else "×"} |
| 短期傾向 | MA25 が下降 | {"○" if contr_cond[1] else "×"} |
| 割安判定 | スコア >= 60 | {low_score} |
| 中心価格 | 25MAとBB-1σの平均 | {safe(contr_range["center"])} |
| 上側許容 | ×1.08 | {safe(contr_range["upper"])} |
| 下側許容 | ×0.97 | {safe(contr_range["lower"])} |
| 判定 | — | **{contr_judge}** |
""")
