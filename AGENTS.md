# Project Guidance

## Service purpose

This repository contains Cosmofy's curated Articles microservice. It is a FastAPI REST service consumed by Cosmofy's ordinary Java GraphQL API rather than directly owning a public client interface.

Its responsibilities are:

- Load and validate the Turso article catalog during application startup.
- Return stable article, author, and banner models with deterministic article IDs.
- Provide pagination, filtering, ordering, text search, and exact-ID retrieval.
- Cache repeated page queries in Redis using the database catalog digest as part of the cache identity.
- Apply simple Redis-backed rate limiting at the microservice boundary.
- Expose liveness/readiness endpoints and telemetry for the wider Cosmofy platform.

The Java GraphQL schema and mobile/web interfaces are outside this service's ownership. Do not add another database, an external article scraper, embeddings, or a GraphQL server unless explicitly requested.

## Architecture rules

- Keep the request path `GraphQL -> Articles microservice -> Redis/catalog` visible in traces.
- Load and validate the Turso catalog once through FastAPI lifespan state.
- Treat Redis cache failures as non-fatal for article retrieval.
- Fail open when Redis cannot enforce rate limits, but emit a structured warning.
- Keep deterministic IDs stable by deriving them from article metadata.
- Include the complete database catalog digest in page-cache identity so restarts after catalog changes invalidate stale pages automatically.

## Observability

Continue W3C trace context from Java GraphQL. Correlate structured logs with `trace_id`, `span_id`, and `request_id`. Telemetry goes to a private collector on each Oracle node, then to AWS X-Ray and CloudWatch. Never place AWS credentials in the application or expose collector ports publicly.

## Git commit convention

Every commit message must begin with one relevant emoji followed by a concise, entirely lowercase description. Do not use the green check-mark emoji.

Examples:

- `✨ add curated article catalog`
- `🐛 fix article filter ordering`
- `🧪 add catalog validation tests`
- `👷 configure production deployment`
