# Day-trade
# 🏛️ Project Parliament — 開発ロードマップ

## プロジェクト概要

複数のAIサービス（Claude, ChatGPT, Gemini）がグループチャット上で仮想通貨チャートを分析・議論し、
稟議制度を通じて合意形成を行い、MEXC取引所でデイトレードを自動実行するWebサービス。

---

## 技術スタック

| レイヤー | 技術 | 用途 |
|---------|------|------|
| バックエンド | Python 3.11+ / Flask | Webサーバー、API統合 |
| リアルタイム通信 | Flask-SocketIO | AI間チャットのリアルタイム配信 |
| フロントエンド | HTML/CSS/JavaScript | UI（Teams風グループチャット） |
| AI API | Anthropic Claude API | 統括AI（議長・トレード執行） |
| AI API | OpenAI ChatGPT API | 議論AI×5体 |
| AI API | Google Gemini API | 議論AI×5体 |
| 取引所API | MEXC API | 仮想通貨取引の執行 |
| データベース | SQLite → PostgreSQL | 議事録・取引履歴の保存 |
| バージョン管理 | GitHub | ソースコード管理 |

---

## AI構成（11体）

```
┌─────────────────────────────────────────────────────┐
│                    Claude（統括AI）                    │
│         議長 / 最終判断 / トレード執行                   │
└─────────────────┬───────────────────┬───────────────┘
                  │                   │
    ┌─────────────▼──────┐  ┌────────▼─────────────┐
    │   ChatGPTチーム (5)   │  │   Geminiチーム (5)    │
    │                      │  │                      │
    │ 🟢 リーダー    ×1     │  │ 🟢 リーダー    ×1     │
    │ 🔵 ワーカー    ×2     │  │ 🔵 ワーカー    ×2     │
    │ 🔴 クリティック ×2     │  │ 🔴 クリティック ×2     │
    └──────────────────────┘  └──────────────────────┘
```

### AI ID体系

| AI ID | 名前 | サービス | 役割 | 投票権 |
|-------|------|---------|------|--------|
| claude_chair | Claude | Anthropic | 議長・統括 | ✅ |
| gpt_leader | GPTリーダー | OpenAI | 対話・まとめ | ✅ |
| gpt_worker_1 | GPT調査員A | OpenAI | 調査・提案 | ❌ |
| gpt_worker_2 | GPT調査員B | OpenAI | 調査・提案 | ❌ |
| gpt_critic_1 | GPT監査A | OpenAI | 監査・反証 | ❌ |
| gpt_critic_2 | GPT監査B | OpenAI | 監査・反証 | ❌ |
| gem_leader | Geminiリーダー | Google | 対話・まとめ | ✅ |
| gem_worker_1 | Gemini調査員A | Google | 調査・提案 | ❌ |
| gem_worker_2 | Gemini調査員B | Google | 調査・提案 | ❌ |
| gem_critic_1 | Gemini監査A | Google | 監査・反証 | ❌ |
| gem_critic_2 | Gemini監査B | Google | 監査・反証 | ❌ |

---

## 業務フロー（詳細）

```
Phase 1: 起動
  ユーザーが「全AIを起動」ボタンをクリック
  → 各AI APIへ接続テスト → ステータスをオンラインに更新

Phase 2: チャート共有 & 議論開始
  ユーザーがチャート画像をアップロード → 「議論を開始」ボタン
  → 全AIにチャート画像を配信
  → 各AIがMEXC APIで市場データを取得
  → 議論ラウンド開始

Phase 3: 議論ラウンド（繰り返し）
  3a. ワーカーが市場分析を提示
  3b. クリティックが反証・リスク指摘
  3c. リーダーが議論をまとめる
  3d. リーダーまたはClaudeが稟議書を提出可能

Phase 4: 稟議・投票
  4a. 稟議書が提出される
  4b. 投票権を持つ3者（Claude, GPTリーダー, Geminiリーダー）が投票
  4c. 提出者以外の全員が「賛成」→ Phase 5へ
  4d. 反対あり → 議論に戻る（Phase 3）

Phase 5: ブラッシュアップ
  5a. ワーカー全停止
  5b. 3リーダーで稟議書を精査・修正
  5c. 最終版をClaudeに提出

Phase 6: トレード実行
  6a. ClaudeがMEXC APIで注文実行
  6b. 監視タイマー開始（5分, 15分, 1時間, 4時間）
  6c. 各チェックポイントで利確/損切判定
  6d. 最大4時間で強制クローズ

Phase 7: 完了
  7a. 取引結果の表示
  7b. 稟議書のダウンロード
```

