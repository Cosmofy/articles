import logging
from uuid import UUID

from fastapi import APIRouter, Request, Response
from opentelemetry import trace
from opentelemetry.trace import Span
from pydantic import ValidationError

from app.cache import (
    RateLimitResult,
    cache_page,
    check_rate_limit,
    get_cached_page,
)
from app.errors import Code, Error
from app.models import Article, ArticleOrdering, ArticlePage, ArticleQuery

router = APIRouter(prefix="/articles", tags=["articles"])
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def _set_rate_limit_headers(response: Response, result: RateLimitResult) -> None:
    response.headers["RateLimit-Limit"] = str(result.limit)
    response.headers["RateLimit-Remaining"] = str(result.remaining)
    response.headers["RateLimit-Reset"] = str(result.reset_after_seconds)


async def _enforce_rate_limit(request: Request, response: Response) -> RateLimitResult:
    settings = request.app.state.settings
    caller_identity = request.client.host if request.client else "unknown"
    result = await check_rate_limit(
        request.app.state.redis_client,
        caller_identity,
        limit=settings.articles_rate_limit_requests,
        window_seconds=settings.articles_rate_limit_window_seconds,
    )
    _set_rate_limit_headers(response, result)

    if not result.allowed:
        logger.warning(
            msg="article request rate limited",
            extra={
                "event": "articles.rate_limit.rejected",
                "rate_limit_remaining": result.remaining,
                "rate_limit_enforced": result.enforced,
            },
        )
        raise Error(
            Code.RATE_LIMITED,
            headers={
                "Retry-After": str(result.reset_after_seconds),
                "RateLimit-Limit": str(result.limit),
                "RateLimit-Remaining": str(result.remaining),
                "RateLimit-Reset": str(result.reset_after_seconds),
            },
        )
    return result


def _record_page_result(
    span: Span,
    *,
    source: str,
    page: ArticlePage,
    query: ArticleQuery,
    rate_limit: RateLimitResult,
) -> None:
    span.set_attribute("articles.result.source", source)
    span.set_attribute("articles.result.count", len(page.articles))
    logger.info(
        msg="articles retrieved",
        extra={
            "event": "articles.retrieved",
            "source": source,
            "cache_status": "hit" if source == "redis" else "miss",
            "article_count": len(page.articles),
            "limit": query.limit,
            "offset": query.offset,
            "ordering": query.ordering.value,
            "has_search": query.search is not None,
            "year": query.year,
            "month": query.month,
            "rate_limit_remaining": rate_limit.remaining,
            "rate_limit_enforced": rate_limit.enforced,
        },
    )


@router.get(
    path="",
    status_code=200,
    summary="retrieve curated articles",
    response_model=ArticlePage,
)
async def get_articles(
    request: Request,
    response: Response,
    limit: int = 24,
    offset: int = 0,
    search: str | None = None,
    year: int | None = None,
    month: int | None = None,
    source: str | None = None,
    ordering: ArticleOrdering = ArticleOrdering.DATE_DESCENDING,
) -> ArticlePage:
    try:
        query = ArticleQuery(
            limit=limit,
            offset=offset,
            search=search,
            year=year,
            month=month,
            source=source,
            ordering=ordering,
        )
    except ValidationError:
        raise Error(Code.INVALID_QUERY)

    rate_limit = await _enforce_rate_limit(request, response)
    catalog = request.app.state.catalog
    parameters = query.model_dump(mode="json", exclude_none=True)

    with tracer.start_as_current_span(
        "articles.pipeline",
        attributes={
            "articles.request.limit": query.limit,
            "articles.request.offset": query.offset,
            "articles.request.has_search": query.search is not None,
            "articles.request.has_source": query.source is not None,
            "articles.request.has_year": query.year is not None,
            "articles.request.has_month": query.month is not None,
            "articles.request.ordering": query.ordering.value,
            "articles.rate_limit.result": "allowed",
            "articles.rate_limit.enforced": rate_limit.enforced,
        },
    ) as span:
        cached_page = await get_cached_page(
            request.app.state.redis_client,
            parameters,
            catalog.version,
        )
        if cached_page is not None:
            try:
                page = ArticlePage.model_validate(cached_page)
            except ValidationError:
                page = None
            if page is not None:
                response.headers["X-Cache"] = "HIT"
                span.set_attribute("articles.cache.outcome", "hit")
                _record_page_result(
                    span,
                    source="redis",
                    page=page,
                    query=query,
                    rate_limit=rate_limit,
                )
                return page

        response.headers["X-Cache"] = "MISS"
        span.set_attribute("articles.cache.outcome", "miss")
        page = catalog.query(query)
        cached = await cache_page(
            request.app.state.redis_client,
            parameters,
            catalog.version,
            page.model_dump(mode="json"),
            ttl_seconds=request.app.state.settings.articles_cache_ttl_seconds,
        )
        span.set_attribute("articles.cache.write", "success" if cached else "error")
        _record_page_result(
            span,
            source="catalog",
            page=page,
            query=query,
            rate_limit=rate_limit,
        )
        return page


@router.get(
    path="/{article_id}",
    status_code=200,
    summary="retrieve one curated article",
    response_model=Article,
)
async def get_article(
    article_id: UUID,
    request: Request,
    response: Response,
) -> Article:
    await _enforce_rate_limit(request, response)
    article = request.app.state.catalog.get(article_id)
    if article is None:
        raise Error(Code.ARTICLE_NOT_FOUND)

    response.headers["X-Cache"] = "MEMORY"
    logger.info(
        msg="article retrieved",
        extra={
            "event": "article.retrieved",
            "source": "catalog",
            "article_id": str(article.id),
        },
    )
    return article
