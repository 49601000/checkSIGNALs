"""
valuation.py  (v3)
────────────────────────────────────────────────────────────────────────────
V（バリュエーション）スコア — 4サブスコア構造

  V1 伝統的割安  : PER / PBR         （絶対評価）
  V2 CF系評価   : EV/EBITDA          （絶対評価）
  V3 株主還元    : 配当利回り          （補助因子）
  V4 セクター相対 : セクター相対PER/PBR/EV （pattern_db から注入）

  最終 V = V1×0.30 + V2×0.20 + V3×0.10 + V4×0.40
  ただし V4 の情報がない場合（米国株や UNK）は
  V1×0.45 + V2×0.30 + V3×0.25 に自動リウェイト

【採点方式】ステップ関数（旧 valuation.py と同思想）
  - 絶対評価（V1〜V3）は従来と同じ基準
  - V4 はセクター相対スコアを pattern_db から受け取る（0〜100）

【設計メモ】
  - PER / PBR の元データと評価コメントは v2 互換で残す
  - EV/EBITDA は絶対評価のみ（セクター相対は V4 に含む）
  - 配当利回り「高配当＝衰退企業」問題 → V3 ウェイトを 0.10 に抑制
"""

from typing import Optional


# ─── V1: 伝統的割安（絶対値） ────────────────────────────────────────────

def _score_v1_traditional(
    per: Optional[float],
    pbr: Optional[float],
) -> float:
    """PER(30) + PBR(25) = MAX 55 → 0〜100 正規化"""
    raw = 0.0

    if per is not None and per > 0:
        if per < 8:    raw += 30
        elif per < 12: raw += 26
        elif per < 20: raw += 20
        elif per < 30: raw += 10
        elif per < 40: raw += 5

    if pbr is not None and pbr > 0:
        if pbr < 0.8:  raw += 25
        elif pbr < 1.2: raw += 20
        elif pbr < 2.0: raw += 10
        elif pbr < 3.0: raw += 5

    max_raw = 30 + 25
    return max(0.0, min(100.0, raw / max_raw * 100.0))


# ─── V2: EV/EBITDA（CF系） ───────────────────────────────────────────────

def _score_v2_ev_ebitda(ev_ebitda: Optional[float]) -> float:
    """EV/EBITDA の絶対評価（低いほど割安）→ 0〜100"""
    if ev_ebitda is None or ev_ebitda <= 0:
        return 50.0  # 情報なしは中立

    if ev_ebitda < 5:    return 100.0
    elif ev_ebitda < 8:  return 85.0
    elif ev_ebitda < 12: return 65.0
    elif ev_ebitda < 16: return 45.0
    elif ev_ebitda < 22: return 25.0
    else:                return 10.0


# ─── V3: 配当利回り（補助因子） ──────────────────────────────────────────

def _score_v3_dividend(dividend_yield: Optional[float]) -> float:
    """配当利回り（補助因子）→ 0〜100"""
    if not dividend_yield:
        return 50.0  # 無配は中立（ペナルティなし）

    if dividend_yield >= 5:   return 100.0
    elif dividend_yield >= 3: return 80.0
    elif dividend_yield >= 2: return 55.0
    elif dividend_yield >= 1: return 35.0
    return 20.0


# ─── メイン: score_valuation ─────────────────────────────────────────────

def score_valuation(
    per: Optional[float],
    pbr: Optional[float],
    dividend_yield: Optional[float],
    ev_ebitda: Optional[float] = None,
    sector_v_score: Optional[float] = None,   # pattern_db から注入
) -> dict:
    """
    V スコアを計算して dict で返す。

    Parameters
    ----------
    sector_v_score : セクター相対スコア（0〜100）。
                     None の場合は V4 を除いたリウェイトで計算。

    Returns
    -------
    {
        "v_score"  : float,  # 最終 V（0〜100）
        "v1"       : float,
        "v2"       : float,
        "v3"       : float,
        "v4"       : float or None,
        "has_sector": bool,
    }
    """
    v1 = _score_v1_traditional(per, pbr)
    v2 = _score_v2_ev_ebitda(ev_ebitda)
    v3 = _score_v3_dividend(dividend_yield)

    has_sector = sector_v_score is not None
    v4 = float(sector_v_score) if has_sector else None

    if has_sector:
        v_final = v1 * 0.30 + v2 * 0.20 + v3 * 0.10 + v4 * 0.40
    else:
        # V4 なし → V1/V2/V3 でリウェイト（合計 1.0）
        v_final = v1 * 0.45 + v2 * 0.30 + v3 * 0.25

    return {
        "v_score":    round(max(0.0, min(100.0, v_final)), 1),
        "v1":         round(v1, 1),
        "v2":         round(v2, 1),
        "v3":         round(v3, 1),
        "v4":         round(v4, 1) if v4 is not None else None,
        "has_sector": has_sector,
    }
