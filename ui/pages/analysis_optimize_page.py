"""Analysis-based Optimization page — optimize prompt using analysis results."""
from __future__ import annotations

import difflib
from typing import Any

import gradio as gr

from llm.model_registry import get_model_names, DEFAULT_MODEL_NAME
from services.analysis_service import AnalysisService
from services.optimization_service import OptimizationService
from services.prompt_service import PromptService
from services.test_run_service import TestRunService
from utils.logger import get_logger

logger = get_logger(__name__)


def build(
    prompt_service: PromptService,
    optimization_service: OptimizationService,
    test_run_service: TestRunService,
    analysis_service:     AnalysisService,
) -> dict[str, Any]:
    gr.Markdown(
        "## 基于分析优化\n"
        "选择一次测试分析结果，系统将根据失败模式和建议自动优化 Prompt。"
    )

    with gr.Row():
        with gr.Column(scale=1):
            analysis_selector = gr.Dropdown(
                label="选择分析报告", choices=[], allow_custom_value=False,
            )
            refresh_btn = gr.Button("🔄 刷新分析列表", size="sm")
            model_selector = gr.Dropdown(
                choices=get_model_names(), value=DEFAULT_MODEL_NAME,
                label="优化模型", interactive=True,
            )
            optimize_validation = gr.Textbox(
                label="表单提示",
                interactive=False,
                value="请选择一条分析报告后开始定向优化。",
            )
            optimize_btn = gr.Button("⚡ 执行定向优化", variant="primary", interactive=False)
            opt_status = gr.Textbox(label="状态", interactive=False)

        with gr.Column(scale=1):
            gr.Markdown("### 原始 Prompt")
            original_box = gr.Textbox(lines=10, interactive=False)

        with gr.Column(scale=1):
            gr.Markdown("### 优化后 Prompt")
            optimized_box = gr.Textbox(lines=10, interactive=False)
            call_info = gr.JSON(label="调用信息")

    diff_html = gr.HTML(label="变更对比")

    # States
    analysis_id_state = gr.State(value=None)
    prompt_id_state = gr.State(value=None)

    def _refresh():
        analyses = analysis_service.list_analyses()
        choices = [
            f"{a.id[:8]}  {a.summary[:40]}  ({a.created_at[:19]})"
            for a in analyses
        ]
        return gr.update(choices=choices, value=None)

    def _on_select_analysis(val):
        if not val:
            return None, gr.update(), None
        prefix = val.split()[0]
        analyses = analysis_service.list_analyses()
        match = next((a for a in analyses if a.id.startswith(prefix)), None)
        if not match:
            return None, gr.update(), None

        # Load original prompt via test_run chain
        tr = test_run_service.get_test_run(match.test_run_id)
        if not tr:
            return match.id, gr.update(), None

        version = prompt_service.get_version_with_content(tr.prompt_version_id)
        prompt_content = version.content if version else ""
        prompt_id = version.prompt_id if version else None

        return match.id, prompt_content, prompt_id

    def _validate_analysis(val):
        if not val:
            return "请选择一条分析报告后开始定向优化。", gr.update(interactive=False)
        return "参数已就绪，可以执行定向优化。", gr.update(interactive=True)

    def _on_optimize(analysis_id, prompt_id, original_text, model):
        if not analysis_id or not prompt_id:
            return gr.update(), gr.update(), gr.update(), "⚠ 请先选择分析报告。"
        try:
            analysis_context = analysis_service.get_analysis_context(analysis_id)
            prompt, version, response = optimization_service.optimize_and_save(
                prompt_id=prompt_id,
                optimization_request="根据测试失败分析结果优化 Prompt",
                model_name=model,
                analysis_context=analysis_context,
            )
            meta = {
                "model": response.model_name,
                "latency_ms": round(response.latency_ms, 1),
                "new_version": f"v{version.version}",
            }
            optimized = prompt_service.get_version_with_content(version.id)
            after_text = optimized.content if optimized else ""
            diff = difflib.HtmlDiff(wrapcolumn=80).make_table(
                (original_text or "").splitlines(),
                after_text.splitlines(),
                fromdesc="原始 Prompt",
                todesc="优化后 Prompt",
                context=True,
                numlines=2,
            )
            return after_text, meta, diff, f"✅ 已生成 v{version.version}"
        except Exception as exc:
            logger.error("Analysis-based optimization failed: %s", exc)
            return gr.update(), gr.update(), gr.update(), f"❌ 优化失败：{exc}"

    refresh_btn.click(fn=_refresh, outputs=[analysis_selector])
    analysis_selector.change(
        fn=_on_select_analysis, inputs=[analysis_selector],
        outputs=[analysis_id_state, original_box, prompt_id_state],
    )
    analysis_selector.change(
        fn=_validate_analysis,
        inputs=[analysis_selector],
        outputs=[optimize_validation, optimize_btn],
    )
    optimize_btn.click(
        fn=_on_optimize,
        inputs=[analysis_id_state, prompt_id_state, original_box, model_selector],
        outputs=[optimized_box, call_info, diff_html, opt_status],
    )

    return {
        "load_fn": _refresh,
        "load_outputs": [analysis_selector],
        "analysis_selector": analysis_selector,
        "analysis_id_state": analysis_id_state,
        "prompt_id_state": prompt_id_state,
        "original_box": original_box,
        "optimize_validation": optimize_validation,
        "optimize_btn": optimize_btn,
        "opt_status": opt_status,
    }
