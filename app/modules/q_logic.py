"""
q_logic.py  (v3.3)
────────────────────────────────────────────────────────────────────────────
Q（ビジネスの質）スコア — 業種別ノックアウト閾値 + 相対評価ブレンド対応版

【v3.3 変更点】
  - ノックアウト判定に industry（yfinance 業種文字列）を追加
  - 業種によって自己資本比率の閾値を動的に変更：
      銀行業  (Banks*)        → 4%   (BIS規制Tier1目安)
      保険業  (Insurance*)    → 8%
      証券・リース (Capital Markets / Financial*Leasing 等) → 8%
      その他                  → 10%  (従来通り)
  - D/E ノックアウトも金融業では適用しない
    （銀行・保険は高レバレッジが正常な業態のため）

【v3.2 からの継続事項】
  - score_quality() に q_rel_scores を渡すと絶対評価と相対評価をαブレンド
  - QWeights で絶対評価の重みを外部注入可能（Optuna対応）
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any


# ─── 業種判定ヘルパー ─────────────────────────────────────────────────────

def _classify_industry(industry: str) -> str:
    """
    yfinance の industry 文字列から内部カテゴリを返す。

    Returns
    -------
    "bank"       : Banks—Regional, Banks—Diversified など
    "insurance"  : Insurance—Life, Insurance—Property & Casualty など
    "fin_other"  : Capital Markets, Financial Conglomerates, Financial—Leasing など
    "other"      : 上記以外
    """
    s = (industry or "").lower()
    if "bank" in s:
        return "bank"
    if "insurance" in s:
        return "insurance"
    if any(x in s for x in ("capital market", "financial", "leasing", "brokerage", "asset management")):
        return "fin_other"
    return "other"


def _er_threshold(industry: str) -> float:
    """業種に応じた自己資本比率のノックアウト閾値（%）を返す。"""
    cat = _classify_industry(industry)
    return {"bank": 4.0, "insurance": 8.0, "fin_other": 8.0, "other": 10.0}[cat]


def _apply_er_knockout(industry: str) -> bool:
    """D/E ノックアウトを適用するか。金融業は False。"""
    return _classify_industry(industry) == "other"


# ─── 重みデータクラス ─────────────────────────────────────────────────────

@dataclass
class QWeights:
    """絶対評価ステップ関数の重みパラメータ。Optuna/スライダーから差し込む。"""
    roe_w: float = 50.0
    roa_w: float = 25.0
    opm_w: float = 25.0
    er_w:  float = 40.0
    de_w:  float = 30.0
    ic_w:  float = 30.0
    w_q1: float = 0.50
    w_q3: float = 0.50
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
    scores, weights = [], []
    for key, wt in [("roe_rel", 2.0), ("roa_rel", 1.0), ("opm_rel", 1.0)]:
        v = q_rel.get(key)
        if v is not None:
            scores.append(v * wt)
            weights.append(wt)
    if not scores:
        return None
    return sum(scores) / sum(weights)


# ─── Q3: 財務健全性（相対評価） ──────────────────────────────────────────

def _score_q3_rel(q_rel: Dict[str, Any]) -> Optional[float]:
    scores, weights = [], []
    for key, wt in [("er_rel", 2.0), ("ic_rel", 1.5)]:
        v = q_rel.get(key)
        if v is not None:
            scores.append(v * wt)
            weights.append(wt)
    if not scores:
        return None
    return sum(scores) / sum(weights)


# ─── ノックアウト判定（業種対応） ────────────────────────────────────────

def _knockout_penalty(
    operating_margin: Optional[float],
    equity_ratio: Optional[float],
    interest_coverage: Optional[float],
    w: QWeights,
    industry: str = "",
) -> Tuple[float, List[str]]:
    """
    業種に応じた閾値でノックアウトペナルティを計算する。

    自己資本比率の閾値:
      銀行業  → 4%
      保険業  → 8%
      証券・リース等 → 8%
      その他  → 10%（従来通り）

    D/Eノックアウト:
      金融業全般（bank / insurance / fin_other）では適用しない。
    """
    penalty: float = 0.0
    warnings: List[str] = []

    # インタレストカバレッジ（業種問わず1.5倍未満は懸念）
    if interest_coverage is not None and interest_coverage < 1.5:
        penalty += w.ko_ic
        warnings.append(f"⚠️ インタレストカバレッジ {interest_coverage:.1f}x（利払い能力に懸念）")

    # 自己資本比率（業種別閾値）
    er_thr = _er_threshold(industry)
    if equity_ratio is not None and equity_ratio < er_thr:
        penalty += w.ko_er
        cat = _classify_industry(industry)
        thr_note = {
            "bank":      f"銀行業基準 {er_thr:.0f}%",
            "insurance": f"保険業基準 {er_thr:.0f}%",
            "fin_other": f"金融業基準 {er_thr:.0f}%",
            "other":     f"基準 {er_thr:.0f}%",
        }[cat]
        warnings.append(f"⚠️ 自己資本比率 {equity_ratio:.1f}%（{thr_note}未満）")

    # 営業利益率赤字（業種問わず）
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
    industry: str = "",                              # ★v3.3
) -> dict:
    """
    Q スコアを計算して dict で返す。

    Parameters
    ----------
    industry : str
        yfinance の industry 文字列。ノックアウト閾値の業種補正に使用。
        例: "Banks—Regional", "Insurance—Life", "Capital Markets"

    Returns
    -------
    {
        "q_score"     : float,
        "q1"          : float,
        "q3"          : float,
        "q1_abs"      : float,
        "q3_abs"      : float,
        "q1_rel"      : float or None,
        "q3_rel"      : float or None,
        "alpha"       : float,
        "penalty"     : float,
        "warnings"    : list[str],
        "weights"     : QWeights,
        "industry_cat": str,   # 業種カテゴリ（"bank"/"insurance"/"fin_other"/"other"）
    }
    """
    w = weights if weights is not None else DEFAULT_WEIGHTS

    # ── 絶対評価 ──
    q1_abs = _score_q1_abs(roe, roa, operating_margin, w)
    q3_abs = _score_q3_abs(equity_ratio, de_ratio, interest_coverage, w)

    # ── 相対評価 ──
    alpha  = 0.0
    q1_rel = None
    q3_rel = None
    if q_rel_scores and q_rel_scores.get("available"):
        alpha  = float(q_rel_scores.get("alpha", 0.0))
        q1_rel = _score_q1_rel(q_rel_scores)
        q3_rel = _score_q3_rel(q_rel_scores)

    # ── ブレンド ──
    def _blend(abs_s: float, rel_s: Optional[float], a: float) -> float:
        if rel_s is None or a == 0.0:
            return abs_s
        return abs_s * (1 - a) + rel_s * a

    q1 = _blend(q1_abs, q1_rel, alpha)
    q3 = _blend(q3_abs, q3_rel, alpha)

    # ── 合成 ──
    total_w = w.w_q1 + w.w_q3
    q_raw   = (q1 * w.w_q1 + q3 * w.w_q3) / total_w if total_w > 0 else 0.0

    # ── ノックアウト（業種別閾値） ──
    penalty, warnings = _knockout_penalty(
        operating_margin, equity_ratio, interest_coverage, w, industry
    )

    # α が高いほどペナルティを割引（最大50%）
    effective_penalty = penalty * (1.0 - alpha * 0.5)
    q_final = max(0.0, min(100.0, q_raw - effective_penalty))

    return {
        "q_score":      round(q_final, 1),
        "q1":           round(q1, 1),
        "q3":           round(q3, 1),
        "q1_abs":       round(q1_abs, 1),
        "q3_abs":       round(q3_abs, 1),
        "q1_rel":       round(q1_rel, 1) if q1_rel is not None else None,
        "q3_rel":       round(q3_rel, 1) if q3_rel is not None else None,
        "alpha":        alpha,
        "penalty":      effective_penalty,
        "warnings":     warnings,
        "weights":      w,
        "industry_cat": _classify_industry(industry),
    }
