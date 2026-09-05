from contextlib import asynccontextmanager
from asyncio import to_thread

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.config import Settings
from app.database import load_database_catalog
from app.errors import Error, handle_error, handle_validation_error
from app.observability import configure_logging, log_requests
from app.routers import articles, health
from app.telemetry import configure_telemetry

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Check whether the articles service and its dependencies are available.",
    },
    {
        "name": "articles",
        "description": "Retrieve Cosmofy's curated astronomy and physics articles.",
    },
]

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    catalog = await to_thread(load_database_catalog, settings)
    async with redis.from_url(settings.redis_url) as redis_client:
        app.state.settings = settings
        app.state.catalog = catalog
        app.state.redis_client = redis_client
        yield


app = FastAPI(
    lifespan=lifespan,  # loads the catalog and opens Redis at startup, then closes Redis at shutdown
    title="Cosmofy Articles API",
    summary="Retrieve Cosmofy's curated astronomy and physics articles.",  # short explanation displayed near the API title
    description="Provides validated, searchable, cached, and rate-limited article data to Cosmofy's Java GraphQL service.",  # longer explanation displayed on the documentation page
    version="1.0.0",
    openapi_tags=OPENAPI_TAGS,  # describes and orders endpoint groups in the documentation
    terms_of_service="https://github.com/Cosmofy/articles",
    contact={"name": "Cosmofy", "url": "https://github.com/Cosmofy"},
    license_info={"name": "Proprietary"},
)
configure_telemetry(app)
app.middleware("http")(log_requests)
app.add_exception_handler(Error, handle_error)
app.add_exception_handler(RequestValidationError, handle_validation_error)
app.include_router(health.router)
app.include_router(articles.router)
