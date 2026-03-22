"""
Repository for TestCase, TestRun, Analysis, WorkflowRun, IterationRound,
Variable, and Template CRUD operations.
"""
from __future__ import annotations

import sqlite3
from typing import List, Optional

from models.prompt import (
    Analysis, IterationRound, Template, TestCase, TestRun, Variable,
    WorkflowRun,
)
from repositories.database import get_connection
from utils.logger import get_logger

logger = get_logger(__name__)


# ── TestCase ──────────────────────────────────────────────────────────────────

class TestCaseRepository:

    def create(self, tc: TestCase) -> TestCase:
        sql = """
            INSERT INTO test_cases
                (id, name, source_type, prompt_version_id, file_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        with get_connection() as conn:
            conn.execute(sql, (
                tc.id, tc.name, tc.source_type,
                tc.prompt_version_id, tc.file_path, tc.created_at,
            ))
            conn.commit()
        logger.debug("Created test_case id=%s name=%s", tc.id, tc.name)
        return tc

    def get(self, tc_id: str) -> Optional[TestCase]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM test_cases WHERE id=?", (tc_id,)
            ).fetchone()
        return _row_to_test_case(row) if row else None

    def list_all(self) -> List[TestCase]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM test_cases ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_test_case(r) for r in rows]

    def list_by_prompt_version(self, prompt_version_id: str) -> List[TestCase]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM test_cases WHERE prompt_version_id=? ORDER BY created_at DESC",
                (prompt_version_id,),
            ).fetchall()
        return [_row_to_test_case(r) for r in rows]


# ── TestRun ───────────────────────────────────────────────────────────────────

class TestRunRepository:

    def create(self, tr: TestRun) -> TestRun:
        sql = """
            INSERT INTO test_runs
                (id, prompt_version_id, test_case_id, model_name, status,
                 total, passed, failed, result_file_path, log_file_path,
                 started_at, completed_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with get_connection() as conn:
            conn.execute(sql, (
                tr.id, tr.prompt_version_id, tr.test_case_id,
                tr.model_name, tr.status,
                tr.total, tr.passed, tr.failed,
                tr.result_file_path, tr.log_file_path,
                tr.started_at, tr.completed_at, tr.created_at,
            ))
            conn.commit()
        logger.debug("Created test_run id=%s", tr.id)
        return tr

    def update(self, tr: TestRun) -> TestRun:
        sql = """
            UPDATE test_runs SET
                status=?, total=?, passed=?, failed=?,
                result_file_path=?, log_file_path=?,
                started_at=?, completed_at=?
            WHERE id=?
        """
        with get_connection() as conn:
            conn.execute(sql, (
                tr.status, tr.total, tr.passed, tr.failed,
                tr.result_file_path, tr.log_file_path,
                tr.started_at, tr.completed_at, tr.id,
            ))
            conn.commit()
        return tr

    def get(self, tr_id: str) -> Optional[TestRun]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM test_runs WHERE id=?", (tr_id,)
            ).fetchone()
        return _row_to_test_run(row) if row else None

    def list_all(self) -> List[TestRun]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM test_runs ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_test_run(r) for r in rows]

    def list_by_prompt_version(self, prompt_version_id: str) -> List[TestRun]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM test_runs WHERE prompt_version_id=? ORDER BY created_at DESC",
                (prompt_version_id,),
            ).fetchall()
        return [_row_to_test_run(r) for r in rows]


# ── Analysis ──────────────────────────────────────────────────────────────────

