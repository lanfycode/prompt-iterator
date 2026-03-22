"""
RenderService — assembles final inputs from prompt, template, user input,
and variables.

Final input = system prompt + prompt template + context template + user input
              + variable replacement
"""
from __future__ import annotations

from typing import Dict, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class RenderService:
    """Renders the final input sent to the model during testing."""

    @staticmethod
    def render(
        prompt_content:   str,
        user_input:       str = "",
        template_content: Optional[str] = None,
        variables:        Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Assemble the final input.

        Variable placeholders use ``{{var_name}}`` syntax.
        """
        parts = []

        if prompt_content:
            parts.append(prompt_content)

        if template_content:
            parts.append(template_content)

        if user_input:
            parts.append(user_input)

        merged = "\n\n".join(parts)

        # Variable replacement
        if variables:
            for name, value in variables.items():
                merged = merged.replace("{{" + name + "}}", value)

        return merged
