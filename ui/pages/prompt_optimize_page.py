"""
Prompt Optimisation page — Tab 2 of the workbench.

Three-column layout:
  Left  : original prompt (editable / loaded from list)
  Centre: optimisation instructions + config
  Right : optimised result + call info

Cross-page integration:
  The function returns (original_box, prompt_id_state) so that
  the Prompt List page can load content into this tab on demand.
"""
from __future__ import annotations

import difflib
import gradio as gr
from typing import Tuple

from llm.model_registry import get_model_names, DEFAULT_MODEL_NAME
from models.prompt import SourceType
from services.optimization_service import OptimizationService
from services.prompt_service import PromptService
from utils.logger import get_logger

logger = get_logger(__name__)


def build(
    prompt_service: PromptService,
    optimization_service: OptimizationService,
) -> Tuple[gr.Textbox, gr.State]:
    """
    Render the Prompt Optimisation tab UI.

    Returns:
        original_box   – the "Original Prompt" Textbox (loaded from list page).
        prompt_id_state – gr.State holding the currently loaded prompt_id.
    """
    gr.Markdown(
        "## Prompt 优化\n"
        "在已有 Prompt 基础上，根据优化要求生成改进版本并保存为新版本。"
    )

    with gr.Row():
        # ── Left: original prompt ─────────────────────────────────────────────
        with gr.Column(scale=1):
            gr.Markdown("### 原始 Prompt")
            original_box = gr.Textbox(
                label="原始 Prompt（可直接粘贴，或从【Prompt 管理】页加载）",
                lines=14,
                max_lines=30,
                interactive=True,
                placeholder="在此输入或粘贴要优化的 Prompt…",
            )
            optimize_validation = gr.Textbox(
                label="输入提示",
                interactive=False,
                value="请填写原始 Prompt 和优化要求。",
            )
            # Hidden state: the prompt_id for saving as a new version
            prompt_id_state = gr.State(value=None)

        # ── Centre: optimisation config ───────────────────────────────────────
        with gr.Column(scale=1):
            gr.Markdown("### 优化配置")
            optimization_input = gr.Textbox(
                label="优化要求",
                placeholder=(
                    "描述你希望如何改进，例如：\n"
                    "• 增强约束，防止模型生成超出范围的内容\n"
                    "• 补充 2–3 个具体示例\n"
                    "• 统一输出格式为 JSON"
                ),
                lines=5,
            )
            model_selector = gr.Dropdown(
                choices=get_model_names(),
                value=DEFAULT_MODEL_NAME,
                label="选择模型",
                interactive=True,
            )
            temperature_slider = gr.Slider(
                minimum=0.0, maximum=1.0, value=0.7, step=0.05,
                label="Temperature",
            )
            optimize_btn = gr.Button("⚡ 执行优化", variant="primary", interactive=False)

        # ── Right: result ─────────────────────────────────────────────────────
        with gr.Column(scale=1):
            gr.Markdown("### 优化结果")
            optimized_box = gr.Textbox(
                label="优化后的 Prompt（可继续编辑）",
                lines=14,
                max_lines=30,
                interactive=True,
            )
            call_info = gr.JSON(label="调用信息", visible=True)

    diff_html = gr.HTML(label="变更对比")

    gr.Markdown("### 💾 保存优化版本")
    with gr.Row():
        save_name = gr.Textbox(
            label="新 Prompt 名称（留空则追加版本到当前 Prompt）",
            placeholder="留空 → 追加版本；填写名称 → 另存为新 Prompt",
            scale=3,
        )
        save_btn = gr.Button("保存", variant="secondary", scale=1, interactive=False)
    save_status = gr.Textbox(label="操作状态", interactive=False)

    def _validate_optimize(original: str, opt_req: str):
        if not original.strip() and not opt_req.strip():
            return "请填写原始 Prompt 和优化要求。", gr.update(interactive=False)
        if not original.strip():
            return "请先填写原始 Prompt。", gr.update(interactive=False)
        if not opt_req.strip():
            return "请先填写优化要求。", gr.update(interactive=False)
        return "参数已就绪，可以执行优化。", gr.update(interactive=True)

    def _validate_save(optimized: str):
        if not optimized.strip():
            return "请先生成优化结果。", gr.update(interactive=False)
        return "优化结果已生成，可以保存。", gr.update(interactive=True)

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_optimize(
        original: str,
        opt_req:  str,
        model:    str,
        temp:     float,
    ):
        if not original.strip():
            gr.Warning("请填写原始 Prompt。")
            return gr.update(), gr.update(), gr.update()
        if not opt_req.strip():
            gr.Warning("请填写优化要求。")
            return gr.update(), gr.update(), gr.update()
        try:
            text, resp = prompt_service.optimize_prompt(
                original_prompt=original,
                optimization_request=opt_req,
                model_name=model,
                temperature=temp,
            )
            meta = {
                "model":         resp.model_name,
                "temperature":   resp.temperature,
                "prompt_tokens": resp.prompt_tokens,
                "output_tokens": resp.output_tokens,
                "latency_ms":    round(resp.latency_ms, 1),
            }
            diff = difflib.HtmlDiff(wrapcolumn=80).make_table(
                original.splitlines(),
                text.splitlines(),
                fromdesc="原始 Prompt",
                todesc="优化后 Prompt",
                context=True,
                numlines=2,
            )
            return text, meta, diff
        except Exception as exc:
            logger.error("Optimisation failed: %s", exc)
            gr.Error(f"优化失败：{exc}")
            return gr.update(), gr.update(), gr.update()

    def _on_save(
        optimised:   str,
        model:       str,
        prompt_id:   str | None,
        new_name:    str,
    ) -> str:
        if not optimised.strip():
            return "⚠ 优化结果为空，请先执行优化。"
        try:
            if prompt_id and not new_name.strip():
                # Append new version to existing prompt
                prompt, version = prompt_service.save_new_version(
                    prompt_id=prompt_id,
                    content=optimised,
                    source_type=SourceType.OPTIMIZED,
                    model_name=model,
                    summary="手动优化",
                )
                return (
                    f"✅ 已追加 v{version.version} 到 Prompt"
                    f"（ID: {prompt_id[:8]}…）"
                )
            else:
                name = new_name.strip() or "优化后的 Prompt"
                prompt, version = prompt_service.save_new_prompt(
                    name=name,
                    content=optimised,
                    source_type=SourceType.OPTIMIZED,
                    model_name=model,
                    summary="通过优化器生成",
                )
                return (
                    f"✅ 已另存为新 Prompt：{name}"
                    f"（v{version.version}，ID: {prompt.id[:8]}…）"
                )
        except Exception as exc:
            logger.error("Save optimised prompt failed: %s", exc)
            return f"❌ 保存失败：{exc}"

    optimize_btn.click(
        fn=_on_optimize,
        inputs=[original_box, optimization_input, model_selector, temperature_slider],
        outputs=[optimized_box, call_info, diff_html],
    )
    save_btn.click(
        fn=_on_save,
        inputs=[optimized_box, model_selector, prompt_id_state, save_name],
        outputs=[save_status],
    )
    original_box.change(
        fn=_validate_optimize,
        inputs=[original_box, optimization_input],
        outputs=[optimize_validation, optimize_btn],
    )
    optimization_input.change(
        fn=_validate_optimize,
        inputs=[original_box, optimization_input],
        outputs=[optimize_validation, optimize_btn],
    )
    optimized_box.change(
        fn=_validate_save,
        inputs=[optimized_box],
        outputs=[save_status, save_btn],
    )

    return original_box, prompt_id_state
