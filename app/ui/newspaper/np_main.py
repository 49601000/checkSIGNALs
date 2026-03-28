"""
app/ui/newspaper/np_main.py — FT寄り newspaper skin

コンセプト:
- Financial Times 寄りのクラシック × モダン
- オフホワイト背景 / 黒文字 / ダークグリーン強調
- 紙っぽい微細ノイズをCSSで薄く追加
- 情報量は削りすぎず、記事レイアウトに再構成
"""

from datetime import datetime
import re
import textwrap
import streamlit as st

from modules.data_fetch import convert_ticker
from ui.output_structure import build_analysis_output
from dict.dic1 import DEFENSIVE_RANK_LABELS


# ─────────────────────────────────────────────────────────────
# Style
# ─────────────────────────────────────────────────────────────

def _setup_style():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@400;500;700&display=swap');

        :root {
            --bg: #f3efe6;
            --paper: #f6f1e8;
            --ink: #111111;
            --muted: #5e5a54;
            --rule: #cfc7b8;
            --green: #244b3c;
            --red: #8f2d2d;
            --soft-green: #e6eee9;
            --soft-red: #f2e5e3;
        }

        html, body, [class*="css"] {
            font-family: "Georgia", "Times New Roman", "Noto Serif JP", serif !important;
            background: var(--bg) !important;
            color: var(--ink) !important;
        }

        .stApp, .stApp > div, section.main, .block-container {
            background: var(--bg) !important;
        }

        .main > div {
            padding-top: 1.1rem;
            padding-bottom: 3rem;
        }

        div[data-testid="stTextInput"] input {
            background: #fbf8f1 !important;
            color: var(--ink) !important;
            border: 1px solid var(--rule) !important;
            border-radius: 0 !important;
            font-family: "Georgia", "Times New Roman", "Noto Serif JP", serif !important;
            font-size: 1rem !important;
            height: 2.8rem !important;
        }

        div[data-testid="stButton"] > button {
            background: #fbf8f1 !important;
            color: var(--ink) !important;
            border: 1px solid var(--ink) !important;
            border-radius: 0 !important;
            font-family: "Georgia", "Times New Roman", "Noto Serif JP", serif !important;
            font-weight: 700 !important;
            letter-spacing: 0.04em !important;
            height: 2.8rem !important;
        }

        div[data-testid="stButton"] > button:hover {
            background: #efe9dc !important;
            color: var(--ink) !important;
            border-color: var(--ink) !important;
        }

        .np-shell {
            position: relative;
            overflow: hidden;
            background:
                radial-gradient(circle at 18% 12%, rgba(0,0,0,0.018), transparent 24%),
                radial-gradient(circle at 82% 28%, rgba(0,0,0,0.014), transparent 22%),
                radial-gradient(circle at 48% 82%, rgba(255,255,255,0.16), transparent 28%),
                linear-gradient(180deg, rgba(255,255,255,0.12), rgba(0,0,0,0.02)),
                var(--paper);
            border: 1px solid var(--rule);
            box-shadow:
                0 1px 0 rgba(0,0,0,0.03),
                0 10px 30px rgba(0,0,0,0.05);
            padding: 28px 30px 26px 30px;
            margin-top: 0.8rem;
            color: var(--ink) !important;
            opacity: 1 !important;
            filter: none !important;
        }

        .np-shell::before {
            content: "";
            position: absolute;
            inset: 0;
            pointer-events: none;
            opacity: 0.05;
            mix-blend-mode: multiply;
            background-image: url("data:image/svg+xml;utf8,\
<svg xmlns='http://www.w3.org/2000/svg' width='140' height='140' viewBox='0 0 140 140'>\
<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/></filter>\
<rect width='140' height='140' filter='url(%23n)' opacity='0.32'/>\
</svg>");
            background-size: 180px 180px;
        }

        .np-shell,
        .np-shell * {
            color: var(--ink);
        }

        .np-masthead,
        .np-alert,
        .np-headline,
        .np-subhed,
        .np-summary,
        .np-columns,
        .np-note,
        .np-footer {
            opacity: 1 !important;
            filter: none !important;
        }

        .np-masthead {
            text-align: center;
            border-bottom: 1px solid var(--rule);
            padding-bottom: 12px;
            margin-bottom: 14px;
            position: relative;
            z-index: 1;
        }

        .np-brand {
            font-size: 0.74rem;
            letter-spacing: 0.30em;
            text-transform: uppercase;
            color: var(--muted) !important;
            -webkit-text-fill-color: var(--muted) !important;
            font-weight: 700;
        }

        .np-date {
            margin-top: 6px;
            font-size: 0.85rem;
            color: var(--muted) !important;
            -webkit-text-fill-color: var(--muted) !important;
        }

        .np-alert {
            position: relative;
            z-index: 1;
            margin: 0 0 16px 0;
            padding: 8px 12px;
            border-top: 2px solid var(--green);
            border-bottom: 1px solid var(--rule);
            color: var(--green) !important;
            -webkit-text-fill-color: var(--green) !important;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            text-align: center;
        }

        .np-headline {
            position: relative;
            z-index: 1;
            text-align: center;
            font-size: 2.15rem;
            line-height: 1.15;
            letter-spacing: -0.01em;
            font-weight: 700;
            margin: 16px 0 10px 0;
            color: var(--ink) !important;
            -webkit-text-fill-color: var(--ink) !important;
        }

        .np-subhed {
            position: relative;
            z-index: 1;
            text-align: center;
            color: var(--green) !important;
            -webkit-text-fill-color: var(--green) !important;
            font-size: 0.96rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 16px;
        }

        .np-summary {
            position: relative;
            z-index: 1;
            border-top: 1px solid var(--rule);
            border-bottom: 1px solid var(--rule);
            padding: 10px 0;
            margin-bottom: 18px;
            text-align: center;
            font-size: 0.96rem;
            line-height: 1.7;
            color: var(--ink) !important;
            -webkit-text-fill-color: var(--ink) !important;
        }

        .np-summary strong {
            font-weight: 700;
            color: var(--ink) !important;
            -webkit-text-fill-color: var(--ink) !important;
        }

        .np-columns {
            position: relative;
            z-index: 1;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 28px;
            align-items: start;
            color: var(--ink) !important;
            -webkit-text-fill-color: var(--ink) !important;
        }

        .np-section {
            border-top: 1px solid var(--ink);
            padding-top: 8px;
            margin-bottom: 18px;
            color: var(--ink) !important;
            -webkit-text-fill-color: var(--ink) !important;
        }

        .np-section-title {
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            margin-bottom: 8px;
            color: var(--ink) !important;
            -webkit-text-fill-color: var(--ink) !important;
        }

        .np-kv {
            display: grid;
            grid-template-columns: 1.15fr 0.85fr;
            gap: 8px;
            padding: 5px 0;
            border-bottom: 1px solid rgba(17,17,17,0.07);
        }

        .np-k {
            color: var(--muted) !important;
            -webkit-text-fill-color: var(--muted) !important;
            font-size: 0.9rem;
        }

        .np-v {
            text-align: right;
            font-variant-numeric: tabular-nums;
            font-weight: 600;
            font-size: 0.94rem;
            color: var(--ink) !important;
            -webkit-text-fill-color: var(--ink) !important;
        }

        .np-note {
            position: relative;
            z-index: 1;
            margin-top: 10px;
            padding-top: 10px;
            border-top: 2px solid var(--ink);
            color: var(--ink) !important;
            -webkit-text-fill-color: var(--ink) !important;
        }

        .np-note-title {
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            margin-bottom: 6px;
            color: var(--ink) !important;
            -webkit-text-fill-color: var(--ink) !important;
        }

        .np-note-body {
            font-size: 0.94rem;
            line-height: 1.85;
            color: var(--ink) !important;
            -webkit-text-fill-color: var(--ink) !important;
            white-space: pre-line;
        }

        .np-footer {
            position: relative;
            z-index: 1;
            border-top: 1px solid var(--rule);
            margin-top: 14px;
            padding-top: 10px;
            text-align: center;
            font-size: 0.78rem;
            color: var(--muted) !important;
            -webkit-text-fill-color: var(--muted) !important;
            letter-spacing: 0.06em;
        }

        @media (max-width: 900px) {
            .np-shell {
                padding: 22px 18px 20px 18px;
            }
            .np-columns {
                grid-template-columns: 1fr;
                gap: 10px;
            }
            .np-headline {
                font-size: 1.7rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _fmt_num(x, digits=2):
    if x is None:
        return "—"
    return f"{float(x):.{digits}f}"


def _fmt_pct(x, digits=1):
    if x is None:
        return "—"
    return f"{float(x):.{digits}f}%"


def _fmt_x(x, digits=2):
    if x is None:
        return "—"
    return f"{float(x):.{digits}f}x"


def _safe(s):
    if s is None:
        return "—"
    return str(s)


def _market_date_label():
    return datetime.now().strftime("%B %d, %Y")


def _signal_label(tech):
    txt = tech.get("signal_text") or "NO CLEAR SIGNAL"
    return str(txt).upper()


def _entryfitness_label(qvt_score):
    if qvt_score is None:
        return "データ不足のため不明"
    if qvt_score >= 70:
        return "魅力的な水準"
    if qvt_score >= 60:
        return "悪くない水準"
    if qvt_score >= 50:
        return "どちらともいえない"
    return "推奨しない"


def _defensive_grade_label(grade):
    if not grade:
        return "—"
    base_grade = str(grade)[0]
    return DEFENSIVE_RANK_LABELS.get(base_grade, "—")


def _summary_risk_text(tech):
    d_score = tech.get("defensive_score")
    raw = tech.get("d_raw") or {}
    pressure = raw.get("⑥_vol_pressure")

    # 長期耐性のラベル決定
    if d_score is not None and d_score >= 0.70:
        long_text = "長期は高"
    elif d_score is not None and d_score >= 0.50:
        long_text = "長期で指数並"
    elif d_score is not None:
        long_text = "長期で低"
    else:
        long_text = "長期のデータ不足"

    # 短期リスク優先
    if pressure is not None and pressure >= 1.10:
        return f"短期の圧力強／{long_text}"
     # 短期に特段の圧力なし
    if d_score is not None:
        return f"短期は中立／{long_text}"
    return "短期：評価不可／長期：データ不足"

def _clean_company_name(summary, ticker):
    return re.sub(
        r"[（(]\d{4,5}[）)]$",
        "",
        _safe(summary.get("company_name", ticker)).rstrip("の").strip()
    ).strip()


def _kv(label, value):
    return f"""
    <div class="np-kv">
      <div class="np-k">{label}</div>
      <div class="np-v">{value}</div>
    </div>
    """


def _section(title, items_html):
    return f"""
    <div class="np-section">
      <div class="np-section-title">{title}</div>
      {items_html}
    </div>
    """


# ─────────────────────────────────────────────────────────────
# Render blocks
# ─────────────────────────────────────────────────────────────

def _render_header(summary, tech, scores, ticker):
    company_name = _clean_company_name(summary, ticker)
    qvt = scores.get("qvt")
    entryfitness = _entryfitness_label(qvt)
    risk_text = _summary_risk_text(tech)
    signal_text = _signal_label(tech)

    html = textwrap.dedent(f"""
        <div class="np-shell">
          <div class="np-masthead">
            <div class="np-brand">CHECKSIGNAL DAILY</div>
            <div class="np-date">{_market_date_label()}</div>
          </div>
          <div class="np-alert">SIGNAL NAVIGATOR</div>
          <div class="np-headline">{company_name} ({ticker})</div>
          <div class="np-subhed">{signal_text}</div>
          <div class="np-summary">
            <strong>エントリー適合度:</strong> {entryfitness}<br>
            <strong>下落耐性:</strong> {risk_text}<br>
            <strong>QVT スコア:</strong> {_fmt_num(qvt, 1)} / 100<br>
          </div>
        </div>
    """).strip()

    st.markdown(html, unsafe_allow_html=True)
def _render_columns(summary, tech, scores):
    q_items = "".join([
        _kv("Q Score", _fmt_num(scores.get("q"), 1)),
        _kv("ROE", _fmt_pct(tech.get("roe"))),
        _kv("ROA", _fmt_pct(tech.get("roa"))),
        _kv("Operating Margin", _fmt_pct(tech.get("operating_margin"))),
        _kv("Equity Ratio", _fmt_pct(tech.get("equity_ratio"))),
        _kv("D/E Ratio", _fmt_x(tech.get("de_ratio"))),
    ])

    v_items = "".join([
        _kv("V Score", _fmt_num(scores.get("v"), 1)),
        _kv("PER", _fmt_x(tech.get("per"))),
        _kv("Forward PER", _fmt_x(tech.get("per_fwd"))),
        _kv("PBR", _fmt_x(tech.get("pbr"))),
        _kv("EV / EBITDA", _fmt_x(tech.get("ev_ebitda"))),
        _kv("Dividend Yield", _fmt_pct(summary.get("dividend_yield"))),
    ])

    t_items = "".join([
        _kv("T Score", _fmt_num(scores.get("t"), 1)),
        _kv("Signal", _safe(tech.get("signal_text"))),
        _kv("RSI (14)", _fmt_num(tech.get("rsi"), 1)),
        _kv("25MA", _fmt_num(tech.get("ma_25"), 2)),
        _kv("50MA", _fmt_num(tech.get("ma_50"), 2)),
        _kv("52W Range", f"{_fmt_num(tech.get('low_52w'), 2)} – {_fmt_num(tech.get('high_52w'), 2)}"),
    ])

    grade = tech.get("d_grade")
    d_label = _defensive_grade_label(grade)
    d_items = "".join([
        _kv("Defensive Grade", _safe(grade)),
        _kv("Interpretation", _safe(d_label)),
        _kv("Defensive Score", _fmt_num(tech.get("defensive_score"), 3)),
        _kv("MA Cluster Ratio", _fmt_num(tech.get("def1"), 3)),
        _kv("Max Drawdown", _fmt_num(tech.get("def4"), 3)),
        _kv("Volume Pressure", _fmt_num(tech.get("def6"), 3)),
    ])

    left_html = _section("Quality", q_items) + _section("Valuation", v_items)
    right_html = _section("Timing", t_items) + _section("Defensive", d_items)

    st.markdown(
        f"""
        <div class="np-shell">
          <div class="np-columns">
            <div>{left_html}</div>
            <div>{right_html}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def _render_note_and_footer(summary, tech, ticker):
    ft = tech.get("financial_type", {})
    ft_ja = ft.get("ja", "—")
    ft_code = ft.get("code", "—")
    ft_desc = ft.get("description", "")

    sector = tech.get("sector") or "—"
    sector_rel = tech.get("sector_rel_scores", {})
    sv = sector_rel.get("sector_v_score")
    pbr_rel = sector_rel.get("pbr_rel_score")

    if sv is not None:
        if sv >= 80:
            sector_comment = "セクター内でかなり割安。"
        elif sv >= 65:
            sector_comment = "セクター内でやや割安。"
        elif sv >= 50:
            sector_comment = "セクター内で中央値水準。"
        elif sv >= 35:
            sector_comment = "セクター内でやや割高。"
        else:
            sector_comment = "セクター内でかなり割高。割高圏にある。"
    else:
        sector_comment = "セクター診断データは限定的。"

    extra_note = "（PBRは割高圏）" if pbr_rel is not None and pbr_rel <= 25 else ""

    valuation_block = (
        f"バリエーション ー 財務タイプは {ft_ja} ({ft_code})。\n"
        f"{ft_desc}"
        f"セクター診断では{sector}セクター内で{sector_comment}{extra_note}"
    )

    summary_comment = tech.get("d_comment_summary") or ""
    detail_comment = tech.get("d_comment_detail") or ""
    defensive_block = (
        f"価格のディフェンシブ性 ー {summary_comment}\n"
        f"{detail_comment}"
    )

    timing_text = tech.get("signal_text") or "—"

    full_note = (
        f"タイミング ー {timing_text}\n\n"
        f"{valuation_block}\n\n"
        f"{defensive_block}"
    )

    html = textwrap.dedent(f"""
        <div class="np-shell">
          <div class="np-note">
            <div class="np-note-title">Analyst Note</div>
            <div class="np-note-body">{full_note}</div>
          </div>
          <div class="np-footer">
            DATA SOURCE: CHECKSIGNAL SYSTEM &nbsp;|&nbsp; TICKER: {ticker}
          </div>
        </div>
    """).strip()

    st.markdown(html, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

def run():
    _setup_style()

    st.markdown(
        """
        <div style="text-align:center; margin-bottom:0.8rem; color:#5e5a54; font-size:0.82rem; letter-spacing:0.10em;">
          FT-INSPIRED NEWSPAPER SKIN
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        av_key = st.secrets.get("ALPHA_VANTAGE_API_KEY", None)
    except Exception:
        av_key = None

    if av_key:
        st.caption("Alpha Vantage API キー設定済み")
    else:
        st.caption("米国株ファンダメンタルは Alpha Vantage API キー未設定の場合、一部制限があります。")

    user_input = st.text_input(
        label="ティッカーを入力",
        placeholder="例：7203　8306　AAPL　MSFT",
        label_visibility="collapsed",
    )
    search = st.button("ANALYZE", use_container_width=True)

    st.caption("4〜5桁の数字は自動で .T を付与。米国株はそのまま入力。")

    if not search and not user_input:
        return

    ticker = convert_ticker(user_input)
    if not ticker:
        st.info("ティッカーを入力すると結果が表示されます。")
        return

    output = build_analysis_output(
        ticker,
        spinner_messages={
            "fetch": f"{ticker} のデータを取得中…",
            "classify": "財務タイプを分類中…",
            "compute": "指標を計算中…",
        },
    )

    if not output or output.get("tech") is None:
        return

    tech = output["tech"]
    summary = output["summary"]
    scores = output["scores"]

    _render_header(summary, tech, scores, ticker)
    _render_columns(summary, tech, scores)
    _render_note_and_footer(summary, tech, ticker)
