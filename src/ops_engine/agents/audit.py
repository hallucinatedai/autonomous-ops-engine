"""Audit agent - logs all workflow events, state transitions, and decisions."""

from typing import Any
from uuid import UUID

from ops_engine.agents.base import BaseAgent
from ops_engine.models import AgentType, AuditEvent, WorkflowStep


class AuditAgent(BaseAgent):
    """Agent responsible for audit logging of workflow events."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(name="audit_agent", config=config)
        self._events: list[AuditEvent] = []

    async def validate(self, step: WorkflowStep) -> bool:
        """Audit agent can always execute."""
        return True

    async def execute(self, step: WorkflowStep) -> dict[str, Any]:
        """Log an audit event for the step execution."""
        workflow_id = UUID(str(step.input_data.get("workflow_id", step.id)))
        event_type = step.input_data.get("event_type", "step_executed")

        event = AuditEvent(
            workflow_id=workflow_id,
            step_id=step.id,
            event_type=event_type,
            agent_type=step.agent_type,
            details={
                "step_name": step.name,
                "input_data": step.input_data,
                "status": step.status.value,
            },
        )

        self._events.append(event)

        return {
            "event_id": str(event.id),
            "event_type": event_type,
            "logged": True,
            "total_events": len(self._events),
        }

    async def rollback(self, step: WorkflowStep) -> bool:
        """Log a rollback event (audit logs are append-only)."""
        workflow_id = UUID(str(step.input_data.get("workflow_id", step.id)))

        event = AuditEvent(
            workflow_id=workflow_id,
            step_id=step.id,
            event_type="step_rolled_back",
            agent_type=step.agent_type,
            details={"step_name": step.name, "reason": "rollback_requested"},
        )

        self._events.append(event)
        return True

    def get_events(
        self, workflow_id: UUID | None = None, event_type: str | None = None
    ) -> list[AuditEvent]:
        """Query audit events with optional filters."""
        events = self._events

        if workflow_id is not None:
            events = [e for e in events if e.workflow_id == workflow_id]

        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]

        return events

    def get_event_count(self) -> int:
        """Get total number of audit events."""
        return len(self._events)

    async def log_event(
        self,
        workflow_id: UUID,
        event_type: str,
        step_id: UUID | None = None,
        agent_type: AgentType | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Directly log an audit event."""
        event = AuditEvent(
            workflow_id=workflow_id,
            step_id=step_id,
            event_type=event_type,
            agent_type=agent_type,
            details=details or {},
        )
        self._events.append(event)
        return event
