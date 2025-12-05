import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz


# ==========================================================
# 0️⃣ Streamlit 基本設定
# ==========================================================
st.set_page_config(page_title="押し目判定ツール（プロ版）", page_icon="📉")
st.title("🔍 押し目＋裁量買いレンジ（順張り・逆張り）プロ版")


# ==========================================================
# 1️⃣ ティッカー補正
# ==========================================================
def convert_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()
    if ticker.endswith(".T") or not ticker.isdigit():
        return ticker
    return ticker + ".T"


# ==========================================================
# 2️⃣ テクニカル計算の補助関数
# ==========================================================
def judge_bb_signal(price, bb_u1, bb_u2, bb_l1, bb_l2):
    if price >= bb_u2:
        return "非常に割高（+2σ以上）", "🔥", 3
    elif price >= bb_u1:
        return "やや割高（+1σ以上）", "📈", 2
    elif price <= bb_l2:
        return "過度な売られすぎ（-2σ以下）", "🧊", 3
    elif price <= bb_l1:
        return "やや売られ気味（-1σ以下）", "📉", 2
    return "平均圏（±1σ内）", "⚪️", 1


def is_high_price_zone(price, ma25, ma50, bb_u1, rsi, high_52w):
    score = 0
    if price <= ma25 * 1.10 and price <= ma50 * 1.10:
        score += 20
    if price <= bb_u1:
        score += 20
    if rsi < 70:
        score += 15
    if price < high_52w * 0.95:
        score += 15
    return score


def is_low_price_zone(price, ma25, ma50, bb_l1, bb_l2, rsi, low_52w):
    score = 0
    if price < ma25 * 0.90 and price < ma50 * 0.90:
        score += 20
    if price < bb_l1:
        score += 15
    if price < bb_l2:
        score += 20
    if rsi < 30:
        score += 15
    if price <= low_52w * 1.05:
        score += 15
    return score


def is_flat_ma(ma25, ma50, ma75, tol=0.03):
    values = [ma25, ma50, ma75]
    return (max(values) - min(values)) / max(values) <= tol


# ==========================================================
# 3️⃣ 押し目判定（アプリの最重要コアロジック）
# ==========================================================
def judge_signal(price, ma25, ma50, ma75, bb_l1, bb_u1, bb_l2, rsi, high_52w, low_52w):

    if rsi is None:
        return "RSI不明", "⚪️", 0

    if price <= ma75 and rsi < 40 and price <= bb_l1:
        return "バーゲン（強い押し目）", "🔴", 3

    elif (price <= ma75 and price < bb_l1) or (rsi < 30 and price < bb_l1):
        return "そこそこ押し目", "🟠", 2

    elif price < ma25 * 0.97 and rsi < 37.5 and price <= bb_l1:
        return "軽い押し目", "🟡", 1

    elif is_high_price_zone(price, ma25, ma50, bb_u1, rsi, high_52w) <= 40:
        return "高値圏（要注意）", "🔥", 0

    return "押し目シグナルなし", "🟢", 0


# ==========================================================
# 4️⃣ 裁量買いレンジ テーブル生成（順張り / 逆張り）
# ==========================================================

# —— 順張り（あなた仕様） ——
def build_trend_table(ma25, ma50, ma75, bb_l1, high_score, df):
    # 判定条件
    mid_trend = ma75 < ma50 < ma25

    ma25_slope = (df["25MA"].iloc[-1] - df["25MA"].iloc[-5]) / df["25MA"].iloc[-5] * 100
    slope_ok = (abs(ma25_slope) <= 0.3 and ma25_slope >= 0)

    # レンジ計算（常に表示）
    center = (ma25 + ma50) / 2
    upper = center * 1.03
    lower = max(center * 0.95, bb_l1)

    # 総合判定
    cond_sum = (1 if mid_trend else 0) + (1 if slope_ok else 0) + (1 if high_score >= 60 else 0)
    final_text = ["見送り", "慎重に", "検討の余地あり", "非常に魅力的"][cond_sum]

    df_out = pd.DataFrame([
        ["中期トレンド", "25>50>75（上昇または横ばい）", "○" if mid_trend else "×"],
        ["短期傾向", "MA25が横ばい〜上昇", "○" if slope_ok else "×"],
        ["割高否定", "スコア ≥60", f"{high_score}"],
        ["中心価格", "25MAと50MAの平均", f"{center:.2f}"],
        ["上側許容", "×1.03", f"{upper:.2f}"],
        ["下側許容", "×0.95 or BB-1σ", f"{lower:.2f}"],
        ["判定", "—", f"**{final_text}**"],
    ], columns=["項目", "内容", "判定"])

    return df_out


