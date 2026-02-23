# checkSIGNAL v2 — Streamlit Cloud デプロイ版

iPhone対応・日本株 / 米国株対応（IRBANK + Alpha Vantage + yfinance）

## ファイル構成

```
checkSIGNAL/
├── streamlit_app.py        # エントリポイント
├── requirements.txt        # 依存ライブラリ
├── .streamlit/
│   └── config.toml         # ダークテーマ設定
└── app/
    ├── main.py             # UI（iPhone最適化）
    └── modules/
        ├── data_fetch.py   # データ取得（IRBANK / Alpha Vantage / yfinance）
        ├── indicators.py   # テクニカル指標計算
        ├── t_logic.py      # タイミングロジック
        ├── q_logic.py      # 質スコアロジック
        ├── q_correction.py # セクター補正
        └── valuation.py    # バリュエーションスコア
```

## Streamlit Cloud デプロイ手順

### 1. GitHub にプッシュ

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOUR_NAME/checkSIGNAL.git
git push -u origin main
```

### 2. Streamlit Cloud でデプロイ

1. https://share.streamlit.io にアクセス
2. "New app" → リポジトリ・ブランチ・Main file (`streamlit_app.py`) を指定
3. **"Advanced settings" → "Secrets"** に以下を入力：

```toml
ALPHA_VANTAGE_API_KEY = "あなたのAPIキー"
```

> Alpha Vantage 無料キーの取得: https://www.alphavantage.co/support/#api-key

4. "Deploy" をクリック → 数分でURLが発行される

## 対応銘柄と取得元

| 入力例 | ファンダ取得元 |
|---|---|
| `7203`（トヨタ） | IRBANK スクレイピング |
| `8306.T`（三菱UFJ） | IRBANK スクレイピング |
| `AAPL`（Apple） | Alpha Vantage OVERVIEW API |
| `MSFT`（Microsoft） | Alpha Vantage OVERVIEW API |

※ Alpha Vantage キー未設定でも米国株のテクニカル分析は動作します。
　 ファンダメンタル（PER/ROE等）は yfinance からの取得にフォールバックします。

## ローカル動作確認

```bash
pip install -r requirements.txt
# .streamlit/secrets.toml を作成
echo 'ALPHA_VANTAGE_API_KEY = "YOUR_KEY"' > .streamlit/secrets.toml
streamlit run streamlit_app.py
```
