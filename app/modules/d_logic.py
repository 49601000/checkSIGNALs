"""
d_logic.py
────────────────────────────────────────────────────────────────────────────
D（価格防衛指数）スコア — 6サブ指標構造

  D1 MAトレンド防衛    : ① 200MA下回り日数比率
  D2 下方乖離耐性      : ② 200MAからの最大下方乖離
  D3 安値水準          : ③ 52週安値 / 200MA
  D4 ドローダウン耐性  : ④ 最大ドローダウン
  D5 下方ボラティリティ: ⑤ 下方ボラティリティ（年率）
  D6 出来高下方圧力    : ⑥ 下落日の出来高倍率平均

【正規化方針】
  各指標はベンチマーク基準で正規化。
    score = clip( 0.5 + k × (ticker_val - bm_val), 0, 1 )
    k = 0.5 / (3σ)
  ベンチマーク = 0.5（= BM相当）

【反転】
  defensive_score = 1 - D_index
  高い = ディフェンシブ性が高い（防衛力が強い）

【グレード】
  S  : 0.80以上
  A  : 0.65–0.80
  B  : 0.50–0.65
  C  : 0.35–0.50
  D  : 0.20–0.35
  E  : 0.20未満
  境界付近は 6指標の分布（上位/下位ランクの多数決）で +/- を付与。
  S+ / E- は不要。

【設計メモ】
  - t_logic / q_logic / v_logic と同じ dict 返却インターフェース
  - ノートブックのセル4〜8の計算ロジックをモジュール化
  - ベンチマーク値は呼び出し元（data_fetch.fetch_all_for_d_index）から注入
"""

from __future__ import annotations

from typing import Optional, Dict, Any, Tuple, List

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════
# 重み定義
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_D_WEIGHTS: Dict[str, float] = {
    "w1_below_ma_ratio": 0.18,   # ① MAトレンド防衛
    "w2_max_neg_dev":    0.18,   # ② 下方乖離耐性
    "w3_52w_low_vs_ma":  0.18,   # ③ 安値水準
    "w4_max_drawdown":   0.22,   # ④ ドローダウン耐性
    "w5_downside_vol":   0.12,   # ⑤ 下方ボラティリティ
    "w6_vol_pressure":   0.12,   # ⑥ 出来高下方圧力
}

# 列名 → 重みキー のマッピング（内部処理用）
_COL_WEIGHT_MAP: List[Tuple[str, str]] = [
    ("①_below_ma_ratio", "w1_below_ma_ratio"),
    ("②_max_neg_dev",    "w2_max_neg_dev"),
    ("③_52w_low_vs_ma",  "w3_52w_low_vs_ma"),
    ("④_max_drawdown",   "w4_max_drawdown"),
    ("⑤_downside_vol",   "w5_downside_vol"),
    ("⑥_vol_pressure",   "w6_vol_pressure"),
]

METRIC_COLS = [col for col, _ in _COL_WEIGHT_MAP]


