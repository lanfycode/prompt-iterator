"""
Domain models for Prompt-Iterator.

Phase 1: Prompt, PromptVersion
Phase 2: TestCase, TestRun, Analysis, IterationRound, WorkflowRun,
         Variable, Template
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# ── Shared enums ──────────────────────────────────────────────────────────────

class SourceType(str, Enum):
    GENERATED = "generated"
    OPTIMIZED = "optimized"
    MANUAL    = "manual"


class TestRunStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELED  = "canceled"


class WorkflowStatus(str, Enum):
    """Status for one-click optimisation workflow runs."""
    PENDING              = "pending"
    GENERATING_TESTCASES = "generating_testcases"
    TESTING              = "testing"
    ANALYZING            = "analyzing"
    OPTIMIZING           = "optimizing"
    TESTING_NEXT_ROUND   = "testing_next_round"
    COMPLETED            = "completed"
    FAILED               = "failed"
    CANCELED             = "canceled"


# ── Phase 1 models ────────────────────────────────────────────────────────────

@dataclass
class Prompt:
    """Top-level Prompt asset."""
    id:              str
    name:            str
    description:     str
    current_version: int
    created_at:      str
    updated_at:      str


@dataclass
class PromptVersion:
    """
    An immutable snapshot of a Prompt at a specific point in time.
    `content` is loaded on demand from the file system and is not stored
    in SQLite.
    """
    id:               str
    prompt_id:        str
    version:          int
    source_type:      str           # SourceType value
    parent_version_id: Optional[str]
    model_name:       Optional[str]
    file_path:        str
    summary:          str
    created_at:       str
    content:          Optional[str] = None   # populated by storage layer


# ── Phase 2 models ────────────────────────────────────────────────────────────

@dataclass
class TestCase:
    """A named set of test cases stored as a JSON file."""
    id:               str
    name:             str
    source_type:      str           # "uploaded" | "generated"
    prompt_version_id: Optional[str]
    file_path:        str
    created_at:       str


@dataclass
class TestRun:
    """Execution record for a batch test."""
    id:                str
    prompt_version_id: str
    test_case_id:      Optional[str]
    model_name:        str
    status:            str          # TestRunStatus value
    total:             int
    passed:            int
    failed:            int
    result_file_path:  Optional[str]
    log_file_path:     Optional[str]
    started_at:        Optional[str]
    completed_at:      Optional[str]
    created_at:        str


@dataclass
class Analysis:
    """Structured analysis report derived from a TestRun."""
    id:          str
    test_run_id: str
    file_path:   str
    summary:     str
    created_at:  str


@dataclass
class IterationRound:
    """A single round inside an automated one-click optimization run."""
    id:               str
    workflow_run_id:  str
    round_number:     int
    prompt_version_id: str
    test_run_id:      Optional[str]
    analysis_id:      Optional[str]
    pass_rate:        Optional[float]
    created_at:       str


@dataclass
class WorkflowRun:
    """Top-level record for a one-click optimisation run."""
    id:                str
    prompt_id:         str
    model_name:        str
    judge_model_name:  str
    status:            str          # WorkflowStatus value
    target_pass_rate:  float
    max_rounds:        int
    current_round:     int
    stop_reason:       Optional[str]
    created_at:        str
    completed_at:      Optional[str]


@dataclass
class Variable:
    """A reusable variable for prompt/template rendering."""
    id:         str
    name:       str
    value:      str
    scope:      str
    created_at: str
    updated_at: str


@dataclass
class Template:
    """A context template for assembling final inputs."""
    id:          str
    name:        str
    content:     str
    description: str
    created_at:  str
    updated_at:  str
