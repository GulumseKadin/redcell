"""Ollama provider (local models).

Talks to a local Ollama server's /api/chat endpoint. Tool-calling support
depends on the model, and local models are noisier than hosted ones, so this
provider is hardened (Faz 9): transient network/5xx errors are retried with
backoff, malformed tool-call arguments never crash the run, and the assistant's
own tool calls are echoed back into history so multi-step tool loops stay
coherent. Kept dependency-free (httpx only) so local-only setups need no cloud SDK.
"""
from __future__ import annotations

import json
import time
from typing import Any

import httpx

from ...config import ProviderName, Settings, Tier, model_for
from ..base import LLMProvider, LLMResponse, Message, ToolCall, ToolSpec

# Base backoff (seconds) between retries; attempt N waits _BACKOFF * N.
_BACKOFF = 0.25


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, settings: Settings):
        self.settings = settings

    def available(self) -> bool:
        try:
            r = httpx.get(f"{self.settings.ollama_base_url}/api/tags", timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST with bounded retries on transient errors (network + HTTP 5xx).

        4xx errors are the caller's fault (bad request) and are NOT retried.
        Raises RuntimeError with the last error once attempts are exhausted.
        """
        attempts = max(1, self.settings.max_retries + 1)
        last_err: Exception | str = "unknown error"
        for attempt in range(attempts):
            if attempt:
                time.sleep(_BACKOFF * attempt)
            try:
                r = httpx.post(url, json=payload, timeout=self.settings.request_timeout)
            except httpx.RequestError as e:  # connection reset, timeout, DNS, ...
                last_err = e
                continue
            if r.status_code >= 500:  # transient server-side; retry
                last_err = f"HTTP {r.status_code}: {r.text[:200]}"
                continue
            r.raise_for_status()  # 4xx -> raise immediately, no retry
            return r.json()
        raise RuntimeError(f"Ollama request to {url} failed after {attempts} attempt(s): {last_err}")

    def chat(
        self,
        tier: Tier,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        model = model_for(ProviderName.OLLAMA, tier)
        payload: dict[str, Any] = {
            "model": model,
            "stream": False,
            "options": {"temperature": temperature},
            "messages": ([{"role": "system", "content": system}] if system else [])
            + [self._msg(m) for m in messages],
        }
        if tools:
            payload["tools"] = [self._tool(t) for t in tools]

        data = self._post(f"{self.settings.ollama_base_url}/api/chat", payload)
        msg = data.get("message", {})

        calls: list[ToolCall] = []
        for i, tc in enumerate(msg.get("tool_calls", []) or []):
            fn = tc.get("function", {})
            name = fn.get("name", "")
            if not name:
                continue  # unusable tool call; skip rather than crash the loop
            calls.append(ToolCall(id=f"call_{i}", name=name, arguments=self._coerce_args(fn.get("arguments"))))

        stop = "tool_use" if calls else "end_turn"
        return LLMResponse(
            message=Message(role="assistant", content=msg.get("content", ""), tool_calls=calls),
            stop_reason=stop,
            raw=data,
        )

    @staticmethod
    def _coerce_args(args: Any) -> dict[str, Any]:
        """Turn whatever the model put in `arguments` into a dict, never raising.

        Local models sometimes emit arguments as a JSON string, a double-encoded
        string, or malformed JSON. A bad tool call should degrade to empty args,
        not kill the whole assessment.
        """
        if isinstance(args, dict):
            return args
        if isinstance(args, str):
            try:
                parsed = json.loads(args or "{}")
                return parsed if isinstance(parsed, dict) else {}
            except (json.JSONDecodeError, ValueError):
                return {}
        return {}

    @staticmethod
    def _tool(t: ToolSpec) -> dict[str, Any]:
        return {"type": "function", "function": {
            "name": t.name, "description": t.description, "parameters": t.input_schema,
        }}

    @staticmethod
    def _msg(m: Message) -> dict[str, Any]:
        if m.role == "tool":
            return {"role": "tool", "content": m.content}
        out: dict[str, Any] = {"role": m.role, "content": m.content}
        # Echo the assistant's own tool calls back into history so the model keeps
        # the thread of a multi-step tool conversation.
        if m.role == "assistant" and m.tool_calls:
            out["tool_calls"] = [
                {"function": {"name": c.name, "arguments": c.arguments}} for c in m.tool_calls
            ]
        return out
