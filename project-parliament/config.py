"""
Project Parliament - 設定管理
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """アプリケーション設定"""

    # Flask
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # AI API Keys
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

    # MEXC Exchange
    MEXC_API_KEY = os.getenv("MEXC_API_KEY", "")
    MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY", "")
    MEXC_USE_TESTNET = os.getenv("MEXC_USE_TESTNET", "true").lower() == "true"

    # Trading Safety
    MAX_TRADE_AMOUNT = float(os.getenv("MAX_TRADE_AMOUNT", "100"))
    MAX_LEVERAGE = int(os.getenv("MAX_LEVERAGE", "5"))

    # Screening
    SCREENING_TOP_N = int(os.getenv("SCREENING_TOP_N", "10"))
    SCREENING_MIN_VOLUME = float(os.getenv("SCREENING_MIN_VOLUME", "100000"))

    # Monitoring
    MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL", "30"))
    TRAILING_STOP_TRIGGER = float(os.getenv("TRAILING_STOP_TRIGGER", "0.02"))
    TRAILING_STOP_DISTANCE = float(os.getenv("TRAILING_STOP_DISTANCE", "0.01"))
    PARTIAL_TP_RATIO = float(os.getenv("PARTIAL_TP_RATIO", "0.5"))
    PARTIAL_TP_TRIGGER = float(os.getenv("PARTIAL_TP_TRIGGER", "0.5"))


# ============================================================
# AIプロファイル定義（9）
# ============================================================
AI_PROFILES = {
    # --- Claude（統括AI / 議長） ---
    "claude_chair": {
        "name": "Claude",
        "service": "anthropic",
        "role": "chair",           # 議長
        "role_label": "統括AI",
        "icon": "🧠",
        "avatar_color": "#d97706",
        "can_vote": True,
        "can_propose": True,
        "description": "議論の進行管理、最終判断、トレード執行を担当",
    },

    # --- ChatGPTチーム（5体） ---
    "gpt_leader": {
        "name": "GPTリーダー",
        "service": "openai",
        "role": "leader",
        "role_label": "対話・まとめ役",
        "icon": "🤖",
        "avatar_color": "#10a37f",
        "can_vote": True,
        "can_propose": True,
        "description": "ChatGPTチームの議論をまとめ、稟議書を作成する",
    },
    "gpt_worker_1": {
        "name": "GPT調査員A",
        "service": "openai",
        "role": "worker",
        "role_label": "調査・提案役",
        "icon": "🔍",
        "avatar_color": "#059669",
        "can_vote": False,
        "can_propose": False,
        "description": "テクニカル分析、市場データの調査を担当",
    },
    "gpt_worker_2": {
        "name": "GPT調査員B",
        "service": "openai",
        "role": "worker",
        "role_label": "調査・提案役",
        "icon": "📊",
        "avatar_color": "#0d9488",
        "can_vote": False,
        "can_propose": False,
        "description": "ファンダメンタル分析、マクロ経済の調査を担当",
    },
    "gpt_critic_1": {
        "name": "GPT監査A",
        "service": "openai",
        "role": "critic",
        "role_label": "監査・反証役",
        "icon": "⚖️",
        "avatar_color": "#dc2626",
        "can_vote": False,
        "can_propose": False,
        "description": "リスク評価、損失シナリオの検証を担当",
    },
    "gpt_critic_2": {
        "name": "GPT監査B",
        "service": "openai",
        "role": "critic",
        "role_label": "監査・反証役",
        "icon": "🛡️",
        "avatar_color": "#e11d48",
        "can_vote": False,
        "can_propose": False,
        "description": "過去データとの整合性検証、反証提示を担当",
    },

    # --- Geminiチーム（3体） ---
    "gem_leader": {
        "name": "Geminiリーダー",
        "service": "gemini",
        "role": "leader",
        "role_label": "対話・まとめ役",
        "icon": "💎",
        "avatar_color": "#4285f4",
        "can_vote": True,
        "can_propose": True,
        "description": "Geminiチームの議論をまとめ、稟議書を作成する",
    },
    "gem_worker": {
        "name": "Gemini調査員",
        "service": "gemini",
        "role": "worker",
        "role_label": "調査役",
        "icon": "🔬",
        "avatar_color": "#2563eb",
        "can_vote": False,
        "can_propose": False,
        "description": "オンチェーンデータ分析、出来高解析、市場調査を担当",
    },
    "gem_proposer": {
        "name": "Gemini提案役",
        "service": "gemini",
        "role": "proposer",
        "role_label": "提案役",
        "icon": "📈",
        "avatar_color": "#7c3aed",
        "can_vote": False,
        "can_propose": True,
        "description": "トレード戦略の立案、エントリー/利確/損切ポイントの提案を担当",
    },
}
