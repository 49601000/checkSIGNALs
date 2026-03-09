"""
data_fetch.py  (v3)
────────────────────────────────────────────────────────────────────────────
【v3 追加取得項目】
  Q強化: 営業利益率 (operating_margin)、D/Eレシオ (de_ratio)、
         インタレスト・カバレッジ (interest_coverage)
  V強化: EV/EBITDA (ev_ebitda)

取得元:
  日本株 : IRBANK スクレイピング（既存） + yfinance 補完（新規項目）
  米国株 : Alpha Vantage OVERVIEW API + yfinance.info フォールバック
"""

from typing import Optional, Tuple, Dict
import re
from datetime import datetime, timedelta
import time

import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd
import streamlit as st

IRBANK_BASE = "https://irbank.net/"
ALPHA_BASE  = "https://www.alphavantage.co/query"
COMPANY_NAME_CACHE: Dict[str, str] = {}


# ─── Alpha Vantage APIキー ─────────────────────────────────────────────────

def _get_av_key() -> Optional[str]:
    try:
        return st.secrets.get("ALPHA_VANTAGE_API_KEY", None)
    except Exception:
        return None


# ─── ティッカー変換 ────────────────────────────────────────────────────────

def convert_ticker(raw: str) -> str:
    t = raw.strip().upper()
    if not t:
        return ""
    if t.endswith(".T"):
        return t
    if t.isdigit() and 4 <= len(t) <= 5:
        return t + ".T"
    return t


def is_jpx_ticker(ticker: str) -> bool:
    t = ticker.strip().upper()
    return t.endswith(".T") or (t.isdigit() and 4 <= len(t) <= 5)


# ─── 共通ユーティリティ ────────────────────────────────────────────────────

def _safe_float(x) -> Optional[float]:
    try:
        return None if x is None or x == "" else float(x)
    except Exception:
        return None


def _compute_dividend_yield(ticker_obj: yf.Ticker, close: float) -> Optional[float]:
    divs = ticker_obj.dividends
    if not isinstance(divs, pd.Series) or len(divs) == 0 or close <= 0:
        return None
    divs.index = pd.to_datetime(divs.index, errors="coerce")
    divs = divs.dropna()
    try:
        if getattr(divs.index, "tz", None) is not None:
            divs.index = divs.index.tz_localize(None)
    except Exception:
        pass
    one_year_ago = (datetime.now() - timedelta(days=365)).replace(tzinfo=None)
    last_year = divs[divs.index >= one_year_ago]
    if len(last_year) == 0:
        return None
    return float(last_year.sum() / close * 100.0)


def _clean_jpx_company_name(name: str) -> str:
    if not isinstance(name, str):
        return name
    for p in ["株価/株式情報", "株価・株式情報", "｜ 株式情報", "｜株式情報",
              "| 株式情報", "|株式情報", "株式情報"]:
        if p in name:
            name = name.split(p)[0]
    return name.strip(" 　-|｜")


def _safe_get_yf_info(ticker_obj) -> dict:
    try:
        info = ticker_obj.info
        return info if isinstance(info, dict) else {}
    except Exception:
        return {}
def _normalize_industry_text(val: str) -> str:
    if not isinstance(val, str):
        return ""
    return val.strip()


def _extract_industry_from_info(info: dict) -> str:
    """
    yfinance の揺れを吸収して業種っぽい文字列を返す。
    優先順位:
      1) industry
      2) industryDisp
      3) sector
      4) category
    """
    if not isinstance(info, dict):
        return ""

    candidates = [
        info.get("industry"),
        info.get("industryDisp"),
        info.get("sector"),
        info.get("category"),
    ]

    for v in candidates:
        s = _normalize_industry_text(v)
        if s:
            return s
    return ""
      

# ─── IRBANK スクレイピング（日本株） ─────────────────────────────────────

