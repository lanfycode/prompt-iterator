"""
Prompt Iterator — application entry point.

Usage:
    cd prompt_iterator
    python app.py

Environment:
    Copy .env.example to .env and set GEMINI_API_KEY before running.
"""
from __future__ import annotations

import sys
import os

# Ensure the project root is importable regardless of cwd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env early (config.py also calls this, double-calling is harmless)
from dotenv import load_dotenv
import gradio as gr
load_dotenv()

from config import APP_TITLE, APP_PORT, ensure_data_dirs
from repositories.database import initialize_db
from services.prompt_service import PromptService
from services.optimization_service import OptimizationService
from services.test_case_service import TestCaseService
from services.test_run_service import TestRunService
from services.analysis_service import AnalysisService
from services.workflow_service import WorkflowService
from services.variable_service import VariableService
from services.template_service import TemplateService
from ui.main import create_ui
from utils.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    logger.info("Starting %s …", APP_TITLE)

    # 1. Ensure data directories and database are initialised
    ensure_data_dirs()
    initialize_db()

    # 2. Instantiate services (singletons shared across all UI handlers)
    prompt_service       = PromptService()
    optimization_service = OptimizationService(prompt_service)
    test_case_service    = TestCaseService()
    test_run_service     = TestRunService()
    analysis_service     = AnalysisService()
    workflow_service     = WorkflowService(
        prompt_service=prompt_service,
        optimization_service=optimization_service,
        test_case_service=test_case_service,
        test_run_service=test_run_service,
        analysis_service=analysis_service,
    )
    variable_service     = VariableService()
    template_service     = TemplateService()

    # 3. Build Gradio application
    app = create_ui(
        prompt_service=prompt_service,
        optimization_service=optimization_service,
        test_case_service=test_case_service,
        test_run_service=test_run_service,
        analysis_service=analysis_service,
        workflow_service=workflow_service,
        variable_service=variable_service,
        template_service=template_service,
    )
    app.queue(default_concurrency_limit=8)

    # 4. Launch
    logger.info("Launching on http://0.0.0.0:%d", APP_PORT)
    app.launch(
        server_name="0.0.0.0",
        server_port=APP_PORT,
        show_error=True,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    main()
