"""
Gemini Service - Google Gemini API ラッパー
"""
import base64
import logging
import time

import google.generativeai as genai

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds


class GeminiService:
    """Google Gemini API とのやり取りを管理するサービス"""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model_name = model
        self._model = None
        self._configured = False

    @property
    def model(self):
        if self._model is None and self.api_key:
            if not self._configured:
                genai.configure(api_key=self.api_key)
                self._configured = True
            self._model = genai.GenerativeModel(self.model_name)
        return self._model

    def send_message(self, messages: list, system_prompt: str = None, images: list = None) -> str:
        """
        Gemini generateContent API を呼び出してレスポンスを返す。

        Args:
            messages: [{"role": "user"/"assistant", "content": "..."}]
            system_prompt: システムプロンプト（任意）
            images: base64エンコードされた画像データのリスト（任意）
                    [{"data": "<base64>", "media_type": "image/png"}, ...]
        Returns:
            レスポンステキスト。エラー時は None。
        """
        if not self.model:
            logger.warning("Gemini: APIキーが未設定のためスキップ")
            return None

        # system_prompt がある場合はモデルを再作成
        model = self._get_model(system_prompt)
        contents = self._build_contents(messages, images)

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = model.generate_content(
                    contents,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=4096,
                    ),
                )
                return response.text
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "resource_exhausted" in error_str.lower():
                    logger.warning("Gemini: レート制限 (attempt %d/%d)", attempt, MAX_RETRIES)
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY * attempt)
                        continue
                elif "400" in error_str or "404" in error_str:
                    logger.error("Gemini API エラー (attempt %d/%d): %s", attempt, MAX_RETRIES, e)
                    if attempt < MAX_RETRIES:
                        time.sleep(RETRY_DELAY * attempt)
                        continue
                else:
                    logger.error("Gemini 予期しないエラー: %s", e)
                    return None

        logger.error("Gemini: 最大リトライ回数に到達")
        return None

    def test_connection(self) -> bool:
        """API接続テスト。短いメッセージを送信して成功可否を返す。"""
        if not self.model:
            logger.warning("Gemini: APIキーが未設定")
            return False
        try:
            response = self.model.generate_content(
                "ping",
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=16,
                ),
            )
            return bool(response.text)
        except Exception as e:
            logger.error("Gemini 接続テスト失敗: %s", e)
            return False

    def _get_model(self, system_prompt: str = None):
        """system_prompt が指定された場合、system_instruction 付きモデルを返す。"""
        if system_prompt:
            if not self._configured:
                genai.configure(api_key=self.api_key)
                self._configured = True
            return genai.GenerativeModel(
                self.model_name,
                system_instruction=system_prompt,
            )
        return self.model

    def _build_contents(self, messages: list, images: list = None) -> list:
        """
        統一メッセージ形式を Gemini API 形式に変換する。
        Gemini は role が "user" と "model" なので assistant -> model に変換。
        画像がある場合、最後の user メッセージに画像を添付。
        """
        contents = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}],
            })

        if images and contents:
            # 最後の user メッセージを探して画像を添付
            for i in range(len(contents) - 1, -1, -1):
                if contents[i]["role"] == "user":
                    image_parts = []
                    for img in images:
                        image_parts.append({
                            "inline_data": {
                                "mime_type": img.get("media_type", "image/png"),
                                "data": img["data"],
                            },
                        })
                    # 画像パーツをテキストの前に挿入
                    contents[i]["parts"] = image_parts + contents[i]["parts"]
                    break

        return contents
