"""
indicators.py  (v3)
────────────────────────────────────────────────────────────────────────────
テクニカル指標の計算 + Q/V/T スコアの統合モジュール。

【v3 の変更点】
  - Q スコア: 内部の簡易関数を廃止 → q_logic.score_quality() を正式呼び出し
  - V スコア: 内部の簡易関数を廃止 → valuation.score_valuation() を正式呼び出し
  - Q 計算に operating_margin / de_ratio / interest_coverage を追加
  - V 計算に ev_ebitda / sector_v_score（pattern_db 由来）を追加
  - tech dict に q1/q3/v1〜v4/q_warnings/financial_type を追加

返却 dict（tech）は main.py / 各 tab レンダラーが直接参照する。
"""

from typing import Optional, Dict, Any

import pandas as pd

from modules.t_logic import compute_t_metrics
from modules.q_logic import score_quality
from modules.valuation import score_valuation


# -----------------------------------------------------------
# 単純テクニカル計算（変更なし）
# -----------------------------------------------------------

def calc_moving_averages(df: pd.DataFrame, close_col: str) -> pd.DataFrame:
    df["25MA"] = df[close_col].rolling(25).mean()
    df["50MA"] = df[close_col].rolling(50).mean()
    df["75MA"] = df[close_col].rolling(75).mean()
    return df


def calc_bollinger_bands(df: pd.DataFrame, close_col: str) -> pd.DataFrame:
    df["20MA"]  = df[close_col].rolling(20).mean()
    df["20STD"] = df[close_col].rolling(20).std()
    df["BB_+1σ"] = df["20MA"] + df["20STD"]
    df["BB_+2σ"] = df["20MA"] + 2 * df["20STD"]
    df["BB_-1σ"] = df["20MA"] - df["20STD"]
    df["BB_-2σ"] = df["20MA"] - 2 * df["20STD"]
    return df


def calc_rsi(df: pd.DataFrame, close_col: str, period: int = 14) -> pd.DataFrame:
    delta    = df[close_col].diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean().replace(0, 1e-10)
    rs       = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))
    return df


def calc_slope(series: pd.Series, window: int = 4) -> float:
    s = series.dropna()
    if len(s) < window + 1:
        return 0.0
    start = float(s.iloc[-window - 1])
    end   = float(s.iloc[-1])
    if start == 0:
        return 0.0
    return (end - start) / start * 100.0


def slope_arrow(series: pd.Series) -> str:
    s = series.dropna()
    if len(s) < 2:
        return "→"
    diff = float(s.iloc[-1]) - float(s.iloc[-2])
    if diff > 0:   return "↗"
    elif diff < 0: return "↘"
    return "→"


# -----------------------------------------------------------
# メイン：compute_indicators
# -----------------------------------------------------------

