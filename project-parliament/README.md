# 🏛️ Project Parliament

複数のAIサービス（Claude, ChatGPT, Gemini）がグループチャット上で仮想通貨チャートを分析・議論し、稟議制度を通じて合意形成を行い、MEXC取引所でデイトレードを自動実行するWebサービス。

## 📌 概要

| 項目 | 内容 |
|------|------|
| 利用者 | 管理人（1名） |
| 目的 | 仮想通貨の自動デイトレード |
| AI構成 | Claude×1 + ChatGPT×5 + Gemini×5 = 11体 |
| 取引所 | MEXC |
| UIイメージ | Microsoft Teams風グループチャット |

## 🚀 セットアップ

```bash
# 1. リポジトリをクローン
git clone https://github.com/YOUR_USERNAME/project-parliament.git
cd project-parliament

# 2. Python仮想環境を作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 依存パッケージをインストール
pip install -r requirements.txt

# 4. 環境変数を設定
cp .env.example .env
# .env を編集してAPIキーを入力

# 5. サーバーを起動
python app.py
```

ブラウザで `http://localhost:5000` にアクセスしてください。

## 📁 プロジェクト構成

```
project-parliament/
├── app.py                  # Flaskエントリーポイント
├── config.py               # 設定 & AIプロファイル定義
├── requirements.txt
├── .env.example            # 環境変数テンプレート
├── static/
│   ├── css/style.css       # UI スタイル
│   └── js/main.js          # フロントエンド制御
├── templates/
│   └── index.html          # メインページ
├── services/               # AI API & 取引所連携
├── core/                   # ビジネスロジック
├── models/                 # データモデル
└── utils/                  # ユーティリティ
```

## 🔧 開発状況

- [x] Phase 1: プロジェクト基盤
- [ ] Phase 2: AI API統合
- [ ] Phase 3: リアルタイムチャット
- [ ] Phase 4: 稟議・投票システム
- [ ] Phase 5: MEXC連携 & トレード
- [ ] Phase 6: 統合テスト

## ⚠️ 注意事項

- **APIキーは `.env` に保存し、絶対にGitにコミットしないでください**
- 開発中はMEXCの**テストネット**を使用してください
- 自動売買にはリスクが伴います。必ず余裕資金で運用してください
