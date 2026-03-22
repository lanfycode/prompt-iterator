"""
Batch Test page — run batch tests and view progress/results.
"""
from __future__ import annotations

import json
import threading
from typing import Optional

import gradio as gr

from llm.model_registry import get_model_names, DEFAULT_MODEL_NAME
from services.prompt_service import PromptService
from services.test_case_service import TestCaseService
from services.test_run_service import TestRunService
from utils.logger import get_logger

logger = get_logger(__name__)


def build(
    prompt_service:    PromptService,
    test_case_service: TestCaseService,
    test_run_service:  TestRunService,
) -> None:
    gr.Markdown(
        "## 批量测试\n"
        "选择 Prompt 和测试用例集，执行批量测试并查看结果统计。"
    )

    with gr.Row():
        with gr.Column(scale=1):
            prompt_selector = gr.Dropdown(
                label="选择 Prompt", choices=[], allow_custom_value=True,
            )
            tc_selector = gr.Dropdown(
                label="选择测试用例集", choices=[], allow_custom_value=True,
            )
            refresh_btn = gr.Button("🔄 刷新列表", size="sm")

            model_selector = gr.Dropdown(
                choices=get_model_names(), value=DEFAULT_MODEL_NAME,
                label="测试模型", interactive=True,
            )
            judge_model_selector = gr.Dropdown(
                choices=get_model_names(), value=DEFAULT_MODEL_NAME,
                label="评判模型（LLM Judge）", interactive=True,
            )
            concurrency_slider = gr.Slider(
                minimum=1, maximum=10, value=3, step=1,
                label="并发数",
            )
            run_btn = gr.Button("▶ 启动批量测试", variant="primary")

        with gr.Column(scale=2):
            progress_box = gr.Textbox(
                label="执行进度", lines=10, max_lines=20, interactive=False,
            )
            result_summary = gr.JSON(label="结果统计")
            run_status = gr.Textbox(label="状态", interactive=False)

    # States
    prompt_id_state = gr.State(value=None)
    version_id_state = gr.State(value=None)
    tc_id_state = gr.State(value=None)
    run_id_state = gr.State(value=None)

    gr.Markdown("### 测试结果详情")
    results_output = gr.JSON(label="逐条结果")
    load_results_btn = gr.Button("📋 加载最近结果详情", size="sm")

    def _refresh():
        prompts = prompt_service.list_prompts()
        p_choices = [f"{p.id[:8]}  {p.name}" for p in prompts]
        tcs = test_case_service.list_test_cases()
        tc_choices = [f"{tc.id[:8]}  {tc.name}" for tc in tcs]
        return gr.update(choices=p_choices, value=None), gr.update(choices=tc_choices, value=None)

    def _on_select_prompt(val):
        if not val:
            return None, None
        prefix = val.split()[0]
        prompts = prompt_service.list_prompts()
        match = next((p for p in prompts if p.id.startswith(prefix)), None)
        if not match:
            return None, None
        latest = prompt_service.get_latest_version_with_content(match.id)
        return match.id, latest.id if latest else None

    def _on_select_tc(val):
        if not val:
            return None
        prefix = val.split()[0]
        tcs = test_case_service.list_test_cases()
        match = next((tc for tc in tcs if tc.id.startswith(prefix)), None)
        return match.id if match else None

    def _on_run(prompt_id, version_id, tc_id, model, judge_model, concurrency):
        if not prompt_id or not version_id:
            return gr.update(), gr.update(), "⚠ 请先选择 Prompt。", None
        if not tc_id:
            return gr.update(), gr.update(), "⚠ 请先选择测试用例集。", None

        version = prompt_service.get_version_with_content(version_id)
        if not version or not version.content:
            return gr.update(), gr.update(), "⚠ Prompt 内容为空。", None

        cases = test_case_service.load_cases(tc_id)
        if not cases:
            return gr.update(), gr.update(), "⚠ 测试用例为空。", None

        log_lines = []

        def on_progress(completed, total, line):
            log_lines.append(line)

        try:
            tr = test_run_service.run_batch_test(
                prompt_content=version.content,
                prompt_version_id=version_id,
                test_case_id=tc_id,
                cases=cases,
                model_name=model,
                judge_model_name=judge_model,
                concurrency=int(concurrency),
                on_progress=on_progress,
            )
            summary = {
                "run_id": tr.id[:8],
                "status": tr.status,
                "total": tr.total,
                "passed": tr.passed,
                "failed": tr.failed,
                "pass_rate": f"{tr.passed / tr.total:.1%}" if tr.total > 0 else "N/A",
            }
            return "\n".join(log_lines), summary, f"✅ 测试完成（{tr.status}）", tr.id
        except Exception as exc:
            logger.error("Batch test failed: %s", exc)
            return "\n".join(log_lines), gr.update(), f"❌ 测试失败：{exc}", None

    def _load_results(run_id):
        if not run_id:
            return "⚠ 暂无测试结果。"
        results = test_run_service.get_results(run_id)
        return results or []

    refresh_btn.click(fn=_refresh, outputs=[prompt_selector, tc_selector])

    prompt_selector.change(
        fn=_on_select_prompt, inputs=[prompt_selector],
        outputs=[prompt_id_state, version_id_state],
    )
    tc_selector.change(
        fn=_on_select_tc, inputs=[tc_selector],
        outputs=[tc_id_state],
    )

    run_btn.click(
        fn=_on_run,
        inputs=[prompt_id_state, version_id_state, tc_id_state,
                model_selector, judge_model_selector, concurrency_slider],
        outputs=[progress_box, result_summary, run_status, run_id_state],
    )

    load_results_btn.click(
        fn=_load_results, inputs=[run_id_state],
        outputs=[results_output],
    )
