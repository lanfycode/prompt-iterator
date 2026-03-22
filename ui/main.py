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
    single_test_page,
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
    prompt_service: PromptService,
    optimization_service: OptimizationService,
    test_case_service: TestCaseService,
    test_run_service: TestRunService,
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
            with gr.Tab("📝 Prompt 管理"):
                with gr.Tabs():
                    with gr.Tab("生成"):
                        prompt_generate_page.build(prompt_service)
                    with gr.Tab("优化"):
                        original_box, prompt_id_state = prompt_optimize_page.build(
                            prompt_service, optimization_service
                        )
                    prompt_list_tab = gr.Tab("列表")

            with gr.Tab("🧪 测试"):
                with gr.Tabs():
                    with gr.Tab("单轮测试"):
                        single_test_bindings = single_test_page.build(
                            prompt_service,
                            variable_service,
                            template_service,
                            test_run_service,
                        )
                    with gr.Tab("测试用例"):
                        test_case_bindings = test_case_page.build(
                            prompt_service,
                            test_case_service,
                        )
                    with gr.Tab("批量测试"):
                        batch_test_bindings = batch_test_page.build(
                            prompt_service,
                            test_case_service,
                            test_run_service,
                        )

            with gr.Tab("📊 分析与优化"):
                with gr.Tabs():
                    with gr.Tab("结果分析"):
                        analysis_bindings = analysis_page.build(
                            prompt_service, test_run_service, analysis_service
                        )
                    with gr.Tab("分析优化"):
                        analysis_optimize_bindings = analysis_optimize_page.build(
                            prompt_service, optimization_service,
                            test_run_service, analysis_service,
                        )
                    with gr.Tab("一键优化"):
                        workflow_bindings = one_click_page.build(
                            prompt_service,
                            workflow_service,
                        )

            with prompt_list_tab:
                prompt_list_bindings = prompt_list_page.build(
                    prompt_service,
                    original_box=original_box,
                    prompt_id_state=prompt_id_state,
                    single_prompt_selector=single_test_bindings["prompt_selector"],
                    single_prompt_id_state=single_test_bindings["prompt_id_state"],
                    single_version_id_state=single_test_bindings["version_id_state"],
                    single_prompt_summary=single_test_bindings["prompt_summary"],
                    single_prompt_content_preview=single_test_bindings["prompt_content_preview"],
                    single_action_validation=single_test_bindings["action_validation"],
                    single_preview_btn=single_test_bindings["preview_btn"],
                    single_run_btn=single_test_bindings["run_btn"],
                    batch_prompt_selector=batch_test_bindings["prompt_selector"],
                    batch_prompt_id_state=batch_test_bindings["prompt_id_state"],
                    batch_version_id_state=batch_test_bindings["version_id_state"],
                    batch_prompt_summary=batch_test_bindings["prompt_summary"],
                    batch_run_validation=batch_test_bindings["run_validation"],
                    batch_run_btn=batch_test_bindings["run_btn"],
                    workflow_prompt_selector=workflow_bindings["prompt_selector"],
                    workflow_prompt_id_state=workflow_bindings["prompt_id_state"],
                    workflow_prompt_summary=workflow_bindings["prompt_summary"],
                    workflow_start_validation=workflow_bindings["start_validation"],
                    workflow_start_btn=workflow_bindings["start_btn"],
                )

            with gr.Tab("⚙️ 配置"):
                with gr.Tabs():
                    with gr.Tab("变量管理"):
                        variable_page.build(variable_service)
                    with gr.Tab("模板管理"):
                        template_page.build(template_service, variable_service)

            with gr.Tab("📋 历史"):
                history_bindings = history_page.build(
                    prompt_service,
                    test_run_service, analysis_service, workflow_service
                    ,
                    single_test_bindings["prompt_selector"],
                    single_test_bindings["prompt_id_state"],
                    single_test_bindings["version_id_state"],
                    single_test_bindings["prompt_summary"],
                    single_test_bindings["prompt_content_preview"],
                    single_test_bindings["template_selector"],
                    single_test_bindings["template_preview"],
                    single_test_bindings["variables_box"],
                    single_test_bindings["user_input_box"],
                    single_test_bindings["model_selector"],
                    single_test_bindings["action_validation"],
                    single_test_bindings["preview_btn"],
                    single_test_bindings["run_btn"],
                    single_test_bindings["run_status"],
                )

        for bindings in [
            prompt_list_bindings,
            single_test_bindings,
            test_case_bindings,
            batch_test_bindings,
            analysis_bindings,
            analysis_optimize_bindings,
            workflow_bindings,
            history_bindings,
        ]:
            app.load(fn=bindings["load_fn"], outputs=bindings["load_outputs"])

    return app
