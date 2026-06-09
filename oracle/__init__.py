"""
World Cup Oracle — Week 1: honesty harness scaffold.

Package layout:
  oracle.db          — DuckDB connection factory + schema init
  oracle.teams       — 48-team canonical ID + alias resolver
  oracle.ingest.*    — raw data ingestion skeletons
  oracle.scoring.*   — RPS / log-loss / Brier / de-vig
  oracle.harness.*   — CLV tracking + backtest harness
"""
