"""Task History page — browse past test runs, analyses, and workflow runs."""
from __future__ import annotations

from typing import Any

import gradio as gr

from services.analysis_service import AnalysisService
from services.prompt_service import PromptService
from services.test_run_service import TestRunService
from services.workflow_service import WorkflowService
from utils.logger import get_logger

logger = get_logger(__name__)

OPEN_MODAL_JS = "() => { document.body.classList.add('pi-modal-open'); }"
CLOSE_MODAL_JS = "() => { document.body.classList.remove('pi-modal-open'); }"


def build(
    prompt_service: PromptService,
    test_run_service: TestRunService,
    analysis_service: AnalysisService,
    workflow_service: WorkflowService,
    single_prompt_selector: gr.Dropdown,
    single_prompt_id_state: gr.State,
    single_version_id_state: gr.State,
    single_prompt_summary: gr.Textbox,
    single_prompt_content_preview: gr.Textbox,
    single_template_selector: gr.Dropdown,
    single_template_preview: gr.Textbox,
    single_variables_box: gr.Dataframe,
    single_user_input_box: gr.Textbox,
    single_model_selector: gr.Dropdown,
    single_action_validation: gr.Textbox,
    single_preview_btn: gr.Button,
    single_run_btn: gr.Button,
    single_run_status: gr.Textbox,
    analysis_run_selector: gr.Dropdown,
    analysis_run_id_state: gr.State,
    analysis_validation: gr.Textbox,
    analysis_btn: gr.Button,
    analysis_status: gr.Textbox,
    analysis_opt_selector: gr.Dropdown,
    analysis_opt_id_state: gr.State,
    analysis_opt_original_box: gr.Textbox,
    analysis_opt_prompt_id_state: gr.State,
    analysis_opt_validation: gr.Textbox,
    analysis_opt_btn: gr.Button,
    analysis_opt_status: gr.Textbox,
) -> dict[str, Any]:
    gr.Markdown(
        "## 任务历史\n"
        "查看过去的测试任务、分析报告和一键优化记录。"
    )

    with gr.Tabs():
        with gr.Tab("测试任务"):
            run_table = gr.Dataframe(
                headers=["状态", "类型", "任务 ID", "通过情况", "模型", "创建时间"],
                datatype=["str", "str", "str", "str", "str", "str"],
                row_count=(0, "dynamic"),
                col_count=(6, "fixed"),
                interactive=False,
                wrap=True,
                label="测试任务列表",
            )
            run_rows_state = gr.State(value=[])
            selected_run_state = gr.State(value=None)
            refresh_runs_btn = gr.Button("🔄 刷新", size="sm")
            replay_single_btn = gr.Button("🔁 回放到单轮测试", size="sm")
            replay_status = gr.Textbox(label="回放状态", interactive=False)

            history_modal_backdrop = gr.Button(
                "",
                visible=False,
                elem_classes=["pi-modal-backdrop"],
            )

            with gr.Column(visible=False, elem_classes=["pi-modal", "pi-modal-wide"]) as run_detail_modal:
                with gr.Row():
                    gr.Markdown("### 测试任务详情")
                    close_run_detail_btn = gr.Button("关闭", size="sm")
                run_detail_output = gr.JSON(label="任务详情")
                run_result_output = gr.JSON(label="执行结果")
                run_log_box = gr.Textbox(label="任务日志", lines=10, interactive=False)

        with gr.Tab("分析报告"):
            analysis_table = gr.Dataframe(
                headers=["分析 ID", "摘要", "创建时间"],
                datatype=["str", "str", "str"],
                row_count=(0, "dynamic"),
                col_count=(3, "fixed"),
                interactive=False,
                wrap=True,
                label="分析报告列表",
            )
            analysis_rows_state = gr.State(value=[])
            selected_analysis_state = gr.State(value=None)
            refresh_analyses_btn = gr.Button("🔄 刷新", size="sm")
            load_to_analysis_opt_btn = gr.Button("📤 加载到分析优化页", size="sm")
            reload_analysis_btn = gr.Button("🔄 带回结果分析页", size="sm")
            analysis_action_status = gr.Textbox(label="分析操作状态", interactive=False)

            with gr.Column(visible=False, elem_classes=["pi-modal", "pi-modal-wide"]) as analysis_detail_modal:
                with gr.Row():
                    gr.Markdown("### 分析报告详情")
                    close_analysis_detail_btn = gr.Button("关闭", size="sm")
                analysis_report_output = gr.JSON(label="分析报告详情")

        with gr.Tab("工作流记录"):
            wf_table = gr.Dataframe(
                headers=["状态", "工作流 ID", "轮次", "目标", "停止原因", "创建时间"],
                datatype=["str", "str", "str", "str", "str", "str"],
                row_count=(0, "dynamic"),
                col_count=(6, "fixed"),
                interactive=False,
                wrap=True,
                label="一键优化记录",
            )
            wf_rows_state = gr.State(value=[])
            refresh_wf_btn = gr.Button("🔄 刷新", size="sm")
            wf_action_status = gr.Textbox(label="工作流操作状态", interactive=False)

            with gr.Column(visible=False, elem_classes=["pi-modal", "pi-modal-wide"]) as wf_detail_modal:
                with gr.Row():
                    gr.Markdown("### 工作流详情")
                    close_wf_detail_btn = gr.Button("关闭", size="sm")
                wf_rounds_output = gr.JSON(label="轮次记录")

    def _refresh_runs():
        runs = test_run_service.list_test_runs()
        rows = []
        for r in runs:
            icon = "✅" if r.status == "completed" else ("🔄" if r.status == "running" else "❌")
            rate = f"{r.passed}/{r.total}" if r.total > 0 else "N/A"
            run_type = "单轮" if not r.test_case_id else "批量"
            rows.append([
                icon,
                run_type,
                r.id,
                rate,
                r.model_name,
                r.created_at[:19].replace("T", " "),
            ])
        return rows, runs

    def _resolve_row_index(evt: gr.SelectData):
        index = getattr(evt, "index", None)
        if isinstance(index, tuple):
            return index[0]
        if isinstance(index, list):
            return index[0]
        return index

    def _load_run_detail(run_rows, evt: gr.SelectData):
        row_index = _resolve_row_index(evt)
        if row_index is None or row_index >= len(run_rows):
            return gr.update(), gr.update(), "请选择一条测试任务记录。", None, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), "请选择一条测试任务记录。"
        tr = run_rows[row_index]
        if not tr:
            return gr.update(), gr.update(), "未找到该任务。", None, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), "未找到该任务。"
        results = test_run_service.get_results(tr.id) or []
        detail = {
            "id": tr.id, "status": tr.status,
            "type": "single_test" if not tr.test_case_id else "batch_test",
            "model": tr.model_name,
            "prompt_version_id": tr.prompt_version_id,
            "test_case_id": tr.test_case_id,
            "total": tr.total, "passed": tr.passed, "failed": tr.failed,
            "started_at": tr.started_at, "completed_at": tr.completed_at,
        }
        log_content = test_run_service.get_log(tr.id) or "（无日志）"
        result_payload: Any = results[0] if len(results) == 1 else results
        return detail, result_payload, log_content, tr, gr.update(visible=True), gr.update(visible=False), gr.update(visible=True), f"已打开测试任务 {tr.id[:8]}… 的详情窗口。"

    def _build_prompt_choice(prompt_id: str) -> str:
        prompt = prompt_service.get_prompt(prompt_id)
        if not prompt:
            raise ValueError(f"Prompt not found: {prompt_id}")
        return f"{prompt.id[:8]}  {prompt.name}"

    def _analysis_choice(analysis) -> str:
        return f"{analysis.id[:8]}  {analysis.summary[:40]}  ({analysis.created_at[:19]})"

    def _run_choice(run) -> str:
        status_icon = "✅" if run.status == "completed" else "❌"
        rate = f"{run.passed}/{run.total}" if run.total > 0 else "N/A"
        return f"{run.id[:8]}  {status_icon} {rate}  {run.model_name}  ({run.created_at[:19]})"

    def _variables_to_rows(variables: Any) -> list[list[str]]:
        if not isinstance(variables, dict) or not variables:
            return [["", ""]]
        return [[str(name), "" if value is None else str(value)] for name, value in variables.items()]

    def _replay_to_single(tr):
        if not tr:
            return (
                gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update(), gr.update(), "⚠ 请先选择一条单轮测试记录。"
            )
        if tr.test_case_id:
            return (
                gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update(), gr.update(), "⚠ 当前选择的是批量测试记录，不能回放到单轮测试页。"
            )
        version = prompt_service.get_version_with_content(tr.prompt_version_id)
        if not version:
            return (
                gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update(), gr.update(), "❌ 找不到对应的 Prompt 版本。"
            )
        results = test_run_service.get_results(tr.id) or []
        if not results:
            return (
                gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update(), gr.update(), "❌ 当前测试记录没有可回放结果。"
            )
        result = results[0]
        prompt_choice = _build_prompt_choice(version.prompt_id)
        template_value = result.get("template_name") or "（不使用模板）"
        variable_rows = _variables_to_rows(result.get("variables") or {})
        action_text = "已从历史记录恢复，请检查输入后重新执行单轮测试。"
        summary = (
            f"Prompt: {prompt_choice}\n"
            f"版本: v{version.version}\n"
            f"Prompt Version ID: {version.id}"
        )
        return (
            gr.update(choices=[_build_prompt_choice(p.id) for p in prompt_service.list_prompts()], value=prompt_choice),
            version.prompt_id,
            version.id,
            summary,
            version.content or "",
            gr.update(value=template_value),
            result.get("template_content") or "（未使用模板）",
            gr.update(value=variable_rows),
            result.get("user_input") or "",
            gr.update(value=tr.model_name),
            action_text,
            gr.update(interactive=True),
            gr.update(interactive=True),
            f"已从历史记录恢复 Run {tr.id[:8]}…，可以重新预览或执行。",
            f"✅ 已将 Run {tr.id[:8]}… 回放到单轮测试页。",
        )

    def _refresh_analyses():
        analyses = analysis_service.list_analyses()
        rows = []
        for a in analyses:
            rows.append([
                a.id,
                a.summary[:80],
                a.created_at[:19].replace("T", " "),
            ])
        return rows, analyses

    def _load_analysis_detail(analysis_rows, evt: gr.SelectData):
        row_index = _resolve_row_index(evt)
        if row_index is None or row_index >= len(analysis_rows):
            return gr.update(), None, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), "请选择一条分析报告记录。"
        analysis = analysis_rows[row_index]
        report = analysis_service.load_report(analysis.id)
        return report or {"error": "未找到分析报告"}, analysis, gr.update(visible=True), gr.update(visible=False), gr.update(visible=True), f"已打开分析报告 {analysis.id[:8]}… 的详情窗口。"

    def _load_analysis_to_optimize(analysis):
        if not analysis:
            return (
                gr.update(), gr.update(), gr.update(), gr.update(),
                "⚠ 请先选择一条分析报告记录。", gr.update(interactive=False), gr.update(),
                "⚠ 请先选择一条分析报告记录。"
            )
        test_run = test_run_service.get_test_run(analysis.test_run_id)
        if not test_run:
            return (
                gr.update(), gr.update(), gr.update(), gr.update(),
                "❌ 找不到该分析对应的测试任务。", gr.update(interactive=False), gr.update(),
                "❌ 找不到该分析对应的测试任务。"
            )
        version = prompt_service.get_version_with_content(test_run.prompt_version_id)
        prompt_content = version.content if version else ""
        prompt_id = version.prompt_id if version else None
        choices = [_analysis_choice(item) for item in analysis_service.list_analyses()]
        selected_choice = _analysis_choice(analysis)
        validation = "已带入分析记录，可以执行定向优化。" if prompt_id else "⚠ 该分析对应的 Prompt 已缺失。"
        return (
            gr.update(choices=choices, value=selected_choice),
            analysis.id,
            prompt_content,
            prompt_id,
            validation,
            gr.update(interactive=bool(prompt_id)),
            f"已从历史加载分析记录 {analysis.id[:8]}…，可继续执行定向优化。",
            f"✅ 已将分析记录 {analysis.id[:8]}… 加载到分析优化页。"
        )

    def _reload_analysis_source(analysis):
        if not analysis:
            return (
                gr.update(), gr.update(), "⚠ 请先选择一条分析报告记录。",
                gr.update(interactive=False), gr.update(), "⚠ 请先选择一条分析报告记录。"
            )
        test_run = test_run_service.get_test_run(analysis.test_run_id)
        if not test_run:
            return (
                gr.update(), gr.update(), "❌ 找不到该分析对应的测试任务。",
                gr.update(interactive=False), gr.update(), "❌ 找不到该分析对应的测试任务。"
            )
        runs = test_run_service.list_test_runs()
        selected_choice = next((_run_choice(run) for run in runs if run.id == test_run.id), None)
        if not selected_choice:
            selected_choice = _run_choice(test_run)
        return (
            gr.update(choices=[_run_choice(run) for run in runs], value=selected_choice),
            test_run.id,
            "已从历史带回测试任务，可以重新分析。",
            gr.update(interactive=True),
            f"已定位到测试任务 {test_run.id[:8]}…，可以重新分析。",
            f"✅ 已将分析来源任务 {test_run.id[:8]}… 带回结果分析页。"
        )

    def _refresh_wf():
        wrs = workflow_service.list_workflow_runs()
        rows = []
        for wr in wrs:
            icon = "✅" if wr.status == "completed" else ("🔄" if "ing" in wr.status else "❌")
            rows.append([
                icon,
                wr.id,
                f"{wr.current_round}/{wr.max_rounds}",
                f"{wr.target_pass_rate:.0%}",
                wr.stop_reason or "N/A",
                wr.created_at[:19].replace("T", " "),
            ])
        return rows, wrs

    def _load_wf_rounds(wf_rows, evt: gr.SelectData):
        row_index = _resolve_row_index(evt)
        if row_index is None or row_index >= len(wf_rows):
            return {"info": "请选择一条工作流记录"}, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), "请选择一条工作流记录。"
        workflow = wf_rows[row_index]
        rounds = workflow_service.get_rounds(workflow.id)
        if not rounds:
            return {"info": "未找到轮次记录"}, gr.update(visible=True), gr.update(visible=False), gr.update(visible=True), "未找到轮次记录。"
        return [
            {
                "round": r.round_number,
                "pass_rate": r.pass_rate,
                "prompt_version_id": r.prompt_version_id[:8] if r.prompt_version_id else None,
                "test_run_id": r.test_run_id[:8] if r.test_run_id else None,
                "analysis_id": r.analysis_id[:8] if r.analysis_id else None,
            }
            for r in rounds
        ], gr.update(visible=True), gr.update(visible=False), gr.update(visible=True), f"已打开工作流 {workflow.id[:8]}… 的详情窗口。"

    def _close_modals():
        return gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)

    def _initial_load():
        run_rows, run_records = _refresh_runs()
        analysis_rows, analysis_records = _refresh_analyses()
        wf_rows, wf_records = _refresh_wf()
        return run_rows, run_records, analysis_rows, analysis_records, wf_rows, wf_records

    refresh_runs_btn.click(fn=_refresh_runs, outputs=[run_table, run_rows_state])
    run_table.select(
        fn=_load_run_detail,
        inputs=[run_rows_state],
        outputs=[run_detail_output, run_result_output, run_log_box, selected_run_state, run_detail_modal, analysis_detail_modal, history_modal_backdrop, replay_status],
        js=OPEN_MODAL_JS,
    )
    close_run_detail_btn.click(fn=_close_modals, outputs=[run_detail_modal, analysis_detail_modal, wf_detail_modal, history_modal_backdrop], js=CLOSE_MODAL_JS)
    replay_single_btn.click(
        fn=_replay_to_single,
        inputs=[selected_run_state],
        outputs=[
            single_prompt_selector,
            single_prompt_id_state,
            single_version_id_state,
            single_prompt_summary,
            single_prompt_content_preview,
            single_template_selector,
            single_template_preview,
            single_variables_box,
            single_user_input_box,
            single_model_selector,
            single_action_validation,
            single_preview_btn,
            single_run_btn,
            single_run_status,
            replay_status,
        ],
    )
    refresh_analyses_btn.click(fn=_refresh_analyses, outputs=[analysis_table, analysis_rows_state])
    analysis_table.select(
        fn=_load_analysis_detail,
        inputs=[analysis_rows_state],
        outputs=[analysis_report_output, selected_analysis_state, analysis_detail_modal, run_detail_modal, history_modal_backdrop, analysis_action_status],
        js=OPEN_MODAL_JS,
    )
    close_analysis_detail_btn.click(fn=_close_modals, outputs=[run_detail_modal, analysis_detail_modal, wf_detail_modal, history_modal_backdrop], js=CLOSE_MODAL_JS)
    load_to_analysis_opt_btn.click(
        fn=_load_analysis_to_optimize,
        inputs=[selected_analysis_state],
        outputs=[
            analysis_opt_selector,
            analysis_opt_id_state,
            analysis_opt_original_box,
            analysis_opt_prompt_id_state,
            analysis_opt_validation,
            analysis_opt_btn,
            analysis_opt_status,
            analysis_action_status,
        ],
    )
    reload_analysis_btn.click(
        fn=_reload_analysis_source,
        inputs=[selected_analysis_state],
        outputs=[
            analysis_run_selector,
            analysis_run_id_state,
            analysis_validation,
            analysis_btn,
            analysis_status,
            analysis_action_status,
        ],
    )
    refresh_wf_btn.click(fn=_refresh_wf, outputs=[wf_table, wf_rows_state])
    wf_table.select(
        fn=_load_wf_rounds,
        inputs=[wf_rows_state],
        outputs=[wf_rounds_output, wf_detail_modal, run_detail_modal, history_modal_backdrop, wf_action_status],
        js=OPEN_MODAL_JS,
    )
    close_wf_detail_btn.click(fn=_close_modals, outputs=[run_detail_modal, analysis_detail_modal, wf_detail_modal, history_modal_backdrop], js=CLOSE_MODAL_JS)
    history_modal_backdrop.click(fn=_close_modals, outputs=[run_detail_modal, analysis_detail_modal, wf_detail_modal, history_modal_backdrop], js=CLOSE_MODAL_JS)

    return {
        "load_fn": _initial_load,
        "load_outputs": [
            run_table,
            run_rows_state,
            analysis_table,
            analysis_rows_state,
            wf_table,
            wf_rows_state,
        ],
    }
