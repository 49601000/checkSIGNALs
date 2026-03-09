"""
pattern_db.py
──────────────────────────────────────────────────────────────────────────
財務特性分類DB（pattern_db_latest.csv）を読み込み、
銘柄のティッカーから財務タイプを判定して、
セクター相対 PER / PBR / EV/EBITDA 評価を提供するモジュール。

【役割】
- CSV を起動時に一度だけ読み込みキャッシュ（st.cache_data）
- ティッカーが ticker_list に含まれるか線形探索で分類コードを確定
- 分類が確定したら中央値・四分位を使ってセクター相対スコアを計算
- 分類コードが不明（UNK）でも「絶対値のみ」として機能は壊れない

【セクター相対スコアの計算方針】
  - PER/PBR は「中央値より低い（割安）ほど高得点」
  - EV/EBITDA も同様に低いほど高得点
  - 対象指標がセクター中央値の何倍かを ratio として計算
    ratio < 0.5   → 100点（かなり割安）
    ratio ≒ 1.0   → 50点（中央値相当）
    ratio > 2.0   → 0点（かなり割高）
  - 線形補間: score = clamp(100 - (ratio - 0.5) / 1.5 * 100, 0, 100)

【注意】
- このモジュールは日本株のみ対象（ticker_list が .T 形式）
- 米国株は UNK 扱いとし、従来の絶対評価のみを使用する
"""

from __future__ import annotations

import os
from typing import Optional, Dict, Any, Tuple

import pandas as pd
import streamlit as st


# ─── CSV パス ──────────────────────────────────────────────────────────────
# Streamlit Cloud では streamlit_app.py と同じルートに置く想定。
# ローカル開発では環境変数 PATTERN_DB_PATH で上書き可能。
_DEFAULT_CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "pattern_db_latest.csv"
)
PATTERN_DB_PATH = os.environ.get("PATTERN_DB_PATH", _DEFAULT_CSV_PATH)


# ─── DB ロード（キャッシュ） ───────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_pattern_db() -> pd.DataFrame:
    """CSVを読み込んで DataFrame で返す（起動時1回のみ）。"""
    path = PATTERN_DB_PATH
    if not os.path.exists(path):
        # フォールバック: 同ディレクトリ直下を探す
        for candidate in [
            "pattern_db_latest.csv",
            "data/pattern_db_latest.csv",
            "app/data/pattern_db_latest.csv",
        ]:
            if os.path.exists(candidate):
                path = candidate
                break
        else:
            return pd.DataFrame()  # 見つからなければ空 DF

    df = pd.read_csv(path, encoding="utf-8-sig")
    # ticker_list をパースしてリスト化しておく
    df["_ticker_set"] = df["ticker_list"].apply(
        lambda x: set(str(x).replace('"', "").split(",")) if pd.notna(x) else set()
    )
    return df


# ─── ティッカー → 財務タイプ判定 ─────────────────────────────────────────

