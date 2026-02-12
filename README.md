# Day-trade
# 🏛️ Project Parliament

複数のAIサービス（Claude, ChatGPT, Gemini）がグループチャット上で仮想通貨チャートを分析・議論し、**稟議制度**を通じて合意形成を行い、MEXC取引所でデイトレードを自動実行するWebサービス。

## 📌 プロジェクト概要

| 項目 | 内容 |
|------|------|
| 利用者 | 管理人（1名） |
| 目的 | 仮想通貨の自動デイトレード |
| AI構成 | Claude ×1 + ChatGPT ×5 + Gemini ×3 = **9体** |
| 取引所 | MEXC（Spot API v3） |
| UIイメージ | Microsoft Teams風グループチャット |
| バックエンド | Flask + Flask-SocketIO（gevent） |
| フロントエンド | Vanilla HTML/CSS/JS + Socket.IO |

---

## 🏗️ システムアーキテクチャ

### 全体フロー

```
[ブラウザ UI]
    │
    │ WebSocket (Socket.IO)
    ▼
[app.py] ─────────────────────────────────────────────────
    │           │           │            │            │
    ▼           ▼           ▼            ▼            ▼
 Orchestrator TradeExecutor TradeReporter MarketScreener MEXCService
  (議論制御)   (注文+監視)   (事後分析)    (銘柄選定)      (API通信)
    │                                       │
    ▼                                       ▼
 AIManager ◄─── ClaudeService       TechnicalAnalyzer
                 OpenAIService        (RSI/MACD/EMA/BB)
                 GeminiService
```

### 処理フロー

```
1. AI起動 → 2. 市場スクリーニング → 3. AI議論（3ラウンド）
→ 4. 稟議書提出 → 5. 投票 → 6. ブラッシュアップ
→ 7. トレード実行 → 8. リアルタイム監視（30秒間隔）
→ 9. 決済 → 10. AI事後分析レポート生成
```

---

## 📁 ディレクトリ構成

```
project-parliament/
├── app.py                          # Flask エントリーポイント（ルート + WebSocket）
├── config.py                       # 設定管理 + AIプロファイル定義（9体）
├── requirements.txt                # Python 依存パッケージ
├── .env.example                    # 環境変数テンプレート
│
├── core/                           # ビジネスロジック層
│   ├── __init__.py
│   ├── orchestrator.py             # AI議論フロー制御（発言順・プロンプト構築・ラウンド管理）
│   ├── proposal.py                 # 稟議書ライフサイクル管理
│   ├── voting.py                   # 投票・合意形成ロジック
│   ├── trade_executor.py           # 注文実行 + リアルタイム監視 + TP/SL判定
│   └── trade_reporter.py           # AI事後分析レポート生成
│
├── services/                       # 外部サービス連携層
│   ├── __init__.py
│   ├── ai_manager.py               # 全AIエージェント統合管理
│   ├── claude_service.py           # Anthropic Claude API ラッパー
│   ├── openai_service.py           # OpenAI ChatGPT API ラッパー
│   ├── gemini_service.py           # Google Gemini API ラッパー
│   ├── mexc_service.py             # MEXC Spot API v3 ラッパー
│   ├── technical_analysis.py       # テクニカル分析エンジン（pandas + ta）
│   └── market_screener.py          # 市場スクリーニング（銘柄選定）
│
├── models/                         # データモデル層（dataclass）
│   ├── __init__.py
│   ├── ai_agent.py                 # AIAgent / AgentStatus
│   ├── message.py                  # Message / MessageType
│   ├── proposal.py                 # Proposal / Vote
│   ├── analysis.py                 # TechnicalIndicators / SymbolAnalysis
│   ├── trade.py                    # TradeRecord / PriceSnapshot
│   └── report.py                   # TradeReport
│
├── utils/                          # ユーティリティ
│   ├── __init__.py
│   └── logger.py                   # ロギング設定
│
├── templates/
│   └── index.html                  # メインページ（Jinja2テンプレート）
│
├── static/
│   ├── css/style.css               # UIスタイル
│   └── js/main.js                  # フロントエンド制御
│
├── tests/                          # テスト（未実装）
└── logs/                           # ログファイル出力先
```

