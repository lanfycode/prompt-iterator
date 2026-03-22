"""One-Click Optimization page — automated multi-round iteration."""
from __future__ import annotations

import threading
import time
from typing import Any

import gradio as gr

from llm.model_registry import get_model_names, DEFAULT_MODEL_NAME
from services.prompt_service import PromptService
from services.workflow_service import WorkflowService
from utils.logger import get_logger

logger = get_logger(__name__)


def build(
    prompt_service: PromptService,
    workflow_service: WorkflowService,
) -> dict[str, Any]:
    gr.Markdown(
        "## 一键优化\n"
        "选择 Prompt，设定目标通过率和最大轮次，系统将自动执行\n"
        "**测试 → 分析 → 优化 → 再测试** 闭环，直至达标或停止。"
    )

    with gr.Row():
        with gr.Column(scale=1):
            prompt_selector = gr.Dropdown(
                label="选择 Prompt", choices=[], allow_custom_value=False,
            )
            refresh_btn = gr.Button("🔄 刷新 Prompt 列表", size="sm")
            prompt_summary = gr.Textbox(
                label="当前优化基线",
                interactive=False,
                placeholder="选择 Prompt 后将显示当前版本和标识信息。",
            )
            model_selector = gr.Dropdown(
                choices=get_model_names(), value=DEFAULT_MODEL_NAME,
                label="测试/优化模型", interactive=True,
            )
            judge_model_selector = gr.Dropdown(
                choices=get_model_names(), value=DEFAULT_MODEL_NAME,
                label="评判模型", interactive=True,
            )
            language_selector = gr.Dropdown(
                label="分析语言",
                choices=[("中文", "zh"), ("英文", "en")],
                value="zh",
                allow_custom_value=False,
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
            start_validation = gr.Textbox(
                label="表单提示",
                interactive=False,
                value="请选择 Prompt 后开始一键优化。",
            )
            with gr.Row():
                start_btn = gr.Button("🚀 开始一键优化", variant="primary", interactive=False)
                stop_btn  = gr.Button("⏹ 停止", variant="stop", interactive=False)

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

    def _start_validation_message(prompt_value):
        if not prompt_value:
            return "请先选择一个 Prompt。", gr.update(interactive=False)
        return "参数已就绪，可以开始一键优化。", gr.update(interactive=True)

    def _refresh():
        prompts = prompt_service.list_prompts()
        choices = [f"{p.id[:8]}  {p.name}" for p in prompts]
        return gr.update(choices=choices, value=None)

    def _on_select_prompt(val):
        if not val:
            return None, ""
        prefix = val.split()[0]
        prompts = prompt_service.list_prompts()
        match = next((p for p in prompts if p.id.startswith(prefix)), None)
        if not match:
            return None, ""
        latest = prompt_service.get_latest_version_with_content(match.id)
        summary = (
            f"Prompt: {match.name}\n"
            f"Prompt ID: {match.id}\n"
            f"当前版本: v{latest.version if latest else match.current_version}\n"
            f"更新时间: {match.updated_at[:19].replace('T', ' ')}"
        )
        return match.id, summary

    def _on_start(prompt_id, model, judge_model, language, target, max_rounds, num_cases, concurrency):
        if not prompt_id:
            return "⚠ 请先选择 Prompt。", gr.update(), gr.update(), None, gr.update(interactive=False), gr.update(interactive=True)

        round_lines = []
        progress_lines = []
        task_state = {
            "workflow_id": None,
            "done": False,
            "error": None,
            "result": None,
        }

        def on_started(workflow_id):
            task_state["workflow_id"] = workflow_id

        def on_round_start(round_num):
            progress_lines.append(f"=====轮次【{round_num}】=====")

        def on_round_complete(round_num, pass_rate, summary):
            line = f"轮次 {round_num}: 通过率 {pass_rate:.1%} — {summary}"
            round_lines.append(line)

        def on_progress(completed, total, log_line):
            progress_lines.append(log_line)

        def worker():
            try:
                wr = workflow_service.run_one_click_optimization(
                    prompt_id=prompt_id,
                    model_name=model,
                    judge_model_name=judge_model,
                    analysis_language=language,
                    target_pass_rate=target,
                    max_rounds=int(max_rounds),
                    num_cases=int(num_cases),
                    concurrency=int(concurrency),
                    on_started=on_started,
                    on_round_start=on_round_start,
                    on_round_complete=on_round_complete,
                    on_progress=on_progress,
                )
                task_state["workflow_id"] = wr.id
                task_state["result"] = wr
            except Exception as exc:
                logger.error("One-click optimization failed: %s", exc)
                task_state["error"] = str(exc)
            finally:
                task_state["done"] = True

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        while thread.is_alive() or not task_state["done"]:
            workflow_id = task_state["workflow_id"]
            if task_state["error"]:
                yield (
                    f"❌ 一键优化失败\n原因: {task_state['error']}",
                    "\n".join(round_lines) or "（无轮次记录）",
                    "\n".join(progress_lines[-30:]) or "（无日志）",
                    workflow_id,
                    gr.update(interactive=False),
                    gr.update(interactive=True),
                )
                return

            status = "工作流启动中…"
            if workflow_id:
                wr = workflow_service.get_workflow_run(workflow_id)
                if wr:
                    status = (
                        f"⏳ 一键优化进行中\n状态: {wr.status}\n"
                        f"当前轮次: {wr.current_round}/{wr.max_rounds}\n"
                        f"停止原因: {wr.stop_reason or 'N/A'}"
                    )

            yield (
                status,
                "\n".join(round_lines) or "（无轮次记录）",
                "\n".join(progress_lines[-30:]) or "（等待首条日志）",
                workflow_id,
                gr.update(interactive=True),
                gr.update(interactive=False),
            )
            time.sleep(0.4)

        wr = task_state["result"]
        final_status = "状态未知"
        workflow_id = task_state["workflow_id"]
        if wr:
            final_status = (
                f"✅ 一键优化已完成\n"
                f"状态: {wr.status}\n"
                f"停止原因: {wr.stop_reason or 'N/A'}"
            )
            if wr.status == "canceled":
                final_status = (
                    f"⏹ 一键优化已停止\n"
                    f"状态: {wr.status}\n"
                    f"停止原因: {wr.stop_reason or 'N/A'}"
                )
            elif wr.status == "failed":
                final_status = (
                    f"❌ 一键优化失败\n"
                    f"状态: {wr.status}\n"
                    f"停止原因: {wr.stop_reason or 'N/A'}"
                )
        elif task_state["error"]:
            final_status = f"❌ 一键优化失败\n原因: {task_state['error']}"
        yield (
            final_status,
            "\n".join(round_lines) or "（无轮次记录）",
            "\n".join(progress_lines[-50:]) or "（无日志）",
            workflow_id,
            gr.update(interactive=False),
            gr.update(interactive=True),
        )

    def _on_stop(workflow_id):
        if not workflow_id:
            return "⚠ 没有正在运行的工作流。", gr.update(interactive=False)
        workflow_service.stop_workflow(workflow_id)
        return "⏹ 已发送停止信号，当前轮结束后将停止。", gr.update(interactive=False)

    refresh_btn.click(fn=_refresh, outputs=[prompt_selector])
    prompt_selector.change(
        fn=_on_select_prompt,
        inputs=[prompt_selector],
        outputs=[prompt_id_state, prompt_summary],
    )
    prompt_selector.change(
        fn=_start_validation_message,
        inputs=[prompt_selector],
        outputs=[start_validation, start_btn],
    )

    start_btn.click(
        fn=_on_start,
        inputs=[prompt_id_state, model_selector, judge_model_selector, language_selector,
                target_slider, max_rounds_slider, num_cases_slider,
                concurrency_slider],
        outputs=[status_box, rounds_box, progress_box, workflow_id_state, stop_btn, start_btn],
    )
    stop_btn.click(
        fn=_on_stop, inputs=[workflow_id_state],
        outputs=[status_box, stop_btn],
    )

    return {
        "load_fn": _refresh,
        "load_outputs": [prompt_selector],
        "prompt_selector": prompt_selector,
        "prompt_id_state": prompt_id_state,
        "prompt_summary": prompt_summary,
        "start_validation": start_validation,
        "start_btn": start_btn,
    }
