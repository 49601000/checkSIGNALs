"""
pattern_db.py  (v3.2)
────────────────────────────────────────────────────────────────────────────
財務特性分類DB（pattern_db_latest.csv）を読み込み、
銘柄のティッカーから財務タイプを判定するモジュール。

【v3.2 追加: 動的タイプ推定】
  ticker_list に未収録の銘柄でも、実測の財務指標から
  最も近い財務タイプを動的推定してQスコアの相対評価に使う。

  推定フロー:
    ① ticker_list で完全一致 → confirmed（confidence そのまま）
    ② 財務指標からユークリッド距離で最近傍タイプを探索
       → estimated（confidence を1段階下げる）
    ③ 距離が閾値超え or 指標不足 → UNK（絶対評価フォールバック）

【距離計算の指標と重み】
  ROE       : 重み 1.0（DBはROE中央値を小数で保持）
  ROA       : 重み 1.5（資産効率は業種差が大きく重要）
  自己資本比率: 重み 1.2
  インタレストカバレッジ: 重み 0.8（銀行等でNullが多いため控えめ）
  営業利益率  : 重み 1.0

  各指標を全タイプのIQR（Q75-Q25）で正規化してから距離計算する。
  IQRが0の場合はその指標をスキップ。

【Q相対評価スコアの計算】
  calc_q_relative_scores() が q_logic.py から呼ばれる。
  各指標について「タイプ中央値を50点」として線形スケール変換:
    score = 50 + (実績 - 中央値) / IQR × 25
    → clamp(0, 100)
  「低いほど良い」指標（D/E、IC以外）は符号を反転。
"""

from __future__ import annotations

import math
import os
from typing import Optional, Dict, Any, List

import pandas as pd
import streamlit as st


# ─── CSV パス ──────────────────────────────────────────────────────────────
_DEFAULT_CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "pattern_db_latest.csv"
)
PATTERN_DB_PATH = os.environ.get("PATTERN_DB_PATH", _DEFAULT_CSV_PATH)

# 動的推定の距離閾値（これを超えたらUNK扱い）
_DISTANCE_THRESHOLD = 3.5

# confidence の降格マッピング
_CONF_DOWNGRADE = {"HIGH": "MID", "MID": "LOW", "LOW": "NONE", "NONE": "NONE"}


# ─── DB ロード ─────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_pattern_db() -> pd.DataFrame:
    """CSVを読み込んでDataFrameで返す（起動時1回のみ）。"""
    path = PATTERN_DB_PATH
    if not os.path.exists(path):
        for candidate in [
            "pattern_db_latest.csv",
            "data/pattern_db_latest.csv",
            "app/data/pattern_db_latest.csv",
        ]:
            if os.path.exists(candidate):
                path = candidate
                break
        else:
            return pd.DataFrame()

    df = pd.read_csv(path, encoding="utf-8-sig")
    df["_ticker_set"] = df["ticker_list"].apply(
        lambda x: set(str(x).replace('"', "").split(",")) if pd.notna(x) else set()
    )
    return df


# ─── 内部ヘルパー ──────────────────────────────────────────────────────────

def _f(row: pd.Series, col: str) -> Optional[float]:
    v = row.get(col)
    return float(v) if pd.notna(v) else None


def _build_type_dict(row: pd.Series, matched: bool, confidence: str, estimated: bool = False) -> Dict[str, Any]:
    return {
        "code":        str(row["financial_type_code"]),
        "name":        str(row["financial_type_name"]),
        "ja":          str(row["financial_type_ja"]),
        "description": str(row["description"]),
        "confidence":  confidence,
        "matched":     matched,
        "estimated":   estimated,
        # Q 相対評価用
        "roe_median":               _f(row, "roe_median"),
        "roe_q25":                  _f(row, "roe_q25"),
        "roe_q75":                  _f(row, "roe_q75"),
        "roa_median":               _f(row, "roa_median"),
        "roa_q25":                  _f(row, "roa_q25"),
        "roa_q75":                  _f(row, "roa_q75"),
        "equity_ratio_median":      _f(row, "equity_ratio_median"),
        "equity_ratio_q25":         _f(row, "equity_ratio_q25"),
        "equity_ratio_q75":         _f(row, "equity_ratio_q75"),
        "interest_coverage_median": _f(row, "interest_coverage_median"),
        "interest_coverage_q25":    _f(row, "interest_coverage_q25"),
        "interest_coverage_q75":    _f(row, "interest_coverage_q75"),
        "operating_margin_median":  _f(row, "operating_margin_median"),
        "operating_margin_q25":     _f(row, "operating_margin_q25"),
        "operating_margin_q75":     _f(row, "operating_margin_q75"),
        # V 相対評価用
        "per_median":               _f(row, "per_median"),
        "per_q25":                  _f(row, "per_q25"),
        "per_q75":                  _f(row, "per_q75"),
        "pbr_median":               _f(row, "pbr_median"),
        "pbr_q25":                  _f(row, "pbr_q25"),
        "pbr_q75":                  _f(row, "pbr_q75"),
        "ev_ebitda_median":         _f(row, "ev_ebitda_median"),
    }