# —— 逆張り（あなたのスクショを完全再現） ——
def build_contrarian_table(ma25, ma50, ma75, bb_l1, bb_l2, rsi, low_52w, df):
    low_score = is_low_price_zone(close, ma25, ma50, bb_l1, bb_l2, rsi, low_52w)

    # 条件
    mid_trend = (ma75 > ma50 > ma25) or is_flat_ma(ma25, ma50, ma75)

    ma25_slope = (df["25MA"].iloc[-1] - df["25MA"].iloc[-5]) / df["25MA"].iloc[-5] * 100
    slope_ok = (ma25_slope < 0)

    # レンジ計算（常に表示）
    center = (ma25 + bb_l1) / 2
    upper = center * 1.08
    lower = center * 0.97

    # 最終判定
    cond_sum = (1 if mid_trend else 0) + (1 if slope_ok else 0) + (1 if low_score >= 60 else 0)
    final_text = ["見送り", "慎重に", "検討の余地あり", "非常に魅力的"][cond_sum]

    df_out = pd.DataFrame([
        ["中期トレンド", "下降 or 横ばい", "○" if mid_trend else "×"],
        ["短期傾向", "MA25が下降", "○" if slope_ok else "×"],
        ["割安判定", "スコア ≥60", f"{low_score}"],
        ["中心価格", "25MAとBB-1σの平均", f"{center:.2f}"],
        ["上側許容", "×1.08", f"{upper:.2f}"],
        ["下側許容", "×0.97", f"{lower:.2f}"],
        ["判定", "—", f"**{final_text}**"],
    ], columns=["項目", "内容", "判定"])

    return df_out


# ==========================================================
# 5️⃣ ユーザー入力
# ==========================================================
ticker_raw = st.text_input("ティッカー（7203, 8306.T, AAPLなど）", "")
ticker = convert_ticker(ticker_raw)
if not ticker:
    st.stop()


# ==========================================================
# 6️⃣ 株価取得（API 1回）
# ==========================================================
df = yf.download(ticker, period="120d", interval="1d")

if df.empty:
    st.error("データ取得失敗")
    st.stop()

if isinstance(df.columns, pd.MultiIndex):
    df.columns = ["_".join(col) for col in df.columns]

close_col = [c for c in df.columns if "Close" in c][0]
close = df[close_col].iloc[-1]
previous_close = df[close_col].iloc[-2]


# ==========================================================
# 7️⃣ 配当取得（API 2回目）
# ==========================================================
divs = yf.Ticker(ticker).dividends
dividend_yield = None

if isinstance(divs, pd.Series) and len(divs) > 0:
    divs.index = pd.to_datetime(divs.index, errors="coerce").dropna().tz_localize(None)
    one_year_ago = datetime.now().replace(tzinfo=None) - timedelta(days=365)
    last_year = divs[divs.index >= one_year_ago]
    if len(last_year) > 0:
        dividend_yield = (last_year.sum() / close) * 100


# ==========================================================
# 8️⃣ テクニカル計算
# ==========================================================
df["25MA"] = df[close_col].rolling(25).mean()
df["50MA"] = df[close_col].rolling(50).mean()
df["75MA"] = df[close_col].rolling(75).mean()

df["20MA"] = df[close_col].rolling(20).mean()
df["20STD"] = df[close_col].rolling(20).std()

df["BB_u1"] = df["20MA"] + df["20STD"]
df["BB_u2"] = df["20MA"] + 2 * df["20STD"]
df["BB_l1"] = df["20MA"] - df["20STD"]
df["BB_l2"] = df["20MA"] - 2 * df["20STD"]

# RSI
delta = df[close_col].diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)
avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean().replace(0, 1e-10)
df["RSI"] = 100 - (100 / (1 + (avg_gain / avg_loss)))

df = df.dropna()
last = df.iloc[-1]

# 値抽出
ma25 = last["25MA"]
ma50 = last["50MA"]
ma75 = last["75MA"]

bb_u1 = last["BB_u1"]
bb_u2 = last["BB_u2"]
bb_l1 = last["BB_l1"]
bb_l2 = last["BB_l2"]

rsi = last["RSI"]

high_52w = df[close_col].max()
low_52w = df[close_col].min()

# ==========================================================
# 9️⃣ 押し目判定 → 最優先表示
# ==========================================================
signal_text, signal_icon, signal_strength = judge_signal(
    close, ma25, ma50, ma75, bb_l1, bb_u1, bb_l2, rsi,
    high_52w, low_52w
)

st.markdown("## 🎯 押し目判定（システム判定）")
st.markdown(f"### {signal_icon} {signal_text}")
st.progress(signal_strength / 3)


# ==========================================================
# 🔟 補助指標（RSI / BB）
# ==========================================================
bb_text, bb_icon, _ = judge_bb_signal(close, bb_u1, bb_u2, bb_l1, bb_l2)

st.markdown("## 📊 補助指標（RSI / BB）")
st.markdown(f"- **RSI:** {rsi:.1f}")
st.markdown(f"- **BB判定:** {bb_text}")


# ==========================================================
# 1️⃣1️⃣ 裁量買いレンジ（順張り or 逆張り）
# ==========================================================
st.markdown("---")

is_uptrend = ma75 < ma50 < ma25

highprice_score = is_high_price_zone(close, ma25, ma50, bb_u1, rsi, high_52w)

if is_uptrend:
    st.markdown("## 📈 <順張り> 裁量買いレンジ")
    table = build_trend_table(ma25, ma50, ma75, bb_l1, highprice_score, df)
else:
    st.markdown("## 🧮 <逆張り> 裁量買いレンジ")
    table = build_contrarian_table(ma25, ma50, ma75, bb_l1, bb_l2, rsi, low_52w, df)

st.write(table)
