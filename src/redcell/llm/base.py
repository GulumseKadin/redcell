"""Provider-agnostic LLM interface.

Every provider speaks the same small protocol so the agent loop never
knows which model it's talking to. The message/tool shapes follow the
now-standard "tool use" pattern: the model may return tool calls, we run
them, and feed results back as tool-result messages.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from ..config import Tier

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class ToolSpec:
    """What the model is told about a tool (name, purpose, JSON schema)."""
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Message:
    role: Role
    content: str = ""
    # assistant turns may carry tool calls; tool turns carry a result for one id
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None


@dataclass
class LLMResponse:
    message: Message
    stop_reason: str                    # "end_turn" | "tool_use" | ...
    raw: Any = None                     # original provider payload, for debugging


class LLMProvider(ABC):
    """Implement one of these per backend (Anthropic, Ollama, ...)."""

    name: str

    @abstractmethod
    def chat(
        self,
        tier: Tier,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        system: str | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """One model turn. May return tool calls in the response message."""
        raise NotImplementedError

    @abstractmethod
    def available(self) -> bool:
        """True if this provider is configured and reachable enough to use."""
        raise NotImplementedError
