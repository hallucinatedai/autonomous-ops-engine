"""Validation agent - checks workflow completeness, policy rules, and data quality."""

from typing import Any

from ops_engine.agents.base import BaseAgent
from ops_engine.models import WorkflowStep


class ValidationAgent(BaseAgent):
    """Agent responsible for validating workflow steps and data."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(name="validation_agent", config=config)
        self._required_fields: list[str] = self.config.get("required_fields", ["name"])
        self._max_retries: int = self.config.get("max_retries", 3)

    async def validate(self, step: WorkflowStep) -> bool:
        """Validate that the step has sufficient input data."""
        if not step.name:
            return False
        if not step.input_data:
            return False
        return True

    async def execute(self, step: WorkflowStep) -> dict[str, Any]:
        """Execute validation checks on the step's input data."""
        issues: list[str] = []

        for field in self._required_fields:
            if field not in step.input_data:
                issues.append(f"Missing required field: {field}")

        if step.max_retries < 0:
            issues.append("max_retries cannot be negative")

        data_quality_score = self._calculate_data_quality(step.input_data)

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "data_quality_score": data_quality_score,
            "fields_checked": len(self._required_fields),
        }

    async def rollback(self, step: WorkflowStep) -> bool:
        """Validation is read-only, no rollback needed."""
        return True

    def _calculate_data_quality(self, data: dict[str, Any]) -> float:
        """Calculate a data quality score based on field completeness."""
        if not data:
            return 0.0
        non_empty = sum(1 for v in data.values() if v is not None and v != "")
        return round(non_empty / len(data), 2)
