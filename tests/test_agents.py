"""Tests for the agent framework."""

from uuid import uuid4

import pytest

from ops_engine.agents.approval import ApprovalAgent
from ops_engine.agents.audit import AuditAgent
from ops_engine.agents.routing import RoutingAgent
from ops_engine.agents.validation import ValidationAgent
from ops_engine.models import AgentType, WorkflowStep, WorkflowType


def _make_step(
    name: str = "test_step",
    agent_type: AgentType = AgentType.VALIDATION,
    input_data: dict | None = None,
) -> WorkflowStep:
    return WorkflowStep(
        name=name,
        agent_type=agent_type,
        input_data=input_data or {},
    )


class TestValidationAgent:
    @pytest.fixture
    def agent(self) -> ValidationAgent:
        return ValidationAgent(config={"required_fields": ["name", "target"]})

    @pytest.mark.asyncio
    async def test_validate_valid_step(self, agent: ValidationAgent):
        step = _make_step(input_data={"name": "deploy", "target": "prod"})
        assert await agent.validate(step) is True

    @pytest.mark.asyncio
    async def test_validate_empty_input(self, agent: ValidationAgent):
        step = _make_step(input_data={})
        assert await agent.validate(step) is False

    @pytest.mark.asyncio
    async def test_execute_all_fields_present(self, agent: ValidationAgent):
        step = _make_step(input_data={"name": "deploy", "target": "prod"})
        result = await agent.execute(step)
        assert result["valid"] is True
        assert result["issues"] == []

    @pytest.mark.asyncio
    async def test_execute_missing_fields(self, agent: ValidationAgent):
        step = _make_step(input_data={"name": "deploy"})
        result = await agent.execute(step)
        assert result["valid"] is False
        assert len(result["issues"]) == 1

    @pytest.mark.asyncio
    async def test_rollback(self, agent: ValidationAgent):
        step = _make_step()
        assert await agent.rollback(step) is True


class TestRoutingAgent:
    @pytest.fixture
    def agent(self) -> RoutingAgent:
        return RoutingAgent()

    @pytest.mark.asyncio
    async def test_validate_with_workflow_type(self, agent: RoutingAgent):
        step = _make_step(
            agent_type=AgentType.ROUTING,
            input_data={"workflow_type": WorkflowType.DEPLOYMENT},
        )
        assert await agent.validate(step) is True

    @pytest.mark.asyncio
    async def test_validate_without_workflow_type(self, agent: RoutingAgent):
        step = _make_step(agent_type=AgentType.ROUTING, input_data={})
        assert await agent.validate(step) is False

    @pytest.mark.asyncio
    async def test_execute_deployment_routing(self, agent: RoutingAgent):
        step = _make_step(
            agent_type=AgentType.ROUTING,
            input_data={"workflow_type": WorkflowType.DEPLOYMENT},
        )
        result = await agent.execute(step)
        assert result["assigned_team"] == "platform-engineering"
        assert result["sla_hours"] == 4

    @pytest.mark.asyncio
    async def test_execute_critical_priority(self, agent: RoutingAgent):
        step = _make_step(
            agent_type=AgentType.ROUTING,
            input_data={
                "workflow_type": WorkflowType.MAINTENANCE,
                "priority": "critical",
            },
        )
        result = await agent.execute(step)
        assert result["sla_hours"] == 2  # 8 // 4

    @pytest.mark.asyncio
    async def test_rollback(self, agent: RoutingAgent):
        step = _make_step(agent_type=AgentType.ROUTING)
        assert await agent.rollback(step) is True


class TestApprovalAgent:
    @pytest.fixture
    def agent(self) -> ApprovalAgent:
        return ApprovalAgent()

    @pytest.mark.asyncio
    async def test_validate_with_workflow_id(self, agent: ApprovalAgent):
        step = _make_step(
            agent_type=AgentType.APPROVAL,
            input_data={"workflow_id": str(uuid4())},
        )
        assert await agent.validate(step) is True

    @pytest.mark.asyncio
    async def test_validate_without_workflow_id(self, agent: ApprovalAgent):
        step = _make_step(agent_type=AgentType.APPROVAL, input_data={})
        assert await agent.validate(step) is False

    @pytest.mark.asyncio
    async def test_execute_creates_approval(self, agent: ApprovalAgent):
        step = _make_step(
            agent_type=AgentType.APPROVAL,
            input_data={"workflow_id": str(uuid4()), "risk_level": "high"},
        )
        result = await agent.execute(step)
        assert result["approval_status"] == "pending"
        assert "approval_id" in result

    @pytest.mark.asyncio
    async def test_auto_approve_low_risk(self):
        agent = ApprovalAgent(config={"auto_approve_low_risk": True})
        step = _make_step(
            agent_type=AgentType.APPROVAL,
            input_data={"workflow_id": str(uuid4()), "risk_level": "low"},
        )
        result = await agent.execute(step)
        assert result["approval_status"] == "approved"
        assert result["auto_approved"] is True

    @pytest.mark.asyncio
    async def test_resolve_approval(self, agent: ApprovalAgent):
        step = _make_step(
            agent_type=AgentType.APPROVAL,
            input_data={"workflow_id": str(uuid4()), "risk_level": "medium"},
        )
        result = await agent.execute(step)
        from uuid import UUID

        approval_id = UUID(result["approval_id"])
        resolved = await agent.resolve_approval(approval_id, approved=True, reason="ok")
        assert resolved is not None
        assert resolved.status.value == "approved"

    @pytest.mark.asyncio
    async def test_rollback_removes_pending(self, agent: ApprovalAgent):
        step = _make_step(
            agent_type=AgentType.APPROVAL,
            input_data={"workflow_id": str(uuid4())},
        )
        await agent.execute(step)
        assert len(agent.get_pending_approvals()) == 1
        await agent.rollback(step)
        assert len(agent.get_pending_approvals()) == 0


class TestAuditAgent:
    @pytest.fixture
    def agent(self) -> AuditAgent:
        return AuditAgent()

    @pytest.mark.asyncio
    async def test_validate(self, agent: AuditAgent):
        step = _make_step(agent_type=AgentType.AUDIT)
        assert await agent.validate(step) is True

    @pytest.mark.asyncio
    async def test_execute_logs_event(self, agent: AuditAgent):
        step = _make_step(
            agent_type=AgentType.AUDIT,
            input_data={"workflow_id": str(uuid4()), "event_type": "test_event"},
        )
        result = await agent.execute(step)
        assert result["logged"] is True
        assert result["total_events"] == 1

    @pytest.mark.asyncio
    async def test_get_events_by_workflow(self, agent: AuditAgent):
        wf_id = uuid4()
        await agent.log_event(
            workflow_id=wf_id, event_type="test", details={"key": "value"}
        )
        events = agent.get_events(workflow_id=wf_id)
        assert len(events) == 1
        assert events[0].event_type == "test"

    @pytest.mark.asyncio
    async def test_get_events_by_type(self, agent: AuditAgent):
        wf_id = uuid4()
        await agent.log_event(workflow_id=wf_id, event_type="type_a")
        await agent.log_event(workflow_id=wf_id, event_type="type_b")
        events = agent.get_events(event_type="type_a")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_rollback_logs_event(self, agent: AuditAgent):
        step = _make_step(
            agent_type=AgentType.AUDIT,
            input_data={"workflow_id": str(uuid4())},
        )
        await agent.rollback(step)
        assert agent.get_event_count() == 1
        events = agent.get_events(event_type="step_rolled_back")
        assert len(events) == 1
