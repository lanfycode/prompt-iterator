"""
Template management page — CRUD for context templates with preview.
"""
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
            tpl_list_box = gr.Textbox(label="已有模板", lines=12, interactive=False)
            refresh_btn = gr.Button("🔄 刷新列表", size="sm")

        with gr.Column(scale=2):
            gr.Markdown("### 新增 / 编辑模板")
            tpl_id_input = gr.Textbox(label="模板 ID（编辑时填写，新增留空）", value="")
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
        if not templates:
            return "（暂无模板）"
        lines = []
        for t in templates:
            desc = f" — {t.description[:30]}" if t.description else ""
            lines.append(
                f"• {t.name}{desc}\n"
                f"  ID: {t.id}  更新: {t.updated_at[:19]}"
            )
        return "\n".join(lines)

    def _save(tpl_id, name, description, content):
        if not name.strip():
            return "模板名称不能为空。", gr.update()
        try:
            if tpl_id.strip():
                template_service.update(tpl_id.strip(), name.strip(), content, description)
                return f"✅ 模板 [{name}] 已更新。", _refresh()
            else:
                template_service.create(name.strip(), content, description)
                return f"✅ 模板 [{name}] 已创建。", _refresh()
        except Exception as e:
            return f"❌ 操作失败: {e}", gr.update()

    def _delete(tpl_id):
        if not tpl_id.strip():
            return "请输入要删除的模板 ID。", gr.update()
        try:
            template_service.delete(tpl_id.strip())
            return "✅ 已删除。", _refresh()
        except Exception as e:
            return f"❌ 删除失败: {e}", gr.update()

    def _preview(content):
        if not content.strip():
            return "请先输入模板内容。"
        variables = variable_service.get_variables_dict(scope="all")
        return template_service.render(content, variables)

    refresh_btn.click(fn=_refresh, outputs=[tpl_list_box])
    save_btn.click(
        fn=_save,
        inputs=[tpl_id_input, tpl_name_input, tpl_desc_input, tpl_content_input],
        outputs=[status_box, tpl_list_box],
    )
    delete_btn.click(fn=_delete, inputs=[tpl_id_input], outputs=[status_box, tpl_list_box])
    preview_btn.click(fn=_preview, inputs=[tpl_content_input], outputs=[preview_box])
