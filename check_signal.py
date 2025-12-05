import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time
import pytz
import requests
from bs4 import BeautifulSoup
from datetime import datetime, time as t

# ============================================================
# Streamlit 基本設定
# ============================================================
st.set_page_config(page_title="買いシグナルチェッカー", page_icon="📊")
st.title("🔍 買いシグナルチェッカー（高速×安定版）")


# ============================================================
# NaN 完全防御フォーマッタ
# ============================================================
def fmt(x):
    """NaN/None を安全に 'N/A' に変換して文字列化"""
    try:
        if x is None:
            return "N/A"
        if isinstance(x, float) and np.isnan(x):
            return "N/A"
        return f"{float(x):.2f}"
    except:
        return "N/A"


# ============================================================
# 日本株ファンダメンタル（企業名・PER・PBR・利回り・業種）
# Yahoo! JAPAN Finance スクレイピング
# ============================================================
def fetch_japan_fundamentals(ticker):
    """Yahoo! JAPAN ファイナンスから企業名 / 業種 / PER / PBR / 配当利回り を取得"""
    url = f"https://finance.yahoo.co.jp/quote/{ticker}"
    name = None
    sector = None
    per = None
    pbr = None
    div_yield = None

    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if r.status_code != 200:
            return None, None, None, None, None

        soup = BeautifulSoup(r.text, "html.parser")

        # ---------- 企業名 ----------
        name_tag = soup.find("h1")
        if name_tag:
            name = name_tag.get_text(strip=True)

        # ---------- 業種（33分類） ----------
        sec_tag = soup.find("span", text="業種")
        if sec_tag and sec_tag.parent:
            sec_val = sec_tag.parent.find_all("span")
            if len(sec_val) >= 2:
                sector = sec_val[1].get_text(strip=True)

        # ---------- 指標テーブル ----------
        rows = soup.find_all("tr")
        for r in rows:
            cols = r.find_all("td")
            if len(cols) != 2:
                continue
            label = cols[0].get_text(strip=True)
            value = cols[1].get_text(strip=True)

            if "PER" in label and value.replace('.', '', 1).isdigit():
                per = float(value)

            if "PBR" in label and value.replace('.', '', 1).isdigit():
                pbr = float(value)

            if "配当利回り" in label:
                if "%" in value:
                    try:
                        div_yield = float(value.replace("%", ""))
                    except:
                        pass

    except:
        pass

    return name, sector, per, pbr, div_yield


# ============================================================
# yfinance 安全アクセス（Rate Limit 防御）
# ============================================================
def safe_info(ticker, retries=3, wait=1.5):
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


@st.cache_data(ttl=1200)
def get_info_cached(ticker):
    return safe_info(ticker)


@st.cache_data(ttl=1200)
def get_price_cached(ticker):
    return yf.download(ticker, period="200d", interval="1d")


# ============================================================
# ティッカー整形
# ============================================================
def convert_ticker(t):
    t = t.strip().upper()
    if t.endswith(".T") or not t.isdigit():
        return t
    return t + ".T"


# ============================================================
# 市場判定
# ============================================================
def get_exchange(info, ticker):
    if ticker.endswith(".T"):
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
# RSI
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
# 押し目判定
# ============================================================
def judge_signal(price, ma25, ma50, ma75, bb_l1, bb_u1, bb_l2, rsi, per, pbr, high, low):
    if rsi is None or np.isnan(rsi):
        return "RSI不明", "⚪️", 0

    if price <= ma75 and rsi < 40 and price <= bb_l1:
        return "バーゲン（強い押し目）", "🔴", 3

    if (price <= ma75 and price < bb_l1) or (rsi < 30 and price < bb_l1):
        return "そこそこ押し目", "🟠", 2

    if price < ma25 * 0.97 and rsi < 37.5 and price <= bb_l1:
        return "軽い押し目", "🟡", 1

    return "押し目シグナルなし", "🟢", 0


# ============================================================
# BB 判定
# ============================================================
def judge_bb_signal(price, bb_u1, bb_u2, bb_l1, bb_l2):
    if price >= bb_u2:
        return "非常に割高（+2σ以上）", "🔥", 3
    elif price >= bb_u1:
        return "やや割高（+1σ以上）", "📈", 2
    elif price <= bb_l2:
        return "過度な売られすぎ（-2σ以下）", "🧊", 3
    elif price <= bb_l1:
        return "やや売られ気味（-1σ以下）", "📉", 2
    else:
        return "平均圏（±1σ内）", "⚪️", 1


