"""Single test page — run one prompt against one input with render preview."""
from __future__ import annotations

from typing import Any, Optional

import gradio as gr

from llm.model_registry import DEFAULT_MODEL_NAME, get_model_names
from services.prompt_service import PromptService
from services.render_service import RenderService
from services.template_service import TemplateService
from services.test_run_service import TestRunService
from services.variable_service import VariableService
from utils.logger import get_logger

logger = get_logger(__name__)


def build(
    prompt_service: PromptService,
    variable_service: VariableService,
    template_service: TemplateService,
    test_run_service: TestRunService,
) -> dict[str, Any]:
    gr.Markdown(
        "## 单轮测试\n"
        "选择一个 Prompt，对单条输入执行快速验证，并查看最终发送内容与模型输出。"
    )

    with gr.Row():
        with gr.Column(scale=1):
            prompt_selector = gr.Dropdown(
                label="选择 Prompt",
                choices=[],
                allow_custom_value=False,
            )
            prompt_summary = gr.Textbox(
                label="当前测试 Prompt",
                interactive=False,
                placeholder="选择 Prompt 后，这里会显示版本和标识信息。",
            )
            prompt_content_preview = gr.Textbox(
                label="当前 Prompt 内容",
                lines=8,
                max_lines=14,
                interactive=False,
            )
            template_selector = gr.Dropdown(
                label="上下文模板",
                choices=[],
                value="（不使用模板）",
                allow_custom_value=False,
            )
            template_preview = gr.Textbox(
                label="模板内容预览",
                lines=5,
                max_lines=10,
                interactive=False,
            )
            variables_box = gr.Dataframe(
                headers=["变量名", "变量值"],
                datatype=["str", "str"],
                row_count=(1, "dynamic"),
                col_count=(2, "fixed"),
                interactive=True,
                wrap=True,
                label="变量表单",
            )
            user_input_box = gr.Textbox(
                label="单条测试输入",
                lines=6,
                max_lines=12,
                placeholder="输入一条待测试内容，例如用户问题、原始文本或上下文。",
            )
            model_selector = gr.Dropdown(
                choices=get_model_names(),
                value=DEFAULT_MODEL_NAME,
                label="测试模型",
                interactive=True,
            )
            action_validation = gr.Textbox(
                label="表单提示",
                interactive=False,
                value="请选择 Prompt 并填写单条测试输入。",
            )
            with gr.Row():
                preview_btn = gr.Button("👁️ 预览最终输入", interactive=False)
                run_btn = gr.Button("▶ 执行单轮测试", variant="primary", interactive=False)

        with gr.Column(scale=1):
            rendered_prompt_box = gr.Textbox(
                label="渲染后的系统 Prompt",
                lines=8,
                max_lines=14,
                interactive=False,
            )
            final_input_box = gr.Textbox(
                label="最终发送内容预览",
                lines=12,
                max_lines=20,
                interactive=False,
            )
            output_box = gr.Textbox(
                label="模型输出",
                lines=12,
                max_lines=20,
                interactive=False,
            )
            call_info = gr.JSON(label="调用信息")
            run_status = gr.Textbox(label="执行状态", interactive=False)

    prompt_id_state = gr.State(value=None)
    version_id_state = gr.State(value=None)

    def _template_choices() -> list[str]:
        templates = template_service.list_all()
        return ["（不使用模板）"] + [f"{tpl.id[:8]}  {tpl.name}" for tpl in templates]

    def _variables_to_rows(variables: dict[str, Any]) -> list[list[str]]:
        if not variables:
            return [["", ""]]
        rows = [[str(name), "" if value is None else str(value)] for name, value in variables.items()]
        return rows or [["", ""]]

    def _normalize_variable_rows(variable_rows: Any) -> list[list[str]]:
        if variable_rows is None:
            return []
        if hasattr(variable_rows, "values"):
            variable_rows = variable_rows.values.tolist()
        normalized: list[list[str]] = []
        for row in variable_rows:
            if row is None:
                continue
            name = "" if len(row) < 1 or row[0] is None else str(row[0]).strip()
            value = "" if len(row) < 2 or row[1] is None else str(row[1])
            if not name and not value:
                continue
            normalized.append([name, value])
        return normalized

    def _refresh():
        prompts = prompt_service.list_prompts()
        prompt_choices = [f"{p.id[:8]}  {p.name}" for p in prompts]
        variables = variable_service.get_variables_dict(scope="all")
        default_variables = _variables_to_rows(variables)
        return (
            gr.update(choices=prompt_choices, value=None),
            gr.update(choices=_template_choices(), value="（不使用模板）"),
            gr.update(value=default_variables),
        )

    def _resolve_template(selector_value: Optional[str]) -> tuple[Optional[str], str]:
        if not selector_value or selector_value == "（不使用模板）":
            return None, ""
        prefix = selector_value.split()[0]
        templates = template_service.list_all()
        match = next((tpl for tpl in templates if tpl.id.startswith(prefix)), None)
        if not match:
            return None, ""
        return match.id, match.content

    def _parse_variables(variable_rows: Any) -> dict[str, str]:
        variables: dict[str, str] = {}
        for name, value in _normalize_variable_rows(variable_rows):
            if not name:
                raise ValueError("变量名不能为空。")
            if name in variables:
                raise ValueError(f"变量名重复：{name}")
            variables[name] = value
        return variables

    def _render_request(version_id: str, template_value: str, variable_rows: Any, user_input: str):
        version = prompt_service.get_version_with_content(version_id)
        if not version or not version.content:
            raise ValueError("当前 Prompt 内容为空。")

        variables = _parse_variables(variable_rows)
        template_id, template_content = _resolve_template(template_value)
        rendered_prompt = template_service.render(version.content, variables)
        rendered_template = template_service.render(template_content, variables) if template_content else ""
        rendered_user_input = template_service.render(user_input, variables) if user_input else ""
        final_input = RenderService.render(
            prompt_content="",
            user_input=rendered_user_input,
            template_content=rendered_template,
            variables=None,
        )
        final_preview = (
            "[System Prompt]\n"
            f"{rendered_prompt or '（空）'}\n\n"
            "[User Payload]\n"
            f"{final_input or '（空）'}"
        )
        return rendered_prompt, final_preview, final_input, template_id

    def _validate_actions(prompt_value: str, user_input: str, variable_rows: Any):
        if not prompt_value:
            return "请选择 Prompt。", gr.update(interactive=False), gr.update(interactive=False)
        if not user_input.strip():
            return "请填写单条测试输入。", gr.update(interactive=False), gr.update(interactive=False)
        try:
            _parse_variables(variable_rows)
        except Exception as exc:
            return f"变量表单填写有误：{exc}", gr.update(interactive=False), gr.update(interactive=False)
        return "参数已就绪，可以预览或执行单轮测试。", gr.update(interactive=True), gr.update(interactive=True)

    def _on_select_prompt(selector_value: str):
        if not selector_value:
            return None, None, "", ""
        prefix = selector_value.split()[0]
        prompts = prompt_service.list_prompts()
        match = next((p for p in prompts if p.id.startswith(prefix)), None)
        if not match:
            return None, None, "", ""
        latest = prompt_service.get_latest_version_with_content(match.id)
        summary = (
            f"Prompt: {match.name}\n"
            f"Prompt ID: {match.id}\n"
            f"当前版本: v{latest.version if latest else match.current_version}\n"
            f"更新时间: {match.updated_at[:19].replace('T', ' ')}"
        )
        return match.id, latest.id if latest else None, summary, latest.content if latest else ""

    def _on_select_template(template_value: str):
        _, content = _resolve_template(template_value)
        return content or "（未使用模板）"

    def _on_preview(version_id: str, template_value: str, variable_rows: Any, user_input: str):
        if not version_id:
            return gr.update(), gr.update(), "⚠ 请先选择 Prompt。"
        try:
            rendered_prompt, final_preview, _, _ = _render_request(
                version_id,
                template_value,
                variable_rows,
                user_input,
            )
            return rendered_prompt, final_preview, "已生成最终输入预览。"
        except Exception as exc:
            logger.error("Single test preview failed: %s", exc)
            return gr.update(), gr.update(), f"❌ 预览失败：{exc}"

    def _on_run(version_id: str, model_name: str, template_value: str, variable_rows: Any, user_input: str):
        if not version_id:
            return gr.update(), gr.update(), gr.update(), gr.update(), "⚠ 请先选择 Prompt。"
        try:
            rendered_prompt, final_preview, actual_prompt_input, template_id = _render_request(
                version_id,
                template_value,
                variable_rows,
                user_input,
            )
            variables = _parse_variables(variable_rows)
            _, template_content = _resolve_template(template_value)
            tr, result = test_run_service.run_single_test(
                prompt_version_id=version_id,
                model_name=model_name,
                user_input=user_input,
                rendered_prompt=rendered_prompt,
                final_input=actual_prompt_input or "",
                variables=variables,
                template_id=template_id,
                template_name=template_value if template_content else None,
            )
            meta = {
                "run_id": tr.id,
                "status": tr.status,
                "model": tr.model_name,
                "template_id": template_id,
                "prompt_version_id": version_id,
                "prompt_tokens": result.get("prompt_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
                "latency_ms": round(result.get("latency_ms", 0.0), 1),
            }
            status_text = f"✅ 单轮测试完成，已记录到历史（Run ID: {tr.id[:8]}…）。"
            if tr.status != "completed":
                status_text = f"❌ 单轮测试失败，已记录到历史（Run ID: {tr.id[:8]}…）。"
            return rendered_prompt, final_preview, result.get("actual_output", ""), meta, status_text
        except Exception as exc:
            logger.error("Single test execution failed: %s", exc)
            return gr.update(), gr.update(), gr.update(), gr.update(), f"❌ 执行失败：{exc}"

    prompt_selector.change(
        fn=_on_select_prompt,
        inputs=[prompt_selector],
        outputs=[prompt_id_state, version_id_state, prompt_summary, prompt_content_preview],
    )
    prompt_selector.change(
        fn=_validate_actions,
        inputs=[prompt_selector, user_input_box, variables_box],
        outputs=[action_validation, preview_btn, run_btn],
    )
    template_selector.change(
        fn=_on_select_template,
        inputs=[template_selector],
        outputs=[template_preview],
    )
    user_input_box.change(
        fn=_validate_actions,
        inputs=[prompt_selector, user_input_box, variables_box],
        outputs=[action_validation, preview_btn, run_btn],
    )
    variables_box.change(
        fn=_validate_actions,
        inputs=[prompt_selector, user_input_box, variables_box],
        outputs=[action_validation, preview_btn, run_btn],
    )
    preview_btn.click(
        fn=_on_preview,
        inputs=[version_id_state, template_selector, variables_box, user_input_box],
        outputs=[rendered_prompt_box, final_input_box, run_status],
    )
    run_btn.click(
        fn=_on_run,
        inputs=[version_id_state, model_selector, template_selector, variables_box, user_input_box],
        outputs=[rendered_prompt_box, final_input_box, output_box, call_info, run_status],
    )

    return {
        "load_fn": _refresh,
        "load_outputs": [prompt_selector, template_selector, variables_box],
        "prompt_selector": prompt_selector,
        "prompt_id_state": prompt_id_state,
        "version_id_state": version_id_state,
        "prompt_summary": prompt_summary,
        "prompt_content_preview": prompt_content_preview,
        "template_selector": template_selector,
        "template_preview": template_preview,
        "variables_box": variables_box,
        "user_input_box": user_input_box,
        "model_selector": model_selector,
        "action_validation": action_validation,
        "preview_btn": preview_btn,
        "run_btn": run_btn,
        "run_status": run_status,
    }