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
# 東証銘柄の企業名辞書（補完用）
# ============================================================
JP_STOCK_NAMES = {
    "9023.T": "TOKYO METRO",
    "7203.T": "TOYOTA MOTOR",
    "8306.T": "MITSUBISHI UFJ",
    "4063.T": "SHIN-ETSU CHEMICAL",
    "9432.T": "NTT",
    "2768.T": "SOGO SHOSHA",
}


# ============================================================
# yfinance 安全アクセス（Rate limit 対策）
# ============================================================
def safe_info(ticker, retries=3, wait=2):
    for i in range(retries):
        try:
            return yf.Ticker(ticker).info
        except Exception as e:
            if "Too Many Requests" in str(e):
                time.sleep(wait)
                wait *= 2
            else:
                raise
    return {}


@st.cache_data(ttl=1800)
def get_info_cached(ticker):
    return safe_info(ticker)


@st.cache_data(ttl=1800)
def get_price_cached(ticker):
    return yf.download(ticker, period="160d", interval="1d")


# ============================================================
# ティッカー変換
# ============================================================
def convert_ticker(t):
    t = t.strip().upper()
    if t.endswith(".T") or not t.isdigit():
        return t
    return t + ".T"


# ============================================================
# 銘柄名を必ず取得（fast_info → info → displayName → JP辞書）
# ============================================================
def get_company_name(ticker):
    try:
        if ticker in JP_STOCK_NAMES:
            return JP_STOCK_NAMES[ticker]

        tk = yf.Ticker(ticker)

        fi = tk.fast_info
        for key in ["longName", "shortName", "displayName"]:
            if key in fi and isinstance(fi[key], str):
                return fi[key]

        info = tk.info
        for key in ["longName", "shortName", "displayName"]:
            if key in info and isinstance(info[key], str):
                return info[key]

        return ticker
    except:
        return ticker


# ============================================================
# ボリンジャーバンド判定（あなたのロジック）
# ============================================================
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


# ============================================================
# 市場状態判定
# ============================================================
def get_exchange(info, ticker):
    if ticker.endswith(".T") or ticker.isdigit():
        return "東証"

    ex = info.get("exchange", "").upper()
    if ex in ["NMS", "NASDAQ"]: return "NASDAQ"
    if ex in ["NYQ", "NYSE"]: return "NYSE"
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


def is_flat(ma25, ma50, ma75, tol=0.03):
    arr = [ma25, ma50, ma75]
    return (max(arr) - min(arr)) / max(arr) <= tol


# ============================================================
# 押し目シグナル（あなたの元ロジック）
# ============================================================
def judge_signal(price, ma25, ma50, ma75, bb_l1, bb_u1, bb_l2, rsi, per, pbr, div, high_52w, low_52w):
    if rsi is None:
        return "RSI不明", "⚪️", 0

    if price <= ma75 and rsi < 40 and price <= bb_l1:
        return "バーゲン（強い押し目）", "🔴", 3

    elif (price <= ma75 and price < bb_l1) or (rsi < 30 and price < bb_l1):
        return "そこそこ押し目", "🟠", 2

    elif price < ma25 * 0.97 and rsi < 37.5 and price <= bb_l1:
        return "軽い押し目", "🟡", 1

    elif is_high_price_zone(price, ma25, ma50, bb_u1, rsi, per, pbr, high_52w) <= 40:
        return "高値圏（要注意！）", "🔥", 0

    else:
        return "押し目シグナルなし", "🟢", 0


# ============================================================
# スコア（順張り/逆張り）
# ============================================================
def is_high_price_zone(price, ma25, ma50, bb_u1, rsi, per, pbr, high_52w):
    score = 0
    if price <= ma25 * 1.10 and price <= ma50 * 1.10: score += 20
    if price <= bb_u1: score += 20
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
# ファンダメンタル強化取得（今回の強化ポイント）
# ============================================================
def get_fundamentals(ticker, info, price):
    """industry / PER / PBR / 配当利回り を強化取得"""

    # ---------- 業種 ----------
    industry = "N/A"

    if "industry" in info and isinstance(info["industry"], str):
        industry = info["industry"]
    elif "sector" in info and isinstance(info["sector"], str):
        industry = info["sector"]

    # ---------- 配当利回り（過去1年配当から再計算） ----------
    div_yield = "N/A"
    try:
        tk = yf.Ticker(ticker)
        divs = tk.dividends
        if len(divs) > 0:
            one_year = divs[divs.index > (divs.index.max() - pd.Timedelta(days=365))].sum()
            if one_year > 0:
                div_yield = round(one_year / price * 100, 2)
    except:
        pass

    # ---------- PER ----------
    per = "N/A"
    try:
        eps = info.get("epsTrailingTwelveMonths")
        if eps and eps != 0:
            per = round(price / eps, 2)
    except:
        pass

    # ---------- PBR ----------
    pbr = "N/A"
    try:
        book = info.get("bookValue")
        if book and book != 0:
            pbr = round(price / book, 2)
    except:
        pass

    return industry, div_yield, per, pbr


