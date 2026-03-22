"""
Task History page — browse past test runs, analyses, and workflow runs.
"""
from __future__ import annotations

import gradio as gr

from services.analysis_service import AnalysisService
from services.test_run_service import TestRunService
from services.workflow_service import WorkflowService
from utils.logger import get_logger

logger = get_logger(__name__)


def build(
    test_run_service: TestRunService,
    analysis_service: AnalysisService,
    workflow_service: WorkflowService,
) -> None:
    gr.Markdown(
        "## 任务历史\n"
        "查看过去的测试任务、分析报告和一键优化记录。"
    )

    with gr.Tabs():
        with gr.Tab("测试任务"):
            run_list_box = gr.Textbox(label="测试任务列表", lines=12, interactive=False)
            refresh_runs_btn = gr.Button("🔄 刷新", size="sm")

            run_detail_id = gr.Textbox(label="任务 ID（输入完整 ID 查看详情）")
            load_detail_btn = gr.Button("查看详情", size="sm")
            run_detail_output = gr.JSON(label="任务详情")
            run_log_box = gr.Textbox(label="任务日志", lines=8, interactive=False)

        with gr.Tab("分析报告"):
            analysis_list_box = gr.Textbox(label="分析报告列表", lines=12, interactive=False)
            refresh_analyses_btn = gr.Button("🔄 刷新", size="sm")

            analysis_detail_id = gr.Textbox(label="分析 ID（输入完整 ID 查看）")
            load_analysis_btn = gr.Button("查看报告", size="sm")
            analysis_report_output = gr.JSON(label="分析报告详情")

        with gr.Tab("工作流记录"):
            wf_list_box = gr.Textbox(label="一键优化记录", lines=12, interactive=False)
            refresh_wf_btn = gr.Button("🔄 刷新", size="sm")

            wf_detail_id = gr.Textbox(label="工作流 ID（输入完整 ID 查看轮次）")
            load_wf_btn = gr.Button("查看轮次详情", size="sm")
            wf_rounds_output = gr.JSON(label="轮次记录")

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _refresh_runs():
        runs = test_run_service.list_test_runs()
        if not runs:
            return "（暂无记录）"
        lines = []
        for r in runs:
            icon = "✅" if r.status == "completed" else ("🔄" if r.status == "running" else "❌")
            rate = f"{r.passed}/{r.total}" if r.total > 0 else "N/A"
            lines.append(
                f"{icon}  {r.id[:8]}  [{r.status}]  {rate}  "
                f"{r.model_name}  {r.created_at[:19]}\n   ID: {r.id}"
            )
        return "\n".join(lines)

    def _load_run_detail(run_id):
        if not run_id.strip():
            return gr.update(), "请输入任务 ID。"
        tr = test_run_service.get_test_run(run_id.strip())
        if not tr:
            return gr.update(), "未找到该任务。"
        detail = {
            "id": tr.id, "status": tr.status,
            "model": tr.model_name,
            "total": tr.total, "passed": tr.passed, "failed": tr.failed,
            "started_at": tr.started_at, "completed_at": tr.completed_at,
        }
        log_content = test_run_service.get_log(run_id.strip()) or "（无日志）"
        return detail, log_content

    def _refresh_analyses():
        analyses = analysis_service.list_analyses()
        if not analyses:
            return "（暂无记录）"
        lines = []
        for a in analyses:
            lines.append(
                f"• {a.id[:8]}  {a.summary[:50]}  {a.created_at[:19]}\n  ID: {a.id}"
            )
        return "\n".join(lines)

    def _load_analysis_detail(analysis_id):
        if not analysis_id.strip():
            return "请输入分析 ID。"
        report = analysis_service.load_report(analysis_id.strip())
        return report or {"error": "未找到分析报告"}

    def _refresh_wf():
        wrs = workflow_service.list_workflow_runs()
        if not wrs:
            return "（暂无记录）"
        lines = []
        for wr in wrs:
            icon = "✅" if wr.status == "completed" else ("🔄" if "ing" in wr.status else "❌")
            lines.append(
                f"{icon}  {wr.id[:8]}  [{wr.status}]  "
                f"轮次 {wr.current_round}/{wr.max_rounds}  "
                f"目标 {wr.target_pass_rate:.0%}\n"
                f"   停止原因: {wr.stop_reason or 'N/A'}  {wr.created_at[:19]}\n"
                f"   ID: {wr.id}"
            )
        return "\n".join(lines)

    def _load_wf_rounds(wf_id):
        if not wf_id.strip():
            return "请输入工作流 ID。"
        rounds = workflow_service.get_rounds(wf_id.strip())
        if not rounds:
            return {"info": "未找到轮次记录"}
        return [
            {
                "round": r.round_number,
                "pass_rate": r.pass_rate,
                "prompt_version_id": r.prompt_version_id[:8] if r.prompt_version_id else None,
                "test_run_id": r.test_run_id[:8] if r.test_run_id else None,
                "analysis_id": r.analysis_id[:8] if r.analysis_id else None,
            }
            for r in rounds
        ]

    refresh_runs_btn.click(fn=_refresh_runs, outputs=[run_list_box])
    load_detail_btn.click(fn=_load_run_detail, inputs=[run_detail_id], outputs=[run_detail_output, run_log_box])
    refresh_analyses_btn.click(fn=_refresh_analyses, outputs=[analysis_list_box])
    load_analysis_btn.click(fn=_load_analysis_detail, inputs=[analysis_detail_id], outputs=[analysis_report_output])
    refresh_wf_btn.click(fn=_refresh_wf, outputs=[wf_list_box])
    load_wf_btn.click(fn=_load_wf_rounds, inputs=[wf_detail_id], outputs=[wf_rounds_output])
