from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class ArticleOrdering(StrEnum):
    DATE_ASCENDING = "date"
    DATE_DESCENDING = "-date"
    TITLE_ASCENDING = "title"
    TITLE_DESCENDING = "-title"


class ArticleQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=24, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    search: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)
    source: str | None = None
    ordering: ArticleOrdering = ArticleOrdering.DATE_DESCENDING

    @field_validator("search", "source")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty")
        return normalized


class SourceAuthor(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str
    title: str
    image: HttpUrl


class SourceBanner(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    image: HttpUrl
    designer: str


class SourceArticle(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    month: int = Field(ge=1, le=12)
    year: int = Field(ge=1900, le=2100)
    title: str
    subtitle: str
    url: HttpUrl
    source: str
    banner: SourceBanner
    authors: list[SourceAuthor] = Field(min_length=1)


class ArticleAuthor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    title: str
    image: HttpUrl


class ArticleBanner(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image: HttpUrl
    designer: str


class Article(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    month: int = Field(ge=1, le=12)
    year: int = Field(ge=1900, le=2100)
    title: str
    subtitle: str
    url: HttpUrl
    source: str
    banner: ArticleBanner
    authors: list[ArticleAuthor] = Field(min_length=1)


class ArticlePage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_count: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    has_next_page: bool
    has_previous_page: bool
    articles: list[Article]
