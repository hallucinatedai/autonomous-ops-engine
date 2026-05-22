"""Tests for the FastAPI REST API."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from ops_engine.api import app
from ops_engine.orchestrator import Orchestrator


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    app.state.orchestrator = Orchestrator(db_path=db_path)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ops-engine"


class TestWorkflowEndpoints:
    @pytest.mark.asyncio
    async def test_submit_workflow(self, client: AsyncClient):
        response = await client.post(
            "/workflows",
            json={
                "name": "Deploy v2.0",
                "intent": "deploy to production",
                "created_by": "test-user",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Deploy v2.0"
        assert data["workflow_type"] == "deployment"
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_workflow(self, client: AsyncClient):
        create_resp = await client.post(
            "/workflows",
            json={"name": "Test WF", "intent": "deploy app"},
        )
        wf_id = create_resp.json()["id"]

        response = await client.get(f"/workflows/{wf_id}")
        assert response.status_code == 200
        assert response.json()["id"] == wf_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_workflow(self, client: AsyncClient):
        response = await client.get(
            "/workflows/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_workflows(self, client: AsyncClient):
        await client.post(
            "/workflows", json={"name": "WF1", "intent": "deploy"}
        )
        await client.post(
            "/workflows", json={"name": "WF2", "intent": "incident alert"}
        )

        response = await client.get("/workflows")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_workflows_with_status_filter(self, client: AsyncClient):
        await client.post(
            "/workflows", json={"name": "WF1", "intent": "deploy"}
        )

        response = await client.get("/workflows?status=pending")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_execute_workflow(self, client: AsyncClient):
        create_resp = await client.post(
            "/workflows",
            json={
                "name": "Deploy",
                "intent": "deploy app",
                "metadata": {"name": "test-deploy"},
            },
        )
        wf_id = create_resp.json()["id"]

        response = await client.post(f"/workflows/{wf_id}/execute")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("completed", "awaiting_approval")

    @pytest.mark.asyncio
    async def test_execute_nonexistent_workflow(self, client: AsyncClient):
        response = await client.post(
            "/workflows/00000000-0000-0000-0000-000000000000/execute"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_rollback_workflow(self, client: AsyncClient):
        create_resp = await client.post(
            "/workflows",
            json={
                "name": "Deploy",
                "intent": "deploy app",
                "metadata": {"name": "test"},
            },
        )
        wf_id = create_resp.json()["id"]
        await client.post(f"/workflows/{wf_id}/execute")

        response = await client.post(f"/workflows/{wf_id}/rollback")
        assert response.status_code == 200
        assert response.json()["status"] == "rolled_back"


class TestApprovalEndpoints:
    @pytest.mark.asyncio
    async def test_approve_workflow(self, client: AsyncClient):
        create_resp = await client.post(
            "/workflows",
            json={
                "name": "Change",
                "intent": "change config",
                "metadata": {"name": "cfg", "risk_level": "high"},
            },
        )
        wf_id = create_resp.json()["id"]

        exec_resp = await client.post(f"/workflows/{wf_id}/execute")
        if exec_resp.json()["status"] == "awaiting_approval":
            response = await client.post(
                f"/workflows/{wf_id}/approve",
                json={"approved": True, "reason": "Approved by test"},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "approved"

    @pytest.mark.asyncio
    async def test_approve_non_pending_workflow(self, client: AsyncClient):
        create_resp = await client.post(
            "/workflows",
            json={"name": "WF", "intent": "deploy"},
        )
        wf_id = create_resp.json()["id"]

        response = await client.post(
            f"/workflows/{wf_id}/approve",
            json={"approved": True, "reason": "test"},
        )
        assert response.status_code == 400


class TestAuditEndpoints:
    @pytest.mark.asyncio
    async def test_get_audit_trail(self, client: AsyncClient):
        create_resp = await client.post(
            "/workflows",
            json={
                "name": "Deploy",
                "intent": "deploy app",
                "metadata": {"name": "test"},
            },
        )
        wf_id = create_resp.json()["id"]
        await client.post(f"/workflows/{wf_id}/execute")

        response = await client.get(f"/workflows/{wf_id}/audit")
        assert response.status_code == 200
        data = response.json()
        assert data["workflow_id"] == wf_id

    @pytest.mark.asyncio
    async def test_audit_nonexistent_workflow(self, client: AsyncClient):
        response = await client.get(
            "/workflows/00000000-0000-0000-0000-000000000000/audit"
        )
        assert response.status_code == 404


class TestAnalyticsEndpoints:
    @pytest.mark.asyncio
    async def test_get_patterns(self, client: AsyncClient):
        response = await client.get("/analytics/patterns")
        assert response.status_code == 200
        data = response.json()
        assert "total_workflows" in data
        assert "success_rate" in data
