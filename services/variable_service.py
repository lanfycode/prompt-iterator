"""
VariableService — manages reusable variables for prompt/template rendering.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from models.prompt import Variable
from repositories.phase2_repository import VariableRepository
from utils.logger import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VariableService:

    def __init__(self, repository: Optional[VariableRepository] = None) -> None:
        self._repo = repository or VariableRepository()

    def create(self, name: str, value: str, scope: str = "global") -> Variable:
        now = _now()
        v = Variable(
            id=str(uuid.uuid4()),
            name=name, value=value, scope=scope,
            created_at=now, updated_at=now,
        )
        self._repo.create(v)
        return v

    def update(self, var_id: str, name: str, value: str, scope: str = "global") -> Variable:
        v = self._repo.get(var_id)
        if not v:
            raise ValueError(f"Variable not found: {var_id}")
        v.name = name
        v.value = value
        v.scope = scope
        v.updated_at = _now()
        self._repo.update(v)
        return v

    def delete(self, var_id: str) -> None:
        self._repo.delete(var_id)

    def get(self, var_id: str) -> Optional[Variable]:
        return self._repo.get(var_id)

    def list_all(self) -> List[Variable]:
        return self._repo.list_all()

    def get_variables_dict(self, scope: str = "global") -> Dict[str, str]:
        """Return all variables as a name→value dict, optionally filtered by scope."""
        return {
            v.name: v.value
            for v in self._repo.list_all()
            if scope == "all" or v.scope == scope
        }
