from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi.testclient import TestClient

from app.cache import RateLimitResult
from app.main import app


def allowed_rate_limit() -> RateLimitResult:
    return RateLimitResult(
        allowed=True,
        limit=120,
        remaining=119,
        reset_after_seconds=45,
    )


def request_articles(path: str = "/articles"):
    return (
        patch(
            "app.routers.articles.check_rate_limit",
            new=AsyncMock(return_value=allowed_rate_limit()),
        ),
        patch(
            "app.routers.articles.get_cached_page",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.routers.articles.cache_page",
            new=AsyncMock(return_value=True),
        ),
    )


def test_articles_returns_bundled_catalog_page() -> None:
    rate_limit, cached, cache = request_articles()
    with TestClient(app) as client, rate_limit, cached, cache:
        response = client.get("/articles")

    assert response.status_code == 200
    assert response.json()["total_count"] == 27
    assert len(response.json()["articles"]) == 24
    assert response.headers["X-Cache"] == "MISS"
    assert response.headers["RateLimit-Limit"] == "120"
    assert UUID(response.json()["articles"][0]["id"])


def test_articles_filters_and_paginates() -> None:
    rate_limit, cached, cache = request_articles()
    with TestClient(app) as client, rate_limit, cached, cache:
        response = client.get(
            "/articles",
            params={"year": 2026, "limit": 2, "offset": 1, "search": "universe"},
        )

    assert response.status_code == 200
    assert response.json()["limit"] == 2
    assert response.json()["offset"] == 1
    assert all(article["year"] == 2026 for article in response.json()["articles"])


def test_articles_uses_valid_cached_page() -> None:
    with (
        TestClient(app) as client,
        patch(
            "app.routers.articles.check_rate_limit",
            new=AsyncMock(return_value=allowed_rate_limit()),
        ),
        patch(
            "app.routers.articles.get_cached_page",
            new=AsyncMock(),
        ) as cached,
        patch("app.routers.articles.cache_page", new=AsyncMock()) as cache,
    ):
        page = app.state.catalog.query(apply_default_query())
        cached.return_value = page.model_dump(mode="json")
        response = client.get("/articles")

    assert response.status_code == 200
    assert response.headers["X-Cache"] == "HIT"
    cache.assert_not_awaited()


def apply_default_query():
    from app.models import ArticleQuery

    return ArticleQuery()


def test_invalid_cached_page_falls_back_to_catalog() -> None:
    with (
        TestClient(app) as client,
        patch(
            "app.routers.articles.check_rate_limit",
            new=AsyncMock(return_value=allowed_rate_limit()),
        ),
        patch(
            "app.routers.articles.get_cached_page",
            new=AsyncMock(return_value={"invalid": True}),
        ),
        patch(
            "app.routers.articles.cache_page",
            new=AsyncMock(return_value=True),
        ) as cache,
    ):
        response = client.get("/articles")

    assert response.status_code == 200
    assert response.headers["X-Cache"] == "MISS"
    cache.assert_awaited_once()


def test_exact_article_and_not_found() -> None:
    with TestClient(app) as client:
        article_id = app.state.catalog.articles[0].id
        with patch(
            "app.routers.articles.check_rate_limit",
            new=AsyncMock(return_value=allowed_rate_limit()),
        ):
            found = client.get(f"/articles/{article_id}")
            missing = client.get("/articles/00000000-0000-0000-0000-000000000000")

    assert found.status_code == 200
    assert found.headers["X-Cache"] == "MEMORY"
    assert found.json()["id"] == str(article_id)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ARTICLE_NOT_FOUND"


def test_invalid_query_uses_stable_error_envelope() -> None:
    with TestClient(app) as client:
        response = client.get("/articles?month=13")

    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "INVALID_QUERY", "message": "The article query is invalid."}
    }


def test_rate_limit_rejection_returns_headers() -> None:
    result = RateLimitResult(
        allowed=False,
        limit=120,
        remaining=0,
        reset_after_seconds=31,
    )
    with (
        TestClient(app) as client,
        patch(
            "app.routers.articles.check_rate_limit", new=AsyncMock(return_value=result)
        ),
    ):
        response = client.get("/articles")

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert response.headers["Retry-After"] == "31"
    assert response.headers["RateLimit-Remaining"] == "0"


def test_health_endpoints() -> None:
    with TestClient(app) as client:
        app.state.redis_client = AsyncMock()
        app.state.redis_client.ping.return_value = True
        live = client.get("/health/live")
        ready = client.get("/health/ready")

    assert live.json() == {
        "status": "ok",
        "app": "Cosmofy Articles API",
        "version": "1.0.0",
    }
    assert ready.status_code == 200
    assert ready.json()["article_count"] == 27
    assert ready.json()["dependencies"] == {"catalog": "ok", "redis": "ok"}
