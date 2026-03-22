"""Batch Test page — run batch tests and view progress/results."""
from __future__ import annotations

import threading
import time
from typing import Any

import gradio as gr

from llm.model_registry import get_model_names, DEFAULT_MODEL_NAME
from services.prompt_service import PromptService
from services.test_case_service import TestCaseService
from services.test_run_service import TestRunService
from utils.logger import get_logger

logger = get_logger(__name__)


def build(
    prompt_service: PromptService,
    test_case_service: TestCaseService,
    test_run_service: TestRunService,
) -> dict[str, Any]:
    gr.Markdown(
        "## 批量测试\n"
        "选择 Prompt 和测试用例集，执行批量测试并查看结果统计。"
    )

    with gr.Row():
        with gr.Column(scale=1):
            prompt_selector = gr.Dropdown(
                label="选择 Prompt", choices=[], allow_custom_value=False,
            )
            tc_selector = gr.Dropdown(
                label="选择测试用例集", choices=[], allow_custom_value=False,
            )
            refresh_btn = gr.Button("🔄 刷新列表", size="sm")
            prompt_summary = gr.Textbox(
                label="当前测试 Prompt",
                interactive=False,
                placeholder="选择 Prompt 后将显示当前版本和标识信息。",
            )

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
            run_validation = gr.Textbox(
                label="表单提示",
                interactive=False,
                value="请选择 Prompt 和测试用例集后开始测试。",
            )
            run_btn = gr.Button("▶ 启动批量测试", variant="primary", interactive=False)

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

    def _run_validation_message(prompt_value, tc_value):
        missing = []
        if not prompt_value:
            missing.append("Prompt")
        if not tc_value:
            missing.append("测试用例集")
        if missing:
            return f"请先选择：{'、'.join(missing)}。", gr.update(interactive=False)
        return "参数已就绪，可以开始批量测试。", gr.update(interactive=True)

    def _refresh():
        prompts = prompt_service.list_prompts()
        p_choices = [f"{p.id[:8]}  {p.name}" for p in prompts]
        tcs = test_case_service.list_test_cases()
        tc_choices = [f"{tc.id[:8]}  {tc.name}" for tc in tcs]
        return (
            gr.update(choices=p_choices, value=None),
            gr.update(choices=tc_choices, value=None),
        )

    def _on_select_prompt(val):
        if not val:
            return None, None, ""
        prefix = val.split()[0]
        prompts = prompt_service.list_prompts()
        match = next((p for p in prompts if p.id.startswith(prefix)), None)
        if not match:
            return None, None, ""
        latest = prompt_service.get_latest_version_with_content(match.id)
        summary = (
            f"Prompt: {match.name}\n"
            f"Prompt ID: {match.id}\n"
            f"当前版本: v{latest.version if latest else match.current_version}\n"
            f"更新时间: {match.updated_at[:19].replace('T', ' ')}"
        )
        return match.id, latest.id if latest else None, summary

    def _on_select_tc(val):
        if not val:
            return None
        prefix = val.split()[0]
        tcs = test_case_service.list_test_cases()
        match = next((tc for tc in tcs if tc.id.startswith(prefix)), None)
        return match.id if match else None

    def _build_run_summary(run_id: str | None):
        if not run_id:
            return gr.update()
        tr = test_run_service.get_test_run(run_id)
        if not tr:
            return gr.update()
        return {
            "run_id": tr.id[:8],
            "status": tr.status,
            "total": tr.total,
            "passed": tr.passed,
            "failed": tr.failed,
            "pass_rate": f"{tr.passed / tr.total:.1%}" if tr.total > 0 else "N/A",
        }

    def _on_run(prompt_id, version_id, tc_id, model, judge_model, concurrency):
        if not prompt_id or not version_id:
            return gr.update(), gr.update(), "⚠ 请先选择 Prompt。", None, gr.update()
        if not tc_id:
            return gr.update(), gr.update(), "⚠ 请先选择测试用例集。", None, gr.update()

        version = prompt_service.get_version_with_content(version_id)
        if not version or not version.content:
            return gr.update(), gr.update(), "⚠ Prompt 内容为空。", None, gr.update()

        cases = test_case_service.load_cases(tc_id)
        if not cases:
            return gr.update(), gr.update(), "⚠ 测试用例为空。", None, gr.update()

        task_state = {
            "run_id": None,
            "done": False,
            "error": None,
            "results": [],
        }
        log_lines: list[str] = []

        def on_progress(completed, total, line):
            log_lines.append(line)

        def on_started(run_id: str):
            task_state["run_id"] = run_id

        def worker():
            try:
                tr = test_run_service.run_batch_test(
                    prompt_content=version.content,
                    prompt_version_id=version_id,
                    test_case_id=tc_id,
                    cases=cases,
                    model_name=model,
                    judge_model_name=judge_model,
                    concurrency=int(concurrency),
                    on_started=on_started,
                    on_progress=on_progress,
                )
                task_state["run_id"] = tr.id
                task_state["results"] = test_run_service.get_results(tr.id) or []
            except Exception as exc:
                logger.error("Batch test failed: %s", exc)
                task_state["error"] = str(exc)
            finally:
                task_state["done"] = True

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        while thread.is_alive() or not task_state["done"]:
            run_id = task_state["run_id"]
            summary = _build_run_summary(run_id)
            if task_state["error"]:
                yield "\n".join(log_lines[-30:]), summary, f"❌ 测试失败：{task_state['error']}", run_id, gr.update()
                return

            status_text = "任务启动中…"
            if run_id:
                tr = test_run_service.get_test_run(run_id)
                if tr:
                    status_text = f"状态: {tr.status}"
                    if tr.total > 0:
                        status_text += f"\n进度: {tr.passed + tr.failed}/{tr.total}"

            yield (
                "\n".join(log_lines[-30:]) or "（等待首条日志）",
                summary,
                status_text,
                run_id,
                gr.update(),
            )
            time.sleep(0.3)

        run_id = task_state["run_id"]
        summary = _build_run_summary(run_id)
        final_status = "✅ 测试完成。"
        if run_id:
            tr = test_run_service.get_test_run(run_id)
            if tr:
                final_status = f"✅ 测试完成（{tr.status}）"
        if task_state["error"]:
            final_status = f"❌ 测试失败：{task_state['error']}"

        yield (
            "\n".join(log_lines[-50:]) or "（无日志）",
            summary,
            final_status,
            run_id,
            task_state["results"] or gr.update(),
        )

    def _load_results(run_id):
        if not run_id:
            return "⚠ 暂无测试结果。"
        results = test_run_service.get_results(run_id)
        return results or []

    refresh_btn.click(fn=_refresh, outputs=[prompt_selector, tc_selector])

    prompt_selector.change(
        fn=_on_select_prompt, inputs=[prompt_selector],
        outputs=[prompt_id_state, version_id_state, prompt_summary],
    )
    prompt_selector.change(
        fn=_run_validation_message,
        inputs=[prompt_selector, tc_selector],
        outputs=[run_validation, run_btn],
    )
    tc_selector.change(
        fn=_on_select_tc, inputs=[tc_selector],
        outputs=[tc_id_state],
    )
    tc_selector.change(
        fn=_run_validation_message,
        inputs=[prompt_selector, tc_selector],
        outputs=[run_validation, run_btn],
    )

    run_btn.click(
        fn=_on_run,
        inputs=[prompt_id_state, version_id_state, tc_id_state,
                model_selector, judge_model_selector, concurrency_slider],
        outputs=[progress_box, result_summary, run_status, run_id_state, results_output],
    )

    load_results_btn.click(
        fn=_load_results, inputs=[run_id_state],
        outputs=[results_output],
    )

    return {
        "load_fn": _refresh,
        "load_outputs": [prompt_selector, tc_selector],
        "prompt_selector": prompt_selector,
        "prompt_id_state": prompt_id_state,
        "version_id_state": version_id_state,
        "prompt_summary": prompt_summary,
        "run_validation": run_validation,
        "run_btn": run_btn,
    }
