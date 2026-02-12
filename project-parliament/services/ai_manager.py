"""
AI Manager - 11体のAIエージェントの統合管理
各サービス（Claude / OpenAI / Gemini）のインスタンスを作成し、
起動・メッセージ送信・停止のライフサイクルを管理する。
"""
import logging

from config import AI_PROFILES, Config
from services.claude_service import ClaudeService
from services.openai_service import OpenAIService
from services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

# サービス名 -> (サービスクラス, config APIキー属性名) のマッピング
SERVICE_MAP = {
    "anthropic": (ClaudeService, "ANTHROPIC_API_KEY"),
    "openai": (OpenAIService, "OPENAI_API_KEY"),
    "gemini": (GeminiService, "GOOGLE_API_KEY"),
}


class AIManager:
    """全AIエージェントのライフサイクル管理"""

    def __init__(self, config=None):
        """
        Args:
            config: Config オブジェクト。None の場合は Config() を使用。
        """
        if config is None:
            config = Config()
        self.config = config
        self.profiles = AI_PROFILES
        self.agents = {}       # ai_id -> {"service": service_instance, "profile": profile, "online": bool}
        self._initialized = False
        self._init_agents()

    def _init_agents(self):
        """AI_PROFILES に基づき各サービスインスタンスを作成する。"""
        for ai_id, profile in self.profiles.items():
            service_name = profile["service"]
            if service_name not in SERVICE_MAP:
                logger.warning("不明なサービス '%s' (ai_id=%s) - スキップ", service_name, ai_id)
                continue

            service_cls, api_key_attr = SERVICE_MAP[service_name]
            api_key = getattr(self.config, api_key_attr, "")

            if not api_key:
                logger.info("%s (%s): APIキー未設定 - オフラインで登録", profile["name"], ai_id)

            service = service_cls(api_key=api_key)
            self.agents[ai_id] = {
                "service": service,
                "profile": profile,
                "online": False,
            }

    def activate_all(self) -> dict:
        """
        全AIエージェントの接続テストを実行し、結果を返す。

        Returns:
            {ai_id: {"status": "online"/"error", "name": "...", "error": "..."(任意)}}
        """
        results = {}
        for ai_id, agent in self.agents.items():
            profile = agent["profile"]
            service = agent["service"]
            try:
                success = service.test_connection()
                if success:
                    agent["online"] = True
                    results[ai_id] = {"status": "online", "name": profile["name"]}
                    logger.info("%s (%s): オンライン", profile["name"], ai_id)
                else:
                    agent["online"] = False
                    results[ai_id] = {"status": "error", "name": profile["name"], "error": "接続テスト失敗"}
                    logger.warning("%s (%s): 接続テスト失敗", profile["name"], ai_id)
            except Exception as e:
                agent["online"] = False
                results[ai_id] = {"status": "error", "name": profile["name"], "error": str(e)}
                logger.error("%s (%s): 起動エラー - %s", profile["name"], ai_id, e)

        self._initialized = True
        return results

    def send_message(self, ai_id: str, content: str, system_prompt: str = None, images: list = None) -> str:
        """
        指定AIにメッセージを送信してレスポンスを得る。

        Args:
            ai_id: AIエージェントID（例: "claude_chair", "gpt_leader"）
            content: 送信するメッセージテキスト
            system_prompt: システムプロンプト（任意）
            images: 画像データリスト（任意）
        Returns:
            レスポンステキスト。エラー時は None。
        """
        if ai_id not in self.agents:
            logger.error("不明なAI ID: %s", ai_id)
            return None

        agent = self.agents[ai_id]
        if not agent["online"]:
            logger.warning("%s (%s): オフライン - メッセージ送信スキップ", agent["profile"]["name"], ai_id)
            return None

        messages = [{"role": "user", "content": content}]
        return agent["service"].send_message(messages, system_prompt=system_prompt, images=images)

    def send_messages(self, ai_id: str, messages: list, system_prompt: str = None, images: list = None) -> str:
        """
        指定AIに会話履歴付きでメッセージを送信してレスポンスを得る。

        Args:
            ai_id: AIエージェントID
            messages: [{"role": "user"/"assistant", "content": "..."}]
            system_prompt: システムプロンプト（任意）
            images: 画像データリスト（任意）
        Returns:
            レスポンステキスト。エラー時は None。
        """
        if ai_id not in self.agents:
            logger.error("不明なAI ID: %s", ai_id)
            return None

        agent = self.agents[ai_id]
        if not agent["online"]:
            logger.warning("%s (%s): オフライン - メッセージ送信スキップ", agent["profile"]["name"], ai_id)
            return None

        return agent["service"].send_message(messages, system_prompt=system_prompt, images=images)

    def get_online_agents(self) -> list:
        """オンラインのAIエージェントIDリストを返す。"""
        return [ai_id for ai_id, agent in self.agents.items() if agent["online"]]

    def get_agent_profile(self, ai_id: str) -> dict:
        """指定AIのプロファイルを返す。"""
        if ai_id in self.agents:
            return self.agents[ai_id]["profile"]
        return None

    def is_online(self, ai_id: str) -> bool:
        """指定AIがオンラインかどうかを返す。"""
        if ai_id in self.agents:
            return self.agents[ai_id]["online"]
        return False

    def shutdown_all(self):
        """全AIエージェントを停止する。"""
        for ai_id, agent in self.agents.items():
            agent["online"] = False
            logger.info("%s (%s): シャットダウン", agent["profile"]["name"], ai_id)
        self._initialized = False
