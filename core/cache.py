"""
Caching layer for ADAPT framework.

Provides in-memory caching with TTL support to improve performance
by avoiding redundant computations and data fetches.
"""

from typing import Any, Optional, Callable
from functools import wraps
from datetime import datetime, timedelta
import hashlib
import json
import asyncio
import pickle


class CacheEntry:
    """Cache entry with TTL"""

    def __init__(self, value: Any, ttl_seconds: int = 300):
        """
        Initialize cache entry.

        Args:
            value: Value to cache
            ttl_seconds: Time-to-live in seconds
        """
        self.value = value
        self.expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        self.created_at = datetime.utcnow()
        self.hit_count = 0

    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return datetime.utcnow() > self.expires_at

    def touch(self):
        """Update hit count"""
        self.hit_count += 1


class SimpleCache:
    """
    Simple in-memory cache with TTL support.

    Thread-safe cache implementation for caching function results,
    API responses, and other data.
    """

    def __init__(self, max_size: int = 1000):
        """
        Initialize cache.

        Args:
            max_size: Maximum number of entries to cache
        """
        self._cache: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self.max_size = max_size
        self.stats = {'hits': 0, 'misses': 0, 'evictions': 0}

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        async with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self.stats['misses'] += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                self.stats['misses'] += 1
                return None

            entry.touch()
            self.stats['hits'] += 1
            return entry.value

    async def set(self, key: str, value: Any, ttl_seconds: int = 300):
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds
        """
        async with self._lock:
            # Evict if cache is full
            if len(self._cache) >= self.max_size and key not in self._cache:
                await self._evict_lru()

            self._cache[key] = CacheEntry(value, ttl_seconds)

    async def delete(self, key: str) -> bool:
        """
        Delete entry from cache.

        Args:
            key: Cache key

        Returns:
            True if entry was deleted, False if not found
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self):
        """Clear all cache entries"""
        async with self._lock:
            self._cache.clear()
            self.stats = {'hits': 0, 'misses': 0, 'evictions': 0}

    async def _evict_lru(self):
        """Evict least recently used entry"""
        if not self._cache:
            return

        # Find entry with oldest creation time and no recent hits
        lru_key = min(
            self._cache.keys(),
            key=lambda k: (self._cache[k].hit_count, self._cache[k].created_at)
        )

        del self._cache[lru_key]
        self.stats['evictions'] += 1

    async def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary of cache stats
        """
        async with self._lock:
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = self.stats['hits'] / total_requests if total_requests > 0 else 0

            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'evictions': self.stats['evictions'],
                'hit_rate': hit_rate,
                'total_requests': total_requests,
            }

    async def cleanup_expired(self):
        """Remove all expired entries"""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)


# Global cache instance
_cache = SimpleCache()


def get_cache() -> SimpleCache:
    """Get the global cache instance"""
    return _cache


def cached(ttl_seconds: int = 300, key_func: Optional[Callable] = None):
    """
    Decorator for caching async function results.

    Args:
        ttl_seconds: Time-to-live for cached results
        key_func: Optional function to generate cache key from args

    Returns:
        Decorator function

    Example:
        @cached(ttl_seconds=60)
        async def fetch_data(param1, param2):
            # expensive operation
            return result
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: hash of function name + args
                try:
                    # Try to serialize args for hashing
                    args_str = pickle.dumps((args, sorted(kwargs.items())))
                    key_data = f"{func.__module__}.{func.__name__}:{hashlib.md5(args_str).hexdigest()}"
                except (TypeError, pickle.PicklingError):
                    # Fallback to string representation
                    key_data = f"{func.__module__}.{func.__name__}:{str(args)}:{str(kwargs)}"

                cache_key = hashlib.md5(key_data.encode()).hexdigest()

            # Try cache
            cached_value = await _cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            await _cache.set(cache_key, result, ttl_seconds)

            return result

        return wrapper

    return decorator


def cache_key_from_args(*args, **kwargs) -> str:
    """
    Generate cache key from function arguments.

    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Cache key string
    """
    try:
        args_str = pickle.dumps((args, sorted(kwargs.items())))
        return hashlib.md5(args_str).hexdigest()
    except (TypeError, pickle.PicklingError):
        return hashlib.md5(f"{args}:{kwargs}".encode()).hexdigest()
