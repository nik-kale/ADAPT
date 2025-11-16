"""
Tests for caching infrastructure.
"""

import pytest
import asyncio

from core.cache import SimpleCache, cached, get_cache


class TestSimpleCache:
    """Tests for SimpleCache"""

    @pytest.mark.asyncio
    async def test_basic_get_set(self):
        """Test basic cache get/set operations"""
        cache = SimpleCache()

        await cache.set("key1", "value1")
        result = await cache.get("key1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Test cache miss returns None"""
        cache = SimpleCache()

        result = await cache.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        """Test that entries expire after TTL"""
        cache = SimpleCache()

        await cache.set("key1", "value1", ttl_seconds=1)

        # Should exist immediately
        result1 = await cache.get("key1")
        assert result1 == "value1"

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Should be expired
        result2 = await cache.get("key1")
        assert result2 is None

    @pytest.mark.asyncio
    async def test_cache_delete(self):
        """Test deleting cache entries"""
        cache = SimpleCache()

        await cache.set("key1", "value1")
        deleted = await cache.delete("key1")

        assert deleted is True

        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Test clearing all cache entries"""
        cache = SimpleCache()

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()

        result1 = await cache.get("key1")
        result2 = await cache.get("key2")

        assert result1 is None
        assert result2 is None

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Test cache statistics"""
        cache = SimpleCache()

        # Some hits
        await cache.set("key1", "value1")
        await cache.get("key1")
        await cache.get("key1")

        # Some misses
        await cache.get("nonexistent1")
        await cache.get("nonexistent2")

        stats = await cache.get_stats()

        assert stats['hits'] == 2
        assert stats['misses'] == 2
        assert stats['hit_rate'] == 0.5
        assert stats['size'] == 1

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """Test LRU eviction when cache is full"""
        cache = SimpleCache(max_size=2)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")  # Should evict key1

        result1 = await cache.get("key1")
        result2 = await cache.get("key2")
        result3 = await cache.get("key3")

        assert result1 is None  # Evicted
        assert result2 == "value2"
        assert result3 == "value3"


class TestCachedDecorator:
    """Tests for @cached decorator"""

    @pytest.mark.asyncio
    async def test_function_caching(self):
        """Test that decorated function results are cached"""
        call_count = 0

        @cached(ttl_seconds=60)
        async def expensive_function(param):
            nonlocal call_count
            call_count += 1
            return f"result_{param}"

        # First call - should execute function
        result1 = await expensive_function("test")
        assert result1 == "result_test"
        assert call_count == 1

        # Second call with same param - should use cache
        result2 = await expensive_function("test")
        assert result2 == "result_test"
        assert call_count == 1  # Not incremented

        # Call with different param - should execute function
        result3 = await expensive_function("other")
        assert result3 == "result_other"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_cache_expiration_in_decorator(self):
        """Test that cached results expire after TTL"""
        call_count = 0

        @cached(ttl_seconds=1)
        async def short_lived_function(param):
            nonlocal call_count
            call_count += 1
            return f"result_{param}"

        # First call
        result1 = await short_lived_function("test")
        assert call_count == 1

        # Immediate second call - should use cache
        result2 = await short_lived_function("test")
        assert call_count == 1

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Call again - cache expired, should execute function
        result3 = await short_lived_function("test")
        assert call_count == 2
