import pytest
from pydantic import ValidationError

from app.models import ArticleOrdering, ArticleQuery


def test_article_query_has_stable_defaults() -> None:
    query = ArticleQuery()

    assert query.limit == 24
    assert query.offset == 0
    assert query.ordering is ArticleOrdering.DATE_DESCENDING
    assert query.search is None
    assert query.year is None
    assert query.month is None
    assert query.source is None


def test_article_query_normalizes_text_filters() -> None:
    query = ArticleQuery(search="  black holes  ", source="  Quanta Magazine ")

    assert query.search == "black holes"
    assert query.source == "Quanta Magazine"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("limit", 0),
        ("limit", 101),
        ("offset", -1),
        ("search", "   "),
        ("source", ""),
        ("year", 1899),
        ("year", 2101),
        ("month", 0),
        ("month", 13),
        ("ordering", "popular"),
    ],
)
def test_article_query_rejects_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        ArticleQuery.model_validate({field: value})


def test_article_query_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ArticleQuery.model_validate({"provider_page": 2})
