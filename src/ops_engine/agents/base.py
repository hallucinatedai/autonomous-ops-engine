"""Base agent interface for the Autonomous Ops Engine."""

from abc import ABC, abstractmethod
from typing import Any

from ops_engine.models import WorkflowStep


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(self, name: str, config: dict[str, Any] | None = None):
        self.name = name
        self.config = config or {}

    @abstractmethod
    async def validate(self, step: WorkflowStep) -> bool:
        """Validate whether the agent can execute the given step."""

    @abstractmethod
    async def execute(self, step: WorkflowStep) -> dict[str, Any]:
        """Execute the agent's logic for the given step."""

    @abstractmethod
    async def rollback(self, step: WorkflowStep) -> bool:
        """Rollback any changes made during execution."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