---

## 開発フェーズ（6段階）

### 🔵 Phase 1: プロジェクト基盤（Week 1-2）
**目標**: 開発環境・プロジェクト骨格の構築

- [ ] GitHub リポジトリ作成
- [ ] Python仮想環境 + requirements.txt
- [ ] Flask + Flask-SocketIO のセットアップ
- [ ] プロジェクトディレクトリ構成の確定
- [ ] 設定管理（.env / config.py）
- [ ] ロギング設定
- [ ] 既存HTML/CSSをFlaskテンプレートに統合

**成果物**: ブラウザでUIが表示され、WebSocketが繋がる状態

```
project-parliament/
├── app.py                  # Flaskアプリのエントリーポイント
├── config.py               # 設定管理
├── requirements.txt
├── .env                    # APIキー（Git管理外）
├── .gitignore
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
├── templates/
│   └── index.html
├── services/
│   ├── __init__.py
│   ├── ai_manager.py       # AI起動・管理
│   ├── claude_service.py    # Claude API
│   ├── openai_service.py    # OpenAI API
│   ├── gemini_service.py    # Gemini API
│   └── mexc_service.py      # MEXC API
├── core/
│   ├── __init__.py
│   ├── orchestrator.py      # 議論フロー制御
│   ├── proposal.py          # 稟議書の管理
│   ├── voting.py            # 投票ロジック
│   └── trade_executor.py    # トレード実行・監視
├── models/
│   ├── __init__.py
│   ├── ai_agent.py          # AIエージェントの定義
│   └── message.py           # メッセージモデル
├── utils/
│   ├── __init__.py
│   └── logger.py
└── tests/
    └── ...
```

---

### 🟢 Phase 2: AI API統合（Week 3-4）
**目標**: 3つのAI APIと正常に通信できる状態

- [ ] Anthropic Claude API 接続
- [ ] OpenAI ChatGPT API 接続（5インスタンスの管理）
- [ ] Google Gemini API 接続（5インスタンスの管理）
- [ ] 各AIの役割別システムプロンプト設計
- [ ] APIレスポンスの統一フォーマット
- [ ] エラーハンドリング・リトライロジック
- [ ] レート制限の管理

**各AIのシステムプロンプト設計ポイント**:

| 役割 | プロンプトの方向性 |
|------|------------------|
| ワーカー（調査） | 市場データの分析、テクニカル指標の算出、根拠の提示 |
| クリティック（監査） | リスクの指摘、反証データの提示、損失シナリオの検証 |
| リーダー（まとめ） | 議論の要約、稟議書の作成、チーム意見の統合 |
| Claude（議長） | 全体進行管理、最終判断、トレード執行指示 |

---

### 🟡 Phase 3: リアルタイムチャット（Week 5-6）
**目標**: AI同士がリアルタイムで議論するチャットUIの実装

- [ ] WebSocket経由のメッセージ配信
- [ ] AI発言の順序制御（オーケストレーター）
- [ ] タイピングインジケーター表示
- [ ] メッセージ種別の表示分け（通常/稟議書/システム）
- [ ] チャットの自動スクロール
- [ ] AIのオンライン/オフラインステータス管理

