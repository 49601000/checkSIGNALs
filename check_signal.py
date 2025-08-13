import streamlit as st
import yfinance as yf
import pandas as pd
import math
from datetime import datetime, time
import pytz

st.set_page_config(page_title="✅任意銘柄の買いシグナルをチェック", page_icon="📊")
st.title("🔍買いシグナルチェッカー")

# 🟦 ユーザーがティッカーを入力
user_input = st.text_input("ティッカーシンボルを入力してください（例: AAPL, 7203, MSFT, 8306.T など）", value="")

def convert_ticker(ticker):
    ticker = ticker.strip().upper()
    if ticker.endswith('.T') or not ticker.isdigit():
        return ticker
    return ticker + ".T"

ticker = convert_ticker(user_input)
if not ticker:
    st.warning("ティッカーを入力してください。")
    st.stop()

ticker_list = [ticker]

# 🏷️ 英語→日本語 銘柄名マップ（略）
name_map = {
    "TOYOTA MOTOR CORP": "トヨタ自動車",
    "MITSUBISHI UFJ FINANCIAL GROUP": "三菱UFJフィナンシャル・グループ",
    "SONY GROUP CORP": "ソニーグループ",
    # 必要に応じて追加
}

# 🏷️ 市場の略称の統一化
def normalize_exchange(exchange_code: str) -> str:
    mapping = {
        "NMS": "NASDAQ",
        "NAS": "NASDAQ",
        "NASDAQ": "NASDAQ",
        "NYQ": "NYSE",
        "NYA": "NYSE",
        "NYSE": "NYSE",
        "TSE": "東証",
        "JPX": "東証",
        "東証": "東証"
    }
    return mapping.get(exchange_code.upper(), "不明")


# 🎯 ボリンジャーバンド判定関数の定義
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

# 🎯 押し目＆RSIによる高値圏シグナル判定
def is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w):
    if None in [price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w]:
        return False  # データ不足で判定不可
    highprice_score = 0
    #株価が25日および50日移動平均よりも＋10%超
    if price > ma25 * 1.10 and price > ma50 * 1.10:
        highprice_score += 20
    #株価がボリンジャーバンド1δ以上
    if price > bb_upper1:
        highprice_score += 20
    #RSI（14日）が70以上
    if rsi >= 70:
        highprice_score += 15
    #PERが20以上
    if per and per >= 20:
        highprice_score += 15
    #PBRが2.0以上
    if pbr and pbr >= 2.0:
        highprice_score += 15
    #株価52週高値圏の95％以上       
    if price >= high_52w * 0.95:
        highprice_score += 15
    return highprice_score >= 60  # 高値圏シグナル

# 🎯 押し目＆RSIによるシグナル判定
def judge_signal(price, ma25, ma50, ma75, bb_lower1, bb_upper1, rsi, per, pbr, high_52w):
    if rsi is None:
        return "RSI不明", "⚪️", 0
    if price <= ma75 and rsi < 40 and price<=bb_lower1:
        return "バーゲン（強い押し目）", "🔴", 3
    elif (price <= ma75 and price < bb_lower1) or (rsi < 30 and price < bb_lower1):
        return "そこそこ押し目", "🟠", 2
    elif price < ma25 * 0.97 and rsi < 37.5 and price<=bb_lower1:
        return "軽い押し目", "🟡", 1
    elif is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w):
        return "高値圏（要注意！）", "🔥", 0
    else:
        return "シグナルなし", "🟢", 0

# 🧭 ティッカーから取引所を判別
def get_exchange_name(ticker: str) -> str:
    if ticker.endswith(".T") or ticker.isdigit():
        return "東証"
    try:
        info = yf.Ticker(ticker).info
        exchange = info.get("exchange", "").upper()

        if exchange in ["NMS", "NAS", "NASDAQ"]:
            return "NASDAQ"
        elif exchange in ["NYQ", "NYA", "NYSE"]:
            return "NYSE"
        else:
            return "その他"
    except Exception:
        return "不明"
        
def is_market_open(now, open_time, close_time):
    if open_time < close_time:
        return open_time <= now <= close_time
    else:
        return now >= open_time or now <= close_time

# 🧭 市場状態の表示テキスト生成
def get_market_status(exchange: str, state: str, status_text: dict = None) -> str:
    exchange = normalize_exchange(exchange)
    now_jst = datetime.now(pytz.timezone("Asia/Tokyo")).time()
    status_map = {
        "NASDAQ": ("NASDAQ", time(22,30), time(5,0)),
        "NYSE":   ("NYSE",   time(22,30), time(5,0)),
        "東証":   ("東証",   time(9,0),   time(15,30))
    }

    label, open_time, close_time = status_map.get(exchange, ("不明", None, None))
    if not open_time or not close_time:
        return f"{label}: 不明"

    is_open = is_market_open(now_jst, open_time, close_time)

    # 引数で指定されたステータステキストがあれば上書き
    status_labels = status_text if status_text else default_status

    if state == "REGULAR":
        status = status_labels["OPEN"] if is_open else status_labels["CLOSED"]
    else:
        status = status_labels["HOLIDAY"]

    return f"{label}: {status}"
