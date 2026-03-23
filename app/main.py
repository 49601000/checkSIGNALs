"""
app/main.py — UI切り替えエントリーポイント

ディレクトリ構成:
app/
├── main.py               ← このファイル（エントリーポイント）
├── ui/
│   ├── __init__.py
│   ├── classic/          ← 従来UI (checkSIGNAL)
│   │   ├── __init__.py
│   │   └── main.py
│   └── magi/             ← MAGIシステムUI
│       ├── __init__.py
│       └── main.py
├── modules/              ← 共通モジュール（変更不要）
├── data/                 ← 共通データ（変更不要）
└── __init__.py

将来UIを追加する手順:
  1. app/ui/ 配下に新ディレクトリを作成（例: app/ui/neo/）
  2. __init__.py と main.py を追加
  3. main.py に run() 関数を実装（シグネチャは既存に倣う）
  4. 下記 UI_REGISTRY にエントリを1行追加するだけで切り替え画面に反映される
"""

import sys
import os

import streamlit as st

# ─── パス設定（app/ 配下から modules/ を参照できるようにする） ───
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)


# ─── UI設定の永続化（ファイルベース） ───────────────────────
# app/ と同ディレクトリに .ui_preference を保存する
# Streamlit Cloud / ローカル両方で動作する
_PREF_FILE = os.path.join(_APP_DIR, ".ui_preference")

def _load_ui_preference():
    """保存済みのUI設定を読み込む。未保存 or 無効なら None。"""
    try:
        if os.path.exists(_PREF_FILE):
            with open(_PREF_FILE, "r") as f:
                key = f.read().strip()
            # _UI_MAP はこの後に定義されるので遅延参照
            return key
    except Exception:
        pass
    return None

def _save_ui_preference(key):
    """UI設定をファイルに永続保存する。"""
    try:
        with open(_PREF_FILE, "w") as f:
            f.write(key)
    except Exception:
        pass  # 書き込み失敗しても動作継続


# ─── UI レジストリ ───────────────────────────────────────────
# 新しいUI skin を追加するときはここに1行追加するだけでOK
#
# キー      : URLクエリパラメータ (?ui=<key>) およびセッション管理に使用
# name      : 選択画面に表示する名前
# icon      : 選択画面に表示する絵文字
# desc      : 共通出力をどう見せるかの説明文
# module    : インポートするモジュールパス（app/ からの相対）
# ─────────────────────────────────────────────────────────────
UI_REGISTRY = [
    {
        "key":    "classic",
        "name":   "checkSIGNAL",
        "icon":   "📡",
        "desc":   "共通分析出力をシンプルモダンに見せる classic skin。視認性重視。",
        "module": "ui.classic.main",
    },
    {
        "key":    "magi",
        "name":   "MAGI SYSTEM",
        "icon":   "🔴",
        "desc":   "共通分析出力をMAGI風に見せる skin。六角形判定パネル・CRT演出。",
        "module": "ui.magi.main",
    },
    # ── 将来UIの追加例（コメントアウト） ──────────────────────
    # {
    #     "key":    "neo",
    #     "name":   "NEO DASHBOARD",
    #     "icon":   "🌐",
    #     "desc":   "グラフ重視の次世代ダッシュボード。",
    #     "module": "ui.neo.main",
    # },
]

# キー→エントリの辞書（内部使用）
_UI_MAP = {u["key"]: u for u in UI_REGISTRY}

# ─── セレクター画面のスタイル ────────────────────────────────
_SELECTOR_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=IBM+Plex+Mono:wght@500;600&display=swap');

:root {
    --bg:      #0d0d0d;
    --surface: #141414;
    --border:  #2a2a2a;
    --accent:  #ff6600;
    --text:    #e0e0e0;
    --dim:     #888;
}

html, body, [class*="css"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'IBM Plex Mono', monospace;
}
.stApp, section.main, .block-container {
    background-color: var(--bg) !important;
}
section[data-testid="stSidebar"] { display: none; }

