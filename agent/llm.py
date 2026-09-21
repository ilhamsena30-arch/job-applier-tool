"""DeepSeek LLM client (OpenAI-compatible)."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from agent.config import get_settings


class LLMClient:
    """Thin wrapper over the OpenAI-compatible DeepSeek API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = OpenAI(
            api_key=settings.deepseek_api_key or "sk-not-set",
            base_url=settings.deepseek_base_url,
        )
        self.model = settings.deepseek_model
        self.reasoning_model = settings.deepseek_reasoning_model

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        """Return the assistant text reply."""
        resp = self._client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    def chat_json(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> Any:
        """Return a parsed JSON object (uses the API's JSON mode)."""
        resp = self._client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Strip markdown fences if present, then retry.
            cleaned = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(cleaned)

    def vision(
        self,
        prompt: str,
        image_base64: str,
        mime_type: str = "image/png",
        *,
        model: str | None = None,
    ) -> str:
        """Send an image + prompt. NOTE: only deepseek-flash supports vision."""
        resp = self._client.chat.completions.create(
            model=model or self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                        },
                    ],
                }
            ],
            temperature=0.0,
        )
        return resp.choices[0].message.content or ""


_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm
