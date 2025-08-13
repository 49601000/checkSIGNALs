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

# 🎯<順張り> 押し目＆RSIによる高値圏シグナル判定
def is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w):
    if None in [price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w]:
        return 0 # データ不足で判定不可
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
    return highprice_score   # 割高圏スコア

# 🎯<逆張り> 押し目＆割安圏シグナル判定
def is_low_price_zone(price, ma25, ma50, bb_lower1, bb_lower2, rsi, per, pbr, low_52w):
    if None in [price, ma25, ma50, bb_lower1, bb_lower2, rsi, per, pbr, low_52w]:
        return 0  # データ不足で判定不可
    lowprice_score = 0
    # 株価が25MAおよび50MAより−10%以上
    if price < ma25 * 0.90 and price < ma50 * 0.90:
        lowprice_score += 20
    # 株価がBB−1σ以下
    if price < bb_lower1:
        lowprice_score += 15
    # 株価がBB−2σ以下
    if price < bb_lower2:
        lowprice_score += 20
    # RSIが30未満（売られすぎ）
    if rsi < 30:
        lowprice_score += 15
    # PERが10未満（割安）
    if per and per < 10:
        lowprice_score += 15
    # PBRが1.0未満（資産割安）
    if pbr and pbr < 1.0:
        lowprice_score += 15
    # 株価が52週安値圏の105%以上（底値圏）
    if price <= low_52w * 1.05:
        lowprice_score += 15
    return lowprice_score         # 割安圏スコア
    #return lowprice_score >= 60  # 割安圏スコア


# 🎯 押し目＆RSIによるシグナル判定
def judge_signal(price, ma25, ma50, ma75, bb_lower1, bb_upper1, bb_lower2, rsi, per, pbr, dividend_yield, high_52w,low_52w):
    if rsi is None:
        return "RSI不明", "⚪️", 0
    if price <= ma75 and rsi < 40 and price<=bb_lower1:
        return "バーゲン（強い押し目）", "🔴", 3
    elif (price <= ma75 and price < bb_lower1) or (rsi < 30 and price < bb_lower1):
        return "そこそこ押し目", "🟠", 2
    elif price < ma25 * 0.97 and rsi < 37.5 and price<=bb_lower1:
        return "軽い押し目", "🟡", 1
    elif is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w)>= 60:
        return "高値圏（要注意！）", "🔥", 0
    else:
        return "シグナルなし", "🟢", 0

#🎯 順張り裁量枠購入可能条件の作成
def calc_discretionary_buy_range(df, ma25, ma50, ma75, bb_lower, highprice_score):
    # ① 中期トレンド判定
    is_mid_uptrend = ma75 < ma50 < ma25
    # ② 短期傾向（25MAの傾き）
    ma25_slope = (df['25MA'].iloc[-1] - df['25MA'].iloc[-5]) / df['25MA'].iloc[-5] * 100
    is_flat_uptrend = abs(ma25_slope) <= 0.3 and ma25_slope >= 0
    # ③ 割高スコアが60点以下（押し目）
    is_pullback = highprice_score <= 60
    # 条件をすべて満たすか判定
    if not (is_mid_uptrend and is_flat_uptrend and is_pullback):
        return None
    # 中心価格
    center_price = (ma25 + ma50) / 2
    # 上限・下限計算
    upper_price = center_price * 1.03
    lower_price = max(center_price * 0.95, bb_lower)
    return {"lower_price": round(lower_price, 2),"upper_price": round(upper_price, 2),"center_price": round(center_price, 2)}


# 横ばい判定関数（±3%以内）
def is_flat_ma(ma25, ma50, ma75, tolerance=0.03):
    ma_values = [ma25, ma50, ma75]
    ma_max = max(ma_values)
    ma_min = min(ma_values)
    return (ma_max - ma_min) / ma_max <= tolerance