_UNK_RESULT: Dict[str, Any] = {
    "code": "UNK", "name": "UNKNOWN", "ja": "分類不能・データ不足",
    "description": "財務タイプを特定できませんでした。絶対評価で採点します。",
    "confidence": "NONE", "matched": False, "estimated": False,
    **{k: None for k in [
        "roe_median","roe_q25","roe_q75",
        "roa_median","roa_q25","roa_q75",
        "equity_ratio_median","equity_ratio_q25","equity_ratio_q75",
        "interest_coverage_median","interest_coverage_q25","interest_coverage_q75",
        "operating_margin_median","operating_margin_q25","operating_margin_q75",
        "per_median","per_q25","per_q75",
        "pbr_median","pbr_q25","pbr_q75",
        "ev_ebitda_median",
    ]},
}


# ─── 動的タイプ推定 ────────────────────────────────────────────────────────

# 推定に使う指標・重み・スケール（DBは小数表記、実測値も同スケールに揃える）
_ESTIMATION_FEATURES = [
    # (DBの中央値列, DBのq25列, DBのq75列, 重み, 実測値スケール変換)
    ("roe_median",               "roe_q25",               "roe_q75",               1.0),
    ("roa_median",               "roa_q25",               "roa_q75",               1.5),
    ("equity_ratio_median",      "equity_ratio_q25",      "equity_ratio_q75",      1.2),
    ("interest_coverage_median", "interest_coverage_q25", "interest_coverage_q75", 0.8),
    ("operating_margin_median",  "operating_margin_q25",  "operating_margin_q75",  1.0),
]

def _to_db_scale(key: str, val: float) -> float:
    """
    実測値（ROE=8.2%, ER=43.0%）をDBスケール（小数）に変換する。
    IC・D/E はそのままの倍率。
    """
    if key in ("interest_coverage_median",):
        return val  # 倍率のまま
    return val / 100.0  # % → 小数


def _estimate_type(
    db: pd.DataFrame,
    roe: Optional[float],
    roa: Optional[float],
    equity_ratio: Optional[float],
    interest_coverage: Optional[float],
    operating_margin: Optional[float],
) -> Dict[str, Any]:
    """
    財務指標から最も近いタイプをユークリッド距離で推定する。
    UNK行は推定対象から除外。
    """
    actuals = {
        "roe_median":               _to_db_scale("roe_median",               roe)               if roe               is not None else None,
        "roa_median":               _to_db_scale("roa_median",               roa)               if roa               is not None else None,
        "equity_ratio_median":      _to_db_scale("equity_ratio_median",      equity_ratio)      if equity_ratio      is not None else None,
        "interest_coverage_median": _to_db_scale("interest_coverage_median", interest_coverage) if interest_coverage is not None else None,
        "operating_margin_median":  _to_db_scale("operating_margin_median",  operating_margin)  if operating_margin  is not None else None,
    }

    # 有効な指標が2つ未満なら推定不可
    valid_count = sum(1 for v in actuals.values() if v is not None)
    if valid_count < 2:
        return _UNK_RESULT

    # 全タイプにわたるIQRを計算（正規化用）
    global_iqr: Dict[str, float] = {}
    for med_col, q25_col, q75_col, _ in _ESTIMATION_FEATURES:
        vals = db[q75_col].dropna() - db[q25_col].dropna()
        iqr = float(vals.median()) if len(vals) > 0 else 0.0
        global_iqr[med_col] = iqr if iqr > 1e-9 else None

    best_row = None
    best_dist = float("inf")

    for _, row in db.iterrows():
        code = str(row["financial_type_code"])
        if code in ("UNK", "MLG"):  # 推定対象外
            continue
        if int(row.get("sample_count", 0)) < 3:
            continue

        dist_sq = 0.0
        used = 0
        for med_col, _, _, weight in _ESTIMATION_FEATURES:
            actual = actuals.get(med_col)
            if actual is None:
                continue
            med_val = _f(row, med_col)
            if med_val is None:
                continue
            iqr = global_iqr.get(med_col)
            if iqr is None:
                continue
            diff = (actual - med_val) / iqr
            dist_sq += (diff * weight) ** 2
            used += 1

        if used < 2:
            continue
        dist = math.sqrt(dist_sq / used)  # 使用指標数で正規化

        if dist < best_dist:
            best_dist = dist
            best_row = row

    if best_row is None or best_dist > _DISTANCE_THRESHOLD:
        return _UNK_RESULT

    orig_conf = str(best_row.get("confidence", "NONE"))
    est_conf  = _CONF_DOWNGRADE.get(orig_conf, "NONE")
    return _build_type_dict(best_row, matched=False, confidence=est_conf, estimated=True)


