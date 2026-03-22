"""
Prompt Generation page — Tab 1 of the Prompt Iterator workbench.

Flow: requirement input → model selection → generate → (optionally) save.
"""
from __future__ import annotations

import gradio as gr

from llm.model_registry import get_model_names, DEFAULT_MODEL_NAME
from models.prompt import SourceType
from services.prompt_service import PromptService
from utils.logger import get_logger

logger = get_logger(__name__)


def build(prompt_service: PromptService) -> None:
    """
    Render all UI components for the Prompt Generation tab.

    This function is called inside an active gr.Blocks context.
    No return value — cross-page component wiring is handled in ui/main.py.
    """
    gr.Markdown(
        "## Prompt 生成\n"
        "输入你的需求描述，系统将调用 LLM 生成结构化 Prompt。"
    )

    with gr.Row():
        # ── Left: inputs ──────────────────────────────────────────────────────
        with gr.Column(scale=1):
            requirement_box = gr.Textbox(
                label="需求描述",
                placeholder=(
                    "请描述你的需求，例如：\n"
                    "一个帮助用户撰写专业英文邮件的 AI 助手，"
                    "需要保持正式语气并自动推断收件人称谓。"
                ),
                lines=8,
                max_lines=20,
            )
            requirement_validation = gr.Textbox(
                label="输入提示",
                interactive=False,
                value="请先输入需求描述。",
            )
            model_selector = gr.Dropdown(
                choices=get_model_names(),
                value=DEFAULT_MODEL_NAME,
                label="选择模型",
                interactive=True,
            )
            temperature_slider = gr.Slider(
                minimum=0.0, maximum=1.0, value=0.7, step=0.05,
                label="Temperature（越高越有创意，越低越确定）",
            )
            generate_btn = gr.Button("⚡ 生成 Prompt", variant="primary", interactive=False)

        # ── Right: outputs ────────────────────────────────────────────────────
        with gr.Column(scale=1):
            result_box = gr.Textbox(
                label="生成结果（可在此编辑后保存）",
                lines=15,
                max_lines=30,
                interactive=True,
            )
            call_info = gr.JSON(label="调用信息", visible=True)

    gr.Markdown("### 💾 保存 Prompt")
    with gr.Row():
        save_name = gr.Textbox(
            label="Prompt 名称",
            placeholder="为这个 Prompt 起一个名称...",
            scale=3,
        )
        save_btn = gr.Button("保存", variant="secondary", scale=1, interactive=False)
    save_status = gr.Textbox(label="操作状态", interactive=False)

    def _validate_generate(requirement: str):
        if not requirement.strip():
            return "请填写需求描述后再生成。", gr.update(interactive=False)
        return "需求描述已就绪，可以生成。", gr.update(interactive=True)

    def _validate_save(content: str, name: str):
        if not content.strip():
            return "请先生成 Prompt 内容。", gr.update(interactive=False)
        if not name.strip():
            return "请填写 Prompt 名称后再保存。", gr.update(interactive=False)
        return "内容与名称已就绪，可以保存。", gr.update(interactive=True)

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_generate(requirement: str, model: str, temperature: float):
        if not requirement.strip():
            gr.Warning("请填写需求描述。")
            return gr.update(), gr.update()
        try:
            text, resp = prompt_service.generate_prompt(
                requirement=requirement,
                model_name=model,
                temperature=temperature,
            )
            meta = {
                "model":         resp.model_name,
                "temperature":   resp.temperature,
                "prompt_tokens": resp.prompt_tokens,
                "output_tokens": resp.output_tokens,
                "latency_ms":    round(resp.latency_ms, 1),
            }
            return text, meta
        except Exception as exc:
            logger.error("Generation failed: %s", exc)
            gr.Error(f"生成失败：{exc}")
            return gr.update(), gr.update()

    def _on_save(content: str, name: str, model: str) -> str:
        if not content.strip():
            return "⚠ 请先生成 Prompt 内容再保存。"
        if not name.strip():
            return "⚠ 请填写 Prompt 名称。"
        try:
            prompt, version = prompt_service.save_new_prompt(
                name=name.strip(),
                content=content,
                source_type=SourceType.GENERATED,
                model_name=model,
                summary="通过生成器生成",
            )
            return (
                f"✅ 已保存：{prompt.name}"
                f"（版本 v{version.version}，ID: {prompt.id[:8]}…）"
            )
        except Exception as exc:
            logger.error("Save failed: %s", exc)
            return f"❌ 保存失败：{exc}"

    generate_btn.click(
        fn=_on_generate,
        inputs=[requirement_box, model_selector, temperature_slider],
        outputs=[result_box, call_info],
    )
    save_btn.click(
        fn=_on_save,
        inputs=[result_box, save_name, model_selector],
        outputs=[save_status],
    )
    requirement_box.change(
        fn=_validate_generate,
        inputs=[requirement_box],
        outputs=[requirement_validation, generate_btn],
    )
    result_box.change(
        fn=_validate_save,
        inputs=[result_box, save_name],
        outputs=[save_status, save_btn],
    )
    save_name.change(
        fn=_validate_save,
        inputs=[result_box, save_name],
        outputs=[save_status, save_btn],
    )
