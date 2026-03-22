"""
Application configuration.

Reads environment variables (from .env) and defines all runtime paths.
Each component should import from here rather than reading env vars directly.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env before anything else
load_dotenv()

# ── Directory layout ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

PROMPTS_DIR     = DATA_DIR / "prompts"
TESTCASES_DIR   = DATA_DIR / "testcases"    # Phase 2
TEST_RUNS_DIR   = DATA_DIR / "test-runs"    # Phase 2
ANALYSIS_DIR    = DATA_DIR / "analysis"     # Phase 2
TEMPLATES_DIR   = DATA_DIR / "templates"
VARIABLES_DIR   = DATA_DIR / "variables"
LOGS_DIR        = DATA_DIR / "logs"

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH = DATA_DIR / "app.db"

# ── API keys ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY:    str = os.environ.get("GEMINI_API_KEY", "")
DASHSCOPE_API_KEY: str = os.environ.get("DASHSCOPE_API_KEY", "")  # Qwen / Alibaba DashScope

# ── App settings ──────────────────────────────────────────────────────────────
APP_TITLE = "Prompt Iterator"
APP_PORT  = int(os.environ.get("APP_PORT", "7860"))


def ensure_data_dirs() -> None:
    """Create all required data directories if they do not already exist."""
    for directory in (
        DATA_DIR, PROMPTS_DIR, TESTCASES_DIR, TEST_RUNS_DIR,
        ANALYSIS_DIR, TEMPLATES_DIR, VARIABLES_DIR, LOGS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
