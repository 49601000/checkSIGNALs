"""
v_logic.py  (v3)
────────────────────────────────────────────────────────────────────────────
V（バリュエーション）スコア — 4サブスコア構造

  V1 伝統的割安  : PER / PBR         （絶対評価）
  V2 CF系評価   : EV/EBITDA          （絶対評価）
  V3 株主還元    : 配当利回り          （補助因子）
  V4 セクター相対 : セクター相対PER/PBR/EV （pattern_db から注入）

【市場別閾値】
  is_us=False（日本株）: 現行の日本市場基準
  is_us=True（米国株）: PER・PBR・EV/EBITDA・配当利回りをUS市場水準に調整

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

from typing import Optional, Dict


# ─── デフォルト重み（V内部） ─────────────────────────────────────────

DEFAULT_V_WEIGHTS_WITH_SECTOR = {
    "v1": 0.2246,
    "v2": 0.2502,
    "v3": 0.1251,
    "v4": 0.40,
}

DEFAULT_V_WEIGHTS_NO_SECTOR = {
    "v1": 0.3744,
    "v2": 0.4170,
    "v3": 0.2085,
}


def _normalize_weights(weights: Dict[str, float], keys: list[str]) -> Dict[str, float]:
    filtered = {k: float(weights[k]) for k in keys}
    total = sum(filtered.values())
    if total <= 0:
        raise ValueError(f"Invalid weights: sum must be > 0, got {total}")
    return {k: v / total for k, v in filtered.items()}


# ─── V1: 伝統的割安（絶対値） ─────────────────────────────────────────

def _score_v1_traditional(
    per: Optional[float],
    pbr: Optional[float],
    is_us: bool = False,
) -> float:
    raw = 0.0

    if per is not None and per > 0:
        if is_us:
            if per < 15: raw += 30
            elif per < 20: raw += 26
            elif per < 28: raw += 20
            elif per < 40: raw += 10
            elif per < 55: raw += 5
        else:
            if per < 8: raw += 30
            elif per < 12: raw += 26
            elif per < 20: raw += 20
            elif per < 30: raw += 10
            elif per < 40: raw += 5

    if pbr is not None and pbr > 0:
        if is_us:
            if pbr < 2.0: raw += 25
            elif pbr < 4.0: raw += 20
            elif pbr < 6.0: raw += 10
            elif pbr < 10.0: raw += 5
        else:
            if pbr < 0.8: raw += 25
            elif pbr < 1.2: raw += 20
            elif pbr < 2.0: raw += 10
            elif pbr < 3.0: raw += 5

    max_raw = 30 + 25
    return max(0.0, min(100.0, raw / max_raw * 100.0))


# ─── V2: EV/EBITDA ─────────────────────────────────────────

def _score_v2_ev_ebitda(ev_ebitda: Optional[float], is_us: bool = False) -> float:
    if ev_ebitda is None or ev_ebitda <= 0:
        return 50.0

    if is_us:
        if ev_ebitda < 8: return 100.0
        elif ev_ebitda < 12: return 85.0
        elif ev_ebitda < 18: return 65.0
        elif ev_ebitda < 25: return 45.0
        elif ev_ebitda < 35: return 25.0
        else: return 10.0
    else:
        if ev_ebitda < 5: return 100.0
        elif ev_ebitda < 8: return 85.0
        elif ev_ebitda < 12: return 65.0
        elif ev_ebitda < 16: return 45.0
        elif ev_ebitda < 22: return 25.0
        else: return 10.0


# ─── V3: 配当利回り ─────────────────────────────────────────

def _score_v3_dividend(dividend_yield: Optional[float], is_us: bool = False) -> float:
    if not dividend_yield:
        return 50.0

    if is_us:
        if dividend_yield >= 3.0: return 100.0
        elif dividend_yield >= 2.0: return 80.0
        elif dividend_yield >= 1.0: return 55.0
        elif dividend_yield >= 0.5: return 35.0
        return 20.0
    else:
        if dividend_yield >= 5: return 100.0
        elif dividend_yield >= 3: return 80.0
        elif dividend_yield >= 2: return 55.0
        elif dividend_yield >= 1: return 35.0
        return 20.0


# ─── メイン関数 ─────────────────────────────────────────

def score_valuation(
    per: Optional[float],
    pbr: Optional[float],
    dividend_yield: Optional[float],
    ev_ebitda: Optional[float] = None,
    sector_v_score: Optional[float] = None,
    is_us: bool = False,
    v_weights_with_sector: Optional[Dict[str, float]] = None,
    v_weights_no_sector: Optional[Dict[str, float]] = None,
) -> dict:

    v1 = _score_v1_traditional(per, pbr, is_us=is_us)
    v2 = _score_v2_ev_ebitda(ev_ebitda, is_us=is_us)
    v3 = _score_v3_dividend(dividend_yield, is_us=is_us)

    if sector_v_score is not None:
        weights = _normalize_weights(
            v_weights_with_sector or DEFAULT_V_WEIGHTS_WITH_SECTOR,
            ["v1", "v2", "v3", "v4"],
        )
        v4 = float(sector_v_score)

        v_final = (
            v1 * weights["v1"] +
            v2 * weights["v2"] +
            v3 * weights["v3"] +
            v4 * weights["v4"]
        )
    else:
        weights = _normalize_weights(
            v_weights_no_sector or DEFAULT_V_WEIGHTS_NO_SECTOR,
            ["v1", "v2", "v3"],
        )

        v_final = (
            v1 * weights["v1"] +
            v2 * weights["v2"] +
            v3 * weights["v3"]
        )

    return {
        "v_score": round(max(0.0, min(100.0, v_final)), 1),
        "v1": round(v1, 1),
        "v2": round(v2, 1),
        "v3": round(v3, 1),
        "v4": round(float(sector_v_score), 1) if sector_v_score is not None else None,
        "has_sector": sector_v_score is not None,
        "is_us": is_us,
        "v_weights_used": weights,
    }
