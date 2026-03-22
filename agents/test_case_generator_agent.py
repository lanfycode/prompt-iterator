"""
TestCaseGeneratorAgent — generates structured test cases from a Prompt.

Given a prompt, this agent produces a JSON array of test cases covering
baseline, boundary, and adversarial scenarios.  Each test case contains
an `input`, `expected` (reference answer for LLM judge), and a
`description`.
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
You are an expert QA engineer for LLM-based systems.

Your task is to generate a comprehensive set of test cases for a given prompt.
Each test case must exercise a specific aspect of the prompt's expected behaviour.

You MUST cover:
1. **Baseline cases** — standard, happy-path inputs.
2. **Boundary cases** — edge conditions, minimal/maximal inputs.
3. **Adversarial cases** — attempts to bypass constraints, inject instructions, or produce unexpected output.

Return ONLY a valid JSON array. Each element must have exactly these fields:
- "input": (string) the user input to send alongside the prompt.
- "expected": (string) a concise reference answer or description of the correct behaviour that a reviewer can use to judge correctness.
- "description": (string) a short label explaining what this test case checks.

Do NOT include any text outside the JSON array — no preamble, no explanation.
Generate between 5 and 20 test cases depending on the prompt's complexity.\
"""


class TestCaseGeneratorAgent(BaseAgent):

    def __init__(self, llm_client: LLMClient) -> None:
        self._client = llm_client

    @property
    def name(self) -> str:
        return "test_case_generator"

    @property
    def system_instruction(self) -> str:
        return _SYSTEM_INSTRUCTION

    def generate(
        self,
        prompt_content: str,
        model_name:     str,
        num_cases:      int = 10,
        temperature:    float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Generate test cases for the given *prompt_content*.

        Returns a parsed list of test-case dicts.
        Raises ValueError if the model output cannot be parsed.
        """
        if not prompt_content.strip():
            raise ValueError("Prompt content cannot be empty.")

        user_message = (
            f"Generate approximately {num_cases} test cases for the following prompt:\n\n"
            f"---\n{prompt_content}\n---"
        )
        logger.info("TestCaseGeneratorAgent.generate  model=%s  num_cases=%d", model_name, num_cases)

        response: LLMResponse = self._client.generate(
            model_name=model_name,
            prompt=user_message,
            system_instruction=self.system_instruction,
            temperature=temperature,
        )

        return self._parse_cases(response.text)

    @staticmethod
    def _parse_cases(text: str) -> List[Dict[str, Any]]:
        """Extract and parse JSON array from model output."""
        cleaned = text.strip()
        # Strip markdown code fences if present
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse test cases JSON: {exc}\nRaw output:\n{text}") from exc

        if not isinstance(data, list):
            raise ValueError("Expected a JSON array of test cases.")
        return data