# 🎯 売られすぎスコア連動型：逆張り裁量枠購入可能レンジ
def calc_discretionary_buy_range_contrarian(df, params):
    ma25 = params["ma25"]
    ma50 = params["ma50"]
    ma75 = params["ma75"]
    bb_lower1 = params["bb_lower1"]
    bb_lower2 = params["bb_lower2"]
    rsi = params["rsi"]
    price = params["price"]
    per = params["per"]
    pbr = params["pbr"]
    dividend_yield = params["dividend_yield"]
    low_52w = params["low_52w"]

    # トレンド条件：下降または横ばい（±3%以内）
    is_downtrend = ma75 > ma50 > ma25
    is_flattrend = is_flat_ma(ma25, ma50, ma75, tolerance=0.03)
    if not (is_downtrend or is_flattrend):
        return None

    # 25MAの傾きがマイナス（短期は下落傾向）
    ma25_slope = (df['25MA'].iloc[-1] - df['25MA'].iloc[-5]) / df['25MA'].iloc[-5] * 100
    if ma25_slope >= 0:
        return None

    # 売られすぎスコア判定（割安圏）
    if not is_low_price_zone(price, ma25, ma50, bb_lower1, bb_lower2, rsi, per, pbr, low_52w):
        return None

    # 中心価格：25MAとBB−1σの平均
    center_price = (ma25 + bb_lower1) / 2
    upper_price = center_price * 1.08
    lower_price = center_price * 0.97

    # ファンダメンタル補正
    fundamentals = ""
    if pbr is not None and pbr < 1.0:
        fundamentals += "PBR割安 "
    if dividend_yield is not None and dividend_yield > 3.0:
        fundamentals += "高配当 "

    return {
        "lower_price": round(lower_price, 2),
        "upper_price": round(upper_price, 2),
        "center_price": round(center_price, 2),
        "fundamentals": fundamentals.strip() if fundamentals else None
    }

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
        dividend_yield = info.get("dividendYield", None)
        per = info.get("trailingPE", None)
        pbr = info.get("priceToBook",None)
        price = info.get("regularMarketPrice", None)
        high_52w = info.get("fiftyTwoWeekHigh", None)
        low_52w = info.get("fiftyTwoWeekLow", None)


        div_text = f"{dividend_yield:.2f}%" if dividend_yield else "—"
        per_text = f"{per:.2f}" if per else "—"
        pbr_text = f"{pbr:.2f}" if pbr else "—"
        
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
        ma25_slope = (df['25MA'].iloc[-1] - df['25MA'].iloc[-5]) / df['25MA'].iloc[-5] * 100
        slope_ok = ma25_slope < 0
        
        
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
        
        # 🎯 シグナル判定（押し目 or 高値圏など）
        signal_text, signal_icon, signal_strength = judge_signal(**params)
        
        # 🎯 順張りスコア（割高度）
        highprice_score = is_high_price_zone(close, ma25, ma50, last["BB_+1σ"], rsi, per, pbr, high_52w)
        
        # 📊 テクニカル指標をまとめる
        params = {
            "price": close,
            "ma25": ma25,
            "ma50": ma50,
            "ma75": ma75,
            "rsi": rsi,
            "bb_lower1": last["BB_-1σ"],
            "bb_lower2": last["BB_-2σ"],
            "bb_upper1": last["BB_+1σ"],
            "per": per,
            "pbr": pbr,
            "dividend_yield":dividend_yield,    
            "high_52w": high_52w,
            "low_52w": low_52w,
            "highprice_score":highprice_score,
        }
        
        # 📊 テクニカル指標をまとめる
        bb_lower1 = params["bb_lower1"]
        bb_lower2 = params["bb_lower2"]
        bb_upper1 = params["bb_upper1"]
        
        # 🎯 順張り裁量レンジ（条件を満たす場合のみ）
        buy_range_trend = calc_discretionary_buy_range(df_valid, params["ma25"], params["ma50"], params["ma75"], params["bb_lower1"], params["highprice_score"])




        # 判定ロジック
        lowprice_score = is_low_price_zone(price, ma25, ma50, bb_lower1, bb_lower2, rsi, per, pbr, low_52w)
        score_text = f"{lowprice_score}点"

        # 逆張り判定
        buy_range_contrarian = calc_discretionary_buy_range_contrarian(df_valid, params)
        
        # ✅ テーブルの表示判定ロジック（順張り or not)
        is_mid_uptrend = ma25 > ma50 and ma25 > ma75

        # 安全な数値整形関数    
        def safe_format(value, digits=2):
            return f"{value:.{digits}f}" if isinstance(value, (int, float)) else "—"
        
        # 順張りレンジ
        if buy_range_trend:
            trend_range = (buy_range_trend["lower_price"], buy_range_trend["upper_price"])
            trend_center = buy_range_trend["center_price"]
            trend_upper = buy_range_trend["upper_price"]
            trend_lower = buy_range_trend["lower_price"]
        else:
            trend_center = trend_upper = trend_lower = None

        # 逆張りレンジ
        if buy_range_contrarian:
            contrarian_range = (buy_range_contrarian["lower_price"], buy_range_contrarian["upper_price"])
            contrarian_center = buy_range_contrarian["center_price"]
            contrarian_upper = buy_range_contrarian["upper_price"]
            contrarian_lower = buy_range_contrarian["lower_price"]
        else:
            contrarian_center = contrarian_upper = contrarian_lower = None

            
        # ✅ 表示用整形
        trend_center_text = safe_format(trend_center)
        trend_upper_text = safe_format(trend_upper)
        trend_lower_text = safe_format(trend_lower)
        trend_range_text = f"{trend_lower_text} ～ {trend_upper_text}" if trend_center else "—"

        contrarian_center_text = safe_format(contrarian_center)
        contrarian_upper_text = safe_format(contrarian_upper)
        contrarian_lower_text = safe_format(contrarian_lower)
        contrarian_range_text = f"{contrarian_lower_text} ～ {contrarian_upper_text}" if contrarian_center else "—"

   
        # ✅ 表示部分（重複なし）
        st.markdown(f"---\n### 💡 {code} - {name}")
        st.markdown(f"**🏭 業種**: {industry}")
        st.markdown(f"**💰 配当利回り**: {div_text}｜**📐 PER**: {per_text}｜**🧮 PBR**: {pbr_text}")
        # 色の判定（高い→赤、安い→緑、変わらず→黒）
        if close > close_price:
            color = "red"
        elif close < close_price:
            color = "green"
        else:
            color = "black"
        st.markdown(
            f"📊 {price_label}: <span style='color:{color}; font-weight:bold;'>{close:.2f}</span>（前日終値: {close_price:.2f}）｜25MA: {ma25:.2f}｜50MA: {ma50:.2f}｜75MA: {ma75:.2f}</span>",
            unsafe_allow_html=True)
        bb_signal_text, bb_icon, bb_strength = judge_bb_signal(close, last["BB_+1σ"], last["BB_+2σ"],last["BB_-1σ"], last["BB_-2σ"])
        st.markdown(f"**📊 RSI**: {rsi:.1f}｜**📏 BB判定(20日)**: {bb_signal_text}")
        st.markdown(f"### {signal_icon} {signal_text}")
        st.progress(signal_strength / 3)

        #順張り裁量判定
        if buy_range_trend:
            buy_range_type = "順張り"
            print(f"🎯 {buy_range_type}裁量買いレンジ: {buy_range_trend['lower_price']} ～ {buy_range_trend['upper_price']}")
            trend_judge = "裁量買いOK"
        else:
            print("❌ 裁量買いレンジなし（条件未達）")
            trend_judge = "裁量買いNG"
        # 逆張り裁量判定
        if buy_range_contrarian:
            buy_range_type = "逆張り"
            print(f"🎯 {buy_range_type}裁量買いレンジ: {buy_range_contrarian['lower_price']} ～ {buy_range_contrarian['upper_price']}")
            contrarian_judge = "裁量買いOK"
        else:
            print("❌ 裁量買いレンジなし（条件未達）")
            contrarian_judge = "裁量買いNG"

        # 中心価格：25MAとBB−1σの平均
        if isinstance(ma25, (int, float)) and isinstance(bb_lower1, (int, float)): 
            center_price_val = (ma25 + bb_lower1) / 2
        else:
            center_price_val = None

        # 許容幅の計算
        upper_bound_val = center_price_val * 1.08 if center_price_val else None
        lower_bound_val = center_price_val * 0.97 if center_price_val else None
        upper_bound_val2 = center_price_val * 1.05 if center_price_val else None
        lower_bound_val2 = center_price_val * 0.95 if center_price_val else None

        # last が None でないことを確認し、キーがあるかも確認
        if "BB_-1σ" in last and last["BB_-1σ"] is not None:
            bb_adjusted = last["BB_-1σ"] if "BB_-1σ" in last and last["BB_-1σ"] is not None else None
            bb_adjusted_text = safe_format(bb_adjusted)
        else:
            bb_adjusted = "—"


        # 1. 順張りロジックの判定（このブロック）
        is_uptrend = ma75 < ma50 < ma25
        ma25_slope = (df["25MA"].iloc[-1] - df["25MA"].iloc[-5]) / df["25MA"].iloc[-5] * 100
        is_flat_or_gentle_up = abs(ma25_slope) <= 0.3 and ma25_slope >= 0
        trend_ok = is_uptrend and is_flat_or_gentle_up
        trend_mark = "○" if is_uptrend else "×"
        slope_mark = "○" if is_flat_or_gentle_up else "×"

        # 2. 高値圏スコア判定（←ここに入れる！）
        highprice_score = is_high_price_zone(price, ma25, ma50, bb_upper1, rsi, per, pbr, high_52w)
        high_score_text = f"{highprice_score}点"
        high_score_ok = highprice_score >= 60
        high_score_mark = "○" if high_score_ok else "×"

        # 3. 表示用の数値変換
        center_price_text = safe_format(center_price_val)
        upper_bound_text = safe_format(upper_bound_val)
        lower_bound_text = safe_format(lower_bound_val)
        upper_bound_text2 = safe_format(upper_bound_val2)
        if lower_bound_val2 is not None:
            lower_bound_text2 = safe_format(max(bb_lower1, lower_bound_val2))
        else:
            lower_bound_text2 = safe_format(bb_lower1)
        bb_adjusted_text = safe_format(bb_adjusted)
        range_text = f"{lower_bound_text} ～ {upper_bound_text}"
        
        if is_mid_uptrend:
            # 4. 順張りテーブルの表示
            st.markdown(f"""
            <div style="margin-top:2em; font-size:16px; font-weight:bold;">📈 <順張り>裁量買いレンジのロジック</div>
            <table>
                <tr><th align="left">項目</th><th align="left">内容</th><th align="left">判定</th></tr>
                <tr><td>中期トレンド</td><td>75MA &gt; 50MA &gt; 25MA</td><td>{trend_mark}</td></tr>
                <tr><td>短期傾向</td><td>25MAの傾きが過去5日で ±0.3%以内（横ばい〜緩やかな上昇）</td><td>{slope_mark}</td></tr>
                <tr><td>順張り押し目判定</td><td>ブルスコアが60点以下で「押し目」と判定（ブルスコアは RSI・PER・PBR・BB・52週高値などを加点評価／スコアが高いほど割高傾向）</td><td>{high_score_text}</td></tr>
                <tr><td>中心価格</td><td>25MAと50MAの平均</td><td>{center_price_text}</td></tr>
                <tr><td>上側許容幅</td><td>中心価格×1.03</td><td>{upper_bound_text2}</td></tr>
                <tr><td>下側許容幅</td><td>中心価格×0.95 または BB−1σの高い方</td><td>{lower_bound_text2}</td></tr>
                <tr><td>BB調整下限</td><td>BB−1σ</td><td>{bb_adjusted_text}</td></tr>
                <tr><td>判定</td><td>上記の組み合わせによる判定</td><td><strong>{trend_judge}</strong></td></tr>
            </table>""", unsafe_allow_html=True)
        
        else:
             # 逆張りロジック表示
            is_downtrend = ma75 > ma50 > ma25
            is_flattrend = is_flat_ma(ma25, ma50, ma75, tolerance=0.03)
            trend_ok = is_downtrend or is_flattrend
            trend_mark = "○" if trend_ok else "×"
            slope_mark = "○" if slope_ok else "×"
    
            st.markdown(f"""
            <div style="margin-top:2em; font-size:16px; font-weight:bold;">🧮 <逆張り>裁量買いレンジのロジック</div>
            <table>
                <tr><th align="left">項目</th><th align="left">内容</th><th align="left">判定</th></tr>
                <tr><td>中期トレンド</td><td>75MA(±3%) ≧ 50MA(±3%) ≧ 25MA(±3%)（下降または横ばい）</td><td>{trend_mark}</td></tr>
                <tr><td>短期傾向</td><td>25MAの傾きが過去5日でマイナス（下落傾向）</td><td>{slope_mark}</td></tr>
                <tr><td>割安圏判定</td><td>ベアスコアが60点以上で「割安」と判定（RSI・PER・PBR・BB・52週安値などを加点評価／スコアが高いほど割安傾向）</td><td>{score_text}</td></tr>
                <tr><td>中心価格</td><td>25MAとBB−1σの平均</td><td>{center_price_text}</td></tr>
                <tr><td>上側許容幅</td><td>中心価格×1.08</td><td>{upper_bound_text}</td></tr>
                <tr><td>下側許容幅</td><td>中心価格×0.97</td><td>{lower_bound_text}</td></tr>
                <tr><td>判定</td><td>上記の組み合わせによる判定</td><td><strong>{contrarian_judge}</strong></td></tr>
            </table>""", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"{code}: 処理中にエラーが発生しました（{e}）")
