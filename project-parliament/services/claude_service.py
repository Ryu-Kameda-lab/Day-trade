"""
Claude Service - Anthropic Claude API ラッパー
"""
import base64
import logging
import time

import anthropic

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds


class ClaudeService:
    """Anthropic Claude API とのやり取りを管理するサービス"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None and self.api_key:
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def send_message(self, messages: list, system_prompt: str = None, images: list = None) -> str:
        """
        Claude Messages API を呼び出してレスポンスを返す。

        Args:
            messages: [{"role": "user"/"assistant", "content": "..."}]
            system_prompt: システムプロンプト（任意）
            images: base64エンコードされた画像データのリスト（任意）
                    [{"data": "<base64>", "media_type": "image/png"}, ...]
        Returns:
            レスポンステキスト。エラー時は None。
        """
        if not self.client:
            logger.warning("Claude: APIキーが未設定のためスキップ")
            return None

        # メッセージ変換: 最後のuserメッセージに画像を添付
        api_messages = self._build_messages(messages, images)

        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": api_messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.client.messages.create(**kwargs)
                return response.content[0].text
            except anthropic.RateLimitError:
                logger.warning("Claude: レート制限 (attempt %d/%d)", attempt, MAX_RETRIES)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
            except anthropic.APIError as e:
                logger.error("Claude API エラー (attempt %d/%d): %s", attempt, MAX_RETRIES, e)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
            except Exception as e:
                logger.error("Claude 予期しないエラー: %s", e)
                return None

        logger.error("Claude: 最大リトライ回数に到達")
        return None

    def test_connection(self) -> bool:
        """API接続テスト。短いメッセージを送信して成功可否を返す。"""
        if not self.client:
            logger.warning("Claude: APIキーが未設定")
            return False
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16,
                messages=[{"role": "user", "content": "ping"}],
            )
            return bool(response.content)
        except Exception as e:
            logger.error("Claude 接続テスト失敗: %s", e)
            return False

    def _build_messages(self, messages: list, images: list = None) -> list:
        """
        統一メッセージ形式を Claude API 形式に変換する。
        画像がある場合、最後の user メッセージに画像ブロックを追加。
        """
        api_messages = []
        for msg in messages:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        if images and api_messages:
            # 最後の user メッセージを探して画像を添付
            for i in range(len(api_messages) - 1, -1, -1):
                if api_messages[i]["role"] == "user":
                    content_blocks = []
                    for img in images:
                        content_blocks.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": img.get("media_type", "image/png"),
                                "data": img["data"],
                            },
                        })
                    content_blocks.append({
                        "type": "text",
                        "text": api_messages[i]["content"],
                    })
                    api_messages[i]["content"] = content_blocks
                    break

        return api_messages
