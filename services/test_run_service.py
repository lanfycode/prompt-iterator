"""
TestRunService — executes and tracks test runs.

Responsibilities:
  - Execute batch tests with configurable concurrency.
  - Use LLM judge (PromptIterationAgent) to evaluate each result.
  - Track task state, persist results and logs.
  - Support retry for failed runs.
"""
from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.prompt_iteration_agent import PromptIterationAgent
from llm.client import LLMClient, LLMResponse
from models.prompt import TestRun, TestRunStatus
from repositories.phase2_repository import TestRunRepository
from storage.test_case_storage import TestCaseStorage, TestRunStorage
from utils.logger import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TestRunService:

    def __init__(
        self,
        llm_client:       Optional[LLMClient] = None,
        test_run_repo:    Optional[TestRunRepository] = None,
        test_case_storage: Optional[TestCaseStorage] = None,
        test_run_storage: Optional[TestRunStorage] = None,
    ) -> None:
        self._client = llm_client or LLMClient.get_instance()
        self._repo   = test_run_repo or TestRunRepository()
        self._tc_storage = test_case_storage or TestCaseStorage()
        self._tr_storage = test_run_storage or TestRunStorage()
        self._judge = PromptIterationAgent(self._client)

    def run_batch_test(
        self,
        prompt_content:    str,
        prompt_version_id: str,
        test_case_id:      str,
        cases:             List[Dict[str, Any]],
        model_name:        str,
        judge_model_name:  str,
        concurrency:       int = 3,
        on_started:        Optional[Callable[[str], None]] = None,
        on_progress:       Optional[Callable[[int, int, str], None]] = None,
    ) -> TestRun:
        """
        Execute batch test.

        Args:
            on_progress: callback(completed, total, log_line) for progress updates.

        Returns the completed TestRun record.
        """
        run_id = str(uuid.uuid4())
        now = _now()

        tr = TestRun(
            id=run_id,
            prompt_version_id=prompt_version_id,
            test_case_id=test_case_id,
            model_name=model_name,
            status=TestRunStatus.PENDING,
            total=len(cases),
            passed=0, failed=0,
            result_file_path=None,
            log_file_path=None,
            started_at=None, completed_at=None,
            created_at=now,
        )
        self._repo.create(tr)

        # Start
        tr.status = TestRunStatus.RUNNING
        tr.started_at = _now()
        self._repo.update(tr)
        if on_started:
            on_started(run_id)

        results: List[Dict[str, Any]] = []
        log_lines: List[str] = []
        passed = 0
        failed = 0

        def _execute_one(idx: int, case: Dict[str, Any]) -> Dict[str, Any]:
            test_input = case["input"]
            expected = case["expected"]
            description = case.get("description", "")

            # Call the model under test
            try:
                response: LLMResponse = self._client.generate(
                    model_name=model_name,
                    prompt=test_input,
                    system_instruction=prompt_content,
                )
                actual_output = response.text
                latency_ms = response.latency_ms
            except Exception as exc:
                actual_output = f"[ERROR] {exc}"
                latency_ms = 0.0

            # Call the LLM judge
            try:
                verdict = self._judge.judge(
                    prompt_content=prompt_content,
                    test_input=test_input,
                    expected=expected,
                    actual_output=actual_output,
                    model_name=judge_model_name,
                )
            except Exception as exc:
                verdict = {"passed": False, "score": 0.0, "reasoning": f"Judge error: {exc}"}

            return {
                "index": idx,
                "input": test_input,
                "expected": expected,
                "description": description,
                "actual_output": actual_output,
                "latency_ms": latency_ms,
                "passed": verdict["passed"],
                "score": verdict["score"],
                "reasoning": verdict["reasoning"],
            }

        try:
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                futures = {
                    pool.submit(_execute_one, i, case): i
                    for i, case in enumerate(cases)
                }
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    if result["passed"]:
                        passed += 1
                    else:
                        failed += 1
                    line = (
                        f"[{len(results)}/{len(cases)}] "
                        f"Case {result['index']}: {'PASS' if result['passed'] else 'FAIL'} "
                        f"(score={result['score']:.2f})"
                    )
                    log_lines.append(line)
                    self._tr_storage.append_log(run_id, line)
                    if on_progress:
                        on_progress(len(results), len(cases), line)

            # Sort results by index
            results.sort(key=lambda r: r["index"])

            tr.passed = passed
            tr.failed = failed
            tr.status = TestRunStatus.COMPLETED
            tr.completed_at = _now()
            tr.result_file_path = self._tr_storage.save_results(run_id, results)
            tr.log_file_path = self._tr_storage.save_log(run_id, log_lines)
            self._repo.update(tr)
            logger.info("Batch test completed: %d/%d passed (run_id=%s)", passed, len(cases), run_id)

        except Exception as exc:
            tr.status = TestRunStatus.FAILED
            tr.completed_at = _now()
            log_lines.append(f"[FATAL] {exc}")
            tr.log_file_path = self._tr_storage.save_log(run_id, log_lines)
            if results:
                tr.result_file_path = self._tr_storage.save_results(run_id, results)
            tr.passed = passed
            tr.failed = failed
            self._repo.update(tr)
            logger.error("Batch test failed (run_id=%s): %s", run_id, exc)

        return tr

    def run_single_test(
        self,
        prompt_version_id: str,
        model_name: str,
        user_input: str,
        rendered_prompt: str,
        final_input: str,
        variables: Optional[Dict[str, Any]] = None,
        template_id: Optional[str] = None,
        template_name: Optional[str] = None,
        template_content: Optional[str] = None,
    ) -> Tuple[TestRun, Dict[str, Any]]:
        """Execute one single test and persist it as a regular test run."""
        run_id = str(uuid.uuid4())
        now = _now()

        tr = TestRun(
            id=run_id,
            prompt_version_id=prompt_version_id,
            test_case_id=None,
            model_name=model_name,
            status=TestRunStatus.PENDING,
            total=1,
            passed=0,
            failed=0,
            result_file_path=None,
            log_file_path=None,
            started_at=None,
            completed_at=None,
            created_at=now,
        )
        self._repo.create(tr)

        tr.status = TestRunStatus.RUNNING
        tr.started_at = _now()
        self._repo.update(tr)

        log_lines = ["[1/1] Single test started"]
        result: Dict[str, Any]

        try:
            response: LLMResponse = self._client.generate(
                model_name=model_name,
                prompt=final_input,
                system_instruction=rendered_prompt,
            )
            result = {
                "mode": "single_test",
                "user_input": user_input,
                "rendered_prompt": rendered_prompt,
                "final_input": final_input,
                "actual_output": response.text,
                "variables": variables or {},
                "template_id": template_id,
                "template_name": template_name,
                "template_content": template_content,
                "latency_ms": response.latency_ms,
                "prompt_tokens": response.prompt_tokens,
                "output_tokens": response.output_tokens,
            }
            tr.status = TestRunStatus.COMPLETED
            tr.passed = 1
            log_lines.append("[1/1] Single test completed")
        except Exception as exc:
            logger.error("Single test failed (run_id=%s): %s", run_id, exc)
            result = {
                "mode": "single_test",
                "user_input": user_input,
                "rendered_prompt": rendered_prompt,
                "final_input": final_input,
                "actual_output": f"[ERROR] {exc}",
                "variables": variables or {},
                "template_id": template_id,
                "template_name": template_name,
                "template_content": template_content,
                "latency_ms": 0.0,
                "prompt_tokens": 0,
                "output_tokens": 0,
            }
            tr.status = TestRunStatus.FAILED
            tr.failed = 1
            log_lines.append(f"[1/1] Single test failed: {exc}")

        tr.completed_at = _now()
        tr.result_file_path = self._tr_storage.save_results(run_id, [result])
        tr.log_file_path = self._tr_storage.save_log(run_id, log_lines)
        self._repo.update(tr)
        return tr, result

    def get_test_run(self, run_id: str) -> Optional[TestRun]:
        return self._repo.get(run_id)

    def get_test_run_status(self, run_id: str) -> Optional[str]:
        tr = self._repo.get(run_id)
        return tr.status if tr else None

    def get_results(self, run_id: str) -> Optional[List[Dict[str, Any]]]:
        tr = self._repo.get(run_id)
        if not tr or not tr.result_file_path:
            return None
        return self._tr_storage.load_results(tr.result_file_path)

    def get_log(self, run_id: str) -> Optional[str]:
        return self._tr_storage.load_log(run_id)

    def list_test_runs(self) -> List[TestRun]:
        return self._repo.list_all()

    def retry_test_run(
        self,
        run_id:           str,
        prompt_content:   str,
        cases:            List[Dict[str, Any]],
        judge_model_name: str,
        concurrency:      int = 3,
        on_started:       Optional[Callable[[str], None]] = None,
        on_progress:      Optional[Callable[[int, int, str], None]] = None,
    ) -> TestRun:
        """Re-run a failed test by creating a new test run with the same params."""
        old_tr = self._repo.get(run_id)
        if not old_tr:
            raise ValueError(f"TestRun not found: {run_id}")

        return self.run_batch_test(
            prompt_content=prompt_content,
            prompt_version_id=old_tr.prompt_version_id,
            test_case_id=old_tr.test_case_id or "",
            cases=cases,
            model_name=old_tr.model_name,
            judge_model_name=judge_model_name,
            concurrency=concurrency,
            on_started=on_started,
            on_progress=on_progress,
        )