def compute_indicators(
    df: pd.DataFrame,
    close_col: str,
    high_52w: Optional[float] = None,
    low_52w: Optional[float] = None,
    # ─ Q 関連 ─
    eps: Optional[float] = None,
    bps: Optional[float] = None,
    eps_fwd: Optional[float] = None,
    per_fwd: Optional[float] = None,
    roe: Optional[float] = None,
    roa: Optional[float] = None,
    equity_ratio: Optional[float] = None,
    operating_margin: Optional[float] = None,    # ★v3
    de_ratio: Optional[float] = None,            # ★v3
    interest_coverage: Optional[float] = None,  # ★v3
    # ─ V 関連 ─
    dividend_yield: Optional[float] = None,
    ev_ebitda: Optional[float] = None,           # ★v3
    # ─ セクター相対（pattern_db 由来） ─
    sector_v_score: Optional[float] = None,      # ★v3
    sector_rel_scores: Optional[Dict[str, Any]] = None,  # ★v3
    financial_type: Optional[Dict[str, Any]] = None,     # ★v3
    q_rel_scores: Optional[Dict[str, Any]] = None,       # ★v3.2 Q相対評価
    industry: str = "",                                   # ★v3.3/v3.4 業種別閾値
    sector: str = "",                                     # ★v3.4 閾値マッチング補助
    is_us: bool = False,                                  # ★v3.5 US市場フラグ
) -> Dict[str, Any]:
    """
    テクニカル指標 + Q/V/T スコアをまとめて計算し、UI 用の dict を返す。
    """

    # ── テクニカル計算 ──
    df = calc_moving_averages(df, close_col)
    df = calc_bollinger_bands(df, close_col)
    df = calc_rsi(df, close_col)

    df_valid = df.dropna(subset=[
        close_col, "25MA", "50MA", "75MA",
        "BB_+1σ", "BB_+2σ", "BB_-1σ", "BB_-2σ", "RSI",
    ])
    if df_valid.empty or len(df_valid) < 5:
        raise ValueError("テクニカル指標を計算するためのデータが不足しています。")

    last = df_valid.iloc[-1]

    price  = float(last[close_col])
    ma_25  = float(last["25MA"])
    ma_50  = float(last["50MA"])
    ma_75  = float(last["75MA"])
    rsi    = float(last["RSI"])
    bb_plus1  = float(last["BB_+1σ"])
    bb_plus2  = float(last["BB_+2σ"])
    bb_minus1 = float(last["BB_-1σ"])
    bb_minus2 = float(last["BB_-2σ"])

    slope_25 = calc_slope(df["25MA"])
    slope_50 = calc_slope(df["50MA"])
    slope_75 = calc_slope(df["75MA"])
    arrow_25 = slope_arrow(df["25MA"])
    arrow_50 = slope_arrow(df["50MA"])
    arrow_75 = slope_arrow(df["75MA"])

    # ── PER / PBR 実績 ──
    per: Optional[float] = None
    pbr: Optional[float] = None
    if eps not in (None, 0):
        per = price / eps
    if bps not in (None, 0):
        pbr = price / bps

    per_fwd_calc: Optional[float] = None
    if per_fwd not in (None, 0):
        per_fwd_calc = per_fwd
    elif eps_fwd not in (None, 0):
        per_fwd_calc = price / eps_fwd

    # ── T ロジック ──
    t_metrics = compute_t_metrics(
        price=price, ma_25=ma_25, ma_50=ma_50, ma_75=ma_75,
        rsi=rsi, bb_plus1=bb_plus1, bb_plus2=bb_plus2,
        bb_minus1=bb_minus1, bb_minus2=bb_minus2,
        slope_25=slope_25, low_52w=low_52w, high_52w=high_52w,
        per=per, pbr=pbr,
    )
    t_score = float(t_metrics["t_score"])

    # ── Q スコア（q_logic を正式呼び出し） ──
    q_result = score_quality(
        roe=roe, roa=roa, equity_ratio=equity_ratio,
        operating_margin=operating_margin,
        de_ratio=de_ratio,
        interest_coverage=interest_coverage,
        q_rel_scores=q_rel_scores,
        industry=industry,
        sector=sector,
        is_us=is_us,
    )
    q_score = q_result["q_score"]

    # ── V スコア（valuation を正式呼び出し） ──
    v_result = score_valuation(
        per=per, pbr=pbr, dividend_yield=dividend_yield,
        ev_ebitda=ev_ebitda,
        sector_v_score=sector_v_score,
    )
    v_score = v_result["v_score"]

    # ── QVT 総合 ──
    #qvt_score = round((q_score + v_score + t_score) / 3.0, 1)
    # ── QVT 重み設定 ──
    WEIGHT_Q = 0.447
    WEIGHT_V = 0.260
    WEIGHT_T = 0.293

    # ── QVT 総合スコア（加重平均） ──
    qvt_score = round(
        (q_score * WEIGHT_Q) +
        (v_score * WEIGHT_V) +
        (t_score * WEIGHT_T),
        1
    )
  

    # ── 返却 dict ──
    result: Dict[str, Any] = {
        # 生データ
        "df": df, "df_valid": df_valid,
        "close": price,

        # MA
        "ma_25": ma_25, "ma_50": ma_50, "ma_75": ma_75,
        "slope_25": slope_25, "slope_50": slope_50, "slope_75": slope_75,
        "arrow_25": arrow_25, "arrow_50": arrow_50, "arrow_75": arrow_75,

        # BB
        "bb_plus1": bb_plus1, "bb_plus2": bb_plus2,
        "bb_minus1": bb_minus1, "bb_minus2": bb_minus2,

        "rsi": rsi,
        "high_52w": high_52w, "low_52w": low_52w,

        # ファンダ（生）
        "eps": eps, "bps": bps, "eps_fwd": eps_fwd,
        "per": per, "pbr": pbr, "per_fwd": per_fwd_calc,
        "roe": roe, "roa": roa, "equity_ratio": equity_ratio,
        "operating_margin": operating_margin,   # ★v3
        "de_ratio": de_ratio,                   # ★v3
        "interest_coverage": interest_coverage, # ★v3
        "dividend_yield": dividend_yield,
        "ev_ebitda": ev_ebitda,                 # ★v3

        # Q サブスコア
        "q_score": q_score,
        "q1": q_result["q1"],
        "q3": q_result["q3"],
        "q_warnings":      q_result["warnings"],
        "er_threshold":    q_result.get("er_threshold",   10.0),   # ★v3.4
        "ic_threshold":    q_result.get("ic_threshold",    1.5),   # ★v3.4
        "threshold_note":  q_result.get("threshold_note", "標準基準"),  # ★v3.4

        # V サブスコア
        "v_score": v_score,
        "v1": v_result["v1"],
        "v2": v_result["v2"],
        "v3": v_result["v3"],
        "v4": v_result["v4"],                   # ★v3
        "has_sector": v_result["has_sector"],   # ★v3

        # セクター相対（UI表示用）
        "sector_rel_scores": sector_rel_scores or {},  # ★v3
        "financial_type": financial_type or {},        # ★v3

        # 市場・セクター情報（render_v_tab で sector_display に使用）
        "sector":   sector   or "",   # ★v4 yfinance英語名をそのまま保持
        "industry": industry or "",   # ★v4
        "is_us":    is_us,            # ★v4

        # T / QVT
        "t_score": t_score,
        "qvt_score": qvt_score,
    }

    # T メトリクスをマージ
    result.update(t_metrics)

    return result
