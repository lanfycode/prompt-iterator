"""Variable management page — CRUD for reusable variables."""
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
            var_table = gr.Dataframe(
                headers=["变量名", "作用域", "变量值", "变量 ID", "更新时间"],
                datatype=["str", "str", "str", "str", "str"],
                row_count=(0, "dynamic"),
                col_count=(5, "fixed"),
                interactive=False,
                wrap=True,
                label="已有变量",
            )
            var_rows_state = gr.State(value=[])
            refresh_btn = gr.Button("🔄 刷新列表", size="sm")

        with gr.Column(scale=1):
            gr.Markdown("### 新增 / 编辑变量")
            var_id_state = gr.State(value="")
            selected_var_box = gr.Textbox(
                label="当前选中变量",
                interactive=False,
                placeholder="点击左侧变量行后，这里会显示当前选中的变量。",
            )
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
        rows = []
        for v in variables:
            rows.append([
                v.name,
                v.scope,
                v.value[:60] + ("…" if len(v.value) > 60 else ""),
                v.id,
                v.updated_at[:19].replace("T", " "),
            ])
        return rows, variables

    def _resolve_row_index(evt: gr.SelectData):
        index = getattr(evt, "index", None)
        if isinstance(index, tuple):
            return index[0]
        if isinstance(index, list):
            return index[0]
        return index

    def _on_select(var_rows, evt: gr.SelectData):
        row_index = _resolve_row_index(evt)
        if row_index is None or row_index >= len(var_rows):
            return "", "", "", "global", ""
        variable = var_rows[row_index]
        summary = f"{variable.name} [{variable.scope}]\nID: {variable.id}"
        return variable.id, summary, variable.name, variable.value, variable.scope

    def _save(var_id, name, value, scope):
        if not name.strip():
            return "变量名不能为空。", gr.update(), gr.update()
        try:
            if var_id.strip():
                variable_service.update(var_id.strip(), name.strip(), value, scope)
                rows, variables = _refresh()
                return f"✅ 变量 [{name}] 已更新。", rows, variables
            else:
                variable_service.create(name.strip(), value, scope)
                rows, variables = _refresh()
                return f"✅ 变量 [{name}] 已创建。", rows, variables
        except Exception as e:
            return f"❌ 操作失败: {e}", gr.update(), gr.update()

    def _delete(var_id):
        if not var_id.strip():
            return "请先从列表中选择要删除的变量。", gr.update(), gr.update()
        try:
            variable_service.delete(var_id.strip())
            rows, variables = _refresh()
            return "✅ 已删除。", rows, variables
        except Exception as e:
            return f"❌ 删除失败: {e}", gr.update(), gr.update()

    refresh_btn.click(fn=_refresh, outputs=[var_table, var_rows_state])
    var_table.select(
        fn=_on_select,
        inputs=[var_rows_state],
        outputs=[var_id_state, selected_var_box, var_name_input, var_value_input, var_scope_input],
    )
    save_btn.click(
        fn=_save,
        inputs=[var_id_state, var_name_input, var_value_input, var_scope_input],
        outputs=[status_box, var_table, var_rows_state],
    )
    delete_btn.click(
        fn=_delete,
        inputs=[var_id_state],
        outputs=[status_box, var_table, var_rows_state],
    )
