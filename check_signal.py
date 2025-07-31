import streamlit as st
import yfinance as yf
import pandas as pd
import math

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
ticker_list = [ticker] if ticker else []


# 🏷️ 英語→日本語 銘柄名マップ
name_map = {
    "TOYOTA MOTOR CORP": "トヨタ自動車",
    "MITSUBISHI UFJ FINANCIAL GROUP": "三菱UFJフィナンシャル・グループ",
    "SONY GROUP CORP": "ソニーグループ",
    "KDDI CORP": "KDDI",
    "NTT INC": "NTT",
    "SUMITOMO CHEMICAL COMPANY":"住友化学",
    "TOKYU FUDOSAN HOLDINGS CORPORAT":"東急不動産",
    "WATTS CO LTD":"ワッツ",
    "TOKYO METRO CO LTD":"東京メトロ",
    "SOFTBANK CORP.":"ソフトバンク",
    "HAZAMA ANDO CORP":"安藤ハザマ",
    "INPEX CORPORATION":"インペックス",
    "MITSUBISHI HC CAPITAL INC":"三菱HCキャピタル",
    "KYUSHU ELECTRIC POWER CO INC":"九州電力",
    "KIKKOMAN CORP":"キッコーマン",
    "MATSUI SECURITIES CO":"松井証券",
    "ASTELLAS PHARMA":"アステラス製薬",
    "SANSHA ELECTRIC MANUFACTURING":"三社電機製作所",
    "NIPPON GEAR CO LTD":"日ギア工業",
    "ONAMBA CO LTD":"オーナンバ",
    "MORITO CO LTD":"モリト",
    "MITSUBISHI CHEMICAL GROUP CORP":"三菱化学グループ",
    "NIPPON SIGNAL CO":"日信号",
    "CREATE MEDIC CO":"クリエート",
    "JAPAN FOUNDATION ENGINEERING CO":"日基礎",
    # 必要に応じて追加
}

# 🎯 ボリンジャーバンド判定関数
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

# 🎯 押し目＆RSIによるシグナル判定
def judge_signal(price, ma25, ma75, rsi, bb_lower1):
    if rsi is None:
        return "RSI不明", "⚪️", 0
    if price <= ma75 and rsi < 40 and price <= bb_lower1:
        return "バーゲン（強い押し目）", "🔴", 3
    elif (price <= ma75 and price < bb_lower1) or (rsi < 30 and price < bb_lower1):
        return "そこそこ押し目", "🟠", 2
    elif price < ma25 * 0.97 and rsi < 37.5 and price <= bb_lower1:
        return "軽い押し目", "🟡", 1
    else:
        return "シグナルなし", "🟢", 0

# 🧭 ティッカーから取引所を判別
def get_exchange_name(ticker: str) -> str:
    if ticker.endswith(".T") or ticker.isdigit():
        return "東証"
    info = yf.Ticker(ticker).info
    exchange = info.get("exchange", "").upper()
    if exchange == "NASDAQ":
        return "NASDAQ"
    elif exchange == "NYSE":
        return "NYSE"
    else:
        return "その他"

# ⏰ 日付をまたぐ時間帯にも対応した営業判定関数
def is_market_open(now, open_time, close_time):
    if open_time < close_time:
        return open_time <= now <= close_time
    else:
        return now >= open_time or now <= close_time

# 🧭 市場状態の表示テキスト生成
from datetime import datetime, time
import pytz

def get_market_status(exchange: str, state: str) -> str:
    now_jst = datetime.now(pytz.timezone("Asia/Tokyo")).time()
    status_map = {
        "NASDAQ": ("NASDAQ", time(22,30), time(5,0)),
        "NYSE":   ("NYSE",   time(22,30), time(5,0)),
        "東証":   ("東証",   time(9,0),   time(15,0))
    }
    label, open_time, close_time = status_map.get(exchange, ("不明", None, None))

    if state == "CLOSED" and open_time and close_time:
        if is_market_open(now_jst, open_time, close_time):
            return f"{label} 営業時間内（marketState=取得不可）"
        else:
            return f"{label} 閉場中"

    state_translation = {
        "REGULAR": "通常取引中",
        "PRE": "プレマーケット",
        "POST": "アフターマーケット",
        "CLOSED": "閉場中",
        "UNKNOWN": "不明"
    }
    return f"{label} {state_translation.get(state, '不明')}"

# 市場情報取得
first_ticker = yf.Ticker(ticker)
exchange_name = get_exchange_name(ticker)
market_state = first_ticker.info.get("marketState", "UNKNOWN")
market_state_jp = get_market_status(exchange_name, market_state)

# Streamlit表示
st.write(f"🕒 現在の市場状態：**{market_state_jp}**")


# 🔁 メインロジック（単一ティッカー対応）
for code in ticker_list:
    try:
        ticker_obj = yf.Ticker(code)
        info = ticker_obj.info

        # ⛳ 日本語名対応
        name_raw = info.get("shortName", "")
        name = name_map.get(name_raw.upper(), name_raw)
        industry = info.get("industry", "業種不明")
        div_yield = info.get("dividendYield", None)
        per = info.get("trailingPE", None)
        price = info.get("regularMarketPrice", None)

        div_text = f"{div_yield:.2f}%" if div_yield else "—"
        per_text = f"{per:.2f}" if per else "—"

        # 🕒 市場状態によって価格を選択
        market_state = info.get("marketState", "UNKNOWN")
        market_price = info.get("regularMarketPrice", None)
        close_price = info.get("previousClose", None)

        if market_price is not None and market_price != close_price:
            price = market_price
            price_label = "現在価格"
        elif close_price is not None:
            price = close_price
            price_label = "終値"
        else:
            price = None
            price_label = "価格未取得"

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
        ma75 = float(last["75MA"])
        rsi = float(last["RSI"])

        signal_text, signal_icon, signal_strength = judge_signal(close, ma25, ma75, rsi, last["BB_-1σ"])

      # ✅ 表示部分（重複なし）
        st.markdown(f"---\n### 💡 {code} - {name}")
        st.markdown(f"**🏭 業種**: {industry}")
        st.markdown(f"**💰 配当利回り**: {div_text}｜**📈 PER**: {per_text}")
        st.write(f"📊 終値: {close:.2f}｜25MA: {ma25:.2f}｜75MA: {ma75:.2f}｜RSI: {rsi:.1f}")
        bb_signal_text, bb_icon, bb_strength = judge_bb_signal(close, last["BB_+1σ"], last["BB_+2σ"],last["BB_-1σ"], last["BB_-2σ"])
        st.markdown(f"**📏 BB判定(20日)**: {bb_icon} {bb_signal_text}")
        st.markdown(f"### {signal_icon} {signal_text}")
        st.progress(signal_strength / 3)

    except Exception as e:
        st.error(f"{code}: 処理中にエラーが発生しました（{e}）")