---

## 🤖 AIエージェント構成

### 役割と権限

| ID | 名前 | サービス | 役割 | 投票権 | 提案権 | 担当 |
|----|------|---------|------|--------|--------|------|
| `claude_chair` | Claude | Anthropic | 議長 (chair) | ✅ | ✅ | 議論進行、最終判断、稟議書最終確定 |
| `gpt_leader` | GPTリーダー | OpenAI | リーダー (leader) | ✅ | ✅ | GPTチームまとめ、稟議書作成 |
| `gpt_worker_1` | GPT調査員A | OpenAI | 調査 (worker) | ❌ | ❌ | テクニカル分析、市場データ調査 |
| `gpt_worker_2` | GPT調査員B | OpenAI | 調査 (worker) | ❌ | ❌ | ファンダメンタル分析、マクロ経済 |
| `gpt_critic_1` | GPT監査A | OpenAI | 監査 (critic) | ❌ | ❌ | リスク評価、損失シナリオ検証 |
| `gpt_critic_2` | GPT監査B | OpenAI | 監査 (critic) | ❌ | ❌ | 過去データ整合性検証、反証 |
| `gem_leader` | Geminiリーダー | Google | リーダー (leader) | ✅ | ✅ | Geminiチームまとめ、稟議書作成 |
| `gem_worker` | Gemini調査員 | Google | 調査 (worker) | ❌ | ❌ | オンチェーン分析、出来高解析 |
| `gem_proposer` | Gemini提案役 | Google | 提案 (proposer) | ❌ | ✅ | トレード戦略立案、エントリー提案 |

### 議論の発言順

`config.py` の `AI_PROFILES` で定義。`orchestrator.py` の `SPEAKING_ORDER` がラウンドごとの発言順を制御。

---

## 📂 各ファイル詳細

### `app.py` — アプリケーションエントリーポイント

**責務**: Flask + Socket.IO の初期化、全サービスの紐付け、API ルートと WebSocket イベントハンドラの定義。

#### HTTP API ルート

| メソッド | パス | 機能 |
|---------|------|------|
| GET | `/` | メインページ表示 |
| GET | `/api/status` | アプリ状態取得 |
| GET | `/api/proposal/<id>` | 稟議書取得 |
| GET | `/api/trade-status` | 現在のトレード状態 |
| GET | `/api/screening` | 市場スクリーニング実行 |
| GET | `/api/trades` | トレード履歴一覧 |
| GET | `/api/reports` | レポート一覧 |
| GET | `/api/reports/<id>` | レポート詳細 |

#### WebSocket イベント（受信 / `socket.on` ハンドラ）

| イベント名 | 機能 |
|-----------|------|
| `activate_all_ai` | 全AIの接続テスト実行 |
| `start_discussion` | 市場スクリーニング → AI議論開始 |
| `submit_proposal` | 稟議書提出 |
| `cast_vote` | 投票 |
| `finalize_proposal` | 稟議書最終確定 |
| `execute_trade` | トレード実行 |
| `stop_discussion` | 議論強制終了 |

#### WebSocket イベント（送信 / `socketio.emit`）

