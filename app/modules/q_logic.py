"""
q_logic.py  (v3.2)
────────────────────────────────────────────────────────────────────────────
Q（ビジネスの質）スコア — 相対評価ブレンド対応版

【v3.2 変更点】
  - score_quality() に q_rel_scores 引数を追加
  - q_rel_scores が渡された場合、絶対評価と相対評価をαブレンド
    Q1_final = Q1_abs × (1-α) + Q1_rel × α
    Q3_final = Q3_abs × (1-α) + Q3_rel × α
  - α は財務タイプの confidence から決まる（pattern_db.py が計算）
    HIGH  → 0.7（相対70%、絶対30%）
    MID   → 0.4（相対40%、絶対60%）
    LOW   → 0.1
    NONE  → 0.0（絶対評価のみ、UNK・未推定銘柄）

【表示への影響なし】
  実測値（ROE 11.5%など）はそのまま表示。採点ロジックだけが変わる。

【QWeights】
  絶対評価部分のステップ関数の重みは QWeights で制御（v3.1互換）。
  相対評価部分は pattern_db の IQR ベースで自動スケール。
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any


# ─── 重みデータクラス（絶対評価部分） ────────────────────────────────────

@dataclass
class QWeights:
    """絶対評価ステップ関数の重みパラメータ。Optuna/スライダーから差し込む。"""

    # Q1 サブスコア内の寄与率（各指標の「最大点」）
    roe_w: float = 50.0
    roa_w: float = 25.0
    opm_w: float = 25.0

    # Q3 サブスコア内の寄与率（各指標の「最大点」）
    er_w:  float = 40.0
    de_w:  float = 30.0
    ic_w:  float = 30.0

    # Q1 / Q3 の合成ウェイト
    w_q1: float = 0.50
    w_q3: float = 0.50

    # ノックアウトペナルティ点数
    ko_ic:  float = 15.0
    ko_er:  float = 15.0
    ko_opm: float = 15.0


DEFAULT_WEIGHTS = QWeights()


# ─── Q1: 収益性（絶対評価） ───────────────────────────────────────────────

def _score_q1_abs(
    roe: Optional[float],
    roa: Optional[float],
    operating_margin: Optional[float],
    w: QWeights,
) -> float:
    raw = 0.0
    if roe is not None:
        if roe <= 0:    r = 0.00
        elif roe < 5:   r = 0.20
        elif roe < 10:  r = 0.40
        elif roe < 15:  r = 0.60
        elif roe < 20:  r = 0.80
        elif roe < 25:  r = 0.90
        else:           r = 1.00
        raw += w.roe_w * r

    if roa is not None:
        if roa <= 0:   r = 0.00
        elif roa < 2:  r = 0.20
        elif roa < 4:  r = 0.40
        elif roa < 6:  r = 0.60
        elif roa < 8:  r = 0.80
        else:          r = 1.00
        raw += w.roa_w * r

    if operating_margin is not None:
        if operating_margin <= 0:    r = 0.00
        elif operating_margin < 3:   r = 0.20
        elif operating_margin < 7:   r = 0.40
        elif operating_margin < 12:  r = 0.60
        elif operating_margin < 20:  r = 0.80
        else:                        r = 1.00
        raw += w.opm_w * r

    max_raw = w.roe_w + w.roa_w + w.opm_w
    return 0.0 if max_raw == 0 else max(0.0, min(100.0, raw / max_raw * 100.0))


# ─── Q3: 財務健全性（絶対評価） ──────────────────────────────────────────

def _score_q3_abs(
    equity_ratio: Optional[float],
    de_ratio: Optional[float],
    interest_coverage: Optional[float],
    w: QWeights,
) -> float:
    raw = 0.0
    if equity_ratio is not None:
        if equity_ratio < 10:    r = 0.000
        elif equity_ratio < 20:  r = 0.125
        elif equity_ratio < 30:  r = 0.250
        elif equity_ratio < 40:  r = 0.500
        elif equity_ratio < 50:  r = 0.750
        elif equity_ratio < 60:  r = 0.875
        else:                    r = 1.000
        raw += w.er_w * r

    if de_ratio is not None:
        if de_ratio > 3.0:   r = 0.000
        elif de_ratio > 2.0: r = 0.167
        elif de_ratio > 1.5: r = 0.333
        elif de_ratio > 1.0: r = 0.500
        elif de_ratio > 0.5: r = 0.733
        else:                r = 1.000
        raw += w.de_w * r

    if interest_coverage is not None:
        if interest_coverage < 1.5:   r = 0.000
        elif interest_coverage < 3:   r = 0.267
        elif interest_coverage < 5:   r = 0.500
        elif interest_coverage < 10:  r = 0.733
        elif interest_coverage < 20:  r = 0.900
        else:                         r = 1.000
        raw += w.ic_w * r

    max_raw = w.er_w + w.de_w + w.ic_w
    return 0.0 if max_raw == 0 else max(0.0, min(100.0, raw / max_raw * 100.0))


# ─── Q1: 収益性（相対評価） ───────────────────────────────────────────────

def _score_q1_rel(q_rel: Dict[str, Any]) -> Optional[float]:
    """
    pattern_db から受け取った相対スコアで Q1 を計算。
    有効な指標の加重平均（ROE:2, ROA:1, OPM:1）。
    """
    scores = []
    weights = []
    for key, w in [("roe_rel", 2.0), ("roa_rel", 1.0), ("opm_rel", 1.0)]:
        v = q_rel.get(key)
        if v is not None:
            scores.append(v * w)
            weights.append(w)
    if not scores:
        return None
    return sum(scores) / sum(weights)


# ─── Q3: 財務健全性（相対評価） ──────────────────────────────────────────

def _score_q3_rel(q_rel: Dict[str, Any]) -> Optional[float]:
    """
    pattern_db から受け取った相対スコアで Q3 を計算。
    有効な指標の加重平均（ER:2, IC:1.5, D/Eはpattern_dbに中央値なし→スキップ）。
    """
    scores = []
    weights = []
    for key, w in [("er_rel", 2.0), ("ic_rel", 1.5)]:
        v = q_rel.get(key)
        if v is not None:
            scores.append(v * w)
            weights.append(w)
    if not scores:
        return None
    return sum(scores) / sum(weights)


# ─── ノックアウト判定 ────────────────────────────────────────────────────

def _knockout_penalty(
    operating_margin: Optional[float],
    equity_ratio: Optional[float],
    interest_coverage: Optional[float],
    w: QWeights,
) -> Tuple[float, List[str]]:
    penalty: float = 0.0
    warnings: List[str] = []

    if interest_coverage is not None and interest_coverage < 1.5:
        penalty += w.ko_ic
        warnings.append(f"⚠️ インタレストカバレッジ {interest_coverage:.1f}x（利払い能力に懸念）")

    if equity_ratio is not None and equity_ratio < 10:
        penalty += w.ko_er
        warnings.append(f"⚠️ 自己資本比率 {equity_ratio:.1f}%（過剰レバレッジ）")

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
    q_rel_scores: Optional[Dict[str, Any]] = None,  # ★v3.2 pattern_db から注入
) -> dict:
    """
    Q スコアを計算して dict で返す。

    Parameters
    ----------
    q_rel_scores : pattern_db.calc_q_relative_scores() の返り値。
        None の場合は絶対評価のみ（UNK・未収録銘柄）。
        渡された場合は alpha ブレンドで絶対評価と相対評価を合成。

    Returns
    -------
    {
        "q_score"     : float,
        "q1"          : float,
        "q3"          : float,
        "q1_abs"      : float,   # 絶対評価Q1（デバッグ・表示用）
        "q3_abs"      : float,
        "q1_rel"      : float or None,  # 相対評価Q1
        "q3_rel"      : float or None,
        "alpha"       : float,   # ブレンド係数
        "penalty"     : float,
        "warnings"    : list[str],
        "weights"     : QWeights,
    }
    """
    w = weights if weights is not None else DEFAULT_WEIGHTS

    # ── 絶対評価 ──
    q1_abs = _score_q1_abs(roe, roa, operating_margin, w)
    q3_abs = _score_q3_abs(equity_ratio, de_ratio, interest_coverage, w)

    # ── 相対評価（注入された場合のみ） ──
    alpha  = 0.0
    q1_rel = None
    q3_rel = None

    if q_rel_scores and q_rel_scores.get("available"):
        alpha  = float(q_rel_scores.get("alpha", 0.0))
        q1_rel = _score_q1_rel(q_rel_scores)
        q3_rel = _score_q3_rel(q_rel_scores)

    # ── ブレンド ──
    def _blend(abs_score: float, rel_score: Optional[float], a: float) -> float:
        if rel_score is None or a == 0.0:
            return abs_score
        return abs_score * (1 - a) + rel_score * a

    q1 = _blend(q1_abs, q1_rel, alpha)
    q3 = _blend(q3_abs, q3_rel, alpha)

    # ── 合成 ──
    total_w = w.w_q1 + w.w_q3
    q_raw   = (q1 * w.w_q1 + q3 * w.w_q3) / total_w if total_w > 0 else 0.0

    # ── ノックアウト ──
    penalty, warnings = _knockout_penalty(operating_margin, equity_ratio, interest_coverage, w)

    # ノックアウトも相対評価の恩恵で緩和（FINタイプなど高レバが正常な業種）
    # → alpha が高いほどペナルティを割引（最大50%割引）
    effective_penalty = penalty * (1.0 - alpha * 0.5)

    q_final = max(0.0, min(100.0, q_raw - effective_penalty))

    return {
        "q_score":  round(q_final, 1),
        "q1":       round(q1, 1),
        "q3":       round(q3, 1),
        "q1_abs":   round(q1_abs, 1),
        "q3_abs":   round(q3_abs, 1),
        "q1_rel":   round(q1_rel, 1) if q1_rel is not None else None,
        "q3_rel":   round(q3_rel, 1) if q3_rel is not None else None,
        "alpha":    alpha,
        "penalty":  effective_penalty,
        "warnings": warnings,
        "weights":  w,
    }
