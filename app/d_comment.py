"""
d_comment.py
────────────────────────────────────────────────────────────────────────────
D（価格防衛）スコアのコメント生成モジュール。

indicators.py と同じ位置（app/）に置き、
output_structure.py / classic/main.py から呼び出す。

【使い方】
    from d_comment import build_d_comment

    comment = build_d_comment(tech)
    # → {"summary": "...", "detail": "..."}

【入力】
    tech dict（indicators.compute_indicators の返却値）
    必要キー:
        defensive_score : float  0〜1
        def1〜def6      : float  各指標の defensive スコア（高い = ディフェンシブ）
                          ※ def6 は main.py 同様に 1-def6 済みの値として扱う

【出力】
    {
        "summary": str   # レーダー形状をもとにした1〜2文の短評
        "detail":  str   # 強み・弱みを掘り下げた2〜3文の詳細コメント
    }
    スコア未計算時は両キーとも None。
"""

from __future__ import annotations

import random
from typing import Dict, Any, Optional, List

from dict.dic1 import COMMENT_PARTS_SUMMARY
from dict.dic2 import COMMENT_PARTS_DETAIL


# ═══════════════════════════════════════════════════════════════════════════
# 内部定数
# ═══════════════════════════════════════════════════════════════════════════

# defensive_score → overall レベルの閾値
_OVERALL_HIGH_TH = 0.65   # S / A 相当
_OVERALL_LOW_TH  = 0.35   # D / E 相当

# 個別指標「強い / 弱い」の閾値（0〜1 スケール）
_FACTOR_OUTER_TH = 0.60   # これ以上 → outer（強み）
_FACTOR_INNER_TH = 0.40   # これ以下 → inner（弱み）

# 形状判定パラメータ
_SHAPE_SPREAD_TH       = 0.30   # max - min がこれ以上 → biased / concentrated
_SHAPE_CONCENTRATED_TH = 0.50   # outer が 1 本だけ & spread 大 → concentrated
_SHAPE_WEAK_TH         = 0.40   # 全指標がこれ以下 → weak


# ═══════════════════════════════════════════════════════════════════════════
# ヘルパー
# ═══════════════════════════════════════════════════════════════════════════

def _pick(lst: list) -> str:
    """リストからランダムに 1 要素を選ぶ。"""
    return random.choice(lst)


