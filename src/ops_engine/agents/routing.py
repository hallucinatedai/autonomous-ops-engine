"""Routing agent - determines responsible teams, workflow paths, and escalation chains."""

from typing import Any

from ops_engine.agents.base import BaseAgent
from ops_engine.models import WorkflowStep, WorkflowType


class RoutingAgent(BaseAgent):
    """Agent responsible for routing workflows to appropriate teams and paths."""

    DEFAULT_ROUTING_RULES: dict[str, dict[str, Any]] = {
        WorkflowType.DEPLOYMENT: {
            "team": "platform-engineering",
            "escalation_chain": ["tech-lead", "engineering-manager", "vp-engineering"],
            "sla_hours": 4,
        },
        WorkflowType.INCIDENT_RESPONSE: {
            "team": "sre",
            "escalation_chain": ["on-call", "incident-commander", "vp-engineering"],
            "sla_hours": 1,
        },
        WorkflowType.CHANGE_REQUEST: {
            "team": "change-advisory-board",
            "escalation_chain": ["change-manager", "director-ops"],
            "sla_hours": 24,
        },
        WorkflowType.MAINTENANCE: {
            "team": "infrastructure",
            "escalation_chain": ["infra-lead", "director-infra"],
            "sla_hours": 8,
        },
        WorkflowType.ONBOARDING: {
            "team": "it-operations",
            "escalation_chain": ["it-manager", "director-it"],
            "sla_hours": 48,
        },
        WorkflowType.CUSTOM: {
            "team": "operations",
            "escalation_chain": ["ops-manager"],
            "sla_hours": 24,
        },
    }

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(name="routing_agent", config=config)
        self._routing_rules = self.config.get("routing_rules", self.DEFAULT_ROUTING_RULES)

    async def validate(self, step: WorkflowStep) -> bool:
        """Validate that the step has a workflow_type for routing."""
        return "workflow_type" in step.input_data

    async def execute(self, step: WorkflowStep) -> dict[str, Any]:
        """Determine routing for the workflow step."""
        workflow_type = step.input_data.get("workflow_type", WorkflowType.CUSTOM)
        priority = step.input_data.get("priority", "medium")

        routing_info = self._routing_rules.get(
            workflow_type, self._routing_rules[WorkflowType.CUSTOM]
        )

        assigned_team = routing_info["team"]
        escalation_chain = routing_info["escalation_chain"]
        sla_hours = routing_info["sla_hours"]

        if priority == "critical":
            sla_hours = max(1, sla_hours // 4)
        elif priority == "high":
            sla_hours = max(1, sla_hours // 2)

        return {
            "assigned_team": assigned_team,
            "escalation_chain": escalation_chain,
            "sla_hours": sla_hours,
            "priority": priority,
            "workflow_type": workflow_type,
        }

    async def rollback(self, step: WorkflowStep) -> bool:
        """Routing is informational, no rollback needed."""
        return True
