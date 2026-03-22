"""
TestExecutionWorkflow — coordinates batch test execution end-to-end.

Orchestrates: load prompt → load/generate test cases → batch test → return results.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from models.prompt import TestCase, TestRun
from services.prompt_service import PromptService
from services.test_case_service import TestCaseService
from services.test_run_service import TestRunService
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TestExecutionResult:
    test_case: TestCase
    test_run: TestRun
    cases: List[Dict[str, Any]]


class TestExecutionWorkflow:

    def __init__(
        self,
        prompt_service:    Optional[PromptService] = None,
        test_case_service: Optional[TestCaseService] = None,
        test_run_service:  Optional[TestRunService] = None,
    ) -> None:
        self._ps  = prompt_service or PromptService()
        self._tcs = test_case_service or TestCaseService()
        self._trs = test_run_service or TestRunService()

    def run(
        self,
        prompt_id:        str,
        model_name:       str,
        judge_model_name: str,
        test_case_id:     Optional[str] = None,
        num_cases:        int = 10,
        concurrency:      int = 3,
        on_progress:      Optional[Callable[[int, int, str], None]] = None,
    ) -> TestExecutionResult:
        """
        Run a batch test end-to-end.

        If *test_case_id* is given, reuses that test case set;
        otherwise generates a new one.
        """
        version = self._ps.get_latest_version_with_content(prompt_id)
        if not version or not version.content:
            raise ValueError(f"No prompt content for prompt_id={prompt_id}")

        # Load or generate test cases
        if test_case_id:
            tc = self._tcs.get_test_case(test_case_id)
            if not tc:
                raise ValueError(f"TestCase not found: {test_case_id}")
            cases = self._tcs.load_cases(test_case_id)
        else:
            tc, cases = self._tcs.generate(
                prompt_content=version.content,
                prompt_version_id=version.id,
                model_name=model_name,
                num_cases=num_cases,
            )

        if not cases:
            raise ValueError("No test cases to execute.")

        tr = self._trs.run_batch_test(
            prompt_content=version.content,
            prompt_version_id=version.id,
            test_case_id=tc.id,
            cases=cases,
            model_name=model_name,
            judge_model_name=judge_model_name,
            concurrency=concurrency,
            on_progress=on_progress,
        )

        logger.info("TestExecutionWorkflow complete: run_id=%s", tr.id)
        return TestExecutionResult(test_case=tc, test_run=tr, cases=cases)
