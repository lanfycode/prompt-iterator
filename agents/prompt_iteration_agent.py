"""
PromptIterationAgent — LLM judge that evaluates whether a model's actual
output matches the expected behaviour for a single test case.

This agent is invoked once per test-case result during batch testing to
produce a pass/fail verdict with reasoning.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict

from agents.base_agent import BaseAgent
from llm.client import LLMClient, LLMResponse
from utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM_INSTRUCTION = """\
You are a strict but fair LLM output evaluator.

You will receive:
1. The prompt that was used.
2. The user input that was sent.
3. The expected behaviour / reference answer.
4. The actual model output.

Your job is to judge whether the actual output satisfies the expected behaviour.

Return ONLY a valid JSON object:
{
  "passed": true/false,
  "score": <float 0.0-1.0>,
  "reasoning": "<brief explanation of your judgement>"
}

Be lenient on surface-level formatting differences but strict on factual
correctness, constraint adherence, and completeness.

Return ONLY valid JSON — no preamble.\
"""


class PromptIterationAgent(BaseAgent):
    """LLM-as-judge for evaluating individual test case results."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._client = llm_client

    @property
    def name(self) -> str:
        return "prompt_iteration_judge"

    @property
    def system_instruction(self) -> str:
        return _SYSTEM_INSTRUCTION

    def judge(
        self,
        prompt_content: str,
        test_input:     str,
        expected:       str,
        actual_output:  str,
        model_name:     str,
        temperature:    float = 0.1,
    ) -> Dict[str, Any]:
        """
        Evaluate a single test result.

        Returns {"passed": bool, "score": float, "reasoning": str}.
        """
        user_message = (
            f"## Prompt\n{prompt_content}\n\n"
            f"## User Input\n{test_input}\n\n"
            f"## Expected Behaviour\n{expected}\n\n"
            f"## Actual Output\n{actual_output}"
        )

        response: LLMResponse = self._client.generate(
            model_name=model_name,
            prompt=user_message,
            system_instruction=self.system_instruction,
            temperature=temperature,
            max_output_tokens=1024,
        )

        return self._parse_verdict(response.text)

    @staticmethod
    def _parse_verdict(text: str) -> Dict[str, Any]:
        cleaned = text.strip()
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback: treat unparseable output as a failure
            return {"passed": False, "score": 0.0, "reasoning": f"Judge output unparseable: {text[:200]}"}
        return {
            "passed": bool(data.get("passed", False)),
            "score": float(data.get("score", 0.0)),
            "reasoning": str(data.get("reasoning", "")),
        }
