"""
data_fetch.py
- 日本株: IRBANK スクレイピング + yfinance（株価・配当）
- 米国株: Alpha Vantage OVERVIEW API + yfinance（株価・配当・補完）
Alpha Vantage APIキーは st.secrets["ALPHA_VANTAGE_API_KEY"] から取得。
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


# ─── Alpha Vantage APIキー ──────────────────────────────────

def _get_av_key() -> Optional[str]:
    try:
        return st.secrets.get("ALPHA_VANTAGE_API_KEY", None)
    except Exception:
        return None


# ─── ティッカー変換 ─────────────────────────────────────────

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


# ─── 共通ユーティリティ ─────────────────────────────────────

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


# ─── IRBANK スクレイピング（日本株） ────────────────────────

def get_jpx_fundamentals_irbank(code: str) -> Tuple[
    Optional[float], Optional[float], Optional[float],
    Optional[float], Optional[float], Optional[float]
]:
    """Returns: eps, bps, per_fwd, roe, roa, equity_ratio"""
    url = f"{IRBANK_BASE}{code}"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": IRBANK_BASE}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception:
        return None, None, None, None, None, None

    soup = BeautifulSoup(resp.text, "html.parser")

    try:
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            raw  = title_tag.string.strip().split("【")[0]
            name = _clean_jpx_company_name(raw)
            if name:
                COMPANY_NAME_CACHE[code]       = name
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

    eps          = (extract_number_near("EPS（連）") or extract_number_near("EPS（単）")
                    or extract_number_near("EPS"))
    bps          = (extract_number_near("BPS（連）") or extract_number_near("BPS（単）")
                    or extract_number_near("BPS"))
    per_fwd      = extract_number_near("PER予")
    roe          = extract_number_near("ROE（連）") or extract_number_near("ROE")
    roa          = extract_number_near("ROA（連）") or extract_number_near("ROA")
    equity_ratio = (extract_number_near("株主資本比率（連）")
                    or extract_number_near("株主資本比率"))

    return eps, bps, per_fwd, roe, roa, equity_ratio


# ─── Alpha Vantage OVERVIEW（米国株） ───────────────────────

def get_us_fundamentals_alpha(symbol: str, api_key: str) -> Tuple[
    Optional[float], Optional[float], Optional[float],
    Optional[float], Optional[float], Optional[float]
]:
    """Returns: eps, bps, per_fwd, roe(%), roa(%), equity_ratio(%)"""
    eps = bps = per_fwd = roe_pct = roa_pct = equity_ratio_pct = None

    params = {"function": "OVERVIEW", "symbol": symbol, "apikey": api_key}
    try:
        resp = requests.get(ALPHA_BASE, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return eps, bps, per_fwd, roe_pct, roa_pct, equity_ratio_pct

    if not isinstance(data, dict) or not data:
        return eps, bps, per_fwd, roe_pct, roa_pct, equity_ratio_pct

    # 会社名キャッシュ
    name_val = data.get("Name")
    if isinstance(name_val, str) and name_val.strip():
        COMPANY_NAME_CACHE[symbol.upper()] = name_val.strip()

    eps_val = _safe_float(data.get("EPS"))
    bps_val = _safe_float(data.get("BookValue"))
    fpe_val = _safe_float(data.get("ForwardPE"))
    roe_raw = _safe_float(data.get("ReturnOnEquityTTM"))
    roa_raw = _safe_float(data.get("ReturnOnAssetsTTM"))

    if eps_val is not None: eps     = eps_val
    if bps_val is not None: bps     = bps_val
    if fpe_val is not None: per_fwd = fpe_val

    # Alpha は小数表記（0.15 = 15%）→ % 変換
    if roe_raw is not None: roe_pct = roe_raw * 100.0
    if roa_raw is not None: roa_pct = roa_raw * 100.0

    # 自己資本比率 ≒ ROA / ROE
    if roe_raw not in (None, 0.0) and roa_raw not in (None, 0.0):
        approx = roa_raw / roe_raw
        if 0.0 < approx < 1.0:
            equity_ratio_pct = approx * 100.0

    return eps, bps, per_fwd, roe_pct, roa_pct, equity_ratio_pct


# ─── メイン取得関数 ─────────────────────────────────────────

def get_price_and_meta(ticker: str, period: str = "400d", interval: str = "1d") -> dict:
    # 株価データ（yfinance・リトライ付き）
    # period="400d" で52週（約260営業日）を確実にカバー
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

    # 直近252営業日（≒52週）だけを52W計算対象にする
    # High/Low列があればより正確（ヒゲを含む）
    try:
        high_col = next(c for c in df.columns if c.startswith("High"))
        low_col  = next(c for c in df.columns if c.startswith("Low"))
        use_hl   = True
    except StopIteration:
        use_hl   = False

    TRADING_DAYS_1Y = 252
    df_1y = df.iloc[-TRADING_DAYS_1Y:]   # 直近1年分

    close          = float(df[close_col].iloc[-1])
    previous_close = float(df[close_col].iloc[-2])

    if use_hl:
        high_52w = float(df_1y[high_col].max())
        low_52w  = float(df_1y[low_col].min())
    else:
        high_52w = float(df_1y[close_col].max())
        low_52w  = float(df_1y[close_col].min())

    eps = bps = per_fwd = eps_fwd = roe = roa = equity_ratio = None

    if is_jpx_ticker(ticker):
        # ── 日本株: IRBANK ──
        code = ticker.replace(".T", "") if ticker.endswith(".T") else ticker
        eps, bps, per_fwd, roe, roa, equity_ratio = get_jpx_fundamentals_irbank(code)
        if per_fwd not in (None, 0.0) and close > 0:
            eps_fwd = close / per_fwd
    else:
        # ── 米国株: Alpha Vantage → yfinance でフォールバック補完 ──
        av_key = _get_av_key()
        if av_key:
            eps, bps, per_fwd, roe, roa, equity_ratio = get_us_fundamentals_alpha(ticker, av_key)

        # yfinance.info で未取得項目を補完
        try:
            info = yf.Ticker(ticker).info or {}
            if eps is None and info.get("trailingEps"):
                eps = float(info["trailingEps"])
            if bps is None and info.get("bookValue"):
                bps = float(info["bookValue"])
            if per_fwd is None and info.get("forwardPE"):
                per_fwd = float(info["forwardPE"])
            if roe is None and info.get("returnOnEquity"):
                roe = float(info["returnOnEquity"]) * 100
            if roa is None and info.get("returnOnAssets"):
                roa = float(info["returnOnAssets"]) * 100
            if equity_ratio is None and roe and roa and roe != 0:
                approx = (roa / 100) / (roe / 100)
                if 0 < approx < 1:
                    equity_ratio = approx * 100
        except Exception:
            pass

        if eps not in (None, 0) and close > 0 and per_fwd is None:
            per_fwd = close / eps

    # 会社名
    ticker_obj   = yf.Ticker(ticker)
    key          = ticker.strip().upper()
    company_name = COMPANY_NAME_CACHE.get(key)
    if not company_name:
        try:
            info = ticker_obj.info or {}
            # 日本株: longName は英語表記が多いので shortName（日本語）を優先
            if is_jpx_ticker(ticker):
                company_name = (info.get("shortName")
                                or info.get("longName")
                                or ticker)
            else:
                company_name = (info.get("longName")
                                or info.get("shortName")
                                or ticker)
        except Exception:
            company_name = ticker

    dividend_yield = _compute_dividend_yield(ticker_obj, close)

    return {
        "df":             df,
        "close_col":      close_col,
        "close":          close,
        "previous_close": previous_close,
        "high_52w":       high_52w,
        "low_52w":        low_52w,
        "company_name":   company_name,
        "dividend_yield": dividend_yield,
        "eps":            eps,
        "bps":            bps,
        "per_fwd":        per_fwd,
        "eps_fwd":        eps_fwd,
        "roe":            roe,
        "roa":            roa,
        "equity_ratio":   equity_ratio,
    }
