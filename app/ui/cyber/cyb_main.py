"""
app/ui/cyber/main.py — checkSIGNAL Cyberpunk Edition
cls_main.py のロジック・仕様関数をサイバーパンクUIで再実装したバージョン。

エントリーポイント: run()
"""

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from modules.data_fetch import convert_ticker
from modules.q_correction import apply_q_correction
from modules.pattern_db import get_all_types_for_display
from ui.output_structure import build_analysis_output
from dict.dic1 import DEFENSIVE_RANK_LABELS


# ─── グローバルスタイル ──────────────────────────────────────────

def _setup_style():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&display=swap');

    :root {
        --bg:       #05050a;
        --surface:  #0a0a15;
        --card:     #0d0d1f;
        --border:   #00f3ff44;
        --cyan:     #00f3ff;
        --green:    #00ff88;
        --pink:     #ff0055;
        --yellow:   #f5c542;
        --text:     #c8f0ff;
        --text-2:   #6aaabb;
        --text-3:   #2a4a55;
    }

    html, body, [class*="css"] {
        font-family: 'Share Tech Mono', monospace;
        background-color: var(--bg) !important;
        color: var(--text) !important;
    }
    .stApp, .stApp > div, section.main, .block-container {
        background-color: var(--bg) !important;
    }
    .main > div { padding-top: 1rem; padding-bottom: 3rem; }

    [data-testid="stSidebar"] {
        background-color: var(--surface);
        border-right: 1px solid var(--cyan);
    }

    h1, h2, h3 {
        color: var(--cyan) !important;
        text-shadow: 0 0 10px var(--cyan), 0 0 20px var(--cyan);
        font-family: 'Orbitron', monospace;
        letter-spacing: 2px;
    }

    .stButton > button {
        background-color: rgba(0, 243, 255, 0.08);
        color: var(--cyan);
        border: 1px solid var(--cyan);
        border-radius: 0px;
        transition: 0.3s;
        width: 100%;
        font-family: 'Share Tech Mono', monospace;
        letter-spacing: 1px;
    }
    .stButton > button:hover {
        background-color: var(--cyan);
        color: #000;
        box-shadow: 0 0 20px var(--cyan);
    }

    div[data-testid="stTextInput"] input {
        background: var(--surface) !important;
        border: 1px solid var(--cyan) !important;
        color: var(--cyan) !important;
        font-family: 'Share Tech Mono', monospace !important;
        font-size: 1.1rem !important;
        border-radius: 0px !important;
    }

    div[data-testid="stTabs"] button {
        font-family: 'Share Tech Mono', monospace !important;
        color: var(--text-2) !important;
        font-size: 0.8rem !important;
        letter-spacing: 1px;
    }
    div[data-testid="stTabs"] button[aria-selected="true"] {
        color: var(--cyan) !important;
        text-shadow: 0 0 8px var(--cyan);
        border-bottom: 2px solid var(--cyan) !important;
    }

    div[data-testid="metric-container"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 0px !important;
        padding: 0.8rem !important;
    }
    div[data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-family: 'Share Tech Mono', monospace !important;
        font-size: 1.6rem !important;
        font-weight: 700 !important;
        color: var(--cyan) !important;
        text-shadow: 0 0 8px var(--cyan);
    }
    div[data-testid="metric-container"] label {
        font-size: 0.65rem !important;
        color: var(--text-2) !important;
        letter-spacing: 1.5px !important;
        text-transform: uppercase;
    }

    hr { border-color: var(--border) !important; }

    div[data-testid="stExpander"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 0px !important;
    }

    /* テーブルスタイル */
    .cyb-table {
        width: 100%; border-collapse: collapse;
        font-family: 'Share Tech Mono', monospace;
        font-size: 0.85rem; table-layout: fixed;
    }
    .cyb-table thead th {
        padding: 6px 10px;
        font-size: 0.58rem; letter-spacing: 1.8px;
        text-transform: uppercase; color: var(--text-2);
        font-weight: 700; background: transparent;
        border-bottom: 1px solid var(--border);
    }
    .cyb-table tbody tr:nth-child(odd)  { background: var(--surface); }
    .cyb-table tbody tr:nth-child(even) { background: var(--card); }
    .cyb-table tbody td {
        padding: 8px 10px; overflow: hidden;
        word-break: break-word; border: none; color: var(--text);
    }
    .cyb-table tbody td:nth-child(1) {
        color: var(--text-2); font-size: 0.78rem;
    }
    .td-ok {
        display: inline-flex; align-items: center; justify-content: center;
        width: 24px; height: 24px;
        background: rgba(0,255,136,.20); color: var(--green);
        font-weight: 900; font-size: 0.8rem;
        border-radius: 0; border: 1.5px solid rgba(0,255,136,.50);
    }
    .td-ng {
        display: inline-flex; align-items: center; justify-content: center;
        width: 24px; height: 24px;
        background: rgba(255,0,85,.20); color: var(--pink);
        font-weight: 900; font-size: 0.8rem;
        border-radius: 0; border: 1.5px solid rgba(255,0,85,.50);
    }
    .td-neu { color: var(--text-3); font-size: 1rem; }
    .ev-badge {
        display: inline-block; background: rgba(0,255,136,.15);
        color: var(--green); font-size: 0.72rem; font-weight: 700;
        padding: 2px 6px; white-space: nowrap;
    }
    .td-right { text-align: right; }

    /* スコアカード */
    .cyb-score-card {
        background: var(--surface);
        border: 1px solid var(--cyan);
        padding: 1rem; text-align: center;
        margin-bottom: 0.5rem;
        box-shadow: 0 0 10px rgba(0,243,255,0.1);
    }
    .cyb-score-label {
        font-size: 0.62rem; letter-spacing: 2px;
        text-transform: uppercase; color: var(--text-2); margin-bottom: 0.4rem;
    }
    .cyb-score-value {
        font-family: 'Orbitron', monospace;
        font-size: 2rem; font-weight: 700; line-height: 1;
    }
    .cyb-score-max { font-size: 0.65rem; color: var(--text-3); margin-top: 0.2rem; }

    /* メトリクスグリッド */
    .cyb-metric-grid {
        display: grid; grid-template-columns: 1fr 1fr;
        gap: 0.4rem; margin-bottom: 0.8rem;
    }
    .cyb-metric-item {
        background: var(--surface);
        border: 1px solid var(--border);
        padding: 0.7rem 0.9rem;
    }
    .cyb-metric-lbl {
        font-size: 0.6rem; letter-spacing: 1.2px;
        text-transform: uppercase; color: var(--text-2);
        margin-bottom: 0.3rem;
    }
    .cyb-metric-val {
        font-family: 'Share Tech Mono', monospace;
        font-size: 1.25rem; font-weight: 700; color: var(--cyan);
        text-shadow: 0 0 6px var(--cyan);
    }
    .cyb-metric-sub {
        font-size: 0.75rem; color: var(--text-2); margin-top: 0.1rem;
    }

    /* 価格ヘッダー */
    .cyb-price-header {
        background: var(--surface);
        border: 1px solid var(--cyan);
        border-left: 3px solid var(--cyan);
        padding: 1rem 1.2rem; margin-bottom: 1rem;
        box-shadow: 0 0 15px rgba(0,243,255,0.1);
    }
    .cyb-ticker { font-size: 0.85rem; color: var(--text-2); letter-spacing: 2px; }
    .cyb-company { font-size: 1.1rem; font-weight: 700; color: var(--text); margin-top: 0.2rem; }
    .cyb-price-main {
        font-family: 'Orbitron', monospace;
        font-size: 2.2rem; font-weight: 700; margin-top: 0.6rem;
        letter-spacing: -0.5px; text-shadow: 0 0 10px currentColor;
    }
    .cyb-price-up   { color: var(--pink); }
    .cyb-price-down { color: var(--green); }
    .cyb-price-flat { color: var(--text); }
    .cyb-price-chg  { font-size: 0.85rem; margin-top: 0.2rem; }

    /* シグナルバナー */
    .cyb-signal-banner {
        padding: 1rem 1.2rem; margin-bottom: 0.8rem;
        display: flex; align-items: center; gap: 0.8rem;
        border-left: 3px solid;
    }
    .cyb-signal-text {
        font-family: 'Orbitron', monospace;
        font-size: 1rem; font-weight: 700; letter-spacing: 1px;
    }
    .cyb-signal-sub { font-size: 0.75rem; color: var(--text-2); margin-top: 0.1rem; }

    /* レンジグリッド */
    .cyb-range-grid {
        display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.4rem;
    }
    .cyb-range-item {
        background: var(--card); border: 1px solid var(--border);
        padding: 0.75rem; text-align: center;
    }
    .cyb-range-lbl {
        font-size: 0.58rem; letter-spacing: 1px; text-transform: uppercase;
        color: var(--text-2); margin-bottom: 0.25rem;
    }
    .cyb-range-val {
        font-family: 'Share Tech Mono', monospace;
        font-size: 1rem; font-weight: 700; color: var(--cyan);
    }
    </style>
    """, unsafe_allow_html=True)


# ─── ヘルパー関数（cls_main.py より移植） ──────────────────────────

def _fmt(x, d=2):
    return "—" if x is None else f"{float(x):.{d}f}"

def _fmt_pct(x):
    return "—" if x is None else f"{float(x):.1f}%"

def _fmt_x(x):
    return "—" if x is None else f"{float(x):.2f}倍"

def _fmt_optional_pct_from_ratio(x):
    return "—" if x is None else f"{float(x) * 100:.1f}%"

def _fmt_optional_float(x, digits=3):
    return "—" if x is None else f"{float(x):.{digits}f}"

def _color_score(s):
    """スコアに応じたサイバーパンクカラーを返す"""
    if s >= 70: return "#00ff88"   # ネオングリーン
    if s >= 55: return "#00f3ff"   # シアン
    if s >= 40: return "#f5c542"   # イエロー
    return "#ff0055"               # ネオンピンク

def _price_class(change):
    if change > 0: return "cyb-price-up"
    if change < 0: return "cyb-price-down"
    return "cyb-price-flat"

def _signal_style(strength, hi_alert):
    if strength >= 3:
        return "background:rgba(0,255,136,.08);border:1px solid #00ff88;border-left:3px solid #00ff88;"
    if strength == 2:
        return "background:rgba(245,197,66,.08);border:1px solid #f5c542;border-left:3px solid #f5c542;"
    if hi_alert:
        return "background:rgba(255,0,85,.08);border:1px solid #ff0055;border-left:3px solid #ff0055;"
    return "background:rgba(0,243,255,.06);border:1px solid #00f3ff44;border-left:3px solid #00f3ff;"

def _build_table(headers, rows):
    ths  = "".join(f"<th>{h}</th>" for h in headers)
    html = f'<table class="cyb-table"><thead><tr>{ths}</tr></thead><tbody>'
    for row in rows:
        cells = "".join(f"<td>{c}</td>" for c in row)
        html += f"<tr>{cells}</tr>"
    html += "</tbody></table>"
    return html


# ─── CyberUI クラス（シグナルカード表示） ──────────────────────────

class CyberUI:
    """
    checkSIGNALs Cyberpunk Edition UI Component
    シグナルカード表示に特化したコンポーネント
    """

    def render_signal_card(self, symbol, signal_type, price, power, volume="NORMAL"):
        """メインのシグナル表示カード"""
        theme_color = "#00f3ff"
        glow_class  = "glow-cyan"

        if signal_type == "HIGH":
            theme_color = "#00ff88"
            glow_class  = "glow-green"
        elif signal_type == "LOW":
            theme_color = "#ff0055"
            glow_class  = "glow-pink"

        html_content = f"""
        <div class="cyber-card {glow_class}">
            <div class="scanline"></div>
            <div class="header">
                <span class="system-tag">SYSTEM_CORE_V4</span>
                <span class="status-tag">ONLINE</span>
            </div>
            <div class="symbol">{symbol}</div>
            <div class="signal-text">{signal_type}</div>
            <div class="price-display">{price}</div>
            <div class="footer-grid">
                <div class="stat-box">
                    <div class="label">POWER</div>
                    <div class="value">{power}%</div>
                </div>
                <div class="stat-box" style="border-left: 1px solid {theme_color}44;">
                    <div class="label">VOL</div>
                    <div class="value">{volume}</div>
                </div>
            </div>
        </div>

        <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

        .cyber-card {{
            background: rgba(10, 10, 20, 0.9);
            border: 2px solid {theme_color};
            padding: 20px; position: relative; overflow: hidden;
            font-family: 'Share Tech Mono', monospace;
            color: {theme_color}; margin: 10px 0; min-height: 220px;
        }}
        .scanline {{
            width: 100%; height: 2px;
            background: rgba(255,255,255,0.1);
            position: absolute; top: 0; left: 0;
            animation: scan 4s linear infinite; z-index: 10;
        }}
        @keyframes scan {{ 0% {{ top: 0; }} 100% {{ top: 100%; }} }}

        .glow-cyan  {{ box-shadow: 0 0 20px rgba(0,243,255,0.3), inset 0 0 10px rgba(0,243,255,0.2); }}
        .glow-green {{ box-shadow: 0 0 25px rgba(0,255,136,0.4), inset 0 0 10px rgba(0,255,136,0.2); border-color:#00ff88; }}
        .glow-pink  {{ box-shadow: 0 0 25px rgba(255,0,85,0.4),  inset 0 0 10px rgba(255,0,85,0.2);  border-color:#ff0055; }}

        .header {{ display:flex; justify-content:space-between; font-size:10px; margin-bottom:15px; border-bottom:1px solid {theme_color}44; padding-bottom:5px; }}
        .symbol {{ font-size:18px; letter-spacing:3px; opacity:0.8; }}
        .signal-text {{ font-size:68px; font-weight:bold; text-align:center; margin:10px 0; text-shadow:0 0 15px {theme_color}; }}
        .price-display {{ font-size:32px; text-align:center; color:#fff; letter-spacing:2px; }}
        .footer-grid {{ display:grid; grid-template-columns:1fr 1fr; margin-top:20px; border-top:1px solid {theme_color}44; padding-top:10px; }}
        .stat-box {{ text-align:center; }}
        .label {{ font-size:10px; opacity:0.6; }}
        .value {{ font-size:18px; font-weight:bold; }}
        </style>
        """
        components.html(html_content, height=320)


# ─── UI パーツ（cls_main.py の render_* をサイバー化） ────────────

def render_price_header(ticker, company_name, close, prev_close, industry="", sector=""):
    company_name = company_name.rstrip("の").strip()
    change     = close - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0
    d          = 0 if close >= 100 else 2
    cls        = _price_class(change)
    sign       = "+" if change >= 0 else ""
    chg_color  = "#ff0055" if change >= 0 else "#00ff88"

    def _badge(text, bg, border, fg):
        return (f'<span style="display:inline-block;background:{bg};'
                f'border:1px solid {border};'
                f'font-size:0.72rem;padding:1px 8px;margin-left:6px;'
                f'color:{fg};vertical-align:middle;font-family:Share Tech Mono,monospace;">{text}</span>')

    badges = ""
    if industry:
        badges += _badge(industry, "rgba(0,243,255,.12)", "rgba(0,243,255,.4)", "#00f3ff")
    if sector and sector != industry:
        badges += _badge(sector, "rgba(0,255,136,.10)", "rgba(0,255,136,.35)", "#00ff88")

    st.markdown(f"""
    <div class="cyb-price-header">
      <div class="cyb-company">{company_name}</div>
      <div class="cyb-ticker">{ticker}{badges}</div>
      <div class="cyb-price-main {cls}">{_fmt(close, d)}</div>
      <div class="cyb-price-chg" style="color:{chg_color}">
        &gt; 前日比 {sign}{_fmt(change, d)} ({sign}{_fmt(change_pct, 2)}%)
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_metrics_row(tech):
    d = 0 if tech["close"] >= 100 else 2
    st.markdown(f"""
    <div class="cyb-metric-grid">
      <div class="cyb-metric-item">
        <div class="cyb-metric-lbl">RSI (14)</div>
        <div class="cyb-metric-val">{_fmt(tech["rsi"], 1)}</div>
      </div>
      <div class="cyb-metric-item">
        <div class="cyb-metric-lbl">BB 判定</div>
        <div class="cyb-metric-val">{tech["bb_icon"]}</div>
        <div class="cyb-metric-sub">{tech["bb_text"]}</div>
      </div>
      <div class="cyb-metric-item">
        <div class="cyb-metric-lbl">25MA</div>
        <div class="cyb-metric-val">{_fmt(tech["ma_25"], d)}</div>
        <div class="cyb-metric-sub">{tech["arrow_25"]}</div>
      </div>
      <div class="cyb-metric-item">
        <div class="cyb-metric-lbl">50MA</div>
        <div class="cyb-metric-val">{_fmt(tech["ma_50"], d)}</div>
        <div class="cyb-metric-sub">{tech["arrow_50"]}</div>
      </div>
      <div class="cyb-metric-item">
        <div class="cyb-metric-lbl">75MA</div>
        <div class="cyb-metric-val">{_fmt(tech["ma_75"], d)}</div>
        <div class="cyb-metric-sub">{tech["arrow_75"]}</div>
      </div>
      <div class="cyb-metric-item">
        <div class="cyb-metric-lbl">52W 高値</div>
        <div class="cyb-metric-val">{_fmt(tech["high_52w"], d)}</div>
        <div class="cyb-metric-sub">安値 {_fmt(tech["low_52w"], d)}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_qvt_cards(q, v, t, qvt):
    def card(label, score, color):
        glow = f"0 0 12px {color}88"
        return f"""
        <div class="cyb-score-card" style="border-color:{color};box-shadow:{glow};">
          <div class="cyb-score-label">{label}</div>
          <div class="cyb-score-value" style="color:{color};text-shadow:0 0 10px {color}">{score:.1f}</div>
          <div class="cyb-score-max">/ 100</div>
        </div>"""

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(card("Q — 質",   q,   "#00ff88"), unsafe_allow_html=True)
    with col2: st.markdown(card("V — 値札", v,   "#00f3ff"), unsafe_allow_html=True)
    with col3: st.markdown(card("T — 時機", t,   "#f5c542"), unsafe_allow_html=True)
    with col4: st.markdown(card("QVT",      qvt, _color_score(qvt)), unsafe_allow_html=True)


# ─── タブ: T ──────────────────────────────────────────────────────

def render_t_tab(tech):
    sig_txt  = tech["signal_text"]
    sig_icon = tech["signal_icon"]
    sig_str  = tech["signal_strength"]
    hi_alert = tech.get("high_price_alert", False)
    t_label  = tech["timing_label"]
    style    = _signal_style(sig_str, hi_alert)

    st.markdown(f"""
    <div class="cyb-signal-banner" style="{style}">
      <div style="font-size:1.8rem">{sig_icon}</div>
      <div>
        <div class="cyb-signal-text">&gt; {sig_txt}</div>
        <div class="cyb-signal-sub">{t_label}</div>
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

    def _slope_label(s):
        if s is None: return "—"
        sign = "+" if s >= 0 else ""
        if s >= 1.5:    desc = "急上昇中"
        elif s >= 0.3:  desc = "上昇中"
        elif s >= 0:    desc = "緩やかに上昇中"
        elif s >= -0.3: desc = "緩やかに下落中"
        elif s >= -1.5: desc = "下落中"
        else:           desc = "急下落中"
        color = "#00ff88" if s >= 0 else "#ff0055"
        return (f'<span style="font-family:Share Tech Mono,monospace;color:{color};font-weight:700">'
                f'{sign}{s:.2f}%</span>'
                f'<span style="font-size:.8rem;color:#6aaabb;margin-left:6px">({desc})</span>')

    def make_52w_bar(pos):
        filled = round(pos / 10)
        bar    = '█' * filled + '░' * (10 - filled)
        color  = '#ff0055' if pos >= 80 else '#f5c542' if pos >= 60 else '#00ff88'
        return (f'<span style="font-family:monospace;letter-spacing:1px;color:{color}">{bar}</span>'
                f'<span style="font-size:.8rem;color:#6aaabb;margin-left:6px">（高値まで {100-pos}%）</span>')

    rows = [
        ("BB 位置",      f'{tech["bb_icon"]} {tech["bb_text"]}', None),
        ("RSI (14)",     f'{_fmt(rsi, 1)}',                      rsi < 30 if rsi else None),
        ("25MA vs 価格", "価格 < MA25" if price < ma25 else "価格 ≥ MA25", price < ma25),
        ("MA25 傾き",    _slope_label(slope),                    None),
        ("52W 位置",     make_52w_bar(pos52),                    None),
        ("モード",       "📈 順張り" if tmode == "trend" else "🧮 逆張り", None),
    ]
    table_html = '<table class="cyb-table"><thead><tr><th>指標</th><th>値</th><th style="text-align:center">判定</th></tr></thead><tbody>'
    for label, val, cond in rows:
        table_html += f'<tr><td>{label}</td><td>{val}</td><td style="text-align:center">{ok_ng(cond)}</td></tr>'
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### 📌 裁量買いレンジ（目安）")
    d = 0 if price >= 100 else 2
    if tmode == "trend":
        center   = (ma25 + ma50) / 2
        upper    = center * 1.03
        lower    = max(center * 0.95, tech["bb_minus1"])
        mode_lbl = "📈 順張り（上昇トレンド押し目狙い）"
    else:
        center   = (ma25 + tech["bb_minus1"]) / 2
        upper    = center * 1.08
        lower    = center * 0.97
        mode_lbl = "🧮 逆張り（調整局面の押し目狙い）"

    st.caption(f"モード: {mode_lbl}")
    st.markdown(f"""
    <div class="cyb-range-grid">
      <div class="cyb-range-item"><div class="cyb-range-lbl">下値（目安）</div><div class="cyb-range-val">{_fmt(lower, d)}</div></div>
      <div class="cyb-range-item"><div class="cyb-range-lbl">中心（目安）</div><div class="cyb-range-val">{_fmt(center, d)}</div></div>
      <div class="cyb-range-item"><div class="cyb-range-lbl">上値（目安）</div><div class="cyb-range-val">{_fmt(upper, d)}</div></div>
    </div>
    """, unsafe_allow_html=True)
    st.caption("※ 裁量買いレンジは環境チェック・トレンド・QVTスコアを組み合わせた参考値です。")


# ─── タブ: Q ──────────────────────────────────────────────────────

def render_q_tab(tech):
    q_score    = float(tech.get("q_score", 0))
    q1         = float(tech.get("q1", 0))
    q3         = float(tech.get("q3", 0))
    q_warnings = tech.get("q_warnings", [])
    roe  = tech.get("roe");  roa = tech.get("roa")
    er   = tech.get("equity_ratio")
    opm  = tech.get("operating_margin")
    de   = tech.get("de_ratio");  ic = tech.get("interest_coverage")
    er_thr   = tech.get("er_threshold", 10.0)
    ic_thr   = tech.get("ic_threshold",  1.5)
    thr_note = tech.get("threshold_note", "標準基準")

    st.metric("Q スコア（ビジネスの質）", f"{q_score:.1f} / 100")
    col1, col2 = st.columns(2)
    col1.metric("Q1 収益性", f"{q1:.1f}")
    col2.metric("Q3 財務健全性", f"{q3:.1f}")

    if thr_note and thr_note != "標準基準":
        st.caption(f"📋 {thr_note}｜自己資本比率閾値 **{er_thr:.0f}%** ／ インタレストカバレッジ閾値 **{ic_thr:.1f}x**")

    for w in q_warnings:
        st.warning(w)

    st.markdown("---")
    st.markdown("##### 📊 収益性指標（Q1）")

    def _q1_eval(key, val):
        if val is None: return "—"
        if key == "roe": return "✓ 高収益" if val >= 15 else ("△ 低収益" if val < 5 else "")
        if key == "roa": return "✓ 高効率" if val >= 5  else ""
        if key == "opm": return "✓ 高利益率" if val >= 10 else ("⚠️ 赤字" if val < 0 else "")
        return ""

    st.markdown(_build_table(["指標", "値", "評価"], [
        ("ROE",        _fmt_pct(roe), _q1_eval("roe", roe)),
        ("ROA",        _fmt_pct(roa), _q1_eval("roa", roa)),
        ("営業利益率", _fmt_pct(opm), _q1_eval("opm", opm)),
    ]), unsafe_allow_html=True)

    st.markdown("##### 🏦 財務健全性指標（Q3）")

    def _q3_eval(key, val):
        if val is None: return "—"
        if key == "er":
            if val >= 40:      return "✓ 健全"
            elif val < er_thr: return f"⚠️ 高レバ（{thr_note}）"
            return ""
        if key == "de": return "✓ 低負債" if val < 0.5 else ("⚠️ 過剰負債" if val > 2.0 else "")
        if key == "ic":
            if val >= 5:       return "✓ 余裕あり"
            elif val < ic_thr: return "⚠️ 危険圏"
            return ""
        return ""

    st.markdown(_build_table(["指標", "値", "評価"], [
        ("自己資本比率",          _fmt_pct(er),                _q3_eval("er", er)),
        ("D/E レシオ",            f"{de:.2f}x" if de else "—", _q3_eval("de", de)),
        ("インタレストカバレッジ", f"{ic:.1f}x" if ic else "—", _q3_eval("ic", ic)),
    ]), unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### 🧩 セクター補正（任意）")
    col1, col2 = st.columns(2)
    with col1: sect_roe = st.number_input("セクター平均 ROE (%)", 0.0, 40.0, 10.0, 0.1)
    with col2: sect_roa = st.number_input("セクター平均 ROA (%)", 0.0, 20.0,  4.0, 0.1)

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

    st.markdown("---")
    with st.expander("📚 Qスコアの見方"):
        st.markdown("""
**Q1 収益性**
- **ROE** — 目安：10%前後が標準、15%超は高収益。借入依存に注意。
- **ROA** — 目安：3〜5%が標準、5%超は資産効率が高い。
- **営業利益率** — 5%未満は薄利、10%超は優良、20%超は超優良。

**Q3 財務健全性**
- **自己資本比率** — 30%未満は高レバレッジ、40〜60%が健全。
- **D/Eレシオ** — 1.0未満が目安。2.0超は過剰レバレッジ要注意。
- **インタレストカバレッジ** — 1.5未満は危険圏、5倍超が安全圏。
        """)


# ─── タブ: V ──────────────────────────────────────────────────────

def render_v_tab(tech):
    v_score    = float(tech.get("v_score", 0))
    v1         = float(tech.get("v1", 0))
    v2         = float(tech.get("v2", 0))
    v3         = float(tech.get("v3", 0))
    v4         = tech.get("v4")
    is_us      = tech.get("is_us", False)
    has_sector = tech.get("has_sector", False)
    per        = tech.get("per");  per_fwd = tech.get("per_fwd")
    pbr        = tech.get("pbr");  dy      = tech.get("dividend_yield")
    ev_ebitda  = tech.get("ev_ebitda")
    sector_name = tech.get("sector")

    _SECTOR_JA = {
        "Financial Services": "金融", "Technology": "テクノロジー",
        "Healthcare": "ヘルスケア", "Consumer Cyclical": "景気循環消費財",
        "Consumer Defensive": "生活必需品", "Industrials": "資本財",
        "Basic Materials": "素材", "Energy": "エネルギー",
        "Real Estate": "不動産", "Communication Services": "通信サービス",
        "Utilities": "公益",
    }
    sector_display = _SECTOR_JA.get(sector_name, sector_name) if sector_name else "不明"
    ft         = tech.get("financial_type", {})
    sector_rel = tech.get("sector_rel_scores", {})

    st.metric("V スコア（割安度）", f"{v_score:.1f} / 100")

    if has_sector and v4 is not None:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("V1 伝統的割安度", f"{v1:.0f}"); col2.metric("V2 企業価値割安度", f"{v2:.0f}")
        col3.metric("V3 株主還元度",   f"{v3:.0f}"); col4.metric("V4 セクター内診断", f"{v4:.0f}")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("V1 伝統的割安度",  f"{v1:.0f}")
        col2.metric("V2 企業価値割安度", f"{v2:.0f}")
        col3.metric("V3 株主還元度",    f"{v3:.0f}")
        if not has_sector:
            st.caption("ℹ️ V4 セクター内診断は日本株DBに収録された銘柄のみ対応。")

    if is_us:
        st.markdown("""
        <div style="background:var(--surface);border:1px solid var(--border);padding:0.9rem 1.1rem;margin-bottom:0.8rem">
          <div style="font-size:0.65rem;letter-spacing:1.5px;color:var(--text-2);text-transform:uppercase">財務タイプ（DB分類）</div>
          <div style="font-size:1.05rem;font-weight:700;color:var(--cyan);margin-top:0.3rem">米国株（分類対象外）</div>
        </div>
        """, unsafe_allow_html=True)
    elif ft.get("code"):
        code = ft.get("code", "—"); ja = ft.get("ja", "—"); desc = ft.get("description", "")
        conf = {"HIGH": "🟢 HIGH", "MID": "🟡 MID", "NONE": "⚪ NONE"}.get(ft.get("confidence", ""), "")
        st.markdown(f"""
        <div style="background:var(--surface);border:1px solid var(--border);padding:0.9rem 1.1rem;margin-bottom:0.8rem">
          <div style="font-size:0.65rem;letter-spacing:1.5px;color:var(--text-2);text-transform:uppercase">財務タイプ（DB分類）</div>
          <div style="font-size:1.05rem;font-weight:700;color:var(--cyan);margin-top:0.3rem">{ja} <span style="font-size:0.7rem;color:var(--text-3)">({code})</span></div>
          <div style="font-size:0.8rem;color:var(--text-2);margin-top:0.3rem">{desc}</div>
          <div style="font-size:0.7rem;color:var(--text-3);margin-top:0.3rem">信頼度: {conf}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    if has_sector:
        st.markdown("##### 📊 セクター相対評価（V4）")
        def _rel(key):
            s = sector_rel.get(key)
            return f"{s:.0f}pt" if s is not None else "—"
        st.markdown(_build_table(["指標", "実測値（vs 中央値）", "相対スコア"], [
            ("PER（相対）",       sector_rel.get("per_vs_median", "—"),       _rel("per_rel_score")),
            ("PBR（相対）",       sector_rel.get("pbr_vs_median", "—"),       _rel("pbr_rel_score")),
            ("EV/EBITDA（相対）", sector_rel.get("ev_ebitda_vs_median", "—"), _rel("ev_ebitda_rel_score")),
        ]), unsafe_allow_html=True)
        st.caption("スコア目安：100pt＝かなり割安 / 50pt＝中央値水準 / 0pt＝かなり割高")

        sv      = sector_rel.get("sector_v_score")
        per_rel = sector_rel.get("per_rel_score")
        pbr_rel = sector_rel.get("pbr_rel_score")
        ev_rel  = sector_rel.get("ev_ebitda_rel_score")
        if sv is not None:
            if sv >= 80:   diag = f"{sector_display}セクター内でかなり割安。買いやすい水準。"
            elif sv >= 65: diag = f"{sector_display}セクター内でやや割安。中央値を下回っており妥当圏。"
            elif sv >= 50: diag = f"{sector_display}セクター内で中央値水準。"
            elif sv >= 35: diag = f"{sector_display}セクター内でやや割高。注意が必要。"
            else:          diag = f"{sector_display}セクター内でかなり割高。"
            notes = []
            if per_rel is not None and per_rel >= 75: notes.append("PERは割安")
            if pbr_rel is not None and pbr_rel >= 75: notes.append("PBRは割安")
            if ev_rel  is not None and ev_rel  >= 75: notes.append("EV/EBITDAは割安")
            if per_rel is not None and per_rel <= 25: notes.append("PERは割高圏")
            if pbr_rel is not None and pbr_rel <= 25: notes.append("PBRは割高圏")
            if notes: diag += f"（{' / '.join(notes)}）"
            st.info(f"📊 セクター診断　{diag}")

    st.markdown("##### 📋 絶対評価（V1〜V3）")

    def eval_per(x):
        if x is None: return "—"
        lo, hi = (18, 40) if is_us else (12, 30)
        return "✓ 割安" if x < lo else ("△ 割高" if x > hi else "")
    def eval_pbr(x):
        if x is None: return "—"
        lo, hi = (2.0, 8.0) if is_us else (1.0, 3.0)
        return "✓ 資産割安" if x < lo else ("△ 割高" if x > hi else "")
    def eval_dy(x):
        if x is None: return "—"
        lo = 2.0 if is_us else 3.0
        return "✓ 高配当" if x >= lo else ""
    def eval_ev(x):
        if x is None: return "—"
        lo, hi = (12, 30) if is_us else (8, 20)
        return "✓ 割安" if x < lo else ("△ 割高" if x > hi else "")

    rows = [
        ("PER（実績）", _fmt_x(per),       eval_per(per)),
        ("予想 PER",    _fmt_x(per_fwd),   eval_per(per_fwd)),
        ("PBR",         _fmt_x(pbr),       eval_pbr(pbr)),
        ("EV/EBITDA",   _fmt_x(ev_ebitda), eval_ev(ev_ebitda)),
        ("配当利回り",  _fmt_pct(dy),      eval_dy(dy)),
    ]
    table_html = '<table class="cyb-table"><thead><tr><th>指標</th><th style="text-align:right">値</th><th style="text-align:right">評価</th></tr></thead><tbody>'
    for label, val, ev in rows:
        badge = f'<span class="ev-badge">{ev}</span>' if ev and ev not in ("—", "") else ""
        table_html += f'<tr><td>{label}</td><td class="td-right">{val}</td><td class="td-right">{badge}</td></tr>'
    table_html += '</tbody></table>'
    st.markdown(table_html, unsafe_allow_html=True)
    mkt_note = "米国株基準（S&P500水準）" if is_us else "日本株基準（東証水準）"
    st.caption(f"Vスコアはバリュエーションの目安。{mkt_note}で評価。")

    st.markdown("---")
    with st.expander("📖 財務タイプ辞典（全分類の解説）"):
        all_types = get_all_types_for_display()
        if all_types:
            for t in all_types:
                if t["sample_count"] == 0: continue
                is_this  = ft.get("matched") and ft.get("code") == t["code"]
                highlight = "🔍 **この銘柄の分類**  " if is_this else ""
                per_m = f"{t['per_median']:.1f}x"    if t["per_median"]             else "—"
                pbr_m = f"{t['pbr_median']:.2f}x"    if t["pbr_median"]             else "—"
                roe_m = f"{t['roe_median']*100:.1f}%" if t["roe_median"] is not None else "—"
                opm_m = f"{t['operating_margin_median']*100:.1f}%" if t["operating_margin_median"] is not None else "—"
                st.markdown(f"**{highlight}{t['ja']}** `{t['code']}`  \n{t['description']}  \n📊 中央値 — PER {per_m} / PBR {pbr_m} / ROE {roe_m} / 営業利益率 {opm_m} （n={t['sample_count']}）\n")
        else:
            st.info("財務タイプDBが読み込まれていません。")


# ─── タブ: QVT ────────────────────────────────────────────────────

def render_qvt_tab(tech):
    q   = float(tech["q_score"])
    v   = float(tech["v_score"])
    t   = float(tech["t_score"])
    qvt = float(tech["qvt_score"])

    corr = st.session_state.get("q_correction_result")
    q_show   = float(corr.get("q_corrected", q))   if corr else q
    qvt_show = float(corr.get("qvt_corrected", qvt)) if corr else qvt

    col1, col2, col3 = st.columns(3)
    if corr:
        col1.metric("Q（補正後）", f"{q_show:.1f}", delta=f"{q_show - q:+.1f}")
    else:
        col1.metric("Q（質）", f"{q:.1f}")
    col2.metric("V（値札）",       f"{v:.1f}")
    col3.metric("T（タイミング）", f"{t:.1f}")

    st.markdown("---")
    color = _color_score(qvt_show)
    msg   = ("総合的に非常に魅力的（主力候補）"          if qvt_show >= 70
             else "買い検討レベル。押し目を慎重に狙いたい" if qvt_show >= 60
             else "悪くないが他候補との比較推奨"           if qvt_show >= 50
             else "テーマ性が強くないなら見送りも選択肢")
    star  = "⭐⭐⭐" if qvt_show >= 71.05 else "⭐⭐" if qvt_show >= 65.35 else "⭐" if qvt_show >= 59.64 else ""

    st.markdown(f"""
    <div class="cyb-score-card" style="padding:1.5rem;border-color:{color};box-shadow:0 0 20px {color}55;">
      <div class="cyb-score-label">QVT 総合スコア</div>
      <div class="cyb-score-value" style="color:{color};font-size:3.5rem;text-shadow:0 0 20px {color}">{qvt_show:.1f}</div>
      <div class="cyb-score-max">/ 100</div>
      <div style="font-size:1.2rem;margin-top:.5rem">{star}</div>
      <div style="font-size:.8rem;color:#6aaabb;margin-top:.5rem;font-family:Share Tech Mono,monospace">&gt; {msg}</div>
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


# ─── タブ: Defensive ─────────────────────────────────────────────

_DEFENSIVE_METRIC_LABELS = [
    "① MA固り比率", "② 最大下方乖離", "③ 52w安値/200MA",
    "④ 最大DD", "⑤ 下方Vol", "⑥ 出来高下方圧力",
]
_DEFENSIVE_RADAR_LABELS = [
    "① MA\n固り比率", "② 最大\n下方乖離", "③ 52w安値\n/200MA",
    "④ 最大\nDD", "⑤ 下方\nVol", "⑥ 出来高\n下方圧力",
]


def _build_defensive_metric_frame(tech):
    rows = []
    raw  = tech.get("d_raw") or {}
    for idx, label in enumerate(_DEFENSIVE_METRIC_LABELS, start=1):
        def_val = tech.get("def6" if idx == 6 else f"def{idx}")
        rank    = tech.get("def6_rank" if idx == 6 else f"def{idx}_rank")
        raw_key = [
            "①_below_ma_ratio", "②_max_neg_dev", "③_52w_low_vs_ma",
            "④_max_drawdown", "⑤_downside_vol", "⑥_vol_pressure",
        ][idx - 1]
        raw_val  = raw.get(raw_key)
        raw_disp = _fmt_optional_float(raw_val, 3) if idx == 6 else _fmt_optional_pct_from_ratio(raw_val)
        rows.append({
            "パラメータ": label,
            "ランク":   rank or "—",
            "スコア":   None if def_val is None else round(float(def_val), 3),
            "ローデータ": raw_disp,
        })
    return pd.DataFrame(rows)


def _render_defensive_radar(tech):
    values = [tech.get(f"def{i}") for i in range(1, 6)] + [tech.get("def6")]
    if any(v is None for v in values):
        st.info("Dスコアのレーダーチャートに必要なデータが不足しています。")
        return

    n      = len(values)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)

    def _polygon_points(series_name, radii):
        rows = []
        for idx, radius in enumerate(radii):
            angle = angles[idx]
            rows.append({
                "series": series_name, "order": idx,
                "label": _DEFENSIVE_RADAR_LABELS[idx],
                "x": float(radius * np.cos(angle)),
                "y": float(radius * np.sin(angle)),
            })
        rows.append(rows[0] | {"order": n})
        return rows

    value_rows = _polygon_points("Ticker", [float(v) for v in values])
    bm_rows    = _polygon_points("BM=0.5", [0.5] * n)
    grid_rows  = []
    for radius in (0.25, 0.5, 0.75, 1.0):
        gr = _polygon_points(f"grid_{radius}", [radius] * n)
        grid_rows.extend(gr)

    grid_df = pd.DataFrame(grid_rows)
    val_df  = pd.DataFrame(value_rows)
    bm_df   = pd.DataFrame(bm_rows)

    grid_layer = alt.Chart(grid_df).mark_line(color="#00f3ff22", strokeWidth=0.8).encode(
        x=alt.X("x:Q", axis=None), y=alt.Y("y:Q", axis=None), order="order:O",
        detail="series:N",
    )
    val_layer = alt.Chart(val_df).mark_line(color="#00ff88", strokeWidth=2).encode(
        x="x:Q", y="y:Q", order="order:O",
    )
    bm_layer = alt.Chart(bm_df).mark_line(color="#ff005566", strokeWidth=1.5, strokeDash=[4, 4]).encode(
        x="x:Q", y="y:Q", order="order:O",
    )
    label_df = val_df[val_df["order"] < n].copy()
    label_layer = alt.Chart(label_df).mark_text(
        color="#00f3ff", fontSize=9, fontWeight="bold",
    ).encode(
        x=alt.X("x:Q"), y=alt.Y("y:Q"),
        text="label:N",
    )
    chart = (grid_layer + bm_layer + val_layer + label_layer).properties(
        height=280,
        background="transparent",
    ).configure_view(stroke=None)
    
    st.altair_chart(chart, use_container_width=True)
    
def _render_close_vs_ma_chart(tech):
    detail = tech.get("d_detail") or {}
    price_df = tech.get("d_price_df")
    ma = detail.get("ma")

    if price_df is None or ma is None or price_df.empty:
        st.info("終値 vs 200MA チャートに必要なデータが不足しています。")
        return

    close_df = price_df[["Close"]].copy()
    close_df["MA200"] = ma.reindex(close_df.index)

    close_df = (
        close_df
        .dropna(subset=["Close", "MA200"])
        .reset_index()
    )

    # index名をDateに統一
    if "index" in close_df.columns:
        close_df = close_df.rename(columns={"index": "Date"})

    base = alt.Chart(close_df).transform_fold(
        ["Close", "MA200"],
        as_=["series", "value"]
    )

    lines = base.mark_line().encode(
        x=alt.X("Date:T", title=None),
        y=alt.Y("value:Q", title="価格"),
        color=alt.Color(
            "series:N",
            scale=alt.Scale(
                domain=["Close", "MA200"],
                range=["#00f3ff", "#f5c542"]
            ),
            legend=alt.Legend(title=None)
        ),
    ).properties(
        height=280,
        background="transparent"
    )

    st.altair_chart(lines, use_container_width=True)

def _render_volume_pressure_boxplot(tech):
    detail    = tech.get("d_detail") or {}
    vol_ratio = detail.get("vol_ratio")
    down_mask = detail.get("down_mask")
    if vol_ratio is None or down_mask is None:
        st.info("出来高倍率箱ひげ図に必要なデータが不足しています。")
        return

    vr = vol_ratio.dropna()
    mask = down_mask.reindex(vr.index).fillna(False).astype(bool)

    if vr.empty:
        st.info("出来高倍率箱ひげ図に必要なデータが不足しています。")
        return

    clip_upper = float(vr.quantile(0.99))
    hist_df = pd.DataFrame({
        "Type": np.where(mask, "下落日", "上昇・横ばい日"),
        "VolumeRatio": vr.clip(upper=clip_upper).values,
    })

    type_domain = ["上昇・横ばい日", "下落日"]
    type_range  = ["#00f3ff", "#ff0055"]

    base = alt.Chart(hist_df)

    box = base.mark_boxplot(
        extent="min-max",
        ticks=True
    ).encode(
        x=alt.X("Type:N", sort=type_domain),
        y=alt.Y("VolumeRatio:Q", title="出来高倍率"),
            axis=alt.Axis(
                labelColor="#e8f7ff",
                titleColor="#e8f7ff",
                gridColor="#3a4d66",   # 少し明るめ
                gridOpacity=0.55
                ),
        ),
        color=alt.Color(
            "Type:N",
            scale=alt.Scale(domain=type_domain, range=type_range),
            legend=None
        )
    ).properties(
        height=280,
        background="transparent"
    )

    st.altair_chart(box, use_container_width=True)

    pressure = (tech.get("d_raw") or {}).get("⑥_vol_pressure")
    n_down   = detail.get("n_down")
    st.caption(f"圧力={_fmt_optional_float(pressure, 3)} / 下落日数={n_down or 0}")


def _render_volume_pressure_histogram(tech):
    detail    = tech.get("d_detail") or {}
    vol_ratio = detail.get("vol_ratio")
    down_mask = detail.get("down_mask")
    if vol_ratio is None or down_mask is None:
        st.info("出来高倍率ヒストグラムに必要なデータが不足しています。")
        return

    vr   = vol_ratio.dropna()
    mask = down_mask.reindex(vr.index).fillna(False).astype(bool)
    clip_upper = float(vr.quantile(0.99))
    hist_df = pd.DataFrame({
        "Type":        np.where(mask, "下落日", "上昇・横ばい日"),
        "VolumeRatio": vr.clip(upper=clip_upper).values,
    })
    type_domain = ["上昇・横ばい日", "下落日"]
    type_range  = ["#00f3ff88", "#ff005588"]

    bars = alt.Chart(hist_df).mark_bar(opacity=0.65).encode(
        x=alt.X("VolumeRatio:Q", bin=alt.Bin(maxbins=30), title="出来高倍率（当日 / 20日MA）"),
        y=alt.Y("count():Q", title="日数"),
        color=alt.Color("Type:N", scale=alt.Scale(domain=type_domain, range=type_range), legend=None),
        tooltip=["Type:N", alt.Tooltip("count():Q", title="件数")],
    )
    bm_line = alt.Chart(pd.DataFrame({"x": [1.0]})).mark_rule(
        color="#f5c542", strokeDash=[6, 4], strokeWidth=1.5,
    ).encode(x=alt.X("x:Q"))
    chart = (bars + bm_line).properties(height=280, background="transparent")
    st.altair_chart(chart, use_container_width=True)

    pressure = (tech.get("d_raw") or {}).get("⑥_vol_pressure")
    n_down   = detail.get("n_down")
    st.caption(f"圧力={_fmt_optional_float(pressure, 3)} / 下落日数={n_down or 0}　　破線=BM(1.0)")


def render_defensive_tab(tech):
    defensive_score = tech.get("defensive_score")
    bm_label  = tech.get("bm_label") or "—"
    bm_ticker = tech.get("bm_ticker") or "—"
    grade     = tech.get("d_grade") or "—"
    base_grade  = grade[0] if grade else "—"
    grade_label = DEFENSIVE_RANK_LABELS.get(base_grade, "—")

    top_col1, top_col2 = st.columns(2)
    score_text = "—" if defensive_score is None else f"{float(defensive_score):.3f}"
    top_col1.metric("価格ディフェンシブ度", grade or "—")
    if grade and grade != "—":
        top_col1.markdown(f"""
        <div style="margin-top:-8px;color:#00f3ff;font-size:1.05rem;font-weight:600;
                    text-shadow:0 0 6px #00f3ff">{grade_label}</div>""",
        unsafe_allow_html=True)
    top_col2.metric("価格ディフェンシブスコア", score_text)
    st.caption(f"比較ベンチマーク: {bm_label} ({bm_ticker})")

    summary_comment = tech.get("d_comment_summary")
    detail_comment  = tech.get("d_comment_detail")
    if summary_comment: st.info(summary_comment)
    if detail_comment:  st.caption(detail_comment)

    metric_df = _build_defensive_metric_frame(tech)
    st.markdown("##### 6指標サマリー")
    st.dataframe(metric_df, use_container_width=True, hide_index=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("##### レーダーチャート")
        _render_defensive_radar(tech)
    with c2:
        st.markdown("##### 終値 vs 200MA")
        _render_close_vs_ma_chart(tech)

    left, right = st.columns(2)
    with left:
        st.markdown("##### 出来高倍率 箱ひげ図")
        _render_volume_pressure_boxplot(tech)
    with right:
        st.markdown("##### 出来高倍率 分布")
        _render_volume_pressure_histogram(tech)

    with st.expander("📘 Defensiveスコアの見方"):
        st.markdown("""
- **Defensive Score** は **高いほど価格耐性が高い**ことを示します。
- **Benchmark = 0.5** はベンチマーク並みの水準です。
- レーダーチャートは外側ほど防衛力が高く、破線がベンチマーク基準線です。
- 出来高圧力チャートは、下落日に出来高が偏っていないかを確認するための補助図です。
        """)


# ─── エントリーポイント ───────────────────────────────────────────

def run():
    """app/main.py から呼ばれるエントリーポイント。"""
    _setup_style()

    st.markdown("""
    <div style="font-family:'Orbitron',monospace;font-size:1.5rem;font-weight:900;
                color:#00f3ff;text-shadow:0 0 10px #00f3ff,0 0 20px #00f3ff;
                letter-spacing:3px;margin-bottom:0">
        check<span style="color:#ff0055">SIGNAL</span>
        <span style="font-size:0.7rem;color:#6aaabb;letter-spacing:2px"> CYBER v4</span>
    </div>
    <div style="font-size:0.62rem;letter-spacing:3px;color:#2a4a55;
                text-transform:uppercase;margin-bottom:1.2rem">
        買いシグナルチェッカー — 日本株 / 米国株対応
    </div>
    """, unsafe_allow_html=True)

    try:
        av_key = st.secrets.get("ALPHA_VANTAGE_API_KEY", None)
    except Exception:
        av_key = None

    if av_key:
        st.caption("✅ Alpha Vantage API キー設定済み（米国株ファンダメンタル対応）")
    else:
        st.info("ℹ️ 米国株のファンダメンタルを取得するには Streamlit Secrets に `ALPHA_VANTAGE_API_KEY` を設定してください。日本株は不要です。")

    user_input = st.text_input(
        label="ティッカーを入力",
        placeholder="例：7203　8306　AAPL　MSFT",
        label_visibility="collapsed",
    )
    search = st.button("⚡ 分析する", use_container_width=True)
    st.caption("4〜5桁の数字は自動で .T（東証）付与。米株はそのまま入力。")

    if not search and not user_input:
        return

    ticker = convert_ticker(user_input)
    if not ticker:
        st.info("ティッカーを入力すると結果が表示されます。")
        return

    output = build_analysis_output(
        ticker,
        spinner_messages={
            "fetch":    f"📥 {ticker} のデータを取得中…",
            "classify": "🔍 財務タイプを分類中…",
            "compute":  "🔢 指標を計算中…",
        },
    )
    if not output or output["tech"] is None:
        return

    base    = output["base"]
    tech    = output["tech"]
    summary = output["summary"]
    scores  = output["scores"]

    render_price_header(
        ticker,
        summary["company_name"],
        summary["close"],
        summary["previous_close"],
        summary["industry"],
        summary["sector"],
    )
    render_metrics_row(tech)
    render_qvt_cards(scores["q"], scores["v"], scores["t"], scores["qvt"])
    st.markdown("---")

    tab_t, tab_q, tab_v, tab_qvt, tab_d = st.tabs(
        ["⏰ タイミング", "🏢 質", "💰 値札", "🧮 総合", "🛡️ 価格耐性"]
    )
    with tab_t:   render_t_tab(tech)
    with tab_q:   render_q_tab(tech)
    with tab_v:   render_v_tab(tech)
    with tab_qvt: render_qvt_tab(tech)
    with tab_d:   render_defensive_tab(tech)

    if base.get("dividend_yield"):
        st.caption(f"予想配当利回り: **{base['dividend_yield']:.2f}%**")


# ─── 開発・テスト用実行ブロック ──────────────────────────────────

if __name__ == "__main__":
    st.set_page_config(page_title="checkSIGNALs Cyber", layout="wide")

    # テスト時はモジュールが未接続のため、シグナルカードのみ単体表示
    _setup_style()
    ui = CyberUI()

    st.markdown("""
    <div style="font-family:'Orbitron',monospace;font-size:1.5rem;font-weight:900;
                color:#00f3ff;text-shadow:0 0 10px #00f3ff,0 0 20px #00f3ff;letter-spacing:3px">
        check<span style="color:#ff0055">SIGNAL</span> CYBER v4
    </div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.header("Debug Console")
        test_symbol = st.text_input("Symbol", "USD/JPY")
        test_signal = st.radio("Signal State", ["WAITING", "HIGH", "LOW"])
        test_price  = st.text_input("Current Price", "150.452")
        test_power  = st.slider("Signal Power", 0, 100, 75)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        ui.render_signal_card(test_symbol, test_signal, test_price, test_power)
