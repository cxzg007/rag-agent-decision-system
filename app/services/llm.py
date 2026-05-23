import json
import logging
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMResponse(BaseModel):
    content: str
    provider: str
    model: str
    raw: dict[str, Any] | None = None


class LLMClient:
    async def chat_json(
        self,
        messages: list[LLMMessage],
        fallback: dict[str, Any],
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        response = await self.chat(messages, temperature=temperature)
        try:
            return json.loads(self._strip_json_fence(response.content))
        except json.JSONDecodeError as exc:
            logger.warning("LLM returned non-JSON content, fallback used: %s", exc)
            return fallback

    async def chat(self, messages: list[LLMMessage], temperature: float = 0.0) -> LLMResponse:
        provider = settings.llm_provider.lower()
        if provider == "mock":
            return self._mock_response(messages)
        if provider in {"openai", "openai-compatible"}:
            return await self._openai_compatible_chat(messages, temperature=temperature)
        logger.warning("unknown LLM_PROVIDER=%s, fallback to mock", settings.llm_provider)
        return self._mock_response(messages)

    def _mock_response(self, messages: list[LLMMessage]) -> LLMResponse:
        user_content = next((item.content for item in reversed(messages) if item.role == "user"), "")
        content = {
            "task_type": "document_qa",
            "route": "rag",
            "rewritten_query": "",
            "plan": [
                "Classify the user task.",
                "Retrieve relevant evidence.",
                "Check evidence sufficiency.",
                "Generate a cited answer.",
            ],
            "passed": True,
            "reason": "mock LLM response",
            "followup_queries": [],
            "answer": "Mock LLM response. Configure LLM_PROVIDER=openai and OPENAI_API_KEY for real generation.",
        }
        if "architecture plan" in user_content.lower() or "design an agent" in user_content.lower():
            content["task_type"] = "plan_generation"
            content["route"] = "plan"
        return LLMResponse(content=json.dumps(content), provider="mock", model="mock")

    async def _openai_compatible_chat(self, messages: list[LLMMessage], temperature: float) -> LLMResponse:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        url = settings.llm_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": settings.llm_model,
            "messages": [item.model_dump() for item in messages],
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
        return LLMResponse(content=content, provider=settings.llm_provider, model=settings.llm_model, raw=data)

    def _strip_json_fence(self, content: str) -> str:
        text = content.strip()
        if text.startswith("```json"):
            text = text.removeprefix("```json").strip()
        elif text.startswith("```"):
            text = text.removeprefix("```").strip()
        if text.endswith("```"):
            text = text.removesuffix("```").strip()
        return text


llm_client = LLMClient()
