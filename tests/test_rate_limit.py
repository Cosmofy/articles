import asyncio
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError

from app.cache import check_rate_limit, rate_limit_key


def test_rate_limit_key_hides_identity() -> None:
    identity = "graphql-service"
    key = rate_limit_key(identity, 60)

    assert key.startswith("cosmofy:articles:v1:rate-limit:60:")
    assert identity not in key


def test_rate_limit_allows_and_rejects() -> None:
    redis_client = AsyncMock()
    redis_client.eval.side_effect = [[3, 42], [11, 35]]

    allowed = asyncio.run(
        check_rate_limit(redis_client, "graphql", limit=10, window_seconds=60)
    )
    rejected = asyncio.run(
        check_rate_limit(redis_client, "graphql", limit=10, window_seconds=60)
    )

    assert allowed.allowed is True
    assert allowed.remaining == 7
    assert allowed.reset_after_seconds == 42
    assert rejected.allowed is False
    assert rejected.remaining == 0


def test_rate_limit_fails_open_when_redis_is_unavailable() -> None:
    redis_client = AsyncMock()
    redis_client.eval.side_effect = ConnectionError("unavailable")

    result = asyncio.run(
        check_rate_limit(redis_client, "graphql", limit=10, window_seconds=60)
    )

    assert result.allowed is True
    assert result.remaining == 10
    assert result.enforced is False


@pytest.mark.parametrize(
    "arguments",
    [
        {"caller_identity": "", "limit": 10, "window_seconds": 60},
        {"caller_identity": "graphql", "limit": 0, "window_seconds": 60},
        {"caller_identity": "graphql", "limit": 10, "window_seconds": 0},
    ],
)
def test_rate_limit_rejects_invalid_configuration(arguments: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        asyncio.run(check_rate_limit(AsyncMock(), **arguments))
