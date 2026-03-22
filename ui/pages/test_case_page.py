"""Test Case Generation page — generate and view structured test cases."""
from __future__ import annotations

from typing import Any

import gradio as gr

from llm.model_registry import get_model_names, DEFAULT_MODEL_NAME
from services.prompt_service import PromptService
from services.test_case_service import TestCaseService
from utils.logger import get_logger

logger = get_logger(__name__)


def build(
    prompt_service: PromptService,
    test_case_service: TestCaseService,
) -> dict[str, Any]:
    gr.Markdown(
        "## 测试用例生成\n"
        "选择一个 Prompt，自动生成结构化测试用例集（含基线、边界、对抗场景）。"
    )

    with gr.Row():
        with gr.Column(scale=1):
            prompt_selector = gr.Dropdown(
                label="选择 Prompt", choices=[], allow_custom_value=False,
            )
            refresh_btn = gr.Button("🔄 刷新 Prompt 列表", size="sm")
            model_selector = gr.Dropdown(
                choices=get_model_names(), value=DEFAULT_MODEL_NAME,
                label="生成模型", interactive=True,
            )
            num_cases_slider = gr.Slider(
                minimum=3, maximum=30, value=10, step=1,
                label="用例数量",
            )
            generate_validation = gr.Textbox(
                label="表单提示",
                interactive=False,
                value="请选择一个 Prompt 后开始生成。",
            )
            generate_btn = gr.Button("⚡ 生成测试用例", variant="primary", interactive=False)

        with gr.Column(scale=2):
            cases_output = gr.JSON(label="生成的测试用例")
            gen_status = gr.Textbox(label="状态", interactive=False)

    # Hidden state
    prompt_id_state = gr.State(value=None)
    version_id_state = gr.State(value=None)
    tc_id_state = gr.State(value=None)

    gr.Markdown("### 已保存的测试用例集")
    tc_list_box = gr.Textbox(label="用例集列表", lines=6, interactive=False)
    refresh_tc_btn = gr.Button("🔄 刷新用例列表", size="sm")

    def _refresh_prompts():
        prompts = prompt_service.list_prompts()
        choices = [f"{p.id[:8]}  {p.name}" for p in prompts]
        return gr.update(choices=choices, value=None)

    def _on_select_prompt(selector_value: str):
        if not selector_value:
            return None, None
        prefix = selector_value.split()[0]
        prompts = prompt_service.list_prompts()
        match = next((p for p in prompts if p.id.startswith(prefix)), None)
        if not match:
            return None, None
        latest = prompt_service.get_latest_version_with_content(match.id)
        return match.id, latest.id if latest else None

    def _validate_generate(selector_value: str):
        if not selector_value:
            return "请选择一个 Prompt 后开始生成。", gr.update(interactive=False)
        return "参数已就绪，可以生成测试用例。", gr.update(interactive=True)

    def _on_generate(prompt_id, version_id, model, num_cases):
        if not prompt_id or not version_id:
            return gr.update(), "⚠ 请先选择一个 Prompt。", None
        version = prompt_service.get_version_with_content(version_id)
        if not version or not version.content:
            return gr.update(), "⚠ Prompt 内容为空。", None
        try:
            tc, cases = test_case_service.generate(
                prompt_content=version.content,
                prompt_version_id=version_id,
                model_name=model,
                num_cases=int(num_cases),
            )
            return cases, f"✅ 已生成 {len(cases)} 条测试用例（ID: {tc.id[:8]}…）", tc.id
        except Exception as exc:
            logger.error("Test case generation failed: %s", exc)
            return gr.update(), f"❌ 生成失败：{exc}", None

    def _refresh_tc_list():
        tcs = test_case_service.list_test_cases()
        if not tcs:
            return "（暂无测试用例集）"
        lines = []
        for tc in tcs:
            lines.append(f"• {tc.id[:8]}  [{tc.source_type}]  {tc.name}  ({tc.created_at[:19]})")
        return "\n".join(lines)

    refresh_btn.click(fn=_refresh_prompts, outputs=[prompt_selector])

    prompt_selector.change(
        fn=_on_select_prompt, inputs=[prompt_selector],
        outputs=[prompt_id_state, version_id_state],
    )
    prompt_selector.change(
        fn=_validate_generate,
        inputs=[prompt_selector],
        outputs=[generate_validation, generate_btn],
    )

    generate_btn.click(
        fn=_on_generate,
        inputs=[prompt_id_state, version_id_state, model_selector, num_cases_slider],
        outputs=[cases_output, gen_status, tc_id_state],
    )

    refresh_tc_btn.click(fn=_refresh_tc_list, outputs=[tc_list_box])

    def _initial_load():
        return _refresh_prompts(), _refresh_tc_list()

    return {
        "load_fn": _initial_load,
        "load_outputs": [prompt_selector, tc_list_box],
    }