.sel-header {
    font-family: 'Orbitron', monospace;
    font-size: 1.05rem;
    font-weight: 900;
    color: var(--accent);
    letter-spacing: 4px;
    text-align: center;
    padding: 8px;
    border: 2px solid var(--accent);
    background: rgba(255,102,0,0.07);
    margin-bottom: 1.2rem;
    text-shadow: 0 0 12px rgba(255,102,0,0.5);
}
.sel-sub {
    font-size: 0.6rem;
    color: var(--dim);
    letter-spacing: 3px;
    text-align: center;
    margin-bottom: 1.5rem;
}
.sel-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    padding: 1rem 1.1rem;
    margin-bottom: 0.6rem;
    cursor: pointer;
    transition: border-color 0.2s, background 0.2s;
}
.sel-card:hover {
    border-color: var(--accent);
    background: rgba(255,102,0,0.06);
}
.sel-card-name {
    font-family: 'Orbitron', monospace;
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--accent);
    letter-spacing: 2px;
    margin-bottom: 0.3rem;
}
.sel-card-desc {
    font-size: 0.7rem;
    color: var(--dim);
    line-height: 1.5;
}
.sel-footer {
    font-size: 0.58rem;
    color: #444;
    text-align: center;
    letter-spacing: 2px;
    margin-top: 1.5rem;
}
div[data-testid="stButton"] > button {
    background: transparent !important;
    border: 1px solid var(--border) !important;
    border-left: 3px solid var(--accent) !important;
    color: var(--text) !important;
    border-radius: 0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.85rem !important;
    text-align: left !important;
    padding: 0.8rem 1rem !important;
    height: auto !important;
    line-height: 1.5 !important;
    white-space: pre-wrap !important;
    transition: background 0.2s !important;
}
div[data-testid="stButton"] > button:hover {
    background: rgba(255,102,0,0.08) !important;
    border-left-color: var(--accent) !important;
    color: var(--accent) !important;
}
</style>
"""


def _load_ui_module(module_path: str):
    """動的インポート。失敗時は None を返す。"""
    import importlib
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        st.error(f"UIモジュールの読み込みに失敗しました: `{module_path}`\n\n{e}")
        return None


def render_selector():
    """UI選択画面を描画し、選択されたキーを返す（未選択時は None）。"""
    st.markdown(_SELECTOR_CSS, unsafe_allow_html=True)
    st.markdown('<div class="sel-header">▶ SELECT SKIN ◀</div>', unsafe_allow_html=True)
    st.markdown('<div class="sel-sub">CHECKSIGNAL — SHARED ANALYSIS OUTPUT + SELECTABLE UI SKINS</div>', unsafe_allow_html=True)

    selected_key = None
    for ui in UI_REGISTRY:
        label = f"{ui['icon']}  {ui['name']}\n{ui['desc']}"
        if st.button(label, key=f"sel_{ui['key']}", use_container_width=True):
            selected_key = ui["key"]

    st.markdown('<div class="sel-footer">■ MORE UI SKINS CAN BE ADDED TO app/ui/ ■</div>', unsafe_allow_html=True)
    return selected_key


def main():
    # ── セッション: 選択済みUIキーを保持（初回は保存済み設定を読み込む） ──
    if "ui_key" not in st.session_state:
        saved = _load_ui_preference()
        # 保存済みキーが有効なUIか確認してからセット
        st.session_state["ui_key"] = saved if (saved and saved in _UI_MAP) else None

    # ── URLクエリパラメータによる直接指定（?ui=magi など） ──
    try:
        params = st.query_params
        url_ui = params.get("ui", None)
        if url_ui and url_ui in _UI_MAP:
            st.session_state["ui_key"] = url_ui
    except Exception:
        pass

    current_key = st.session_state.get("ui_key")

    # ── UI未選択 → セレクター表示 ──
    if current_key is None:
        chosen = render_selector()
        if chosen:
            st.session_state["ui_key"] = chosen
            _save_ui_preference(chosen)  # ← 選択を永続保存
            st.rerun()
        return

    # ── UI選択済み → 対応モジュールを動的ロードして run() 実行 ──
    ui_entry = _UI_MAP.get(current_key)
    if ui_entry is None:
        st.error(f"不明なUIキー: {current_key}")
        st.session_state["ui_key"] = None
        st.rerun()
        return

    mod = _load_ui_module(ui_entry["module"])
    if mod is None:
        # ロード失敗時はセレクターに戻す
        if st.button("← セレクターに戻る"):
            st.session_state["ui_key"] = None
            st.rerun()
        return

    # ── サイドバーにUI切り替えボタンを追加（折りたたみ可） ──
    with st.sidebar:
        st.markdown(f"**現在のskin: {ui_entry['icon']} {ui_entry['name']}**")
        st.markdown("---")
        st.markdown("**skin を切り替える**")
        for ui in UI_REGISTRY:
            if ui["key"] == current_key:
                continue  # 現在選択中は表示しない
            if st.button(f"{ui['icon']} {ui['name']}", key=f"sw_{ui['key']}", use_container_width=True):
                st.session_state["ui_key"] = ui["key"]
                _save_ui_preference(ui["key"])  # ← 切り替えを永続保存
                st.rerun()
        st.markdown("---")
        if st.button("🏠 セレクターに戻る", use_container_width=True):
            st.session_state["ui_key"] = None
            _save_ui_preference("")   # ← 保存済み設定をクリア
            st.rerun()

    # ── 実際のUIを実行 ──
    mod.run()


if __name__ == "__main__":
    main()
