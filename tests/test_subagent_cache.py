"""Unit tests for the subagent response caching layer."""

import os
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.models.subagent_models import SubagentMetadata, SubagentResponse
from backend.services.subagents.cache import (
    CacheConfig,
    CacheEntry,
    CacheMetrics,
    SubagentCache,
    get_subagent_cache,
    reset_subagent_cache,
)

# =============================================================================
# CacheConfig Tests
# =============================================================================


class TestCacheConfig:
    """Tests for CacheConfig."""

    def test_default_config(self):
        """Should create config with sensible defaults."""
        config = CacheConfig.default()

        assert config.enabled is True
        assert config.default_ttl == 3600
        assert config.max_entries == 1000
        assert config.agent_ttls["rules"] == 3600 * 24  # 24 hours
        assert config.agent_ttls["state"] == 0  # No caching
        assert config.agent_ttls["action_space"] == 3600  # 1 hour
        assert config.agent_ttls["scenario"] == 3600 * 24  # 24 hours

    def test_disabled_config(self):
        """Should create disabled config."""
        config = CacheConfig.disabled()

        assert config.enabled is False

    def test_from_env_defaults(self):
        """Should load defaults when env vars not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = CacheConfig.from_env()

        assert config.enabled is True
        assert config.default_ttl == 3600

    def test_from_env_disabled(self):
        """Should disable cache via env var."""
        with patch.dict(os.environ, {"SUBAGENT_CACHE_ENABLED": "false"}):
            config = CacheConfig.from_env()

        assert config.enabled is False

    def test_from_env_custom_ttl(self):
        """Should load custom TTL from env."""
        with patch.dict(os.environ, {"SUBAGENT_CACHE_DEFAULT_TTL": "7200"}):
            config = CacheConfig.from_env()

        assert config.default_ttl == 7200

    def test_from_env_max_entries(self):
        """Should load max entries from env."""
        with patch.dict(os.environ, {"SUBAGENT_CACHE_MAX_ENTRIES": "500"}):
            config = CacheConfig.from_env()

        assert config.max_entries == 500


# =============================================================================
# CacheEntry Tests
# =============================================================================


class TestCacheEntry:
    """Tests for CacheEntry."""

    @pytest.fixture
    def sample_response(self):
        """Create a sample SubagentResponse."""
        return SubagentResponse(
            content="Test response",
            confidence=0.9,
            sources=["Test source"],
            metadata=SubagentMetadata(agent_type="rules"),
        )

    def test_entry_not_expired(self, sample_response):
        """Should not be expired within TTL."""
        entry = CacheEntry(
            response=sample_response,
            created_at=time.time(),
            ttl=3600,
            agent_type="rules",
            query_hash="abc123",
        )

        assert entry.is_expired() is False
        assert entry.time_remaining() > 0

    def test_entry_expired(self, sample_response):
        """Should be expired after TTL."""
        entry = CacheEntry(
            response=sample_response,
            created_at=time.time() - 3700,  # 3700 seconds ago
            ttl=3600,
            agent_type="rules",
            query_hash="abc123",
        )

        assert entry.is_expired() is True
        assert entry.time_remaining() == 0

    def test_zero_ttl_always_expired(self, sample_response):
        """Should always be expired with TTL of 0."""
        entry = CacheEntry(
            response=sample_response,
            created_at=time.time(),
            ttl=0,
            agent_type="state",
            query_hash="abc123",
        )

        assert entry.is_expired() is True
        assert entry.time_remaining() == 0


# =============================================================================
# CacheMetrics Tests
# =============================================================================


class TestCacheMetrics:
    """Tests for CacheMetrics."""

    def test_initial_metrics(self):
        """Should start with zeros."""
        metrics = CacheMetrics()

        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.evictions == 0
        assert metrics.expirations == 0

    def test_total_requests(self):
        """Should calculate total requests."""
        metrics = CacheMetrics(hits=10, misses=5)

        assert metrics.total_requests == 15

    def test_hit_rate(self):
        """Should calculate hit rate percentage."""
        metrics = CacheMetrics(hits=75, misses=25)

        assert metrics.hit_rate == 75.0

    def test_hit_rate_no_requests(self):
        """Should return 0 when no requests."""
        metrics = CacheMetrics()

        assert metrics.hit_rate == 0.0

    def test_to_dict(self):
        """Should convert to dictionary."""
        metrics = CacheMetrics(hits=10, misses=5, evictions=2, expirations=3)
        result = metrics.to_dict()

        assert result["hits"] == 10
        assert result["misses"] == 5
        assert result["evictions"] == 2
        assert result["expirations"] == 3
        assert result["total_requests"] == 15
        assert result["hit_rate"] == 66.67


# =============================================================================
# SubagentCache Tests
# =============================================================================


class TestSubagentCache:
    """Tests for SubagentCache."""

    @pytest.fixture
    def cache(self):
        """Create a cache with default config."""
        return SubagentCache(CacheConfig.default())

    @pytest.fixture
    def sample_response(self):
        """Create a sample SubagentResponse."""
        return SubagentResponse(
            content="Test response",
            confidence=0.9,
            sources=["Test source"],
            metadata=SubagentMetadata(agent_type="rules"),
        )

    def test_cache_and_retrieve(self, cache, sample_response):
        """Should cache and retrieve response."""
        cache.cache_response("rules", "test query", sample_response)

        cached = cache.get_cached_response("rules", "test query")

        assert cached is not None
        assert cached.content == "Test response"

    def test_cache_miss(self, cache):
        """Should return None for cache miss."""
        cached = cache.get_cached_response("rules", "nonexistent query")

        assert cached is None

    def test_cache_with_context(self, cache, sample_response):
        """Should cache with context and match correctly."""
        context = {"investigator_name": "Roland Banks"}

        cache.cache_response("rules", "test query", sample_response, context)

        # Same context should hit
        cached = cache.get_cached_response("rules", "test query", context)
        assert cached is not None

        # Different context should miss
        different_context = {"investigator_name": "Wendy Adams"}
        cached = cache.get_cached_response("rules", "test query", different_context)
        assert cached is None

    def test_different_agent_types_separate(self, cache, sample_response):
        """Should cache separately for different agent types."""
        cache.cache_response("rules", "test query", sample_response)

        # Same query, different agent type should miss
        cached = cache.get_cached_response("action_space", "test query")
        assert cached is None

    def test_state_agent_not_cached(self, cache, sample_response):
        """Should not cache state agent responses (TTL=0)."""
        cache.cache_response("state", "test query", sample_response)

        cached = cache.get_cached_response("state", "test query")
        assert cached is None

    def test_cache_disabled(self, sample_response):
        """Should not cache when disabled."""
        config = CacheConfig.disabled()
        cache = SubagentCache(config)

        cache.cache_response("rules", "test query", sample_response)
        cached = cache.get_cached_response("rules", "test query")

        assert cached is None

    def test_expired_entry_removed(self, sample_response):
        """Should remove expired entries on access."""
        config = CacheConfig(enabled=True, default_ttl=1, agent_ttls={"rules": 1})
        cache = SubagentCache(config)

        cache.cache_response("rules", "test query", sample_response)

        # Wait for expiration
        time.sleep(1.5)

        cached = cache.get_cached_response("rules", "test query")
        assert cached is None
        assert cache.get_metrics().expirations >= 1

    def test_eviction_at_max_capacity(self, sample_response):
        """Should evict oldest entries at max capacity."""
        config = CacheConfig(
            enabled=True,
            default_ttl=3600,
            agent_ttls={"rules": 3600},
            max_entries=3,
        )
        cache = SubagentCache(config)

        # Fill cache
        for i in range(4):
            cache.cache_response("rules", f"query_{i}", sample_response)

        # Should have evicted one entry
        assert cache.size() == 3
        assert cache.get_metrics().evictions >= 1

    def test_invalidate_by_agent_type(self, cache, sample_response):
        """Should invalidate entries by agent type."""
        cache.cache_response("rules", "query1", sample_response)
        cache.cache_response("rules", "query2", sample_response)
        cache.cache_response("action_space", "query3", sample_response)

        count = cache.invalidate_cache(agent_type="rules")

        assert count == 2
        assert cache.get_cached_response("rules", "query1") is None
        assert cache.get_cached_response("action_space", "query3") is not None

    def test_clear_cache(self, cache, sample_response):
        """Should clear all entries."""
        cache.cache_response("rules", "query1", sample_response)
        cache.cache_response("action_space", "query2", sample_response)

        cache.clear()

        assert cache.size() == 0

    def test_metrics_tracking(self, cache, sample_response):
        """Should track cache metrics."""
        # Cache miss
        cache.get_cached_response("rules", "nonexistent")

        # Cache hit
        cache.cache_response("rules", "test query", sample_response)
        cache.get_cached_response("rules", "test query")
        cache.get_cached_response("rules", "test query")

        metrics = cache.get_metrics()
        assert metrics.hits == 2
        assert metrics.misses == 1
        assert metrics.hit_rate == pytest.approx(66.67, rel=0.01)

    def test_reset_metrics(self, cache, sample_response):
        """Should reset metrics to zero."""
        cache.cache_response("rules", "test query", sample_response)
        cache.get_cached_response("rules", "test query")

        cache.reset_metrics()
        metrics = cache.get_metrics()

        assert metrics.hits == 0
        assert metrics.misses == 0

    def test_get_entry_info(self, cache, sample_response):
        """Should return entry info."""
        cache.cache_response("rules", "test query", sample_response)

        info = cache.get_entry_info("rules", "test query")

        assert info is not None
        assert info["agent_type"] == "rules"
        assert info["ttl"] == 3600 * 24
        assert info["time_remaining"] > 0
        assert info["is_expired"] is False

    def test_get_entry_info_not_found(self, cache):
        """Should return None for nonexistent entry."""
        info = cache.get_entry_info("rules", "nonexistent")

        assert info is None


# =============================================================================
# Query Hashing Tests
# =============================================================================


class TestQueryHashing:
    """Tests for query hashing."""

    @pytest.fixture
    def cache(self):
        return SubagentCache(CacheConfig.default())

    def test_same_query_same_hash(self, cache):
        """Should generate same hash for identical queries."""
        hash1 = cache._hash_query("rules", "test query")
        hash2 = cache._hash_query("rules", "test query")

        assert hash1 == hash2

    def test_different_query_different_hash(self, cache):
        """Should generate different hash for different queries."""
        hash1 = cache._hash_query("rules", "query one")
        hash2 = cache._hash_query("rules", "query two")

        assert hash1 != hash2

    def test_different_agent_different_hash(self, cache):
        """Should generate different hash for different agent types."""
        hash1 = cache._hash_query("rules", "test query")
        hash2 = cache._hash_query("action_space", "test query")

        assert hash1 != hash2

    def test_context_affects_hash(self, cache):
        """Should include context in hash."""
        hash1 = cache._hash_query("rules", "test", {"name": "Roland"})
        hash2 = cache._hash_query("rules", "test", {"name": "Wendy"})
        hash3 = cache._hash_query("rules", "test", None)

        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3

    def test_internal_context_ignored(self, cache):
        """Should ignore internal context fields (starting with _)."""
        hash1 = cache._hash_query("rules", "test", {"name": "Roland"})
        hash2 = cache._hash_query(
            "rules", "test",
            {"name": "Roland", "_internal": "ignored"}
        )

        assert hash1 == hash2


# =============================================================================
# Global Cache Tests
# =============================================================================


class TestGlobalCache:
    """Tests for global cache instance."""

    def test_get_singleton(self):
        """Should return same instance."""
        reset_subagent_cache()

        cache1 = get_subagent_cache()
        cache2 = get_subagent_cache()

        assert cache1 is cache2

    def test_reset_creates_new(self):
        """Should create new instance after reset."""
        cache1 = get_subagent_cache()
        reset_subagent_cache()
        cache2 = get_subagent_cache()

        assert cache1 is not cache2


# =============================================================================
# Integration with BaseSubagent Tests
# =============================================================================


class TestCacheIntegration:
    """Integration tests for cache with BaseSubagent."""

    @pytest.fixture
    def mock_llm_response(self):
        """Create a mock LLM response."""
        mock_response = MagicMock()
        mock_response.content = "Test LLM response"
        return mock_response

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_cache_hit_skips_llm(self, mock_chat_class, mock_llm_response):
        """Should return cached response without calling LLM."""
        from backend.services.subagents.base import RulesSubagent

        # Reset cache
        reset_subagent_cache()

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = RulesSubagent()

        # First call - should hit LLM
        response1 = agent.query("test query")
        assert mock_llm.invoke.call_count == 1

        # Second call - should use cache
        response2 = agent.query("test query")
        assert mock_llm.invoke.call_count == 1  # Still 1, no new call

        assert response1.content == response2.content

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_cache_disabled_always_calls_llm(self, mock_chat_class, mock_llm_response):
        """Should always call LLM when cache disabled."""
        from backend.services.subagents.base import RulesSubagent

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = RulesSubagent(use_cache=False)

        # Both calls should hit LLM
        agent.query("test query")
        agent.query("test query")

        assert mock_llm.invoke.call_count == 2

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_state_agent_never_cached(self, mock_chat_class, mock_llm_response):
        """State agent should never use cache (TTL=0)."""
        from backend.services.subagents.base import StateSubagent

        # Reset cache
        reset_subagent_cache()

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = StateSubagent()

        # Both calls should hit LLM
        agent.query("test query")
        agent.query("test query")

        assert mock_llm.invoke.call_count == 2

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("backend.services.subagents.base.ChatOpenAI")
    def test_different_context_cache_miss(self, mock_chat_class, mock_llm_response):
        """Different context should cause cache miss."""
        from backend.services.subagents.base import RulesSubagent

        # Reset cache
        reset_subagent_cache()

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_llm_response
        mock_chat_class.return_value = mock_llm

        agent = RulesSubagent()

        # Different contexts should both call LLM
        agent.query("test query", {"investigator_name": "Roland"})
        agent.query("test query", {"investigator_name": "Wendy"})

        assert mock_llm.invoke.call_count == 2
