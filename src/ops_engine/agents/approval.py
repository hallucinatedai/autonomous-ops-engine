"""Approval agent - human-in-the-loop approval with context and recommendations."""

from datetime import datetime
from typing import Any
from uuid import UUID

from ops_engine.agents.base import BaseAgent
from ops_engine.models import ApprovalRequest, ApprovalStatus, WorkflowStep


class ApprovalAgent(BaseAgent):
    """Agent responsible for managing human-in-the-loop approvals."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(name="approval_agent", config=config)
        self._pending_approvals: dict[UUID, ApprovalRequest] = {}
        self._auto_approve_low_risk: bool = self.config.get("auto_approve_low_risk", False)

    async def validate(self, step: WorkflowStep) -> bool:
        """Validate that the step has necessary approval context."""
        return "workflow_id" in step.input_data

    async def execute(self, step: WorkflowStep) -> dict[str, Any]:
        """Create an approval request and return its details."""
        workflow_id = UUID(str(step.input_data["workflow_id"]))
        risk_level = step.input_data.get("risk_level", "medium")

        if self._auto_approve_low_risk and risk_level == "low":
            return {
                "approval_status": ApprovalStatus.APPROVED,
                "auto_approved": True,
                "reason": "Low-risk workflow auto-approved by policy",
            }

        recommendation = self._generate_recommendation(step.input_data)

        approval_request = ApprovalRequest(
            workflow_id=workflow_id,
            step_id=step.id,
            requested_by=step.input_data.get("requested_by", "system"),
            assigned_to=step.input_data.get("assigned_to", ""),
            context=step.input_data,
            recommendation=recommendation,
        )

        self._pending_approvals[approval_request.id] = approval_request

        return {
            "approval_id": str(approval_request.id),
            "approval_status": ApprovalStatus.PENDING,
            "recommendation": recommendation,
            "assigned_to": approval_request.assigned_to,
        }

    async def rollback(self, step: WorkflowStep) -> bool:
        """Cancel any pending approval requests for this step."""
        to_remove = [
            aid
            for aid, req in self._pending_approvals.items()
            if req.step_id == step.id
        ]
        for aid in to_remove:
            del self._pending_approvals[aid]
        return True

    async def resolve_approval(
        self, approval_id: UUID, approved: bool, reason: str = ""
    ) -> ApprovalRequest | None:
        """Resolve a pending approval request."""
        request = self._pending_approvals.get(approval_id)
        if request is None:
            return None

        request.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        request.decision_reason = reason
        request.resolved_at = datetime.utcnow()

        del self._pending_approvals[approval_id]
        return request

    def get_pending_approvals(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        return list(self._pending_approvals.values())

    def _generate_recommendation(self, context: dict[str, Any]) -> str:
        """Generate an approval recommendation based on context."""
        risk_level = context.get("risk_level", "medium")
        workflow_type = context.get("workflow_type", "unknown")

        if risk_level == "low":
            return f"RECOMMEND APPROVE: Low-risk {workflow_type} workflow."
        elif risk_level == "high":
            return f"RECOMMEND REVIEW: High-risk {workflow_type} workflow requires careful review."
        elif risk_level == "critical":
            return (
                f"RECOMMEND ESCALATE: Critical-risk {workflow_type} workflow "
                "requires senior approval."
            )
        return f"NEUTRAL: Medium-risk {workflow_type} workflow. Review and decide."
