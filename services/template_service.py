"""
TemplateService — manages context templates for assembling final inputs.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from models.prompt import Template
from repositories.phase2_repository import TemplateRepository
from utils.logger import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TemplateService:

    def __init__(self, repository: Optional[TemplateRepository] = None) -> None:
        self._repo = repository or TemplateRepository()

    def create(self, name: str, content: str, description: str = "") -> Template:
        now = _now()
        t = Template(
            id=str(uuid.uuid4()),
            name=name, content=content, description=description,
            created_at=now, updated_at=now,
        )
        self._repo.create(t)
        return t

    def update(self, tpl_id: str, name: str, content: str, description: str = "") -> Template:
        t = self._repo.get(tpl_id)
        if not t:
            raise ValueError(f"Template not found: {tpl_id}")
        t.name = name
        t.content = content
        t.description = description
        t.updated_at = _now()
        self._repo.update(t)
        return t

    def delete(self, tpl_id: str) -> None:
        self._repo.delete(tpl_id)

    def get(self, tpl_id: str) -> Optional[Template]:
        return self._repo.get(tpl_id)

    def list_all(self) -> List[Template]:
        return self._repo.list_all()

    def render(self, template_content: str, variables: Dict[str, str]) -> str:
        """
        Render a template by replacing {{var_name}} placeholders with values.
        Unknown variables are left as-is.
        """
        result = template_content
        for name, value in variables.items():
            result = result.replace("{{" + name + "}}", value)
        return result
