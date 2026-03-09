# checkSIGNAL v3 — 設計変更サマリー

## 変更ファイル一覧

| ファイル | v2 → v3 |
|---|---|
| `modules/pattern_db.py` | ★ **新規追加**。財務特性DBの読込・分類・相対スコア計算 |
| `modules/data_fetch.py` | 取得項目追加（operating_margin / de_ratio / interest_coverage / ev_ebitda） |
| `modules/q_logic.py`    | 全面改訂。3サブスコア構造 + ノックアウト条件 |
| `modules/valuation.py`  | 全面改訂。4サブスコア構造 + EV/EBITDA + セクター相対 |
| `modules/indicators.py` | q_logic / valuation を正式呼び出しに切替。新規引数追加 |
| `modules/q_correction.py` | 変更なし（互換維持） |
| `modules/t_logic.py`    | 変更なし |
| `main.py`               | pattern_db 呼び出し追加、render_q_tab/render_v_tab 拡張 |

---

## Q スコア構造（v3）

```
Q = Q1 × 0.50 + Q3 × 0.50

Q1（収益性）:  ROE / ROA / 営業利益率
Q3（財務健全性）: 自己資本比率 / D/Eレシオ / インタレストカバレッジ

ノックアウト: 以下いずれかで -15pt
  - インタレストカバレッジ < 1.5x
  - 自己資本比率 < 10%
  - 営業利益率 < 0%（営業赤字）
```

### v2 との比較

| 旧 | 新 | 変更内容 |
|---|---|---|
| ROE / ROA / 自己資本比率の線形マッピング | Q1+Q3の分離 | ROEのレバレッジ依存問題を緩和 |
| ノックアウトなし | ノックアウト条件3つ | 重大欠陥銘柄の誤評価防止 |
| q_logic.py 未使用 | q_logic.py を正式呼び出し | 二重実装を解消 |

---

## V スコア構造（v3）

```
【セクター相対あり（日本株・DB分類済み）】
V = V1×0.30 + V2×0.20 + V3×0.10 + V4×0.40

【セクター相対なし（米国株・UNK）】
V = V1×0.45 + V2×0.30 + V3×0.25

V1（伝統的割安）:  PER / PBR（絶対評価）
V2（CF系評価）:    EV/EBITDA（絶対評価）
V3（株主還元）:    配当利回り（補助因子・ウェイト抑制）
V4（セクター相対）: pattern_db の中央値との比較
```

### セクター相対スコア（V4）の計算

- ratio = actual / sector_median
- ratio ≒ 0.5 → 100点（かなり割安）
- ratio ≒ 1.0 → 50点（中央値水準）
- ratio ≒ 2.0 → 0点（かなり割高）

---

## pattern_db.py の設計

### 役割
1. `load_pattern_db()` — CSV を st.cache_data でキャッシュ
2. `classify_ticker(ticker, db)` — ティッカーから財務タイプを判定
3. `calc_sector_relative_scores(ft, per, pbr, ev_ebitda)` — セクター相対スコア計算
4. `get_all_types_for_display(db)` — 財務タイプ辞典用のデータ返却

### CSV パス設定
```
デフォルト: app/data/pattern_db_latest.csv
環境変数: PATTERN_DB_PATH で上書き可能
```

### 米国株の扱い
- ticker_list は `.T` 形式（東証銘柄）のみ
- 米国株は classify_ticker が `matched=False` を返す
- `has_sector=False` となり V4 を除いたリウェイトで V スコア計算

---

## UI 変更点

### Q タブ
- Q1/Q3 サブスコアを表示
- ノックアウト警告を st.warning で表示
- 収益性テーブル（ROE/ROA/営業利益率）
- 財務健全性テーブル（自己資本比率/D-E/インタレストカバレッジ）
- セクター補正（q_correction）は v2 互換で維持

### V タブ
- V1〜V4 サブスコアを表示（V4 は日本株のみ）
- 財務タイプバッジ（分類コード・説明・信頼度）
- セクター相対テーブル（vs 中央値テキスト + 相対スコア）
- EV/EBITDA を絶対評価テーブルに追加
- 財務タイプ辞典 expander（全 24 分類の解説 + 中央値）

---

## data_fetch.py 追加取得項目

| 項目 | 日本株（IRBANK） | 日本株（yfinance補完） | 米国株（Alpha Vantage） | 米国株（yfinance補完） |
|---|---|---|---|---|
| operating_margin | △ 難しい | ✓ operatingMargins | ✓ OperatingMarginTTM | ✓ |
| interest_coverage | — | ✓ ebit/interestExpense で計算 | — | ✓ |
| de_ratio | — | ✓ debtToEquity | — | ✓ |
| ev_ebitda | — | ✓ enterpriseValue/ebitda | ✓ EVToEBITDA | ✓ |

---

## 将来拡張メモ

- **Q2（安定性）**: EPS の標準偏差・ROE のブレを計算するには複数年データが必要。
  yfinance の `earnings_history` や IRBANK の時系列 API が使えれば実装可能。
- **G（成長）因子**: revenue_growth / earnings_growth は pattern_db に既に中央値あり。
  `data_fetch` で revenue_growth を取得できれば QGVT 化の準備が整う。
- **セクター集中アラート**: 同一 financial_type_code の銘柄を複数保有している場合に
  警告する機能は、ポートフォリオ機能と合わせて実装するのが現実的。
