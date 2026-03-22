"""
TestCaseService — manages test case set lifecycle.

Responsibilities:
  - Generate test cases from a prompt via TestCaseGeneratorAgent.
  - Validate test case JSON structure.
  - Persist and retrieve test case sets.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from agents.test_case_generator_agent import TestCaseGeneratorAgent
from llm.client import LLMClient
from models.prompt import TestCase
from repositories.phase2_repository import TestCaseRepository
from storage.test_case_storage import TestCaseStorage, validate_test_cases
from utils.logger import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TestCaseService:

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        repository: Optional[TestCaseRepository] = None,
        storage:    Optional[TestCaseStorage] = None,
    ) -> None:
        self._client = llm_client or LLMClient.get_instance()
        self._repo   = repository or TestCaseRepository()
        self._storage = storage or TestCaseStorage()
        self._generator = TestCaseGeneratorAgent(self._client)

    def generate(
        self,
        prompt_content:    str,
        prompt_version_id: str,
        model_name:        str,
        num_cases:         int = 10,
        temperature:       float = 0.7,
        name:              str = "",
    ) -> Tuple[TestCase, List[Dict[str, Any]]]:
        """
        Generate test cases for *prompt_content*, validate, persist, and return
        (TestCase metadata, list of case dicts).
        """
        cases = self._generator.generate(
            prompt_content=prompt_content,
            model_name=model_name,
            num_cases=num_cases,
            temperature=temperature,
        )

        errors = validate_test_cases(cases)
        if errors:
            raise ValueError(f"Generated test cases failed validation: {errors}")

        tc_id = str(uuid.uuid4())
        file_path = self._storage.save(tc_id, cases)

        tc = TestCase(
            id=tc_id,
            name=name or f"Auto-generated ({len(cases)} cases)",
            source_type="generated",
            prompt_version_id=prompt_version_id,
            file_path=file_path,
            created_at=_now(),
        )
        self._repo.create(tc)
        logger.info("Generated %d test cases → tc_id=%s", len(cases), tc_id)
        return tc, cases

    def validate(self, cases: List[Dict[str, Any]]) -> List[str]:
        """Validate a list of test case dicts. Returns error messages."""
        return validate_test_cases(cases)

    def save_uploaded(
        self,
        name: str,
        cases: List[Dict[str, Any]],
        prompt_version_id: Optional[str] = None,
    ) -> TestCase:
        """Save externally provided (uploaded) test cases."""
        errors = validate_test_cases(cases)
        if errors:
            raise ValueError(f"Uploaded test cases failed validation: {errors}")

        tc_id = str(uuid.uuid4())
        file_path = self._storage.save(tc_id, cases)
        tc = TestCase(
            id=tc_id, name=name,
            source_type="uploaded",
            prompt_version_id=prompt_version_id,
            file_path=file_path,
            created_at=_now(),
        )
        self._repo.create(tc)
        return tc

    def get_test_case(self, tc_id: str) -> Optional[TestCase]:
        return self._repo.get(tc_id)

    def load_cases(self, tc_id: str) -> Optional[List[Dict[str, Any]]]:
        """Load the actual case list from file for a given test case set."""
        tc = self._repo.get(tc_id)
        if not tc:
            return None
        return self._storage.load(tc.file_path)

    def list_test_cases(self) -> List[TestCase]:
        return self._repo.list_all()
