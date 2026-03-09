"""
main.py — iPhone最適化 Streamlit UI  (v3)
"""
import streamlit as st
from modules.data_fetch import convert_ticker, get_price_and_meta
from modules.indicators import compute_indicators
from modules.q_correction import apply_q_correction
from modules.pattern_db import (          # ★v3
    load_pattern_db,
    classify_ticker,
    calc_sector_relative_scores,
    get_all_types_for_display,
)


# ─── ページ設定 ─────────────────────────────────────────────

def setup_page():
    st.set_page_config(
        page_title="checkSIGNAL",
        page_icon="📡",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500;600&family=Outfit:wght@600;700;800&display=swap');

    :root {
        --bg:       #0f1117;
        --surface:  #1a1d27;
        --card:     #22263a;
        --border:   #2e3452;
        --text:     #e8eaf0;
        --text-2:   #9da3b8;
        --text-3:   #5c6280;
        --accent:   #4f8ef7;
        --green:    #3ecf72;
        --red:      #f05c6e;
        --yellow:   #f5c542;
        --orange:   #f28c38;
    }

    html, body, [class*="css"] {
        font-family: 'Noto Sans JP', sans-serif;
        background-color: var(--bg) !important;
        color: var(--text) !important;
    }
    .stApp, .stApp > div, section.main, .block-container {
        background-color: var(--bg) !important;
    }
    .main > div { padding-top: 1rem; padding-bottom: 3rem; }
    section[data-testid="stSidebar"] { display: none; }

    .cs-title {
        font-family: 'Outfit', sans-serif;
        font-size: 1.6rem; font-weight: 800;
        color: var(--text); letter-spacing: -0.5px;
        margin-bottom: 0;
    }
    .cs-title span { color: var(--accent); }
    .cs-sub {
        font-size: 0.65rem; letter-spacing: 2px;
        text-transform: uppercase; color: var(--text-3);
        margin-bottom: 1.2rem;
    }

    .score-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .score-label {
        font-size: 0.68rem; letter-spacing: 1.5px;
        text-transform: uppercase; color: var(--text-2);
        font-weight: 700;
        margin-bottom: 0.4rem;
    }
    .score-value {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 2.2rem; font-weight: 700;
        line-height: 1;
    }
    .score-max { font-size: 0.7rem; color: var(--text-3); font-weight: 600; margin-top: 0.2rem; }

    .signal-banner {
        border-radius: 12px; padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
        display: flex; align-items: center; gap: 0.8rem;
    }
    .signal-icon { font-size: 1.8rem; }
    .signal-text {
        font-family: 'Outfit', sans-serif;
        font-size: 1.05rem; font-weight: 700; color: var(--text);
    }
    .signal-sub { font-size: 0.75rem; color: var(--text-2); font-weight: 600; margin-top: 0.1rem; }

    .price-header {
        background: var(--surface); border: 1px solid var(--border);
        border-radius: 12px; padding: 1rem 1.2rem;
        margin-bottom: 1rem;
    }
    .price-ticker {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1rem; font-weight: 600; color: var(--text-2);
        letter-spacing: 0.5px;
    }
    .price-company {
        font-family: 'Noto Sans JP', sans-serif;
        font-size: 1.05rem; font-weight: 700; color: var(--text);
        margin-top: 0.2rem; line-height: 1.4;
    }
    .price-main {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 2.4rem; font-weight: 700; margin-top: 0.6rem;
        letter-spacing: -0.5px;
    }
    .price-up   { color: var(--red); }
    .price-down { color: var(--green); }
    .price-flat { color: var(--text); }
    .price-chg  { font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem; font-weight: 600; margin-top: 0.2rem; }

    .metric-grid {
        display: grid; grid-template-columns: 1fr 1fr;
        gap: 0.5rem; margin-bottom: 0.8rem;
    }
    .metric-item {
        background: var(--surface); border: 1px solid var(--border);
        border-radius: 10px; padding: 0.8rem 0.9rem;
    }
    .metric-lbl {
        font-size: 0.65rem; letter-spacing: 1.2px;
        text-transform: uppercase; color: var(--text-2);
        font-weight: 700; margin-bottom: 0.3rem;
    }
    .metric-val {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.3rem; font-weight: 700; color: var(--text);
    }
    .metric-sub {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.8rem; font-weight: 600; color: var(--text-2); margin-top: 0.15rem;
    }

    .range-grid {
        display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.5rem;
    }
    .range-item {
        background: var(--card); border: 1px solid var(--border);
        border-radius: 8px; padding: 0.75rem;
        text-align: center;
    }
    .range-lbl {
        font-size: 0.6rem; letter-spacing: 1px;
        text-transform: uppercase; color: var(--text-2);
        font-weight: 700; margin-bottom: 0.25rem;
    }
    .range-val {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.05rem; font-weight: 700; color: var(--text);
    }

    .cs-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.87rem;
        table-layout: fixed;
    }
    .cs-table th:nth-child(1), .cs-table td:nth-child(1) { width: 28%; }
    .cs-table th:nth-child(2), .cs-table td:nth-child(2) { width: 54%; }
    .cs-table th:nth-child(3), .cs-table td:nth-child(3) { width: 18%; }
    .cs-table thead th {
        padding: 6px 10px 6px 12px;
        font-size: 0.58rem; letter-spacing: 1.8px;
        text-transform: uppercase;
        color: var(--text-3); font-weight: 700;
        background: transparent;
        border-bottom: 1px solid var(--border);
        white-space: nowrap;
    }
    .cs-table tbody tr:nth-child(odd)  { background: var(--surface); }
    .cs-table tbody tr:nth-child(even) { background: var(--card); }
    .cs-table tbody td {
        padding: 8px 10px 8px 12px;
        overflow: hidden; word-break: break-word;
        border: none;
    }
    .cs-table tbody td:nth-child(1) {
        color: var(--text-2);
        font-size: 0.78rem; font-weight: 600;
        letter-spacing: 0.1px;
        border-left: 3px solid transparent;
    }
    .cs-table tbody td:nth-child(2) {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.9rem; font-weight: 600;
        color: var(--text);
    }
    .cs-table tbody td:nth-child(3) {
        text-align: center;
        vertical-align: middle;
    }
    .td-ok {
        display: inline-flex; align-items: center; justify-content: center;
        width: 24px; height: 24px;
        background: rgba(62,207,114,.20);
        color: var(--green);
        font-weight: 900; font-size: 0.8rem;
        border-radius: 50%;
        border: 1.5px solid rgba(62,207,114,.50);
    }
    .td-ng {
        display: inline-flex; align-items: center; justify-content: center;
        width: 24px; height: 24px;
        background: rgba(240,92,110,.20);
        color: var(--red);
        font-weight: 900; font-size: 0.8rem;
        border-radius: 50%;
        border: 1.5px solid rgba(240,92,110,.50);
    }
    .td-neu { color: var(--text-3); font-size: 1rem; }
    .ev-badge {
        display: inline-block;
        background: rgba(62,207,114,.15);
        color: var(--green);
        font-size: 0.72rem; font-weight: 700;
        border-radius: 4px; padding: 2px 6px;
        white-space: nowrap;
    }
    .td-right {
        text-align: right; color: var(--text);
        font-family: 'IBM Plex Mono', monospace; font-weight: 600;
    }

    div[data-testid="stTabs"] button {
        font-size: 0.82rem !important;
        font-weight: 700 !important;
        padding: 0.5rem 0.9rem !important;
        font-family: 'Noto Sans JP', sans-serif !important;
        color: var(--text-2) !important;
    }
    div[data-testid="metric-container"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        padding: 0.8rem !important;
    }
    div[data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 1.6rem !important; font-weight: 700 !important;
        color: var(--text) !important;
    }
    div[data-testid="metric-container"] label {
        font-size: 0.7rem !important; font-weight: 700 !important;
        color: var(--text-2) !important; letter-spacing: 0.05em !important;
    }
    div[data-testid="stAlert"] {
        background-color: var(--surface) !important;
        color: var(--text) !important;
    }
    div[data-testid="stButton"] > button {
        height: 3rem !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
        border-radius: 10px !important;
        width: 100%;
        font-family: 'Noto Sans JP', sans-serif !important;
    }
    div[data-testid="stTextInput"] input {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        height: 3rem !important;
        border-radius: 10px !important;
        color: var(--text) !important;
    }
    div[data-testid="stNumberInput"] input {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        height: 2.8rem !important;
    }
    hr { border-color: var(--border) !important; }
    div[data-testid="stExpander"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
    }
    </style>
    """, unsafe_allow_html=True)


# ─── ヘルパー ────────────────────────────────────────────────

def _fmt(x, d=2):
    return "—" if x is None else f"{float(x):.{d}f}"

def _fmt_pct(x):
    return "—" if x is None else f"{float(x):.1f}%"

def _fmt_x(x):
    return "—" if x is None else f"{float(x):.2f}倍"

def _color_score(s):
    if s >= 70: return "#3ecf72"
    if s >= 55: return "#4f8ef7"
    if s >= 40: return "#f5c542"
    return "#f05c6e"

def _price_class(change):
    if change > 0: return "price-up"
    if change < 0: return "price-down"
    return "price-flat"

def _signal_style(strength, hi_alert):
    if strength >= 3:
        return "background:rgba(62,207,114,.12);border:1px solid #3ecf72;"
    if strength == 2:
        return "background:rgba(245,197,66,.10);border:1px solid #f5c542;"
    if hi_alert:
        return "background:rgba(240,92,110,.12);border:1px solid #f05c6e;"
    return "background:rgba(79,142,247,.10);border:1px solid #4f8ef7;"

def _build_table(headers: list, rows: list) -> str:
    """汎用 cs-table HTML ビルダー。"""
    ths = "".join(f"<th>{h}</th>" for h in headers)
    html = f'<table class="cs-table"><thead><tr>{ths}</tr></thead><tbody>'
    for row in rows:
        cells = "".join(f"<td>{c}</td>" for c in row)
        html += f"<tr>{cells}</tr>"
    html += "</tbody></table>"
    return html


# ─── UI パーツ ───────────────────────────────────────────────

def render_price_header(ticker, company_name, close, prev_close, industry="", sector=""):
    change = close - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0
    d = 0 if close >= 100 else 2
    cls = _price_class(change)
    sign = "+" if change >= 0 else ""
    chg_color = "#f05c6e" if change >= 0 else "#3ecf72"

    # ③ TICKER | INDUSTRY | SECTOR バッジを並べて表示
    def _badge(text, bg, border, fg):
        return (
            f'<span style="display:inline-block;background:{bg};'
            f'border:1px solid {border};border-radius:4px;'
            f'font-size:0.72rem;padding:1px 8px;margin-left:6px;'
            f'color:{fg};vertical-align:middle;">{text}</span>'
        )
    badges = ""
    if industry:
        # industry: 青系
        badges += _badge(industry, "rgba(79,142,247,.15)", "rgba(79,142,247,.4)", "#8ab4f8")
    if sector and sector != industry:
        # sector: 緑系（industryと同じ場合は非表示）
        badges += _badge(sector, "rgba(100,180,100,.12)", "rgba(100,180,100,.35)", "#7ecf7e")

    st.markdown(f"""
    <div class="price-header">
      <div class="price-company">{company_name}</div>
      <div class="price-ticker">{ticker}{badges}</div>
      <div class="price-main {cls}">{_fmt(close, d)}</div>
      <div class="price-chg" style="color:{chg_color}">
        前日比 {sign}{_fmt(change, d)} ({sign}{_fmt(change_pct, 2)}%)
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_metrics_row(tech):
    d = 0 if tech["close"] >= 100 else 2
    st.markdown(f"""
    <div class="metric-grid">
      <div class="metric-item">
        <div class="metric-lbl">RSI (14)</div>
        <div class="metric-val">{_fmt(tech["rsi"], 1)}</div>
      </div>
      <div class="metric-item">
        <div class="metric-lbl">BB 判定</div>
        <div class="metric-val">{tech["bb_icon"]}</div>
        <div class="metric-sub">{tech["bb_text"]}</div>
      </div>
      <div class="metric-item">
        <div class="metric-lbl">25MA</div>
        <div class="metric-val">{_fmt(tech["ma_25"], d)}</div>
        <div class="metric-sub">{tech["arrow_25"]}</div>
      </div>
      <div class="metric-item">
        <div class="metric-lbl">50MA</div>
        <div class="metric-val">{_fmt(tech["ma_50"], d)}</div>
        <div class="metric-sub">{tech["arrow_50"]}</div>
      </div>
      <div class="metric-item">
        <div class="metric-lbl">75MA</div>
        <div class="metric-val">{_fmt(tech["ma_75"], d)}</div>
        <div class="metric-sub">{tech["arrow_75"]}</div>
      </div>
      <div class="metric-item">
        <div class="metric-lbl">52W 高値</div>
        <div class="metric-val">{_fmt(tech["high_52w"], d)}</div>
        <div class="metric-sub">安値 {_fmt(tech["low_52w"], d)}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_qvt_cards(q, v, t, qvt):
    def card(label, score, color):
        return f"""
        <div class="score-card">
          <div class="score-label">{label}</div>
          <div class="score-value" style="color:{color}">{score:.1f}</div>
          <div class="score-max">/ 100</div>
        </div>"""

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(card("Q — 質", q, "#16a34a"), unsafe_allow_html=True)
    with col2:
        st.markdown(card("V — 値札", v, "#2563eb"), unsafe_allow_html=True)
    with col3:
        st.markdown(card("T — 時機", t, "#d97706"), unsafe_allow_html=True)
    with col4:
        st.markdown(card("QVT", qvt, _color_score(qvt)), unsafe_allow_html=True)


# ─── タブ: T ─────────────────────────────────────────────────

def render_t_tab(tech):
    sig_txt  = tech["signal_text"]
    sig_icon = tech["signal_icon"]
    sig_str  = tech["signal_strength"]
    hi_alert = tech.get("high_price_alert", False)
    t_label  = tech["timing_label"]
    style    = _signal_style(sig_str, hi_alert)

    st.markdown(f"""
    <div class="signal-banner" style="{style}">
      <div class="signal-icon">{sig_icon}</div>
      <div>
        <div class="signal-text">{sig_txt}</div>
        <div class="signal-sub">{t_label}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if hi_alert:
        st.warning("⚠️ 高値掴みリスク（高値圏 / RSI過熱 / 52W高値付近）")

    price = tech["close"]
    ma25  = tech["ma_25"]
    ma50  = tech["ma_50"]
    ma75  = tech["ma_75"]
    rsi   = tech["rsi"]
    slope = tech.get("slope_25", 0)
    low52 = tech["low_52w"]
    hi52  = tech["high_52w"]
    pos52 = int((price - low52) / (hi52 - low52) * 100) if hi52 > low52 else 0
    tmode = tech.get("t_mode", "—")

    def ok_ng(cond):
        if cond is None: return '<span class="td-neu">—</span>'
        return '<span class="td-ok">○</span>' if cond else '<span class="td-ng">×</span>'

    def _slope_label(s) -> str:
        if s is None: return "—"
        sign = "+" if s >= 0 else ""
        if s >= 1.5:    desc = "急上昇中"
        elif s >= 0.3:  desc = "上昇中"
        elif s >= 0:    desc = "緩やかに上昇中"
        elif s >= -0.3: desc = "緩やかに下落中"
        elif s >= -1.5: desc = "下落中"
        else:           desc = "急下落中"
        color = "var(--green)" if s >= 0 else "var(--red)"
        mono = 'IBM Plex Mono'
        return (
            f'<span style="font-family:{mono},monospace;color:{color};font-weight:700">'
            f'{sign}{s:.2f}%</span>'
            f'<span style="font-size:.8rem;color:var(--text-2);margin-left:6px">({desc})</span>'
        )

    def make_52w_bar(pos: int) -> str:
        filled = round(pos / 10)
        empty  = 10 - filled
        bar    = '█' * filled + '░' * empty
        from_hi = 100 - pos
        color = '#f05c6e' if pos >= 80 else '#f5c542' if pos >= 60 else '#3ecf72'
        return (
            f'<span style="font-family:monospace;letter-spacing:1px;color:{color}">{bar}</span>'
            f'<span style="font-size:.8rem;color:var(--text-2);margin-left:6px">（高値まで {from_hi}%）</span>'
        )

    rows = [
        ("BB 位置",      f'{tech["bb_icon"]} {tech["bb_text"]}', None),
        ("RSI (14)",     f'{_fmt(rsi, 1)}',                      rsi < 30 if rsi else None),
        ("25MA vs 価格", "価格 < MA25" if price < ma25 else "価格 ≥ MA25", price < ma25),
        ("MA25 傾き",    _slope_label(slope),                    None),
        ("52W 位置",     make_52w_bar(pos52),                    None),
        ("モード",       "📈 順張り" if tmode == "trend" else "🧮 逆張り", None),
    ]

    table_html = '''<table class="cs-table">
      <thead><tr>
        <th>指標</th><th>値</th><th style="text-align:center">判定</th>
      </tr></thead>
      <tbody>'''
    for label, val, cond in rows:
        table_html += f'<tr><td>{label}</td><td>{val}</td><td>{ok_ng(cond)}</td></tr>'
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### 📌 裁量買いレンジ（目安）")

    d = 0 if price >= 100 else 2
    if tmode == "trend":
        center = (ma25 + ma50) / 2
        upper  = center * 1.03
        lower  = max(center * 0.95, tech["bb_minus1"])
        mode_lbl = "📈 順張り（上昇トレンド押し目狙い）"
    else:
        center = (ma25 + tech["bb_minus1"]) / 2
        upper  = center * 1.08
        lower  = center * 0.97
        mode_lbl = "🧮 逆張り（調整局面の押し目狙い）"

    st.caption(f"モード: {mode_lbl}")
    st.markdown(f"""
    <div class="range-grid">
      <div class="range-item">
        <div class="range-lbl">下値（目安）</div>
        <div class="range-val">{_fmt(lower, d)}</div>
      </div>
      <div class="range-item">
        <div class="range-lbl">中心（目安）</div>
        <div class="range-val">{_fmt(center, d)}</div>
      </div>
      <div class="range-item">
        <div class="range-lbl">上値（目安）</div>
        <div class="range-val">{_fmt(upper, d)}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.caption("※ 裁量買いレンジは環境チェック・トレンド・QVTスコアを組み合わせた参考値です。")


# ─── タブ: Q ─────────────────────────────────────────────────

def render_q_tab(tech):
    q_score    = float(tech.get("q_score", 0))
    q1         = float(tech.get("q1", 0))
    q3         = float(tech.get("q3", 0))
    q_warnings = tech.get("q_warnings", [])
    roe  = tech.get("roe")
    roa  = tech.get("roa")
    er   = tech.get("equity_ratio")
    opm  = tech.get("operating_margin")
    de   = tech.get("de_ratio")
    ic   = tech.get("interest_coverage")

    # ─ Qスコア + サブスコア ─
    st.metric("Qスコア（ビジネスの質）", f"{q_score:.1f} / 100")
    col1, col2 = st.columns(2)
    col1.metric("Q1 収益性", f"{q1:.1f}")
    col2.metric("Q3 財務健全性", f"{q3:.1f}")

    # ─ ノックアウト警告 ─
    for w in q_warnings:
        st.warning(w)

    st.markdown("---")

    # ─ Q1: 収益性テーブル ─
    st.markdown("##### 📊 収益性指標（Q1）")

    def _q1_eval(key, val):
        if val is None: return "—"
        if key == "roe":  return "✓ 高収益" if val >= 15 else ("△ 低収益" if val < 5 else "")
        if key == "roa":  return "✓ 高効率" if val >= 5  else ""
        if key == "opm":  return "✓ 高利益率" if val >= 10 else ("⚠️ 赤字" if val < 0 else "")
        return ""

    rows_q1 = [
        ("ROE",       _fmt_pct(roe), _q1_eval("roe", roe)),
        ("ROA",       _fmt_pct(roa), _q1_eval("roa", roa)),
        ("営業利益率", _fmt_pct(opm), _q1_eval("opm", opm)),
    ]
    st.markdown(_build_table(["指標", "値", "評価"], rows_q1), unsafe_allow_html=True)

    # ─ Q3: 財務健全性テーブル ─
    st.markdown("##### 🏦 財務健全性指標（Q3）")

    def _q3_eval(key, val):
        if val is None: return "—"
        if key == "er": return "✓ 健全" if val >= 40 else ("⚠️ 高レバ" if val < 20 else "")
        if key == "de": return "✓ 低負債" if val < 0.5 else ("⚠️ 過剰負債" if val > 2.0 else "")
        if key == "ic": return "✓ 余裕あり" if val >= 5 else ("⚠️ 危険圏" if val < 1.5 else "")
        return ""

    de_str = f"{de:.2f}x" if de is not None else "—"
    ic_str = f"{ic:.1f}x" if ic is not None else "—"
    rows_q3 = [
        ("自己資本比率",          _fmt_pct(er), _q3_eval("er", er)),
        ("D/E レシオ",            de_str,        _q3_eval("de", de)),
        ("インタレストカバレッジ", ic_str,        _q3_eval("ic", ic)),
    ]
    st.markdown(_build_table(["指標", "値", "評価"], rows_q3), unsafe_allow_html=True)

    # ─ セクター補正（v2互換） ─
    st.markdown("---")
    st.markdown("##### 🧩 セクター補正（任意）")

    col1, col2 = st.columns(2)
    with col1:
        sect_roe = st.number_input("セクター平均 ROE (%)", 0.0, 40.0, 10.0, 0.1)
    with col2:
        sect_roa = st.number_input("セクター平均 ROA (%)", 0.0, 20.0, 4.0, 0.1)

    if st.button("補正する", use_container_width=True):
        if roe is None or roa is None:
            st.error("ROE / ROA データが不足のため補正できません。")
        else:
            result   = apply_q_correction(tech=tech, sector_roe=sect_roe, sector_roa=sect_roa)
            q_corr   = result.get("q_corrected")
            qvt_corr = result.get("qvt_corrected")
            st.session_state["q_correction_result"] = result
            c1, c2 = st.columns(2)
            c1.metric("Q（補正前）", f"{q_score:.1f}")
            c2.metric("Q（補正後）", f"{q_corr:.1f}", delta=f"{q_corr - q_score:+.1f}")
            st.caption(f"補正後 QVT: **{qvt_corr:.1f}**")
            st.info("セクター基準を用いて Q を補正した結果です。")

    # ─ Qスコアの見方 ─
    st.markdown("---")
    with st.expander("📚 Qスコアの見方"):
        st.markdown("""
**Q1 収益性**
- **ROE** — 目安：10%前後が標準、15%超は高収益。借入依存に注意。
- **ROA** — 目安：3〜5%が標準、5%超は資産効率が高い。
- **営業利益率** — 5%未満は薄利、10%超は優良、20%超は超優良。

**Q3 財務健全性**
- **自己資本比率** — 30%未満は高レバレッジ、40〜60%が健全、60%超は堅固。
- **D/Eレシオ** — 1.0未満が目安。2.0超は過剰レバレッジ要注意。
- **インタレストカバレッジ** — 1.5未満は危険圏、5倍超が安全圏の目安。

| セクター例 | ROE目安 | ROA目安 | 営業利益率目安 |
|---|---|---|---|
| 生活必需品・インフラ | 8〜12% | 3〜6% | 5〜10% |
| テック・成長株 | 10〜20%+ | 5〜10% | 15〜30% |
| 景気敏感（自動車等） | 8〜12% | 3〜6% | 5〜10% |
| 金融 | 8〜12% | 0.5〜2% | — |
        """)


# ─── タブ: V ─────────────────────────────────────────────────

def render_v_tab(tech):
    v_score    = float(tech.get("v_score", 0))
    v1         = float(tech.get("v1", 0))
    v2         = float(tech.get("v2", 0))
    v3         = float(tech.get("v3", 0))
    v4         = tech.get("v4")
    has_sector = tech.get("has_sector", False)

    per      = tech.get("per")
    per_fwd  = tech.get("per_fwd")
    pbr      = tech.get("pbr")
    dy       = tech.get("dividend_yield")
    ev_ebitda = tech.get("ev_ebitda")

    ft         = tech.get("financial_type", {})
    sector_rel = tech.get("sector_rel_scores", {})

    # ─ Vスコア + サブスコア ─
    st.metric("Vスコア（割安度）", f"{v_score:.1f} / 100")

    if has_sector and v4 is not None:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("V1 割安",  f"{v1:.0f}")
        col2.metric("V2 CF系",  f"{v2:.0f}")
        col3.metric("V3 配当",  f"{v3:.0f}")
        col4.metric("V4 相対",  f"{v4:.0f}")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("V1 割安", f"{v1:.0f}")
        col2.metric("V2 CF系", f"{v2:.0f}")
        col3.metric("V3 配当", f"{v3:.0f}")
        if not has_sector:
            st.caption("ℹ️ セクター相対評価（V4）は日本株DBに収録された銘柄のみ対応。")

    st.markdown("---")

    # ─ 財務タイプバッジ（DB分類済み銘柄のみ） ─
    if ft.get("matched"):
        code = ft.get("code", "—")
        ja   = ft.get("ja", "—")
        desc = ft.get("description", "")
        conf = ft.get("confidence", "")
        conf_badge = {"HIGH": "🟢 HIGH", "MID": "🟡 MID", "NONE": "⚪ NONE"}.get(conf, conf)
        st.markdown(f"""
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:0.9rem 1.1rem;margin-bottom:0.8rem">
          <div style="font-size:0.65rem;letter-spacing:1.5px;color:var(--text-2);font-weight:700;text-transform:uppercase">財務タイプ（DB分類）</div>
          <div style="font-size:1.05rem;font-weight:700;color:var(--text);margin-top:0.3rem">{ja} <span style="font-size:0.7rem;color:var(--text-3)">({code})</span></div>
          <div style="font-size:0.8rem;color:var(--text-2);margin-top:0.3rem">{desc}</div>
          <div style="font-size:0.7rem;color:var(--text-3);margin-top:0.3rem">信頼度: {conf_badge}</div>
        </div>
        """, unsafe_allow_html=True)

    # ─ セクター相対テーブル ─
    if has_sector:
        st.markdown("##### 📊 セクター相対評価（V4）")
        def _rel_score_str(key):
            s = sector_rel.get(key)
            return f"{s:.0f}pt" if s is not None else "—"

        rows_rel = [
            ("PER（相対）",       sector_rel.get("per_vs_median", "—"),       _rel_score_str("per_rel_score")),
            ("PBR（相対）",       sector_rel.get("pbr_vs_median", "—"),       _rel_score_str("pbr_rel_score")),
            ("EV/EBITDA（相対）", sector_rel.get("ev_ebitda_vs_median", "—"), _rel_score_str("ev_ebitda_rel_score")),
        ]
        st.markdown(_build_table(["指標", "実測値（vs 中央値）", "相対スコア"], rows_rel), unsafe_allow_html=True)
        st.caption("スコア目安：100pt＝かなり割安 / 50pt＝中央値水準 / 0pt＝かなり割高")

    # ─ 絶対評価テーブル ─
    st.markdown("##### 📋 絶対評価（V1〜V3）")

    def eval_per(x):
        if x is None: return "—"
        if x < 12: return "✓ 割安"
        if x > 30: return "△ 割高"
        return ""

    def eval_pbr(x):
        if x is None: return "—"
        if x < 1: return "✓ 資産割安"
        if x > 3: return "△ 割高"
        return ""

    def eval_dy(x):
        if x is None: return "—"
        if x >= 3: return "✓ 高配当"
        return ""

    def eval_ev(x):
        if x is None: return "—"
        if x < 8:  return "✓ 割安"
        if x > 20: return "△ 割高"
        return ""

    rows = [
        ("PER（実績）",  _fmt_x(per),       eval_per(per)),
        ("予想 PER",     _fmt_x(per_fwd),   eval_per(per_fwd)),
        ("PBR",          _fmt_x(pbr),       eval_pbr(pbr)),
        ("EV/EBITDA",    _fmt_x(ev_ebitda), eval_ev(ev_ebitda)),
        ("配当利回り",   _fmt_pct(dy),      eval_dy(dy)),
    ]
    table_html = '<table class="cs-table"><thead><tr><th>指標</th><th style="text-align:right">値</th><th style="text-align:right">評価</th></tr></thead><tbody>'
    for label, val, ev in rows:
        badge = f'<span class="ev-badge">{ev}</span>' if ev and ev not in ("—", "") else ""
        table_html += f'<tr><td>{label}</td><td class="td-right">{val}</td><td style="text-align:right">{badge}</td></tr>'
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)
    st.caption("Vスコアはバリュエーションの目安。セクター特性と合わせて解釈してください。")

    # ─ 財務タイプ辞典 ─
    st.markdown("---")
    with st.expander("📖 財務タイプ辞典（全分類の解説）"):
        all_types = get_all_types_for_display()
        if all_types:
            for t in all_types:
                if t["sample_count"] == 0:
                    continue
                is_this = ft.get("matched") and ft.get("code") == t["code"]
                highlight = "🔍 **この銘柄の分類**  " if is_this else ""
                per_m = f"{t['per_median']:.1f}x"   if t["per_median"]              else "—"
                pbr_m = f"{t['pbr_median']:.2f}x"   if t["pbr_median"]              else "—"
                roe_m = f"{t['roe_median']*100:.1f}%" if t["roe_median"] is not None else "—"
                opm_m = f"{t['operating_margin_median']*100:.1f}%" if t["operating_margin_median"] is not None else "—"
                st.markdown(f"""
**{highlight}{t['ja']}** `{t['code']}`  
{t['description']}  
📊 中央値 — PER {per_m} / PBR {pbr_m} / ROE {roe_m} / 営業利益率 {opm_m} （n={t['sample_count']}）
""")
        else:
            st.info("財務タイプDBが読み込まれていません。`data/pattern_db_latest.csv` を確認してください。")


# ─── タブ: QVT ────────────────────────────────────────────────

def render_qvt_tab(tech):
    q   = float(tech["q_score"])
    v   = float(tech["v_score"])
    t   = float(tech["t_score"])
    qvt = float(tech["qvt_score"])

    corr = st.session_state.get("q_correction_result")
    if corr:
        q_show   = float(corr.get("q_corrected", q))
        qvt_show = float(corr.get("qvt_corrected", qvt))
    else:
        q_show   = q
        qvt_show = qvt

    col1, col2, col3 = st.columns(3)
    if corr:
        col1.metric("Q（補正後）", f"{q_show:.1f}", delta=f"{q_show - q:+.1f}")
    else:
        col1.metric("Q（質）", f"{q:.1f}")
    col2.metric("V（値札）", f"{v:.1f}")
    col3.metric("T（タイミング）", f"{t:.1f}")

    st.markdown("---")

    color = _color_score(qvt_show)
    msg = ("総合的に非常に魅力的（主力候補）"          if qvt_show >= 70
           else "買い検討レベル。押し目を慎重に狙いたい" if qvt_show >= 60
           else "悪くないが他候補との比較推奨"           if qvt_show >= 50
           else "テーマ性が強くないなら見送りも選択肢")
    star = "⭐⭐⭐" if qvt_show >= 70 else "⭐⭐" if qvt_show >= 60 else "⭐" if qvt_show >= 50 else ""

    st.markdown(f"""
    <div class="score-card" style="padding:1.5rem">
      <div class="score-label">QVT 総合スコア</div>
      <div class="score-value" style="color:{color};font-size:3.5rem">{qvt_show:.1f}</div>
      <div class="score-max">/ 100</div>
      <div style="font-size:1.2rem;margin-top:.5rem">{star}</div>
      <div style="font-size:.8rem;color:#9da3b8;margin-top:.5rem">{msg}</div>
    </div>
    """, unsafe_allow_html=True)

    if corr:
        st.caption("※ コメントは補正後QVTスコアをもとに判定しています。")

    with st.expander("📘 QVT フレームワーク"):
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
        """)


# ─── メイン ─────────────────────────────────────────────────

def main():
    setup_page()

    st.markdown('<div class="cs-title">check<span>SIGNAL</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="cs-sub">買いシグナルチェッカー v3 — 日本株 / 米国株対応</div>', unsafe_allow_html=True)

    # ─ APIキー状態チェック ─
    try:
        av_key = st.secrets.get("ALPHA_VANTAGE_API_KEY", None)
    except Exception:
        av_key = None

    if av_key:
        st.caption("✅ Alpha Vantage API キー設定済み（米国株ファンダメンタル対応）")
    else:
        st.info(
            "ℹ️ **米国株のファンダメンタル**（PER / PBR / ROE 等）を取得するには、"
            "Streamlit Cloud の Secrets に `ALPHA_VANTAGE_API_KEY` を設定してください。"
            "日本株は設定不要です。",
        )

    # ─ 入力 ─
    user_input = st.text_input(
        label="ティッカーを入力",
        placeholder="例：7203　8306　AAPL　MSFT",
        label_visibility="collapsed",
    )
    search = st.button("📡 分析する", use_container_width=True)
    st.caption("4〜5桁の数字は自動で .T（東証）付与。米株はそのまま入力。")

    if not search and not user_input:
        return

    ticker = convert_ticker(user_input)
    if not ticker:
        st.info("ティッカーを入力すると結果が表示されます。")
        return

    # ─ データ取得 ─
    with st.spinner(f"📥 {ticker} のデータを取得中…"):
        try:
            base = get_price_and_meta(ticker)
        except ValueError as e:
            st.error(str(e))
            return

    # ─ 財務タイプ分類（pattern_db） ─
    with st.spinner("🔍 財務タイプを分類中…"):
        db             = load_pattern_db()
        financial_type = classify_ticker(ticker, db)

        # セクター相対スコア計算用に PER/PBR を仮算出
        _close = base.get("close", 0)
        _eps   = base.get("eps")
        _bps   = base.get("bps")
        _per_tmp = (_close / _eps) if (_eps and _eps != 0 and _close) else None
        _pbr_tmp = (_close / _bps) if (_bps and _bps != 0 and _close) else None

        sector_rel    = calc_sector_relative_scores(
            ft=financial_type,
            per=_per_tmp,
            pbr=_pbr_tmp,
            ev_ebitda=base.get("ev_ebitda"),
        )
        sector_v_score = sector_rel.get("sector_v_score") if financial_type.get("matched") else None

    # ─ 指標計算 ─
    with st.spinner("🔢 指標を計算中…"):
        try:
            tech = compute_indicators(
                base["df"], base["close_col"],
                base["high_52w"], base["low_52w"],
                # 既存
                eps=base.get("eps"), bps=base.get("bps"),
                eps_fwd=base.get("eps_fwd"), per_fwd=base.get("per_fwd"),
                roe=base.get("roe"), roa=base.get("roa"),
                equity_ratio=base.get("equity_ratio"),
                dividend_yield=base.get("dividend_yield"),
                # v3 追加
                operating_margin=base.get("operating_margin"),
                de_ratio=base.get("de_ratio"),
                interest_coverage=base.get("interest_coverage"),
                ev_ebitda=base.get("ev_ebitda"),
                sector_v_score=sector_v_score,
                sector_rel_scores=sector_rel,
                financial_type=financial_type,
                industry=base.get("industry", ""),
                sector=base.get("sector", ""),
                is_us=not ticker.upper().endswith(".T"),  # ★v3.5
            )
        except ValueError as e:
            st.error(str(e))
            return

    # ─ ヘッダー ─
    render_price_header(ticker, base["company_name"], base["close"], base["previous_close"], base.get("industry",""), base.get("sector",""))
    render_metrics_row(tech)
    render_qvt_cards(tech["q_score"], tech["v_score"], tech["t_score"], tech["qvt_score"])

    st.markdown("---")

    # ─ タブ ─
    tab_t, tab_q, tab_v, tab_qvt = st.tabs(["⏰ タイミング", "🏢 質", "💰 値札", "🧮 総合"])

    with tab_t:
        render_t_tab(tech)
    with tab_q:
        render_q_tab(tech)
    with tab_v:
        render_v_tab(tech)
    with tab_qvt:
        render_qvt_tab(tech)

    if base.get("dividend_yield"):
        st.caption(f"予想配当利回り: **{base['dividend_yield']:.2f}%**")


if __name__ == "__main__":
    main()
