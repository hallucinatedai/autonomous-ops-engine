"""Operational memory for workflow history and execution patterns."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from ops_engine.models import AuditEvent, Workflow, WorkflowStatus


class OperationalMemory:
    """Store and query workflow history, prior approvals, and execution patterns."""

    def __init__(self, db_path: str = "ops_engine.db"):
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database schema."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    workflow_type TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    status TEXT NOT NULL,
                    created_by TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS workflow_steps (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    agent_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_data TEXT DEFAULT '{}',
                    output_data TEXT DEFAULT '{}',
                    error_message TEXT,
                    depends_on TEXT DEFAULT '[]',
                    step_order INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    step_id TEXT,
                    event_type TEXT NOT NULL,
                    agent_type TEXT,
                    details TEXT DEFAULT '{}',
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
                );

                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requested_by TEXT DEFAULT '',
                    assigned_to TEXT DEFAULT '',
                    recommendation TEXT DEFAULT '',
                    decision_reason TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
                );

                CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status);
                CREATE INDEX IF NOT EXISTS idx_workflows_type ON workflows(workflow_type);
                CREATE INDEX IF NOT EXISTS idx_audit_workflow ON audit_events(workflow_id);
                CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type);
            """)
        finally:
            conn.close()

    def save_workflow(self, workflow: Workflow) -> None:
        """Persist a workflow to the database."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO workflows
                (id, name, workflow_type, description, status,
                 created_by, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(workflow.id),
                    workflow.name,
                    workflow.workflow_type.value,
                    workflow.description,
                    workflow.status.value,
                    workflow.created_by,
                    workflow.created_at.isoformat(),
                    workflow.updated_at.isoformat(),
                    json.dumps(workflow.metadata),
                ),
            )

            for idx, step in enumerate(workflow.steps):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO workflow_steps
                    (id, workflow_id, name, agent_type, status, input_data, output_data,
                     error_message, depends_on, step_order, started_at, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(step.id),
                        str(workflow.id),
                        step.name,
                        step.agent_type.value,
                        step.status.value,
                        json.dumps(step.input_data),
                        json.dumps(step.output_data),
                        step.error_message,
                        json.dumps([str(d) for d in step.depends_on]),
                        idx,
                        step.started_at.isoformat() if step.started_at else None,
                        step.completed_at.isoformat() if step.completed_at else None,
                    ),
                )

            conn.commit()
        finally:
            conn.close()

    def get_workflow(self, workflow_id: UUID) -> Workflow | None:
        """Retrieve a workflow by ID."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM workflows WHERE id = ?", (str(workflow_id),)
            ).fetchone()

            if row is None:
                return None

            from ops_engine.models import AgentType, StepStatus, WorkflowStep, WorkflowType

            steps_rows = conn.execute(
                "SELECT * FROM workflow_steps WHERE workflow_id = ?"
                " ORDER BY step_order ASC",
                (str(workflow_id),),
            ).fetchall()

            steps = []
            for s in steps_rows:
                depends_on_raw = s["depends_on"] if "depends_on" in s.keys() else "[]"
                steps.append(
                    WorkflowStep(
                        id=UUID(s["id"]),
                        name=s["name"],
                        agent_type=AgentType(s["agent_type"]),
                        status=StepStatus(s["status"]),
                        input_data=json.loads(s["input_data"]),
                        output_data=json.loads(s["output_data"]),
                        error_message=s["error_message"],
                        depends_on=[UUID(d) for d in json.loads(depends_on_raw)],
                        started_at=(
                            datetime.fromisoformat(s["started_at"])
                            if s["started_at"]
                            else None
                        ),
                        completed_at=(
                            datetime.fromisoformat(s["completed_at"])
                            if s["completed_at"]
                            else None
                        ),
                    )
                )

            return Workflow(
                id=UUID(row["id"]),
                name=row["name"],
                workflow_type=WorkflowType(row["workflow_type"]),
                description=row["description"],
                status=WorkflowStatus(row["status"]),
                created_by=row["created_by"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                metadata=json.loads(row["metadata"]),
                steps=steps,
            )
        finally:
            conn.close()

    def list_workflows(
        self,
        status: WorkflowStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Workflow]:
        """List workflows with optional status filter."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row

            if status:
                rows = conn.execute(
                    "SELECT id FROM workflows WHERE status = ?"
                    " ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (status.value, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id FROM workflows ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()

            workflows = []
            for row in rows:
                wf = self.get_workflow(UUID(row["id"]))
                if wf:
                    workflows.append(wf)
            return workflows
        finally:
            conn.close()

    def save_audit_event(self, event: AuditEvent) -> None:
        """Persist an audit event."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """
                INSERT INTO audit_events
                (id, workflow_id, step_id, event_type, agent_type, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event.id),
                    str(event.workflow_id),
                    str(event.step_id) if event.step_id else None,
                    event.event_type,
                    event.agent_type.value if event.agent_type else None,
                    json.dumps(event.details),
                    event.timestamp.isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_audit_events(
        self, workflow_id: UUID | None = None, limit: int = 100
    ) -> list[AuditEvent]:
        """Query audit events."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row

            if workflow_id:
                rows = conn.execute(
                    "SELECT * FROM audit_events"
                    " WHERE workflow_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (str(workflow_id), limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()

            from ops_engine.models import AgentType

            events = []
            for row in rows:
                events.append(
                    AuditEvent(
                        id=UUID(row["id"]),
                        workflow_id=UUID(row["workflow_id"]),
                        step_id=UUID(row["step_id"]) if row["step_id"] else None,
                        event_type=row["event_type"],
                        agent_type=(
                            AgentType(row["agent_type"]) if row["agent_type"] else None
                        ),
                        details=json.loads(row["details"]),
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                    )
                )
            return events
        finally:
            conn.close()

    def get_workflow_patterns(self, workflow_type: str | None = None) -> dict[str, Any]:
        """Analyze execution patterns from workflow history."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row

            if workflow_type:
                rows = conn.execute(
                    "SELECT status, COUNT(*) as count FROM workflows"
                    " WHERE workflow_type = ? GROUP BY status",
                    (workflow_type,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT status, COUNT(*) as count FROM workflows GROUP BY status"
                ).fetchall()

            total = sum(row["count"] for row in rows)
            status_counts = {row["status"]: row["count"] for row in rows}

            completed = status_counts.get("completed", 0)
            success_rate = (completed / total * 100) if total > 0 else 0.0

            return {
                "total_workflows": total,
                "status_distribution": status_counts,
                "success_rate": round(success_rate, 2),
            }
        finally:
            conn.close()

    def delete_db(self) -> None:
        """Delete the database file (for testing)."""
        path = Path(self._db_path)
        if path.exists():
            path.unlink()
