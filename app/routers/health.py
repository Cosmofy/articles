import logging
from asyncio import to_thread

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from redis import RedisError
from turso_serverless import Error as TursoError

from app.database import check_database

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger(__name__)


@router.get(path="/live", status_code=200, summary="app liveness check")
def live(request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "app": request.app.title,
            "version": request.app.version,
        },
    )


@router.get(path="/ready", status_code=200, summary="app readiness check")
async def ready(request: Request) -> JSONResponse:
    try:
        logger.info(
            msg="checking redis readiness",
            extra={"event": "articles.readiness.redis", "dependency": "articles:redis"},
        )
        redis_ready = bool(await request.app.state.redis_client.ping())
    except RedisError, OSError:
        redis_ready = False
        logger.exception(
            msg="redis readiness check failed",
            extra={
                "event": "articles.readiness.redis.failed",
                "dependency": "articles:redis",
            },
        )

    try:
        logger.info(
            msg="checking turso readiness",
            extra={"event": "articles.readiness.turso", "dependency": "articles:turso"},
        )
        turso_ready = await to_thread(check_database)
    except TursoError, OSError:
        turso_ready = False
        logger.exception(
            msg="turso readiness check failed",
            extra={
                "event": "articles.readiness.turso.failed",
                "dependency": "articles:turso",
            },
        )

    catalog_ready = request.app.state.catalog.count > 0
    dependencies = {
        "catalog": "ok" if catalog_ready else "unavailable",
        "redis": "ok" if redis_ready else "unavailable",
        "turso": "ok" if turso_ready else "unavailable",
    }
    if redis_ready and turso_ready and catalog_ready:
        return JSONResponse(
            status_code=200,
            content={
                "status": "ready",
                "dependencies": dependencies,
                "article_count": request.app.state.catalog.count,
            },
        )

    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "dependencies": dependencies},
    )
