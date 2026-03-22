"""
WorkflowService — orchestrates the one-click optimisation pipeline.

Pipeline per round:
  1. Generate test cases (round 1 only — reuse afterwards).
  2. Execute batch test.
  3. Analyse results.
  4. If pass_rate >= target → stop.
  5. Optimise prompt using analysis context.
  6. Repeat from step 2 with new version.

Stop conditions:
  - Target pass rate reached.
  - Maximum rounds exhausted.
  - Consecutive rounds with no improvement.
  - External cancellation flag.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from llm.client import LLMClient
from models.prompt import (
    IterationRound, TestRun, WorkflowRun, WorkflowStatus,
)
from repositories.phase2_repository import (
    IterationRoundRepository, WorkflowRunRepository,
)
from services.analysis_service import AnalysisService
from services.optimization_service import OptimizationService
from services.prompt_service import PromptService
from services.test_case_service import TestCaseService
from services.test_run_service import TestRunService
from utils.logger import get_logger

logger = get_logger(__name__)

_NO_IMPROVE_LIMIT = 2  # stop after N consecutive rounds without improvement


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowService:

    def __init__(
        self,
        prompt_service:       Optional[PromptService] = None,
        optimization_service: Optional[OptimizationService] = None,
        test_case_service:    Optional[TestCaseService] = None,
        test_run_service:     Optional[TestRunService] = None,
        analysis_service:     Optional[AnalysisService] = None,
        workflow_repo:        Optional[WorkflowRunRepository] = None,
        round_repo:           Optional[IterationRoundRepository] = None,
    ) -> None:
        self._ps  = prompt_service or PromptService()
        self._os  = optimization_service or OptimizationService(self._ps)
        self._tcs = test_case_service or TestCaseService()
        self._trs = test_run_service or TestRunService()
        self._as  = analysis_service or AnalysisService()
        self._wr_repo = workflow_repo or WorkflowRunRepository()
        self._ir_repo = round_repo or IterationRoundRepository()
        self._cancel_flags: Dict[str, bool] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def run_one_click_optimization(
        self,
        prompt_id:        str,
        model_name:       str,
        judge_model_name: str,
        target_pass_rate: float = 0.8,
        max_rounds:       int   = 5,
        num_cases:        int   = 10,
        concurrency:      int   = 3,
        on_round_complete: Optional[Callable[[int, float, str], None]] = None,
        on_progress:       Optional[Callable[[int, int, str], None]] = None,
    ) -> WorkflowRun:
        """
        Execute the full automated optimization loop synchronously.

        Args:
            on_round_complete: callback(round_number, pass_rate, summary)
            on_progress: callback(completed, total, log_line) for test progress
        """
        # Load current prompt version
        version = self._ps.get_latest_version_with_content(prompt_id)
        if not version or not version.content:
            raise ValueError(f"No prompt content for prompt_id={prompt_id}")

        wr = WorkflowRun(
            id=str(uuid.uuid4()),
            prompt_id=prompt_id,
            model_name=model_name,
            judge_model_name=judge_model_name,
            status=WorkflowStatus.PENDING,
            target_pass_rate=target_pass_rate,
            max_rounds=max_rounds,
            current_round=0,
            stop_reason=None,
            created_at=_now(),
            completed_at=None,
        )
        self._wr_repo.create(wr)
        self._cancel_flags[wr.id] = False

        prompt_content = version.content
        current_version_id = version.id
        best_pass_rate = 0.0
        no_improve_count = 0
        test_case_id: Optional[str] = None
        cases: Optional[List[Dict[str, Any]]] = None

        try:
            for round_num in range(1, max_rounds + 1):
                if self._cancel_flags.get(wr.id, False):
                    wr.stop_reason = "User cancelled"
                    wr.status = WorkflowStatus.CANCELED
                    break

                wr.current_round = round_num

                # Step 1: Generate test cases (first round only)
                if test_case_id is None:
                    wr.status = WorkflowStatus.GENERATING_TESTCASES
                    self._wr_repo.update(wr)

                    tc, cases = self._tcs.generate(
                        prompt_content=prompt_content,
                        prompt_version_id=current_version_id,
                        model_name=model_name,
                        num_cases=num_cases,
                    )
                    test_case_id = tc.id

                # Create round record
                ir = IterationRound(
                    id=str(uuid.uuid4()),
                    workflow_run_id=wr.id,
                    round_number=round_num,
                    prompt_version_id=current_version_id,
                    test_run_id=None,
                    analysis_id=None,
                    pass_rate=None,
                    created_at=_now(),
                )
                self._ir_repo.create(ir)

                # Step 2: Batch test
                wr.status = WorkflowStatus.TESTING if round_num == 1 else WorkflowStatus.TESTING_NEXT_ROUND
                self._wr_repo.update(wr)

                tr = self._trs.run_batch_test(
                    prompt_content=prompt_content,
                    prompt_version_id=current_version_id,
                    test_case_id=test_case_id,
                    cases=cases,
                    model_name=model_name,
                    judge_model_name=judge_model_name,
                    concurrency=concurrency,
                    on_progress=on_progress,
                )
                ir.test_run_id = tr.id
                pass_rate = tr.passed / tr.total if tr.total > 0 else 0.0
                ir.pass_rate = pass_rate
                self._ir_repo.update(ir)

                # Step 3: Analyse
                wr.status = WorkflowStatus.ANALYZING
                self._wr_repo.update(wr)

                analysis = self._as.analyze_test_run(
                    test_run_id=tr.id,
                    prompt_content=prompt_content,
                    result_file_path=tr.result_file_path or "",
                    model_name=model_name,
                )
                ir.analysis_id = analysis.id
                self._ir_repo.update(ir)

                round_summary = analysis.summary or f"Pass rate: {pass_rate:.1%}"
                if on_round_complete:
                    on_round_complete(round_num, pass_rate, round_summary)

                # Check stop conditions
                if pass_rate >= target_pass_rate:
                    wr.stop_reason = f"Target pass rate {target_pass_rate:.0%} reached ({pass_rate:.1%})"
                    wr.status = WorkflowStatus.COMPLETED
                    break

                if pass_rate <= best_pass_rate:
                    no_improve_count += 1
                else:
                    no_improve_count = 0
                    best_pass_rate = pass_rate

                if no_improve_count >= _NO_IMPROVE_LIMIT:
                    wr.stop_reason = f"No improvement for {_NO_IMPROVE_LIMIT} consecutive rounds"
                    wr.status = WorkflowStatus.COMPLETED
                    break

                if round_num >= max_rounds:
                    wr.stop_reason = f"Maximum rounds ({max_rounds}) reached"
                    wr.status = WorkflowStatus.COMPLETED
                    break

                # Step 4: Optimise
                wr.status = WorkflowStatus.OPTIMIZING
                self._wr_repo.update(wr)

                analysis_context = self._as.get_analysis_context(analysis.id)
                prompt, new_version = self._os.optimize_and_save(
                    prompt_id=prompt_id,
                    optimization_request="Improve the prompt based on the test failure analysis.",
                    model_name=model_name,
                    analysis_context=analysis_context,
                )[:2]

                prompt_content = new_version.content or self._ps.get_version_with_content(new_version.id).content
                current_version_id = new_version.id

        except Exception as exc:
            logger.error("Workflow failed (wr_id=%s): %s", wr.id, exc)
            wr.status = WorkflowStatus.FAILED
            wr.stop_reason = str(exc)

        wr.completed_at = _now()
        self._wr_repo.update(wr)
        self._cancel_flags.pop(wr.id, None)
        logger.info("Workflow %s finished: status=%s reason=%s", wr.id, wr.status, wr.stop_reason)
        return wr

    def stop_workflow(self, workflow_run_id: str) -> None:
        """Signal a running workflow to cancel at the next check point."""
        self._cancel_flags[workflow_run_id] = True
        logger.info("Cancel requested for workflow %s", workflow_run_id)

    def get_workflow_run(self, wr_id: str) -> Optional[WorkflowRun]:
        return self._wr_repo.get(wr_id)

    def get_rounds(self, wr_id: str) -> List[IterationRound]:
        return self._ir_repo.list_by_workflow(wr_id)

    def list_workflow_runs(self) -> List[WorkflowRun]:
        return self._wr_repo.list_all()
