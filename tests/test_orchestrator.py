"""Tests for the workflow orchestrator."""

from pathlib import Path
from uuid import uuid4

import pytest

from ops_engine.models import WorkflowStatus, WorkflowType
from ops_engine.orchestrator import Orchestrator


@pytest.fixture
def orchestrator(tmp_path: Path) -> Orchestrator:
    """Create an orchestrator with a temporary database."""
    db_path = str(tmp_path / "test.db")
    return Orchestrator(db_path=db_path)


class TestOrchestratorWorkflowCreation:
    def test_create_deployment_workflow(self, orchestrator: Orchestrator):
        workflow = orchestrator.create_workflow(
            name="Deploy v2.0",
            intent="deploy the new release to production",
            created_by="test-user",
        )
        assert workflow.name == "Deploy v2.0"
        assert workflow.workflow_type == WorkflowType.DEPLOYMENT
        assert workflow.status == WorkflowStatus.PENDING
        assert workflow.created_by == "test-user"
        assert len(workflow.steps) == 4

    def test_create_incident_workflow(self, orchestrator: Orchestrator):
        workflow = orchestrator.create_workflow(
            name="API Outage",
            intent="there is a critical outage affecting the API",
        )
        assert workflow.workflow_type == WorkflowType.INCIDENT_RESPONSE

    def test_create_custom_workflow(self, orchestrator: Orchestrator):
        workflow = orchestrator.create_workflow(
            name="Custom Task",
            intent="do something completely unrelated to known types",
        )
        assert workflow.workflow_type == WorkflowType.CUSTOM

    def test_workflow_has_ordered_steps(self, orchestrator: Orchestrator):
        workflow = orchestrator.create_workflow(name="Test", intent="deploy something")
        assert workflow.steps[0].name == "validate_input"
        assert workflow.steps[1].name == "route_workflow"
        assert workflow.steps[2].name == "request_approval"
        assert workflow.steps[3].name == "audit_log"

    def test_workflow_step_dependencies(self, orchestrator: Orchestrator):
        workflow = orchestrator.create_workflow(name="Test", intent="deploy something")
        assert workflow.steps[0].depends_on == []
        assert workflow.steps[1].depends_on == [workflow.steps[0].id]
        assert workflow.steps[2].depends_on == [workflow.steps[1].id]
        assert workflow.steps[3].depends_on == [workflow.steps[2].id]


class TestOrchestratorExecution:
    @pytest.mark.asyncio
    async def test_execute_workflow(self, orchestrator: Orchestrator):
        workflow = orchestrator.create_workflow(
            name="Deploy v2.0",
            intent="deploy the new release",
            metadata={"name": "deploy-v2"},
        )
        result = await orchestrator.execute_workflow(workflow.id)
        assert result.status in (
            WorkflowStatus.COMPLETED,
            WorkflowStatus.AWAITING_APPROVAL,
        )

    @pytest.mark.asyncio
    async def test_execute_nonexistent_workflow(self, orchestrator: Orchestrator):
        with pytest.raises(ValueError, match="not found"):
            await orchestrator.execute_workflow(uuid4())

    @pytest.mark.asyncio
    async def test_rollback_workflow(self, orchestrator: Orchestrator):
        workflow = orchestrator.create_workflow(
            name="Deploy v2.0",
            intent="deploy the new release",
            metadata={"name": "deploy-v2"},
        )
        await orchestrator.execute_workflow(workflow.id)
        result = await orchestrator.rollback_workflow(workflow.id)
        assert result.status == WorkflowStatus.ROLLED_BACK

    @pytest.mark.asyncio
    async def test_rollback_nonexistent_workflow(self, orchestrator: Orchestrator):
        with pytest.raises(ValueError, match="not found"):
            await orchestrator.rollback_workflow(uuid4())


class TestOrchestratorApproval:
    @pytest.mark.asyncio
    async def test_approve_workflow(self, orchestrator: Orchestrator):
        workflow = orchestrator.create_workflow(
            name="Change DB",
            intent="change the database configuration",
            metadata={"name": "db-change", "risk_level": "high"},
        )
        executed = await orchestrator.execute_workflow(workflow.id)

        if executed.status == WorkflowStatus.AWAITING_APPROVAL:
            result = await orchestrator.approve_workflow(
                workflow.id, approved=True, reason="Looks good"
            )
            assert result.status == WorkflowStatus.APPROVED

    @pytest.mark.asyncio
    async def test_reject_workflow(self, orchestrator: Orchestrator):
        workflow = orchestrator.create_workflow(
            name="Risky Change",
            intent="change the network firewall rules",
            metadata={"name": "fw-change", "risk_level": "critical"},
        )
        executed = await orchestrator.execute_workflow(workflow.id)

        if executed.status == WorkflowStatus.AWAITING_APPROVAL:
            result = await orchestrator.approve_workflow(
                workflow.id, approved=False, reason="Too risky"
            )
            assert result.status == WorkflowStatus.REJECTED


class TestOrchestratorQuery:
    def test_list_workflows(self, orchestrator: Orchestrator):
        orchestrator.create_workflow(name="WF1", intent="deploy app")
        orchestrator.create_workflow(name="WF2", intent="incident alert")
        workflows = orchestrator.list_workflows()
        assert len(workflows) == 2

    def test_list_workflows_with_status_filter(self, orchestrator: Orchestrator):
        orchestrator.create_workflow(name="WF1", intent="deploy app")
        workflows = orchestrator.list_workflows(status=WorkflowStatus.PENDING)
        assert len(workflows) == 1
        assert workflows[0].status == WorkflowStatus.PENDING

    def test_get_workflow_by_id(self, orchestrator: Orchestrator):
        workflow = orchestrator.create_workflow(name="Test", intent="deploy")
        retrieved = orchestrator.get_workflow(workflow.id)
        assert retrieved is not None
        assert retrieved.id == workflow.id

    def test_get_nonexistent_workflow(self, orchestrator: Orchestrator):
        result = orchestrator.get_workflow(uuid4())
        assert result is None