# ============================================================
# 高値スコア・安値スコア（裁量買い評価）
# ============================================================
def is_high_price_zone(price, ma25, ma50, bb_u1, rsi, per, pbr, high):
    score = 0
    if price <= ma25 * 1.10 and price <= ma50 * 1.10:
        score += 20
    if price <= bb_u1:
        score += 20
    if rsi < 70:
        score += 15
    if per is not None and per < 20:
        score += 15
    if pbr is not None and pbr < 2.0:
        score += 15
    if high and price < high * 0.95:
        score += 15
    return score


def is_low_price_zone(price, ma25, ma50, bb_l1, bb_l2, rsi, per, pbr, low):
    score = 0
    if price < ma25 * 0.90 and price < ma50 * 0.90:
        score += 20
    if price < bb_l1:
        score += 15
    if price < bb_l2:
        score += 20
    if rsi < 30:
        score += 15
    if per is not None and per < 10:
        score += 15
    if pbr is not None and pbr < 1.0:
        score += 15
    if low and price <= low * 1.05:
        score += 15
    return score


# ============================================================
# 裁量買い表示の4段階
# ============================================================
def grade_comment(cnt):
    if cnt == 3:
        return "買い候補として非常に魅力的です。"
    if cnt == 2:
        return "買い検討の余地があります。"
    if cnt == 1:
        return "慎重に検討すべき状況です。"
    return "現時点では見送りが妥当です。"


# ============================================================
# ▼▼ メイン処理 ▼▼
# ============================================================

ticker_input = st.text_input("ティッカー（例: AAPL / 7203 / 8306.T）", "")

if not ticker_input:
    st.stop()

ticker = convert_ticker(ticker_input)

# ---------- info ----------
info = get_info_cached(ticker)

exchange = get_exchange(info, ticker)
st.write(f"🕒 市場状態：**{exchange}（{market_state(exchange)}）**")

# ---------- price ----------
df = get_price_cached(ticker)
if df.empty:
    st.error("株価データが取得できません")
    st.stop()

close_col = [c for c in df.columns if "Close" in c][0]

# MA / BB
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
yest = float(df[close_col].iloc[-2]) if len(df) >= 2 else price

ma25 = last["25MA"]
ma50 = last["50MA"]
ma75 = last["75MA"]
rsi = last["RSI"]
bb_u1 = last["BB_u1"]
bb_u2 = last["BB_u2"]
bb_l1 = last["BB_l1"]
bb_l2 = last["BB_l2"]

high52 = info.get("fiftyTwoWeekHigh")
low52 = info.get("fiftyTwoWeekLow")

# ---------- 日本株ファンダメ ----------
name_jp, sector_jp, per_jp, pbr_jp, div_jp = fetch_japan_fundamentals(ticker)

# 名称決定（yfinance → Yahoo）
name_display = name_jp or info.get("longName") or info.get("shortName") or ticker


# ===========================
# 📌 ヘッダー表示
# ===========================
st.markdown(f"### 📌 {ticker} / {name_display}")

# 業種
st.markdown(f"🏭 **業種**: {sector_jp or 'N/A'}")

# 配当・PER・PBR
st.markdown(
    f"💰 **配当利回り**: {fmt(div_jp)}%｜"
    f"📐 **PER**: {fmt(per_jp)}｜"
    f"🧮 **PBR**: {fmt(pbr_jp)}"
)

# 価格
color = "green" if price > yest else "red" if price < yest else "white"
st.markdown(
    f"📊 **現値**: <span style='color:{color};font-weight:bold;'>{fmt(price)}</span>"
    f"（前日終値: {fmt(yest)}）｜"
    f"25MA: {fmt(ma25)}｜50MA: {fmt(ma50)}｜75MA: {fmt(ma75)}",
    unsafe_allow_html=True,
)

# RSI/BB
bb_text, bb_icon, bb_strength = judge_bb_signal(price, bb_u1, bb_u2, bb_l1, bb_l2)
st.markdown(f"📈 **RSI**: {fmt(rsi)}｜🧪 **BB判定(20日)**: {bb_icon} {bb_text}")


# ============================================================
# 📌 押し目シグナル
# ============================================================
st.subheader("🎯 押し目シグナル（短期判定）")

signal_text, signal_icon, signal_strength = judge_signal(
    price, ma25, ma50, ma75, bb_l1, bb_u1, bb_l2, rsi, per_jp, pbr_jp, high52, low52
)

st.markdown(f"{signal_icon} **{signal_text}**")


# ============================================================
# ▼▼ 順張り or 逆張りの分岐判定 ▼▼
# ============================================================
is_mid_uptrend = ma25 > ma50 and ma25 > ma75
is_mid_downtrend = ma75 > ma50 and ma50 > ma25

