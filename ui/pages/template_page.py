"""Template management page — CRUD for context templates with preview."""
from __future__ import annotations

import gradio as gr

from services.template_service import TemplateService
from services.variable_service import VariableService
from utils.logger import get_logger

logger = get_logger(__name__)


def build(
    template_service: TemplateService,
    variable_service: VariableService,
) -> None:
    gr.Markdown(
        "## 模板管理\n"
        "管理上下文模板，使用 `{{变量名}}` 占位符引用变量。可预览渲染结果。"
    )

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 模板列表")
            tpl_table = gr.Dataframe(
                headers=["模板名", "描述", "模板 ID", "更新时间"],
                datatype=["str", "str", "str", "str"],
                row_count=(0, "dynamic"),
                col_count=(4, "fixed"),
                interactive=False,
                wrap=True,
                label="已有模板",
            )
            tpl_rows_state = gr.State(value=[])
            refresh_btn = gr.Button("🔄 刷新列表", size="sm")

        with gr.Column(scale=2):
            gr.Markdown("### 新增 / 编辑模板")
            tpl_id_state = gr.State(value="")
            selected_tpl_box = gr.Textbox(
                label="当前选中模板",
                interactive=False,
                placeholder="点击左侧模板行后，这里会显示当前选中的模板。",
            )
            tpl_name_input = gr.Textbox(label="模板名称")
            tpl_desc_input = gr.Textbox(label="描述（可选）")
            tpl_content_input = gr.Textbox(
                label="模板内容（支持 {{变量名}} 占位符）", lines=8
            )
            with gr.Row():
                save_btn = gr.Button("💾 保存", variant="primary")
                delete_btn = gr.Button("🗑️ 删除", variant="stop")
                preview_btn = gr.Button("👁️ 预览渲染")
            status_box = gr.Textbox(label="操作结果", interactive=False)

            gr.Markdown("### 渲染预览")
            preview_box = gr.Textbox(label="渲染结果", lines=6, interactive=False)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _refresh():
        templates = template_service.list_all()
        rows = []
        for t in templates:
            rows.append([
                t.name,
                (t.description or "")[:60],
                t.id,
                t.updated_at[:19].replace("T", " "),
            ])
        return rows, templates

    def _resolve_row_index(evt: gr.SelectData):
        index = getattr(evt, "index", None)
        if isinstance(index, tuple):
            return index[0]
        if isinstance(index, list):
            return index[0]
        return index

    def _on_select(tpl_rows, evt: gr.SelectData):
        row_index = _resolve_row_index(evt)
        if row_index is None or row_index >= len(tpl_rows):
            return "", "", "", "", ""
        template = tpl_rows[row_index]
        summary = f"{template.name}\nID: {template.id}"
        return template.id, summary, template.name, template.description, template.content

    def _save(tpl_id, name, description, content):
        if not name.strip():
            return "模板名称不能为空。", gr.update(), gr.update()
        try:
            if tpl_id.strip():
                template_service.update(tpl_id.strip(), name.strip(), content, description)
                rows, templates = _refresh()
                return f"✅ 模板 [{name}] 已更新。", rows, templates
            else:
                template_service.create(name.strip(), content, description)
                rows, templates = _refresh()
                return f"✅ 模板 [{name}] 已创建。", rows, templates
        except Exception as e:
            return f"❌ 操作失败: {e}", gr.update(), gr.update()

    def _delete(tpl_id):
        if not tpl_id.strip():
            return "请先从列表中选择要删除的模板。", gr.update(), gr.update()
        try:
            template_service.delete(tpl_id.strip())
            rows, templates = _refresh()
            return "✅ 已删除。", rows, templates
        except Exception as e:
            return f"❌ 删除失败: {e}", gr.update(), gr.update()

    def _preview(content):
        if not content.strip():
            return "请先输入模板内容。"
        variables = variable_service.get_variables_dict(scope="all")
        return template_service.render(content, variables)

    refresh_btn.click(fn=_refresh, outputs=[tpl_table, tpl_rows_state])
    tpl_table.select(
        fn=_on_select,
        inputs=[tpl_rows_state],
        outputs=[tpl_id_state, selected_tpl_box, tpl_name_input, tpl_desc_input, tpl_content_input],
    )
    save_btn.click(
        fn=_save,
        inputs=[tpl_id_state, tpl_name_input, tpl_desc_input, tpl_content_input],
        outputs=[status_box, tpl_table, tpl_rows_state],
    )
    delete_btn.click(
        fn=_delete,
        inputs=[tpl_id_state],
        outputs=[status_box, tpl_table, tpl_rows_state],
    )
    preview_btn.click(fn=_preview, inputs=[tpl_content_input], outputs=[preview_box])