# ============================================================
# メイン処理
# ============================================================
ticker_input = st.text_input("ティッカー（例: AAPL / 7203 / 8306.T）", "")

ticker = convert_ticker(ticker_input)
if not ticker:
    st.stop()

info = get_info_cached(ticker)
name = get_company_name(ticker)

exchange = get_exchange(info, ticker)
state = market_state(exchange)

st.subheader(f"📌 {ticker} / {name}")
st.write(f"🕒 市場状態：**{exchange}（{state}）**")


# price データ
df = get_price_cached(ticker)
close_col = [c for c in df.columns if "Close" in c][0]

df["25MA"] = df[close_col].rolling(25).mean()
df["50MA"] = df[close_col].rolling(50).mean()
df["75MA"] = df[close_col].rolling(75).mean()
df["20MA"] = df[close_col].rolling(20).mean()
df["20STD"] = df[close_col].rolling(20).std()

df["BB_+1σ"] = df["20MA"] + df["20STD"]
df["BB_+2σ"] = df["20MA"] + 2 * df["20STD"]
df["BB_-1σ"] = df["20MA"] - df["20STD"]
df["BB_-2σ"] = df["20MA"] - 2 * df["20STD"]

df["RSI"] = calc_rsi(df, close_col)

last = df.dropna().iloc[-1]

price = float(last[close_col])
ma25 = float(last["25MA"])
ma50 = float(last["50MA"])
ma75 = float(last["75MA"])
bb_u1 = float(last["BB_+1σ"])
bb_u2 = float(last["BB_+2σ"])
bb_l1 = float(last["BB_-1σ"])
bb_l2 = float(last["BB_-2σ"])
rsi = float(last["RSI"])

# 前日終値
close_price = df[close_col].iloc[-2]

# 企業情報ファンダメンタル
industry, div_calc, per_calc, pbr_calc = get_fundamentals(ticker, info, price)

div_text = f"{div_calc}%" if div_calc != "N/A" else "N/A"
per_text = f"{per_calc}" if per_calc != "N/A" else "N/A"
pbr_text = f"{pbr_calc}" if pbr_calc != "N/A" else "N/A"

# BB 判定
bb_text, bb_icon, _ = judge_bb_signal(price, bb_u1, bb_u2, bb_l1, bb_l2)

# RSI slope
rsi_slope = (df["RSI"].iloc[-1] - df["RSI"].iloc[-5]) / abs(df["RSI"].iloc[-5] + 1e-10) * 100

# スコア
high_score = is_high_price_zone(price, ma25, ma50, bb_u1, rsi, per_calc, pbr_calc, info.get("fiftyTwoWeekHigh"))
low_score = is_low_price_zone(price, ma25, ma50, bb_l1, bb_l2, rsi, per_calc, pbr_calc, info.get("fiftyTwoWeekLow"))


# ============================================================
# 銘柄基本情報の表示
# ============================================================
st.markdown(f"**🏭 業種**: {industry}")
st.markdown(f"**💰 配当利回り**: {div_text}｜**📐 PER**: {per_text}｜**🧮 PBR**: {pbr_text}")

# 色付け
if price > close_price:
    color = "red"
elif price < close_price:
    color = "green"
else:
    color = "white"

st.markdown(
    f"📊 現値: <span style='color:{color}; font-weight:bold;'>{price:.2f}</span> "
    f"（前日終値: {close_price:.2f}）｜25MA: {ma25:.2f}｜50MA: {ma50:.2f}｜75MA: {ma75:.2f}",
    unsafe_allow_html=True
)

st.markdown(f"📊 **RSI**: {rsi:.1f}｜**📏 BB判定(20日)**: {bb_icon} {bb_text}")
st.markdown("---")


# ============================================================
# 押し目シグナル
# ============================================================
signal_text, signal_emoji, _ = judge_signal(
    price, ma25, ma50, ma75, bb_l1, bb_u1, bb_l2, rsi,
    per_calc, pbr_calc, div_calc, info.get("fiftyTwoWeekHigh"), info.get("fiftyTwoWeekLow")
)

st.subheader("🎯 押し目シグナル（短期判定）")
st.write(f"### {signal_emoji} {signal_text}")
st.markdown("---")


# ============================================================
# 順張り or 逆張り 自動判定
# ============================================================
is_mid_uptrend = (ma25 > ma50) and (ma25 > ma75)
is_mid_downtrend = (ma75 >= ma50 >= ma25)


# ============================================================
# 4段階評価（順張り）
# ============================================================
def trend_eval():
    c = 0
    if ma25 > ma50 > ma75 or is_flat(ma25, ma50, ma75): c += 1
    if 0 <= rsi_slope <= 0.3: c += 1
    if high_score >= 60: c += 1

    if c == 3: return c, "買い候補として非常に魅力的です。"
    if c == 2: return c, "買い検討の余地があります。"
    if c == 1: return c, "慎重に検討すべき状況です。"
    return c, "現時点では見送りが妥当です。"


# ============================================================
# 4段階評価（逆張り）
# ============================================================
def contrarian_eval():
    c = 0
    if ma75 >= ma50 >= ma25: c += 1
    if rsi_slope < 0: c += 1
    if low_score >= 60: c += 1

    if c == 3: return c, "買い候補として非常に魅力的です。"
    if c == 2: return c, "買い検討の余地があります。"
    if c == 1: return c, "慎重に検討すべき状況です。"
    return c, "現時点では見送りが妥当です。"


# ============================================================
# テーブル表示（順張り or 逆張り）
# ============================================================
if is_mid_uptrend:

    ok_count, comment = trend_eval()

    trend_mark = "〇" if (ma25 > ma50 > ma75 or is_flat(ma25, ma50, ma75)) else "×"
    slope_mark = "〇" if 0 <= rsi_slope <= 0.3 else "×"
    high_score_text = f"{high_score}点"

    center_price = (ma25 + ma50) / 2
    upper_bound = center_price * 1.03
    lower_bound = max(center_price * 0.95, bb_l1)

    st.markdown(f"""
    <div style="margin-top:2em; font-size:24px; font-weight:bold;">📈 <順張り>裁量買いの検討</div>
    <table>
        <tr><th align="left">項目</th><th align="left">内容</th><th align="left">判定</th></tr>
        <tr><td>中期トレンド</td><td>25MA ≧ 50MA ≧ 75MA（上昇 or 横ばい）</td><td>{trend_mark}</td></tr>
        <tr><td>短期傾向</td><td>25MA傾きが過去5日で ±0.3%以内</td><td>{slope_mark}</td></tr>
        <tr><td>順張り押し目判定</td><td>ブルスコア（60点以上で押し目）</td><td>{high_score_text}</td></tr>
        <tr><td>中心価格</td><td>25MAと50MAの平均</td><td>{center_price:.2f}</td></tr>
        <tr><td>上側許容幅</td><td>中心価格×1.03</td><td>{upper_bound:.2f}</td></tr>
        <tr><td>下側許容幅</td><td>中心×0.95 or BB-1σの大きい方</td><td>{lower_bound:.2f}</td></tr>
        <tr><td>判定</td><td>順張り裁量評価</td><td><strong>{comment}</strong></td></tr>
    </table>
    """, unsafe_allow_html=True)


else:

    ok_count, comment = contrarian_eval()

    trend_mark2 = "〇" if (ma75 >= ma50 >= ma25) else "×"
    slope_mark2 = "〇" if rsi_slope < 0 else "×"
    score_text = f"{low_score}点"

    center_price = (ma25 + bb_l1) / 2
    upper_bound = center_price * 1.08
    lower_bound = center_price * 0.97

    st.markdown(f"""
    <div style="margin-top:2em; font-size:24px; font-weight:bold;">🧮 <逆張り>裁量買いの検討</div>
    <table>
        <tr><th align="left">項目</th><th align="left">内容</th><th align="left">判定</th></tr>
        <tr><td>中期トレンド</td><td>75MA ≥ 50MA ≥ 25MA（下降 or 横ばい）</td><td>{trend_mark2}</td></tr>
        <tr><td>短期傾向</td><td>25MA傾きが過去5日でマイナス</td><td>{slope_mark2}</td></tr>
        <tr><td>割安圏判定</td><td>ベアスコア（60点以上）</td><td>{score_text}</td></tr>
        <tr><td>中心価格</td><td>25MAとBB-1σの平均</td><td>{center_price:.2f}</td></tr>
        <tr><td>上側許容幅</td><td>中心価格×1.08</td><td>{upper_bound:.2f}</td></tr>
        <tr><td>下側許容幅</td><td>中心価格×0.97</td><td>{lower_bound:.2f}</td></tr>
        <tr><td>判定</td><td>逆張り裁量評価</td><td><strong>{comment}</strong></td></tr>
    </table>
    """, unsafe_allow_html=True)