def _get_factor_scores(tech: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """
    tech から def1〜def6 を取り出す。
    def6 は indicators / main.py の方針に合わせ「1 - raw_def6」済みの値として
    そのまま受け取る（呼び出し元で反転済み前提）。
    """
    return {str(i): tech.get(f"def{i}") for i in range(1, 7)}


def _classify_overall(defensive_score: float) -> str:
    """defensive_score → 'high' / 'mid' / 'low'"""
    if defensive_score >= _OVERALL_HIGH_TH:
        return "high"
    if defensive_score <= _OVERALL_LOW_TH:
        return "low"
    return "mid"


def _classify_shape(scores: Dict[str, Optional[float]]) -> str:
    """
    6 指標のスコア分布から形状タイプを判定。

    Returns
    -------
    'balanced' | 'biased' | 'concentrated' | 'weak'
    """
    vals = [v for v in scores.values() if v is not None]
    if not vals:
        return "balanced"

    # 全指標が低い → weak
    if max(vals) <= _SHAPE_WEAK_TH:
        return "weak"

    spread = max(vals) - min(vals)

    # spread が大きい場合
    if spread >= _SHAPE_SPREAD_TH:
        outer_count = sum(1 for v in vals if v >= _FACTOR_OUTER_TH)
        # 突出 1 本だけ → concentrated
        if outer_count == 1 and max(vals) >= _SHAPE_CONCENTRATED_TH:
            return "concentrated"
        return "biased"

    return "balanced"


def _classify_factors(scores: Dict[str, Optional[float]]) -> tuple[List[str], List[str]]:
    """
    各指標を outer（強み）/ inner（弱み）に分類する。

    Returns
    -------
    (outer_keys, inner_keys) : 各 key は '1'〜'6' の文字列
    """
    outer, inner = [], []
    for k, v in scores.items():
        if v is None:
            continue
        if v >= _FACTOR_OUTER_TH:
            outer.append(k)
        elif v <= _FACTOR_INNER_TH:
            inner.append(k)
    return outer, inner


# ═══════════════════════════════════════════════════════════════════════════
# サマリーコメント生成（dic1 使用）
# ═══════════════════════════════════════════════════════════════════════════

def _build_summary_comment(
    defensive_score: float,
    scores: Dict[str, Optional[float]],
) -> str:
    """
    レーダー形状をもとにした短評（1〜2 文）を生成する。
    dic1.COMMENT_PARTS_SUMMARY を使用。
    """
    parts = COMMENT_PARTS_SUMMARY

    # A. 全体傾向
    overall_level = _classify_overall(defensive_score)
    sentence_overall = _pick(parts["overall"][overall_level])

    # D. 形状
    shape = _classify_shape(scores)
    sentence_shape = _pick(parts["shape"][shape])

    # B/C. 突出指標があれば 1 本追加
    outer, inner = _classify_factors(scores)
    sentence_factor = ""

    if len(outer) >= 3:
        sentence_factor = _pick(parts["grouped"]["outer"])
    elif len(inner) >= 3:
        sentence_factor = _pick(parts["grouped"]["inner"])
    elif len(outer) == 1:
        sentence_factor = parts["factors"][outer[0]]["outer"]
    elif len(inner) == 1:
        sentence_factor = parts["factors"][inner[0]]["inner"]

    # 組み立て
    sentences = [sentence_overall, sentence_shape]
    if sentence_factor:
        sentences.append(sentence_factor)

    return "".join(sentences)


# ═══════════════════════════════════════════════════════════════════════════
# 詳細コメント生成（dic2 使用）
# ═══════════════════════════════════════════════════════════════════════════

def _build_detail_comment(
    defensive_score: float,
    scores: Dict[str, Optional[float]],
) -> str:
    """
    強み・弱みを掘り下げた詳細コメント（2〜3 文）を生成する。
    dic2.COMMENT_PARTS_DETAIL を使用。
    """
    parts = COMMENT_PARTS_DETAIL
    outer, inner = _classify_factors(scores)

    # A. 導入: スコアレベルと強弱の有無で選択
    overall_level = _classify_overall(defensive_score)
    if overall_level == "high" and inner:
        intro = parts["intro"][4]   # 「総合では強めだが、いくつか脆い部分も抱える。」
    elif overall_level == "low" and outer:
        intro = parts["intro"][3]   # 「総合では弱めだが、一部に防衛的な要素も残る。」
    elif outer and inner:
        intro = _pick(parts["intro"][:3])
    elif not outer and not inner:
        intro = parts["intro"][1]   # 「ディフェンシブ性は中位圏だが、指標ごとの濃淡がある。」
    else:
        intro = _pick(parts["intro"])

    # B. 強み（最大 2 本）
    strength_sentences = [
        parts["strengths"][k] for k in outer[:2]
    ]

    # C. 弱み（最大 2 本）
    weakness_sentences = [
        parts["weaknesses"][k] for k in inner[:2]
    ]

    # D. 総括: 強弱の組み合わせで選択
    if outer and inner:
        summary = parts["summary"][0]   # 「強みと弱みがはっきり分かれたプロファイル。」
    elif overall_level == "high":
        summary = parts["summary"][2]   # 「守りの強さは確認できるが、全面的に安定しているわけではない。」
    elif overall_level == "low" and not outer:
        summary = parts["summary"][4]   # 「ディフェンシブ性は限定的で、脆さが目立つ。」
    elif inner and not outer:
        summary = parts["summary"][3]   # 「特定の弱点が総合評価を押し下げている。」
    else:
        summary = parts["summary"][1]   # 「一部に防衛力はあるが、全体としては中立〜弱め。」

    # 組み立て
    sentences = [intro] + strength_sentences + weakness_sentences + [summary]
    return "".join(sentences)


# ═══════════════════════════════════════════════════════════════════════════
# 公開 API
# ═══════════════════════════════════════════════════════════════════════════

def build_d_comment(tech: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    D スコアのサマリー・詳細コメントを生成して返す。

    Parameters
    ----------
    tech : dict
        indicators.compute_indicators() の返却値。
        defensive_score / def1〜def6 が必要。
        def6 は「1 - raw_def6」反転済みの値として扱う。

    Returns
    -------
    dict
        {
            "summary": str | None,   # レーダー形状ベースの短評
            "detail":  str | None,   # 強み弱み掘り下げの詳細コメント
        }
    """
    defensive_score = tech.get("defensive_score")
    if defensive_score is None:
        return {"summary": None, "detail": None}

    defensive_score = float(defensive_score)

    # def6 は既に main.py 側で 1-def6 反転済み前提で取得
    scores = _get_factor_scores(tech)

    # 全指標が None の場合（D スコア未計算）
    if all(v is None for v in scores.values()):
        return {"summary": None, "detail": None}

    summary = _build_summary_comment(defensive_score, scores)
    detail  = _build_detail_comment(defensive_score, scores)

    return {"summary": summary, "detail": detail}
