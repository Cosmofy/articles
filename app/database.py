from collections import defaultdict

from opentelemetry import trace
from opentelemetry.trace import SpanKind
from pydantic import ValidationError
import turso_serverless
from turso_serverless import Connection

from app.config import Settings
from app.errors import Code, Error
from app.models import SourceArticle
from app.source import ArticleCatalog, build_article_catalog

tracer = trace.get_tracer(__name__)


def database_span_attributes(operation: str, table: str) -> dict[str, str]:
    return {
        "db.system.name": "turso",
        "db.namespace": "articles",
        "db.operation.name": operation,
        "db.collection.name": table,
    }


def connect_database(settings: Settings | None = None) -> Connection:
    resolved_settings = settings or Settings()
    return turso_serverless.connect(
        resolved_settings.turso_database_url,
        auth_token=resolved_settings.turso_auth_token,
    )


def load_database_catalog(settings: Settings | None = None) -> ArticleCatalog:
    with tracer.start_as_current_span(
        "turso.articles.select",
        kind=SpanKind.CLIENT,
        attributes=database_span_attributes("SELECT", "articles"),
    ) as span:
        connection = connect_database(settings)
        try:
            rows = connection.execute(
                """
                SELECT
                    article.id,
                    article.month,
                    article.year,
                    article.title,
                    article.subtitle,
                    article.url,
                    article.source,
                    article.banner_image,
                    article.banner_designer,
                    author.position,
                    author.name,
                    author.title,
                    author.image
                FROM articles AS article
                LEFT JOIN article_authors AS author
                  ON author.article_id = article.id
                ORDER BY article.id, author.position
                """
            ).fetchall()
            span.set_attribute("db.response.returned_rows", len(rows))
        finally:
            connection.close()

    if not rows:
        raise Error(Code.INVALID_DATASET)

    authors_by_article: dict[str, list[dict[str, object]]] = defaultdict(list)
    articles_by_id: dict[str, tuple] = {}
    for row in rows:
        article_id = str(row[0])
        articles_by_id[article_id] = row
        if row[9] is not None:
            authors_by_article[article_id].append(
                {"name": row[10], "title": row[11], "image": row[12]}
            )

    try:
        source_articles = [
            SourceArticle.model_validate(
                {
                    "month": row[1],
                    "year": row[2],
                    "title": row[3],
                    "subtitle": row[4],
                    "url": row[5],
                    "source": row[6],
                    "banner": {"image": row[7], "designer": row[8]},
                    "authors": authors_by_article[article_id],
                }
            )
            for article_id, row in articles_by_id.items()
        ]
        catalog = build_article_catalog(source_articles)
    except ValidationError as exception:
        raise Error(Code.INVALID_DATASET) from exception

    if {str(article.id) for article in catalog.articles} != set(articles_by_id):
        raise Error(Code.INVALID_DATASET)
    return catalog


def check_database() -> bool:
    with tracer.start_as_current_span(
        "turso.articles.readiness",
        kind=SpanKind.CLIENT,
        attributes=database_span_attributes("SELECT", "articles"),
    ):
        connection = connect_database()
        try:
            return connection.execute("SELECT 1").fetchone() == (1,)
        finally:
            connection.close()
