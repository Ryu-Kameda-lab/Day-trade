"""
設定モジュール - 環境変数からAPIキー・各種設定値を読み込む
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# プロジェクトルートの .env を読み込む
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


# ── MEXC API ──
MEXC_API_KEY = os.getenv("MEXC_API_KEY", "")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY", "")

# ── OpenAI API ──
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── Anthropic (Claude) API ──
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Google (Gemini) API ──
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# ── Discord Webhook ──
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


def is_configured(key_name: str) -> bool:
    """指定されたAPIキーが設定されているかチェック"""
    value = globals().get(key_name, "")
    return bool(value) and not value.startswith("your_")


def get_available_ai_models() -> list[str]:
    """設定済みのAIモデル名リストを返す"""
    models = []
    if is_configured("OPENAI_API_KEY"):
        models.append("openai")
    if is_configured("ANTHROPIC_API_KEY"):
        models.append("anthropic")
    if is_configured("GOOGLE_API_KEY"):
        models.append("google")
    return models