def get_jpx_fundamentals_irbank(code: str) -> dict:
    """
    Returns dict with keys:
        eps, bps, per_fwd, roe, roa, equity_ratio,
        operating_margin, interest_coverage
    ※ D/E レシオは IRBANK から直接取れないため yfinance で補完
    """
    url = f"{IRBANK_BASE}{code}"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": IRBANK_BASE}
    result = {k: None for k in [
        "eps", "bps", "per_fwd", "roe", "roa", "equity_ratio",
        "operating_margin", "interest_coverage"
    ]}

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception:
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    # 会社名キャッシュ
    try:
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            raw  = title_tag.string.strip().split("【")[0]
            name = _clean_jpx_company_name(raw)
            if name:
                COMPANY_NAME_CACHE[code]        = name
                COMPANY_NAME_CACHE[f"{code}.T"] = name
    except Exception:
        pass

    def extract_number_near(label: str) -> Optional[float]:
        node = soup.find(string=re.compile(re.escape(label)))
        if not node:
            return None
        cur = node
        for _ in range(8):
            if cur is None:
                break
            m = re.search(r"([\d,]+(?:\.\d+)?)", str(cur))
            if m:
                try:
                    return float(m.group(1).replace(",", ""))
                except ValueError:
                    return None
            cur = cur.find_next(string=True)
        return None

    result["eps"]          = (extract_number_near("EPS（連）") or extract_number_near("EPS（単）")
                               or extract_number_near("EPS"))
    result["bps"]          = (extract_number_near("BPS（連）") or extract_number_near("BPS（単）")
                               or extract_number_near("BPS"))
    result["per_fwd"]      = extract_number_near("PER予")
    result["roe"]          = extract_number_near("ROE（連）") or extract_number_near("ROE")
    result["roa"]          = extract_number_near("ROA（連）") or extract_number_near("ROA")
    result["equity_ratio"] = (extract_number_near("株主資本比率（連）")
                               or extract_number_near("株主資本比率"))
    # 営業利益率・インタレストカバレッジは IRBANK に掲載がないことが多い
    # → yfinance 補完に委ねる（下の get_price_and_meta 内で処理）

    return result


# ─── Alpha Vantage OVERVIEW（米国株） ─────────────────────────────────────

