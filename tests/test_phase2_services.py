"""
Unit tests for Phase 2 services.

All LLM calls are mocked; DB and storage use temporary paths.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


def _setup_temp_env():
    """Redirect DB and storage to temp locations."""
    import config as cfg
    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_dir = tempfile.mkdtemp()
    cfg.DB_PATH = Path(tmp_db.name)
    cfg.DATA_DIR = Path(tmp_dir)
    cfg.PROMPTS_DIR = Path(tmp_dir) / "prompts"
    cfg.TESTCASES_DIR = Path(tmp_dir) / "testcases"
    cfg.TEST_RUNS_DIR = Path(tmp_dir) / "test-runs"
    cfg.ANALYSIS_DIR = Path(tmp_dir) / "analysis"
    cfg.LOGS_DIR = Path(tmp_dir) / "logs"
    cfg.TEMPLATES_DIR = Path(tmp_dir) / "templates"
    cfg.VARIABLES_DIR = Path(tmp_dir) / "variables"
    for d in [cfg.PROMPTS_DIR, cfg.TESTCASES_DIR, cfg.TEST_RUNS_DIR,
              cfg.ANALYSIS_DIR, cfg.LOGS_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    from repositories.database import initialize_db
    initialize_db()
    return tmp_db, tmp_dir


def _seed_prompt_and_version(prompt_id="p-001", version_id="pv-001"):
    """Insert prerequisite prompt + prompt_version rows so FK constraints pass."""
    from repositories.database import get_connection
    now = "2025-01-01T00:00:00+00:00"
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO prompts (id, name, description, current_version, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (prompt_id, "Test Prompt", "", 1, now, now),
        )
        conn.execute(
            "INSERT OR IGNORE INTO prompt_versions (id, prompt_id, version, source_type, model_name, file_path, summary, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (version_id, prompt_id, 1, "manual", "gemini-2.5-flash", "/tmp/fake.md", "", now),
        )


def _mock_llm_client():
    from llm.client import LLMResponse
    client = MagicMock()
    client.generate.return_value = LLMResponse(
        text="Mock LLM output",
        model_name="gemini-2.5-flash",
        temperature=0.7,
        prompt_tokens=10,
        output_tokens=10,
        latency_ms=100.0,
    )
    return client


# ══════════════════════════════════════════════════════════════════════════════
# TestCaseService
# ══════════════════════════════════════════════════════════════════════════════
class TestTestCaseService(unittest.TestCase):

    def setUp(self):
        self._tmp_db, self._tmp_dir = _setup_temp_env()
        self._mock_client = _mock_llm_client()

        sample_cases = json.dumps([
            {"input": "Hello", "expected": "Hi there", "description": "greeting"},
            {"input": "Bye", "expected": "Goodbye", "description": "farewell"},
        ])
        self._mock_client.generate.return_value = MagicMock(
            text=sample_cases,
            model_name="gemini-2.5-flash",
            temperature=0.7,
            prompt_tokens=50,
            output_tokens=50,
            latency_ms=200.0,
        )

        _seed_prompt_and_version()

        from services.test_case_service import TestCaseService
        self.service = TestCaseService(llm_client=self._mock_client)

    def tearDown(self):
        self._tmp_db.close()
        os.unlink(self._tmp_db.name)

    def test_generate_creates_test_case(self):
        tc, cases = self.service.generate(
            prompt_content="You are a greeter.",
            prompt_version_id="pv-001",
            model_name="gemini-2.5-flash",
            num_cases=2,
        )
        self.assertEqual(len(cases), 2)
        self.assertEqual(tc.source_type, "generated")
        self.assertIsNotNone(tc.id)

    def test_save_uploaded_persists(self):
        cases = [{"input": "A", "expected": "B"}]
        tc = self.service.save_uploaded(name="Manual", cases=cases)
        self.assertEqual(tc.source_type, "uploaded")
        loaded = self.service.load_cases(tc.id)
        self.assertEqual(loaded, cases)

    def test_validate_fails_on_missing_fields(self):
        errors = self.service.validate([{"input": "A"}])
        self.assertTrue(len(errors) > 0)

    def test_list_returns_saved(self):
        self.service.save_uploaded("T", [{"input": "x", "expected": "y"}])
        self.assertEqual(len(self.service.list_test_cases()), 1)


# ══════════════════════════════════════════════════════════════════════════════
# TestRunService
# ══════════════════════════════════════════════════════════════════════════════
class TestTestRunService(unittest.TestCase):

    def setUp(self):
        self._tmp_db, self._tmp_dir = _setup_temp_env()
        self._mock_client = _mock_llm_client()

        # Judge returns "passed"
        judge_json = json.dumps({"passed": True, "score": 0.9, "reasoning": "ok"})
        self._mock_client.generate.return_value = MagicMock(
            text=judge_json,
            model_name="gemini-2.5-flash",
            temperature=0.1,
            prompt_tokens=10,
            output_tokens=10,
            latency_ms=50.0,
        )

        _seed_prompt_and_version()

        from services.test_run_service import TestRunService
        self.service = TestRunService(llm_client=self._mock_client)

    def tearDown(self):
        self._tmp_db.close()
        os.unlink(self._tmp_db.name)

    def test_batch_test_completes(self):
        cases = [
            {"input": "Hello", "expected": "Hi", "description": "g"},
        ]
        tr = self.service.run_batch_test(
            prompt_content="You are a bot.",
            prompt_version_id="pv-001",
            test_case_id=None,
            cases=cases,
            model_name="gemini-2.5-flash",
            judge_model_name="gemini-2.5-flash",
            concurrency=1,
        )
        self.assertEqual(tr.status, "completed")
        self.assertEqual(tr.total, 1)
        self.assertEqual(tr.passed, 1)

    def test_list_returns_runs(self):
        cases = [{"input": "A", "expected": "B"}]
        self.service.run_batch_test(
            prompt_content="p",
            prompt_version_id="pv-001",
            test_case_id=None,
            cases=cases,
            model_name="gemini-2.5-flash",
            judge_model_name="gemini-2.5-flash",
        )
        runs = self.service.list_test_runs()
        self.assertEqual(len(runs), 1)

    def test_get_results_returns_data(self):
        cases = [{"input": "A", "expected": "B"}]
        tr = self.service.run_batch_test(
            prompt_content="p",
            prompt_version_id="pv-001",
            test_case_id=None,
            cases=cases,
            model_name="gemini-2.5-flash",
            judge_model_name="gemini-2.5-flash",
        )
        results = self.service.get_results(tr.id)
        self.assertIsNotNone(results)
        self.assertEqual(len(results), 1)


# ══════════════════════════════════════════════════════════════════════════════
# AnalysisService
# ══════════════════════════════════════════════════════════════════════════════
class TestAnalysisService(unittest.TestCase):

    def setUp(self):
        self._tmp_db, self._tmp_dir = _setup_temp_env()
        self._mock_client = _mock_llm_client()

        report = json.dumps({
            "summary": "All good",
            "failure_categories": [],
            "error_patterns": [],
            "suggestions": ["try harder"]
        })
        self._mock_client.generate.return_value = MagicMock(
            text=report,
            model_name="gemini-2.5-flash",
            temperature=0.3,
            prompt_tokens=20,
            output_tokens=20,
            latency_ms=100.0,
        )

        _seed_prompt_and_version()

        from services.analysis_service import AnalysisService
        self.service = AnalysisService(llm_client=self._mock_client)

    def tearDown(self):
        self._tmp_db.close()
        os.unlink(self._tmp_db.name)

    def test_analyze_creates_record(self):
        # First, store some fake results
        from storage.test_case_storage import TestRunStorage
        trs = TestRunStorage()
        result_path = trs.save_results("run-001", [{"input": "A", "passed": True, "score": 1.0}])

        from repositories.phase2_repository import TestRunRepository
        from models.prompt import TestRun, TestRunStatus
        repo = TestRunRepository()
        tr = TestRun(
            id="run-001", prompt_version_id="pv-001", test_case_id=None,
            model_name="gemini-2.5-flash", status=TestRunStatus.COMPLETED,
            total=1, passed=1, failed=0,
            result_file_path=result_path,
            log_file_path=None,
            started_at=None, completed_at=None,
            created_at="2025-01-01",
        )
        repo.create(tr)

        analysis = self.service.analyze_test_run(
            test_run_id="run-001",
            prompt_content="You are a bot.",
            result_file_path=tr.result_file_path,
            model_name="gemini-2.5-flash",
        )
        self.assertEqual(analysis.summary, "All good")

    def test_load_report(self):
        from storage.test_case_storage import TestRunStorage, AnalysisStorage
        trs = TestRunStorage()
        result_path = trs.save_results("run-002", [{"input": "A", "passed": True}])

        from repositories.phase2_repository import TestRunRepository
        from models.prompt import TestRun, TestRunStatus
        repo = TestRunRepository()
        tr = TestRun(
            id="run-002", prompt_version_id="pv-001", test_case_id=None,
            model_name="m", status=TestRunStatus.COMPLETED,
            total=1, passed=1, failed=0,
            result_file_path=result_path,
            log_file_path=None,
            started_at=None, completed_at=None, created_at="2025-01-01",
        )
        repo.create(tr)

        analysis = self.service.analyze_test_run(
            test_run_id="run-002",
            prompt_content="p",
            result_file_path=tr.result_file_path,
            model_name="m",
        )
        report = self.service.load_report(analysis.id)
        self.assertIsNotNone(report)
        self.assertIn("summary", report)


# ══════════════════════════════════════════════════════════════════════════════
# VariableService
# ══════════════════════════════════════════════════════════════════════════════
class TestVariableService(unittest.TestCase):

    def setUp(self):
        self._tmp_db, self._tmp_dir = _setup_temp_env()
        from services.variable_service import VariableService
        self.service = VariableService()

    def tearDown(self):
        self._tmp_db.close()
        os.unlink(self._tmp_db.name)

    def test_create_and_get(self):
        v = self.service.create("api_key", "secret123")
        fetched = self.service.get(v.id)
        self.assertEqual(fetched.name, "api_key")
        self.assertEqual(fetched.value, "secret123")

    def test_update(self):
        v = self.service.create("name", "old")
        updated = self.service.update(v.id, "name", "new")
        self.assertEqual(updated.value, "new")

    def test_delete(self):
        v = self.service.create("to_delete", "val")
        self.service.delete(v.id)
        self.assertIsNone(self.service.get(v.id))

    def test_get_variables_dict(self):
        self.service.create("a", "1")
        self.service.create("b", "2")
        d = self.service.get_variables_dict()
        self.assertEqual(d, {"a": "1", "b": "2"})


# ══════════════════════════════════════════════════════════════════════════════
# TemplateService
# ══════════════════════════════════════════════════════════════════════════════
class TestTemplateService(unittest.TestCase):

    def setUp(self):
        self._tmp_db, self._tmp_dir = _setup_temp_env()
        from services.template_service import TemplateService
        self.service = TemplateService()

    def tearDown(self):
        self._tmp_db.close()
        os.unlink(self._tmp_db.name)

    def test_create_and_list(self):
        t = self.service.create("greet", "Hello {{name}}", "A greeting template")
        self.assertEqual(len(self.service.list_all()), 1)
        self.assertEqual(t.name, "greet")

    def test_render(self):
        result = self.service.render(
            "Hello {{name}}, you are {{role}}.",
            {"name": "Alice", "role": "admin"},
        )
        self.assertEqual(result, "Hello Alice, you are admin.")

    def test_render_unknown_var_left_as_is(self):
        result = self.service.render("{{x}} and {{y}}", {"x": "1"})
        self.assertEqual(result, "1 and {{y}}")

    def test_update_template(self):
        t = self.service.create("tpl", "old content")
        self.service.update(t.id, "tpl", "new content")
        fetched = self.service.get(t.id)
        self.assertEqual(fetched.content, "new content")


if __name__ == "__main__":
    unittest.main()
