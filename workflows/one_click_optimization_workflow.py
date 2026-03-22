"""
OneClickOptimizationWorkflow — thin wrapper that delegates to WorkflowService
for the full automated loop.

Stop conditions:
  - Pass rate ≥ target threshold.
  - No improvement for N consecutive rounds.
  - Maximum iteration count reached.
  - User manually cancels the run.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from models.prompt import IterationRound, WorkflowRun
from services.workflow_service import WorkflowService
from utils.logger import get_logger

logger = get_logger(__name__)


class OneClickOptimizationWorkflow:

    def __init__(self, workflow_service: Optional[WorkflowService] = None) -> None:
        self._ws = workflow_service or WorkflowService()

    def run(
        self,
        prompt_id:        str,
        model_name:       str,
        judge_model_name: str,
        target_pass_rate: float = 0.8,
        max_rounds:       int = 5,
        num_cases:        int = 10,
        concurrency:      int = 3,
        on_round_complete: Optional[Callable[[int, float, str], None]] = None,
        on_progress:       Optional[Callable[[int, int, str], None]] = None,
    ) -> WorkflowRun:
        return self._ws.run_one_click_optimization(
            prompt_id=prompt_id,
            model_name=model_name,
            judge_model_name=judge_model_name,
            target_pass_rate=target_pass_rate,
            max_rounds=max_rounds,
            num_cases=num_cases,
            concurrency=concurrency,
            on_round_complete=on_round_complete,
            on_progress=on_progress,
        )

    def stop(self, workflow_run_id: str) -> None:
        self._ws.stop_workflow(workflow_run_id)

    def get_rounds(self, workflow_run_id: str) -> List[IterationRound]:
        return self._ws.get_rounds(workflow_run_id)
