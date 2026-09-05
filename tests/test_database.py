from unittest.mock import Mock

import pytest

from app import database
from app.errors import Code, Error

ARTICLE_ID = "170d27fd-b084-5f05-bcff-b254d44ae4a5"
EXPECTED_ID = "08a9352e-347b-5291-a8e6-d9daf105fff6"


class FakeConnection:
    def __init__(self, rows: list[tuple]):
        self.rows = rows
        self.closed = False

    def execute(self, _statement: str):
        result = Mock()
        result.fetchall.return_value = self.rows
        return result

    def close(self) -> None:
        self.closed = True


def article_rows(article_id: str = ARTICLE_ID) -> list[tuple]:
    article = (
        article_id,
        3,
        2026,
        "Maps of Black Holes",
        "A detailed look at the universe.",
        "https://example.com/black-holes",
        "Quanta Magazine",
        "https://example.com/banner.jpg",
        "Example Designer",
    )
    return [
        article
        + (
            0,
            "Ada Lovelace",
            "Staff Writer",
            "https://example.com/ada.jpg",
        )
    ]


def test_load_database_catalog_validates_rows_and_closes_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(article_rows(EXPECTED_ID))
    monkeypatch.setattr(database, "connect_database", lambda _settings=None: connection)

    catalog = database.load_database_catalog()

    assert catalog.count == 1
    assert str(catalog.articles[0].id) == EXPECTED_ID
    assert catalog.articles[0].authors[0].name == "Ada Lovelace"
    assert connection.closed is True


def test_load_database_catalog_rejects_ids_that_do_not_match_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection(article_rows())
    monkeypatch.setattr(database, "connect_database", lambda _settings=None: connection)

    with pytest.raises(Error) as raised:
        database.load_database_catalog()

    assert raised.value.code is Code.INVALID_DATASET


def test_load_database_catalog_rejects_empty_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection([])
    monkeypatch.setattr(database, "connect_database", lambda _settings=None: connection)

    with pytest.raises(Error) as raised:
        database.load_database_catalog()

    assert raised.value.code is Code.INVALID_DATASET
