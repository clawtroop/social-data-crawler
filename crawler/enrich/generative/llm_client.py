from __future__ import annotations

import json
from typing import Any

import httpx

from crawler.enrich.models import LLMResponse


class LLMConfigurationError(ValueError):
    """Raised when a generative enrichment request lacks required AI config."""


class LLMRequestError(RuntimeError):
    """Raised when the configured model endpoint cannot return a response."""


class LLMEmptyResponseError(RuntimeError):
    """Raised when the model endpoint returns no usable content."""


class LLMClient:
    """Async client for OpenAI-compatible LLM APIs."""

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        default_model: str = "",
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self.timeout = timeout

    @classmethod
    def from_model_config(cls, model_config: dict[str, Any]) -> LLMClient:
        return cls(
            base_url=str(model_config.get("base_url", "")),
            api_key=str(model_config.get("api_key", "")),
            default_model=str(model_config.get("model", "")),
            timeout=float(model_config.get("timeout", 60.0)),
        )

    async def complete(
        self,
        prompt: str,
        *,
        model: str = "",
        max_tokens: int = 512,
        temperature: float = 0.2,
        system_prompt: str = "",
    ) -> LLMResponse:
        """Send a completion request to an OpenAI-compatible API."""
        resolved_model = model or self.default_model
        if not self.base_url or not resolved_model:
            raise LLMConfigurationError("AI configuration is incomplete")

        url = f"{self.base_url}/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": resolved_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            raise LLMRequestError("LLM request failed") from exc

        content = self._extract_content(data)
        if not content:
            raise LLMEmptyResponseError("LLM returned empty response")
        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            model=data.get("model", resolved_model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

    @staticmethod
    def _extract_content(data: dict[str, Any]) -> str:
        choices = data.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = [p.get("text", "") for p in content if isinstance(p, dict)]
            return "".join(parts).strip()
        return ""


def parse_json_response(content: str) -> dict[str, Any] | list[Any]:
    """Try to parse JSON from LLM response, handling markdown code blocks."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # remove opening ```json
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": content}