ma25_slope = (df["25MA"].iloc[-1] - df["25MA"].iloc[-5]) / df["25MA"].iloc[-5] * 100

high_score = is_high_price_zone(price, ma25, ma50, bb_u1, rsi, per_jp, pbr_jp, high52)
low_score = is_low_price_zone(price, ma25, ma50, bb_l1, bb_l2, rsi, per_jp, pbr_jp, low52)


# ============================================================
# 📈 順張りテーブル（上昇トレンド時）
# ============================================================
if is_mid_uptrend:

    trend_ok = 0
    if abs((ma25 - ma50) / ma50) <= 0.03 and abs((ma50 - ma75) / ma75) <= 0.03:
        trend_ok += 1
        trend_mark = "◯"
    else:
        trend_mark = "×"

    if 0 <= ma25_slope <= 0.3:
        slope_mark = "◯"
        trend_ok += 1
    else:
        slope_mark = "×"

    score_text = f"{high_score}点"
    if high_score >= 60:
        score_mark = "◯"
        trend_ok += 1
    else:
        score_mark = "×"

    comment = grade_comment(trend_ok)

    center = (ma25 + ma50) / 2
    upper = center * 1.03
    lower = max(center * 0.95, bb_l1)

    st.markdown("""
    <div style="margin-top:3em;font-size:24px;font-weight:bold;">📈 &lt;順張り&gt; 裁量買いの検討</div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <table>
        <tr><th>項目</th><th>内容</th><th>判定</th></tr>
        <tr><td>中期トレンド</td><td>25MA ≧ 50MA ≧ 75MA（上昇または横ばい）</td><td>{trend_mark}</td></tr>
        <tr><td>短期傾向</td><td>25MA傾きが過去5日で +0〜0.3%</td><td>{slope_mark}</td></tr>
        <tr><td>割高否定スコア</td><td>60点以上で押し目</td><td>{score_mark}（{score_text}）</td></tr>
        <tr><td>中心価格</td><td>25MAと50MAの平均</td><td>{fmt(center)}</td></tr>
        <tr><td>上側許容幅</td><td>中心価格 × 1.03</td><td>{fmt(upper)}</td></tr>
        <tr><td>下側許容幅</td><td>中心価格 × 0.95 または BB-1σ</td><td>{fmt(lower)}</td></tr>
        <tr><td>総合判定</td><td>順張り裁量評価</td><td><strong>{comment}</strong></td></tr>
    </table>
    """, unsafe_allow_html=True)


# ============================================================
# 🧮 逆張りテーブル（下降トレンド時）
# ============================================================
elif is_mid_downtrend:

    trend_ok = 0
    if abs((ma75 - ma50) / ma50) <= 0.03 and abs((ma50 - ma25) / ma25) <= 0.03:
        tmark = "◯"
        trend_ok += 1
    else:
        tmark = "×"

    if ma25_slope < 0:
        smark = "◯"
        trend_ok += 1
    else:
        smark = "×"

    score_text = f"{low_score}点"
    if low_score >= 60:
        score_mark = "◯"
        trend_ok += 1
    else:
        score_mark = "×"

    comment = grade_comment(trend_ok)

    center = (ma25 + bb_l1) / 2
    upper = center * 1.08
    lower = center * 0.97

    st.markdown("""
    <div style="margin-top:3em;font-size:24px;font-weight:bold;">🧮 &lt;逆張り&gt; 裁量買いの検討</div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <table>
        <tr><th>項目</th><th>内容</th><th>判定</th></tr>
        <tr><td>中期トレンド</td><td>75MA ≧ 50MA ≧ 25MA（下降または横ばい）</td><td>{tmark}</td></tr>
        <tr><td>短期傾向</td><td>25MA傾きが過去5日でマイナス</td><td>{smark}</td></tr>
        <tr><td>割安圏判定</td><td>60点以上で割安</td><td>{score_mark}（{score_text}）</td></tr>
        <tr><td>中心価格</td><td>25MAとBB-1σの平均</td><td>{fmt(center)}</td></tr>
        <tr><td>上側許容幅</td><td>中心価格 × 1.08</td><td>{fmt(upper)}</td></tr>
        <tr><td>下側許容幅</td><td>中心価格 × 0.97</td><td>{fmt(lower)}</td></tr>
        <tr><td>総合評価</td><td>逆張り裁量評価</td><td><strong>{comment}</strong></td></tr>
    </table>
    """, unsafe_allow_html=True)


# ============================================================
# トレンド中立（どちらでもない）
# ============================================================
else:
    st.info("上昇トレンド/下降トレンドのいずれでもありません。")
