# ShadowOps Backend: Phase 2

This backend slice supports fixture-backed investigation tools, optional Groq tool selection, real Hindsight recall, deterministic checkout remediation simulation, and retaining resolved incident outcomes through the Hindsight Python client. When `GROQ_API_KEY` is configured, the agent uses Groq function calling to choose tools. Without it, a transparent symptom-based rules planner is used and returned as `planner_mode: rules_fallback`; this is not reported as an LLM run.

## Setup

From the repository root, create and activate a virtual environment, then install the dependencies:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edit `.env` with `HINDSIGHT_API_URL=https://api.hindsight.vectorize.io`, your dedicated `HINDSIGHT_BANK_ID`, and a real `HINDSIGHT_API_KEY` from Hindsight Cloud. Keep the key only in `.env`; the backend sends it as bearer authentication through the official Python SDK. Set `GROQ_API_KEY` to enable Groq function calling; `GROQ_MODEL` defaults to `openai/gpt-oss-120b`. `RUN_HINDSIGHT_CLOUD_E2E=1` is only needed to opt into the live integration test. For a local Hindsight server, use its API URL (commonly `http://localhost:8888`); the server itself must have its own LLM provider configured for memory extraction. No application endpoint fabricates memory if Hindsight is unavailable.

Start the API:

```powershell
python -m uvicorn backend.shadowops.main:app --reload
```

Interactive API documentation is at `http://127.0.0.1:8000/docs`; health check is `http://127.0.0.1:8000/health`.

## Phase 2 Flow

1. `POST /api/incidents/investigate` selects fixture-backed tools, runs them, then performs a real Hindsight recall and returns current tool evidence plus matching-service memories.
2. `POST /api/incidents/simulate-remediation` simulates deterministic outcomes for the checkout 503/database-pool demo scenario.
3. `POST /api/incidents/resolve` writes the supplied incident evidence and remediation outcomes to Hindsight. A successful response is returned only when Hindsight confirms the synchronous write.
4. Investigate a similar incident again to view the selected tools, their structured evidence, actual Hindsight facts, and the recommendation derived from explicitly labeled successful/failed actions.

The test suite uses an in-memory test double to verify orchestration. That is not a live Hindsight integration test. To verify real persistence and recall, configure a Hindsight service, start the API, and run the four requests above; the response includes the actual returned memory text and identifiers.

Run focused tests with `python -m pytest tests/test_incident_memory_workflow.py -q`.

After configuring the Cloud values in `.env`, run the real, non-mocked integration test with:

```powershell
$env:RUN_HINDSIGHT_CLOUD_E2E = "1"
python -m pytest tests/test_hindsight_cloud_live.py -q
```

The test refuses to run against a local endpoint, uses unique incident IDs, checks actual recalled facts/metadata from the configured Cloud bank, and leaves its test records in that bank.