"""Subagent response caching layer.

This module implements a caching layer for subagent responses to avoid
redundant LLM calls for identical queries. It provides TTL-based invalidation
with configurable per-agent-type cache settings.

Key Features:
- In-memory caching with optional Redis backend (future)
- Configurable TTL per agent type
- Query hashing for cache keys
- Cache enable/disable via config
- Hit rate metrics tracking

Usage:
    cache = SubagentCache()

    # Check cache before calling subagent
    cached = cache.get_cached_response("rules", "Can Roland include Shrivelling?")
    if cached:
        return cached

    # After getting response from subagent
    cache.cache_response("rules", query, response)
"""

import hashlib
import os
import time
from dataclasses import dataclass, field
from typing import Any

from backend.models.subagent_models import SubagentResponse

# =============================================================================
# Configuration
# =============================================================================


@dataclass(frozen=True)
class CacheConfig:
    """Configuration for the subagent cache.

    Attributes:
        enabled: Whether caching is enabled.
        default_ttl: Default TTL in seconds for cache entries.
        agent_ttls: TTL overrides per agent type.
        max_entries: Maximum number of cache entries (0 = unlimited).
    """

    enabled: bool = True
    default_ttl: int = 3600  # 1 hour default
    agent_ttls: dict[str, int] = field(default_factory=dict)
    max_entries: int = 1000

    @classmethod
    def default(cls) -> "CacheConfig":
        """Create default cache configuration.

        Default TTLs:
        - rules_agent: 24 hours (rules rarely change)
        - state_agent: 0 (always fresh - deck may have changed)
        - action_space_agent: 1 hour (card pool stable)
        - scenario_agent: 24 hours (scenarios don't change)

        Returns:
            CacheConfig with sensible defaults.
        """
        return cls(
            enabled=True,
            default_ttl=3600,
            agent_ttls={
                "rules": 3600 * 24,  # 24 hours
                "state": 0,  # Always fresh
                "action_space": 3600,  # 1 hour
                "scenario": 3600 * 24,  # 24 hours
            },
            max_entries=1000,
        )

    @classmethod
    def from_env(cls) -> "CacheConfig":
        """Create config from environment variables.

        Environment variables:
            SUBAGENT_CACHE_ENABLED: "true" or "false" (default: "true")
            SUBAGENT_CACHE_DEFAULT_TTL: Default TTL in seconds (default: 3600)
            SUBAGENT_CACHE_MAX_ENTRIES: Max entries (default: 1000)

        Returns:
            CacheConfig from environment.
        """
        enabled_str = os.getenv("SUBAGENT_CACHE_ENABLED", "true").lower()
        enabled = enabled_str in ("true", "1", "yes")

        return cls(
            enabled=enabled,
            default_ttl=int(os.getenv("SUBAGENT_CACHE_DEFAULT_TTL", "3600")),
            agent_ttls={
                "rules": 3600 * 24,
                "state": 0,
                "action_space": 3600,
                "scenario": 3600 * 24,
            },
            max_entries=int(os.getenv("SUBAGENT_CACHE_MAX_ENTRIES", "1000")),
        )

    @classmethod
    def disabled(cls) -> "CacheConfig":
        """Create a disabled cache configuration.

        Returns:
            CacheConfig with caching disabled.
        """
        return cls(enabled=False)


# =============================================================================
# Cache Entry
# =============================================================================


@dataclass
class CacheEntry:
    """A cached response entry.

    Attributes:
        response: The cached SubagentResponse.
        created_at: Unix timestamp when entry was created.
        ttl: Time-to-live in seconds.
        agent_type: The agent type that generated this response.
        query_hash: Hash of the original query.
    """

    response: SubagentResponse
    created_at: float
    ttl: int
    agent_type: str
    query_hash: str

    def is_expired(self) -> bool:
        """Check if this cache entry has expired.

        Returns:
            True if expired, False if still valid.
        """
        if self.ttl <= 0:
            return True  # TTL of 0 means no caching
        return time.time() > (self.created_at + self.ttl)

    def time_remaining(self) -> float:
        """Get time remaining until expiration.

        Returns:
            Seconds remaining, or 0 if expired.
        """
        if self.ttl <= 0:
            return 0
        remaining = (self.created_at + self.ttl) - time.time()
        return max(0, remaining)


# =============================================================================
# Cache Metrics
# =============================================================================