def _normalize_d_weights(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        raise ValueError(f"D weights の合計が0以下です: {total}")
    return {k: v / total for k, v in weights.items()}


# ═══════════════════════════════════════════════════════════════════════════
# セル4: 6指標の計算関数
# ═══════════════════════════════════════════════════════════════════════════

def calc_below_ma_ratio(close: pd.Series, ma_period: int = 200) -> dict:
    """
    ① 200MA下回り日数比率
    = (終値 < MA の日数) / 有効日数合計
    MAが計算できる期間（ma_period日以降）で評価。
    """
    ma    = close.rolling(ma_period).mean()
    valid = close[ma.notna()]
    mav   = ma[ma.notna()]
    ratio = (valid < mav).sum() / len(valid) if len(valid) > 0 else np.nan
    return {"value": ratio, "ma": ma}


def calc_max_negative_deviation(close: pd.Series, ma_period: int = 200) -> dict:
    """
    ② 200MAからの最大下方乖離
    = |min((Close - MA) / MA)|
    """
    ma  = close.rolling(ma_period).mean()
    dev = (close - ma) / ma
    return {"value": abs(dev.min()), "deviation_series": dev}


def calc_52w_low_vs_ma(close: pd.Series, low: pd.Series,
                        ma_period: int = 200) -> dict:
    """
    ③ 52週安値 / 200MA
    score = max(1 - (52w安値 / MA), 0)  ※最終日時点の値を代表値
    """
    ma      = close.rolling(ma_period).mean()
    low_52w = low.rolling(252).min()
    ratio   = low_52w / ma
    score   = (1 - ratio).clip(lower=0)
    latest  = score.dropna().iloc[-1] if score.dropna().shape[0] > 0 else np.nan
    return {"value": latest, "52w_low": low_52w, "ratio_series": ratio}


def calc_max_drawdown(close: pd.Series) -> dict:
    """
    ④ 最大ドローダウン
    = |min((Close - cummax) / cummax)|
    """
    cummax = close.cummax()
    dd     = (close - cummax) / cummax
    return {
        "value":          abs(dd.min()),
        "mdd_date":       dd.idxmin(),
        "drawdown_series": dd,
    }


def calc_downside_volatility(close: pd.Series,
                              annual_factor: int = 252) -> dict:
    """
    ⑤ 下方ボラティリティ（年率）
    = std(負リターンのみ) × √252
    """
    ret = close.pct_change().dropna()
    dv  = ret[ret < 0].std() * np.sqrt(annual_factor)
    return {
        "value":            dv,
        "daily_returns":    ret,
        "negative_returns": ret[ret < 0],
    }


def calc_volume_pressure(close: pd.Series, volume: pd.Series,
                          vol_ma_window: int = 20) -> dict:
    """
    ⑥ 出来高加重下方圧力
    = 下落日（日次リターン < 0）における出来高倍率の平均
    出来高倍率 = 当日出来高 / 過去 vol_ma_window 日移動平均出来高

    > 1.0 → 下落時に出来高が集まりやすい → 売り圧力が強い
    """
    ret       = close.pct_change()
    vol_ma    = volume.rolling(vol_ma_window).mean()
    vol_ratio = volume / vol_ma.replace(0, np.nan)

    valid_mask = (volume > 0) & ret.notna() & vol_ma.notna()
    down_mask  = valid_mask & (ret < 0)

    pressure = vol_ratio[down_mask].mean() if down_mask.sum() > 0 else np.nan
    return {
        "value":     pressure,
        "vol_ratio": vol_ratio,
        "down_mask": down_mask,
        "n_down":    int(down_mask.sum()),
    }


def compute_raw_metrics(df: pd.DataFrame,
                        ma_period: int = 200,
                        vol_ma_window: int = 20) -> Tuple[dict, dict]:
    """
    DataFrame[Close, Low, Volume] から6指標の生値と中間データを計算する。

    Returns
    -------
    raw_vals : {"①_below_ma_ratio": float, ...}  各指標の生値
    detail   : 可視化用の中間 Series / スカラーをまとめた dict
    """
    close, low, volume = df["Close"], df["Low"], df["Volume"]

    r1 = calc_below_ma_ratio(close, ma_period)
    r2 = calc_max_negative_deviation(close, ma_period)
    r3 = calc_52w_low_vs_ma(close, low, ma_period)
    r4 = calc_max_drawdown(close)
    r5 = calc_downside_volatility(close)
    r6 = calc_volume_pressure(close, volume, vol_ma_window)

    raw_vals = {
        "①_below_ma_ratio": r1["value"],
        "②_max_neg_dev":    r2["value"],
        "③_52w_low_vs_ma":  r3["value"],
        "④_max_drawdown":   r4["value"],
        "⑤_downside_vol":   r5["value"],
        "⑥_vol_pressure":   r6["value"],
    }
    detail = {
        "ma":        r1["ma"],
        "deviation": r2["deviation_series"],
        "drawdown":  r4["drawdown_series"],
        "daily_ret": r5["daily_returns"],
        "52w_low":   r3["52w_low"],
        "mdd_date":  r4["mdd_date"],
        "vol_ratio": r6["vol_ratio"],
        "down_mask": r6["down_mask"],
        "n_down":    r6["n_down"],
    }
    return raw_vals, detail


def compute_benchmark_raw(
    bm_df: pd.DataFrame,
    ma_period: int = 200,
    vol_ma_window: int = 20,
) -> Dict[str, float]:
    """
    ベンチマーク価格データから D スコア正規化用の生値 dict を生成する。

    Parameters
    ----------
    bm_df : pd.DataFrame
        ベンチマークの価格データ DataFrame[Close, Low, Volume]
    ma_period : int
        移動平均ウィンドウ（デフォルト 200）
    vol_ma_window : int
        出来高移動平均ウィンドウ（デフォルト 20）

    Returns
    -------
    dict
        score_defense() にそのまま渡せるベンチマーク生値 dict
    """
    raw_vals, _ = compute_raw_metrics(
        bm_df,
        ma_period=ma_period,
        vol_ma_window=vol_ma_window,
    )
    return raw_vals


def build_benchmark_raw_store(
    bm_data: Dict[str, pd.DataFrame],
    ma_period: int = 200,
    vol_ma_window: int = 20,
) -> Dict[str, Dict[str, float]]:
    """
    市場別ベンチマーク価格データを D スコア用の生値ストアへ変換する。

    Parameters
    ----------
    bm_data : dict
        {market: DataFrame[Close, Low, Volume]}
    ma_period : int
        移動平均ウィンドウ（デフォルト 200）
    vol_ma_window : int
        出来高移動平均ウィンドウ（デフォルト 20）

    Returns
    -------
    dict
        {market: bm_raw_vals_dict}
    """
    bm_raw_store: Dict[str, Dict[str, float]] = {}
    for market, df in bm_data.items():
        bm_raw_store[market] = compute_benchmark_raw(
            df,
            ma_period=ma_period,
            vol_ma_window=vol_ma_window,
        )
    return bm_raw_store


# ═══════════════════════════════════════════════════════════════════════════
# セル5: ベンチマーク基準の正規化
# ═══════════════════════════════════════════════════════════════════════════

def benchmark_normalize(ticker_val: float, bm_val: float,
                         all_vals: pd.Series) -> float:
    """
    ベンチマーク基準の正規化スコアを計算する。

    score = clip( 0.5 + k × (ticker_val - bm_val), 0, 1 )
    k = 0.5 / (3σ)   ← 3σ分の差が ±0.5 に対応
    σ は全銘柄 + BM のプールで推定。

    Parameters
    ----------
    ticker_val : 対象銘柄の指標値（スカラー）
    bm_val     : ベンチマークの指標値（スカラー）
    all_vals   : スケール推定用プール（同市場銘柄 + BM の Series）

    Returns
    -------
    float : [0, 1] に正規化されたスコア（0.5 = BM相当）
    """
    pool = all_vals.dropna()
    std  = pool.std(ddof=0)

    if std < 1e-12 or np.isnan(std):
        return 0.5

    k     = 0.5 / (3.0 * std)
    score = 0.5 + k * (ticker_val - bm_val)
    return float(np.clip(score, 0.0, 1.0))


# ═══════════════════════════════════════════════════════════════════════════
# セル6: グレード付与ロジック
# ═══════════════════════════════════════════════════════════════════════════

# ② ランク境界定義
RANK_BOUNDS: List[Tuple[str, float, float]] = [
    ("S", 0.80, 1.01),
    ("A", 0.65, 0.80),
    ("B", 0.50, 0.65),
    ("C", 0.35, 0.50),
    ("D", 0.20, 0.35),
    ("E", 0.00, 0.20),
]

RANK_BOUNDARY_WIDTH = 0.075   # ±この範囲内を「境界付近」と判定


def get_base_rank(score: float) -> str:
    """② スコアからベースランク（S/A/B/C/D/E）を返す"""
    for rank, lo, hi in RANK_BOUNDS:
        if lo <= score < hi:
            return rank
    return "E"

PRESSURE_RANK_BOUNDS = [
    ("E",      0.80, 1.01),
    ("D",  0.65, 0.80),
    ("C",    0.50, 0.65),
    ("B",  0.35, 0.50),
    ("A",      0.00, 0.35),
]

def get_pressure_rank(score: float) -> str:
    for rank, lo, hi in PRESSURE_RANK_BOUNDS:
        if lo <= score < hi:
            return rank
    return "A"
  
def _get_rank_center(rank: str) -> float:
    """ランクの中央値を返す"""
    for r, lo, hi in RANK_BOUNDS:
        if r == rank:
            return (lo + hi) / 2 if hi < 1.01 else (lo + 1.0) / 2
    return 0.5


def get_plus_minus(score: float, base_rank: str,
                   metric_norm_scores: pd.Series) -> str:
    """
    ③④ +/- 判定

    ③ 境界付近でない場合（中央値ルール）:
       ランク幅を6分割したバッファで +/無印/- を決定。
       S+ / E- は不要なので除外。

    ④ 境界付近（RANK_BOUNDARY_WIDTH 以内）の場合（案X: 6指標の分布）:
       各指標の defensive スコア（1 - norm）でランクを評価し、
       上位ランクの指標が多ければ +、下位が多ければ -、同数は無印。

    Parameters
    ----------
    score              : defensive_score（0〜1）
    base_rank          : get_base_rank の結果
    metric_norm_scores : METRIC_COLS の正規化スコア Series（D指数方向）
    """
    rank_idx = [r for r, _, _ in RANK_BOUNDS]
    cur_idx  = rank_idx.index(base_rank)
    _, lo, hi = RANK_BOUNDS[cur_idx]

    near_upper = (hi < 1.01) and (score >= hi - RANK_BOUNDARY_WIDTH)
    near_lower = (lo > 0.00) and (score <  lo + RANK_BOUNDARY_WIDTH)

    if not near_upper and not near_lower:
        # ③ 中央値ルール
        mid  = _get_rank_center(base_rank)
        band = (hi - lo) / 6
        if score >= mid + band:
            suffix = "+" if base_rank != "S" else ""
        elif score <= mid - band:
            suffix = "-" if base_rank != "E" else ""
        else:
            suffix = ""
        return base_rank + suffix

    # ④ 境界付近: 6指標の分布で判定
    def_scores = 1.0 - metric_norm_scores   # 反転して defensive 方向に
    upper_count = lower_count = 0
    for ms in def_scores:
        ms_rank = get_base_rank(float(ms))
        ms_idx  = rank_idx.index(ms_rank)
        if ms_idx < cur_idx:
            upper_count += 1
        elif ms_idx > cur_idx:
            lower_count += 1

    if upper_count > lower_count:
        suffix = "+"
    elif lower_count > upper_count:
        suffix = "-"
    else:
        suffix = ""

    # S+ / E- は不要
    if base_rank == "S" and suffix == "+":
        suffix = ""
    if base_rank == "E" and suffix == "-":
        suffix = ""

    return base_rank + suffix


# ═══════════════════════════════════════════════════════════════════════════
# メイン: score_defense（他の *_logic.py と同じインターフェース）
# ═══════════════════════════════════════════════════════════════════════════

def score_defense(
    df: pd.DataFrame,
    bm_raw_vals: Dict[str, float],
    same_market_raw: Optional[Dict[str, Dict[str, float]]] = None,
    ma_period: int = 200,
    vol_ma_window: int = 20,
    weights: Optional[Dict[str, float]] = None,
) -> dict:
    """
    D（価格防衛）スコアを計算して dict で返す。

    t_logic.compute_t_metrics / q_logic.score_quality / v_logic.score_valuation
    と同じ「dict 返却」インターフェース。

    Parameters
    ----------
    df : pd.DataFrame
        対象銘柄の価格データ DataFrame[Close, Low, Volume]
    bm_raw_vals : dict
        ベンチマークの6指標生値
        例: {"①_below_ma_ratio": 0.32, "②_max_neg_dev": 0.18, ...}
    same_market_raw : dict, optional
        同一市場の全銘柄生値 {label: raw_vals_dict}
        指定すると σ 推定の精度が上がる。
        None の場合は対象銘柄とBMの2点のみでσを推定。
    ma_period : int
        移動平均ウィンドウ（デフォルト 200）
    vol_ma_window : int
        出来高移動平均ウィンドウ（デフォルト 20）
    weights : dict, optional
        6指標の重み。None なら DEFAULT_D_WEIGHTS を使用。

    Returns
    -------
    dict:
        d_score         : D_index（高い = リスク大）
        defensive_score : 1 - d_score（高い = ディフェンシブ）
        grade           : グレード文字列（例: 'B-', 'A+'）
        base_rank       : ベースランク（例: 'B'）
        d1〜d6          : 各指標の正規化スコア（0〜1, D指数方向）
        def1〜def6      : 各指標の defensive スコア（1 - d_n）
        raw             : 各指標の生値 dict
        detail          : 可視化用中間データ dict
        weights_used    : 使用した重み dict
    """
    w = _normalize_d_weights(weights or DEFAULT_D_WEIGHTS)

    # ── 生値・中間データの計算 ──
    raw_vals, detail = compute_raw_metrics(df, ma_period, vol_ma_window)

    # ── ベンチマーク基準の正規化 ──
    norm_scores: Dict[str, float] = {}
    for col in METRIC_COLS:
        ticker_val = raw_vals[col]
        bm_val     = bm_raw_vals.get(col, np.nan)

        # σ 推定用プール（同市場銘柄 + BM）
        if same_market_raw:
            group_vals = pd.Series({
                label: rv[col]
                for label, rv in same_market_raw.items()
                if col in rv
            })
        else:
            group_vals = pd.Series({"__self__": ticker_val})

        all_vals = pd.concat([
            group_vals,
            pd.Series({"__bm__": bm_val})
        ]).dropna()

        norm_scores[col] = benchmark_normalize(ticker_val, bm_val, all_vals)

    # ── D_index の合成 ──
    d_index = sum(
        norm_scores[col] * w[wk]
        for col, wk in _COL_WEIGHT_MAP
    )
    d_index = float(np.clip(d_index, 0.0, 1.0))

    # ── defensive_score（反転） ──
    defensive_score = round(1.0 - d_index, 4)

    # ── グレード付与 ──
    metric_norm_series = pd.Series({col: norm_scores[col] for col in METRIC_COLS})
    base_rank = get_base_rank(defensive_score)
    grade     = get_plus_minus(defensive_score, base_rank, metric_norm_series)

    # ── defensive 方向の指標スコア（1 - norm） ──
    display_scores = {
        "①_below_ma_ratio": round(1.0 - norm_scores["①_below_ma_ratio"], 4),
        "②_max_neg_dev":    round(1.0 - norm_scores["②_max_neg_dev"], 4),
        "③_52w_low_vs_ma":  round(1.0 - norm_scores["③_52w_low_vs_ma"], 4),
        "④_max_drawdown":   round(1.0 - norm_scores["④_max_drawdown"], 4),
        "⑤_downside_vol":   round(1.0 - norm_scores["⑤_downside_vol"], 4),
        "⑥_vol_pressure":   round(norm_scores["⑥_vol_pressure"], 4),   # ← ここだけ非反転
    }
    vp_score = round(norm_scores["⑥_vol_pressure"], 4)
    vp_rank  = get_pressure_rank(vp_score)
    return {
        # ── メインスコア ──
        "d_score":         round(d_index, 4),
        "defensive_score": defensive_score,
        "grade":           grade,
        "base_rank":       base_rank,

        # ── サブスコア（D指数方向）──
        "d1": round(norm_scores["①_below_ma_ratio"], 4),
        "d2": round(norm_scores["②_max_neg_dev"],    4),
        "d3": round(norm_scores["③_52w_low_vs_ma"],  4),
        "d4": round(norm_scores["④_max_drawdown"],   4),
        "d5": round(norm_scores["⑤_downside_vol"],   4),
        "d6": round(norm_scores["⑥_vol_pressure"],   4),
        "vp_score": vp_score,
        "vp_rank":  vp_rank,
      
        # ── サブスコア（defensive 方向）──
        "def1": def_scores["①_below_ma_ratio"],
        "def2": def_scores["②_max_neg_dev"],
        "def3": def_scores["③_52w_low_vs_ma"],
        "def4": def_scores["④_max_drawdown"],
        "def5": def_scores["⑤_downside_vol"],
        "def6": round(1.0 - norm_scores["⑥_vol_pressure"], 4),  # 従来維持
      
        "vp_score": round(norm_scores["⑥_vol_pressure"], 4),     # ← 新規追加（高いほど圧力強い） 

        # ── 生値・中間データ ──
        "raw":    raw_vals,
        "detail": detail,

        # ── 設定 ──
        "weights_used":    w,
        "ma_period":       ma_period,
        "vol_ma_window":   vol_ma_window,
    }

# ═══════════════════════════════════════════════════════════════════════════
# セル8: グレードサマリー生成（複数銘柄 → grade_df）
# ═══════════════════════════════════════════════════════════════════════════

# グレード表示順（ソート用）
GRADE_ORDER: List[str] = [
    "S", "S-",
    "A+", "A", "A-",
    "B+", "B", "B-",
    "C+", "C", "C-",
    "D+", "D", "D-",
    "E+", "E",
]

# グレード → 表示スタイル（Streamlit / Jupyter 共用）
GRADE_STYLE: Dict[str, Dict[str, str]] = {
    "S":  {"bg": "#1e3a5f", "fg": "#60a5fa"},
    "A":  {"bg": "#14532d", "fg": "#4ade80"},
    "B":  {"bg": "#1a2e05", "fg": "#a3e635"},
    "C":  {"bg": "#422006", "fg": "#fb923c"},
    "D":  {"bg": "#450a0a", "fg": "#f87171"},
    "E":  {"bg": "#27272a", "fg": "#a1a1aa"},
}


def grade_color_css(grade: str) -> str:
    """
    グレード文字列から CSS スタイル文字列を返す。
    Jupyter の .applymap / Streamlit の st.markdown で使用可能。

    例: 'B-' → 'background-color: #1a2e05; color: #a3e635'
    """
    key = grade[0] if grade else "E"   # 先頭1文字でスタイルを決定
    style = GRADE_STYLE.get(key, GRADE_STYLE["E"])
    return f"background-color: {style['bg']}; color: {style['fg']}"


def compute_grade_summary(
    results: List[Dict[str, Any]],
) -> pd.DataFrame:
    """
    score_defense の返却値リストから grade_df を生成する。

    セル8の以下のブロックに相当:
        results = []
        for label in norm_df.index:
            ...
        grade_df = pd.DataFrame(results).set_index('Ticker')

    Parameters
    ----------
    results : list of dict
        各銘柄の score_defense 返却値に以下のキーを追加したリスト:
            - "label"     : ティッカー表示ラベル
            - "market"    : 市場区分
            - "bm_label"  : ベンチマーク名

    Returns
    -------
    pd.DataFrame
        インデックス = Ticker
        カラム:
            Market, Benchmark, defensive_score, Grade,
            ①_below_ma_ratio 〜 ⑥_vol_pressure（defensive 方向）
    """
    rows = []
    for r in results:
        label = r.get("label", "")
        row = {
            "Ticker":          label,
            "Market":          r.get("market", ""),
            "Benchmark":       r.get("bm_label", ""),
            "defensive_score": r["defensive_score"],
            "Grade":           r["grade"],
        }
        # 指標別 defensive スコア（1 - norm、高い = 防衛力が高い）
        for col in METRIC_COLS:
            key = f"def{METRIC_COLS.index(col) + 1}"   # def1〜def6
            row[col] = r.get(key, float("nan"))
        rows.append(row)

    df = pd.DataFrame(rows).set_index("Ticker")
    df = df.sort_values("defensive_score", ascending=False)
    return df


def build_results_list(
    price_data: Dict[str, pd.DataFrame],
    ticker_meta: Dict[str, dict],
    bm_data: Dict[str, pd.DataFrame],
    ma_period: int = 200,
    vol_ma_window: int = 20,
    weights: Optional[Dict[str, float]] = None,
) -> Tuple[List[dict], Dict[str, dict], Dict[str, dict]]:
    """
    複数銘柄のスコアを一括計算し、results リストと中間データを返す。

    セル6の calc_d_index() 相当のエントリポイント。
    単一銘柄アプリでも複数銘柄ノートブックでも使える汎用関数。

    Parameters
    ----------
    price_data   : {label: DataFrame[Close, Low, Volume]}
    ticker_meta  : {label: parse_ticker_for_d の返却 dict}
    bm_data      : {market: DataFrame[Close, Low, Volume]}
    ma_period    : int
    vol_ma_window: int
    weights      : dict, optional

    Returns
    -------
    results      : score_defense 結果リスト（label/market/bm_label を追加済み）
    detail_store : {label: detail dict}（可視化用）
    bm_raw_store : {market: raw_vals dict}（ベンチマーク生値）
    """
    # ── ベンチマーク生値の事前計算 ──
    bm_raw_store = build_benchmark_raw_store(
        bm_data,
        ma_period=ma_period,
        vol_ma_window=vol_ma_window,
    )

    # ── 全銘柄の生値を先に計算（σ推定プール用）──
    all_raw: Dict[str, dict] = {}
    for label, df in price_data.items():
        rv, _ = compute_raw_metrics(df, ma_period, vol_ma_window)
        all_raw[label] = rv

    # ── 市場別グループ化 ──
    market_groups: Dict[str, Dict[str, dict]] = {}
    for label, meta in ticker_meta.items():
        mkt = meta["market"]
        market_groups.setdefault(mkt, {})[label] = all_raw.get(label, {})

    # ── 銘柄ごとの score_defense 計算 ──
    results: List[dict] = []
    detail_store: Dict[str, dict] = {}

    for label, df in price_data.items():
        meta    = ticker_meta[label]
        market  = meta["market"]
        bm_rv   = bm_raw_store.get(market, {})
        same_rv = market_groups.get(market, {})

        result = score_defense(
            df            = df,
            bm_raw_vals   = bm_rv,
            same_market_raw = same_rv,
            ma_period     = ma_period,
            vol_ma_window = vol_ma_window,
            weights       = weights,
        )

        # label / market / bm_label をスコア dict に追加
        result["label"]    = label
        result["market"]   = market
        result["bm_label"] = meta.get("bm_label", "")

        results.append(result)
        detail_store[label] = result["detail"]

    return results, detail_store, bm_raw_store
