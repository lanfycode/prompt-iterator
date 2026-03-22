"""
File-system storage for test case files and test run results.

Test case files are JSON under data/testcases/<test_case_id>/cases.json.
Test run results are JSON under data/test-runs/<test_run_id>/results.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import config as _config
from utils.logger import get_logger

logger = get_logger(__name__)


# ── TestCase JSON schema ──────────────────────────────────────────────────────
#
# Expected format:
# [
#   {
#     "input": "...",
#     "expected": "...",            # reference answer for LLM judge
#     "description": "..."         # optional human-readable label
#   },
#   ...
# ]

_REQUIRED_FIELDS = {"input", "expected"}


def validate_test_cases(cases: List[Dict[str, Any]]) -> List[str]:
    """
    Validate a list of test case dicts.

    Returns a list of error messages (empty if valid).
    """
    errors: List[str] = []
    if not isinstance(cases, list):
        return ["Test cases must be a JSON array."]
    if len(cases) == 0:
        return ["Test cases array is empty."]

    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"Item {i}: must be a JSON object.")
            continue
        missing = _REQUIRED_FIELDS - set(case.keys())
        if missing:
            errors.append(f"Item {i}: missing fields {sorted(missing)}.")
        if "input" in case and not isinstance(case["input"], str):
            errors.append(f"Item {i}: 'input' must be a string.")
        if "expected" in case and not isinstance(case["expected"], str):
            errors.append(f"Item {i}: 'expected' must be a string.")
    return errors


class TestCaseStorage:
    """Read / write test case JSON files."""

    def __init__(self) -> None:
        _config.ensure_data_dirs()

    def save(self, test_case_id: str, cases: List[Dict[str, Any]]) -> str:
        """Save test cases JSON, return the file path."""
        directory = _config.TESTCASES_DIR / test_case_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "cases.json"
        path.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("Saved test cases → %s  (%d items)", path, len(cases))
        return str(path)

    def load(self, file_path: str) -> Optional[List[Dict[str, Any]]]:
        """Load and parse test cases from a JSON file."""
        path = Path(file_path)
        if not path.exists():
            logger.warning("Test case file not found: %s", path)
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else None
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in %s: %s", path, exc)
            return None


class TestRunStorage:
    """Read / write test run result files and log files."""

    def __init__(self) -> None:
        _config.ensure_data_dirs()

    def _run_dir(self, test_run_id: str) -> Path:
        d = _config.TEST_RUNS_DIR / test_run_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_results(self, test_run_id: str, results: List[Dict[str, Any]]) -> str:
        path = self._run_dir(test_run_id) / "results.json"
        path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("Saved test results → %s", path)
        return str(path)

    def load_results(self, file_path: str) -> Optional[List[Dict[str, Any]]]:
        path = Path(file_path)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def save_log(self, test_run_id: str, log_lines: List[str]) -> str:
        path = self._run_dir(test_run_id) / "run.log"
        path.write_text("\n".join(log_lines), encoding="utf-8")
        return str(path)

    def append_log(self, test_run_id: str, line: str) -> str:
        path = self._run_dir(test_run_id) / "run.log"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return str(path)

    def load_log(self, test_run_id: str) -> Optional[str]:
        path = self._run_dir(test_run_id) / "run.log"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")


class AnalysisStorage:
    """Read / write analysis report files."""

    def __init__(self) -> None:
        _config.ensure_data_dirs()

    def save(self, analysis_id: str, report: Dict[str, Any]) -> str:
        directory = _config.ANALYSIS_DIR / analysis_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "report.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("Saved analysis report → %s", path)
        return str(path)

    def load(self, file_path: str) -> Optional[Dict[str, Any]]:
        path = Path(file_path)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
