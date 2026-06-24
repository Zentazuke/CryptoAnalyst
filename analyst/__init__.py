"""Crypto Analyst — a standalone, verifiable crypto analytics tool.

A0 (Foundation): ingest live OHLCV from Crypto.com, persist to DuckDB with
full provenance, archive raw payloads for replay, and detect data gaps.
Trust is a first-class subsystem: every datapoint carries its source and the
time it was ingested, and quality checks gate what we believe.
"""

__version__ = "0.1.0"
