"""Tiny SQL migration runner — PROMPT.md §4 ("Postgres + numbered .sql
migrations run by a tiny runner"). No ORM, no alembic: migrations are
plain numbered .sql files in db/migrations/, applied in filename order,
each in its own transaction, tracked in a schema_migrations table so
reruns are idempotent.

Usage (from py/, via uv):
    uv run python -m ingest.migrate migrate
    uv run python -m ingest.migrate reset      # DROP SCHEMA public CASCADE, then migrate
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import psycopg

from ingest.db import get_connection

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"

_BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _migration_files() -> list[Path]:
    return sorted(p for p in MIGRATIONS_DIR.glob("*.sql") if p.is_file())


def _applied_versions(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(_BOOTSTRAP_SQL)
        conn.commit()
        cur.execute("SELECT version FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}


def migrate(conn: psycopg.Connection) -> list[str]:
    applied_now: list[str] = []
    already_applied = _applied_versions(conn)
    for path in _migration_files():
        version = path.name
        if version in already_applied:
            continue
        sql = path.read_text()
        with conn.cursor() as cur:
            try:
                cur.execute(sql)
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            except psycopg.Error:
                conn.rollback()
                logger.error("migration %s failed, rolled back", version)
                raise
        conn.commit()
        applied_now.append(version)
        logger.info("applied %s", version)
    return applied_now


def reset(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE")
        cur.execute("CREATE SCHEMA public")
    conn.commit()
    logger.info("schema reset (DROP SCHEMA public CASCADE; CREATE SCHEMA public)")


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if len(argv) != 1 or argv[0] not in {"migrate", "reset"}:
        print(__doc__)
        return 2

    with get_connection() as conn:
        if argv[0] == "reset":
            reset(conn)
        applied = migrate(conn)

    if applied:
        print(f"applied {len(applied)} migration(s): {', '.join(applied)}")
    else:
        print("no pending migrations")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