# ─── ティッカー → 財務タイプ判定（公開API） ───────────────────────────────

def classify_ticker(
    ticker: str,
    db: Optional[pd.DataFrame] = None,
    # Q指標（動的推定用）
    roe: Optional[float] = None,
    roa: Optional[float] = None,
    equity_ratio: Optional[float] = None,
    interest_coverage: Optional[float] = None,
    operating_margin: Optional[float] = None,
) -> Dict[str, Any]:
    """
    ①  ticker_list に収録済み → confirmed
    ②  未収録 + Q指標あり  → 動的推定（estimated）
    ③  それ以外           → UNK

    v3.2 から Q指標を渡すと動的推定が有効になる。
    """
    if db is None:
        db = load_pattern_db()
    if db is None or db.empty:
        return _UNK_RESULT

    t_norm = ticker.strip().upper()
    candidates = {t_norm}
    if t_norm.endswith(".T"):
        candidates.add(t_norm[:-2])
    else:
        candidates.add(t_norm + ".T")

    # ① 完全一致
    for _, row in db.iterrows():
        if row["_ticker_set"] & candidates:
            return _build_type_dict(row, matched=True, confidence=str(row["confidence"]))

    # ② 動的推定
    return _estimate_type(db, roe, roa, equity_ratio, interest_coverage, operating_margin)


# ─── Q 相対評価スコア計算（q_logic.py から呼ばれる） ──────────────────────

def calc_q_relative_scores(
    ft: Dict[str, Any],
    roe: Optional[float],
    roa: Optional[float],
    equity_ratio: Optional[float],
    interest_coverage: Optional[float],
    operating_margin: Optional[float],
) -> Dict[str, Any]:
    """
    財務タイプの中央値・IQRを使って各Q指標の相対スコア（0〜100）を計算する。
    「タイプ中央値 = 50点」として線形スケール変換。

    Returns
    -------
    {
        "roe_rel"  : float or None,
        "roa_rel"  : float or None,
        "er_rel"   : float or None,
        "ic_rel"   : float or None,
        "opm_rel"  : float or None,
        "alpha"    : float,   # ブレンド係数（HIGH=0.7, MID=0.4, LOW/NONE=0.0）
        "available": bool,    # 相対評価が有効かどうか
    }
    """
    conf = ft.get("confidence", "NONE")
    alpha_map = {"HIGH": 0.7, "MID": 0.4, "LOW": 0.1, "NONE": 0.0}
    alpha = alpha_map.get(conf, 0.0)

    if alpha == 0.0 or ft.get("code") == "UNK":
        return {"roe_rel": None, "roa_rel": None, "er_rel": None,
                "ic_rel": None, "opm_rel": None, "alpha": 0.0, "available": False}

    def _rel(actual_pct, med_col, q25_col, q75_col, higher_better=True) -> Optional[float]:
        """
        actual_pct: 実測値（%, 倍率など UI表示単位）
        med/q25/q75: DBから取得（小数表記）
        """
        if actual_pct is None:
            return None
        med = ft.get(med_col)
        q25 = ft.get(q25_col)
        q75 = ft.get(q75_col)
        if med is None or q25 is None or q75 is None:
            return None
        iqr = q75 - q25
        if iqr < 1e-9:
            return None

        # 実測値をDBスケール（小数）に変換
        if med_col == "interest_coverage_median":
            actual_db = actual_pct  # ICは倍率のまま
        else:
            actual_db = actual_pct / 100.0  # % → 小数

        diff = actual_db - med
        if not higher_better:
            diff = -diff
        score = 50.0 + (diff / iqr) * 25.0
        return round(max(0.0, min(100.0, score)), 1)

    return {
        "roe_rel":  _rel(roe,               "roe_median",               "roe_q25",               "roe_q75"),
        "roa_rel":  _rel(roa,               "roa_median",               "roa_q25",               "roa_q75"),
        "er_rel":   _rel(equity_ratio,      "equity_ratio_median",      "equity_ratio_q25",      "equity_ratio_q75"),
        "ic_rel":   _rel(interest_coverage, "interest_coverage_median", "interest_coverage_q25", "interest_coverage_q75"),
        "opm_rel":  _rel(operating_margin,  "operating_margin_median",  "operating_margin_q25",  "operating_margin_q75"),
        "alpha":    alpha,
        "available": True,
    }


