"""
AI Manager - 全AIエージェントの起動・管理を統括する
Phase 2 で実装予定。現在はスタブ。
"""
from config import AI_PROFILES


class AIManager:
    """全AIエージェントのライフサイクル管理"""

    def __init__(self):
        self.agents = {}  # ai_id -> AIAgent インスタンス
        self._initialized = False

    async def activate_all(self):
        """
        全AIエージェントをアクティブにする
        各AI APIへの接続テストを行い、成功したものをオンラインにする
        """
        results = {}
        for ai_id, profile in AI_PROFILES.items():
            try:
                # Phase 2: 実際のAPI接続テストを実装
                # agent = await self._create_agent(ai_id, profile)
                # self.agents[ai_id] = agent
                results[ai_id] = {"status": "online", "name": profile["name"]}
            except Exception as e:
                results[ai_id] = {"status": "error", "name": profile["name"], "error": str(e)}

        self._initialized = True
        return results

    async def send_message(self, ai_id: str, messages: list, images: list = None):
        """
        指定したAIにメッセージを送信し、応答を取得する
        Phase 2 で実装予定
        """
        # TODO: 各サービスのAPIを呼び出す
        raise NotImplementedError("Phase 2 で実装予定")

    def get_online_agents(self) -> list:
        """オンラインのAIエージェント一覧を返す"""
        return list(self.agents.keys())

    def shutdown_all(self):
        """全AIエージェントを停止する"""
        self.agents.clear()
        self._initialized = False
