"""Result Analysis page — analyse batch test results."""
from __future__ import annotations

from typing import Any

import gradio as gr

from llm.model_registry import get_model_names, DEFAULT_MODEL_NAME
from services.analysis_service import AnalysisService
from services.prompt_service import PromptService
from services.test_run_service import TestRunService
from utils.logger import get_logger

logger = get_logger(__name__)


def build(
    prompt_service: PromptService,
    test_run_service: TestRunService,
    analysis_service: AnalysisService,
) -> dict[str, Any]:
    gr.Markdown(
        "## 结果分析\n"
        "选择一次已完成的测试任务，生成失败分类、错误模式和优化建议。"
    )

    with gr.Row():
        with gr.Column(scale=1):
            run_selector = gr.Dropdown(
                label="选择测试任务", choices=[], allow_custom_value=False,
            )
            refresh_btn = gr.Button("🔄 刷新任务列表", size="sm")
            language_selector = gr.Dropdown(
                label="分析语言",
                choices=[("中文", "zh"), ("英文", "en")],
                value="zh",
                allow_custom_value=False,
            )
            model_selector = gr.Dropdown(
                choices=get_model_names(), value=DEFAULT_MODEL_NAME,
                label="分析模型", interactive=True,
            )
            analyze_validation = gr.Textbox(
                label="表单提示",
                interactive=False,
                value="请选择一条测试任务后开始分析。",
            )
            analyze_btn = gr.Button("🔍 执行分析", variant="primary", interactive=False)
            analysis_status = gr.Textbox(label="状态", interactive=False)

        with gr.Column(scale=2):
            summary_box = gr.Textbox(label="分析摘要", lines=3, interactive=False)
            report_output = gr.JSON(label="完整分析报告")

    # States
    run_id_state = gr.State(value=None)
    analysis_id_state = gr.State(value=None)

    def _refresh():
        runs = test_run_service.list_test_runs()
        choices = []
        for r in runs:
            status_icon = "✅" if r.status == "completed" else "❌"
            rate = f"{r.passed}/{r.total}" if r.total > 0 else "N/A"
            choices.append(f"{r.id[:8]}  {status_icon} {rate}  {r.model_name}  ({r.created_at[:19]})")
        return gr.update(choices=choices, value=None)

    def _on_select_run(val):
        if not val:
            return None
        prefix = val.split()[0]
        runs = test_run_service.list_test_runs()
        match = next((r for r in runs if r.id.startswith(prefix)), None)
        return match.id if match else None

    def _validate_run(val):
        if not val:
            return "请选择一条测试任务后开始分析。", gr.update(interactive=False)
        return "参数已就绪，可以执行分析。", gr.update(interactive=True)

    def _on_analyze(run_id, model, language):
        if not run_id:
            return gr.update(), gr.update(), "⚠ 请先选择测试任务。", None
        tr = test_run_service.get_test_run(run_id)
        if not tr:
            return gr.update(), gr.update(), "⚠ 未找到测试任务。", None
        if not tr.result_file_path:
            return gr.update(), gr.update(), "⚠ 该测试任务没有结果文件。", None

        # Retrieve prompt content
        version = prompt_service.get_version_with_content(tr.prompt_version_id)
        prompt_content = version.content if version else ""

        try:
            analysis = analysis_service.analyze_test_run(
                test_run_id=run_id,
                prompt_content=prompt_content,
                result_file_path=tr.result_file_path,
                model_name=model,
                response_language=language,
            )
            report = analysis_service.load_report(analysis.id)
            return (
                analysis.summary,
                report,
                f"✅ 分析完成（ID: {analysis.id[:8]}…）",
                analysis.id,
            )
        except Exception as exc:
            logger.error("Analysis failed: %s", exc)
            return gr.update(), gr.update(), f"❌ 分析失败：{exc}", None

    refresh_btn.click(fn=_refresh, outputs=[run_selector])
    run_selector.change(fn=_on_select_run, inputs=[run_selector], outputs=[run_id_state])
    run_selector.change(fn=_validate_run, inputs=[run_selector], outputs=[analyze_validation, analyze_btn])
    analyze_btn.click(
        fn=_on_analyze, inputs=[run_id_state, model_selector, language_selector],
        outputs=[summary_box, report_output, analysis_status, analysis_id_state],
    )

    return {
        "load_fn": _refresh,
        "load_outputs": [run_selector],
    }
