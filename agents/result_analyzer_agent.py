"""
ResultAnalyzerAgent — analyses batch test results to extract failure
classifications, error patterns, and optimisation recommendations.

The analysis output is a structured JSON object that feeds directly into
PromptOptimizerAgent via the analysis_context parameter.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from agents.base_agent import BaseAgent
from llm.client import LLMClient, LLMResponse
from utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM_INSTRUCTION = """\
You are an expert AI quality analyst.

You receive batch test results for an LLM prompt. Each result contains:
- the test input
- the expected behaviour
- the actual model output
- whether it passed or failed (judged by another LLM)
- the judge's reasoning

Your job is to produce a structured analysis report in JSON with these fields:
{
  "summary": "<2-3 sentence overview of overall quality>",
  "total": <int>,
  "passed": <int>,
  "failed": <int>,
  "pass_rate": <float 0-1>,
  "failure_categories": [
    {"category": "<name>", "count": <int>, "examples": ["<brief description>"]}
  ],
  "error_patterns": ["<pattern description>"],
  "suggestions": ["<specific, actionable improvement suggestion>"]
}

Return ONLY valid JSON — no preamble, no explanation.\
"""

_LANGUAGE_HINTS = {
    "zh": "All natural-language values in the JSON must be written in Simplified Chinese.",
    "en": "All natural-language values in the JSON must be written in English.",
}


class ResultAnalyzerAgent(BaseAgent):

    def __init__(self, llm_client: LLMClient) -> None:
        self._client = llm_client

    @property
    def name(self) -> str:
        return "result_analyzer"

    @property
    def system_instruction(self) -> str:
        return _SYSTEM_INSTRUCTION

    def analyze(
        self,
        prompt_content: str,
        test_results:   List[Dict[str, Any]],
        model_name:     str,
        temperature:    float = 0.3,
        response_language: str = "zh",
    ) -> Dict[str, Any]:
        """
        Analyse *test_results* and return a structured report dict.

        Raises ValueError if the model output cannot be parsed.
        """
        results_text = json.dumps(test_results, ensure_ascii=False, indent=2)
        user_message = (
            f"## Prompt Under Test\n\n{prompt_content}\n\n"
            f"## Test Results\n\n{results_text}"
        )
        logger.info("ResultAnalyzerAgent.analyze  model=%s  results=%d", model_name, len(test_results))

        response: LLMResponse = self._client.generate(
            model_name=model_name,
            prompt=user_message,
            system_instruction=(
                self.system_instruction
                + "\n\n"
                + _LANGUAGE_HINTS.get(response_language, _LANGUAGE_HINTS["zh"])
            ),
            temperature=temperature,
        )

        return self._parse_report(response.text)

    @staticmethod
    def _parse_report(text: str) -> Dict[str, Any]:
        """Extract and parse JSON object from model output."""
        cleaned = text.strip()
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse analysis JSON: {exc}\nRaw output:\n{text}") from exc

        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object for analysis report.")
        return data
