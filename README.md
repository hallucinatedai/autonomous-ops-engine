# Autonomous Ops Engine

AI-native workflow orchestration system for enterprise operations.

## Overview

The Autonomous Ops Engine provides intelligent workflow routing, orchestration, and execution with human-in-the-loop approvals for enterprise operational tasks. It uses an agent-based architecture where specialized agents handle validation, routing, approval, and audit logging.

## Features

- **Workflow Router** — Maps user intent to workflow type using keyword matching
- **Orchestrator** — Executes workflows step-by-step with state management
- **Agent Framework** — Pluggable agents with `validate()`, `execute()`, `rollback()` interface
- **Validation Agent** — Checks policy rules, data quality, and completeness
- **Routing Agent** — Determines responsible teams and escalation chains
- **Approval Agent** — Human-in-the-loop approval with context-aware recommendations
- **Audit Agent** — Immutable audit logging for all workflow events
- **Operational Memory** — SQLite-backed workflow history and pattern analysis
- **REST API** — FastAPI endpoints for workflow submission, execution, and management

## Architecture

```
User Intent → Workflow Router → Orchestrator → Agent Pipeline → Operational Memory
                                     ↓
                    [Validation → Routing → Approval → Audit]
```

## Tech Stack

- Python 3.11+
- FastAPI + uvicorn
- Pydantic v2
- SQLite (persistence)
- pytest (testing)

## Quick Start

### Prerequisites

- Python 3.11 or higher
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/hallucinatedai/autonomous-ops-engine.git
cd autonomous-ops-engine

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"
```

### Running the API

```bash
uvicorn ops_engine.api:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Running Tests

```bash
pytest
```

### Using Docker

```bash
docker compose up --build
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/workflows` | Submit a new workflow |
| GET | `/workflows` | List workflows (optional `?status=` filter) |
| GET | `/workflows/{id}` | Get workflow details |
| POST | `/workflows/{id}/execute` | Execute a pending workflow |
| POST | `/workflows/{id}/approve` | Approve/reject a workflow |
| POST | `/workflows/{id}/rollback` | Rollback a workflow |
| GET | `/workflows/{id}/audit` | Get audit trail |
| GET | `/analytics/patterns` | Workflow execution analytics |

## Example Usage

```bash
# Submit a workflow
curl -X POST http://localhost:8000/workflows \
  -H "Content-Type: application/json" \
  -d '{"name": "Deploy v2.0", "intent": "deploy the app to production", "created_by": "ops-team"}'

# Execute the workflow
curl -X POST http://localhost:8000/workflows/{workflow_id}/execute

# Check status
curl http://localhost:8000/workflows/{workflow_id}
```

## Project Structure

```
autonomous-ops-engine/
├── src/ops_engine/
│   ├── __init__.py
│   ├── models.py          # Pydantic models
│   ├── orchestrator.py    # Central orchestration engine
│   ├── router.py          # Intent → workflow type routing
│   ├── memory.py          # SQLite operational memory
│   ├── api.py             # FastAPI REST API
│   └── agents/
│       ├── base.py        # Base agent interface
│       ├── validation.py  # Validation agent
│       ├── routing.py     # Routing agent
│       ├── approval.py    # Approval agent
│       └── audit.py       # Audit agent
├── tests/
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Contributors

- Akash Raj
- Prem Kumar
