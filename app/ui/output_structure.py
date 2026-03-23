"""UI向けの共通出力構造を組み立てるモジュール。

classic / magi などのUIはこのモジュールから返る分析結果を描画するだけにし、
データ取得・分類・指標計算の責務をここへ集約する。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

from modules.data_fetch import get_price_and_meta
from modules.indicators import compute_indicators
from modules.pattern_db import (
    calc_sector_relative_scores_from_db,
    classify_ticker,
    load_pattern_db,
)


DEFAULT_SPINNER_MESSAGES: Dict[str, str] = {
    "fetch": "データ取得中…",
    "classify": "財務タイプ分類中…",
    "compute": "指標計算中…",
}


def _merge_spinner_messages(spinner_messages: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    merged = dict(DEFAULT_SPINNER_MESSAGES)
    if spinner_messages:
        merged.update({k: v for k, v in spinner_messages.items() if v})
    return merged



def _compute_sector_context(base: Dict[str, Any]) -> Dict[str, Any]:
    close_price = base.get("close", 0)
    eps = base.get("eps")
    bps = base.get("bps")
    sector_name = base.get("sector", "")

    per_tmp = (close_price / eps) if (eps and eps != 0 and close_price) else None
    pbr_tmp = (close_price / bps) if (bps and bps != 0 and close_price) else None
    sector_rel = calc_sector_relative_scores_from_db(
        sector=sector_name,
        per=per_tmp,
        pbr=pbr_tmp,
        ev_ebitda=base.get("ev_ebitda"),
    )
    sector_v_score = (
        sector_rel.get("sector_v_score")
        if sector_name and sector_rel.get("sector_matched", False)
        else None
    )
    return {
        "sector_name": sector_name,
        "sector_rel": sector_rel,
        "sector_v_score": sector_v_score,
    }



def _finalize_tech(ticker: str, base: Dict[str, Any], tech: Dict[str, Any], sector_name: str) -> Dict[str, Any]:
    per_final = tech.get("per")
    pbr_final = tech.get("pbr")
    ev_final = tech.get("ev_ebitda")

    if per_final or pbr_final or ev_final:
        sector_rel_final = calc_sector_relative_scores_from_db(
            sector=sector_name,
            per=per_final,
            pbr=pbr_final,
            ev_ebitda=ev_final,
        )
        tech["sector_rel_scores"] = sector_rel_final
        if sector_rel_final.get("sector_matched", False):
            tech["sector_v_score"] = sector_rel_final.get("sector_v_score")

    tech["is_us"] = not ticker.upper().endswith(".T")
    if not tech.get("sector"):
        tech["sector"] = base.get("sector", "")
    if not tech.get("industry"):
        tech["industry"] = base.get("industry", "")
    return tech



def build_analysis_output(
    ticker: str,
    spinner_messages: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    """UI描画用の共通出力構造を返す。失敗時は None。"""
    messages = _merge_spinner_messages(spinner_messages)

    with st.spinner(messages["fetch"]):
        try:
            base = get_price_and_meta(ticker)
        except ValueError as exc:
            st.error(str(exc))
            return None

    with st.spinner(messages["classify"]):
        financial_type = classify_ticker(
            ticker,
            load_pattern_db(),
            roe=base.get("roe"),
            roa=base.get("roa"),
            equity_ratio=base.get("equity_ratio"),
            interest_coverage=base.get("interest_coverage"),
            operating_margin=base.get("operating_margin"),
        )
        sector_context = _compute_sector_context(base)

    with st.spinner(messages["compute"]):
        try:
            tech = compute_indicators(
                base["df"],
                base["close_col"],
                base["high_52w"],
                base["low_52w"],
                eps=base.get("eps"),
                bps=base.get("bps"),
                eps_fwd=base.get("eps_fwd"),
                per_fwd=base.get("per_fwd"),
                roe=base.get("roe"),
                roa=base.get("roa"),
                equity_ratio=base.get("equity_ratio"),
                dividend_yield=base.get("dividend_yield"),
                operating_margin=base.get("operating_margin"),
                de_ratio=base.get("de_ratio"),
                interest_coverage=base.get("interest_coverage"),
                ev_ebitda=base.get("ev_ebitda"),
                sector_v_score=sector_context["sector_v_score"],
                sector_rel_scores=sector_context["sector_rel"],
                financial_type=financial_type,
                industry=base.get("industry", ""),
                sector=base.get("sector", ""),
                is_us=not ticker.upper().endswith(".T"),
                price_df=base.get("price_df", base["df"]),
                bm_raw_vals=base.get("bm_raw_vals"),
            )
        except ValueError as exc:
            st.error(str(exc))
            return {
                "ticker": ticker,
                "base": base,
                "tech": None,
                "summary": {
                    "company_name": base.get("company_name", ""),
                    "close": base.get("close"),
                    "previous_close": base.get("previous_close"),
                    "industry": base.get("industry", ""),
                    "sector": base.get("sector", ""),
                    "dividend_yield": base.get("dividend_yield"),
                    "is_us": not ticker.upper().endswith(".T"),
                },
                "scores": None,
            }

    tech = _finalize_tech(ticker, base, tech, sector_context["sector_name"])

    return {
        "ticker": ticker,
        "base": base,
        "tech": tech,
        "summary": {
            "company_name": base.get("company_name", ""),
            "close": base.get("close"),
            "previous_close": base.get("previous_close"),
            "industry": base.get("industry", ""),
            "sector": base.get("sector", ""),
            "dividend_yield": base.get("dividend_yield"),
            "is_us": tech.get("is_us", False),
        },
        "scores": {
            "q": float(tech["q_score"]),
            "v": float(tech["v_score"]),
            "t": float(tech["t_score"]),
            "qvt": float(tech["qvt_score"]),
        },
    }
