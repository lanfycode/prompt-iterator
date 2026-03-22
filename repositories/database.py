"""
SQLite initialisation and connection management.

The full schema (including Phase 2 tables) is created on first launch so that
upgrading later requires no migrations — Phase 2 simply starts using the tables
that were already there.
"""
from __future__ import annotations

import sqlite3
from typing import Generator

import config as _config
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Schema definitions ────────────────────────────────────────────────────────

_DDL_PROMPTS = """
CREATE TABLE IF NOT EXISTS prompts (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    current_version INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
"""

_DDL_PROMPT_VERSIONS = """
CREATE TABLE IF NOT EXISTS prompt_versions (
    id                TEXT PRIMARY KEY,
    prompt_id         TEXT NOT NULL,
    version           INTEGER NOT NULL,
    source_type       TEXT NOT NULL DEFAULT 'manual',
    parent_version_id TEXT,
    model_name        TEXT,
    file_path         TEXT NOT NULL,
    summary           TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
);
"""

# ── Phase 2 tables (created now for schema consistency) ───────────────────────

_DDL_TEST_CASES = """
CREATE TABLE IF NOT EXISTS test_cases (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    source_type       TEXT NOT NULL DEFAULT 'uploaded',
    prompt_version_id TEXT,
    file_path         TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    FOREIGN KEY (prompt_version_id) REFERENCES prompt_versions(id)
);
"""

_DDL_TEST_RUNS = """
CREATE TABLE IF NOT EXISTS test_runs (
    id                TEXT PRIMARY KEY,
    prompt_version_id TEXT NOT NULL,
    test_case_id      TEXT,
    model_name        TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending',
    total             INTEGER NOT NULL DEFAULT 0,
    passed            INTEGER NOT NULL DEFAULT 0,
    failed            INTEGER NOT NULL DEFAULT 0,
    result_file_path  TEXT,
    log_file_path     TEXT,
    started_at        TEXT,
    completed_at      TEXT,
    created_at        TEXT NOT NULL,
    FOREIGN KEY (prompt_version_id) REFERENCES prompt_versions(id),
    FOREIGN KEY (test_case_id)      REFERENCES test_cases(id)
);
"""

_DDL_ANALYSES = """
CREATE TABLE IF NOT EXISTS analyses (
    id          TEXT PRIMARY KEY,
    test_run_id TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    FOREIGN KEY (test_run_id) REFERENCES test_runs(id)
);
"""

_DDL_VARIABLES = """
CREATE TABLE IF NOT EXISTS variables (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    value      TEXT NOT NULL,
    scope      TEXT NOT NULL DEFAULT 'global',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_DDL_TEMPLATES = """
CREATE TABLE IF NOT EXISTS templates (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    content     TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""

_DDL_WORKFLOW_RUNS = """
CREATE TABLE IF NOT EXISTS workflow_runs (
    id                TEXT PRIMARY KEY,
    prompt_id         TEXT NOT NULL,
    model_name        TEXT NOT NULL,
    judge_model_name  TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending',
    target_pass_rate  REAL NOT NULL DEFAULT 0.8,
    max_rounds        INTEGER NOT NULL DEFAULT 5,
    current_round     INTEGER NOT NULL DEFAULT 0,
    stop_reason       TEXT,
    created_at        TEXT NOT NULL,
    completed_at      TEXT,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
);
"""

_DDL_ITERATION_ROUNDS = """
CREATE TABLE IF NOT EXISTS iteration_rounds (
    id                TEXT PRIMARY KEY,
    workflow_run_id   TEXT NOT NULL,
    round_number      INTEGER NOT NULL,
    prompt_version_id TEXT NOT NULL,
    test_run_id       TEXT,
    analysis_id       TEXT,
    pass_rate         REAL,
    created_at        TEXT NOT NULL,
    FOREIGN KEY (workflow_run_id)    REFERENCES workflow_runs(id),
    FOREIGN KEY (prompt_version_id) REFERENCES prompt_versions(id),
    FOREIGN KEY (test_run_id)       REFERENCES test_runs(id),
    FOREIGN KEY (analysis_id)       REFERENCES analyses(id)
);
"""

_ALL_DDL = [
    _DDL_PROMPTS,
    _DDL_PROMPT_VERSIONS,
    _DDL_TEST_CASES,
    _DDL_TEST_RUNS,
    _DDL_ANALYSES,
    _DDL_VARIABLES,
    _DDL_TEMPLATES,
    _DDL_WORKFLOW_RUNS,
    _DDL_ITERATION_ROUNDS,
]


# ── Connection helpers ────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """Open a new connection with row_factory and foreign-key enforcement."""
    conn = sqlite3.connect(str(_config.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def initialize_db() -> None:
    """Create all tables (idempotent — safe to call on every startup)."""
    _config.ensure_data_dirs()
    with get_connection() as conn:
        for ddl in _ALL_DDL:
            conn.execute(ddl)
        conn.commit()
    logger.info("Database ready at %s", _config.DB_PATH)