def classify_ticker(ticker: str, db: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """
    ティッカーを財務特性DBで検索し、分類情報を返す。

    Returns
    -------
    dict with keys:
        code        : str  分類コード (e.g. "HQLg", "UNK")
        name        : str  英語名
        ja          : str  日本語名
        description : str  説明文
        confidence  : str  "HIGH" / "MID" / "NONE"
        matched     : bool ティッカーがDBで見つかったか
        per_median  : float or None
        per_q25     : float or None
        per_q75     : float or None
        pbr_median  : float or None
        pbr_q25     : float or None
        pbr_q75     : float or None
        ev_ebitda_median : float or None
        roe_median  : float or None
        roa_median  : float or None
        operating_margin_median : float or None
        interest_coverage_median : float or None
    """
    _unk = {
        "code": "UNK", "name": "UNCLASSIFIED", "ja": "分類不能・データ不足",
        "description": "DBに該当エントリなし。絶対評価のみを使用します。",
        "confidence": "NONE", "matched": False,
        "per_median": None, "per_q25": None, "per_q75": None,
        "pbr_median": None, "pbr_q25": None, "pbr_q75": None,
        "ev_ebitda_median": None,
        "roe_median": None, "roa_median": None,
        "operating_margin_median": None, "interest_coverage_median": None,
    }

    if db is None:
        db = load_pattern_db()
    if db.empty:
        return _unk

    # .T 付き / なし両方で検索
    t_norm = ticker.strip().upper()
    candidates = {t_norm}
    if t_norm.endswith(".T"):
        candidates.add(t_norm[:-2])
    else:
        candidates.add(t_norm + ".T")

    for _, row in db.iterrows():
        if row["_ticker_set"] & candidates:
            def _f(col):
                v = row.get(col)
                return float(v) if pd.notna(v) else None

            return {
                "code": str(row["financial_type_code"]),
                "name": str(row["financial_type_name"]),
                "ja":   str(row["financial_type_ja"]),
                "description": str(row["description"]),
                "confidence":  str(row["confidence"]),
                "matched": True,
                "per_median":  _f("per_median"),
                "per_q25":     _f("per_q25"),
                "per_q75":     _f("per_q75"),
                "pbr_median":  _f("pbr_median"),
                "pbr_q25":     _f("pbr_q25"),
                "pbr_q75":     _f("pbr_q75"),
                "ev_ebitda_median": _f("ev_ebitda_median"),
                "roe_median":  _f("roe_median"),
                "roa_median":  _f("roa_median"),
                "operating_margin_median": _f("operating_margin_median"),
                "interest_coverage_median": _f("interest_coverage_median"),
            }

    return _unk


# ─── セクター相対スコア計算 ───────────────────────────────────────────────

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _relative_score_lower_better(
    actual: Optional[float],
    median: Optional[float],
    lo_ratio: float = 0.5,
    hi_ratio: float = 2.0,
) -> Optional[float]:
    """
    「低いほど良い」指標のセクター相対スコア（PER / PBR / EV/EBITDA）。

    ratio = actual / median
    ratio == lo_ratio → 100点
    ratio == 1.0      → 線形補間
    ratio == hi_ratio → 0点
    """
    if actual is None or median in (None, 0):
        return None
    ratio = actual / median
    # lo_ratio〜hi_ratio を 100〜0 にマッピング
    score = 100.0 - _clamp(
        (ratio - lo_ratio) / (hi_ratio - lo_ratio) * 100.0, 0.0, 100.0
    )
    return round(score, 1)


def calc_sector_relative_scores(
    ft: Dict[str, Any],
    per: Optional[float],
    pbr: Optional[float],
    ev_ebitda: Optional[float],
) -> Dict[str, Any]:
    """
    財務タイプ情報（ft）と実測値から、セクター相対スコアを計算して返す。

    Returns
    -------
    dict:
        per_rel_score      : float or None  (0〜100)
        pbr_rel_score      : float or None
        ev_ebitda_rel_score: float or None
        per_vs_median      : str   表示用テキスト (例: "15.2x (中央値 17.0x)")
        pbr_vs_median      : str
        ev_ebitda_vs_median: str
        sector_v_score     : float  セクター相対Vサブスコア（0〜100）
    """
    per_rel   = _relative_score_lower_better(per,       ft.get("per_median"))
    pbr_rel   = _relative_score_lower_better(pbr,       ft.get("pbr_median"))
    ev_rel    = _relative_score_lower_better(ev_ebitda, ft.get("ev_ebitda_median"))

    def _vs_text(actual, median, unit="x"):
        if actual is None:
            return "—"
        if median is None:
            return f"{actual:.1f}{unit}"
        diff_pct = (actual / median - 1) * 100
        sign = "+" if diff_pct >= 0 else ""
        return f"{actual:.1f}{unit}（中央値 {median:.1f}{unit} / {sign}{diff_pct:.0f}%）"

    # セクター相対 V スコア：有効なスコアの平均
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

def get_all_types_for_display(db: Optional[pd.DataFrame] = None) -> list[Dict[str, Any]]:
    """
    全財務タイプの code / ja / description / 主要中央値 を辞書リストで返す。
    UIの「財務タイプ辞典」表示で使用。
    """
    if db is None:
        db = load_pattern_db()
    if db.empty:
        return []

    result = []
    for _, row in db.iterrows():
        def _f(col):
            v = row.get(col)
            return float(v) if pd.notna(v) else None

        result.append({
            "code":        str(row["financial_type_code"]),
            "ja":          str(row["financial_type_ja"]),
            "description": str(row["description"]),
            "confidence":  str(row["confidence"]),
            "sample_count": int(row["sample_count"]),
            "per_median":  _f("per_median"),
            "pbr_median":  _f("pbr_median"),
            "roe_median":  _f("roe_median"),
            "roa_median":  _f("roa_median"),
            "operating_margin_median": _f("operating_margin_median"),
            "interest_coverage_median": _f("interest_coverage_median"),
        })
    return result