| イベント名 | データ | 用途 |
|-----------|--------|------|
| `ai_status_change` | `{ai_id, status, name}` | AI接続状態変更通知 |
| `new_message` | メッセージ全文 | チャットメッセージ配信 |
| `phase_change` | `{phase}` | フェーズ変更通知 |
| `ai_speaking` | `{ai_id, speaking}` | AI発言中表示 |
| `proposal_submitted` | 稟議書データ | 稟議書提出通知 |
| `voting_update` | 投票状況 | 投票状況更新 |
| `proposal_finalized` | 確定稟議書 | 稟議書最終確定通知 |
| `trade_executed` | トレード情報 | トレード開始通知 |
| `trade_monitor_update` | ポジション状態 | リアルタイム監視データ（30秒毎） |
| `trade_partial_tp` | 部分利確データ | 部分利確通知 |
| `trade_closed` | 決済結果 | トレード終了通知 |
| `trade_report_generated` | レポート | AI分析レポート完成通知 |
| `error` | `{message}` | エラー通知 |
| `reset` | — | UI全体リセット |

---

### `config.py` — 設定管理

**責務**: 環境変数からの設定読み込みと AI プロファイル定義。

#### 設定項目

| カテゴリ | 変数名 | デフォルト | 説明 |
|---------|--------|-----------|------|
| Flask | `FLASK_SECRET_KEY` | `dev-secret-key` | セッション暗号化キー |
| Flask | `FLASK_DEBUG` | `false` | デバッグモード |
| AI | `ANTHROPIC_API_KEY` | — | Claude API キー |
| AI | `OPENAI_API_KEY` | — | ChatGPT API キー |
| AI | `GOOGLE_API_KEY` | — | Gemini API キー |
| MEXC | `MEXC_API_KEY` | — | MEXC API キー |
| MEXC | `MEXC_SECRET_KEY` | — | MEXC シークレットキー |
| MEXC | `MEXC_USE_TESTNET` | `true` | テストネット使用 |
| 取引 | `MAX_TRADE_AMOUNT` | `100` | 1回の最大取引額（USDT） |
| 取引 | `MAX_LEVERAGE` | `5` | 最大レバレッジ |
| スクリーニング | `SCREENING_TOP_N` | `10` | 上位N銘柄を分析 |
| スクリーニング | `SCREENING_MIN_VOLUME` | `100000` | 最小出来高フィルタ |
| 監視 | `MONITOR_INTERVAL` | `30` | 監視間隔（秒） |
| 監視 | `TRAILING_STOP_TRIGGER` | `0.02` | トレイリングストップ発動閾値（2%） |
| 監視 | `TRAILING_STOP_DISTANCE` | `0.01` | トレイリングストップ追跡距離（1%） |
| 監視 | `PARTIAL_TP_RATIO` | `0.5` | 部分利確の決済割合（50%） |
| 監視 | `PARTIAL_TP_TRIGGER` | `0.5` | 部分利確のTP到達率（50%） |

---

### `core/orchestrator.py` — 議論フロー制御

**責務**: AI間の議論ラウンド管理、発言順制御、プロンプト構築、稟議書生成指示。

**主要機能**:
- `start_discussion()`: 市場データ + スクリーニング結果 → AIプロンプト構築 → 3ラウンドの議論実行
- `_build_system_prompt()`: AI役割に応じたシステムプロンプト生成
- `_build_user_prompt()`: 市場データ＋過去発言を含むユーザープロンプト生成（テクニカル分析データ付き）
- `_create_final_proposal()`: 議長(Claude)に稟議書生成を指示 → パース

**リファクタリングポイント**:
- プロンプトテンプレートのハードコーディング → 外部ファイル or テンプレートエンジン化
- 発言順 `SPEAKING_ORDER` の動的変更対応
- ラウンド数の設定化

---

### `core/proposal.py` — 稟議書管理

**責務**: 稟議書のCRUD、ステータス遷移管理。

**ステータス遷移**: `draft` → `submitted` → `voting` → `brushup` → `finalized`

**主要メソッド**: `create()`, `submit()`, `start_brushup()`, `finalize()`, `get()`

---

### `core/voting.py` — 投票システム

**責務**: 投票の記録と合意形成判定。

**投票権者**: `claude_chair`, `gpt_leader`, `gem_leader` の3体
**判定ロジック**: 全投票者が投票完了後、賛成多数なら `approved`、それ以外は `rejected`

