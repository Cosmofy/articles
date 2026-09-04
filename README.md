# articles

Curated astronomy and physics article microservice for Cosmofy. The FastAPI service validates the bundled catalog, provides filtering and pagination, and serves Cosmofy's Java GraphQL federation.

Production: `https://articles.api.cosmofy.services.deployim.com`

```text
Java GraphQL federation -> rate limit -> Redis page cache -> in-memory validated catalog
```

The dataset is versioned by its SHA-256 digest. Deploying a changed `data/articles.json` automatically produces new Redis keys, so old cached pages cannot hide a catalog update.

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
- `GET /health/ready` checks the validated catalog and Redis.

Run `uv run pytest -v` for the complete suite. The Java integration contract is in [`docs/GRAPHQL_FEDERATION.md`](docs/GRAPHQL_FEDERATION.md).
