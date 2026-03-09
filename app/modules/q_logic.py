"""
q_logic.py  (v3)
────────────────────────────────────────────────────────────────────────────
Q（ビジネスの質）スコア — 3サブスコア構造

  Q1 収益性   : ROE / ROA / 営業利益率
  Q2 安定性   : （将来拡張用。v3では簡易スタブ）
  Q3 財務健全性: 自己資本比率 / D/Eレシオ / インタレストカバレッジ

  最終 Q = Q1 × 0.50 + Q3 × 0.50   （Q2 は現在 0 ウェイト）

【採点方式】ステップ関数（旧 q_logic と同思想）
  - 各指標を 0〜MAX_RAW_n に採点
  - サブスコアは 0〜100 に正規化
  - 合成 Q も 0〜100

【ノックアウト条件】
  以下のいずれかに該当すると、合成 Q に -15pt ペナルティ（フロア 0）
  ① インタレストカバレッジ < 1.5（利払い能力が極めて低い）
  ② 自己資本比率 < 10%（過剰レバレッジ）
  ③ 営業利益率 < 0%（継続的な営業赤字）
"""

from typing import Optional, Tuple


# ─── Q1: 収益性 ──────────────────────────────────────────────────────────

def _score_q1_profitability(
    roe: Optional[float],
    roa: Optional[float],
    operating_margin: Optional[float],
) -> float:
    """ROE(50) + ROA(25) + 営業利益率(25) = MAX 100"""
    raw = 0.0

    # ROE (0〜50)
    if roe is not None:
        if roe <= 0:    raw += 0
        elif roe < 5:   raw += 10
        elif roe < 10:  raw += 20
        elif roe < 15:  raw += 30
        elif roe < 20:  raw += 40
        elif roe < 25:  raw += 45
        else:           raw += 50

    # ROA (0〜25)
    if roa is not None:
        if roa <= 0:    raw += 0
        elif roa < 2:   raw += 5
        elif roa < 4:   raw += 10
        elif roa < 6:   raw += 15
        elif roa < 8:   raw += 20
        else:           raw += 25

    # 営業利益率 % (0〜25)
    if operating_margin is not None:
        if operating_margin <= 0:    raw += 0
        elif operating_margin < 3:   raw += 5
        elif operating_margin < 7:   raw += 10
        elif operating_margin < 12:  raw += 15
        elif operating_margin < 20:  raw += 20
        else:                        raw += 25

    max_raw = 50 + 25 + 25
    return max(0.0, min(100.0, raw / max_raw * 100.0))


# ─── Q3: 財務健全性 ──────────────────────────────────────────────────────

def _score_q3_financial_health(
    equity_ratio: Optional[float],
    de_ratio: Optional[float],
    interest_coverage: Optional[float],
) -> float:
    """自己資本比率(40) + D/E(30) + インタレストカバレッジ(30) = MAX 100"""
    raw = 0.0

    # 自己資本比率 % (0〜40)
    if equity_ratio is not None:
        if equity_ratio < 10:    raw += 0
        elif equity_ratio < 20:  raw += 5
        elif equity_ratio < 30:  raw += 10
        elif equity_ratio < 40:  raw += 20
        elif equity_ratio < 50:  raw += 30
        elif equity_ratio < 60:  raw += 35
        else:                    raw += 40

    # D/E レシオ（低いほど良い、0〜30）
    if de_ratio is not None:
        if de_ratio > 3.0:   raw += 0
        elif de_ratio > 2.0: raw += 5
        elif de_ratio > 1.5: raw += 10
        elif de_ratio > 1.0: raw += 15
        elif de_ratio > 0.5: raw += 22
        else:                raw += 30

    # インタレスト・カバレッジ（高いほど良い、0〜30）
    if interest_coverage is not None:
        if interest_coverage < 1.5:   raw += 0
        elif interest_coverage < 3:   raw += 8
        elif interest_coverage < 5:   raw += 15
        elif interest_coverage < 10:  raw += 22
        elif interest_coverage < 20:  raw += 27
        else:                         raw += 30

    max_raw = 40 + 30 + 30
    return max(0.0, min(100.0, raw / max_raw * 100.0))


# ─── ノックアウト判定 ────────────────────────────────────────────────────

def _knockout_penalty(
    operating_margin: Optional[float],
    equity_ratio: Optional[float],
    interest_coverage: Optional[float],
) -> Tuple[float, list[str]]:
    """ペナルティ点数と、該当した警告メッセージリストを返す。"""
    penalty = 0.0
    warnings = []

    if interest_coverage is not None and interest_coverage < 1.5:
        penalty += 15.0
        warnings.append(f"⚠️ インタレストカバレッジ {interest_coverage:.1f}x（利払い能力に懸念）")

    if equity_ratio is not None and equity_ratio < 10:
        penalty += 15.0
        warnings.append(f"⚠️ 自己資本比率 {equity_ratio:.1f}%（過剰レバレッジ）")

    if operating_margin is not None and operating_margin < 0:
        penalty += 15.0
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
) -> dict:
    """
    Q スコアを計算して dict で返す。

    Returns
    -------
    {
        "q_score"   : float,   # 最終 Q（0〜100）
        "q1"        : float,   # 収益性サブスコア
        "q3"        : float,   # 財務健全性サブスコア
        "penalty"   : float,   # ノックアウトペナルティ
        "warnings"  : list[str],
    }
    """
    q1 = _score_q1_profitability(roe, roa, operating_margin)
    q3 = _score_q3_financial_health(equity_ratio, de_ratio, interest_coverage)

    # 合成（Q2 は将来実装のため現在はウェイト 0）
    q_raw = q1 * 0.50 + q3 * 0.50

    # ノックアウト
    penalty, warnings = _knockout_penalty(operating_margin, equity_ratio, interest_coverage)
    q_final = max(0.0, min(100.0, q_raw - penalty))

    return {
        "q_score":  round(q_final, 1),
        "q1":       round(q1, 1),
        "q3":       round(q3, 1),
        "penalty":  penalty,
        "warnings": warnings,
    }
