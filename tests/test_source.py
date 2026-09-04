import json
from pathlib import Path

import pytest

from app.errors import Code, Error
from app.models import ArticleOrdering, ArticleQuery
from app.source import load_article_catalog


def source_article(
    *,
    month: int = 3,
    year: int = 2026,
    title: str = "Maps of Black Holes",
    url: str = "https://example.com/black-holes",
) -> dict[str, object]:
    return {
        "month": month,
        "year": year,
        "title": title,
        "subtitle": "A detailed look at the universe.",
        "url": url,
        "source": "Quanta Magazine",
        "banner": {
            "image": "https://example.com/banner.jpg",
            "designer": "  Example Designer  ",
        },
        "authors": [
            {
                "name": "  Ada Lovelace  ",
                "title": "  Staff Writer  ",
                "image": "https://example.com/ada.jpg",
            }
        ],
    }


def write_catalog(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_bundled_catalog_is_valid_and_complete() -> None:
    catalog = load_article_catalog(Path("data/articles.json"))

    assert catalog.count == 27
    assert len(catalog.version) == 64


def test_catalog_generates_stable_ids_and_normalizes_whitespace(tmp_path: Path) -> None:
    path = tmp_path / "articles.json"
    write_catalog(path, [source_article()])

    first = load_article_catalog(path)
    second = load_article_catalog(path)
    article = first.articles[0]

    assert article.id == second.articles[0].id
    assert article.banner.designer == "Example Designer"
    assert article.authors[0].name == "Ada Lovelace"
    assert first.get(article.id) == article


def test_dataset_digest_changes_with_content(tmp_path: Path) -> None:
    path = tmp_path / "articles.json"
    write_catalog(path, [source_article()])
    first = load_article_catalog(path)
    write_catalog(path, [source_article(title="A Different Article")])
    second = load_article_catalog(path)

    assert first.version != second.version


def test_catalog_filters_search_year_month_and_source(tmp_path: Path) -> None:
    path = tmp_path / "articles.json"
    write_catalog(
        path,
        [
            source_article(),
            source_article(
                month=8,
                year=2025,
                title="Planet Formation",
                url="https://example.com/planets",
            ),
        ],
    )
    catalog = load_article_catalog(path)

    assert catalog.query(ArticleQuery(search="ada")).total_count == 2
    assert catalog.query(ArticleQuery(search="black holes")).total_count == 1
    assert catalog.query(ArticleQuery(year=2025, month=8)).total_count == 1
    assert catalog.query(ArticleQuery(source="quanta magazine")).total_count == 2


def test_catalog_paginates_and_orders(tmp_path: Path) -> None:
    path = tmp_path / "articles.json"
    write_catalog(
        path,
        [
            source_article(year=2024, title="Alpha", url="https://example.com/a"),
            source_article(year=2026, title="Charlie", url="https://example.com/c"),
            source_article(year=2025, title="Bravo", url="https://example.com/b"),
        ],
    )
    catalog = load_article_catalog(path)

    newest = catalog.query(ArticleQuery(limit=1))
    alphabetical = catalog.query(
        ArticleQuery(limit=2, offset=1, ordering=ArticleOrdering.TITLE_ASCENDING)
    )

    assert newest.articles[0].title == "Charlie"
    assert newest.has_next_page is True
    assert alphabetical.total_count == 3
    assert [article.title for article in alphabetical.articles] == ["Bravo", "Charlie"]
    assert alphabetical.has_previous_page is True


@pytest.mark.parametrize("payload", [[], {}, [{"title": "incomplete"}]])
def test_invalid_catalog_is_rejected(tmp_path: Path, payload: object) -> None:
    path = tmp_path / "articles.json"
    write_catalog(path, payload)

    with pytest.raises(Error) as raised:
        load_article_catalog(path)

    assert raised.value.code is Code.INVALID_DATASET


def test_missing_catalog_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(Error) as raised:
        load_article_catalog(tmp_path / "missing.json")

    assert raised.value.code is Code.INVALID_DATASET
