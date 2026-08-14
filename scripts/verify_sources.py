#!/usr/bin/env python3
"""Phase 0 recon: probe every data source endpoint in PROMPT.md Section 3
with a lightweight, single-row/HEAD-class request and print a PASS/FAIL
table. Read-only. No writes, no auth, no scraping beyond one probe per
endpoint. Exit code is nonzero if any REQUIRED source fails.
"""
from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta

CONTACT_EMAIL = "aminielijah11@gmail.com"
SEC_UA = f"SignalDesk/0.1 ({CONTACT_EMAIL})"
GENERIC_UA = f"SignalDesk/0.1 recon probe ({CONTACT_EMAIL})"

TIMEOUT = 15


@dataclass
class Probe:
    group: str
    name: str
    url: str
    required: bool
    headers: dict[str, str]
    note: str = ""


def _last_published_index_url() -> str:
    # Today's daily-index file is often not yet published (pre-close) and a
    # 403/404 on *today's* file is not evidence the endpoint is dead. Probe
    # the most recent weekday instead, which is what a real backfill job
    # would actually request.
    d = date.today() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    q = (d.month - 1) // 3 + 1
    return (
        f"https://www.sec.gov/Archives/edgar/daily-index/{d.year}/QTR{q}/"
        f"form.{d.strftime('%Y%m%d')}.idx"
    )


def _recent_finra_url() -> str:
    # FINRA short volume files are only published for trading days and lag
    # by ~1 day; walk back until we build a plausible URL (existence is
    # checked by the actual request, not here).
    d = date.today() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{d.strftime('%Y%m%d')}.txt"


PROBES: list[Probe] = [
    Probe(
        "SEC EDGAR",
        "real-time filing index (Form 4 atom feed)",
        "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&output=atom",
        True,
        {"User-Agent": SEC_UA},
    ),
    Probe(
        "SEC EDGAR",
        "daily index (.idx)",
        _last_published_index_url(),
        True,
        {"User-Agent": SEC_UA},
        note="most recent weekday's index (today's file is often not yet published)",
    ),
    Probe(
        "SEC EDGAR",
        "full text search (EFTS)",
        "https://efts.sec.gov/LATEST/search-index?q=%22Form%204%22&forms=4",
        True,
        {"User-Agent": SEC_UA},
    ),
    Probe(
        "SEC EDGAR",
        "company submissions JSON (AAPL CIK 0000320193)",
        "https://data.sec.gov/submissions/CIK0000320193.json",
        True,
        {"User-Agent": SEC_UA},
    ),
    Probe(
        "SEC EDGAR",
        "ticker -> CIK map",
        "https://www.sec.gov/files/company_tickers.json",
        True,
        {"User-Agent": SEC_UA},
    ),
    Probe(
        "Congress (Senate)",
        "eFD search landing page",
        "https://efdsearch.senate.gov/search/",
        True,
        {"User-Agent": GENERIC_UA},
        note="requires session/CSRF cookie flow to actually search; probing landing page only",
    ),
    Probe(
        "Congress (House)",
        "Financial Disclosure landing page",
        "https://disclosures-clerk.house.gov/FinancialDisclosure",
        True,
        {"User-Agent": GENERIC_UA},
    ),
    Probe(
        "Congress mirror",
        "senate-stock-watcher-data (raw.githubusercontent)",
        "https://raw.githubusercontent.com/timothycarambat/senate-stock-watcher-data/master/aggregate/all_transactions.json",
        False,
        {"User-Agent": GENERIC_UA},
    ),
    Probe(
        "Congress mirror",
        "house-stock-watcher-data (raw.githubusercontent, TattooedHead fork)",
        "https://raw.githubusercontent.com/TattooedHead/house-stock-watcher-data/master/data/all_transactions.json",
        False,
        {"User-Agent": GENERIC_UA},
        note="original timothycarambat/house-stock-watcher-data repo is gone (404); this is the "
        "actively-maintained successor found during Phase 0 recon (last push within 24h)",
    ),
    Probe(
        "Congress enrichment",
        "unitedstates/congress-legislators (current members YAML)",
        "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-current.yaml",
        True,
        {"User-Agent": GENERIC_UA},
    ),
    Probe(
        "FINRA",
        "daily short sale volume (CNMSshvol)",
        _recent_finra_url(),
        True,
        {"User-Agent": GENERIC_UA},
        note="most recent weekday; a single day's 404 does not mean the source is dead",
    ),
    Probe(
        "CBOE",
        "daily market statistics",
        "https://www.cboe.com/us/options/market_statistics/daily/",
        False,
        {"User-Agent": GENERIC_UA},
        note="page structure must be hand-verified in Phase 7; probing reachability only",
    ),
    Probe(
        "FRED",
        "series metadata (DGS10) — no key required for this probe",
        "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
        True,
        {"User-Agent": GENERIC_UA},
        note="the CSV endpoint works without a key; the JSON API needs a free key (see accounts list)",
    ),
    Probe(
        "Prices",
        "Stooq EOD CSV (AAPL) — free, no key, no official rate policy",
        "https://stooq.com/q/d/l/?s=aapl.us&i=d",
        False,
        {"User-Agent": GENERIC_UA},
        note="candidate cross-check source alongside yfinance",
    ),
]


def probe(p: Probe) -> tuple[bool, str]:
    req = urllib.request.Request(p.url, headers=p.headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read(256)
            return True, f"HTTP {resp.status}, {len(body)}B+ read"
    except urllib.error.HTTPError as e:
        # A 404 on a date-specific endpoint (today's index/short-vol file)
        # is often "not published yet", not "endpoint gone" — surfaced via
        # the probe's note, not silently treated as PASS.
        return False, f"HTTP {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return False, f"URLError {e.reason}"
    except Exception as e:  # noqa: BLE001 — recon script, not production ingest code
        return False, f"{type(e).__name__}: {e}"


def main() -> int:
    rows = []
    any_required_failed = False
    for p in PROBES:
        ok, detail = probe(p)
        if not ok and p.required:
            any_required_failed = True
        rows.append((p.group, p.name, "PASS" if ok else "FAIL", detail, p.required, p.note))
        time.sleep(0.3)  # be polite even during a recon pass

    group_w = max(len(r[0]) for r in rows)
    name_w = max(len(r[1]) for r in rows)
    print(f"{'GROUP':<{group_w}}  {'ENDPOINT':<{name_w}}  {'REQ':<3}  RESULT  DETAIL")
    print("-" * (group_w + name_w + 60))
    for group, name, status, detail, required, note in rows:
        req_flag = "yes" if required else "no"
        print(f"{group:<{group_w}}  {name:<{name_w}}  {req_flag:<3}  {status:<6}  {detail}")
        if note:
            print(f"{'':<{group_w}}  note: {note}")

    print()
    if any_required_failed:
        print("RESULT: one or more REQUIRED sources FAILED. Investigate before Phase 1.")
        return 1
    print("RESULT: all REQUIRED sources reachable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
