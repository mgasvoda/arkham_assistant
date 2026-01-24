"""Tests for LLM configuration module."""

import os
from unittest.mock import patch

import pytest

from backend.services.llm_config import (
    DEFAULT_ORCHESTRATOR_MODEL,
    DEFAULT_SUBAGENT_MODEL,
    clear_config_cache,
    get_llm_config,
    get_orchestrator_llm,
    get_subagent_llm,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the config cache before and after each test."""
    clear_config_cache()
    yield
    clear_config_cache()


class TestGetLLMConfig:
    """Tests for get_llm_config function."""

    def test_default_values(self):
        """Config uses defaults when environment variables are not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = get_llm_config()

        assert config.orchestrator_model == DEFAULT_ORCHESTRATOR_MODEL
        assert config.subagent_model == DEFAULT_SUBAGENT_MODEL
        assert config.api_key is None

    def test_override_orchestrator_model(self):
        """ORCHESTRATOR_MODEL environment variable overrides default."""
        with patch.dict(os.environ, {"ORCHESTRATOR_MODEL": "o3"}, clear=True):
            config = get_llm_config()

        assert config.orchestrator_model == "o3"
        assert config.subagent_model == DEFAULT_SUBAGENT_MODEL

    def test_override_subagent_model(self):
        """SUBAGENT_MODEL environment variable overrides default."""
        with patch.dict(os.environ, {"SUBAGENT_MODEL": "gpt-5-mini"}, clear=True):
            config = get_llm_config()

        assert config.orchestrator_model == DEFAULT_ORCHESTRATOR_MODEL
        assert config.subagent_model == "gpt-5-mini"

    def test_api_key_from_environment(self):
        """OPENAI_API_KEY is loaded from environment."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}, clear=True):
            config = get_llm_config()

        assert config.api_key == "sk-test-key"

    def test_all_variables_override(self):
        """All environment variables can be overridden together."""
        env = {
            "ORCHESTRATOR_MODEL": "o4-mini",
            "SUBAGENT_MODEL": "gpt-5-mini",
            "OPENAI_API_KEY": "sk-custom-key",
        }
        with patch.dict(os.environ, env, clear=True):
            config = get_llm_config()

        assert config.orchestrator_model == "o4-mini"
        assert config.subagent_model == "gpt-5-mini"
        assert config.api_key == "sk-custom-key"

    def test_config_is_frozen(self):
        """LLMConfig instances are immutable."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}, clear=True):
            config = get_llm_config()

        with pytest.raises(AttributeError):
            config.orchestrator_model = "new-model"


class TestGetOrchestratorLLM:
    """Tests for get_orchestrator_llm function."""

    def test_raises_without_api_key(self):
        """Raises ValueError when OPENAI_API_KEY is not set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                get_orchestrator_llm()

    def test_creates_client_with_api_key(self):
        """Creates ChatOpenAI client when API key is set."""
        env = {"OPENAI_API_KEY": "sk-test-key", "ORCHESTRATOR_MODEL": "gpt-4o"}
        with patch.dict(os.environ, env, clear=True):
            llm = get_orchestrator_llm()

        assert llm.model_name == "gpt-4o"
        assert llm.temperature == 0.0

    def test_custom_temperature(self):
        """Custom temperature is applied to the client."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            llm = get_orchestrator_llm(temperature=0.7)

        assert llm.temperature == 0.7


class TestGetSubagentLLM:
    """Tests for get_subagent_llm function."""

    def test_raises_without_api_key(self):
        """Raises ValueError when OPENAI_API_KEY is not set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                get_subagent_llm()

    def test_creates_client_with_api_key(self):
        """Creates ChatOpenAI client when API key is set."""
        env = {"OPENAI_API_KEY": "sk-test-key", "SUBAGENT_MODEL": "gpt-4o-mini"}
        with patch.dict(os.environ, env, clear=True):
            llm = get_subagent_llm()

        assert llm.model_name == "gpt-4o-mini"
        assert llm.temperature == 0.0

    def test_custom_temperature(self):
        """Custom temperature is applied to the client."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            llm = get_subagent_llm(temperature=0.5)

        assert llm.temperature == 0.5


class TestClearConfigCache:
    """Tests for clear_config_cache function."""

    def test_cache_is_cleared(self):
        """Clearing cache allows new config to be loaded."""
        with patch.dict(os.environ, {"ORCHESTRATOR_MODEL": "model-1"}, clear=True):
            config1 = get_llm_config()
            assert config1.orchestrator_model == "model-1"

        clear_config_cache()

        with patch.dict(os.environ, {"ORCHESTRATOR_MODEL": "model-2"}, clear=True):
            config2 = get_llm_config()
            assert config2.orchestrator_model == "model-2"