class AnalysisRepository:

    def create(self, a: Analysis) -> Analysis:
        sql = """
            INSERT INTO analyses (id, test_run_id, file_path, summary, created_at)
            VALUES (?, ?, ?, ?, ?)
        """
        with get_connection() as conn:
            conn.execute(sql, (
                a.id, a.test_run_id, a.file_path, a.summary, a.created_at,
            ))
            conn.commit()
        logger.debug("Created analysis id=%s test_run_id=%s", a.id, a.test_run_id)
        return a

    def get(self, analysis_id: str) -> Optional[Analysis]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM analyses WHERE id=?", (analysis_id,)
            ).fetchone()
        return _row_to_analysis(row) if row else None

    def get_by_test_run(self, test_run_id: str) -> Optional[Analysis]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM analyses WHERE test_run_id=? ORDER BY created_at DESC LIMIT 1",
                (test_run_id,),
            ).fetchone()
        return _row_to_analysis(row) if row else None

    def list_all(self) -> List[Analysis]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM analyses ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_analysis(r) for r in rows]


# ── WorkflowRun ───────────────────────────────────────────────────────────────

class WorkflowRunRepository:

    def create(self, wr: WorkflowRun) -> WorkflowRun:
        sql = """
            INSERT INTO workflow_runs
                (id, prompt_id, model_name, judge_model_name, status,
                 target_pass_rate, max_rounds, current_round,
                 stop_reason, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with get_connection() as conn:
            conn.execute(sql, (
                wr.id, wr.prompt_id, wr.model_name, wr.judge_model_name,
                wr.status, wr.target_pass_rate, wr.max_rounds,
                wr.current_round, wr.stop_reason,
                wr.created_at, wr.completed_at,
            ))
            conn.commit()
        logger.debug("Created workflow_run id=%s", wr.id)
        return wr

    def update(self, wr: WorkflowRun) -> WorkflowRun:
        sql = """
            UPDATE workflow_runs SET
                status=?, current_round=?, stop_reason=?, completed_at=?
            WHERE id=?
        """
        with get_connection() as conn:
            conn.execute(sql, (
                wr.status, wr.current_round,
                wr.stop_reason, wr.completed_at, wr.id,
            ))
            conn.commit()
        return wr

    def get(self, wr_id: str) -> Optional[WorkflowRun]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_runs WHERE id=?", (wr_id,)
            ).fetchone()
        return _row_to_workflow_run(row) if row else None

    def list_all(self) -> List[WorkflowRun]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM workflow_runs ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_workflow_run(r) for r in rows]


# ── IterationRound ────────────────────────────────────────────────────────────

class IterationRoundRepository:

    def create(self, ir: IterationRound) -> IterationRound:
        sql = """
            INSERT INTO iteration_rounds
                (id, workflow_run_id, round_number, prompt_version_id,
                 test_run_id, analysis_id, pass_rate, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        with get_connection() as conn:
            conn.execute(sql, (
                ir.id, ir.workflow_run_id, ir.round_number,
                ir.prompt_version_id, ir.test_run_id,
                ir.analysis_id, ir.pass_rate, ir.created_at,
            ))
            conn.commit()
        return ir

    def update(self, ir: IterationRound) -> IterationRound:
        sql = """
            UPDATE iteration_rounds SET
                test_run_id=?, analysis_id=?, pass_rate=?
            WHERE id=?
        """
        with get_connection() as conn:
            conn.execute(sql, (
                ir.test_run_id, ir.analysis_id, ir.pass_rate, ir.id,
            ))
            conn.commit()
        return ir

    def list_by_workflow(self, workflow_run_id: str) -> List[IterationRound]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM iteration_rounds WHERE workflow_run_id=? ORDER BY round_number",
                (workflow_run_id,),
            ).fetchall()
        return [_row_to_iteration_round(r) for r in rows]


# ── Variable ──────────────────────────────────────────────────────────────────

