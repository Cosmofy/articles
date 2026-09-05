import os
from pathlib import Path

import pytest

os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("TURSO_DATABASE_URL", "libsql://test.example.com")
os.environ.setdefault("TURSO_AUTH_TOKEN", "test-token")


@pytest.fixture(autouse=True)
def stub_runtime_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.source import load_article_catalog

    monkeypatch.setattr(
        "app.main.load_database_catalog",
        lambda _settings: load_article_catalog(Path("data/articles.json")),
    )
    monkeypatch.setattr("app.routers.health.check_database", lambda: True)
