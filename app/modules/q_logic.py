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

DEFAULT_Q_WEIGHTS = {
    "w_q1": 0.50,
    "w_q3": 0.50,
}

CUSTOM_Q_WEIGHTS_BT = {
    "w_q1": 0.1164,
    "w_q3": 0.8836,
}


def _build_qweights(
    base: Optional[QWeights] = None,
    custom_q_weights: Optional[Dict[str, float]] = None,
) -> QWeights:
    """
    QWeights を生成する。
    - base があればそれをベースに使う
    - custom_q_weights があれば w_q1 / w_q3 を上書き
    - 合計が1でなくても内部で正規化する
    """
    src = base if base is not None else DEFAULT_WEIGHTS

    w = QWeights(
        roe_w=src.roe_w,
        roa_w=src.roa_w,
        opm_w=src.opm_w,
        er_w=src.er_w,
        de_w=src.de_w,
        ic_w=src.ic_w,
        w_q1=src.w_q1,
        w_q3=src.w_q3,
        ko_ic=src.ko_ic,
        ko_er=src.ko_er,
        ko_opm=src.ko_opm,
    )

    if custom_q_weights is None:
        return w

    q1 = float(custom_q_weights.get("w_q1", w.w_q1))
    q3 = float(custom_q_weights.get("w_q3", w.w_q3))

    total = q1 + q3
    if total <= 0:
        raise ValueError(f"Invalid Q weights: w_q1 + w_q3 must be > 0, got {total}")

    w.w_q1 = q1 / total
    w.w_q3 = q3 / total

    return w

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
    銀行Q1（調整版）
      - ROEを主軸
      - ROAは銀行専用レンジ
      - 営業利益率はさらに軽い補助指標
      - 欠損項目は分母から外す
    """
    raw = 0.0
    max_raw = 0.0

    # ROE: 銀行向け
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

    # ROA: 銀行専用レンジ
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

    # 営業利益率: さらに軽くする（従来 0.50倍 → 今回 0.25倍）
    bank_opm_weight = w.opm_w * 0.25
    if operating_margin is not None:
        r = (
            0.00 if operating_margin <= 0 else
            0.25 if operating_margin < 5 else
            0.40 if operating_margin < 10 else
            0.55 if operating_margin < 20 else
            0.70 if operating_margin < 30 else
            0.82 if operating_margin < 40 else
            0.90
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
    weight_factor: float = 0.8,  # ← 自己資本比率影響度の微調整係数
) -> float:
    """
    銀行Q3（係数調整版）
      - 自己資本比率のみで段階評価
      - 最終スコアに係数を掛けて影響度を微調整
      - 4%未満は厳しめ維持
    """
    if equity_ratio is None:
        return 0.0

    x = equity_ratio

    if x < er_thr:
        base_score = 0.0
    elif x < 4.2:
        base_score = 28.0
    elif x < 4.5:
        base_score = 38.0
    elif x < 5.0:
        base_score = 50.0
    elif x < 5.5:
        base_score = 65.0
    elif x < 6.0:
        base_score = 75.0
    elif x < 7.0:
        base_score = 85.0
    elif x < 8.0:
        base_score = 92.0
    else:
        base_score = 100.0
    # 影響度を微調整
    adjusted_score = base_score * weight_factor

    return adjusted_score

def _score_q3_abs(
    equity_ratio: Optional[float],
    de_ratio: Optional[float],
    interest_coverage: Optional[float],
    w: QWeights,
    er_thr: float = 10.0,
    ic_thr: float = 1.5,
    industry: str = "",
    sector: str = "",
    roe: Optional[float] = None,
) -> float:
    """
    一般業種:
      - ER / D/E / IC の3本柱
    銀行:
      - 自己資本比率のみで採点
    その他金融:
      - ERは金融向け、D/E / ICは従来どおり
    超高収益企業（ROE >= 50%）:
      - 自己資本比率の閾値を緩和（積極的自社株買いによる資本圧縮を考慮）
    """
    if _is_bank_industry(industry, sector):
        return _score_q3_abs_bank(equity_ratio=equity_ratio, er_thr=er_thr)

    # 超高収益企業は自己資本比率閾値を緩和してスコアリング
    # ROE >= 100%: er_thrを0.4倍に縮小（閾値を大幅緩和）
    # ROE >= 50% : er_thrを0.6倍に縮小（閾値を中程度緩和）
    effective_er_thr = er_thr
    if equity_ratio is not None and roe is not None:
        if roe >= 100.0:
            effective_er_thr = er_thr * 0.4
        elif roe >= 50.0:
            effective_er_thr = er_thr * 0.6

    raw = 0.0

    is_financial = _is_financial_industry(industry, sector)

    if equity_ratio is not None:
        if is_financial:
            r = _score_er_financial(equity_ratio, effective_er_thr, industry=industry, sector=sector)
        else:
            r = _score_er_general(equity_ratio, effective_er_thr)
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
    roe: Optional[float] = None,
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
        # ROEが高い超高収益企業（積極的な自社株買いによる資本圧縮）は
        # 財務的脆弱性ではなくレバレッジ活用と判断し、警告・ペナルティを軽減する
        _HIGH_ROE_THRESHOLD = 50.0   # ROE ≥ 50%：高収益レバレッジとみなす基準
        _VERY_HIGH_ROE_THRESHOLD = 100.0  # ROE ≥ 100%：超高収益（Apple等）

        if roe is not None and roe >= _VERY_HIGH_ROE_THRESHOLD:
            # ペナルティなし、情報提供のみ（警告アイコンなし）
            warnings.append(
                f"ℹ️ 自己資本比率 {equity_ratio:.1f}%"
                f"（{note} {er_thr:.0f}% 未満）"
                f" ／ ROE {roe:.0f}% — 高収益による資本効率化レバレッジ（財務リスクは低い）"
            )
        elif roe is not None and roe >= _HIGH_ROE_THRESHOLD:
            # ペナルティ半減、補足コメント付き警告
            penalty += w.ko_er * 0.5
            warnings.append(
                f"⚠️ 自己資本比率 {equity_ratio:.1f}%"
                f"（{note} {er_thr:.0f}% 未満）"
                f" ／ ROE {roe:.0f}% — 高収益構造によるレバレッジの可能性あり"
            )
        else:
            # 通常の警告・ペナルティ
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
    custom_q_weights: Optional[Dict[str, float]] = None,
) -> dict:
    """
    Q スコアを計算して dict で返す。

    Parameters
    ----------
    weights : Optional[QWeights]
        Q全体の基礎ウェイト。未指定なら DEFAULT_WEIGHTS。
    custom_q_weights : Optional[Dict[str, float]]
        Q内部の q1 / q3 の重みだけ上書きしたいときに使う。
        例:
            {"w_q1": 0.50, "w_q3": 0.50}      # default相当
            {"w_q1": 0.1164, "w_q3": 0.8836}  # バックテスト結果
    """
    w = _build_qweights(base=weights, custom_q_weights=custom_q_weights)

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
        roe=roe,
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
        roe=roe,
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
        "q_weights_used": {
            "w_q1": round(w.w_q1, 6),
            "w_q3": round(w.w_q3, 6),
        },
        "er_threshold": thr["er"],
        "ic_threshold": thr["ic"],
        "threshold_note": thr["note"],
    }


def compute_q_block(
    roe: Optional[float],
    roa: Optional[float],
    equity_ratio: Optional[float],
    operating_margin: Optional[float] = None,
    de_ratio: Optional[float] = None,
    interest_coverage: Optional[float] = None,
    q_rel_scores: Optional[Dict[str, Any]] = None,
    industry: str = "",
    sector: str = "",
    is_us: bool = False,
) -> Dict[str, Any]:
    """
    indicators 向けに Q スコア結果を整形したブロックを返す。
    """
    q_result = score_quality(
        roe=roe,
        roa=roa,
        equity_ratio=equity_ratio,
        operating_margin=operating_margin,
        de_ratio=de_ratio,
        interest_coverage=interest_coverage,
        q_rel_scores=q_rel_scores,
        industry=industry,
        sector=sector,
        is_us=is_us,
    )
    return {
        "q_result": q_result,
        "q_score": q_result["q_score"],
        "payload": {
            "q1": q_result["q1"],
            "q3": q_result["q3"],
            "q_warnings": q_result["warnings"],
            "er_threshold": q_result.get("er_threshold", 10.0),
            "ic_threshold": q_result.get("ic_threshold", 1.5),
            "threshold_note": q_result.get("threshold_note", "標準基準"),
        },
    }
