"""SEC ticker -> CIK map ingester — PROMPT.md §3.1, §12 Phase 2.

Seeds `issuers` from https://www.sec.gov/files/company_tickers.json, the
one bulk endpoint that gives every SEC-registered ticker/CIK/name triple
in a single request. This is deliberately not built on the §6 dispatch-
parser architecture (that's for the many structurally-different Form 4
variants) — there is exactly one shape of response here.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg

from config.env import require_env
from ingest.db import get_connection

logger = logging.getLogger(__name__)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
TIMEOUT_SECONDS = 30


def _user_agent() -> str:
    contact = require_env("SIGNAL_DESK_CONTACT_EMAIL")
    return f"SignalDesk/0.1 ({contact})"


@dataclass(frozen=True)
class IssuerRow:
    cik: int
    ticker: str
    name: str


def fetch_company_tickers() -> dict[str, Any]:
    req = urllib.request.Request(TICKERS_URL, headers={"User-Agent": _user_agent()})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        body = resp.read()
    result: dict[str, Any] = json.loads(body)
    return result


def parse_company_tickers(raw: dict[str, Any]) -> list[IssuerRow]:
    rows = []
    for entry in raw.values():
        cik = entry.get("cik_str")
        ticker = entry.get("ticker")
        name = entry.get("title")
        if cik is None or not ticker or not name:
            continue
        rows.append(IssuerRow(cik=int(cik), ticker=str(ticker).upper(), name=str(name)))
    return rows


def validate(rows: list[IssuerRow]) -> tuple[list[IssuerRow], list[str]]:
    valid: list[IssuerRow] = []
    rejected: list[str] = []
    seen_ciks: set[int] = set()
    for row in rows:
        if row.cik <= 0:
            rejected.append(f"cik {row.cik}: non-positive CIK")
            continue
        if row.cik in seen_ciks:
            rejected.append(f"cik {row.cik}: duplicate within this fetch, keeping first")
            continue
        if not row.ticker.strip():
            rejected.append(f"cik {row.cik}: empty ticker")
            continue
        if not row.name.strip():
            rejected.append(f"cik {row.cik}: empty name")
            continue
        seen_ciks.add(row.cik)
        valid.append(row)
    return valid, rejected


UPSERT_CHUNK_SIZE = 500


def upsert_issuers(conn: psycopg.Connection, rows: list[IssuerRow]) -> int:
    # One multi-row INSERT per chunk instead of one round trip per row —
    # ~7,995 individual round trips to Neon took several minutes; chunked,
    # it's ~16 round trips. Still fully parameterized (no string-built
    # values), just a repeated placeholder pattern.
    with conn.cursor() as cur:
        for start in range(0, len(rows), UPSERT_CHUNK_SIZE):
            chunk = rows[start : start + UPSERT_CHUNK_SIZE]
            placeholders = ", ".join(["(%s, %s, %s, now())"] * len(chunk))
            params: list[object] = []
            for row in chunk:
                params.extend([row.cik, row.ticker, row.name])
            cur.execute(
                f"""
                INSERT INTO issuers (cik, ticker, name, updated_at)
                VALUES {placeholders}
                ON CONFLICT (cik) DO UPDATE
                    SET ticker = EXCLUDED.ticker,
                        name = EXCLUDED.name,
                        updated_at = now()
                """,
                params,
            )
    conn.commit()
    return len(rows)


def run(conn: psycopg.Connection) -> int:
    started_at = datetime.now(UTC)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ingest_log (source, started_at, status) VALUES (%s, %s, 'running') "
            "RETURNING id",
            ("sec_tickers", started_at),
        )
        row = cur.fetchone()
        assert row is not None
        log_id = row[0]
    conn.commit()

    try:
        raw = fetch_company_tickers()
        parsed = parse_company_tickers(raw)
        valid, rejected = validate(parsed)
        if rejected:
            sample = rejected[:5]
            logger.warning(
                "sec_tickers: %d rows rejected during validation (sample of %d): %s",
                len(rejected),
                len(sample),
                sample,
            )
        written = upsert_issuers(conn, valid)
    except (urllib.error.URLError, psycopg.Error) as e:
        logger.error("sec_tickers ingest failed: %s", e)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE ingest_log SET finished_at = %s, status = 'failed', error = %s "
                "WHERE id = %s",
                (datetime.now(UTC), str(e), log_id),
            )
        conn.commit()
        raise

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE ingest_log SET finished_at = %s, status = 'success', "
            "rows_in = %s, rows_written = %s WHERE id = %s",
            (datetime.now(UTC), len(parsed), written, log_id),
        )
    conn.commit()
    logger.info("sec_tickers: wrote %d issuers (%d rejected)", written, len(rejected))
    return written


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    start = time.monotonic()
    with get_connection() as conn:
        written = run(conn)
    logger.info("done in %.1fs", time.monotonic() - start)
    return 0 if written > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