---

### `core/trade_executor.py` — トレード実行 + リアルタイム監視

**責務**: MEXC への注文送信、ポジションの 30 秒間隔監視、TP/SL 判定、トレイリングストップ、部分利確。

**主要機能**:

| 機能 | 説明 |
|------|------|
| `execute_trade()` | 稟議書に基づく指値注文を MEXC に送信 |
| `_monitor_position()` | 30秒ポーリングで現在価格を取得し判定 |
| トレイリングストップ | 2%利益到達で発動 → 最高値から1%追跡 |
| 部分利確 | TP距離50%到達で保有量の50%を成行決済 |
| テクニカル指標取得 | 各チェックで RSI / Volume Ratio を取得 |
| `close_position()` | 成行注文でポジション全決済 |
| クローズ後コールバック | `on_trade_closed` → `TradeReporter` に連携 |

**データモデル**: `TradeRecord`（`models/trade.py`）で全ライフサイクルを記録

---

### `core/trade_reporter.py` — 事後分析レポーター

**責務**: トレード終了後、テクニカル指標を再取得し、エントリー時と比較してAIにレポート生成を依頼。

**処理フロー**:
1. クローズ時の klines を取得 → テクニカル分析実行
2. エントリー時 vs クローズ時の指標差を構造化
3. Claude（議長AI）にレポート生成プロンプトを送信
4. AIが不可の場合はフォールバックの自動分析を実行
5. `TradeReport` モデルに格納し、WebSocket で配信

---

### `services/ai_manager.py` — AI統合管理

**責務**: 全 AI エージェントのライフサイクル管理（起動テスト・メッセージ送信・停止）。

**サービスマッピング**:
| サービス名 | クラス | API キー変数 |
|-----------|-------|-------------|
| `anthropic` | `ClaudeService` | `ANTHROPIC_API_KEY` |
| `openai` | `OpenAIService` | `OPENAI_API_KEY` |
| `gemini` | `GeminiService` | `GOOGLE_API_KEY` |

---

### `services/claude_service.py` / `openai_service.py` / `gemini_service.py`

**責務**: 各AI APIの呼び出しラッパー。統一インターフェース `send_message(messages, system_prompt, images)` を提供。

---

### `services/mexc_service.py` — MEXC API ラッパー

**責務**: MEXC Spot API v3 との通信。署名生成、リクエスト送信、データ取得。

**主要メソッド**:

| メソッド | 説明 |
|---------|------|
| `test_connection()` | API接続テスト |
| `get_ticker_price(symbol)` | 現在価格取得 |
| `get_klines(symbol, interval, limit)` | ローソク足データ取得 |
| `get_24hr_ticker(symbol)` | 24時間ティッカー |
| `get_order_book(symbol)` | 注文板取得 |
| `get_market_overview()` | USDT建て出来高上位ペア一覧 |
| `get_multi_timeframe_klines(symbol, timeframes)` | 複数時間足一括取得 |
| `get_recent_trades(symbol)` | 直近約定履歴 |
| `place_order(symbol, side, type, ...)` | 注文送信 |
| `get_open_orders(symbol)` | 未約定注文一覧 |
| `cancel_order(symbol, order_id)` | 注文キャンセル |
| `get_account_balance()` | 口座残高取得 |
| `get_order_status(symbol, order_id)` | 注文状態確認 |

**テストネット対応**: `MEXC_USE_TESTNET=true` で `https://api.mexc.com` → テストネットURL に切替

---

### `services/technical_analysis.py` — テクニカル分析エンジン

**責務**: ローソク足データから各種テクニカル指標を計算し、トレードシグナルを検出。

**依存ライブラリ**: `pandas`, `ta`

**計算指標**:

