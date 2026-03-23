"""
indicators.py  (v4)
────────────────────────────────────────────────────────────────────────────
テクニカル指標の計算 + Q/V/T+Dスコアの統合モジュール。

【v3 の変更点】
  - Q スコア: 内部の簡易関数を廃止 → q_logic.score_quality() を正式呼び出し
  - V スコア: 内部の簡易関数を廃止 → v_logic.score_valuation() を正式呼び出し
  - Q 計算に operating_margin / de_ratio / interest_coverage を追加
  - V 計算に ev_ebitda / sector_v_score（pattern_db 由来）を追加
  - tech dict に q1/q3/v1〜v4/q_warnings/financial_type を追加

返却 dict（tech）は main.py / 各 tab レンダラーが直接参照する。
"""

from typing import Optional, Dict, Any

import pandas as pd

from modules.t_logic import compute_t_block
from modules.q_logic import compute_q_block
from modules.v_logic import compute_v_block
from modules.d_logic import score_defense, get_base_rank


 # -----------------------------------------------------------
 # D スコアのマージ
 # -----------------------------------------------------------

_D_SUBSCORE_KEYS = [f"def{i}" for i in range(1, 7)]


def _merge_defense_result(result: Dict[str, Any], d_result: Dict[str, Any]) -> None:
    """score_defense() の結果を indicators の返却 dict にマージする。"""
    defensive_score = d_result.get("defensive_score")
    if defensive_score is None:
        for key in _D_SUBSCORE_KEYS:
            result[key] = None
            result[f"{key}_rank"] = None
        result["d_score"] = None
        result["defensive_score"] = None
        result["d_grade"] = None
        result["d_base_rank"] = None
        result["d_raw"] = None
        result["d_detail"] = None
        result["vp_score"] = None
        return

    for key in _D_SUBSCORE_KEYS:
        value = d_result.get(key)
        result[key] = value
        result[f"{key}_rank"] = get_base_rank(value) if value is not None else None

    result["d_score"] = d_result.get("d_score")
    result["defensive_score"] = defensive_score
    result["d_grade"] = d_result.get("grade")
    result["d_base_rank"] = d_result.get("base_rank")
    result["d_raw"] = d_result.get("raw", {})
    result["d_detail"] = d_result.get("detail", {})
    result["vp_score"] = d_result.get("vp_score")
    result["vp_score"] = d_result.get("vp_score")
    result["vp_rank"]  = d_result.get("vp_rank")
    result["d_error"] = d_result.get("_d_error")
    result["vp_score"] = d_result.get("vp_score")
    result["vp_rank"] = d_result.get("vp_rank")
  


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
    # ─ D スコア関連 ─
    price_df: Optional[pd.DataFrame] = None,              # ★D Close/Low/Volume DataFrame
    bm_raw_vals: Optional[Dict[str, float]] = None,       # ★D ベンチマーク生値
    same_market_raw: Optional[Dict[str, Any]] = None,     # ★D σ推定用同市場生値
    d_weights: Optional[Dict[str, float]] = None,         # ★D 重み
    d_ma_period: int = 200,                               # ★D MAウィンドウ
    d_vol_ma_window: int = 20,                            # ★D 出来高MAウィンドウ
) -> Dict[str, Any]:
    """
    テクニカル指標 + Q/V/T スコアをまとめて計算し、UI 用の dict を返す。
    """

    t_block = compute_t_block(
        df=df,
        close_col=close_col,
        high_52w=high_52w,
        low_52w=low_52w,
    )
    df = t_block["df"]
    df_valid = t_block["df_valid"]
    tech_snapshot = t_block["snapshot"]
    price = tech_snapshot["close"]

    v_block = compute_v_block(
        price=price,
        eps=eps,
        bps=bps,
        dividend_yield=dividend_yield,
        eps_fwd=eps_fwd,
        per_fwd=per_fwd,
        ev_ebitda=ev_ebitda,
        sector_v_score=sector_v_score,
        is_us=is_us,
    )
    valuation_inputs = v_block["valuation_inputs"]
    per = valuation_inputs["per"]
    pbr = valuation_inputs["pbr"]
    t_metrics = t_block["t_metrics"]
    t_score = float(t_metrics["t_score"])

    q_block = compute_q_block(
        roe=roe, roa=roa, equity_ratio=equity_ratio,
        operating_margin=operating_margin,
        de_ratio=de_ratio,
        interest_coverage=interest_coverage,
        q_rel_scores=q_rel_scores,
        industry=industry,
        sector=sector,
        is_us=is_us,
    )
    q_result = q_block["q_result"]
    q_score = q_block["q_score"]
    v_result = v_block["v_result"]
    v_score = v_block["v_score"]


    # ── QVT 総合 ──
    #qvt_score = round((q_score + v_score + t_score) / 3.0, 1)
    # ── QVT 重み設定 ──
    WEIGHT_Q = 0.2621
    WEIGHT_V = 0.3258
    WEIGHT_T = 0.4122

    # ── QVT 総合スコア（加重平均） ──
    qvt_score = round(
        (q_score * WEIGHT_Q) +
        (v_score * WEIGHT_V) +
        (t_score * WEIGHT_T),
        1
    )
  

    # ── D スコア（price_df と bm_raw_vals が渡された場合のみ計算）──
    d_result: Dict[str, Any] = {}
    if price_df is not None and bm_raw_vals is not None:
        try:
            d_result = score_defense(
                df            = price_df,
                bm_raw_vals   = bm_raw_vals,
                same_market_raw = same_market_raw,
                ma_period     = d_ma_period,
                vol_ma_window = d_vol_ma_window,
                weights       = d_weights,
            )
        except Exception as _e:
            d_result = {"d_score": None, "defensive_score": None,
                        "grade": None, "base_rank": None,
                        "_d_error": str(_e)}

    # ── 返却 dict ──
    result: Dict[str, Any] = {
        # 生データ
        "df": df, "df_valid": df_valid,
        "close": price,

        # MA
        "ma_25": tech_snapshot["ma_25"], "ma_50": tech_snapshot["ma_50"], "ma_75": tech_snapshot["ma_75"],
        "slope_25": tech_snapshot["slope_25"], "slope_50": tech_snapshot["slope_50"], "slope_75": tech_snapshot["slope_75"],
        "arrow_25": tech_snapshot["arrow_25"], "arrow_50": tech_snapshot["arrow_50"], "arrow_75": tech_snapshot["arrow_75"],

        # BB
        "bb_plus1": tech_snapshot["bb_plus1"], "bb_plus2": tech_snapshot["bb_plus2"],
        "bb_minus1": tech_snapshot["bb_minus1"], "bb_minus2": tech_snapshot["bb_minus2"],

        "rsi": tech_snapshot["rsi"],
        "high_52w": high_52w, "low_52w": low_52w,

        # ファンダ（生）
        "eps": eps, "bps": bps, "eps_fwd": eps_fwd,
        "per": per, "pbr": pbr, "per_fwd": valuation_inputs["per_fwd"],
        "roe": roe, "roa": roa, "equity_ratio": equity_ratio,
        "operating_margin": operating_margin,   # ★v3
        "de_ratio": de_ratio,                   # ★v3
        "interest_coverage": interest_coverage, # ★v3
        "dividend_yield": dividend_yield,
        "ev_ebitda": ev_ebitda,                 # ★v3

        # Q サブスコア
        "q_score": q_score,
        **q_block["payload"],

        # V サブスコア
        "v_score": v_score,
        **v_block["payload"],

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

    # ── D スコアをマージ ──
    _merge_defense_result(result, d_result)

    return result