**メッセージのデータ構造**:
```python
{
    "type": "ai_message" | "system" | "proposal" | "vote",
    "ai_id": "gpt_leader",
    "ai_name": "GPTリーダー",
    "icon": "🤖",
    "avatar_color": "#10a37f",
    "content": "分析結果を報告します...",
    "timestamp": "2026-02-11T10:30:00",
    "metadata": {}  # 稟議書や投票データ
}
```

---

### 🟠 Phase 4: 稟議・投票システム（Week 7-8）
**目標**: 稟議書の提出・投票・ブラッシュアップの一連のフロー

- [ ] 稟議書のデータモデル設計
- [ ] リーダーによる稟議書提出ロジック
- [ ] 投票システム（賛成/反対 + 理由）
- [ ] 満場一致の判定ロジック
- [ ] ブラッシュアップフェーズの制御
- [ ] 右パネルへの稟議書表示・投票状況更新

**稟議書のデータ構造**:
```python
{
    "id": "proposal_001",
    "submitted_by": "gpt_leader",
    "timestamp": "2026-02-11T10:35:00",
    "strategy": "long",           # long / short
    "pair": "BTC/USDT",
    "entry_price": 95200,
    "take_profit": 98500,
    "stop_loss": 93800,
    "reasoning": "テクニカル・マクロの根拠...",
    "votes": {
        "claude_chair": {"vote": "support", "reason": "..."},
        "gpt_leader": null,  # 提出者は投票しない
        "gem_leader": {"vote": "support", "reason": "..."}
    },
    "status": "voting" | "approved" | "rejected" | "reviewing" | "finalized"
}
```

---

### 🔴 Phase 5: MEXC連携 & トレード実行（Week 9-10）
**目標**: 稟議書に基づいた自動トレードの実行と監視

- [ ] MEXC API認証・接続
- [ ] 市場データ取得（価格、出来高、指標）
- [ ] 注文実行（指値/成行）
- [ ] ポジション監視タイマー（5分/15分/1時間/4時間）
- [ ] 利確・損切ロジック
- [ ] 4時間の強制クローズ
- [ ] 取引結果のUI表示

**MEXC API エンドポイント**:
```
GET  /api/v3/ticker/price     # 現在価格
GET  /api/v3/klines           # ローソク足データ
POST /api/v3/order            # 注文作成
GET  /api/v3/openOrders       # オープン注文確認
DELETE /api/v3/order          # 注文キャンセル
GET  /api/v3/account          # 残高確認
```

---

### 🟣 Phase 6: 統合テスト & 仕上げ（Week 11-12）
**目標**: 全体フローの通しテストとバグ修正

- [ ] Phase 1→7 の一気通貫テスト
- [ ] エラーハンドリングの強化
- [ ] UIの細部調整
- [ ] ログ出力の整備
- [ ] README.md の整備
- [ ] デプロイ手順の文書化

---

## 拡張機能（Phase 7以降）

### 取引レポート自動生成
- 取引クローズ時に結果レポートをテキストファイルで保存
- 次回議論時にAIが過去レポートを参照材料として使用

### ダッシュボード
- API使用料の集計表示
- 取引の損益履歴グラフ
- 勝率・平均利益率などの統計情報

---

## セキュリティ注意事項

1. **APIキーは絶対にGitにコミットしない** → `.env` + `.gitignore`
2. **MEXC APIはIPホワイトリストを設定**
3. **初期段階ではMEXCのテストネットを使用**
4. **取引金額に上限を設定**（1回あたりの最大金額）
5. **ローカル実行のみ**（管理人1名の利用のため）

---

## 次のステップ

**Phase 1 から着手します。以下を順番に実施：**

1. GitHubリポジトリの初期設定
2. Flaskプロジェクトの基本構造を作成
3. 既存のHTML/CSSをFlaskテンプレートとして統合
4. WebSocket（Flask-SocketIO）の基本接続を確認
5. AI起動ボタンのモック動作を実装
