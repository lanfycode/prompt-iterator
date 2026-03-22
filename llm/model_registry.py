"""
Model registry — single source of truth for all supported LLM models.

Supported providers:
  - "gemini": Google Generative AI (google-genai SDK)
  - "qwen":   Alibaba DashScope via OpenAI-compatible endpoint

Adding a new model means appending one entry to _MODELS.
All UI components and service layers read from here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ModelConfig:
    name:                str
    display_name:        str
    provider:            str   = "gemini"  # "gemini" | "qwen"
    max_output_tokens:   int   = 8192
    default_temperature: float = 0.7
    supports_thinking:   bool  = False


# ── Supported model catalogue ─────────────────────────────────────────────────
_MODELS: List[ModelConfig] = [
    # ── Google Gemini ──────────────────────────────────────────────────────────
    ModelConfig(
        name="gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
        supports_thinking=True,
    ),
    ModelConfig(
        name="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        supports_thinking=True,
    ),
    ModelConfig(
        name="gemini-2.5-flash-lite",
        display_name="Gemini 2.5 Flash Lite",
        max_output_tokens=4096,
    ),
    ModelConfig(
        name="gemini-3-flash-preview",
        display_name="Gemini 3 Flash (Preview)",
    ),
    ModelConfig(
        name="gemini-3.1-pro-preview",
        display_name="Gemini 3.1 Pro (Preview)",
    ),
    # ── Alibaba Qwen (DashScope) ───────────────────────────────────────────────
    ModelConfig(
        name="qwen3.5-plus",
        display_name="Qwen3.5-Plus",
        provider="qwen",
    ),
    ModelConfig(
        name="qwen3.5-flash",
        display_name="Qwen3.5-Flash",
        provider="qwen",
    ),
    ModelConfig(
        name="qwen3-max",
        display_name="Qwen3-Max",
        provider="qwen",
    ),
]

_MODEL_MAP: Dict[str, ModelConfig] = {m.name: m for m in _MODELS}
DEFAULT_MODEL_NAME = "gemini-2.5-flash"


def list_models() -> List[ModelConfig]:
    return list(_MODELS)


def get_model_names() -> List[str]:
    return [m.name for m in _MODELS]


def get_model_config(name: str) -> Optional[ModelConfig]:
    return _MODEL_MAP.get(name)


def get_default_model() -> ModelConfig:
    return _MODEL_MAP[DEFAULT_MODEL_NAME]
