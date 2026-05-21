"""Central workflow orchestration engine."""

from datetime import datetime
from typing import Any
from uuid import UUID

from ops_engine.agents.approval import ApprovalAgent
from ops_engine.agents.audit import AuditAgent
from ops_engine.agents.routing import RoutingAgent
from ops_engine.agents.validation import ValidationAgent
from ops_engine.memory import OperationalMemory
from ops_engine.models import (
    AgentType,
    StepStatus,
    Workflow,
    WorkflowStatus,
    WorkflowStep,
    WorkflowType,
)
from ops_engine.router import WorkflowRouter


class Orchestrator:
    """Central engine that executes workflows step-by-step."""

    def __init__(self, db_path: str = "ops_engine.db"):
        self.memory = OperationalMemory(db_path=db_path)
        self.router = WorkflowRouter()
        self._agents: dict[AgentType, Any] = {
            AgentType.VALIDATION: ValidationAgent(),
            AgentType.ROUTING: RoutingAgent(),
            AgentType.APPROVAL: ApprovalAgent(),
            AgentType.AUDIT: AuditAgent(),
        }

    def create_workflow(
        self,
        name: str,
        intent: str,
        description: str = "",
        created_by: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Workflow:
        """Create a new workflow from user intent."""
        workflow_type = self.router.route(intent)

        steps = self._build_workflow_steps(workflow_type, metadata or {})

        workflow = Workflow(
            name=name,
            workflow_type=workflow_type,
            description=description or intent,
            steps=steps,
            created_by=created_by,
            metadata=metadata or {},
        )

        self.memory.save_workflow(workflow)
        return workflow

    async def execute_workflow(self, workflow_id: UUID) -> Workflow:
        """Execute a workflow step by step."""
        workflow = self.memory.get_workflow(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow {workflow_id} not found")

        workflow.status = WorkflowStatus.RUNNING
        workflow.updated_at = datetime.utcnow()

        audit_agent: AuditAgent = self._agents[AgentType.AUDIT]
        await audit_agent.log_event(
            workflow_id=workflow.id,
            event_type="workflow_started",
            details={"workflow_name": workflow.name, "type": workflow.workflow_type.value},
        )

        for step in workflow.steps:
            if not self._dependencies_met(step, workflow.steps):
                continue

            result = await self._execute_step(workflow, step)

            if step.status == StepStatus.FAILED:
                workflow.status = WorkflowStatus.FAILED
                break

            if result.get("approval_status") == "pending":
                workflow.status = WorkflowStatus.AWAITING_APPROVAL
                break

        if all(s.status == StepStatus.COMPLETED for s in workflow.steps):
            workflow.status = WorkflowStatus.COMPLETED

        workflow.updated_at = datetime.utcnow()
        self.memory.save_workflow(workflow)

        await audit_agent.log_event(
            workflow_id=workflow.id,
            event_type="workflow_completed",
            details={"final_status": workflow.status.value},
        )

        return workflow

    async def _execute_step(
        self, workflow: Workflow, step: WorkflowStep
    ) -> dict[str, Any]:
        """Execute a single workflow step."""
        agent = self._agents.get(step.agent_type)
        if agent is None:
            step.status = StepStatus.FAILED
            step.error_message = f"No agent registered for type: {step.agent_type}"
            return {"error": step.error_message}

        step.status = StepStatus.RUNNING
        step.started_at = datetime.utcnow()

        step.input_data["workflow_id"] = str(workflow.id)

        is_valid = await agent.validate(step)
        if not is_valid:
            step.status = StepStatus.FAILED
            step.error_message = "Step validation failed"
            step.completed_at = datetime.utcnow()
            return {"error": step.error_message}

        try:
            result = await agent.execute(step)
            step.output_data = result
            step.status = StepStatus.COMPLETED
            step.completed_at = datetime.utcnow()
            return result
        except Exception as e:
            step.retries += 1
            if step.retries < step.max_retries:
                step.status = StepStatus.PENDING
                step.error_message = f"Retry {step.retries}/{step.max_retries}: {e}"
            else:
                step.status = StepStatus.FAILED
                step.error_message = f"Max retries exceeded: {e}"
                step.completed_at = datetime.utcnow()
            return {"error": str(e)}

    async def rollback_workflow(self, workflow_id: UUID) -> Workflow:
        """Rollback a workflow by rolling back completed steps in reverse."""
        workflow = self.memory.get_workflow(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow {workflow_id} not found")

        completed_steps = [
            s for s in workflow.steps if s.status == StepStatus.COMPLETED
        ]

        for step in reversed(completed_steps):
            agent = self._agents.get(step.agent_type)
            if agent:
                await agent.rollback(step)
                step.status = StepStatus.ROLLED_BACK

        workflow.status = WorkflowStatus.ROLLED_BACK
        workflow.updated_at = datetime.utcnow()
        self.memory.save_workflow(workflow)
        return workflow

    async def approve_workflow(
        self, workflow_id: UUID, approved: bool, reason: str = ""
    ) -> Workflow:
        """Approve or reject a workflow awaiting approval."""
        workflow = self.memory.get_workflow(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow {workflow_id} not found")

        if workflow.status != WorkflowStatus.AWAITING_APPROVAL:
            raise ValueError(
                f"Workflow is not awaiting approval (status: {workflow.status})"
            )

        if approved:
            workflow.status = WorkflowStatus.APPROVED
            for step in workflow.steps:
                if step.agent_type == AgentType.APPROVAL:
                    step.output_data["decision"] = "approved"
                    step.output_data["reason"] = reason
        else:
            workflow.status = WorkflowStatus.REJECTED
            for step in workflow.steps:
                if step.agent_type == AgentType.APPROVAL:
                    step.output_data["decision"] = "rejected"
                    step.output_data["reason"] = reason

        workflow.updated_at = datetime.utcnow()
        self.memory.save_workflow(workflow)

        audit_agent: AuditAgent = self._agents[AgentType.AUDIT]
        await audit_agent.log_event(
            workflow_id=workflow.id,
            event_type="workflow_approval_decision",
            details={"approved": approved, "reason": reason},
        )

        return workflow

    def get_workflow(self, workflow_id: UUID) -> Workflow | None:
        """Get a workflow by ID."""
        return self.memory.get_workflow(workflow_id)

    def list_workflows(
        self, status: WorkflowStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[Workflow]:
        """List workflows with optional filters."""
        return self.memory.list_workflows(status=status, limit=limit, offset=offset)

    def _build_workflow_steps(
        self, workflow_type: WorkflowType, metadata: dict[str, Any]
    ) -> list[WorkflowStep]:
        """Build the default steps for a workflow type."""
        steps = [
            WorkflowStep(
                name="validate_input",
                agent_type=AgentType.VALIDATION,
                description="Validate workflow input and policy compliance",
                input_data={"workflow_type": workflow_type.value, **metadata},
            ),
            WorkflowStep(
                name="route_workflow",
                agent_type=AgentType.ROUTING,
                description="Determine routing and responsible team",
                input_data={"workflow_type": workflow_type.value, **metadata},
            ),
            WorkflowStep(
                name="request_approval",
                agent_type=AgentType.APPROVAL,
                description="Request human approval if needed",
                input_data={
                    "workflow_type": workflow_type.value,
                    "risk_level": metadata.get("risk_level", "medium"),
                    **metadata,
                },
            ),
            WorkflowStep(
                name="audit_log",
                agent_type=AgentType.AUDIT,
                description="Log workflow execution for audit",
                input_data={"event_type": "workflow_executed", **metadata},
            ),
        ]

        steps[1].depends_on = [steps[0].id]
        steps[2].depends_on = [steps[1].id]
        steps[3].depends_on = [steps[2].id]

        return steps

    def _dependencies_met(
        self, step: WorkflowStep, all_steps: list[WorkflowStep]
    ) -> bool:
        """Check if all dependencies for a step are met."""
        if not step.depends_on:
            return True

        step_map = {s.id: s for s in all_steps}
        return all(
            step_map[dep_id].status == StepStatus.COMPLETED
            for dep_id in step.depends_on
            if dep_id in step_map
        )
