import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

ARTICLES_REDIS_NAMESPACE = "cosmofy:articles:v1"
PAGE_CACHE_TTL_SECONDS = 3600
RATE_LIMIT_REQUESTS = 120
RATE_LIMIT_WINDOW_SECONDS = 60


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_after_seconds: int
    enforced: bool = True


_RATE_LIMIT_SCRIPT = """
local count = redis.call("INCR", KEYS[1])
local ttl = redis.call("TTL", KEYS[1])

if count == 1 or ttl < 0 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
    ttl = tonumber(ARGV[1])
end

return {count, ttl}
"""


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def page_cache_key(parameters: Mapping[str, object], dataset_version: str) -> str:
    cache_identity = {"dataset": dataset_version, "query": parameters}
    fingerprint = hashlib.sha256(
        _canonical_json(cache_identity).encode("utf-8")
    ).hexdigest()
    return f"{ARTICLES_REDIS_NAMESPACE}:cache:page:{fingerprint}"


def rate_limit_key(caller_identity: str, window_seconds: int) -> str:
    if not caller_identity:
        raise ValueError("caller_identity must not be empty")
    if window_seconds <= 0:
        raise ValueError("window_seconds must be greater than zero")

    fingerprint = hashlib.sha256(caller_identity.encode("utf-8")).hexdigest()
    return f"{ARTICLES_REDIS_NAMESPACE}:rate-limit:{window_seconds}:{fingerprint}"


async def get_cached_page(
    client: Redis,
    parameters: Mapping[str, object],
    dataset_version: str,
) -> dict[str, Any] | None:
    try:
        key = page_cache_key(parameters, dataset_version)
        cached_page = await client.get(name=key)
    except RedisError, OSError, TypeError, ValueError:
        logger.warning(
            msg="article page cache read failed",
            extra={
                "event": "articles.cache.read_failed",
                "dependency": "articles:redis",
            },
            exc_info=True,
        )
        return None

    if cached_page is None:
        return None

    try:
        page = json.loads(cached_page)
        if not isinstance(page, dict):
            raise TypeError("cached article page must be a JSON object")
        return page
    except json.JSONDecodeError, TypeError, UnicodeDecodeError, ValueError:
        logger.warning(
            msg="discarding invalid article page cache entry",
            extra={
                "event": "articles.cache.invalid",
                "dependency": "articles:redis",
                "cache_key": key,
            },
        )
        try:
            await client.delete(key)
        except RedisError, OSError:
            logger.warning(
                msg="invalid article cache entry could not be deleted",
                extra={
                    "event": "articles.cache.delete_failed",
                    "dependency": "articles:redis",
                    "cache_key": key,
                },
                exc_info=True,
            )
        return None


async def cache_page(
    client: Redis,
    parameters: Mapping[str, object],
    dataset_version: str,
    page: Mapping[str, object],
    ttl_seconds: int = PAGE_CACHE_TTL_SECONDS,
) -> bool:
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be greater than zero")

    try:
        key = page_cache_key(parameters, dataset_version)
        await client.set(name=key, value=_canonical_json(page), ex=ttl_seconds)
        return True
    except RedisError, OSError, TypeError, ValueError:
        logger.warning(
            msg="article page cache write failed",
            extra={
                "event": "articles.cache.write_failed",
                "dependency": "articles:redis",
            },
            exc_info=True,
        )
        return False


async def check_rate_limit(
    client: Redis,
    caller_identity: str,
    limit: int = RATE_LIMIT_REQUESTS,
    window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
) -> RateLimitResult:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    key = rate_limit_key(caller_identity, window_seconds)
    try:
        result = await client.eval(_RATE_LIMIT_SCRIPT, 1, key, window_seconds)
        count, ttl = (int(value) for value in result)
    except RedisError, OSError, TypeError, ValueError:
        logger.warning(
            msg="article rate limit unavailable; allowing request",
            extra={
                "event": "articles.rate_limit.fail_open",
                "dependency": "articles:redis",
            },
            exc_info=True,
        )
        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=limit,
            reset_after_seconds=window_seconds,
            enforced=False,
        )

    return RateLimitResult(
        allowed=count <= limit,
        limit=limit,
        remaining=max(0, limit - count),
        reset_after_seconds=max(1, ttl),
    )
