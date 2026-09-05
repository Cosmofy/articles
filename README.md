# articles

Curated astronomy and physics article microservice for Cosmofy. The FastAPI service loads and validates its Turso catalog, provides filtering and pagination, and serves Cosmofy's Java GraphQL API.

Production: `https://articles.api.cosmofy.services.deployim.com`

```text
Java GraphQL -> rate limit -> Redis page cache -> in-memory validated Turso catalog
```

The validated database contents are versioned by a SHA-256 digest. Restarting the service after a catalog change automatically produces new Redis keys, so old cached pages cannot hide an update.

## Local development

```bash
uv sync --dev
uv run uvicorn app.main:app --reload --port 29403
```

API documentation is available at `http://127.0.0.1:29403/docs`.

Endpoints:

- `GET /articles` retrieves a page with optional search, year, month, source, and ordering filters.
- `GET /articles/{article_id}` retrieves one exact article.
- `GET /health/live` checks the FastAPI process.
- `GET /health/ready` checks the validated catalog, Turso, and Redis.

Set `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` in `.env`, then run `uv run pytest -v` for the complete suite. The Java integration contract is in [`docs/GRAPHQL_FEDERATION.md`](docs/GRAPHQL_FEDERATION.md).

## Catalog import

The checked-in JSON file is the validated seed used to initialize or intentionally replace the Turso catalog; the running service never reads it. Apply `migrations/001_create_articles.sql`, then run:

```bash
uv run python -m scripts.import_articles data/articles.json
```
