"""
Variable management page — CRUD for reusable variables.
"""
from __future__ import annotations

import gradio as gr

from services.variable_service import VariableService
from utils.logger import get_logger

logger = get_logger(__name__)


def build(variable_service: VariableService) -> None:
    gr.Markdown("## 变量管理\n管理可复用的变量，在 Prompt 和模板中使用 `{{变量名}}` 引用。")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 变量列表")
            var_list_box = gr.Textbox(label="已有变量", lines=12, interactive=False)
            refresh_btn = gr.Button("🔄 刷新列表", size="sm")

        with gr.Column(scale=1):
            gr.Markdown("### 新增 / 编辑变量")
            var_id_input = gr.Textbox(label="变量 ID（编辑时填写，新增留空）", value="")
            var_name_input = gr.Textbox(label="变量名")
            var_value_input = gr.Textbox(label="变量值", lines=3)
            var_scope_input = gr.Dropdown(
                label="作用域", choices=["global", "project"], value="global"
            )
            with gr.Row():
                save_btn = gr.Button("💾 保存", variant="primary")
                delete_btn = gr.Button("🗑️ 删除", variant="stop")
            status_box = gr.Textbox(label="操作结果", interactive=False)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _refresh():
        variables = variable_service.list_all()
        if not variables:
            return "（暂无变量）"
        lines = []
        for v in variables:
            lines.append(
                f"• [{v.scope}] {v.name} = {v.value[:40]}{'…' if len(v.value) > 40 else ''}\n"
                f"  ID: {v.id}  更新: {v.updated_at[:19]}"
            )
        return "\n".join(lines)

    def _save(var_id, name, value, scope):
        if not name.strip():
            return "变量名不能为空。", gr.update()
        try:
            if var_id.strip():
                variable_service.update(var_id.strip(), name.strip(), value, scope)
                return f"✅ 变量 [{name}] 已更新。", _refresh()
            else:
                variable_service.create(name.strip(), value, scope)
                return f"✅ 变量 [{name}] 已创建。", _refresh()
        except Exception as e:
            return f"❌ 操作失败: {e}", gr.update()

    def _delete(var_id):
        if not var_id.strip():
            return "请输入要删除的变量 ID。", gr.update()
        try:
            variable_service.delete(var_id.strip())
            return "✅ 已删除。", _refresh()
        except Exception as e:
            return f"❌ 删除失败: {e}", gr.update()

    refresh_btn.click(fn=_refresh, outputs=[var_list_box])
    save_btn.click(
        fn=_save,
        inputs=[var_id_input, var_name_input, var_value_input, var_scope_input],
        outputs=[status_box, var_list_box],
    )
    delete_btn.click(fn=_delete, inputs=[var_id_input], outputs=[status_box, var_list_box])
