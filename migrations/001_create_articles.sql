PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    year INTEGER NOT NULL CHECK (year BETWEEN 1900 AND 2100),
    title TEXT NOT NULL,
    subtitle TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT NOT NULL,
    banner_image TEXT NOT NULL,
    banner_designer TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS article_authors (
    article_id TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK (position >= 0),
    name TEXT NOT NULL,
    title TEXT NOT NULL,
    image TEXT NOT NULL,
    PRIMARY KEY (article_id, position)
);

CREATE INDEX IF NOT EXISTS articles_date_idx ON articles(year, month);
CREATE INDEX IF NOT EXISTS articles_source_idx ON articles(source);
