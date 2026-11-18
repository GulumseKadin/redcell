"""Anthropic provider.

Translates redcell's neutral Message/ToolSpec shapes to the Anthropic
Messages API and back. Import of the SDK is lazy so the package still
imports when only Ollama is installed.
"""
from __future__ import annotations

from typing import Any

from ...config import ProviderName, Settings, Tier, model_for
from ..base import LLMProvider, LLMResponse, Message, ToolCall, ToolSpec


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None

    def available(self) -> bool:
        return bool(self.settings.anthropic_api_key)

    def _client_lazy(self):
        if self._client is None:
            import anthropic  # lazy import
            self._client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
        return self._client

    def chat(
        self,
        tier: Tier,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        client = self._client_lazy()
        model = model_for(ProviderName.ANTHROPIC, tier)

        resp = client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=temperature,
            system=system or "You are an authorized security testing assistant.",
            tools=[self._tool(t) for t in (tools or [])],
            messages=[self._msg(m) for m in messages],
        )

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))

        return LLMResponse(
            message=Message(role="assistant", content="".join(text_parts), tool_calls=calls),
            stop_reason=resp.stop_reason,
            raw=resp,
        )

    # --- shape translation ---------------------------------------------------
    @staticmethod
    def _tool(t: ToolSpec) -> dict[str, Any]:
        return {"name": t.name, "description": t.description, "input_schema": t.input_schema}

    @staticmethod
    def _msg(m: Message) -> dict[str, Any]:
        if m.role == "tool":
            return {
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": m.tool_call_id,
                    "content": m.content,
                }],
            }
        if m.role == "assistant" and m.tool_calls:
            content: list[dict[str, Any]] = []
            if m.content:
                content.append({"type": "text", "text": m.content})
            for c in m.tool_calls:
                content.append({"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments})
            return {"role": "assistant", "content": content}
        return {"role": m.role, "content": m.content}
