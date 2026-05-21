"""FastAPI REST API for the Autonomous Ops Engine."""

import os
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query

from ops_engine.models import (
    ApprovalDecision,
    Workflow,
    WorkflowStatus,
    WorkflowSubmission,
)
from ops_engine.orchestrator import Orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    db_path = os.environ.get("OPS_ENGINE_DB_PATH", "ops_engine.db")
    app.state.orchestrator = Orchestrator(db_path=db_path)
    yield


app = FastAPI(
    title="Autonomous Ops Engine",
    description="AI-native workflow orchestration system for enterprise operations",
    version="0.1.0",
    lifespan=lifespan,
)


def _get_orchestrator() -> Orchestrator:
    return app.state.orchestrator


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "ops-engine"}


@app.post("/workflows", response_model=Workflow, status_code=201)
async def submit_workflow(submission: WorkflowSubmission) -> Workflow:
    """Submit a new workflow for orchestration."""
    orchestrator = _get_orchestrator()
    workflow = orchestrator.create_workflow(
        name=submission.name,
        intent=submission.intent,
        description=submission.description,
        created_by=submission.created_by,
        metadata=submission.metadata,
    )
    return workflow


@app.post("/workflows/{workflow_id}/execute", response_model=Workflow)
async def execute_workflow(workflow_id: UUID) -> Workflow:
    """Execute a pending workflow."""
    orchestrator = _get_orchestrator()
    try:
        workflow = await orchestrator.execute_workflow(workflow_id)
        return workflow
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/workflows/{workflow_id}", response_model=Workflow)
async def get_workflow(workflow_id: UUID) -> Workflow:
    """Get workflow details by ID."""
    orchestrator = _get_orchestrator()
    workflow = orchestrator.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@app.get("/workflows", response_model=list[Workflow])
async def list_workflows(
    status: WorkflowStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Workflow]:
    """List workflows with optional status filter."""
    orchestrator = _get_orchestrator()
    return orchestrator.list_workflows(status=status, limit=limit, offset=offset)


@app.post("/workflows/{workflow_id}/approve", response_model=Workflow)
async def approve_workflow(workflow_id: UUID, decision: ApprovalDecision) -> Workflow:
    """Approve or reject a workflow awaiting approval."""
    orchestrator = _get_orchestrator()
    try:
        workflow = await orchestrator.approve_workflow(
            workflow_id=workflow_id,
            approved=decision.approved,
            reason=decision.reason,
        )
        return workflow
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/workflows/{workflow_id}/rollback", response_model=Workflow)
async def rollback_workflow(workflow_id: UUID) -> Workflow:
    """Rollback a workflow."""
    orchestrator = _get_orchestrator()
    try:
        workflow = await orchestrator.rollback_workflow(workflow_id)
        return workflow
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/workflows/{workflow_id}/audit")
async def get_audit_trail(workflow_id: UUID) -> dict[str, Any]:
    """Get audit trail for a workflow."""
    orchestrator = _get_orchestrator()
    workflow = orchestrator.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    events = orchestrator.memory.get_audit_events(workflow_id=workflow_id)
    return {
        "workflow_id": str(workflow_id),
        "events": [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "agent_type": e.agent_type.value if e.agent_type else None,
                "details": e.details,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in events
        ],
    }


@app.get("/analytics/patterns")
async def get_workflow_patterns(
    workflow_type: str | None = Query(default=None),
) -> dict[str, Any]:
    """Get workflow execution patterns and analytics."""
    orchestrator = _get_orchestrator()
    return orchestrator.memory.get_workflow_patterns(workflow_type=workflow_type)
