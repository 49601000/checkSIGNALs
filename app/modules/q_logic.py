"""
q_logic.py  (v3.5)
────────────────────────────────────────────────────────────────────────────
Q（ビジネスの質）スコア — 業種別閾値CSV対応版

【v3.5 変更点】
  - 金融業のみ Q3絶対評価のER段階表を別ロジック化
  - _score_q3_abs() に industry / sector を渡して金融判定
  - 一般業種は従来のER段階表を維持
  - score_quality() から _score_q3_abs() 呼び出しを拡張

【設計意図】
  - JPM など金融株で、自己資本比率が業種基準を上回っているのに
    Q3が過小評価されやすい問題を緩和する
  - 他業種のスコアリングには極力影響を与えない
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any

import pandas as pd


# ─── 閾値DB ────────────────────────────────────────────────────────────────

_THRESHOLD_DB_TSE: Optional[Dict[str, Dict]] = None  # TSE: industry → 閾値
_THRESHOLD_DB_US: Optional[Dict[str, Dict]] = None   # US : sector  → 閾値

_DEFAULT_ER_THR = 10.0
_DEFAULT_IC_THR = 1.5


def _load_csv_to_dict(path: str, key_col: str) -> Dict[str, Dict]:
    df = pd.read_csv(path, encoding="utf-8-sig")
    return {
        str(row[key_col]).strip(): {
            "er": float(row["er_threshold_pct"]),
            "ic": float(row["ic_threshold_x"]),
            "note": str(row.get("note", "")),
        }
        for _, row in df.iterrows()
        if pd.notna(row.get(key_col))
    }

def _find_file(filenames: list) -> Optional[str]:
    """
    CSVを探す。q_logic.py は app/modules/ にあるので ../data/ = app/data/。
    os.path.abspath(__file__) で Streamlit Cloud でも確実にパスを解決する。
    """
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        rel_data = os.path.normpath(os.path.join(base, "..", "data"))
    except Exception:
        rel_data = None

    for name in filenames:
        candidates = []
        if rel_data:
            candidates.append(os.path.join(rel_data, name))
        candidates += [
            os.path.join("app", "data", name),
            os.path.join("data", name),
            name,
        ]
        for p in candidates:
            if os.path.exists(p):
                return os.path.abspath(p)
    return None


def _load_threshold_db_tse() -> Dict[str, Dict]:
    """TSE用: industry単位の閾値DB（CSVがあれば優先、なければビルトイン）"""
    global _THRESHOLD_DB_TSE
    if _THRESHOLD_DB_TSE is not None:
        return _THRESHOLD_DB_TSE
    path = _find_file(["industry_thresholds.csv"])
    try:
        _THRESHOLD_DB_TSE = _load_csv_to_dict(path, "industry") if path else _BUILTIN_TSE
    except Exception:
        _THRESHOLD_DB_TSE = _BUILTIN_TSE
    return _THRESHOLD_DB_TSE


def _load_threshold_db_us() -> Dict[str, Dict]:
    """US用: sector単位の閾値DB（CSVがあれば優先、なければビルトイン）"""
    global _THRESHOLD_DB_US
    if _THRESHOLD_DB_US is not None:
        return _THRESHOLD_DB_US
    path = _find_file(["industry_thresholds_us.csv"])
    try:
        _THRESHOLD_DB_US = _load_csv_to_dict(path, "sector") if path else _BUILTIN_US
    except Exception:
        _THRESHOLD_DB_US = _BUILTIN_US
    return _THRESHOLD_DB_US


def get_thresholds(industry: str, sector: str = "", is_us: bool = False) -> Dict[str, Any]:
    """
    市場に応じた閾値を返す。

    TSE（is_us=False）: industry_thresholds.csv を industry で引く
    US （is_us=True ）: industry_thresholds_us.csv を sector で引く

    Returns: {"er": float, "ic": float, "note": str, "custom": bool}
    """
    if is_us:
        db = _load_threshold_db_us()
        key = (sector or "").strip()
        if key and key in db:
            return {**db[key], "custom": True}
        if not key:
            key = (industry or "").strip()
            for db_key, val in db.items():
                if key and db_key.lower() in key.lower():
                    return {**val, "custom": True}
    else:
        db = _load_threshold_db_tse()
        key = (industry or "").strip()
        if key and key in db:
            return {**db[key], "custom": True}
        for db_key, val in db.items():
            if key and (key.lower() in db_key.lower() or db_key.lower() in key.lower()):
                return {**val, "custom": True}

    return {"er": _DEFAULT_ER_THR, "ic": _DEFAULT_IC_THR, "note": "標準基準", "custom": False}


# ─── 重みデータクラス ─────────────────────────────────────────────────────

@dataclass
class QWeights:
    """絶対評価ステップ関数の重みパラメータ。Optuna/スライダーから差し込む。"""
    roe_w: float = 50.0
    roa_w: float = 25.0
    opm_w: float = 25.0
    er_w: float = 40.0
    de_w: float = 30.0
    ic_w: float = 30.0
    w_q1: float = 0.50
    w_q3: float = 0.50
    ko_ic: float = 15.0
    ko_er: float = 15.0
    ko_opm: float = 15.0


DEFAULT_WEIGHTS = QWeights()


# ─── Q1: 収益性（絶対評価） ───────────────────────────────────────────────

def _score_q1_abs(roe, roa, operating_margin, w: QWeights) -> float:
    raw = 0.0
    if roe is not None:
        r = (
            0 if roe <= 0 else
            0.20 if roe < 5 else
            0.40 if roe < 10 else
            0.60 if roe < 15 else
            0.80 if roe < 20 else
            0.90 if roe < 25 else
            1.00
        )
        raw += w.roe_w * r
    if roa is not None:
        r = (
            0 if roa <= 0 else
            0.20 if roa < 2 else
            0.40 if roa < 4 else
            0.60 if roa < 6 else
            0.80 if roa < 8 else
            1.00
        )
        raw += w.roa_w * r
    if operating_margin is not None:
        r = (
            0 if operating_margin <= 0 else
            0.20 if operating_margin < 3 else
            0.40 if operating_margin < 7 else
            0.60 if operating_margin < 12 else
            0.80 if operating_margin < 20 else
            1.00
        )
        raw += w.opm_w * r

    max_raw = w.roe_w + w.roa_w + w.opm_w
    return 0.0 if max_raw == 0 else max(0.0, min(100.0, raw / max_raw * 100.0))


# ─── Q3: 財務健全性（絶対評価） ──────────────────────────────────────────

def _is_financial_industry(industry: str = "", sector: str = "") -> bool:
    """
    金融業かどうかをざっくり判定する。
    TSEは industry ベース、USは sector='Financial Services' を主に想定。
    """
    ind = (industry or "").lower()
    sec = (sector or "").lower()
    text = f"{ind} {sec}"

    financial_keywords = [
        "bank", "banks",
        "insurance",
        "capital markets",
        "asset management",
        "credit services",
        "mortgage finance",
        "financial conglomerates",
        "financial services",
        "securities",
        "leasing",
        "rental & leasing",
    ]
    return any(k in text for k in financial_keywords)


def _score_er_general(equity_ratio: float, er_thr: float) -> float:
    """
    一般業種向けのER段階表（従来ロジック）。
    """
    ratio = equity_ratio / er_thr if er_thr > 0 else 0
    return (
        0.000 if ratio < 1.0 else
        0.125 if ratio < 2.0 else
        0.250 if ratio < 3.0 else
        0.500 if ratio < 4.0 else
        0.750 if ratio < 5.0 else
        0.875 if ratio < 6.0 else
        1.000
    )


def _score_er_financial(
    equity_ratio: float,
    er_thr: float,
    industry: str = "",
    sector: str = "",
) -> float:
    """
    金融業向けのER段階表。
    一般業種よりも、閾値を少し上回った段階で点が入りやすいように調整。

    基本思想:
      - 閾値未満        -> 0.000
      - 1.00x〜1.25x   -> 0.350
      - 1.25x〜1.50x   -> 0.500
      - 1.50x〜2.00x   -> 0.650
      - 2.00x〜2.50x   -> 0.800
      - 2.50x〜3.00x   -> 0.900
      - 3.00x以上      -> 1.000

    例）JPM / US金融基準 er_thr=6.0%, equity_ratio=8.4%
        ratio=1.40 → 0.500
    """
    ratio = equity_ratio / er_thr if er_thr > 0 else 0

    return (
        0.000 if ratio < 1.0 else
        0.350 if ratio < 1.25 else
        0.500 if ratio < 1.50 else
        0.650 if ratio < 2.00 else
        0.800 if ratio < 2.50 else
        0.900 if ratio < 3.00 else
        1.000
    )


def _score_q3_abs(
    equity_ratio,
    de_ratio,
    interest_coverage,
    w: QWeights,
    er_thr: float = 10.0,
    ic_thr: float = 1.5,
    industry: str = "",
    sector: str = "",
) -> float:
    """
    ER・ICの採点ステップを業種別閾値（er_thr / ic_thr）に対して相対化する。

    変更点:
      - 一般業種は従来のER段階表を使う
      - 金融業だけER段階表を別ロジックにする
      - D/E, IC のロジックは現状維持
    """
    raw = 0.0
    is_financial = _is_financial_industry(industry, sector)

    if equity_ratio is not None:
        if is_financial:
            r = _score_er_financial(
                equity_ratio=equity_ratio,
                er_thr=er_thr,
                industry=industry,
                sector=sector,
            )
        else:
            r = _score_er_general(equity_ratio=equity_ratio, er_thr=er_thr)
        raw += w.er_w * r

    if de_ratio is not None:
        r = (
            0.000 if de_ratio > 3.0 else
            0.167 if de_ratio > 2.0 else
            0.333 if de_ratio > 1.5 else
            0.500 if de_ratio > 1.0 else
            0.733 if de_ratio > 0.5 else
            1.000
        )
        raw += w.de_w * r

    if interest_coverage is not None:
        ratio_ic = interest_coverage / ic_thr if ic_thr > 0 else 0
        r = (
            0.000 if ratio_ic < 1.0 else
            0.267 if ratio_ic < 2.0 else
            0.500 if ratio_ic < 3.0 else
            0.733 if ratio_ic < 6.0 else
            0.900 if ratio_ic < 13.0 else
            1.000
        )
        raw += w.ic_w * r

    max_raw = w.er_w + w.de_w + w.ic_w
    return 0.0 if max_raw == 0 else max(0.0, min(100.0, raw / max_raw * 100.0))


# ─── 相対評価 ─────────────────────────────────────────────────────────────

def _score_q1_rel(q_rel: Dict[str, Any]) -> Optional[float]:
    scores, weights = [], []
    for key, wt in [("roe_rel", 2.0), ("roa_rel", 1.0), ("opm_rel", 1.0)]:
        v = q_rel.get(key)
        if v is not None:
            scores.append(v * wt)
            weights.append(wt)
    return sum(scores) / sum(weights) if scores else None


def _score_q3_rel(q_rel: Dict[str, Any]) -> Optional[float]:
    scores, weights = [], []
    for key, wt in [("er_rel", 2.0), ("ic_rel", 1.5)]:
        v = q_rel.get(key)
        if v is not None:
            scores.append(v * wt)
            weights.append(wt)
    return sum(scores) / sum(weights) if scores else None


# ─── ノックアウト判定（業種別閾値CSV対応） ───────────────────────────────

def _knockout_penalty(
    operating_margin: Optional[float],
    equity_ratio: Optional[float],
    interest_coverage: Optional[float],
    w: QWeights,
    industry: str = "",
    sector: str = "",
    is_us: bool = False,
) -> Tuple[float, List[str]]:
    """
    industry_thresholds.csv から閾値を取得してノックアウト判定。
    CSVに未収録の業種はデフォルト値（ER:10%, IC:1.5x）を使用。
    """
    penalty: float = 0.0
    warnings: List[str] = []

    thr = get_thresholds(industry, sector, is_us=is_us)
    er_thr = thr["er"]
    ic_thr = thr["ic"]
    note = thr["note"]
    custom = thr["custom"]

    if interest_coverage is not None and interest_coverage < ic_thr:
        penalty += w.ko_ic
        warnings.append(
            f"⚠️ インタレストカバレッジ {interest_coverage:.1f}x"
            f"（{'業種基準' if custom else '標準基準'} {ic_thr:.1f}x 未満）"
        )

    if equity_ratio is not None and equity_ratio < er_thr:
        penalty += w.ko_er
        warnings.append(
            f"⚠️ 自己資本比率 {equity_ratio:.1f}%"
            f"（{note} {er_thr:.0f}% 未満）"
        )

    if operating_margin is not None and operating_margin < 0:
        penalty += w.ko_opm
        warnings.append(f"⚠️ 営業利益率 {operating_margin:.1f}%（営業赤字）")

    return penalty, warnings


# ─── メイン: score_quality ───────────────────────────────────────────────

def score_quality(
    roe: Optional[float],
    roa: Optional[float],
    equity_ratio: Optional[float],
    operating_margin: Optional[float] = None,
    de_ratio: Optional[float] = None,
    interest_coverage: Optional[float] = None,
    weights: Optional[QWeights] = None,
    q_rel_scores: Optional[Dict[str, Any]] = None,
    industry: str = "",
    sector: str = "",
    is_us: bool = False,
) -> dict:
    """
    Q スコアを計算して dict で返す。

    Parameters
    ----------
    industry : str
        yfinance / TSEマスターの industry 文字列
    sector : str
        yfinance / TSEマスターの sector 文字列（マッチング補助用）

    Returns
    -------
    {
        "q_score", "q1", "q3",
        "q1_abs", "q3_abs", "q1_rel", "q3_rel",
        "alpha", "penalty", "warnings", "weights",
        "er_threshold", "ic_threshold", "threshold_note",
    }
    """
    w = weights if weights is not None else DEFAULT_WEIGHTS

    q1_abs = _score_q1_abs(roe, roa, operating_margin, w)

    _thr = get_thresholds(industry, sector, is_us=is_us)
    q3_abs = _score_q3_abs(
        equity_ratio=equity_ratio,
        de_ratio=de_ratio,
        interest_coverage=interest_coverage,
        w=w,
        er_thr=_thr["er"],
        ic_thr=_thr["ic"],
        industry=industry,
        sector=sector,
    )

    alpha, q1_rel, q3_rel = 0.0, None, None
    if q_rel_scores and q_rel_scores.get("available"):
        alpha = float(q_rel_scores.get("alpha", 0.0))
        q1_rel = _score_q1_rel(q_rel_scores)
        q3_rel = _score_q3_rel(q_rel_scores)

    def _blend(a, r, al):
        return a if (r is None or al == 0.0) else a * (1 - al) + r * al

    q1 = _blend(q1_abs, q1_rel, alpha)
    q3 = _blend(q3_abs, q3_rel, alpha)

    total_w = w.w_q1 + w.w_q3
    q_raw = (q1 * w.w_q1 + q3 * w.w_q3) / total_w if total_w > 0 else 0.0

    penalty, warnings = _knockout_penalty(
        operating_margin=operating_margin,
        equity_ratio=equity_ratio,
        interest_coverage=interest_coverage,
        w=w,
        industry=industry,
        sector=sector,
        is_us=is_us,
    )
    effective_penalty = penalty * (1.0 - alpha * 0.5)
    q_final = max(0.0, min(100.0, q_raw - effective_penalty))

    thr = get_thresholds(industry, sector, is_us=is_us)
    return {
        "q_score": round(q_final, 1),
        "q1": round(q1, 1),
        "q3": round(q3, 1),
        "q1_abs": round(q1_abs, 1),
        "q3_abs": round(q3_abs, 1),
        "q1_rel": round(q1_rel, 1) if q1_rel is not None else None,
        "q3_rel": round(q3_rel, 1) if q3_rel is not None else None,
        "alpha": alpha,
        "penalty": effective_penalty,
        "warnings": warnings,
        "weights": w,
        "er_threshold": thr["er"],
        "ic_threshold": thr["ic"],
        "threshold_note": thr["note"],
    }
