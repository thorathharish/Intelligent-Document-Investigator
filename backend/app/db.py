"""SQLite access: one connection per thread, WAL mode, schema bootstrap (LLD section 4)."""
import sqlite3
import threading

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS investigations (
  id          TEXT PRIMARY KEY,
  title       TEXT NOT NULL,
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
  id                TEXT PRIMARY KEY,
  investigation_id  TEXT NOT NULL REFERENCES investigations(id),
  filename          TEXT NOT NULL,
  ext               TEXT NOT NULL,
  stored_path       TEXT NOT NULL,
  sha256            TEXT NOT NULL,
  size_bytes        INTEGER NOT NULL,
  status            TEXT NOT NULL,
  error_message     TEXT,
  page_count        INTEGER,
  extraction_method TEXT,
  chunk_count       INTEGER DEFAULT 0,
  created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_inv ON documents(investigation_id);

CREATE TABLE IF NOT EXISTS chunks (
  id                TEXT PRIMARY KEY,
  document_id       TEXT NOT NULL REFERENCES documents(id),
  investigation_id  TEXT NOT NULL,
  ordinal           INTEGER NOT NULL,
  page              INTEGER,
  section           TEXT,
  paragraph_index   INTEGER NOT NULL,
  text              TEXT NOT NULL,
  text_hash         TEXT NOT NULL,
  extraction_method TEXT NOT NULL,
  ocr_confidence    REAL,
  embedding         BLOB
);
CREATE INDEX IF NOT EXISTS idx_chunks_inv ON chunks(investigation_id);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id, ordinal);

CREATE TABLE IF NOT EXISTS runs (
  id                TEXT PRIMARY KEY,
  investigation_id  TEXT NOT NULL REFERENCES investigations(id),
  question          TEXT NOT NULL,
  cache_key         TEXT NOT NULL,
  state             TEXT NOT NULL,
  degraded          INTEGER NOT NULL DEFAULT 0,
  result_json       TEXT NOT NULL,
  model             TEXT,
  latency_ms        INTEGER,
  created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_inv   ON runs(investigation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_runs_cache ON runs(cache_key);
"""

_local = threading.local()


def get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(settings.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


def init_db() -> None:
    for folder in (settings.data_dir, settings.uploads_dir, settings.recordings_dir):
        folder.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()


def query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    return get_conn().execute(sql, params).fetchall()


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    return get_conn().execute(sql, params).fetchone()


def execute(sql: str, params: tuple = ()) -> None:
    conn = get_conn()
    conn.execute(sql, params)
    conn.commit()
