import asyncio
import json
from unittest.mock import AsyncMock

from redis.exceptions import ConnectionError

from app.cache import (
    PAGE_CACHE_TTL_SECONDS,
    cache_page,
    get_cached_page,
    page_cache_key,
)


def test_page_cache_key_is_deterministic_and_namespaced() -> None:
    first = page_cache_key({"limit": 20, "year": 2026}, "dataset-a")
    second = page_cache_key({"year": 2026, "limit": 20}, "dataset-a")

    assert first == second
    assert first.startswith("cosmofy:articles:v1:cache:page:")


def test_page_cache_key_changes_for_query_or_dataset() -> None:
    assert page_cache_key({"year": 2025}, "a") != page_cache_key({"year": 2026}, "a")
    assert page_cache_key({"year": 2026}, "a") != page_cache_key({"year": 2026}, "b")


def test_cached_page_hit_and_miss() -> None:
    redis_client = AsyncMock()
    redis_client.get.side_effect = [b'{"articles":[],"total_count":0}', None]

    hit = asyncio.run(get_cached_page(redis_client, {"limit": 24}, "dataset"))
    miss = asyncio.run(get_cached_page(redis_client, {"limit": 24}, "dataset"))

    assert hit == {"articles": [], "total_count": 0}
    assert miss is None


def test_cache_page_writes_canonical_json_with_ttl() -> None:
    redis_client = AsyncMock()
    page = {"total_count": 0, "articles": []}
    parameters = {"limit": 24}

    written = asyncio.run(cache_page(redis_client, parameters, "dataset", page))

    assert written is True
    redis_client.set.assert_awaited_once_with(
        name=page_cache_key(parameters, "dataset"),
        value=json.dumps(
            page,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
        ex=PAGE_CACHE_TTL_SECONDS,
    )


def test_invalid_cache_is_deleted() -> None:
    redis_client = AsyncMock()
    redis_client.get.return_value = b"not-json"

    result = asyncio.run(get_cached_page(redis_client, {"limit": 24}, "dataset"))

    assert result is None
    redis_client.delete.assert_awaited_once()


def test_redis_cache_failures_are_non_fatal() -> None:
    redis_client = AsyncMock()
    redis_client.get.side_effect = ConnectionError("unavailable")
    redis_client.set.side_effect = ConnectionError("unavailable")

    read = asyncio.run(get_cached_page(redis_client, {"limit": 24}, "dataset"))
    written = asyncio.run(
        cache_page(redis_client, {"limit": 24}, "dataset", {"articles": []})
    )

    assert read is None
    assert written is False
