"""Pydantic models for the Autonomous Ops Engine."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class WorkflowStatus(str, Enum):
    """Status of a workflow execution."""

    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class StepStatus(str, Enum):
    """Status of a workflow step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


class ApprovalStatus(str, Enum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class WorkflowType(str, Enum):
    """Types of workflows supported."""

    DEPLOYMENT = "deployment"
    INCIDENT_RESPONSE = "incident_response"
    CHANGE_REQUEST = "change_request"
    MAINTENANCE = "maintenance"
    ONBOARDING = "onboarding"
    CUSTOM = "custom"


class AgentType(str, Enum):
    """Types of agents in the system."""

    VALIDATION = "validation"
    ROUTING = "routing"
    APPROVAL = "approval"
    AUDIT = "audit"


class WorkflowStep(BaseModel):
    """A single step in a workflow."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    agent_type: AgentType
    description: str = ""
    depends_on: list[UUID] = Field(default_factory=list)
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retries: int = 0
    max_retries: int = 3


class Workflow(BaseModel):
    """A workflow definition and its execution state."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    workflow_type: WorkflowType
    description: str = ""
    steps: list[WorkflowStep] = Field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_by: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Agent(BaseModel):
    """Represents an agent in the system."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    agent_type: AgentType
    description: str = ""
    is_active: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    """A human-in-the-loop approval request."""

    id: UUID = Field(default_factory=uuid4)
    workflow_id: UUID
    step_id: UUID
    requested_by: str = ""
    assigned_to: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    recommendation: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    decision_reason: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None


class AuditEvent(BaseModel):
    """An audit log entry for workflow events."""

    id: UUID = Field(default_factory=uuid4)
    workflow_id: UUID
    step_id: UUID | None = None
    event_type: str
    agent_type: AgentType | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WorkflowSubmission(BaseModel):
    """Request model for submitting a new workflow."""

    name: str
    intent: str
    description: str = ""
    created_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    """Request model for approving or rejecting a workflow."""

    approved: bool
    reason: str = ""
    decided_by: str = ""