def get_us_fundamentals_alpha(symbol: str, api_key: str) -> dict:
    """
    Returns dict with keys:
        eps, bps, per_fwd, roe, roa, equity_ratio,
        operating_margin, interest_coverage, ev_ebitda
    """
    result = {k: None for k in [
        "eps", "bps", "per_fwd", "roe", "roa", "equity_ratio",
        "operating_margin", "interest_coverage", "ev_ebitda"
    ]}

    params = {"function": "OVERVIEW", "symbol": symbol, "apikey": api_key}
    try:
        resp = requests.get(ALPHA_BASE, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return result

    if not isinstance(data, dict) or not data:
        return result

    # 会社名キャッシュ
    name_val = data.get("Name")
    if isinstance(name_val, str) and name_val.strip():
        COMPANY_NAME_CACHE[symbol.upper()] = name_val.strip()

    eps_val = _safe_float(data.get("EPS"))
    bps_val = _safe_float(data.get("BookValue"))
    fpe_val = _safe_float(data.get("ForwardPE"))
    roe_raw = _safe_float(data.get("ReturnOnEquityTTM"))
    roa_raw = _safe_float(data.get("ReturnOnAssetsTTM"))
    opm_raw = _safe_float(data.get("OperatingMarginTTM"))  # ★新規
    evebitda_raw = _safe_float(data.get("EVToEBITDA"))     # ★新規

    if eps_val is not None: result["eps"]     = eps_val
    if bps_val is not None: result["bps"]     = bps_val
    if fpe_val is not None: result["per_fwd"] = fpe_val

    # Alpha は小数表記（0.15 = 15%）→ % 変換
    if roe_raw is not None: result["roe"] = roe_raw * 100.0
    if roa_raw is not None: result["roa"] = roa_raw * 100.0
    if opm_raw is not None: result["operating_margin"] = opm_raw * 100.0

    # EV/EBITDA は倍率のまま使用
    if evebitda_raw is not None: result["ev_ebitda"] = evebitda_raw

    # 自己資本比率 ≒ ROA / ROE
    if roe_raw not in (None, 0.0) and roa_raw not in (None, 0.0):
        approx = roa_raw / roe_raw
        if 0.0 < approx < 1.0:
            result["equity_ratio"] = approx * 100.0

    return result


# ─── yfinance から新規項目を補完 ─────────────────────────────────────────

def _supplement_from_yfinance(info: dict, current: dict) -> dict:
    """
    yfinance.info から未取得項目を補完する。
    current は既存の結果 dict（上書きは None のときのみ）。
    """
    # ← ここに追加
    import streamlit as st
    st.write("DEBUG yf.info keys:", {k: info.get(k) for k in [
        "operatingMargins", "ebit", "interestExpense", 
        "operatingCashflow", "debtToEquity", "totalDebt", 
        "totalStockholderEquity"
    ]})
    #####
  
    def _fill(key_current, info_key, scale=1.0):
        if current.get(key_current) is None:
            val = _safe_float(info.get(info_key))
            if val is not None:
                current[key_current] = val * scale

    _fill("eps",              "trailingEps")
    _fill("bps",              "bookValue")
    _fill("per_fwd",          "forwardPE")
    _fill("roe",              "returnOnEquity",  100.0)
    _fill("roa",              "returnOnAssets",  100.0)
    _fill("operating_margin", "operatingMargins", 100.0)  # ★新規

    # インタレストカバレッジ：yfinance に直接フィールドなし → 複数経路で計算
    if current.get("interest_coverage") is None:
        ebit   = _safe_float(info.get("ebit"))
        int_ex = _safe_float(info.get("interestExpense"))
        if ebit is not None and int_ex not in (None, 0):
            # interestExpense はマイナス表記の場合あり → abs / cov < 0 も許容（赤字企業）
            current["interest_coverage"] = round(ebit / abs(int_ex), 2)
        elif current.get("interest_coverage") is None:
            # 経路②: operatingCashflow / interestExpense
            op_cf  = _safe_float(info.get("operatingCashflow"))
            if op_cf is not None and int_ex not in (None, 0):
                current["interest_coverage"] = round(op_cf / abs(int_ex), 2)

    # D/E レシオ：yfinance から複数経路で取得
    if current.get("de_ratio") is None:
        de = _safe_float(info.get("debtToEquity"))
        if de is not None:
            # yfinance は % 表記（例: 150.0 = D/E 1.50 倍）→ 100 で割って倍率に変換
            current["de_ratio"] = round(de / 100.0, 3)
        else:
            # 経路②: totalDebt / totalStockholderEquity
            total_debt   = _safe_float(info.get("totalDebt"))
            total_equity = _safe_float(info.get("totalStockholderEquity"))
            if total_debt is not None and total_equity not in (None, 0):
                current["de_ratio"] = round(total_debt / abs(total_equity), 3)

    # EV/EBITDA
    if current.get("ev_ebitda") is None:
        ev_val     = _safe_float(info.get("enterpriseValue"))
        ebitda_val = _safe_float(info.get("ebitda"))
        if ev_val and ebitda_val and ebitda_val > 0:
            current["ev_ebitda"] = round(ev_val / ebitda_val, 2)

    # 自己資本比率の補完
    if current.get("equity_ratio") is None:
        roe = current.get("roe")
        roa = current.get("roa")
        if roe and roa and roe != 0:
            approx = (roa / 100) / (roe / 100)
            if 0 < approx < 1:
                current["equity_ratio"] = approx * 100

    return current


# ─── メイン取得関数 ────────────────────────────────────────────────────────

def get_price_and_meta(ticker: str, period: str = "400d", interval: str = "1d") -> dict:
    """
    株価データ + ファンダメンタル指標をまとめて取得して返す。

    返却 dict の主なキー（v3 追加項目に ★）:
        df, close_col, close, previous_close, high_52w, low_52w
        company_name, dividend_yield
        eps, bps, per_fwd, eps_fwd
        roe, roa, equity_ratio
        operating_margin ★, interest_coverage ★, de_ratio ★
        ev_ebitda ★
    """
    # ── 株価データ（yfinance・リトライ付き） ──
    df = None
    last_err = None
    for _ in range(2):
        try:
            df = yf.download(ticker, period=period, interval=interval, progress=False)
        except Exception as e:
            last_err = e
            df = pd.DataFrame()
        if not df.empty and len(df) >= 2:
            break
        time.sleep(1)

    if df is None or df.empty or len(df) < 2:
        msg = f"株価データ取得エラー: {last_err}" if last_err else "株価データが取得できませんでした。"
        raise ValueError(msg)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["_".join(col).strip() for col in df.columns]

    try:
        close_col = next(c for c in df.columns if "Close" in c)
    except StopIteration:
        raise ValueError("終値（Close）列が見つかりませんでした。")

    try:
        high_col = next(c for c in df.columns if c.startswith("High"))
        low_col  = next(c for c in df.columns if c.startswith("Low"))
        use_hl   = True
    except StopIteration:
        use_hl   = False

    TRADING_DAYS_1Y = 252
    df_1y = df.iloc[-TRADING_DAYS_1Y:]

    close          = float(df[close_col].iloc[-1])
    previous_close = float(df[close_col].iloc[-2])

    if use_hl:
        high_52w = float(df_1y[high_col].max())
        low_52w  = float(df_1y[low_col].min())
    else:
        high_52w = float(df_1y[close_col].max())
        low_52w  = float(df_1y[close_col].min())

    # ── ファンダメンタル取得 ──
    fundamentals: dict = {k: None for k in [
        "eps", "bps", "per_fwd", "eps_fwd",
        "roe", "roa", "equity_ratio",
        "operating_margin", "interest_coverage", "de_ratio",
        "ev_ebitda",
    ]}

    if is_jpx_ticker(ticker):
        # ── 日本株: IRBANK ──
        code = ticker.replace(".T", "") if ticker.endswith(".T") else ticker
        irbank = get_jpx_fundamentals_irbank(code)
        for k in ("eps", "bps", "per_fwd", "roe", "roa", "equity_ratio",
                  "operating_margin", "interest_coverage"):
            if irbank.get(k) is not None:
                fundamentals[k] = irbank[k]

        # yfinance で補完（IRBANK で取れない項目を埋める）
        try:
            info = yf.Ticker(ticker).info or {}
            fundamentals = _supplement_from_yfinance(info, fundamentals)
        except Exception:
            pass

    else:
        # ── 米国株: Alpha Vantage → yfinance フォールバック ──
        av_key = _get_av_key()
        if av_key:
            av = get_us_fundamentals_alpha(ticker, av_key)
            for k, v in av.items():
                if v is not None:
                    fundamentals[k] = v

        try:
            info = yf.Ticker(ticker).info or {}
            fundamentals = _supplement_from_yfinance(info, fundamentals)
        except Exception:
            pass

    # PER（実績）が未計算なら補完
    if fundamentals["eps"] not in (None, 0) and close > 0 and fundamentals.get("per_fwd") is None:
        fundamentals["per_fwd"] = close / fundamentals["eps"]

    # 予想 EPS
    if fundamentals["per_fwd"] not in (None, 0) and close > 0:
        fundamentals["eps_fwd"] = close / fundamentals["per_fwd"]

    #  ── yfinance オブジェクト / info は 1回だけ取得 ──
    ticker_obj   = yf.Ticker(ticker)
    info = _safe_get_yf_info(ticker_obj)
    
  
    # ── 会社名 ──
    key          = ticker.strip().upper()
    company_name = COMPANY_NAME_CACHE.get(key)
    if not company_name:
        if is_jpx_ticker(ticker):
            company_name = (
                info.get("shortName")
                or info.get("longName")
                or ticker
            )
        else:
            company_name = (info.get("longName") or info.get("shortName") or ticker)

    dividend_yield = _compute_dividend_yield(ticker_obj, close)

    # ── 業種分類（ノックアウト閾値補正用） ──
    industry = _extract_industry_from_info(info)
  　# デバッグコード（後で消すこと！）──────────
    import streamlit as st
    st.write("DEBUG industry:", industry)
    # ────────────────────────────────────────

    
    return {
        "df":             df,
        "close_col":      close_col,
        "close":          close,
        "previous_close": previous_close,
        "high_52w":       high_52w,
        "low_52w":        low_52w,
        "company_name":   company_name,
        "dividend_yield": dividend_yield,
        "industry": industry,
        # ファンダメンタル
        **fundamentals,
    }