class VariableRepository:

    def create(self, v: Variable) -> Variable:
        sql = """
            INSERT INTO variables (id, name, value, scope, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        with get_connection() as conn:
            conn.execute(sql, (
                v.id, v.name, v.value, v.scope, v.created_at, v.updated_at,
            ))
            conn.commit()
        return v

    def update(self, v: Variable) -> Variable:
        sql = "UPDATE variables SET name=?, value=?, scope=?, updated_at=? WHERE id=?"
        with get_connection() as conn:
            conn.execute(sql, (v.name, v.value, v.scope, v.updated_at, v.id))
            conn.commit()
        return v

    def delete(self, var_id: str) -> None:
        with get_connection() as conn:
            conn.execute("DELETE FROM variables WHERE id=?", (var_id,))
            conn.commit()

    def get(self, var_id: str) -> Optional[Variable]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM variables WHERE id=?", (var_id,)).fetchone()
        return _row_to_variable(row) if row else None

    def list_all(self) -> List[Variable]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM variables ORDER BY name").fetchall()
        return [_row_to_variable(r) for r in rows]


# ── Template ──────────────────────────────────────────────────────────────────

class TemplateRepository:

    def create(self, t: Template) -> Template:
        sql = """
            INSERT INTO templates (id, name, content, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        with get_connection() as conn:
            conn.execute(sql, (
                t.id, t.name, t.content, t.description,
                t.created_at, t.updated_at,
            ))
            conn.commit()
        return t

    def update(self, t: Template) -> Template:
        sql = """
            UPDATE templates SET name=?, content=?, description=?, updated_at=?
            WHERE id=?
        """
        with get_connection() as conn:
            conn.execute(sql, (t.name, t.content, t.description, t.updated_at, t.id))
            conn.commit()
        return t

    def delete(self, tpl_id: str) -> None:
        with get_connection() as conn:
            conn.execute("DELETE FROM templates WHERE id=?", (tpl_id,))
            conn.commit()

    def get(self, tpl_id: str) -> Optional[Template]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM templates WHERE id=?", (tpl_id,)).fetchone()
        return _row_to_template(row) if row else None

    def list_all(self) -> List[Template]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM templates ORDER BY name").fetchall()
        return [_row_to_template(r) for r in rows]


# ── Row converters ────────────────────────────────────────────────────────────

def _row_to_test_case(row: sqlite3.Row) -> TestCase:
    return TestCase(
        id=row["id"], name=row["name"],
        source_type=row["source_type"],
        prompt_version_id=row["prompt_version_id"],
        file_path=row["file_path"], created_at=row["created_at"],
    )

def _row_to_test_run(row: sqlite3.Row) -> TestRun:
    return TestRun(
        id=row["id"],
        prompt_version_id=row["prompt_version_id"],
        test_case_id=row["test_case_id"],
        model_name=row["model_name"], status=row["status"],
        total=row["total"], passed=row["passed"], failed=row["failed"],
        result_file_path=row["result_file_path"],
        log_file_path=row["log_file_path"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        created_at=row["created_at"],
    )

def _row_to_analysis(row: sqlite3.Row) -> Analysis:
    return Analysis(
        id=row["id"], test_run_id=row["test_run_id"],
        file_path=row["file_path"], summary=row["summary"],
        created_at=row["created_at"],
    )

def _row_to_workflow_run(row: sqlite3.Row) -> WorkflowRun:
    return WorkflowRun(
        id=row["id"], prompt_id=row["prompt_id"],
        model_name=row["model_name"],
        judge_model_name=row["judge_model_name"],
        status=row["status"],
        target_pass_rate=row["target_pass_rate"],
        max_rounds=row["max_rounds"],
        current_round=row["current_round"],
        stop_reason=row["stop_reason"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )

def _row_to_iteration_round(row: sqlite3.Row) -> IterationRound:
    return IterationRound(
        id=row["id"],
        workflow_run_id=row["workflow_run_id"],
        round_number=row["round_number"],
        prompt_version_id=row["prompt_version_id"],
        test_run_id=row["test_run_id"],
        analysis_id=row["analysis_id"],
        pass_rate=row["pass_rate"],
        created_at=row["created_at"],
    )

def _row_to_variable(row: sqlite3.Row) -> Variable:
    return Variable(
        id=row["id"], name=row["name"], value=row["value"],
        scope=row["scope"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )

def _row_to_template(row: sqlite3.Row) -> Template:
    return Template(
        id=row["id"], name=row["name"], content=row["content"],
        description=row["description"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )
