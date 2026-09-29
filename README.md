# ShadowOps

ShadowOps is an incident-response workspace for SRE teams. It investigates service incidents, inspects service signals, recalls prior incident outcomes from Hindsight, and records remediation results as persistent organizational memory.

> ShadowOps currently operates on deterministic simulated services and does not connect to or modify production infrastructure.

## The Problem

During an incident, engineers often repeat investigations and remediation attempts because knowledge from previous incidents is scattered across tickets, logs, documentation, and conversations.

A restart may temporarily recover a service without addressing the underlying problem. Without persistent memory, a future investigation may repeat the same failed approach.

## The Solution

ShadowOps combines incident investigation tools with a dedicated Hindsight memory bank.

The system:

- Inspects current logs, metrics, deployments, service state, and dependencies.
- Recalls relevant outcomes from previous incidents using Hindsight.
- Keeps failed, partial, and successful remediation attempts separate.
- Records resolved incidents and their lessons as persistent memory.
- Uses previously recorded outcomes to provide useful context during future investigations.

## Why Hindsight?

Hindsight acts as the long-term memory layer for ShadowOps.

The application database stores operational state such as incidents, tool traces, remediation attempts, and write receipts. Hindsight stores the cross-incident knowledge that can be recalled during future investigations.

ShadowOps uses the official Hindsight Python client for real retain and recall operations.

