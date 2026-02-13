"""
LLM?????? - ???AI??? (OpenAI / Claude / Gemini) ?????
"""

import json
import re

from config.settings import (
    ANTHROPIC_API_KEY,
    GOOGLE_API_KEY,
    OPENAI_API_KEY,
    is_configured,
)


class LLMClient:
    """??LLM?API???????"""

    def __init__(self):
        self._openai_client = None
        self._anthropic_client = None
        self._google_model = None

    @property
    def openai_client(self):
        if self._openai_client is None and is_configured("OPENAI_API_KEY"):
            import openai

            self._openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        return self._openai_client

    @property
    def anthropic_client(self):
        if self._anthropic_client is None and is_configured("ANTHROPIC_API_KEY"):
            import anthropic

            self._anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        return self._anthropic_client

    @property
    def google_model(self):
        if self._google_model is None and is_configured("GOOGLE_API_KEY"):
            import google.generativeai as genai

            genai.configure(api_key=GOOGLE_API_KEY)
            self._google_model = genai.GenerativeModel("gemini-2.0-flash")
        return self._google_model

    def query_openai(self, prompt: str, system_prompt: str = "", model: str = "gpt-5") -> str:
        """OpenAI API (GPT?) ??????"""
        if not self.openai_client:
            return ""

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request_kwargs = {
            "model": model,
            "messages": messages,
            "max_completion_tokens": 4096,
            "temperature": 0.3,
        }
        if model.startswith("gpt-5"):
            request_kwargs.pop("temperature", None)

        try:
            response = self.openai_client.chat.completions.create(**request_kwargs)
            return response.choices[0].message.content or ""
        except Exception as e:
            error_text = str(e)
            is_temperature_error = (
                "temperature" in error_text and "unsupported_value" in error_text
            )
            if is_temperature_error:
                request_kwargs.pop("temperature", None)
                try:
                    response = self.openai_client.chat.completions.create(**request_kwargs)
                    return response.choices[0].message.content or ""
                except Exception as retry_error:
                    print(f"[LLMClient] OpenAI API???: {retry_error}")
                    return ""

            print(f"[LLMClient] OpenAI API???: {e}")
            return ""

    def query_anthropic(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str = "claude-sonnet-4-20250514",
    ) -> str:
        """Anthropic API (Claude) ??????"""
        if not self.anthropic_client:
            return ""

        try:
            kwargs = {
                "model": model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            response = self.anthropic_client.messages.create(**kwargs)
            return response.content[0].text if response.content else ""
        except Exception as e:
            print(f"[LLMClient] Anthropic API???: {e}")
            return ""

    def query_google(self, prompt: str, system_prompt: str = "") -> str:
        """Google Gemini API ??????"""
        if not self.google_model:
            return ""

        try:
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = self.google_model.generate_content(full_prompt)
            return response.text or ""
        except Exception as e:
            print(f"[LLMClient] Google API???: {e}")
            return ""

    def query(self, prompt: str, system_prompt: str = "", provider: str = "openai") -> str:
        """?????????????????????????"""
        providers = {
            "openai": self.query_openai,
            "anthropic": self.query_anthropic,
            "google": self.query_google,
        }

        if provider in providers:
            result = providers[provider](prompt, system_prompt)
            if result:
                return result

        for name, func in providers.items():
            if name != provider:
                result = func(prompt, system_prompt)
                if result:
                    return result

        return "?????AI??????????API????????????"

    def query_json(self, prompt: str, system_prompt: str = "", provider: str = "openai") -> dict:
        """JSON????????????"""
        result = self.query(prompt, system_prompt, provider)
        return self._parse_json(result)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """??????JSON??????"""
        if not text:
            return {}

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        try:
            match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
            if match:
                return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

        return {"raw_response": text}
