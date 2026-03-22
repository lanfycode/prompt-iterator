"""Prompt management page with table-based prompt and version browsing."""
from __future__ import annotations

from typing import Any, Optional

import gradio as gr

from services.prompt_service import PromptService
from utils.logger import get_logger

logger = get_logger(__name__)


def build(
    prompt_service: PromptService,
    original_box: gr.Textbox,
    prompt_id_state: gr.State,
    single_prompt_selector: gr.Dropdown,
    single_prompt_id_state: gr.State,
    single_version_id_state: gr.State,
    single_prompt_summary: gr.Textbox,
    single_prompt_content_preview: gr.Textbox,
    single_action_validation: gr.Textbox,
    single_preview_btn: gr.Button,
    single_run_btn: gr.Button,
    batch_prompt_selector: gr.Dropdown,
    batch_prompt_id_state: gr.State,
    batch_version_id_state: gr.State,
    batch_prompt_summary: gr.Textbox,
    batch_run_validation: gr.Textbox,
    batch_run_btn: gr.Button,
    workflow_prompt_selector: gr.Dropdown,
    workflow_prompt_id_state: gr.State,
    workflow_prompt_summary: gr.Textbox,
    workflow_start_validation: gr.Textbox,
    workflow_start_btn: gr.Button,
) -> dict[str, Any]:
    """Render the Prompt Management tab UI and wire cross-page load events."""

    gr.Markdown(
        "## Prompt 管理\n"
        "查看已保存的所有 Prompt 及其版本历史，并将任意版本直接加载到后续流程。"
    )

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Prompt 列表")
            refresh_btn = gr.Button("🔄 刷新列表", variant="secondary", size="sm")
            prompt_table = gr.Dataframe(
                headers=["名称", "当前版本", "更新时间", "Prompt ID"],
                datatype=["str", "str", "str", "str"],
                row_count=(0, "dynamic"),
                col_count=(4, "fixed"),
                interactive=False,
                wrap=True,
                label="已保存的 Prompt",
            )
            prompt_rows_state = gr.State(value=[])
            prompt_summary = gr.Textbox(
                label="当前选中 Prompt",
                interactive=False,
                placeholder="点击左侧表格中的 Prompt 行后，这里会显示摘要。",
            )

        with gr.Column(scale=1):
            gr.Markdown("### 版本历史")
            selected_prompt_id = gr.State(value=None)
            selected_version_id = gr.State(value=None)
            version_rows_state = gr.State(value=[])
            version_table = gr.Dataframe(
                headers=["版本", "来源", "模型", "摘要", "创建时间", "版本 ID"],
                datatype=["str", "str", "str", "str", "str", "str"],
                row_count=(0, "dynamic"),
                col_count=(6, "fixed"),
                interactive=False,
                wrap=True,
                label="版本历史",
            )

            gr.Markdown("### 版本内容预览")
            with gr.Row():
                load_to_optimize_btn = gr.Button(
                    "📤 加载到优化页", variant="primary", size="sm"
                )
                load_to_single_btn = gr.Button(
                    "⚡ 加载到单轮测试", variant="secondary", size="sm"
                )
                load_to_batch_btn = gr.Button(
                    "🧪 加载到批量测试", variant="secondary", size="sm"
                )
                load_to_workflow_btn = gr.Button(
                    "🚀 加载到一键优化", variant="secondary", size="sm"
                )
            content_preview = gr.Textbox(
                label="版本内容",
                lines=12,
                max_lines=25,
                interactive=False,
            )
            load_status = gr.Textbox(label="操作状态", interactive=False)

    def _on_refresh():
        prompts = prompt_service.list_prompts()
        rows = [
            [
                prompt.name,
                f"v{prompt.current_version}",
                prompt.updated_at[:19].replace("T", " "),
                prompt.id,
            ]
            for prompt in prompts
        ]
        return rows, prompts, [], [], None, None, "", "已加载 Prompt 列表。"

    def _resolve_row_index(evt: gr.SelectData) -> Optional[int]:
        index = getattr(evt, "index", None)
        if isinstance(index, tuple):
            return index[0]
        if isinstance(index, list):
            return index[0]
        return index

    def _on_select_prompt(prompt_rows, evt: gr.SelectData):
        row_index = _resolve_row_index(evt)
        if row_index is None or row_index >= len(prompt_rows):
            return [], [], None, "", "", ""
        prompt = prompt_rows[row_index]
        versions = prompt_service.list_versions(prompt.id)
        version_rows = [
            [
                f"v{version.version}",
                str(version.source_type),
                version.model_name or "—",
                version.summary[:80],
                version.created_at[:19].replace("T", " "),
                version.id,
            ]
            for version in versions
        ]
        summary = (
            f"名称: {prompt.name}\n"
            f"Prompt ID: {prompt.id}\n"
            f"当前版本: v{prompt.current_version}\n"
            f"更新时间: {prompt.updated_at[:19].replace('T', ' ')}"
        )
        return version_rows, versions, prompt.id, summary, "", "请选择一个版本查看内容。"

    def _on_select_version(version_rows, evt: gr.SelectData):
        row_index = _resolve_row_index(evt)
        if row_index is None or row_index >= len(version_rows):
            return None, "", ""
        version = version_rows[row_index]
        resolved = prompt_service.get_version_with_content(version.id)
        if not resolved:
            return None, "", f"❌ 找不到版本：{version.id}"
        content = resolved.content or "(内容为空)"
        return resolved.id, content, f"已选中版本 v{resolved.version}。"

    def _build_prompt_choice(prompt_id: str) -> str:
        prompt = prompt_service.get_prompt(prompt_id)
        if not prompt:
            raise ValueError(f"Prompt not found: {prompt_id}")
        return f"{prompt.id[:8]}  {prompt.name}"

    def _load_to_optimize(version_id: str | None):
        if not version_id:
            return gr.update(), gr.update(), "⚠ 请先在版本表中选择一个版本。"
        version = prompt_service.get_version_with_content(version_id)
        if not version:
            return gr.update(), gr.update(), f"❌ 找不到版本：{version_id}"
        return version.content or "", version.prompt_id, f"✅ 已加载版本 v{version.version} 到优化页。"

    def _load_to_single(version_id: str | None):
        if not version_id:
            return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), "⚠ 请先在版本表中选择一个版本。"
        version = prompt_service.get_version_with_content(version_id)
        if not version:
            return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), f"❌ 找不到版本：{version_id}"
        prompt_choice = _build_prompt_choice(version.prompt_id)
        summary = (
            f"Prompt: {prompt_choice}\n"
            f"版本: v{version.version}\n"
            f"版本 ID: {version.id}"
        )
        return (
            gr.update(choices=[_build_prompt_choice(p.id) for p in prompt_service.list_prompts()], value=prompt_choice),
            version.prompt_id,
            version.id,
            summary,
            version.content or "",
            "已带入 Prompt，请填写单条测试输入后执行。",
            gr.update(interactive=False),
            gr.update(interactive=False),
            f"✅ 已加载版本 v{version.version} 到单轮测试页。",
        )

    def _load_to_batch(version_id: str | None):
        if not version_id:
            return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), "⚠ 请先在版本表中选择一个版本。"
        version = prompt_service.get_version_with_content(version_id)
        if not version:
            return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), f"❌ 找不到版本：{version_id}"
        prompt_choice = _build_prompt_choice(version.prompt_id)
        summary = (
            f"Prompt: {prompt_choice}\n"
            f"版本: v{version.version}\n"
            f"版本 ID: {version.id}"
        )
        return (
            gr.update(choices=[_build_prompt_choice(p.id) for p in prompt_service.list_prompts()], value=prompt_choice),
            version.prompt_id,
            version.id,
            summary,
            "已带入 Prompt，继续选择测试用例集即可开始批量测试。",
            gr.update(interactive=False),
            f"✅ 已加载版本 v{version.version} 到批量测试页。",
        )

    def _load_to_workflow(version_id: str | None):
        if not version_id:
            return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), "⚠ 请先在版本表中选择一个版本。"
        version = prompt_service.get_version_with_content(version_id)
        if not version:
            return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), f"❌ 找不到版本：{version_id}"
        prompt_choice = _build_prompt_choice(version.prompt_id)
        summary = (
            f"Prompt: {prompt_choice}\n"
            f"当前基线版本: v{version.version}\n"
            f"版本 ID: {version.id}"
        )
        return (
            gr.update(choices=[_build_prompt_choice(p.id) for p in prompt_service.list_prompts()], value=prompt_choice),
            version.prompt_id,
            summary,
            "参数已就绪，可以开始一键优化。",
            gr.update(interactive=True),
            f"✅ 已加载版本 v{version.version} 到一键优化页。",
        )

    refresh_btn.click(
        fn=_on_refresh,
        outputs=[
            prompt_table,
            prompt_rows_state,
            version_table,
            version_rows_state,
            selected_prompt_id,
            selected_version_id,
            content_preview,
            load_status,
        ],
    )

    prompt_table.select(
        fn=_on_select_prompt,
        inputs=[prompt_rows_state],
        outputs=[
            version_table,
            version_rows_state,
            selected_prompt_id,
            prompt_summary,
            content_preview,
            load_status,
        ],
    )

    version_table.select(
        fn=_on_select_version,
        inputs=[version_rows_state],
        outputs=[selected_version_id, content_preview, load_status],
    )

    load_to_optimize_btn.click(
        fn=_load_to_optimize,
        inputs=[selected_version_id],
        outputs=[original_box, prompt_id_state, load_status],
    )

    load_to_single_btn.click(
        fn=_load_to_single,
        inputs=[selected_version_id],
        outputs=[
            single_prompt_selector,
            single_prompt_id_state,
            single_version_id_state,
            single_prompt_summary,
            single_prompt_content_preview,
            single_action_validation,
            single_preview_btn,
            single_run_btn,
            load_status,
        ],
    )

    load_to_batch_btn.click(
        fn=_load_to_batch,
        inputs=[selected_version_id],
        outputs=[
            batch_prompt_selector,
            batch_prompt_id_state,
            batch_version_id_state,
            batch_prompt_summary,
            batch_run_validation,
            batch_run_btn,
            load_status,
        ],
    )

    load_to_workflow_btn.click(
        fn=_load_to_workflow,
        inputs=[selected_version_id],
        outputs=[
            workflow_prompt_selector,
            workflow_prompt_id_state,
            workflow_prompt_summary,
            workflow_start_validation,
            workflow_start_btn,
            load_status,
        ],
    )

    return {
        "load_fn": _on_refresh,
        "load_outputs": [
            prompt_table,
            prompt_rows_state,
            version_table,
            version_rows_state,
            selected_prompt_id,
            selected_version_id,
            content_preview,
            load_status,
        ],
    }
