"""
d_logic.py
────────────────────────────────────────────────────────────────────────────
D（Difference / benchmark-relative）指標ロジック。

責務:
  - 個別銘柄とベンチマークの価格系列を整列
  - relative return / excess return を計算
  - Dスコアと可視化用データを返す

UIや orchestrator 側ではこの結果を描画・payload化するだけに留める。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd


RETURN_WINDOWS = (20, 60, 120)


def _normalize_score(excess_return_pct: Optional[float]) -> Optional[float]:
    if excess_return_pct is None:
        return None
    score = 50.0 + (float(excess_return_pct) * 2.5)
    return max(0.0, min(100.0, score))


def _calc_return_pct(series: pd.Series, window: int) -> Optional[float]:
    clean = series.dropna()
    if len(clean) <= window:
        return None
    start = float(clean.iloc[-window - 1])
    end = float(clean.iloc[-1])
    if start == 0:
        return None
    return (end - start) / start * 100.0


def _build_relative_ratio_series(
    stock_close: pd.Series,
    benchmark_close: pd.Series,
    points: int = 120,
) -> list[Dict[str, Any]]:
    merged = pd.concat(
        [stock_close.rename("stock"), benchmark_close.rename("benchmark")],
        axis=1,
        join="inner",
    ).dropna()
    if merged.empty:
        return []

    merged = merged.tail(points).copy()
    base_stock = float(merged["stock"].iloc[0])
    base_benchmark = float(merged["benchmark"].iloc[0])
    if base_stock == 0 or base_benchmark == 0:
        return []

    merged["stock_norm"] = merged["stock"] / base_stock
    merged["benchmark_norm"] = merged["benchmark"] / base_benchmark
    merged["relative_ratio"] = merged["stock_norm"] / merged["benchmark_norm"]

    return [
        {
            "date": idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx),
            "relative_ratio": round(float(row["relative_ratio"]), 4),
        }
        for idx, row in merged.iterrows()
    ]


def compute_d_metrics(
    price_df: Optional[pd.DataFrame],
    close_col: str,
    bm_raw_vals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    個別銘柄とベンチマーク系列から Dスコア と可視化用データを返す。

    bm_raw_vals 想定:
      {
        "ticker": "^N225",
        "df": <pd.DataFrame>,
        "close_col": "Close",
        "company_name": "Nikkei 225"
      }
    """
    default_result = {
        "d_score": None,
        "d_scores": {
            "overall": None,
            "vs_benchmark": None,
            "windows": {},
        },
        "visualization": {
            "benchmark_ticker": bm_raw_vals.get("ticker") if bm_raw_vals else None,
            "benchmark_name": bm_raw_vals.get("company_name") if bm_raw_vals else None,
            "relative_ratio_series": [],
            "return_comparison": [],
        },
    }

    if price_df is None or bm_raw_vals is None:
        return default_result

    benchmark_df = bm_raw_vals.get("df")
    benchmark_close_col = bm_raw_vals.get("close_col")
    if benchmark_df is None or not benchmark_close_col:
        return default_result

    if close_col not in price_df.columns or benchmark_close_col not in benchmark_df.columns:
        return default_result

    stock_close = price_df[close_col]
    benchmark_close = benchmark_df[benchmark_close_col]

    window_scores: Dict[str, Dict[str, Optional[float]]] = {}
    valid_scores: list[float] = []
    return_comparison: list[Dict[str, Any]] = []

    for window in RETURN_WINDOWS:
        stock_return = _calc_return_pct(stock_close, window)
        benchmark_return = _calc_return_pct(benchmark_close, window)
        excess_return = (
            None
            if stock_return is None or benchmark_return is None
            else stock_return - benchmark_return
        )
        score = _normalize_score(excess_return)
        if score is not None:
            valid_scores.append(score)

        window_key = f"{window}d"
        window_scores[window_key] = {
            "stock_return_pct": round(stock_return, 2) if stock_return is not None else None,
            "benchmark_return_pct": round(benchmark_return, 2) if benchmark_return is not None else None,
            "excess_return_pct": round(excess_return, 2) if excess_return is not None else None,
            "score": round(score, 1) if score is not None else None,
        }
        return_comparison.append({
            "window": window_key,
            **window_scores[window_key],
        })

    overall_score = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else None

    return {
        "d_score": overall_score,
        "d_scores": {
            "overall": overall_score,
            "vs_benchmark": overall_score,
            "windows": window_scores,
        },
        "visualization": {
            "benchmark_ticker": bm_raw_vals.get("ticker"),
            "benchmark_name": bm_raw_vals.get("company_name"),
            "relative_ratio_series": _build_relative_ratio_series(stock_close, benchmark_close),
            "return_comparison": return_comparison,
        },
    }
