"""
main.py — iPhone最適化 Streamlit UI
"""
import streamlit as st
from app.modules.data_fetch import convert_ticker, get_price_and_meta
from app.modules.indicators import compute_indicators
from app.modules.q_correction import apply_q_correction


# ─── ページ設定 ─────────────────────────────────────────────

def setup_page():
    st.set_page_config(
        page_title="checkSIGNAL",
        page_icon="📡",
        layout="centered",   # iPhone は centered が読みやすい
        initial_sidebar_state="collapsed",
    )
    # カスタムCSS（iPhone最適化・ウォームライトテーマ）
    st.markdown("""
    <style>
    /* Google Fonts: Noto Sans JP（日本語）+ IBM Plex Mono（数字・視認性重視）+ Outfit（UI） */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500;600&family=Outfit:wght@600;700;800&display=swap');

    /* ── カラー変数（ダーク） ── */
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

    /* ── 全体 ── */
    html, body, [class*="css"] {
        font-family: 'Noto Sans JP', sans-serif;
        background-color: var(--bg) !important;
        color: var(--text) !important;
    }
    /* Streamlit のデフォルト白背景を上書き */
    .stApp, .stApp > div, section.main, .block-container {
        background-color: var(--bg) !important;
    }
    .main > div { padding-top: 1rem; padding-bottom: 3rem; }
    section[data-testid="stSidebar"] { display: none; }

    /* ── タイトル ── */
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

    /* ── スコアカード ── */
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

    /* ── シグナルバナー ── */
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

    /* ── 価格ヘッダー ── */
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

    /* ── メトリクスグリッド ── */
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

    /* ── レンジボックス ── */
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

    /* ── テーブル ── */
    .cs-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.87rem;
        table-layout: fixed;
    }
    /* 列幅 */
    .cs-table th:nth-child(1), .cs-table td:nth-child(1) { width: 28%; }
    .cs-table th:nth-child(2), .cs-table td:nth-child(2) { width: 54%; }
    .cs-table th:nth-child(3), .cs-table td:nth-child(3) { width: 18%; }
    /* ヘッダー */
    .cs-table thead th {
        padding: 6px 10px 6px 12px;
        font-size: 0.58rem; letter-spacing: 1.8px;
        text-transform: uppercase;
        color: var(--text-3); font-weight: 700;
        background: transparent;
        border-bottom: 1px solid var(--border);
        white-space: nowrap;
    }
    /* 奇数行・偶数行で交互カラー */
    .cs-table tbody tr:nth-child(odd)  { background: var(--surface); }
    .cs-table tbody tr:nth-child(even) { background: var(--card); }
    /* セル共通 */
    .cs-table tbody td {
        padding: 8px 10px 8px 12px;
        overflow: hidden; word-break: break-word;
        border: none;
    }
    /* 指標ラベル列 */
    .cs-table tbody td:nth-child(1) {
        color: var(--text-2);
        font-size: 0.78rem; font-weight: 600;
        letter-spacing: 0.1px;
        border-left: 3px solid transparent;
    }
    /* 値列 */
    .cs-table tbody td:nth-child(2) {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.9rem; font-weight: 600;
        color: var(--text);
    }
    /* 判定列 */
    .cs-table tbody td:nth-child(3) {
        text-align: center;
        vertical-align: middle;
    }
    /* ○ バッジ */
    .td-ok {
        display: inline-flex; align-items: center; justify-content: center;
        width: 24px; height: 24px;
        background: rgba(62,207,114,.20);
        color: var(--green);
        font-weight: 900; font-size: 0.8rem;
        border-radius: 50%;
        border: 1.5px solid rgba(62,207,114,.50);
    }
    /* × バッジ */
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
    /* 評価バッジ（Vタブ） */
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

    /* ── Streamlit標準コンポーネント上書き ── */
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
    /* info/warning メッセージ背景 */
    div[data-testid="stAlert"] {
        background-color: var(--surface) !important;
        color: var(--text) !important;
    }
    /* ボタン（iPhone指タップ向け） */
    div[data-testid="stButton"] > button {
        height: 3rem !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
        border-radius: 10px !important;
        width: 100%;
        font-family: 'Noto Sans JP', sans-serif !important;
    }
    /* テキスト入力 */
    div[data-testid="stTextInput"] input {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        height: 3rem !important;
        border-radius: 10px !important;
        color: var(--text) !important;
    }
    /* number_input */
    div[data-testid="stNumberInput"] input {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        height: 2.8rem !important;
    }
    /* セパレータ */
    hr { border-color: var(--border) !important; }

    /* expander */
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
    if s >= 70: return "#3ecf72"   # bright green
    if s >= 55: return "#4f8ef7"   # bright blue
    if s >= 40: return "#f5c542"   # amber
    return "#f05c6e"               # red

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


# ─── UI パーツ ───────────────────────────────────────────────

def render_price_header(ticker, company_name, close, prev_close):
    change = close - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0
    d = 0 if close >= 100 else 2
    cls = _price_class(change)
    sign = "+" if change >= 0 else ""
    chg_color = "#f05c6e" if change >= 0 else "#3ecf72"
    st.markdown(f"""
    <div class="price-header">
      <div class="price-company">{company_name}</div>
      <div class="price-ticker">{ticker}</div>
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
    sig_txt = tech["signal_text"]
    sig_icon = tech["signal_icon"]
    sig_str = tech["signal_strength"]
    hi_alert = tech.get("high_price_alert", False)
    t_label = tech["timing_label"]
    style = _signal_style(sig_str, hi_alert)

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

    # テーブル
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

    rows = [
        ("BB 位置",    f'{tech["bb_icon"]} {tech["bb_text"]}',  None),
        ("RSI (14)",   f'{_fmt(rsi, 1)}',   rsi < 30 if rsi else None),
        ("25MA vs 価格", "価格 < MA25" if price < ma25 else "価格 ≥ MA25", price < ma25),
        ("MA25 傾き",  f'{_fmt(slope, 2)}%',  None),
        ("52W 位置",   f'{pos52}%（安値から）', None),
        ("モード",     "📈 順張り" if tmode == "trend" else "🧮 逆張り", None),
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
    q_score = float(tech.get("q_score", 0))
    roe = tech.get("roe")
    roa = tech.get("roa")
    er  = tech.get("equity_ratio")

    st.metric("Qスコア", f"{q_score:.1f} / 100")

    if roe is None and roa is None and er is None:
        st.caption("⚠️ ROE / ROA / 自己資本比率のデータが取得できませんでした。")
    else:
        table_html = '<table class="cs-table"><thead><tr><th>指標</th><th style="text-align:right">値</th></tr></thead><tbody>'
        for label, val in [("ROE", _fmt_pct(roe)), ("ROA", _fmt_pct(roa)),
                            ("自己資本比率", _fmt_pct(er))]:
            table_html += f'<tr><td>{label}</td><td class="td-right">{val}</td></tr>'
        table_html += '</tbody></table>'
        st.markdown(table_html, unsafe_allow_html=True)

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
            result = apply_q_correction(tech=tech, sector_roe=sect_roe, sector_roa=sect_roa)
            q_corr = result.get("q_corrected")
            qvt_corr = result.get("qvt_corrected")
            st.session_state["q_correction_result"] = result

            c1, c2 = st.columns(2)
            c1.metric("Q（補正前）", f"{q_score:.1f}")
            c2.metric("Q（補正後）", f"{q_corr:.1f}", delta=f"{q_corr - q_score:+.1f}")
            st.caption(f"補正後 QVT: **{qvt_corr:.1f}**")
            st.info("セクター基準を用いて Q を補正した結果です。")

    st.markdown("---")
    with st.expander("📚 Qスコアの見方"):
        st.markdown("""
**ROE** — 目安：10%前後が標準、15%超は高収益。借入依存に注意。  
**ROA** — 目安：3〜5%が標準、5〜8%超は資産効率が高い。  
**自己資本比率** — 30%未満は高レバレッジ、40〜60%が健全、60%超は堅固。

| セクター例 | ROE目安 | ROA目安 |
|---|---|---|
| 生活必需品・インフラ | 8〜12% | 3〜6% |
| テック・成長株 | 10〜20%+ | 5〜10% |
| 景気敏感（自動車等） | 8〜12% | 3〜6% |
| 金融 | 8〜12% | 0.5〜2% |
        """)


# ─── タブ: V ─────────────────────────────────────────────────

def render_v_tab(tech):
    v_score = float(tech.get("v_score", 0))
    per = tech.get("per")
    per_fwd = tech.get("per_fwd")
    pbr = tech.get("pbr")
    dy  = tech.get("dividend_yield")

    st.metric("Vスコア（割安度）", f"{v_score:.1f} / 100")

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

    rows = [
        ("PER（実績）", _fmt_x(per), eval_per(per)),
        ("予想 PER",    _fmt_x(per_fwd), eval_per(per_fwd)),
        ("PBR",        _fmt_x(pbr), eval_pbr(pbr)),
        ("配当利回り",  _fmt_pct(dy), eval_dy(dy)),
    ]
    table_html = '<table class="cs-table"><thead><tr><th>指標</th><th style="text-align:right">値</th><th style="text-align:right">評価</th></tr></thead><tbody>'
    for label, val, ev in rows:
        badge = f'<span class="ev-badge">{ev}</span>' if ev and ev not in ("—","") else ""
        table_html += f'<tr><td>{label}</td><td class="td-right">{val}</td><td style="text-align:right">{badge}</td></tr>'
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)
    st.caption("Vスコアは PER / PBR / 配当利回りを正規化したざっくり指標。セクター特性と合わせて解釈推奨。")


# ─── タブ: QVT ────────────────────────────────────────────────

def render_qvt_tab(tech):
    q = float(tech["q_score"])
    v = float(tech["v_score"])
    t = float(tech["t_score"])
    qvt = float(tech["qvt_score"])

    corr = st.session_state.get("q_correction_result")
    if corr:
        q_show = float(corr.get("q_corrected", q))
        qvt_show = float(corr.get("qvt_corrected", qvt))
    else:
        q_show = q
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
    msg = ("総合的に非常に魅力的（主力候補）" if qvt_show >= 70
           else "買い検討レベル。押し目を慎重に狙いたい" if qvt_show >= 60
           else "悪くないが他候補との比較推奨" if qvt_show >= 50
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
**Q（Quality）** — ビジネスの質。ROE・ROA・自己資本比率から算出。  
**V（Valuation）** — 割安度。PER・PBR・配当利回りから算出。  
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
    st.markdown('<div class="cs-sub">買いシグナルチェッカー v2 — 日本株 / 米国株対応</div>', unsafe_allow_html=True)

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

    with st.spinner("🔢 指標を計算中…"):
        try:
            tech = compute_indicators(
                base["df"], base["close_col"],
                base["high_52w"], base["low_52w"],
                eps=base.get("eps"), bps=base.get("bps"),
                eps_fwd=base.get("eps_fwd"), per_fwd=base.get("per_fwd"),
                roe=base.get("roe"), roa=base.get("roa"),
                equity_ratio=base.get("equity_ratio"),
                dividend_yield=base.get("dividend_yield"),
            )
        except ValueError as e:
            st.error(str(e))
            return

    # ─ ヘッダー ─
    render_price_header(ticker, base["company_name"], base["close"], base["previous_close"])
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

    # 配当利回り
    if base.get("dividend_yield"):
        st.caption(f"予想配当利回り: **{base['dividend_yield']:.2f}%**")