@dataclass
class CacheMetrics:
    """Metrics for cache performance tracking.

    Attributes:
        hits: Number of cache hits.
        misses: Number of cache misses.
        evictions: Number of entries evicted due to max size.
        expirations: Number of entries expired.
    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0

    @property
    def total_requests(self) -> int:
        """Total number of cache requests."""
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as a percentage.

        Returns:
            Hit rate between 0.0 and 100.0, or 0.0 if no requests.
        """
        if self.total_requests == 0:
            return 0.0
        return (self.hits / self.total_requests) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary.

        Returns:
            Dictionary with all metrics.
        """
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "total_requests": self.total_requests,
            "hit_rate": round(self.hit_rate, 2),
        }


# =============================================================================
# Subagent Cache
# =============================================================================


class SubagentCache:
    """In-memory cache for subagent responses.

    This cache stores SubagentResponse objects keyed by agent type and
    query hash. It supports TTL-based expiration with per-agent-type
    configuration.

    Thread Safety:
        This implementation is NOT thread-safe. For multi-threaded usage,
        external synchronization or a thread-safe cache backend is needed.

    Example:
        cache = SubagentCache()

        # Check cache
        response = cache.get_cached_response("rules", "Can Roland include X?")
        if response:
            return response

        # Cache new response
        response = subagent.query(query, context)
        cache.cache_response("rules", query, response)
    """

    def __init__(self, config: CacheConfig | None = None):
        """Initialize the cache.

        Args:
            config: Cache configuration. If None, uses default config.
        """
        self.config = config or CacheConfig.default()
        self._cache: dict[str, CacheEntry] = {}
        self._metrics = CacheMetrics()

    def _hash_query(
        self,
        agent_type: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Generate a hash key for a query.

        The hash includes the agent type, query text, and relevant
        context fields to ensure different contexts don't collide.

        Args:
            agent_type: The subagent type.
            query: The query string.
            context: Optional context dictionary.

        Returns:
            SHA256 hash string for the cache key.
        """
        # Build hash input
        parts = [agent_type, query]

        # Include relevant context fields (exclude internal fields)
        if context:
            relevant_context = {
                k: v for k, v in sorted(context.items())
                if v is not None and not k.startswith("_")
            }
            if relevant_context:
                parts.append(str(relevant_context))

        hash_input = "|||".join(parts)
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def _get_ttl(self, agent_type: str) -> int:
        """Get the TTL for a specific agent type.

        Args:
            agent_type: The subagent type.

        Returns:
            TTL in seconds.
        """
        return self.config.agent_ttls.get(agent_type, self.config.default_ttl)

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache is at max capacity."""
        if self.config.max_entries <= 0:
            return  # Unlimited

        while len(self._cache) >= self.config.max_entries:
            # Find oldest entry
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].created_at,
            )
            del self._cache[oldest_key]
            self._metrics.evictions += 1

    def _clean_expired(self) -> None:
        """Remove expired entries from cache."""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            del self._cache[key]
            self._metrics.expirations += 1

    def get_cached_response(
        self,
        agent_type: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> SubagentResponse | None:
        """Get a cached response if available and not expired.

        Args:
            agent_type: The subagent type.
            query: The query string.
            context: Optional context dictionary.

        Returns:
            Cached SubagentResponse if found and valid, None otherwise.
        """
        if not self.config.enabled:
            self._metrics.misses += 1
            return None

        # Check if this agent type has caching disabled (TTL=0)
        if self._get_ttl(agent_type) <= 0:
            self._metrics.misses += 1
            return None

        cache_key = self._hash_query(agent_type, query, context)
        entry = self._cache.get(cache_key)

        if entry is None:
            self._metrics.misses += 1
            return None

        if entry.is_expired():
            # Remove expired entry
            del self._cache[cache_key]
            self._metrics.expirations += 1
            self._metrics.misses += 1
            return None

        self._metrics.hits += 1
        return entry.response

    def cache_response(
        self,
        agent_type: str,
        query: str,
        response: SubagentResponse,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Cache a subagent response.

        Args:
            agent_type: The subagent type.
            query: The query string.
            response: The SubagentResponse to cache.
            context: Optional context dictionary.
        """
        if not self.config.enabled:
            return

        ttl = self._get_ttl(agent_type)
        if ttl <= 0:
            return  # Don't cache if TTL is 0

        # Evict old entries if needed
        self._evict_if_needed()

        cache_key = self._hash_query(agent_type, query, context)
        self._cache[cache_key] = CacheEntry(
            response=response,
            created_at=time.time(),
            ttl=ttl,
            agent_type=agent_type,
            query_hash=cache_key,
        )

    def invalidate_cache(
        self,
        agent_type: str | None = None,
        query_pattern: str | None = None,
    ) -> int:
        """Invalidate cache entries matching criteria.

        Args:
            agent_type: If provided, only invalidate entries for this agent type.
            query_pattern: If provided, only invalidate entries whose query
                          hash contains this pattern (not commonly used).

        Returns:
            Number of entries invalidated.
        """
        if not self.config.enabled:
            return 0

        keys_to_remove = []

        for key, entry in self._cache.items():
            should_remove = True

            if agent_type is not None and entry.agent_type != agent_type:
                should_remove = False

            if query_pattern is not None and query_pattern not in entry.query_hash:
                should_remove = False

            if should_remove:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._cache[key]

        return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def get_metrics(self) -> CacheMetrics:
        """Get cache metrics.

        Returns:
            CacheMetrics with current statistics.
        """
        return self._metrics

    def reset_metrics(self) -> None:
        """Reset cache metrics to zero."""
        self._metrics = CacheMetrics()

    def size(self) -> int:
        """Get current number of cache entries.

        Returns:
            Number of entries in cache.
        """
        return len(self._cache)

    def get_entry_info(self, agent_type: str, query: str) -> dict[str, Any] | None:
        """Get detailed info about a specific cache entry.

        Useful for debugging and testing.

        Args:
            agent_type: The subagent type.
            query: The query string.

        Returns:
            Dictionary with entry info, or None if not found.
        """
        cache_key = self._hash_query(agent_type, query)
        entry = self._cache.get(cache_key)

        if entry is None:
            return None

        return {
            "agent_type": entry.agent_type,
            "query_hash": entry.query_hash,
            "created_at": entry.created_at,
            "ttl": entry.ttl,
            "time_remaining": entry.time_remaining(),
            "is_expired": entry.is_expired(),
        }


# =============================================================================
# Global cache instance
# =============================================================================


_default_cache: SubagentCache | None = None


def get_subagent_cache() -> SubagentCache:
    """Get the default subagent cache instance.

    Returns:
        SubagentCache singleton instance.
    """
    global _default_cache
    if _default_cache is None:
        _default_cache = SubagentCache(CacheConfig.from_env())
    return _default_cache


def reset_subagent_cache() -> None:
    """Reset the global cache instance.

    Useful for testing or reconfiguration.
    """
    global _default_cache
    _default_cache = None