custom_labels = {
        "OPEN": "取引中",
        "CLOSED": "取引終了",
        "HOLIDAY": "休場中"
}

print(get_market_status("NASDAQ", "REGULAR", custom_labels))

# 市場情報取得
first_ticker = yf.Ticker(ticker)
exchange_name = get_exchange_name(ticker)
state_text = "REGULAR"  # または "HOLIDAY" など
market_state_jp = get_market_status(exchange_name, state_text, custom_labels)
st.write(f"🕒 現在の市場状態：**{market_state_jp}**")



# 🔁 メインロジック（単一ティッカー対応）
for code in ticker_list:
    try:
        ticker_obj = yf.Ticker(code)
        info = ticker_obj.info

        name_raw = info.get("shortName", "")
        name = name_map.get(name_raw.upper(), name_raw)
        industry = info.get("industry", "業種不明")
        div_yield = info.get("dividendYield", None)
        per = info.get("trailingPE", None)
        pbr = info.get("priceToBook",None)
        price = info.get("regularMarketPrice", None)
        high_52w = info.get("fiftyTwoWeekHigh", None)

        div_text = f"{div_yield:.2f}%" if div_yield else "—"
        per_text = f"{per:.2f}" if per else "—"
        pbr_text = f"{pbr:2f}" if pbr else "—"
        
        # 価格選択
        market_state = info.get("marketState", "UNKNOWN")
        market_price = info.get("regularMarketPrice", None)
        close_price = info.get("previousClose", None)
        close_price_label = "前日終値"
        price = market_price if market_price and market_price != close_price else close_price
        price_label = "現在価格" if market_price and market_price != close_price else "終値"

        df = yf.download(code, period="120d", interval="1d")
        if df.empty or pd.isna(price):
            st.warning(f"{code}: 株価データが取得できませんでした。")
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = ['_'.join(col).strip() for col in df.columns]

        close_col = next((col for col in df.columns if "Close" in col), None)
        if not close_col:
            st.warning(f"{code}: 'Close'列が見つかりません。列一覧: {df.columns.tolist()}")
            continue

        # 指標計算
        df["25MA"] = df[close_col].rolling(25).mean()
        df["50MA"] = df[close_col].rolling(50).mean()
        df["75MA"] = df[close_col].rolling(75).mean()
        df["20MA"] = df[close_col].rolling(window=20).mean()
        df["20STD"] = df[close_col].rolling(window=20).std()
        df["BB_+1σ"] = df["20MA"] + df["20STD"]
        df["BB_+2σ"] = df["20MA"] + 2 * df["20STD"]
        df["BB_-1σ"] = df["20MA"] - df["20STD"]
        df["BB_-2σ"] = df["20MA"] - 2 * df["20STD"]

        delta = df[close_col].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean().replace(0, 1e-10)
        rs = avg_gain / avg_loss
        df["RSI"] = 100 - (100 / (1 + rs))
        
        df_valid = df.dropna()
        if df_valid.empty:
            st.warning(f"{code}: 有効なテクニカル指標がありません。")
            continue

        last = df_valid.iloc[-1]
        close = float(last[close_col])
        ma25 = float(last["25MA"])
        ma50 = float(last["50MA"])
        ma75 = float(last["75MA"])
        rsi = float(last["RSI"])

        params = {
            "price": close,
            "ma25": ma25,
            "ma50": ma50,
            "ma75": ma75,
            "rsi": rsi,
            "bb_lower1": last["BB_-1σ"],
            "bb_upper1": last["BB_+1σ"],
            "per": per,
            "pbr": pbr,
            "high_52w": high_52w
        }
        signal_text, signal_icon, signal_strength = judge_signal(**params)

        # ✅ 表示部分（重複なし）
        st.markdown(f"---\n### 💡 {code} - {name}")
        st.markdown(f"**🏭 業種**: {industry}")
        st.markdown(f"**💰 配当利回り**: {div_text}｜**📐 PER**: {per_text} |**🧮 PBR**: {per_text}")
        # 色の判定（高い→赤、安い→緑、変わらず→黒）
        if close > close_price:
            color = "red"
        elif close < close_price:
            color = "green"
        else:
            color = "black"
        st.markdown(
            f"📊 {price_label}: <span style='color:{color}; font-weight:bold;'>{close:.2f}</span>（前日終値: {close_price:.2f}）｜25MA: {ma25:.2f}｜50MA: {ma50:.2f}｜75MA: {ma75:.2f}</span>",
            unsafe_allow_html=True
)

        bb_signal_text, bb_icon, bb_strength = judge_bb_signal(close, last["BB_+1σ"], last["BB_+2σ"],last["BB_-1σ"], last["BB_-2σ"])
        st.markdown(f"**📊 RSI**: {rsi:.1f}｜**📏 BB判定(20日)**: {bb_signal_text}")
        st.markdown(f"### {signal_icon} {signal_text}")
        st.progress(signal_strength / 3)

    except Exception as e:
        st.error(f"{code}: 処理中にエラーが発生しました（{e}）")
