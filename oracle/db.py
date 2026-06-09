"""DuckDB connection factory and schema initialisation."""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import duckdb

# Default: project-local file; override with env var in CI or tests.
_DEFAULT_DB = Path(__file__).parent.parent / "data" / "oracle.duckdb"
DB_PATH = Path(os.environ.get("ORACLE_DB_PATH", _DEFAULT_DB))

_CREATE_SCHEMA = """
-- append-only raw results from martj42 (natural key: date + teams)
CREATE TABLE IF NOT EXISTS results (
    date          DATE        NOT NULL,
    home_team     TEXT        NOT NULL,
    away_team     TEXT        NOT NULL,
    home_score    INTEGER,
    away_score    INTEGER,
    tournament    TEXT,
    city          TEXT,
    country       TEXT,
    neutral       BOOLEAN,
    home_team_id  TEXT,          -- canonical team id (resolved)
    away_team_id  TEXT
);

-- 2026 fixture list (Week 11 canonical schema)
CREATE TABLE IF NOT EXISTS fixtures (
    match_id        TEXT PRIMARY KEY,
    stage           TEXT,           -- 'group', 'r32', 'r16', 'qf', 'sf', 'final', 'third_place'
    group_name      TEXT,           -- null for knockouts
    home_team       TEXT,
    away_team       TEXT,
    kickoff_at      TIMESTAMP,      -- null until official schedule available
    venue           TEXT,
    city            TEXT,
    host_country    TEXT,           -- 'USA' | 'Canada' | 'Mexico'
    source          TEXT,           -- e.g. 'placeholder_wc2026_groups_v1' | 'official_fifa_2026'
    is_placeholder  BOOLEAN         -- true until official data replaces the row
);

-- market odds snapshots (append-only; each row is one snapshot)
CREATE TABLE IF NOT EXISTS market_snapshots (
    snapshot_id   TEXT       NOT NULL,
    fixture_id    TEXT       NOT NULL,
    captured_at   TIMESTAMP  NOT NULL,
    bookmaker     TEXT       NOT NULL,
    market        TEXT       NOT NULL,  -- '1x2', 'ou25', 'btts', etc.
    outcome       TEXT       NOT NULL,  -- 'home', 'draw', 'away', 'over', 'under', ...
    decimal_odds  DOUBLE     NOT NULL,
    PRIMARY KEY (snapshot_id, outcome)
);

-- model predictions (one row per outcome per match)
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id TEXT       NOT NULL,
    fixture_id    TEXT       NOT NULL,
    predicted_at  TIMESTAMP  NOT NULL,
    model_version TEXT       NOT NULL,
    market        TEXT       NOT NULL,
    outcome       TEXT       NOT NULL,
    probability   DOUBLE     NOT NULL,
    PRIMARY KEY (prediction_id, outcome)
);

-- scoring results written after the match
CREATE TABLE IF NOT EXISTS scores (
    score_id      TEXT PRIMARY KEY,
    fixture_id    TEXT      NOT NULL,
    scored_at     TIMESTAMP NOT NULL,
    model_version TEXT      NOT NULL,
    metric        TEXT      NOT NULL,  -- 'rps', 'log_loss', 'brier', 'clv'
    value         DOUBLE    NOT NULL,
    notes         TEXT
);

-- 48-team canonical reference
CREATE TABLE IF NOT EXISTS teams (
    team_id      TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    confederation TEXT NOT NULL  -- UEFA, CONMEBOL, AFC, CAF, CONCACAF, OFC
);
"""


@contextmanager
def get_conn(db_path: Path | str | None = None) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Yield a DuckDB connection, initialising the schema on first use.

    Pass db_path=':memory:' for isolated tests.
    """
    path = str(db_path) if db_path is not None else str(DB_PATH)
    conn = duckdb.connect(path)
    try:
        conn.execute(_CREATE_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path | str | None = None) -> None:
    """Create the database and run schema migrations. Safe to call repeatedly."""
    with get_conn(db_path):
        pass
