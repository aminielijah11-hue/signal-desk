from __future__ import annotations

from ingest.sources.sec_tickers import IssuerRow, parse_company_tickers, validate

SAMPLE_RAW = {
    "0": {"cik_str": 320193, "ticker": "aapl", "title": "Apple Inc."},
    "1": {"cik_str": 1045810, "ticker": "nvda", "title": "NVIDIA CORP"},
    "2": {"cik_str": None, "ticker": "BAD1", "title": "Missing CIK"},
    "3": {"cik_str": 123, "ticker": "", "title": "Empty Ticker"},
    "4": {"cik_str": 456, "ticker": "BAD2"},  # missing title entirely
}


def test_parse_uppercases_ticker_and_skips_incomplete_rows():
    rows = parse_company_tickers(SAMPLE_RAW)
    assert IssuerRow(cik=320193, ticker="AAPL", name="Apple Inc.") in rows
    assert IssuerRow(cik=1045810, ticker="NVDA", name="NVIDIA CORP") in rows
    # missing cik_str, empty ticker, and missing title were all dropped at parse time
    assert len(rows) == 2


def test_validate_rejects_non_positive_cik():
    rows = [IssuerRow(cik=0, ticker="ZERO", name="Zero Cik Co")]
    valid, rejected = validate(rows)
    assert valid == []
    assert len(rejected) == 1
    assert "non-positive" in rejected[0]


def test_validate_rejects_duplicate_cik_keeping_first():
    rows = [
        IssuerRow(cik=1, ticker="FIRST", name="First"),
        IssuerRow(cik=1, ticker="SECOND", name="Second"),
    ]
    valid, rejected = validate(rows)
    assert len(valid) == 1
    assert valid[0].ticker == "FIRST"
    assert len(rejected) == 1
    assert "duplicate" in rejected[0]


def test_validate_rejects_blank_name():
    rows = [IssuerRow(cik=1, ticker="X", name="   ")]
    valid, rejected = validate(rows)
    assert valid == []
    assert "empty name" in rejected[0]


def test_validate_accepts_clean_row():
    rows = [IssuerRow(cik=320193, ticker="AAPL", name="Apple Inc.")]
    valid, rejected = validate(rows)
    assert valid == rows
    assert rejected == []
