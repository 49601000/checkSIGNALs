"""
q_logic.py  (v3.1)
────────────────────────────────────────────────────────────────────────────
Q（ビジネスの質）スコア — サブスコア構造 + 重み外部注入対応

  Q1 収益性   : ROE / ROA / 営業利益率
  Q3 財務健全性: 自己資本比率 / D/Eレシオ / インタレストカバレッジ
  最終 Q      : Q1 × w_q1 + Q3 × w_q3  （デフォルト各0.50）

【重みの外部注入】
  score_quality() の引数 weights に QWeights インスタンスを渡すことで
  Optuna / スライダーチューニングからパラメータを差し込める。
  weights=None の場合はデフォルト値（v3互換）を使用。

【QWeights フィールド一覧】
  Q1サブスコア内の寄与率（各指標の「最大点」）
    roe_w  : ROE の最大点        （デフォルト 50）
    roa_w  : ROA の最大点        （デフォルト 25）
    opm_w  : 営業利益率の最大点   （デフォルト 25）
  Q3サブスコア内の寄与率
    er_w   : 自己資本比率の最大点  （デフォルト 40）
    de_w   : D/E レシオの最大点   （デフォルト 30）
    ic_w   : インタレストカバレッジの最大点（デフォルト 30）
  合成ウェイト
    w_q1   : Q1 のウェイト        （デフォルト 0.50）
    w_q3   : Q3 のウェイト        （デフォルト 0.50）
  ノックアウトペナルティ点数
    ko_ic  : カバレッジ低下時      （デフォルト 15）
    ko_er  : 自己資本率低下時      （デフォルト 15）
    ko_opm : 営業赤字時            （デフォルト 15）

【Optuna 最適化の使い方（param_tuning.ipynb 側）】
  import optuna
  from modules.q_logic import QWeights, score_quality

  def objective(trial):
      w = QWeights(
          roe_w = trial.suggest_float("roe_w", 10, 80),
          roa_w = trial.suggest_float("roa_w",  5, 50),
          opm_w = trial.suggest_float("opm_w",  5, 50),
          er_w  = trial.suggest_float("er_w",  10, 60),
          de_w  = trial.suggest_float("de_w",   0, 50),
          ic_w  = trial.suggest_float("ic_w",   0, 50),
          w_q1  = trial.suggest_float("w_q1", 0.2, 0.8),
          w_q3  = trial.suggest_float("w_q3", 0.2, 0.8),
          ko_ic = trial.suggest_float("ko_ic",  0, 30),
          ko_er = trial.suggest_float("ko_er",  0, 30),
          ko_opm= trial.suggest_float("ko_opm", 0, 30),
      )
      scores = [score_quality(**funda, weights=w)["q_score"] for funda in GOOD_STOCKS]
      return sum(scores) / len(scores)  # 優良銘柄のQを最大化

  study = optuna.create_study(direction="maximize")
  study.optimize(objective, n_trials=200)
  best_w = QWeights(**study.best_params)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, List


# ─── 重みデータクラス ─────────────────────────────────────────────────────

@dataclass
class QWeights:
    """Q スコア計算の全重みパラメータ。Optuna/スライダーから差し込む。"""

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


# デフォルト重み（変更しない）
DEFAULT_WEIGHTS = QWeights()


# ─── Q1: 収益性 ──────────────────────────────────────────────────────────

def _score_q1_profitability(
    roe: Optional[float],
    roa: Optional[float],
    operating_margin: Optional[float],
    w: QWeights,
) -> float:
    """ROE / ROA / 営業利益率 を採点し 0〜100 に正規化して返す。"""
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


# ─── Q3: 財務健全性 ──────────────────────────────────────────────────────

def _score_q3_financial_health(
    equity_ratio: Optional[float],
    de_ratio: Optional[float],
    interest_coverage: Optional[float],
    w: QWeights,
) -> float:
    """自己資本比率 / D/E / インタレストカバレッジ を採点し 0〜100 に正規化。"""
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
) -> dict:
    """
    Q スコアを計算して dict で返す。

    Parameters
    ----------
    weights : QWeights or None
        重みパラメータ。None の場合はデフォルト値を使用。
        Optuna やスライダーチューニングから差し込む場合はインスタンスを渡す。

    Returns
    -------
    {
        "q_score"  : float,       # 最終 Q（0〜100）
        "q1"       : float,       # 収益性サブスコア（0〜100）
        "q3"       : float,       # 財務健全性サブスコア（0〜100）
        "penalty"  : float,       # ノックアウトペナルティ合計
        "warnings" : list[str],   # 警告メッセージ
        "weights"  : QWeights,    # 使用した重み（チューニング記録用）
    }
    """
    w = weights if weights is not None else DEFAULT_WEIGHTS

    q1 = _score_q1_profitability(roe, roa, operating_margin, w)
    q3 = _score_q3_financial_health(equity_ratio, de_ratio, interest_coverage, w)

    total_w = w.w_q1 + w.w_q3
    q_raw   = (q1 * w.w_q1 + q3 * w.w_q3) / total_w if total_w > 0 else 0.0

    penalty, warnings = _knockout_penalty(operating_margin, equity_ratio, interest_coverage, w)
    q_final = max(0.0, min(100.0, q_raw - penalty))

    return {
        "q_score":  round(q_final, 1),
        "q1":       round(q1, 1),
        "q3":       round(q3, 1),
        "penalty":  penalty,
        "warnings": warnings,
        "weights":  w,
    }
