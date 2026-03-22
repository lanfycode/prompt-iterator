"""
Main Gradio application builder.

Assembles all tabs inside a single gr.Blocks context using a nested
L1 + L2 tab structure and wires cross-page state.
"""
from __future__ import annotations

import gradio as gr

from services.prompt_service import PromptService
from services.optimization_service import OptimizationService
from services.test_case_service import TestCaseService
from services.test_run_service import TestRunService
from services.analysis_service import AnalysisService
from services.workflow_service import WorkflowService
from services.variable_service import VariableService
from services.template_service import TemplateService

from ui.pages import (
    prompt_generate_page,
    prompt_optimize_page,
    prompt_list_page,
    test_case_page,
    batch_test_page,
    analysis_page,
    analysis_optimize_page,
    one_click_page,
    history_page,
    variable_page,
    template_page,
)


def create_ui(
    prompt_service:       PromptService,
    optimization_service: OptimizationService,
    test_case_service:    TestCaseService,
    test_run_service:     TestRunService,
    analysis_service:     AnalysisService,
    workflow_service:     WorkflowService,
    variable_service:     VariableService,
    template_service:     TemplateService,
) -> gr.Blocks:
    """Build and return the Gradio Blocks application."""

    with gr.Blocks(
        title="Prompt Iterator",
        analytics_enabled=False,
    ) as app:
        gr.Markdown(
            "# ✨ Prompt Iterator\n"
            "> Prompt 工程工作台 — 生成、优化、测试、分析、迭代"
        )

        with gr.Tabs():
            # ── L1: Prompt 管理 ───────────────────────────────────────────
            with gr.Tab("📝 Prompt 管理"):
                with gr.Tabs():
                    with gr.Tab("生成"):
                        prompt_generate_page.build(prompt_service)
                    with gr.Tab("优化"):
                        original_box, prompt_id_state = prompt_optimize_page.build(
                            prompt_service, optimization_service
                        )
                    with gr.Tab("列表"):
                        prompt_list_page.build(
                            prompt_service,
                            original_box=original_box,
                            prompt_id_state=prompt_id_state,
                        )

            # ── L1: 测试 ─────────────────────────────────────────────────
            with gr.Tab("🧪 测试"):
                with gr.Tabs():
                    with gr.Tab("测试用例"):
                        test_case_page.build(prompt_service, test_case_service)
                    with gr.Tab("批量测试"):
                        batch_test_page.build(
                            prompt_service, test_case_service, test_run_service
                        )

            # ── L1: 分析与优化 ────────────────────────────────────────────
            with gr.Tab("📊 分析与优化"):
                with gr.Tabs():
                    with gr.Tab("结果分析"):
                        analysis_page.build(
                            prompt_service, test_run_service, analysis_service
                        )
                    with gr.Tab("分析优化"):
                        analysis_optimize_page.build(
                            prompt_service, optimization_service,
                            test_run_service, analysis_service,
                        )
                    with gr.Tab("一键优化"):
                        one_click_page.build(prompt_service, workflow_service)

            # ── L1: 配置 ─────────────────────────────────────────────────
            with gr.Tab("⚙️ 配置"):
                with gr.Tabs():
                    with gr.Tab("变量管理"):
                        variable_page.build(variable_service)
                    with gr.Tab("模板管理"):
                        template_page.build(template_service, variable_service)

            # ── L1: 历史 ─────────────────────────────────────────────────
            with gr.Tab("📋 历史"):
                history_page.build(
                    test_run_service, analysis_service, workflow_service
                )

    return app