- [Hindsight GitHub](https://github.com/vectorize-io/hindsight)
- [Hindsight Documentation](https://hindsight.vectorize.io/)
- [What is Agent Memory?](https://vectorize.io/what-is-agent-memory)

## Architecture

```text
                         ┌──────────────────────┐
                         │     ShadowOps UI     │
                         │ React + TypeScript   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     FastAPI API      │
                         │    Python Backend    │
                         └──────────┬───────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
                 ▼                  ▼                  ▼
        ┌────────────────┐ ┌───────────────┐ ┌─────────────────┐
        │ Incident Tools │ │    SQLite     │ │    Hindsight    │
        │ Logs / Metrics │ │ Operational   │ │ Long-term       │
        │ Health / Deps  │ │ State & Traces│ │ Memory          │
        └────────────────┘ └───────────────┘ └─────────────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Groq Tool Planner  │
                         │ Function Calling /   │
                         │ Rules-based Fallback │
                         └──────────────────────┘
```

The Groq planner uses function calling when `GROQ_API_KEY` is configured. When it is not configured, ShadowOps uses an explicit rules-based planner.

Hindsight and Groq credentials remain on the backend.

## Memory Lifecycle

1. The operator submits incident details.
2. The planner selects bounded investigation tools.
3. Tools inspect deterministic service fixtures and return structured evidence.
4. ShadowOps sends a compact incident query to Hindsight.
5. Relevant historical facts are recalled and displayed to the operator.
6. The operator runs one or more remediation simulations.
7. Each remediation result is recorded as **Failed**, **Partial**, or **Successful**.
8. When the incident is resolved, the remediation attempts and incident summary are retained in Hindsight.
9. A later investigation can recall those facts and use them as historical context.

## Features

- Five simulated services:
  - Checkout
  - Payment
  - Order
  - Authentication
  - Notifications
- Structured service health, logs, metrics, deployment, and dependency tools.
- Groq-compatible function calling with schema validation.
- Explicit rules-based fallback when Groq is unavailable.
- Real Hindsight Cloud recall and retain operations.
- Stable Hindsight document identifiers.
- Clear unavailable and empty-memory states.
- Deterministic remediation simulations.
- SQLite persistence for incidents, tool traces, remediation attempts, and Hindsight write receipts.
- Demo seed and reset/reseed functionality.
- Side-by-side evaluation with and without Hindsight recall.
- Responsive interface for investigation, timeline, memory evidence, service health, and evaluation.

## Example Incident

Consider a checkout service returning `503` errors because its database connection pool is exhausted.

A restart may temporarily restore the service, but the underlying database pool limitation remains.

ShadowOps can:

1. Inspect the current service signals.
2. Recall a previous incident from Hindsight.
3. Identify that restarting the service previously provided only temporary recovery.
4. Simulate the restart and record it as a failed or partial remediation.
5. Simulate increasing the database connection pool.
6. Record the successful remediation.
7. Retain the outcome in Hindsight.

If a similar incident occurs later, the previous remediation history can be recalled instead of starting from scratch.

## Technology

### Frontend

- React 19
- TypeScript
- Vite
- Lucide Icons

### Backend

- Python
- FastAPI
- Pydantic
- SQLite

### Agent Planner

- Groq-compatible chat completions
- Function calling
- Rules-based fallback

### Memory

- Hindsight
- Official `hindsight-client`
- Hindsight Cloud or compatible local Hindsight API

## Setup

Requirements:

- Python 3.11+
- Node.js 20+

Create the Python environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install backend dependencies:

```powershell
pip install -r requirements-dev.txt
```

Install frontend dependencies:

```powershell
npm --prefix frontend install
```

Create the environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` locally.

For Hindsight Cloud:

```env
HINDSIGHT_API_URL=https://api.hindsight.vectorize.io
HINDSIGHT_BANK_ID=shadowops-demo
HINDSIGHT_API_KEY=your-real-cloud-api-key
```

Optional Groq configuration:

```env
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=openai/gpt-oss-120b
```

For a local Hindsight server, change `HINDSIGHT_API_URL` to the appropriate local endpoint.

> Never commit API keys or other secrets. `.env` is ignored by Git, while `.env.example` contains placeholders only.

## Run Locally

### Backend

Open a terminal and run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.shadowops.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

Open another terminal:

```powershell
npm --prefix frontend run dev
```

Open:

```text
http://127.0.0.1:5173
```

FastAPI documentation:

```text
http://127.0.0.1:8000/docs
```

Backend health:

```text
http://127.0.0.1:8000/health
```

The SQLite ledger defaults to:

```text
data/shadowops.sqlite3
```

You can override this using `SHADOWOPS_DB_PATH`.

The SQLite database stores application state only. Hindsight remains the long-term memory layer.

## Demo Flow

A typical investigation follows this flow:

```text
Seed Hindsight Memories
        ↓
Investigate Incident
        ↓
Inspect Current Signals
        ↓
Recall Historical Outcomes
        ↓
Review Recommended Action
        ↓
Run Remediation
        ↓
Record Outcome
        ↓
Retain Resolution in Hindsight
        ↓
Investigate a Similar Incident
        ↓
Recall Previous Knowledge
```

For the detailed walkthrough, see [`docs/DEMO_RUNBOOK.md`](docs/DEMO_RUNBOOK.md).

## Evaluation

ShadowOps includes an evaluation workflow that compares the same incident with and without Hindsight recall.

The evaluation records:

- Tool calls
- Current incident evidence
- Returned Hindsight facts
- Explicitly tagged remediation outcomes
- Measured latency
- Evaluation run data

The results are stored in SQLite and can be reviewed through the evaluation interface.

See [`docs/EVALUATION.md`](docs/EVALUATION.md) for details.

## Tests

Run backend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Build the frontend:

```powershell
npm --prefix frontend run build
```

The live Hindsight Cloud lifecycle test is opt-in through:

```env
RUN_HINDSIGHT_CLOUD_E2E=1
```

A unit test using an in-memory test double does not verify the live Hindsight Cloud integration.

## Project Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Hindsight Architecture](docs/HINDSIGHT_ARCHITECTURE.md)
- [Demo Runbook](docs/DEMO_RUNBOOK.md)
- [Evaluation](docs/EVALUATION.md)

## Future Improvements

- Add an LLM-based answer synthesis layer with strict evidence citations.
- Add authentication and team/tenant boundaries.
- Replace deterministic fixtures with authorized observability integrations.
- Expand evaluation to repeated datasets and report aggregate results with uncertainty.
- Support additional incident types and remediation workflows.