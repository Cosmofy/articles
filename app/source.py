import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import TypeAdapter, ValidationError

from app.errors import Code, Error
from app.models import (
    Article,
    ArticleOrdering,
    ArticlePage,
    ArticleQuery,
    SourceArticle,
)

SOURCE_ARTICLES = TypeAdapter(list[SourceArticle])


class ArticleCatalog:
    def __init__(self, articles: list[Article], version: str):
        self.articles = tuple(articles)
        self.version = version
        self._articles_by_id = {article.id: article for article in articles}

        if len(self._articles_by_id) != len(self.articles):
            raise Error(Code.INVALID_DATASET)

    @property
    def count(self) -> int:
        return len(self.articles)

    def get(self, article_id: UUID) -> Article | None:
        return self._articles_by_id.get(article_id)

    def query(self, query: ArticleQuery) -> ArticlePage:
        articles = list(self.articles)

        if query.year is not None:
            articles = [article for article in articles if article.year == query.year]
        if query.month is not None:
            articles = [article for article in articles if article.month == query.month]
        if query.source is not None:
            source = query.source.casefold()
            articles = [
                article for article in articles if article.source.casefold() == source
            ]
        if query.search is not None:
            needle = query.search.casefold()
            articles = [
                article for article in articles if needle in _searchable_text(article)
            ]

        reverse = query.ordering in {
            ArticleOrdering.DATE_DESCENDING,
            ArticleOrdering.TITLE_DESCENDING,
        }
        if query.ordering in {
            ArticleOrdering.DATE_ASCENDING,
            ArticleOrdering.DATE_DESCENDING,
        }:
            articles.sort(
                key=lambda article: (
                    article.year,
                    article.month,
                    article.title.casefold(),
                ),
                reverse=reverse,
            )
        else:
            articles.sort(key=lambda article: article.title.casefold(), reverse=reverse)

        total_count = len(articles)
        page = articles[query.offset : query.offset + query.limit]
        return ArticlePage(
            total_count=total_count,
            limit=query.limit,
            offset=query.offset,
            has_next_page=query.offset + len(page) < total_count,
            has_previous_page=query.offset > 0 and total_count > 0,
            articles=page,
        )


def load_article_catalog(path: Path) -> ArticleCatalog:
    try:
        source_bytes = path.read_bytes()
        source_articles = SOURCE_ARTICLES.validate_json(source_bytes)
    except OSError, ValidationError:
        raise Error(Code.INVALID_DATASET)

    if not source_articles:
        raise Error(Code.INVALID_DATASET)

    return build_article_catalog(source_articles)


def build_article_catalog(source_articles: list[SourceArticle]) -> ArticleCatalog:
    if not source_articles:
        raise Error(Code.INVALID_DATASET)

    articles = [_normalize_article(article) for article in source_articles]
    canonical_articles = [
        article.model_dump(mode="json")
        for article in sorted(articles, key=lambda article: str(article.id))
    ]
    canonical_bytes = json.dumps(
        canonical_articles,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    version = hashlib.sha256(canonical_bytes).hexdigest()
    return ArticleCatalog(articles, version)


def _normalize_article(source: SourceArticle) -> Article:
    identity = (
        f"{source.year:04d}-{source.month:02d}:{source.title.strip()}:{source.url!s}"
    )
    return Article(
        id=uuid5(NAMESPACE_URL, identity),
        month=source.month,
        year=source.year,
        title=source.title.strip(),
        subtitle=source.subtitle.strip(),
        url=source.url,
        source=source.source.strip(),
        banner={
            "image": source.banner.image,
            "designer": source.banner.designer.strip(),
        },
        authors=[
            {
                "name": author.name.strip(),
                "title": author.title.strip(),
                "image": author.image,
            }
            for author in source.authors
        ],
    )


def _searchable_text(article: Article) -> str:
    values = [
        article.title,
        article.subtitle,
        article.source,
        article.banner.designer,
        *(author.name for author in article.authors),
        *(author.title for author in article.authors),
    ]
    return " ".join(values).casefold()