# ─── セクター相対スコア計算（Vスコア用） ─────────────────────────────────

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _relative_score_lower_better(
    actual: Optional[float],
    median: Optional[float],
) -> Optional[float]:
    if actual is None or median in (None, 0):
        return None
    ratio = actual / median
    score = 100.0 - _clamp((ratio - 0.5) / 1.5 * 100.0, 0.0, 100.0)
    return round(score, 1)


def calc_sector_relative_scores(
    ft: Dict[str, Any],
    per: Optional[float],
    pbr: Optional[float],
    ev_ebitda: Optional[float],
) -> Dict[str, Any]:
    per_rel = _relative_score_lower_better(per,       ft.get("per_median"))
    pbr_rel = _relative_score_lower_better(pbr,       ft.get("pbr_median"))
    ev_rel  = _relative_score_lower_better(ev_ebitda, ft.get("ev_ebitda_median"))

    def _vs_text(actual, median, unit="x"):
        if actual is None: return "—"
        if median is None: return f"{actual:.1f}{unit}"
        diff_pct = (actual / median - 1) * 100
        sign = "+" if diff_pct >= 0 else ""
        return f"{actual:.1f}{unit}（中央値 {median:.1f}{unit} / {sign}{diff_pct:.0f}%）"

    rel_scores = [s for s in (per_rel, pbr_rel, ev_rel) if s is not None]
    sector_v_score = round(sum(rel_scores) / len(rel_scores), 1) if rel_scores else 50.0

    return {
        "per_rel_score":       per_rel,
        "pbr_rel_score":       pbr_rel,
        "ev_ebitda_rel_score": ev_rel,
        "per_vs_median":       _vs_text(per,       ft.get("per_median")),
        "pbr_vs_median":       _vs_text(pbr,       ft.get("pbr_median")),
        "ev_ebitda_vs_median": _vs_text(ev_ebitda, ft.get("ev_ebitda_median")),
        "sector_v_score":      sector_v_score,
    }


# ─── DBの全分類一覧（教育的表示用） ──────────────────────────────────────

def get_all_types_for_display(db: Optional[pd.DataFrame] = None) -> List[Dict[str, Any]]:
    if db is None:
        db = load_pattern_db()
    if db is None or db.empty:
        return []
    result = []
    for _, row in db.iterrows():
        result.append({
            "code":        str(row["financial_type_code"]),
            "ja":          str(row["financial_type_ja"]),
            "description": str(row["description"]),
            "confidence":  str(row["confidence"]),
            "sample_count": int(row["sample_count"]),
            "per_median":  _f(row, "per_median"),
            "pbr_median":  _f(row, "pbr_median"),
            "roe_median":  _f(row, "roe_median"),
            "roa_median":  _f(row, "roa_median"),
            "operating_margin_median": _f(row, "operating_margin_median"),
            "interest_coverage_median": _f(row, "interest_coverage_median"),
        })
    return result
