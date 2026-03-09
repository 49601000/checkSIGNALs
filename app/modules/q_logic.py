"""
q_logic.py  (v4.0 provisional)
────────────────────────────────────────────────────────────────────────────
Q（ビジネスの質）スコア — 業種別閾値CSV対応版

【v4.0 変更点】
  - 銀行業だけ Q1 / Q3 を専用段階表で採点
  - 銀行Q1:
      * ROE = 銀行向けレンジ
      * ROA = 銀行向けレンジ
      * 営業利益率 = 補助指標
      * 欠損項目は available-weight 正規化
  - 銀行Q3:
      * 自己資本比率のみで100点化
      * BIS Tier1 目安 4%近辺を細かく刻む
  - 一般業種は従来ロジックを維持

【設計意図】
  - 一般事業会社（例: トヨタ）と銀行で指標の意味が違う問題を緩和
  - 銀行だけ別物差しで採点し、最終的には同じ 0–100 スケールに載せる
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any

import pandas as pd


# ─── 閾値DB ────────────────────────────────────────────────────────────────

_THRESHOLD_DB_TSE: Optional[Dict[str, Dict]] = None
_THRESHOLD_DB_US: Optional[Dict[str, Dict]] = None

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


# ─── 重み ──────────────────────────────────────────────────────────────────

@dataclass
class QWeights:
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


# ─── 業種判定 ──────────────────────────────────────────────────────────────

def _is_financial_industry(industry: str = "", sector: str = "") -> bool:
    ind = (industry or "").lower()
    sec = (sector or "").lower()
    text = f"{ind} {sec}"
    keywords = [
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
    return any(k in text for k in keywords)


def _is_bank_industry(industry: str = "", sector: str = "") -> bool:
    ind = (industry or "").lower()
    sec = (sector or "").lower()
    text = f"{ind} {sec}"
    bank_keywords = [
        "bank", "banks",
        "regional bank",
        "regional banks",
        "diversified bank",
        "diversified banks",
    ]
    return any(k in text for k in bank_keywords)


# ─── Q1: 一般業種 ──────────────────────────────────────────────────────────

def _score_q1_abs_general(
    roe: Optional[float],
    roa: Optional[float],
    operating_margin: Optional[float],
    w: QWeights,
) -> float:
    raw = 0.0

    if roe is not None:
        r = (
            0.00 if roe <= 0 else
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
            0.00 if roa <= 0 else
            0.20 if roa < 2 else
            0.40 if roa < 4 else
            0.60 if roa < 6 else
            0.80 if roa < 8 else
            1.00
        )
        raw += w.roa_w * r

    if operating_margin is not None:
        r = (
            0.00 if operating_margin <= 0 else
            0.20 if operating_margin < 3 else
            0.40 if operating_margin < 7 else
            0.60 if operating_margin < 12 else
            0.80 if operating_margin < 20 else
            1.00
        )
        raw += w.opm_w * r

    max_raw = w.roe_w + w.roa_w + w.opm_w
    return 0.0 if max_raw == 0 else max(0.0, min(100.0, raw / max_raw * 100.0))


# ─── Q1: 銀行専用 ──────────────────────────────────────────────────────────

def _score_q1_abs_bank(
    roe: Optional[float],
    roa: Optional[float],
    operating_margin: Optional[float],
    w: QWeights,
) -> float:
    """
    銀行Q1（暫定版）
      - ROEを主軸
      - ROAは銀行専用レンジ
      - 営業利益率は補助指標
      - 欠損項目は分母から外す
    """
    raw = 0.0
    max_raw = 0.0

    # ROE: 銀行向けにやや厳しすぎない刻み
    if roe is not None:
        r = (
            0.00 if roe <= 0 else
            0.20 if roe < 3 else
            0.35 if roe < 5 else
            0.50 if roe < 8 else
            0.65 if roe < 10 else
            0.80 if roe < 12 else
            0.90 if roe < 15 else
            1.00
        )
        raw += w.roe_w * r
        max_raw += w.roe_w

    # ROA: 銀行は一般企業より低いので専用レンジ
    if roa is not None:
        r = (
            0.00 if roa <= 0 else
            0.15 if roa < 0.10 else
            0.30 if roa < 0.20 else
            0.45 if roa < 0.30 else
            0.60 if roa < 0.40 else
            0.72 if roa < 0.50 else
            0.82 if roa < 0.60 else
            0.90 if roa < 0.80 else
            1.00
        )
        raw += w.roa_w * r
        max_raw += w.roa_w

    # 営業利益率: 補助指標。定義差が大きいので軽く扱う
    bank_opm_weight = w.opm_w * 0.50
    if operating_margin is not None:
        r = (
            0.00 if operating_margin <= 0 else
            0.30 if operating_margin < 5 else
            0.50 if operating_margin < 10 else
            0.65 if operating_margin < 20 else
            0.80 if operating_margin < 30 else
            0.90 if operating_margin < 40 else
            1.00
        )
        raw += bank_opm_weight * r
        max_raw += bank_opm_weight

    return 0.0 if max_raw == 0 else max(0.0, min(100.0, raw / max_raw * 100.0))


def _score_q1_abs(
    roe: Optional[float],
    roa: Optional[float],
    operating_margin: Optional[float],
    w: QWeights,
    industry: str = "",
    sector: str = "",
) -> float:
    if _is_bank_industry(industry, sector):
        return _score_q1_abs_bank(roe, roa, operating_margin, w)
    return _score_q1_abs_general(roe, roa, operating_margin, w)


# ─── Q3: 一般業種 / 金融一般 ─────────────────────────────────────────────

def _score_er_general(equity_ratio: float, er_thr: float) -> float:
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


# ─── Q3: 銀行専用 ──────────────────────────────────────────────────────────

def _score_q3_abs_bank(
    equity_ratio: Optional[float],
    er_thr: float = 4.0,
) -> float:
    """
    銀行Q3（暫定版）
      - 自己資本比率のみで100点化
      - 4%付近の立ち上がりを細かく刻む
      - 4%未満はかなり厳しめ
    """
    if equity_ratio is None:
        return 0.0

    x = equity_ratio

    # er_thr を将来変える余地は残すが、暫定的には 4% 近辺を重視
    if x < er_thr:
        return 0.0
    elif x < 4.2:
        return 35.0
    elif x < 4.5:
        return 45.0
    elif x < 5.0:
        return 55.0
    elif x < 5.5:
        return 65.0
    elif x < 6.0:
        return 75.0
    elif x < 7.0:
        return 85.0
    elif x < 8.0:
        return 92.0
    else:
        return 100.0


def _score_q3_abs(
    equity_ratio: Optional[float],
    de_ratio: Optional[float],
    interest_coverage: Optional[float],
    w: QWeights,
    er_thr: float = 10.0,
    ic_thr: float = 1.5,
    industry: str = "",
    sector: str = "",
) -> float:
    """
    一般業種:
      - ER / D/E / IC の3本柱
    銀行:
      - 自己資本比率のみで採点
    その他金融:
      - ERは金融向け、D/E / ICは従来どおり
    """
    if _is_bank_industry(industry, sector):
        return _score_q3_abs_bank(equity_ratio=equity_ratio, er_thr=er_thr)

    raw = 0.0

    is_financial = _is_financial_industry(industry, sector)

    if equity_ratio is not None:
        if is_financial:
            r = _score_er_financial(equity_ratio, er_thr, industry=industry, sector=sector)
        else:
            r = _score_er_general(equity_ratio, er_thr)
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


# ─── ノックアウト ─────────────────────────────────────────────────────────

def _knockout_penalty(
    operating_margin: Optional[float],
    equity_ratio: Optional[float],
    interest_coverage: Optional[float],
    w: QWeights,
    industry: str = "",
    sector: str = "",
    is_us: bool = False,
) -> Tuple[float, List[str]]:
    penalty: float = 0.0
    warnings: List[str] = []

    thr = get_thresholds(industry, sector, is_us=is_us)
    er_thr = thr["er"]
    ic_thr = thr["ic"]
    note = thr["note"]
    custom = thr["custom"]

    # 銀行は IC を実務上使わない前提に寄せる
    is_bank = _is_bank_industry(industry, sector)

    if (not is_bank) and interest_coverage is not None and interest_coverage < ic_thr:
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

    # 銀行では営業利益率のノックアウトは使わない
    if (not is_bank) and operating_margin is not None and operating_margin < 0:
        penalty += w.ko_opm
        warnings.append(f"⚠️ 営業利益率 {operating_margin:.1f}%（営業赤字）")

    return penalty, warnings


# ─── メイン ───────────────────────────────────────────────────────────────

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
    """
    w = weights if weights is not None else DEFAULT_WEIGHTS

    q1_abs = _score_q1_abs(
        roe=roe,
        roa=roa,
        operating_margin=operating_margin,
        w=w,
        industry=industry,
        sector=sector,
    )

    thr = get_thresholds(industry, sector, is_us=is_us)
    q3_abs = _score_q3_abs(
        equity_ratio=equity_ratio,
        de_ratio=de_ratio,
        interest_coverage=interest_coverage,
        w=w,
        er_thr=thr["er"],
        ic_thr=thr["ic"],
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
