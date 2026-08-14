"""Shared Postgres connection helper for ingesters.

Every ingester connects through here rather than reading DATABASE_URL
itself, so there's one place that owns connection setup (autocommit off
by default — callers commit explicitly, matching CONTRACT.md's
transaction-per-run requirement).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from config.env import load_env, require_env


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    load_env()
    dsn = require_env("DATABASE_URL")
    conn = psycopg.connect(dsn)
    try:
        yield conn
    finally:
        conn.close()
