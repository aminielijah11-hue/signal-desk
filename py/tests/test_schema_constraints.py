"""Live-DB proof that the schema's constraints actually hold — not just
that the SQL parses. Runs against DATABASE_URL (Neon locally, the CI
Postgres service in Actions). Every test opens its own connection and
rolls back unconditionally in teardown, so nothing persists either way.

The first test is PROMPT.md §4/§12 Phase 2's mandated acceptance
criterion: "a test proves inserting an ocr row with needs_review=false
raises."
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg
import pytest

from ingest.db import get_connection


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set — no live database to test constraints against")
    with get_connection() as connection:
        yield connection
        connection.rollback()


def _seed_congress_member(conn: psycopg.Connection, bioguide_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO congress_members (bioguide_id, name, chamber) VALUES (%s, %s, %s)",
            (bioguide_id, "Test Member", "house"),
        )


def _insert_congress_trade(
    conn: psycopg.Connection, bioguide_id: str, provenance: str, needs_review: bool
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO congress_trades
                (bioguide_id, txn_date, disclosed_at, type, amount_low, amount_high,
                 amount_bracket_id, source_url, provenance, needs_review)
            VALUES
                (%s, '2026-01-01', '2026-01-10', 'P', 1001, 15000, 1,
                 'https://example.com/ptr.pdf', %s, %s)
            """,
            (bioguide_id, provenance, needs_review),
        )


def test_ocr_row_with_needs_review_false_is_rejected(conn: psycopg.Connection) -> None:
    _seed_congress_member(conn, "T000001")
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert_congress_trade(conn, "T000001", provenance="ocr", needs_review=False)


def test_ocr_row_with_needs_review_true_is_accepted(conn: psycopg.Connection) -> None:
    _seed_congress_member(conn, "T000002")
    _insert_congress_trade(conn, "T000002", provenance="ocr", needs_review=True)  # must not raise


def test_ocr_low_conf_without_review_is_also_rejected(conn: psycopg.Connection) -> None:
    _seed_congress_member(conn, "T000003")
    with pytest.raises(psycopg.errors.CheckViolation):
        _insert_congress_trade(conn, "T000003", provenance="ocr_low_conf", needs_review=False)


def test_html_provenance_does_not_require_review(conn: psycopg.Connection) -> None:
    _seed_congress_member(conn, "T000004")
    _insert_congress_trade(conn, "T000004", provenance="html", needs_review=False)  # must not raise


def test_negative_insider_trade_price_is_rejected(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO issuers (cik, name) VALUES (9999001, 'Test Issuer')")
        cur.execute(
            "INSERT INTO insiders (owner_cik, name, first_seen, last_seen) "
            "VALUES (9999002, 'Test Insider', '2026-01-01', '2026-01-01')"
        )
        cur.execute(
            "INSERT INTO form4_filings (accession, issuer_cik, filed_at, period_of_report) "
            "VALUES ('0000000000-26-000001', 9999001, now(), '2026-01-01')"
        )
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute("""
                INSERT INTO insider_trades
                    (accession, owner_cik, issuer_cik, txn_date, code, shares, price, provenance)
                VALUES
                    ('0000000000-26-000001', 9999002, 9999001, '2026-01-01', 'P', 100, -5, 'xml')
                """)


def test_prices_daily_high_below_low_is_rejected(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO issuers (cik, name) VALUES (9999003, 'Test Issuer 2')")
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute("""
                INSERT INTO prices_daily (cik, d, open, high, low, close, adj_close, volume)
                VALUES (9999003, '2026-01-01', 10, 5, 20, 10, 10, 100)
                """)
