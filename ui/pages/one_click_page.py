"""
One-Click Optimization page — automated multi-round iteration.
"""
from __future__ import annotations

import threading
from typing import Optional

import gradio as gr

from llm.model_registry import get_model_names, DEFAULT_MODEL_NAME
from services.prompt_service import PromptService
from services.workflow_service import WorkflowService
from utils.logger import get_logger

logger = get_logger(__name__)


def build(
    prompt_service:   PromptService,
    workflow_service: WorkflowService,
) -> None:
    gr.Markdown(
        "## 一键优化\n"
        "选择 Prompt，设定目标通过率和最大轮次，系统将自动执行\n"
        "**测试 → 分析 → 优化 → 再测试** 闭环，直至达标或停止。"
    )

    with gr.Row():
        with gr.Column(scale=1):
            prompt_selector = gr.Dropdown(
                label="选择 Prompt", choices=[], allow_custom_value=True,
            )
            refresh_btn = gr.Button("🔄 刷新 Prompt 列表", size="sm")
            model_selector = gr.Dropdown(
                choices=get_model_names(), value=DEFAULT_MODEL_NAME,
                label="测试/优化模型", interactive=True,
            )
            judge_model_selector = gr.Dropdown(
                choices=get_model_names(), value=DEFAULT_MODEL_NAME,
                label="评判模型", interactive=True,
            )
            target_slider = gr.Slider(
                minimum=0.5, maximum=1.0, value=0.8, step=0.05,
                label="目标通过率",
            )
            max_rounds_slider = gr.Slider(
                minimum=1, maximum=10, value=5, step=1,
                label="最大迭代轮次",
            )
            num_cases_slider = gr.Slider(
                minimum=3, maximum=30, value=10, step=1,
                label="每轮测试用例数",
            )
            concurrency_slider = gr.Slider(
                minimum=1, maximum=10, value=3, step=1,
                label="并发数",
            )
            with gr.Row():
                start_btn = gr.Button("🚀 开始一键优化", variant="primary")
                stop_btn  = gr.Button("⏹ 停止", variant="stop")

        with gr.Column(scale=2):
            status_box = gr.Textbox(
                label="运行状态", lines=2, interactive=False,
            )
            rounds_box = gr.Textbox(
                label="轮次记录", lines=12, max_lines=25, interactive=False,
            )
            progress_box = gr.Textbox(
                label="测试进度日志", lines=8, max_lines=15, interactive=False,
            )

    # States
    prompt_id_state = gr.State(value=None)
    workflow_id_state = gr.State(value=None)

    def _refresh():
        prompts = prompt_service.list_prompts()
        choices = [f"{p.id[:8]}  {p.name}" for p in prompts]
        return gr.update(choices=choices, value=None)

    def _on_select_prompt(val):
        if not val:
            return None
        prefix = val.split()[0]
        prompts = prompt_service.list_prompts()
        match = next((p for p in prompts if p.id.startswith(prefix)), None)
        return match.id if match else None

    def _on_start(prompt_id, model, judge_model, target, max_rounds, num_cases, concurrency):
        if not prompt_id:
            return "⚠ 请先选择 Prompt。", gr.update(), gr.update(), None

        round_lines = []
        progress_lines = []

        def on_round_complete(round_num, pass_rate, summary):
            line = f"轮次 {round_num}: 通过率 {pass_rate:.1%} — {summary}"
            round_lines.append(line)

        def on_progress(completed, total, log_line):
            progress_lines.append(log_line)

        try:
            wr = workflow_service.run_one_click_optimization(
                prompt_id=prompt_id,
                model_name=model,
                judge_model_name=judge_model,
                target_pass_rate=target,
                max_rounds=int(max_rounds),
                num_cases=int(num_cases),
                concurrency=int(concurrency),
                on_round_complete=on_round_complete,
                on_progress=on_progress,
            )
            status = f"状态: {wr.status}\n停止原因: {wr.stop_reason or 'N/A'}"
            return (
                status,
                "\n".join(round_lines) or "（无轮次记录）",
                "\n".join(progress_lines[-30:]) or "（无日志）",
                wr.id,
            )
        except Exception as exc:
            logger.error("One-click optimization failed: %s", exc)
            return (
                f"❌ 运行失败：{exc}",
                "\n".join(round_lines),
                "\n".join(progress_lines[-30:]),
                None,
            )

    def _on_stop(workflow_id):
        if not workflow_id:
            return "⚠ 没有正在运行的工作流。"
        workflow_service.stop_workflow(workflow_id)
        return "已发送停止信号。"

    refresh_btn.click(fn=_refresh, outputs=[prompt_selector])
    prompt_selector.change(fn=_on_select_prompt, inputs=[prompt_selector], outputs=[prompt_id_state])

    start_btn.click(
        fn=_on_start,
        inputs=[prompt_id_state, model_selector, judge_model_selector,
                target_slider, max_rounds_slider, num_cases_slider,
                concurrency_slider],
        outputs=[status_box, rounds_box, progress_box, workflow_id_state],
    )
    stop_btn.click(
        fn=_on_stop, inputs=[workflow_id_state],
        outputs=[status_box],
    )
