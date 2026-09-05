import argparse
from pathlib import Path

from app.database import connect_database
from app.source import load_article_catalog


def import_articles(path: Path) -> int:
    catalog = load_article_catalog(path)
    connection = connect_database()
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM article_authors")
        connection.execute("DELETE FROM articles")
        for article in catalog.articles:
            connection.execute(
                """
                INSERT INTO articles (
                    id, month, year, title, subtitle, url, source,
                    banner_image, banner_designer
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(article.id),
                    article.month,
                    article.year,
                    article.title,
                    article.subtitle,
                    str(article.url),
                    article.source,
                    str(article.banner.image),
                    article.banner.designer,
                ),
            )
            for position, author in enumerate(article.authors):
                connection.execute(
                    """
                    INSERT INTO article_authors (
                        article_id, position, name, title, image
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(article.id),
                        position,
                        author.name,
                        author.title,
                        str(author.image),
                    ),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return catalog.count


def main() -> None:
    parser = argparse.ArgumentParser(description="Replace the Turso article catalog.")
    parser.add_argument("path", nargs="?", type=Path, default=Path("data/articles.json"))
    args = parser.parse_args()
    count = import_articles(args.path)
    print(f"imported {count} articles")


if __name__ == "__main__":
    main()
