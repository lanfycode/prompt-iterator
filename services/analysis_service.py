"""
AnalysisService — analyses batch test results.

Responsibilities:
  - Read test results from a completed TestRun.
  - Invoke ResultAnalyzerAgent to produce a structured report.
  - Persist and retrieve analysis reports.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents.result_analyzer_agent import ResultAnalyzerAgent
from llm.client import LLMClient
from models.prompt import Analysis
from repositories.phase2_repository import AnalysisRepository
from storage.test_case_storage import AnalysisStorage, TestRunStorage
from utils.logger import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnalysisService:

    def __init__(
        self,
        llm_client:       Optional[LLMClient] = None,
        analysis_repo:    Optional[AnalysisRepository] = None,
        analysis_storage: Optional[AnalysisStorage] = None,
        test_run_storage: Optional[TestRunStorage] = None,
    ) -> None:
        self._client = llm_client or LLMClient.get_instance()
        self._repo = analysis_repo or AnalysisRepository()
        self._storage = analysis_storage or AnalysisStorage()
        self._tr_storage = test_run_storage or TestRunStorage()
        self._analyzer = ResultAnalyzerAgent(self._client)

    def analyze_test_run(
        self,
        test_run_id:    str,
        prompt_content: str,
        result_file_path: str,
        model_name:     str,
        temperature:    float = 0.3,
        response_language: str = "zh",
    ) -> Analysis:
        """
        Analyse the results of a test run and persist the report.

        Returns the Analysis metadata record.
        """
        results = self._tr_storage.load_results(result_file_path)
        if not results:
            raise ValueError(f"No results found at {result_file_path}")

        report = self._analyzer.analyze(
            prompt_content=prompt_content,
            test_results=results,
            model_name=model_name,
            temperature=temperature,
            response_language=response_language,
        )

        analysis_id = str(uuid.uuid4())
        file_path = self._storage.save(analysis_id, report)
        summary = report.get("summary", "")

        analysis = Analysis(
            id=analysis_id,
            test_run_id=test_run_id,
            file_path=file_path,
            summary=summary,
            created_at=_now(),
        )
        self._repo.create(analysis)
        logger.info("Analysis created id=%s for test_run=%s", analysis_id, test_run_id)
        return analysis

    def get_analysis(self, analysis_id: str) -> Optional[Analysis]:
        return self._repo.get(analysis_id)

    def get_analysis_by_test_run(self, test_run_id: str) -> Optional[Analysis]:
        return self._repo.get_by_test_run(test_run_id)

    def load_report(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Load the full analysis report JSON."""
        analysis = self._repo.get(analysis_id)
        if not analysis:
            return None
        return self._storage.load(analysis.file_path)

    def get_analysis_context(self, analysis_id: str) -> Optional[str]:
        """
        Build an analysis_context string suitable for passing to
        PromptOptimizerAgent.  Returns None if not found.
        """
        report = self.load_report(analysis_id)
        if not report:
            return None
        return json.dumps(report, ensure_ascii=False, indent=2)

    def list_analyses(self) -> List[Analysis]:
        return self._repo.list_all()
