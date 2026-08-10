import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "regulations.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS regulations (
    id            INTEGER PRIMARY KEY,
    seq           INTEGER NOT NULL,
    title         TEXT NOT NULL,
    category_l0   TEXT,
    category_l1   TEXT,
    department    TEXT,
    enact_date    TEXT,
    status        TEXT NOT NULL DEFAULT '현행',
    source_pages  TEXT
);

CREATE TABLE IF NOT EXISTS amendments (
    id             INTEGER PRIMARY KEY,
    regulation_id  INTEGER NOT NULL REFERENCES regulations(id),
    amend_date     TEXT NOT NULL,
    ordinal        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS articles (
    id             INTEGER PRIMARY KEY,
    regulation_id  INTEGER NOT NULL REFERENCES regulations(id),
    chapter        TEXT,
    section        TEXT,
    gwan           TEXT,
    no             INTEGER NOT NULL,
    sub_no         INTEGER,
    title          TEXT,
    body           TEXT NOT NULL,
    ordinal        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS addenda (
    id             INTEGER PRIMARY KEY,
    regulation_id  INTEGER NOT NULL REFERENCES regulations(id),
    line           TEXT NOT NULL,
    ordinal        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS attachments (
    id             INTEGER PRIMARY KEY,
    regulation_id  INTEGER NOT NULL REFERENCES regulations(id),
    label          TEXT NOT NULL,
    start_page     INTEGER,
    end_page       INTEGER,
    lines_json     TEXT NOT NULL,
    rows_json      TEXT,
    file_url       TEXT,
    ordinal        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS revisions (
    id             INTEGER PRIMARY KEY,
    regulation_id  INTEGER NOT NULL REFERENCES regulations(id),
    revised_at     TEXT NOT NULL,
    summary        TEXT,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS revision_changes (
    id             INTEGER PRIMARY KEY,
    revision_id    INTEGER NOT NULL REFERENCES revisions(id),
    article_no     INTEGER NOT NULL,
    article_sub_no INTEGER,
    article_title  TEXT,
    old_body       TEXT,
    new_body       TEXT,
    ordinal        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_sessions (
    token       TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_amendments_reg ON amendments(regulation_id);
CREATE INDEX IF NOT EXISTS idx_revisions_reg ON revisions(regulation_id);
CREATE INDEX IF NOT EXISTS idx_revision_changes_rev ON revision_changes(revision_id);
CREATE INDEX IF NOT EXISTS idx_articles_reg ON articles(regulation_id);
CREATE INDEX IF NOT EXISTS idx_addenda_reg ON addenda(regulation_id);
CREATE INDEX IF NOT EXISTS idx_attachments_reg ON attachments(regulation_id);
CREATE INDEX IF NOT EXISTS idx_regulations_cat ON regulations(category_l0, category_l1);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.executescript(SCHEMA)

    tokenize = "trigram"
    try:
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS regulations_fts "
            f"USING fts5(title, body, tokenize='{tokenize}')"
        )
    except sqlite3.OperationalError:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS regulations_fts "
            "USING fts5(title, body)"
        )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"DB initialized at {DB_PATH}")
