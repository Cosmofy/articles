# Java GraphQL integration contract

## Ownership

Clients call Cosmofy's ordinary Java GraphQL API. Java calls this REST service. Clients must not call this service directly.

The Articles service owns catalog validation, deterministic IDs, filtering, pagination, Redis page caching, and Redis-backed rate limiting. Java must not connect to this service's Redis or read `articles.json` itself.

Production base URL: `https://articles.api.cosmofy.services.deployim.com`

## REST operations

### `GET /articles`

Optional query parameters:

| Name | Type | Default | Rules |
| --- | --- | --- | --- |
| `limit` | integer | `24` | `1..100` |
| `offset` | integer | `0` | At least `0` |
| `search` | string | omitted | Trimmed and non-empty |
| `year` | integer | omitted | `1900..2100` |
| `month` | integer | omitted | `1..12` |
| `source` | string | omitted | Exact case-insensitive source name |
| `ordering` | enum | `-date` | `date`, `-date`, `title`, or `-title` |

Successful body:

```json
{
  "total_count": 27,
  "limit": 24,
  "offset": 0,
  "has_next_page": true,
  "has_previous_page": false,
  "articles": [
    {
      "id": "e265a685-c093-5097-9337-fb1cdc73936c",
      "month": 8,
      "year": 2026,
      "title": "Example title",
      "subtitle": "Example subtitle",
      "url": "https://publisher.example/article",
      "source": "Quanta Magazine",
      "banner": {
        "image": "https://publisher.example/banner.jpg",
        "designer": "Designer Name"
      },
      "authors": [
        {
          "name": "Author Name",
          "title": "Staff Writer",
          "image": "https://publisher.example/author.jpg"
        }
      ]
    }
  ]
}
```

### `GET /articles/{article_id}`

Returns one article using the deterministic UUID from the page response. Unknown IDs return `ARTICLE_NOT_FOUND` with HTTP 404.

## Errors

```json
{
  "error": {
    "code": "INVALID_QUERY",
    "message": "The article query is invalid."
  }
}
```

Known codes are `INVALID_QUERY` (422), `ARTICLE_NOT_FOUND` (404), `RATE_LIMITED` (429), `INVALID_DATASET` (503), and `INTERNAL_ERROR` (500).

## Response metadata

Successful list responses return `X-Cache: HIT` or `MISS`. Exact article responses return `X-Cache: MEMORY`. Rate-limit headers and `x-request-id` are returned consistently. Java should capture these in telemetry without exposing them as article business fields.

## GraphQL integration

Livia preserves the existing client-facing `articles` field and adds IDs and pagination through backward-compatible schema additions. Its ordinary GraphQL model is:

```graphql
type Article {
  id: ID!
  month: Int!
  year: Int!
  title: String!
  subtitle: String!
  url: String!
  source: String!
  banner: ArticleBanner!
  authors: [ArticleAuthor!]!
}

type ArticleAuthor {
  name: String!
  title: String!
  image: String!
}

type ArticleBanner {
  image: String!
  designer: String!
}
```

Do not add duplicate Redis caching in Java. Forward W3C `traceparent`/`tracestate` and `x-request-id`, reuse Livia's managed HTTP client, and map snake_case transport fields. DGS federation schema transformation is disabled.
