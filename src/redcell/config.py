"""Configuration: settings, .env loading, and the tier -> model mapping.

The key idea (borrowed from Decepticon's design): agents never name a
concrete model. They ask for a *tier* (HIGH / MID / LOW). The factory
maps that tier to a real model on whichever provider is configured, so
you can swap providers without touching agent code.
"""
from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Tier(str, Enum):
    HIGH = "high"   # orchestrator, exploit reasoning, analysis
    MID = "mid"     # execution, verification
    LOW = "low"     # recon, summarization, cheap/local work


class ProviderName(str, Enum):
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class StoreBackend(str, Enum):
    SQLITE = "sqlite"   # default, zero setup
    NEO4J = "neo4j"     # graph state (Faz 4)


# tier -> model, per provider. Edit these to taste.
TIER_MODELS: dict[ProviderName, dict[Tier, str]] = {
    ProviderName.ANTHROPIC: {
        Tier.HIGH: "claude-opus-4-8",
        Tier.MID: "claude-sonnet-5",
        Tier.LOW: "claude-haiku-4-5",
    },
    ProviderName.OLLAMA: {
        Tier.HIGH: "qwen3:14b",
        Tier.MID: "qwen3:4b-instruct",
        Tier.LOW: "qwen3:4b-instruct",
    },
}


class Settings(BaseModel):
    provider: ProviderName = ProviderName.ANTHROPIC
    # Provider the factory falls back to when the primary has no key configured.
    fallback_provider: ProviderName | None = ProviderName.OLLAMA

    anthropic_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # Safety
    scope_file: str = "scope.yaml"
    require_approval: bool = True       # ask a human before each target-touching action
    dry_run: bool = False               # if True, tools describe what they'd do and stop

    # Engine
    max_steps: int = 25                 # hard cap on the agent reasoning loop
    workdir: str = ".redcell"

    # Provider resilience (Faz 9)
    request_timeout: float = 120.0      # per-request HTTP timeout, seconds
    max_retries: int = 2                # extra attempts on transient provider errors

    # Shared state backend (Faz 4)
    store: StoreBackend = StoreBackend.SQLITE
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str | None = None
    neo4j_database: str | None = None

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            provider=ProviderName(os.getenv("REDCELL_PROVIDER", "anthropic")),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            scope_file=os.getenv("REDCELL_SCOPE_FILE", "scope.yaml"),
            require_approval=os.getenv("REDCELL_REQUIRE_APPROVAL", "true").lower() == "true",
            dry_run=os.getenv("REDCELL_DRY_RUN", "false").lower() == "true",
            max_steps=int(os.getenv("REDCELL_MAX_STEPS", "25")),
            request_timeout=float(os.getenv("REDCELL_REQUEST_TIMEOUT", "120")),
            max_retries=int(os.getenv("REDCELL_MAX_RETRIES", "2")),
            store=StoreBackend(os.getenv("REDCELL_STORE", "sqlite")),
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
            neo4j_password=os.getenv("NEO4J_PASSWORD"),
            neo4j_database=os.getenv("NEO4J_DATABASE"),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.load()


def model_for(provider: ProviderName, tier: Tier) -> str:
    return TIER_MODELS[provider][tier]
