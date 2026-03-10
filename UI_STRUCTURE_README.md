# UI切り替え構成ガイド

## 新ディレクトリ構成

```
app/
├── main.py                  ← ★ エントリーポイント（このファイルに差し替え）
├── ui/
│   ├── __init__.py          ← 空ファイルでOK
│   ├── classic/
│   │   ├── __init__.py      ← 空ファイルでOK
│   │   └── main.py          ← 従来UI (ui_classic_main.py をリネーム)
│   └── magi/
│       ├── __init__.py      ← 空ファイルでOK
│       └── main.py          ← MAGIシステムUI (ui_magi_main.py をリネーム)
├── modules/                 ← 変更不要
├── data/                    ← 変更不要
└── __init__.py              ← 変更不要
```

## セットアップ手順

1. 既存の `app/main.py` を `app/main_backup.py` にリネーム（バックアップ）
2. `main_new.py` → `app/main.py` に配置
3. `app/ui/` ディレクトリを作成
4. `app/ui/__init__.py` を作成（空ファイル）
5. `app/ui/classic/` を作成 → `__init__.py`（空）と `ui_classic_main.py` → `main.py` に配置
6. `app/ui/magi/` を作成 → `__init__.py`（空）と `ui_magi_main.py` → `main.py` に配置

## 将来UIを追加する方法

### Step 1: ディレクトリ作成
```
app/ui/neo/
├── __init__.py   ← 空ファイル
└── main.py       ← run() 関数を実装
```

### Step 2: run() 関数の実装
```python
# app/ui/neo/main.py の最小構成
import streamlit as st

def run():
    """app/main.py から呼ばれるエントリーポイント。"""
    st.title("NEO DASHBOARD")
    # ... UIを実装
```

### Step 3: レジストリに1行追加
`app/main.py` の `UI_REGISTRY` に追記するだけ:
```python
UI_REGISTRY = [
    { "key": "classic", ... },
    { "key": "magi",    ... },
    # ↓ これだけ追加
    {
        "key":    "neo",
        "name":   "NEO DASHBOARD",
        "icon":   "🌐",
        "desc":   "グラフ重視の次世代ダッシュボード。",
        "module": "ui.neo.main",
    },
]
```

## UI切り替え方法

### アプリ内から
- サイドバーに切り替えボタンが表示される
- 「🏠 セレクターに戻る」でUI選択画面に戻れる

### URLから直接指定
```
https://your-app.streamlit.app/?ui=classic
https://your-app.streamlit.app/?ui=magi
```

## 注意事項

- 各UIの `main.py` は必ず `run()` 関数を実装すること
- `modules/` や `data/` は共通なので変更不要
- `st.set_page_config()` はエントリーポイントの `app/main.py` で一元管理
  （各UIの `run()` 内では呼ばない）
- セッションステートは UIをまたいで共有されるので、キー名の衝突に注意