| 指標 | パラメータ | 用途 |
|------|-----------|------|
| RSI | 期間14 | 買われすぎ/売られすぎ判定 |
| MACD | 12, 26, 9 | トレンド方向・強さ |
| EMA | 20, 50 | 短期/中期トレンド |
| ボリンジャーバンド | 期間20, σ2 | ボラティリティ・反転 |
| ATR | 期間14 | ボラティリティ幅 |
| 出来高比率 | 直近20期間平均比 | 出来高の相対強度 |

**スコアリング（0-100点）**: RSI・MACD・EMA・出来高を重み付けしてスコア化。高スコア＝トレード機会の魅力度が高い。

**リファクタリングポイント**:
- スコアリングの重み付けを設定ファイルから読み込む仕組み
- カスタムインジケータの追加容易化（プラグイン方式）

---

### `services/market_screener.py` — 市場スクリーナー

**責務**: MEXC の出来高上位ペアに対してテクニカル分析を実行し、スコアランキングで候補銘柄を自動選定。

**処理フロー**:
1. `mexc_service.get_market_overview()` で USDT ペアの出来高上位を取得
2. 各ペアについて複数時間足（1h, 4h, 1d）の klines を取得
3. `TechnicalAnalyzer` でスコアリング
4. スコア上位N件を返却
5. AI議論用のフォーマット済みテキストを生成

---

### `models/` — データモデル

| ファイル | クラス | 説明 |
|---------|-------|------|
| `ai_agent.py` | `AIAgent`, `AgentStatus` | AIエージェントの状態管理 |
| `message.py` | `Message`, `MessageType` | チャットメッセージ構造 |
| `proposal.py` | `Proposal`, `Vote` | 稟議書・投票データ |
| `analysis.py` | `TechnicalIndicators`, `SymbolAnalysis`, `MultiTimeframeAnalysis` | テクニカル分析結果 |
| `trade.py` | `TradeRecord`, `PriceSnapshot` | トレード履歴・スナップショット |
| `report.py` | `TradeReport` | AI事後分析レポート |

---

## 🖥️ フロントエンド構成

### レイアウト（3カラム）

```
┌──────────┬──────────────────────┬─────────────┐
│ サイドバー │     チャットエリア     │   右パネル   │
│ (72px)   │    (メインコンテンツ)  │  (300px)    │
│          │                      │             │
│ AIアイコン│                      │ [稟議書]     │
│ +状態    │   吹き出し形式の      │ [ポジション]  │
│ インジケ  │   メッセージ表示      │ [レポート]   │
│ ータ     │                      │  ← タブ切替  │
│          ├──────────────────────┤             │
│          │ コントロールバー       │             │
│          │ (起動/開始/停止)      │             │
└──────────┴──────────────────────┴─────────────┘
```

### 右パネル 3タブ

| タブ | 内容 |
|------|------|
| 📋 稟議書 | 戦略・価格・根拠 + 投票ボード |
| 📊 ポジション | 現在価格・PnL・TP/SL・テクニカル指標・フラグ |
| 📑 レポート | クローズ後のAI分析レポートカード一覧 |

### WebSocket イベント処理（`main.js`）

ポジション監視は `trade_monitor_update` イベント（30秒ごと）で以下を更新:
- 現在価格 / 含み損益（色分け）
- TP距離 / SL距離
- RSI / 出来高比率 / 経過時間
- トレイリングストップ / 部分利確フラグ

---

## 🚀 セットアップ

```bash
# 1. リポジトリをクローン
git clone <repo-url>
cd project-parliament

# 2. Python仮想環境を作成・有効化
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3. 依存パッケージをインストール
pip install -r requirements.txt

# 4. 環境変数を設定
cp .env.example .env
# .env を編集してAPIキーを入力

# 5. サーバーを起動
python app.py
```

ブラウザで `http://localhost:5000` にアクセス。

---

## 🔧 依存ライブラリ

