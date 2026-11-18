"""The agent reasoning loop (ReAct: reason -> act -> observe -> repeat).

This is Faz 0's engine and the pattern every specialized agent reuses.
It is intentionally small and readable — the whole point of writing this
yourself is that you can see exactly what the agent does each step.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import Tier
from ..llm.base import LLMProvider, Message
from ..safety.scope import ScopeError, ScopeGuard
from ..state import Store
from ..tools.base import ToolRegistry


@dataclass
class AgentConfig:
    name: str
    tier: Tier
    system_prompt: str
    max_steps: int = 25


@dataclass
class AgentRun:
    transcript: list[Message] = field(default_factory=list)
    steps: int = 0
    stopped_reason: str = ""


class Agent:
    def __init__(
        self,
        config: AgentConfig,
        provider: LLMProvider,
        registry: ToolRegistry,
        guard: ScopeGuard,
        store: Store,
        on_event=None,  # optional callback(event: str, payload: dict) for the CLI/UI
    ):
        self.config = config
        self.provider = provider
        self.registry = registry
        self.guard = guard
        self.store = store
        self.on_event = on_event or (lambda e, p: None)

    def run(self, task: str) -> AgentRun:
        run = AgentRun()
        messages: list[Message] = [Message(role="user", content=task)]
        specs = self.registry.specs()

        for step in range(1, self.config.max_steps + 1):
            run.steps = step
            self.on_event("think", {"agent": self.config.name, "step": step})

            resp = self.provider.chat(
                tier=self.config.tier,
                messages=messages,
                tools=specs,
                system=self.config.system_prompt,
            )
            messages.append(resp.message)

            if not resp.message.tool_calls:
                run.stopped_reason = "end_turn"
                run.transcript = messages
                self.on_event("final", {"agent": self.config.name, "text": resp.message.content})
                return run

            # Execute each requested tool call through the scope guard.
            for call in resp.message.tool_calls:
                tool = self.registry.get(call.name)
                if tool is None:
                    result_text = f"Unknown tool: {call.name}"
                else:
                    try:
                        self.on_event("act", {"tool": call.name, "args": call.arguments})
                        result = tool.invoke(call.arguments, self.guard)
                        result_text = result.summary
                        if result.ok and result.data:
                            self.store.add_finding(self.config.name, call.name, result.data, result.summary)
                    except ScopeError as e:
                        result_text = str(e)
                        self.on_event("blocked", {"tool": call.name, "reason": result_text})
                messages.append(Message(role="tool", content=result_text, tool_call_id=call.id))

        run.stopped_reason = "max_steps"
        run.transcript = messages
        return run
