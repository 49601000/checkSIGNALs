"""
app/ui/magi/main.py — MAGI SYSTEM UI

エントリーポイント: run()
  app/main.py から動的インポートされ、run() が呼ばれる。
"""

import streamlit as st
from modules.data_fetch import convert_ticker, get_price_and_meta
from modules.indicators import compute_indicators
from modules.q_correction import apply_q_correction
from modules.pattern_db import (
    load_pattern_db,
    classify_ticker,
    calc_sector_relative_scores,            # 財務タイプ表示用（旧・変更なし）
    calc_sector_relative_scores_from_db,    # V4 計算用（sector_db ベース・新方式）
    load_sector_db,                         # sector_db_latest.csv ローダー
    get_all_types_for_display,
)


# ─── スタイル ─────────────────────────────────────────────────

def _setup_style():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&family=Noto+Sans+JP:wght@400;700&family=Noto+Serif+JP:wght@900&display=swap');

    :root {
        --bg:         #0a0a0a;
        --surface:    #111111;
        --card:       #161616;
        --border:     #2a2a2a;
        --text:       #ff6600;
        --text-dim:   #cc4400;
        --text-dark:  #662200;
        --blue-glow:  #4477ff;
        --red-bright: #ff2222;
        --red-glow:   #ff4444;
        --orange:     #ff6600;
        --jp-mincho:  'Noto Serif JP', 'Hiragino Mincho ProN', 'Yu Mincho', serif;
    }

    html, body, [class*="css"] {
        font-family: 'Share Tech Mono', var(--jp-mincho), monospace;
        background-color: var(--bg) !important;
        color: var(--text) !important;
    }
    .stApp, .stApp > div, section.main, .block-container {
        background-color: var(--bg) !important;
    }
    .main > div { padding-top: 0.5rem; padding-bottom: 3rem; }

    /* スキャンライン */
    .stApp::before {
        content: '';
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: repeating-linear-gradient(
            0deg,
            rgba(255,100,0,0.03) 0px, rgba(255,100,0,0.03) 1px,
            transparent 1px, transparent 3px
        );
        pointer-events: none; z-index: 9999;
    }

    /* ヘッダーバナー */
    .magi-banner {
        background: #000; border: 1px solid var(--orange);
        border-bottom: 3px solid var(--orange);
        padding: 4px 10px; margin-bottom: 2px;
        font-family: 'Share Tech Mono', monospace;
        font-size: 0.58rem; color: var(--orange); letter-spacing: 2px;
    }
    .magi-banner-title {
        font-family: 'Orbitron', monospace;
        font-size: 1.1rem; font-weight: 900; color: #fff;
        letter-spacing: 3px; text-align: center;
        background: var(--orange); padding: 4px; margin-bottom: 2px;
        text-shadow: 0 0 10px rgba(255,102,0,0.8);
    }

    /* 検索バー */
    div[data-testid="stTextInput"] input {
        font-family: 'Share Tech Mono', monospace !important;
        font-size: 1rem !important; font-weight: 600 !important;
        height: 2.8rem !important; border-radius: 0 !important;
        border: 1px solid var(--orange) !important;
        background: #000 !important; color: var(--orange) !important;
        letter-spacing: 2px;
    }
    div[data-testid="stTextInput"] input::placeholder { color: var(--text-dark) !important; }
    div[data-testid="stButton"] > button {
        height: 2.8rem !important; font-size: 0.85rem !important;
        font-weight: 700 !important; border-radius: 0 !important;
        border: 1px solid var(--orange) !important;
        background: var(--orange) !important; color: #000 !important;
        font-family: 'Orbitron', monospace !important; letter-spacing: 2px; width: 100%;
    }
    div[data-testid="stButton"] > button:hover { background: #fff !important; color: #000 !important; }

    /* MAGIメインコンテナ */
    .magi-container {
        background: #000; border: 2px solid var(--orange);
        padding: 0; margin: 0.5rem 0;
        font-family: 'Share Tech Mono', monospace;
    }
    .magi-header-strip {
        background: var(--orange); color: #000;
        font-family: 'Orbitron', monospace;
        font-size: 0.7rem; font-weight: 700; letter-spacing: 3px;
        padding: 3px 8px; text-align: center;
    }

    /* ノード（六角形風） */
    .magi-node {
        border: 2px solid; padding: 0.5rem 0.8rem; text-align: center;
        position: relative; min-width: 110px;
        clip-path: polygon(10% 0%, 90% 0%, 100% 50%, 90% 100%, 10% 100%, 0% 50%);
    }
    .magi-node-approve {
        border-color: var(--blue-glow);
        background: rgba(20, 60, 180, 0.3);
        box-shadow: 0 0 15px rgba(68,119,255,0.4), inset 0 0 10px rgba(68,119,255,0.1);
    }
    .magi-node-deny {
        border-color: var(--red-glow);
        background: rgba(180, 20, 20, 0.3);
        box-shadow: 0 0 15px rgba(255,68,68,0.4), inset 0 0 10px rgba(255,68,68,0.1);
    }
    .magi-node-label {
        font-family: 'Orbitron', monospace;
        font-size: 0.6rem; font-weight: 700; letter-spacing: 1px; margin-bottom: 2px;
    }
    .magi-node-approve .magi-node-label { color: #aaccff; }
    .magi-node-deny   .magi-node-label { color: #ffaaaa; }
    .magi-node-verdict {
        font-family: 'Noto Serif JP', 'Orbitron', serif;
        font-size: 1.05rem; font-weight: 900; letter-spacing: 2px;
    }
    .magi-node-approve .magi-node-verdict { color: #fff; text-shadow: 0 0 12px #4477ff; }
    .magi-node-deny    .magi-node-verdict { color: #fff; text-shadow: 0 0 12px #ff4444; }
    .magi-node-score { font-family: 'Share Tech Mono', monospace; font-size: 0.75rem; margin-top: 2px; }
    .magi-node-approve .magi-node-score { color: #88bbff; }
    .magi-node-deny    .magi-node-score { color: #ff8888; }

    /* 中央MAGIパネル */
    .magi-center-panel {
        border: 2px solid var(--orange);
        background: rgba(255, 102, 0, 0.08);
        padding: 0.6rem 1rem; text-align: center;
        margin: 6px auto; max-width: 200px;
    }
    .magi-center-name {
        font-family: 'Orbitron', monospace;
        font-size: 0.85rem; font-weight: 900; color: var(--orange);
        letter-spacing: 4px; text-shadow: 0 0 10px rgba(255,102,0,0.7);
    }
    .magi-center-comment { font-size: 0.65rem; color: var(--orange); letter-spacing: 0.5px; line-height: 1.4; font-family: 'Noto Serif JP', serif !important; font-weight: 900 !important; }

    /* 情報パネル */
    .info-panel {
        background: #000; border: 1px solid var(--orange);
        padding: 0.5rem 0.7rem;
        font-family: var(--jp-mincho);
        font-size: 0.62rem; color: var(--orange); line-height: 1.8;
        font-weight: 900;
    }
    .info-panel-title {
        font-family: 'Orbitron', monospace;
        font-size: 0.55rem; letter-spacing: 2px; color: var(--text-dim);
        border-bottom: 1px solid var(--text-dark);
        padding-bottom: 3px; margin-bottom: 5px;
    }
    .info-row { display: flex; justify-content: space-between; margin-bottom: 1px; }
    .info-val { color: #ffaa66; font-weight: 700; }
    .info-val-up { color: #ff4444; }
    .info-val-down { color: #44ff88; }

    /* 待機画面 */
    .magi-idle {
        background: #000; border: 2px solid var(--orange);
        padding: 2rem; text-align: center; margin: 1rem 0;
        position: relative; overflow: hidden;
    }
    .magi-idle::before {
        content: ''; position: absolute; top: -50%; left: -50%;
        width: 200%; height: 200%;
        background: conic-gradient(transparent, rgba(255,102,0,0.05), transparent);
        animation: rotate 8s linear infinite;
    }
    @keyframes rotate { 100% { transform: rotate(360deg); } }
    .magi-idle-text {
        font-family: 'Orbitron', monospace;
        font-size: 1.4rem; font-weight: 900; color: var(--orange);
        letter-spacing: 6px; text-shadow: 0 0 20px rgba(255,102,0,0.8);
        animation: pulse 2s ease-in-out infinite; position: relative; z-index: 1;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; text-shadow: 0 0 20px rgba(255,102,0,0.8); }
        50%       { opacity: 0.6; text-shadow: 0 0 5px rgba(255,102,0,0.3); }
    }
    .magi-idle-sub { font-size: 0.6rem; color: var(--text-dark); letter-spacing: 3px; margin-top: 0.5rem; position: relative; z-index: 1; }

    /* タブ */
    div[data-testid="stTabs"] {
        background: #000 !important;
        border: 1px solid var(--orange) !important;
        border-top: 3px solid var(--orange) !important;
    }
    div[data-testid="stTabs"] button {
        font-family: 'Orbitron', monospace !important;
        font-size: 0.65rem !important; font-weight: 700 !important;
        letter-spacing: 1px !important; color: var(--text-dim) !important;
        border-radius: 0 !important; border-bottom: 2px solid transparent !important;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        color: var(--orange) !important;
        border-bottom: 2px solid var(--orange) !important;
        background: rgba(255,102,0,0.08) !important;
    }

    /* メトリクス */
    div[data-testid="metric-container"] {
        background: #000 !important; border: 1px solid var(--orange) !important;
        border-radius: 0 !important; padding: 0.6rem !important;
    }
    div[data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-family: 'Share Tech Mono', var(--jp-mincho), monospace !important;
        font-size: 1.4rem !important; font-weight: 900 !important; color: var(--orange) !important;
    }
    div[data-testid="metric-container"] label {
        font-family: 'Orbitron', monospace !important;
        font-size: 0.55rem !important; font-weight: 700 !important;
        color: var(--text-dim) !important; letter-spacing: 1.5px !important;
    }

    /* テーブル */
    .cs-table {
        width: 100%; border-collapse: collapse;
        font-family: 'Share Tech Mono', monospace; font-size: 0.82rem;
        border: 1px solid var(--orange);
    }
    .cs-table thead th {
        background: rgba(255,102,0,0.15); color: var(--orange);
        font-family: 'Orbitron', monospace; font-size: 0.55rem; letter-spacing: 2px;
        padding: 6px 10px; border-bottom: 1px solid var(--orange);
    }
    .cs-table tbody tr { border-bottom: 1px solid rgba(255,102,0,0.15); }
    .cs-table tbody tr:nth-child(odd)  { background: rgba(255,102,0,0.03); }
    .cs-table tbody tr:nth-child(even) { background: transparent; }
    .cs-table tbody td { padding: 7px 10px; color: var(--orange); font-family: var(--jp-mincho); font-weight: 900; }
    .td-ok {
        display: inline-flex; align-items: center; justify-content: center;
        width: 22px; height: 22px;
        background: rgba(68,119,255,.20); color: #4477ff;
        font-weight: 900; font-size: 0.75rem; border: 1.5px solid rgba(68,119,255,.5);
    }
    .td-ng {
        display: inline-flex; align-items: center; justify-content: center;
        width: 22px; height: 22px;
        background: rgba(255,68,68,.20); color: #ff4444;
        font-weight: 900; font-size: 0.75rem; border: 1.5px solid rgba(255,68,68,.5);
    }
    .td-neu { color: var(--text-dark); font-size: 0.9rem; }
    .td-right { text-align: right; }
    .ev-badge {
        display: inline-block; background: rgba(68,119,255,.15); color: #88aaff;
        font-size: 0.68rem; border: 1px solid rgba(68,119,255,.4); padding: 1px 5px;
    }

    /* シグナルバナー */
    .signal-banner {
        border: 1px solid; padding: 0.8rem 1rem; margin-bottom: 0.8rem;
        display: flex; align-items: center; gap: 0.8rem;
    }
    .signal-icon { font-size: 1.6rem; }
    .signal-text { font-family: 'Noto Serif JP', 'Orbitron', serif; font-size: 0.9rem; font-weight: 900; color: var(--orange); }
    .signal-sub  { font-size: 0.7rem; color: var(--text-dim); margin-top: 0.1rem; font-family: 'Noto Serif JP', serif; font-weight: 900; }

    /* レンジグリッド */
    .range-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4px; }
    .range-item { background: #000; border: 1px solid var(--orange); padding: 0.6rem; text-align: center; }
    .range-lbl {
        font-family: 'Orbitron', monospace; font-size: 0.55rem; letter-spacing: 1px;
        color: var(--text-dim); font-weight: 700; margin-bottom: 0.25rem;
    }
    .range-val { font-family: 'Share Tech Mono', monospace; font-size: 1rem; font-weight: 700; color: var(--orange); }

    /* スコアカード */
    .score-card { background: #000; border: 1px solid var(--orange); padding: 0.8rem; text-align: center; margin-bottom: 4px; }
    .score-label {
        font-family: 'Orbitron', monospace; font-size: 0.55rem; letter-spacing: 2px;
        color: var(--text-dim); font-weight: 700; margin-bottom: 0.3rem;
    }
    .score-value { font-family: 'Share Tech Mono', monospace; font-size: 2rem; font-weight: 700; line-height: 1; }
    .score-max   { font-size: 0.6rem; color: var(--text-dark); margin-top: 0.2rem; font-family: 'Noto Serif JP', serif; font-weight: 900; }

    hr { border-color: rgba(255,102,0,0.3) !important; }
    div[data-testid="stExpander"] {
        background: #000 !important; border: 1px solid var(--orange) !important; border-radius: 0 !important;
    }
    div[data-testid="stAlert"] {
        background-color: rgba(255,102,0,0.08) !important;
        border: 1px solid var(--orange) !important; color: var(--orange) !important;
    }
    div[data-testid="stNumberInput"] input {
        font-family: 'Share Tech Mono', monospace !important;
        background: #000 !important; color: var(--orange) !important;
        border: 1px solid var(--orange) !important; border-radius: 0 !important;
    }
    .stCaption { color: var(--text-dim) !important; font-size: 0.65rem !important; }
    /* Streamlit本文テキスト（caption, info, markdownなど） */
    .stMarkdown p, .stMarkdown li, .stMarkdown td, .stMarkdown span,
    div[data-testid="stCaptionContainer"],
    div[data-testid="stCaptionContainer"] p,
    div[data-testid="stAlert"],
    div[data-testid="stAlert"] p,
    .stWarning p, .stInfo p {
        font-family: 'Noto Serif JP', serif !important;
        font-weight: 900 !important;
    }

    /* expander：矢印アイコンを非表示 */
    div[data-testid="stExpander"] summary svg,
    div[data-testid="stExpander"] summary [data-testid="stExpanderToggleIcon"] {
        display: none !important;
    }

    /* expanderラベル（summary直下のテキストノードを持つp）を明朝体に */
    div[data-testid="stExpander"] summary p {
        font-family: 'Noto Serif JP', serif !important;
        font-weight: 900 !important;
        font-size: 0.85rem !important;
        letter-spacing: 0.05em !important;
        padding-left: 0 !important;
    }

    /* expanderコンテンツ内テキスト */
    div[data-testid="stExpander"] div[data-testid="stExpanderDetails"] p,
    div[data-testid="stExpander"] div[data-testid="stExpanderDetails"] li,
    div[data-testid="stExpander"] div[data-testid="stExpanderDetails"] td,
    div[data-testid="stExpander"] div[data-testid="stExpanderDetails"] th {
        font-family: 'Noto Serif JP', serif !important;
        font-weight: 900 !important;
    }

    /* st.metricのdelta値など */
    div[data-testid="stMetricDelta"],
    div[data-testid="stMetricDelta"] p,
    div[data-testid="stMetricDelta"] span {
        font-family: 'Noto Serif JP', serif !important;
        font-weight: 900 !important;
    }

    /* st.caption */
    .stCaption, .stCaption p, .stCaption span,
    div[data-testid="stCaptionContainer"] *,
    small { 
        font-family: 'Noto Serif JP', serif !important;
        font-weight: 900 !important;
    }

    /* signal-banner内テキスト（明朝+!important強制） */
    .signal-text {
        font-family: 'Noto Serif JP', serif !important;
        font-weight: 900 !important;
        font-size: 0.95rem !important;
    }
    .signal-sub {
        font-family: 'Noto Serif JP', serif !important;
        font-weight: 900 !important;
        font-size: 0.72rem !important;
    }

    /* stMarkdown — p/li/td のみ対象（* は使わない） */
    .stMarkdown p, .stMarkdown li, .stMarkdown td, .stMarkdown th,
    .stMarkdown strong, .stMarkdown em {
        font-family: 'Noto Serif JP', serif !important;
        font-weight: 900 !important;
    }

    /* st.info / st.warning バナー本文のみ */
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] li {
        font-family: 'Noto Serif JP', serif !important;
        font-weight: 900 !important;
    }

    /* number_input / text_input ラベル */
    div[data-testid="stNumberInput"] label p,
    div[data-testid="stTextInput"] label p {
        font-family: 'Noto Serif JP', serif !important;
        font-weight: 900 !important;
    }

    /* Orbitron を維持すべき要素（再指定で保護） */
    .magi-node-label, .magi-center-name, .info-panel-title,
    .range-lbl, .score-label, .cs-table thead th,
    div[data-testid="stTabs"] button,
    div[data-testid="stButton"] > button,
    .magi-banner, .magi-banner-title, .magi-header-strip {
        font-family: 'Orbitron', monospace !important;
    }
    /* Share Tech Mono を維持すべき要素 */
    .magi-node-score, .range-val, .score-value,
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-family: 'Share Tech Mono', monospace !important;
    }

    </style>
    """, unsafe_allow_html=True)


# ─── ヘルパー ─────────────────────────────────────────────────

def _fmt(x, d=2):
    return "—" if x is None else f"{float(x):.{d}f}"

def _fmt_pct(x):
    return "—" if x is None else f"{float(x):.1f}%"

def _fmt_x(x):
    return "—" if x is None else f"{float(x):.2f}倍"

def _color_score(s):
    return "var(--blue-glow)" if s >= 60 else "var(--red-bright)"

def _signal_style(strength, hi_alert):
    if strength >= 3: return "background:rgba(68,119,255,.1);border-color:#4477ff;"
    if strength == 2: return "background:rgba(255,170,0,.08);border-color:#ffaa00;"
    if hi_alert:      return "background:rgba(255,68,68,.1);border-color:#ff4444;"
    return "background:rgba(255,102,0,.08);border-color:#ff6600;"

def _build_table(headers, rows):
    ths  = "".join(f"<th>{h}</th>" for h in headers)
    html = f'<table class="cs-table"><thead><tr>{ths}</tr></thead><tbody>'
    for row in rows:
        cells = "".join(f"<td>{c}</td>" for c in row)
        html += f"<tr>{cells}</tr>"
    html += "</tbody></table>"
    return html

def _node_verdict(score, threshold=60):
    return ("approve", "承認") if score >= threshold else ("deny", "否定")

def _magi_comment(qvt):
    if qvt >= 70: return "主力候補 — 全システム承認"
    if qvt >= 60: return "買い検討 — 押し目を慎重に"
    if qvt >= 50: return "比較推奨 — 他候補と比較を"
    return "見送推奨 — テーマ性を要確認"


# ─── MAGIパネル ───────────────────────────────────────────────

def render_magi_panel(q, v, t, qvt, ticker, base, tech):
    close        = base["close"]
    prev         = base["previous_close"]
    company_name = base.get("company_name", "").rstrip("の").strip()  # ②③ 銘柄名・末尾"の"除去
    industry     = base.get("industry", "")
    sector       = base.get("sector", "")
    change       = close - prev
    change_pct   = (change / prev * 100) if prev else 0
    sign         = "+" if change >= 0 else ""
    chg_cls      = "info-val-up" if change >= 0 else "info-val-down"
    d            = 0 if close >= 100 else 2

    rsi     = tech.get("rsi")
    bb_icon = tech.get("bb_icon", "—")
    bb_text = tech.get("bb_text", "—")
    ma25    = tech.get("ma_25")
    ma50    = tech.get("ma_50")
    ma75    = tech.get("ma_75")
    hi52    = tech.get("high_52w")
    lo52    = tech.get("low_52w")

    q_cls, q_verd = _node_verdict(q)
    v_cls, v_verd = _node_verdict(v)
    t_cls, t_verd = _node_verdict(t)
    qvt_color     = _color_score(qvt)
    comment       = _magi_comment(qvt)
    ticker_disp   = ticker.replace(".T", "")

    def _node(label, score, verdict, cls_key):
        nc = "magi-node magi-node-approve" if cls_key == "approve" else "magi-node magi-node-deny"
        return (
            '<div class="' + nc + '">' +
            '<div class="magi-node-label">' + label + '</div>' +
            '<div class="magi-node-verdict">' + verdict + '</div>' +
            '<div class="magi-node-score">' + f"{score:.1f}" + 'pt</div>' +
            '</div>'
        )

    # ① ヘッダー + 左右情報パネル（② 銘柄名を company_name 行に追加）
    st.markdown(
        '<div class="magi-container">' +
        '<div class="magi-header-strip">RESULT OF THE DELIBERATION</div>' +
        '<div style="padding:0.5rem;background:#000">' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-bottom:6px">' +

        '<div class="info-panel">' +
        '<div class="info-panel-title">&#9632; STOCK DATA</div>' +
        '<div style="font-size:0.75rem;color:#ffcc88;font-weight:700;margin-bottom:3px;letter-spacing:0.5px">' + company_name + '</div>' +
        '<div class="info-row"><span>' + ticker_disp + '</span><span class="info-val">' + industry + '</span></div>' +
        '<div class="info-row"><span>SECTOR</span><span class="info-val" style="font-size:0.55rem">' + sector + '</span></div>' +
        '<div style="border-top:1px solid var(--text-dark);margin:4px 0"></div>' +
        '<div style="font-size:1rem;color:#ffaa66;font-weight:700;letter-spacing:1px">' + _fmt(close, d) + '</div>' +
        '<div class="info-row"><span>前日比</span>' +
        '<span class="' + chg_cls + '">' + sign + _fmt(change, d) + ' (' + sign + _fmt(change_pct, 2) + '%)</span></div>' +
        '</div>' +

        '<div class="info-panel">' +
        '<div class="info-panel-title">&#9632; TECHNICAL</div>' +
        '<div class="info-row"><span>RSI (14)</span><span class="info-val">' + _fmt(rsi, 1) + '</span></div>' +
        '<div class="info-row"><span>BB判定</span><span class="info-val">' + bb_icon + '</span></div>' +
        '<div style="font-size:0.55rem;color:var(--text-dim)">' + bb_text + '</div>' +
        '<div style="border-top:1px solid var(--text-dark);margin:4px 0"></div>' +
        '<div class="info-row"><span>25MA</span><span class="info-val">' + _fmt(ma25, d) + '</span></div>' +
        '<div class="info-row"><span>50MA</span><span class="info-val">' + _fmt(ma50, d) + '</span></div>' +
        '<div class="info-row"><span>75MA</span><span class="info-val">' + _fmt(ma75, d) + '</span></div>' +
        '<div style="border-top:1px solid var(--text-dark);margin:4px 0"></div>' +
        '<div class="info-row"><span>52W高値</span><span class="info-val">' + _fmt(hi52, d) + '</span></div>' +
        '<div class="info-row"><span>安値</span><span class="info-val">' + _fmt(lo52, d) + '</span></div>' +
        '</div></div>',
        unsafe_allow_html=True
    )

    # ②③④ MAGIボックス全体（BALTHASAR + 中央スコア + CASPER/MELCHIOR）を1つのdivで囲む
    st.markdown(
        '<div style="border:1px solid var(--orange);padding:1rem 0.5rem 0.8rem;position:relative;margin-top:6px">' +

        '<div style="position:absolute;top:-12px;left:50%;transform:translateX(-50%);' +
        'background:#000;border:1px solid var(--orange);padding:0 10px;' +
        'font-family:Orbitron,monospace;font-size:0.75rem;font-weight:700;' +
        'color:var(--orange);letter-spacing:3px;white-space:nowrap">&#9632; MAGI &#9632;</div>' +

        '<div style="display:flex;justify-content:center;margin-bottom:8px">' +
        _node("VALUATION/BALTHASAR-2", v, v_verd, v_cls) +
        '</div>' +

        '<div style="display:flex;justify-content:center;margin:0 0 8px">' +
        '<div class="magi-center-panel">' +
        '<div class="magi-center-name">MAGI</div>' +
        '<div style="font-family:Share Tech Mono,monospace;font-size:1.8rem;font-weight:900;color:' + qvt_color + '">' + f"{qvt:.1f}" + '</div>' +
        '<div class="magi-center-comment">' + comment + '</div>' +
        '</div></div>' +

        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px">' +
        _node("TIMING/CASPER-3", t, t_verd, t_cls) +
        _node("QUALITY/MELCHIOR-1", q, q_verd, q_cls) +
        '</div>' +

        '</div>' +
        '</div>' +
        '</div>',
        unsafe_allow_html=True
    )


# ─── タブ: T ─────────────────────────────────────────────────

def render_t_tab(tech):
    sig_txt  = tech["signal_text"];   sig_icon = tech["signal_icon"]
    sig_str  = tech["signal_strength"]; hi_alert = tech.get("high_price_alert", False)
    t_label  = tech["timing_label"];  style = _signal_style(sig_str, hi_alert)

    st.markdown(f"""
    <div class="signal-banner" style="{style}">
      <div class="signal-icon">{sig_icon}</div>
      <div><div class="signal-text">{sig_txt}</div><div class="signal-sub">{t_label}</div></div>
    </div>
    """, unsafe_allow_html=True)

    if hi_alert:
        st.warning("⚠️ 高値掴みリスク（高値圏 / RSI過熱 / 52W高値付近）")

    price = tech["close"]; ma25 = tech["ma_25"]; ma50 = tech["ma_50"]
    rsi   = tech["rsi"];   slope = tech.get("slope_25", 0)
    low52 = tech["low_52w"]; hi52 = tech["high_52w"]
    pos52 = int((price - low52) / (hi52 - low52) * 100) if hi52 > low52 else 0
    tmode = tech.get("t_mode", "—")

    def ok_ng(cond):
        if cond is None: return '<span class="td-neu">—</span>'
        return '<span class="td-ok">○</span>' if cond else '<span class="td-ng">×</span>'

    def _slope_label(s):
        if s is None: return "—"
        sign = "+" if s >= 0 else ""
        desc = "急上昇中" if s >= 1.5 else "上昇中" if s >= 0.3 else "緩やか上昇" if s >= 0 else "緩やか下落" if s >= -0.3 else "下落中" if s >= -1.5 else "急下落中"
        color = "#4477ff" if s >= 0 else "#ff4444"
        return f'<span style="color:{color};font-weight:700">{sign}{s:.2f}%</span> <span style="font-size:.75rem;color:#996633">({desc})</span>'

    def make_52w_bar(pos):
        bar   = '█' * round(pos / 10) + '░' * (10 - round(pos / 10))
        color = '#ff4444' if pos >= 80 else '#ffaa00' if pos >= 60 else '#4477ff'
        return f'<span style="font-family:monospace;color:{color}">{bar}</span> <span style="font-size:.75rem;color:#996633">({100-pos}%下)</span>'

    rows = [
        ("BB位置",    f'{tech["bb_icon"]} {tech["bb_text"]}', None),
        ("RSI (14)", f'{_fmt(rsi, 1)}',                      rsi < 30 if rsi else None),
        ("価格 vs MA25", "< MA25" if price < ma25 else "≥ MA25", price < ma25),
        ("MA25傾き",  _slope_label(slope),                   None),
        ("52W位置",   make_52w_bar(pos52),                   None),
        ("モード",    "📈 順張り" if tmode == "trend" else "🧮 逆張り", None),
    ]
    table_html = '<table class="cs-table"><thead><tr><th>指標</th><th>値</th><th style="text-align:center">判定</th></tr></thead><tbody>'
    for label, val, cond in rows:
        table_html += f'<tr><td>{label}</td><td>{val}</td><td style="text-align:center">{ok_ng(cond)}</td></tr>'
    st.markdown(table_html + '</tbody></table>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### 📌 裁量買いレンジ（目安）")
    d = 0 if price >= 100 else 2
    if tmode == "trend":
        center = (ma25 + ma50) / 2; upper = center * 1.03
        lower  = max(center * 0.95, tech["bb_minus1"]); mode_lbl = "📈 順張り（上昇トレンド押し目狙い）"
    else:
        center = (ma25 + tech["bb_minus1"]) / 2; upper = center * 1.08
        lower  = center * 0.97; mode_lbl = "🧮 逆張り（調整局面の押し目狙い）"

    st.caption(f"モード: {mode_lbl}")
    st.markdown(f"""
    <div class="range-grid">
      <div class="range-item"><div class="range-lbl">下値</div><div class="range-val">{_fmt(lower,d)}</div></div>
      <div class="range-item"><div class="range-lbl">中心</div><div class="range-val">{_fmt(center,d)}</div></div>
      <div class="range-item"><div class="range-lbl">上値</div><div class="range-val">{_fmt(upper,d)}</div></div>
    </div>
    """, unsafe_allow_html=True)
    st.caption("※ 裁量買いレンジは環境チェック・トレンド・QVTスコアを組み合わせた参考値です。")


# ─── タブ: Q ─────────────────────────────────────────────────

def render_q_tab(tech):
    q_score = float(tech.get("q_score", 0)); q1 = float(tech.get("q1", 0)); q3 = float(tech.get("q3", 0))
    q_warnings = tech.get("q_warnings", [])
    roe = tech.get("roe"); roa = tech.get("roa"); er = tech.get("equity_ratio")
    opm = tech.get("operating_margin"); de = tech.get("de_ratio"); ic = tech.get("interest_coverage")
    er_thr = tech.get("er_threshold", 10.0); ic_thr = tech.get("ic_threshold", 1.5)
    thr_note = tech.get("threshold_note", "標準基準")

    st.metric("QUALITY SCORE", f"{q_score:.1f} / 100")
    col1, col2 = st.columns(2)
    col1.metric("Q1 収益性", f"{q1:.1f}"); col2.metric("Q3 財務健全性", f"{q3:.1f}")
    if thr_note and thr_note != "標準基準":
        st.caption(f"📋 {thr_note}｜自己資本比率閾値 {er_thr:.0f}% / インタレストカバレッジ閾値 {ic_thr:.1f}x")
    for w in q_warnings:
        st.warning(w)

    st.markdown("---")
    st.markdown("##### Q1 収益性指標")

    def _q1_eval(key, val):
        if val is None: return "—"
        if key == "roe": return "✓ 高収益" if val >= 15 else ("△ 低収益" if val < 5 else "")
        if key == "roa": return "✓ 高効率" if val >= 5  else ""
        if key == "opm": return "✓ 高利益率" if val >= 10 else ("⚠️ 赤字" if val < 0 else "")
        return ""

    st.markdown(_build_table(["指標", "値", "評価"], [
        ("ROE", _fmt_pct(roe), _q1_eval("roe", roe)),
        ("ROA", _fmt_pct(roa), _q1_eval("roa", roa)),
        ("営業利益率", _fmt_pct(opm), _q1_eval("opm", opm)),
    ]), unsafe_allow_html=True)

    st.markdown("##### Q3 財務健全性指標")

    def _q3_eval(key, val):
        if val is None: return "—"
        if key == "er": return "✓ 健全" if val >= 40 else (f"⚠️ 高レバ" if val < er_thr else "")
        if key == "de": return "✓ 低負債" if val < 0.5 else ("⚠️ 過剰負債" if val > 2.0 else "")
        if key == "ic": return "✓ 余裕あり" if val >= 5 else ("⚠️ 危険圏" if val < ic_thr else "")
        return ""

    st.markdown(_build_table(["指標", "値", "評価"], [
        ("自己資本比率",          _fmt_pct(er),               _q3_eval("er", er)),
        ("D/E レシオ",            f"{de:.2f}x" if de else "—", _q3_eval("de", de)),
        ("インタレストカバレッジ", f"{ic:.1f}x" if ic else "—", _q3_eval("ic", ic)),
    ]), unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### セクター補正（任意）")
    col1, col2 = st.columns(2)
    with col1: sect_roe = st.number_input("セクター平均ROE(%)", 0.0, 40.0, 10.0, 0.1)
    with col2: sect_roa = st.number_input("セクター平均ROA(%)", 0.0, 20.0, 4.0, 0.1)
    if st.button("補正する", use_container_width=True):
        if roe is None or roa is None:
            st.error("ROE / ROA データ不足のため補正できません。")
        else:
            result   = apply_q_correction(tech=tech, sector_roe=sect_roe, sector_roa=sect_roa)
            q_corr   = result.get("q_corrected"); qvt_corr = result.get("qvt_corrected")
            st.session_state["q_correction_result"] = result
            c1, c2 = st.columns(2)
            c1.metric("Q（補正前）", f"{q_score:.1f}")
            c2.metric("Q（補正後）", f"{q_corr:.1f}", delta=f"{q_corr - q_score:+.1f}")
            st.caption(f"補正後 QVT: {qvt_corr:.1f}")


# ─── タブ: V ─────────────────────────────────────────────────

def render_v_tab(tech):
    v_score = float(tech.get("v_score", 0)); v1 = float(tech.get("v1", 0)); v2 = float(tech.get("v2", 0))
    v3 = float(tech.get("v3", 0)); v4 = tech.get("v4"); has_sector = tech.get("has_sector", False)
    per = tech.get("per"); per_fwd = tech.get("per_fwd"); pbr = tech.get("pbr")
    dy = tech.get("dividend_yield"); ev_ebitda = tech.get("ev_ebitda")
    sector_name = tech.get("sector")
    ft = tech.get("financial_type", {}); sector_rel = tech.get("sector_rel_scores", {})

    st.metric("VALUATION SCORE", f"{v_score:.1f} / 100")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("V1 伝統的割安度", f"{v1:.0f}")
    col2.metric("V2 企業価値割安度", f"{v2:.0f}")
    col3.metric("V3 株主還元度", f"{v3:.0f}")
    col4.metric("V4 セクター内診断", f"{v4:.0f}" if (has_sector and v4 is not None) else "—")
    ft_code = ft.get("code", "")
    ft_ja   = ft.get("ja",   "")
    v4_note = f"財務タイプ: {ft_code}（{ft_ja}）" if ft_code and ft_code != "UNK" else "財務タイプ: DB未収録"
    st.caption(f"V1: PER・PBR ／ V2: EV/EBITDA ／ V3: 配当利回り ／ V4: {v4_note}")


    if ft.get("code"):
        code = ft.get("code", "—"); ja = ft.get("ja", "—"); desc = ft.get("description", "")
        st.markdown(f"""
        <div style="background:#000;border:1px solid var(--orange);padding:0.7rem 1rem;margin:0.5rem 0">
          <div style="font-size:0.55rem;letter-spacing:2px;color:var(--text-dim);font-family:'Orbitron',monospace">財務タイプ</div>
          <div style="font-size:0.95rem;font-weight:700;color:var(--orange);margin-top:0.2rem">{ja} <span style="font-size:0.65rem;color:var(--text-dark)">({code})</span></div>
          <div style="font-size:0.75rem;color:var(--text-dim);margin-top:0.2rem">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    if has_sector:
        st.markdown("##### セクター相対評価（V4）")
        def _rel(key):
            s = sector_rel.get(key)
            return f"{s:.0f}pt" if s is not None else "—"
        st.markdown(_build_table(["指標", "実測値(vs中央値)", "スコア"], [
            ("PER（相対）",       sector_rel.get("per_vs_median", "—"),       _rel("per_rel_score")),
            ("PBR（相対）",       sector_rel.get("pbr_vs_median", "—"),       _rel("pbr_rel_score")),
            ("EV/EBITDA（相対）", sector_rel.get("ev_ebitda_vs_median", "—"), _rel("ev_ebitda_rel_score")),
        ]), unsafe_allow_html=True)
        st.caption("スコア目安：100pt＝かなり割安 / 50pt＝中央値水準 / 0pt＝かなり割高")

        sv = sector_rel.get("sector_v_score")
        per_rel = sector_rel.get("per_rel_score")
        pbr_rel = sector_rel.get("pbr_rel_score")
        ev_rel  = sector_rel.get("ev_ebitda_rel_score")
        ft_ja   = ft.get("ja", "")
        if sv is not None:
            if sv >= 80:   diag =  f"{sector_name}セクター内でかなり割安。買いやすい水準。"
            elif sv >= 65: diag =  f"{sector_name}セクター内でやや割安。中央値を下回っており妥当圏。"
            elif sv >= 50: diag =  f"{sector_name}セクター内で中央値水準。特段割安でも割高でもない。"
            elif sv >= 35: diag =  f"{sector_name}セクター内でやや割高。中央値を上回っており注意が必要。"
            else:          diag =  f"{sector_name}セクター内でかなり割高。割高圏にある。"
            notes = []
            if per_rel is not None and per_rel >= 75: notes.append("PERは割安")
            if pbr_rel is not None and pbr_rel >= 75: notes.append("PBRは割安")
            if ev_rel  is not None and ev_rel  >= 75: notes.append("EV/EBITDAは割安")
            if per_rel is not None and per_rel <= 25: notes.append("PERは割高圏")
            if pbr_rel is not None and pbr_rel <= 25: notes.append("PBRは割高圏")
            if notes: diag += f"（{' / '.join(notes)}）"
            st.info(f"📊 セクター診断　{diag}")

    st.markdown("##### 絶対評価（V1〜V3）")
    def eval_per(x):
        return "—" if x is None else ("✓ 割安" if x < 12 else ("△ 割高" if x > 30 else ""))
    def eval_pbr(x):
        return "—" if x is None else ("✓ 資産割安" if x < 1 else ("△ 割高" if x > 3 else ""))
    def eval_dy(x):
        return "—" if x is None else ("✓ 高配当" if x >= 3 else "")
    def eval_ev(x):
        return "—" if x is None else ("✓ 割安" if x < 8 else ("△ 割高" if x > 20 else ""))

    rows = [
        ("PER（実績）",  _fmt_x(per),       eval_per(per)),
        ("予想PER",      _fmt_x(per_fwd),   eval_per(per_fwd)),
        ("PBR",          _fmt_x(pbr),       eval_pbr(pbr)),
        ("EV/EBITDA",    _fmt_x(ev_ebitda), eval_ev(ev_ebitda)),
        ("配当利回り",   _fmt_pct(dy),      eval_dy(dy)),
    ]
    table_html = '<table class="cs-table"><thead><tr><th>指標</th><th style="text-align:right">値</th><th style="text-align:right">評価</th></tr></thead><tbody>'
    for label, val, ev in rows:
        badge = f'<span class="ev-badge">{ev}</span>' if ev and ev not in ("—", "") else ""
        table_html += f'<tr><td>{label}</td><td class="td-right">{val}</td><td style="text-align:right">{badge}</td></tr>'
    st.markdown(table_html + '</tbody></table>', unsafe_allow_html=True)

    st.markdown("---")
    with st.expander("財務タイプ辞典"):
        all_types = get_all_types_for_display()
        if all_types:
            for t in all_types:
                if t["sample_count"] == 0: continue
                is_this = ft.get("code") and ft.get("code") == t["code"]
                highlight = "🔍 **この銘柄の分類**  " if is_this else ""
                per_m = f"{t['per_median']:.1f}x"    if t["per_median"]             else "—"
                pbr_m = f"{t['pbr_median']:.2f}x"    if t["pbr_median"]             else "—"
                roe_m = f"{t['roe_median']*100:.1f}%" if t["roe_median"] is not None else "—"
                opm_m = f"{t['operating_margin_median']*100:.1f}%" if t["operating_margin_median"] is not None else "—"
                st.markdown(f"**{highlight}{t['ja']}** `{t['code']}`  \n{t['description']}  \n📊 PER {per_m} / PBR {pbr_m} / ROE {roe_m} / 営業利益率 {opm_m} (n={t['sample_count']})")
        else:
            st.info("財務タイプDBが読み込まれていません。")


# ─── タブ: QVT ────────────────────────────────────────────────

def render_qvt_tab(tech):
    q   = float(tech["q_score"]); v = float(tech["v_score"])
    t   = float(tech["t_score"]); qvt = float(tech["qvt_score"])
    corr = st.session_state.get("q_correction_result")
    q_show, qvt_show = (float(corr.get("q_corrected", q)), float(corr.get("qvt_corrected", qvt))) if corr else (q, qvt)

    col1, col2, col3 = st.columns(3)
    if corr: col1.metric("Q（補正後）", f"{q_show:.1f}", delta=f"{q_show - q:+.1f}")
    else:    col1.metric("- QUALITY -", f"{q:.1f}")
    col2.metric("-  VALUATION -", f"{v:.1f}"); col3.metric("- TIMING -", f"{t:.1f}")

    st.markdown("---")
    color = _color_score(qvt_show)
    msg   = _magi_comment(qvt_show)
    star  = "⭐⭐⭐" if qvt_show >= 70 else "⭐⭐" if qvt_show >= 60 else "⭐" if qvt_show >= 50 else ""

    st.markdown(f"""
    <div class="score-card" style="padding:1.5rem;border:2px solid var(--orange)">
      <div class="score-label">QVT -total score-</div>
      <div class="score-value" style="color:{color};font-size:3.5rem">{qvt_show:.1f}</div>
      <div class="score-max">/ 100</div>
      <div style="font-size:1.2rem;margin-top:.5rem">{star}</div>
      <div style="font-size:.75rem;color:var(--text-dim);margin-top:.5rem;font-family:'Share Tech Mono'">{msg}</div>
    </div>
    """, unsafe_allow_html=True)

    if corr: st.caption("※ コメントは補正後QVTスコアをもとに判定。")
    with st.expander("QVT フレームワーク"):
        st.markdown("""
**Q（Quality）** — ビジネスの質。ROE・ROA・営業利益率（Q1）＋自己資本比率・D/E・インタレストカバレッジ（Q3）。  
**V（Valuation）** — 割安度。PER・PBR・EV/EBITDA・配当利回り＋セクター相対評価（日本株）。  
**T（Timing）** — テクニカル的な買いタイミング。RSI・BB・MA・52Wレンジから算出。

| QVT | 目安 |
|---|---|
| 70以上 | 主力候補 |
| 60〜69 | 慎重に押し目 |
| 50〜59 | 比較検討 |
| 50未満 | 見送りも選択肢 |

**セクター別 Q 目安**

| セクター例 | ROE目安 | ROA目安 | 営業利益率目安 |
|---|---|---|---|
| 生活必需品・インフラ | 8〜12% | 3〜6% | 5〜10% |
| テック・成長株 | 10〜20%+ | 5〜10% | 15〜30% |
| 景気敏感（自動車等） | 8〜12% | 3〜6% | 5〜10% |
| 金融 | 8〜12% | 0.5〜2% | — |
        """)


# ─── データ取得 & 指標計算（共通処理） ──────────────────────

def _fetch_and_compute(ticker):
    with st.spinner(f"■ {ticker} データ取得中…"):
        try:
            base = get_price_and_meta(ticker)
        except ValueError as e:
            st.error(str(e)); return None, None

    with st.spinner("■ 財務タイプ分類中…"):
        db = load_pattern_db()
        financial_type = classify_ticker(
            ticker, db,
            roe=base.get("roe"),
            roa=base.get("roa"),
            equity_ratio=base.get("equity_ratio"),
            interest_coverage=base.get("interest_coverage"),
            operating_margin=base.get("operating_margin"),
        )
        _close = base.get("close", 0); _eps = base.get("eps"); _bps = base.get("bps")
        _per_tmp = (_close / _eps) if (_eps and _eps != 0 and _close) else None
        _pbr_tmp = (_close / _bps) if (_bps and _bps != 0 and _close) else None
        # V4: sector_db ベースで計算（financial_type は表示ラベルに限定）
        _sector_name = base.get("sector", "")
        sector_rel = calc_sector_relative_scores_from_db(
            sector=_sector_name, per=_per_tmp, pbr=_pbr_tmp, ev_ebitda=base.get("ev_ebitda"))
        sector_v_score = sector_rel.get("sector_v_score") if (
            _sector_name and sector_rel.get("sector_matched", False)
        ) else None

    with st.spinner("■ 指標計算中…"):
        try:
            tech = compute_indicators(
                base["df"], base["close_col"], base["high_52w"], base["low_52w"],
                eps=base.get("eps"), bps=base.get("bps"),
                eps_fwd=base.get("eps_fwd"), per_fwd=base.get("per_fwd"),
                roe=base.get("roe"), roa=base.get("roa"),
                equity_ratio=base.get("equity_ratio"), dividend_yield=base.get("dividend_yield"),
                operating_margin=base.get("operating_margin"), de_ratio=base.get("de_ratio"),
                interest_coverage=base.get("interest_coverage"), ev_ebitda=base.get("ev_ebitda"),
                sector_v_score=sector_v_score, sector_rel_scores=sector_rel,
                financial_type=financial_type,
                industry=base.get("industry", ""), sector=base.get("sector", ""),
                is_us=not ticker.upper().endswith(".T"),
            )
        except ValueError as e:
            st.error(str(e)); return base, None

    # compute_indicators 後に ev_ebitda が確定するので sector_rel を再計算して上書き
    _per_final = tech.get("per")
    _pbr_final = tech.get("pbr")
    _ev_final  = tech.get("ev_ebitda")
    if _per_final or _pbr_final or _ev_final:
        # compute_indicators 後に確定した値で sector_rel を再計算（sector_db ベース）
        sector_rel_final = calc_sector_relative_scores_from_db(
            sector=_sector_name, per=_per_final, pbr=_pbr_final, ev_ebitda=_ev_final)
        tech["sector_rel_scores"] = sector_rel_final
        # sector_matched = True のときのみ V4 を有効化
        if sector_rel_final.get("sector_matched", False):
            tech["sector_v_score"] = sector_rel_final.get("sector_v_score")

    # is_us を tech に格納しておく（各タブから参照可能に）
    tech["is_us"] = not ticker.upper().endswith(".T")
    return base, tech


# ─── エントリーポイント ───────────────────────────────────────

def run():
    """app/main.py から呼ばれるエントリーポイント。"""
    _setup_style()

    st.markdown("""
    <div class="magi-banner">DIRECT BUS CONNECTION MAGI-47 &nbsp;■&nbsp; ACCESS AUTHORIZED — SUPERUSER</div>
    <div class="magi-banner-title">▶ MOTION : BUY THE DIP ◀</div>
    <div class="magi-banner">MAGI SYSTEM v3 — 日本株 / 米国株対応</div>
    """, unsafe_allow_html=True)

    col_input, col_btn = st.columns([4, 1])
    with col_input:
        user_input = st.text_input("ticker", placeholder="ティッカー入力：7203 / AAPL", label_visibility="collapsed")
    with col_btn:
        search = st.button("ANALYZE", use_container_width=True)

    try:
        av_key = st.secrets.get("ALPHA_VANTAGE_API_KEY", None)
    except Exception:
        av_key = None
    if not av_key:
        st.caption("ℹ️ 米国株ファンダメンタルはALPHA_VANTAGE_API_KEYをSecretsに設定してください。")

    if not search and not user_input:
        st.markdown("""
        <div class="magi-idle">
          <div class="magi-idle-text">QUALITY · VALUATION · TIMING</div>
          <div class="magi-idle-sub">AWAITING INPUT — ENTER TICKER TO BEGIN ANALYSIS</div>
        </div>
        """, unsafe_allow_html=True)
        return

    ticker = convert_ticker(user_input)
    if not ticker:
        st.info("ティッカーを入力すると結果が表示されます。")
        return

    base, tech = _fetch_and_compute(ticker)
    if base is None or tech is None:
        return

    q   = float(tech["q_score"]); v = float(tech["v_score"])
    t   = float(tech["t_score"]); qvt = float(tech["qvt_score"])

    render_magi_panel(q, v, t, qvt, ticker, base, tech)
    st.markdown("---")

    tab_t, tab_q, tab_v, tab_qvt = st.tabs([
        "⏰ TIMING / CASPER",
        "🏢 QUALITY / MELCHIOR",
        "💰 VALUATION / BALTHASAR",
        "🧮 QVT / MAGI",
    ])
    with tab_t:   render_t_tab(tech)
    with tab_q:   render_q_tab(tech)
    with tab_v:   render_v_tab(tech)
    with tab_qvt: render_qvt_tab(tech)

    if base.get("dividend_yield"):
        st.caption(f"予想配当利回り: {base['dividend_yield']:.2f}%")
