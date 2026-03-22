"""
Unified LLM call client — the single entry-point for all model interactions.

Supported providers:
  - Gemini  : Google Generative AI (google-genai SDK)
  - Qwen    : Alibaba DashScope via OpenAI-compatible endpoint
               (base_url = https://dashscope.aliyuncs.com/compatible-mode/v1)

All agents delegate to LLMClient.generate(); routing to the correct backend
is determined automatically via the model registry's ``provider`` field.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from config import DASHSCOPE_API_KEY, GEMINI_API_KEY
from utils.logger import get_logger

logger = get_logger(__name__)

_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


@dataclass
class LLMResponse:
    """Structured result returned by every model call."""
    text:          str
    model_name:    str
    temperature:   float
    prompt_tokens: int
    output_tokens: int
    latency_ms:    float


class LLMClient:
    """
    Singleton wrapper that routes requests to the correct LLM backend.

    All agents delegate to this class so that:
    - API key management is centralised.
    - Call metadata (latency, token counts) is captured uniformly.
    - Adding a new provider requires only local changes here.
    """

    _instance: Optional["LLMClient"] = None

    def __init__(self) -> None:
        self._gemini_client = None
        self._qwen_client   = None

        if GEMINI_API_KEY:
            from google import genai as _genai  # lazy import
            self._gemini_client = _genai.Client(api_key=GEMINI_API_KEY)
            logger.info("Gemini backend initialised.")
        else:
            logger.warning("GEMINI_API_KEY not set — Gemini models unavailable.")

        if DASHSCOPE_API_KEY:
            from openai import OpenAI  # lazy import
            self._qwen_client = OpenAI(
                api_key=DASHSCOPE_API_KEY,
                base_url=_QWEN_BASE_URL,
            )
            logger.info("Qwen (DashScope) backend initialised.")
        else:
            logger.warning("DASHSCOPE_API_KEY not set — Qwen models unavailable.")

        if not self._gemini_client and not self._qwen_client:
            raise EnvironmentError(
                "No API keys configured. "
                "Set GEMINI_API_KEY or DASHSCOPE_API_KEY in your .env file."
            )

    @classmethod
    def get_instance(cls) -> "LLMClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Public interface ───────────────────────────────────────────────────────

    def generate(
        self,
        model_name:         str,
        prompt:             str,
        system_instruction: Optional[str] = None,
        temperature:        float = 0.7,
        max_output_tokens:  int   = 8192,
    ) -> LLMResponse:
        """
        Send a single generation request and return a structured response.

        The backend (Gemini or Qwen) is selected via the model registry.
        Raises RuntimeError on API failure.
        """
        from llm.model_registry import get_model_config  # avoid circular at module level
        cfg = get_model_config(model_name)
        provider = cfg.provider if cfg else "gemini"

        logger.info("→ provider=%s  model=%s  temperature=%.2f", provider, model_name, temperature)

        if provider == "qwen":
            return self._generate_qwen(model_name, prompt, system_instruction, temperature, max_output_tokens)
        return self._generate_gemini(model_name, prompt, system_instruction, temperature, max_output_tokens)

    # ── Private backends ───────────────────────────────────────────────────────

    def _generate_gemini(
        self,
        model_name:         str,
        prompt:             str,
        system_instruction: Optional[str],
        temperature:        float,
        max_output_tokens:  int,
    ) -> LLMResponse:
        if self._gemini_client is None:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set. Cannot use Gemini models."
            )
        from google.genai import types

        config_kwargs: dict = {
            "temperature":       temperature,
            "max_output_tokens": max_output_tokens,
        }
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        config = types.GenerateContentConfig(**config_kwargs)
        t0 = time.monotonic()

        try:
            raw = self._gemini_client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            logger.error("Gemini call failed [%s]: %s", model_name, exc)
            raise RuntimeError(f"LLM call failed ({model_name}): {exc}") from exc

        latency_ms = (time.monotonic() - t0) * 1000
        usage = raw.usage_metadata

        prompt_tokens = (
            getattr(usage, "prompt_token_count",  None)
            or getattr(usage, "input_token_count",  0)
        ) if usage else 0
        output_tokens = (
            getattr(usage, "candidates_token_count", None)
            or getattr(usage, "output_token_count",  0)
        ) if usage else 0

        result = LLMResponse(
            text=raw.text or "",
            model_name=model_name,
            temperature=temperature,
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )
        logger.info(
            "← tokens_in=%d  tokens_out=%d  latency=%.0fms",
            result.prompt_tokens, result.output_tokens, result.latency_ms,
        )
        return result

    def _generate_qwen(
        self,
        model_name:         str,
        prompt:             str,
        system_instruction: Optional[str],
        temperature:        float,
        max_output_tokens:  int,
    ) -> LLMResponse:
        if self._qwen_client is None:
            raise EnvironmentError(
                "DASHSCOPE_API_KEY is not set. Cannot use Qwen models."
            )
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        t0 = time.monotonic()
        try:
            completion = self._qwen_client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_output_tokens,
            )
        except Exception as exc:
            logger.error("Qwen call failed [%s]: %s", model_name, exc)
            raise RuntimeError(f"LLM call failed ({model_name}): {exc}") from exc

        latency_ms    = (time.monotonic() - t0) * 1000
        usage         = completion.usage
        prompt_tokens = getattr(usage, "prompt_tokens",     0) if usage else 0
        output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        text          = completion.choices[0].message.content or "" if completion.choices else ""

        result = LLMResponse(
            text=text,
            model_name=model_name,
            temperature=temperature,
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )
        logger.info(
            "← tokens_in=%d  tokens_out=%d  latency=%.0fms",
            result.prompt_tokens, result.output_tokens, result.latency_ms,
        )
        return result
