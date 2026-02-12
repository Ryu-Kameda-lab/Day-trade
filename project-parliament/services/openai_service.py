"""
OpenAI Service - OpenAI ChatGPT API ラッパー
"""
import base64
import logging
import time

import openai

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds


class OpenAIService:
    """OpenAI ChatGPT API とのやり取りを管理するサービス"""

    def __init__(self, api_key: str, model: str = "gpt-4.1"):
        self.api_key = api_key
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None and self.api_key:
            self._client = openai.OpenAI(api_key=self.api_key)
        return self._client

    def send_message(self, messages: list, system_prompt: str = None, images: list = None) -> str:
        """
        OpenAI Chat Completions API を呼び出してレスポンスを返す。

        Args:
            messages: [{"role": "user"/"assistant", "content": "..."}]
            system_prompt: システムプロンプト（任意）
            images: base64エンコードされた画像データのリスト（任意）
                    [{"data": "<base64>", "media_type": "image/png"}, ...]
        Returns:
            レスポンステキスト。エラー時は None。
        """
        if not self.client:
            logger.warning("OpenAI: APIキーが未設定のためスキップ")
            return None

        api_messages = self._build_messages(messages, system_prompt, images)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=api_messages,
                    max_tokens=4096,
                )
                return response.choices[0].message.content
            except openai.RateLimitError:
                logger.warning("OpenAI: レート制限 (attempt %d/%d)", attempt, MAX_RETRIES)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
            except openai.APIError as e:
                logger.error("OpenAI API エラー (attempt %d/%d): %s", attempt, MAX_RETRIES, e)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY * attempt)
            except Exception as e:
                logger.error("OpenAI 予期しないエラー: %s", e)
                return None

        logger.error("OpenAI: 最大リトライ回数に到達")
        return None

    def test_connection(self) -> bool:
        """API接続テスト。短いメッセージを送信して成功可否を返す。"""
        if not self.client:
            logger.warning("OpenAI: APIキーが未設定")
            return False
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=16,
            )
            return bool(response.choices)
        except Exception as e:
            logger.error("OpenAI 接続テスト失敗: %s", e)
            return False

    def _build_messages(self, messages: list, system_prompt: str = None, images: list = None) -> list:
        """
        統一メッセージ形式を OpenAI API 形式に変換する。
        system_prompt があれば先頭に system メッセージを追加。
        画像がある場合、最後の user メッセージに画像URLを追加。
        """
        api_messages = []

        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        if images and api_messages:
            # 最後の user メッセージを探して画像を添付
            for i in range(len(api_messages) - 1, -1, -1):
                if api_messages[i]["role"] == "user":
                    content_parts = []
                    content_parts.append({
                        "type": "text",
                        "text": api_messages[i]["content"],
                    })
                    for img in images:
                        media_type = img.get("media_type", "image/png")
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{img['data']}",
                            },
                        })
                    api_messages[i]["content"] = content_parts
                    break

        return api_messages