| パッケージ | バージョン | 用途 |
|-----------|-----------|------|
| `flask` | 3.1.0 | Web フレームワーク |
| `flask-socketio` | 5.5.1 | WebSocket 通信 |
| `python-dotenv` | 1.1.0 | 環境変数管理 |
| `gevent` / `gevent-websocket` | ≥24.2.1 | 非同期 WebSocket |
| `anthropic` | 0.43.0 | Claude API |
| `openai` | 1.59.2 | ChatGPT API |
| `google-generativeai` | 0.8.0 | Gemini API |
| `requests` | 2.32.3 | MEXC API HTTP通信 |
| `pandas` | ≥2.1.0 | テクニカル分析データ処理 |
| `ta` | ≥0.11.0 | テクニカル指標計算 |
| `python-dateutil` | 2.9.0 | 日付処理 |

---

## 🔄 開発状況

- [x] Phase 1: プロジェクト基盤（Flask, SocketIO, ディレクトリ構成）
- [x] Phase 2: AI API 統合（Claude, ChatGPT, Gemini サービス層）
- [x] Phase 3: リアルタイムチャット（WebSocket, メッセージUI）
- [x] Phase 4: 稟議・投票システム（提案→投票→ブラッシュアップ）
- [x] Phase 5: MEXC 連携 & トレード（注文実行・監視・決済）
- [x] Phase A: テクニカル分析基盤（RSI/MACD/EMA/BB/ATR）
- [x] Phase B: 市場スクリーニング & AI議論へのデータ統合
- [x] Phase C: ポジション管理高度化（30秒監視, トレイリングストップ, 部分利確）
- [x] Phase D: 事後分析 & AI レポート生成
- [x] Phase E: UI/フロントエンド拡張（タブ切替, 監視UI, レポートUI）
- [ ] Phase F: ユニットテスト & 統合テスト

---

## 🛠️ リファクタリング検討事項

### 優先度：高

| 箇所 | 課題 | 提案 |
|------|------|------|
| `app.py` | 537行で肥大化。ルート定義・WS処理・ビジネスロジックが混在 | Blueprint分割。WS処理をハンドラ層へ分離 |
| `orchestrator.py` | プロンプトのハードコーディング（441行） | プロンプトテンプレート外部化（YAML/Jinja2） |
| `trade_executor.py` | 429行。監視ループとビジネスロジックが同居 | 監視ロジックを別クラスに分離 |
| 状態管理 | `app_state` がグローバル辞書 | 状態管理クラスまたは Redis 導入 |

### 優先度：中

| 箇所 | 課題 | 提案 |
|------|------|------|
| エラーハンドリング | try/except が散在、統一的なエラー処理なし | カスタム例外クラス + 共通エラーハンドラ |
| テスト | テストファイルが空 | pytest + モック。特に `TechnicalAnalyzer` と `MarketScreener` |
| 型ヒント | 一部の関数で不足 | 全パブリックメソッドに型ヒント追記 |
| ログ | `logger.info/error` の粒度がまちまち | 構造化ログ（JSON形式）導入 |

### 優先度：低

| 箇所 | 課題 | 提案 |
|------|------|------|
| config.py | AIプロファイルがハードコード | YAML/JSON 外部ファイル化 |
| フロントエンド | Vanilla JS で状態管理が複雑化する可能性 | React/Vue 検討（規模次第） |
| DB | 全データがインメモリ | SQLite or PostgreSQL 永続化 |

---

## ⚠️ 注意事項

- **APIキーは `.env` に保存し、絶対にGitにコミットしないでください**
- 開発中はMEXCの **テストネット** を使用してください（`MEXC_USE_TESTNET=true`）
- 自動売買にはリスクが伴います。**必ず余裕資金で運用してください**
- 現在の実装は **MEXC Spot API** のみ対応。先物（Futures）は未対応

---

## 📝 ライセンス

プライベートプロジェクト。無断転載・再配布禁止。
