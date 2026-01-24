"""Centralized LLM configuration for the Arkham Assistant.

This module provides environment variable-based configuration for LLM models
and factory functions to create configured LangChain chat clients.
"""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Load environment variables from .env file
load_dotenv()


# Default model configurations
DEFAULT_ORCHESTRATOR_MODEL = "gpt-4o"
DEFAULT_SUBAGENT_MODEL = "gpt-4o-mini"


@dataclass(frozen=True)
class LLMConfig:
    """Configuration for LLM models."""

    orchestrator_model: str
    subagent_model: str
    api_key: str | None


@lru_cache(maxsize=1)
def get_llm_config() -> LLMConfig:
    """Load LLM configuration from environment variables.

    Returns:
        LLMConfig with model names and API key.
    """
    return LLMConfig(
        orchestrator_model=os.getenv("ORCHESTRATOR_MODEL", DEFAULT_ORCHESTRATOR_MODEL),
        subagent_model=os.getenv("SUBAGENT_MODEL", DEFAULT_SUBAGENT_MODEL),
        api_key=os.getenv("OPENAI_API_KEY"),
    )


def get_orchestrator_llm(temperature: float = 0.0) -> ChatOpenAI:
    """Create a ChatOpenAI client configured for the orchestrator.

    The orchestrator uses a more capable reasoning model for complex
    decision-making and tool orchestration.

    Args:
        temperature: Sampling temperature (0.0 = deterministic).

    Returns:
        Configured ChatOpenAI instance.

    Raises:
        ValueError: If OPENAI_API_KEY is not set.
    """
    config = get_llm_config()
    if not config.api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    return ChatOpenAI(
        model=config.orchestrator_model,
        temperature=temperature,
        api_key=config.api_key,
    )


def get_subagent_llm(temperature: float = 0.0) -> ChatOpenAI:
    """Create a ChatOpenAI client configured for subagents.

    Subagents use a smaller, faster model for focused tasks like
    card lookups and simple queries.

    Args:
        temperature: Sampling temperature (0.0 = deterministic).

    Returns:
        Configured ChatOpenAI instance.

    Raises:
        ValueError: If OPENAI_API_KEY is not set.
    """
    config = get_llm_config()
    if not config.api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    return ChatOpenAI(
        model=config.subagent_model,
        temperature=temperature,
        api_key=config.api_key,
    )


def clear_config_cache() -> None:
    """Clear the cached LLM configuration.

    Useful for testing when environment variables change.
    """
    get_llm_config.cache_clear()
