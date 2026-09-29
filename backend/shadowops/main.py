from contextlib import contextmanager
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .hindsight_memory import (
    MemoryConfigurationError,
    MemoryServiceError,
    configured_memory_store,
)
from .incident_agent import IncidentMemoryAgent
from .incident_agent import simulate_remediation
from .tool_calling import ToolPlanningError
from .repository import IncidentRepository
from .demo_scenarios import DEMO_INCIDENTS
from .simulated_environment import SERVICES, service_health
from .models import (
    IncidentRequest,
    InvestigationResponse,
    EvaluationRequest,
    RemediationSimulationRequest,
    RemediationSimulationResponse,
    ResolveIncidentRequest,
    RetainResponse,
)

load_dotenv()
repository = IncidentRepository()
logger = logging.getLogger("shadowops.request")
app = FastAPI(title="ShadowOps Incident Memory API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        started = perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            (perf_counter() - started) * 1000,
        )
        return response


app.add_middleware(RequestIdMiddleware)


@contextmanager
def _agent():
    memory = None
    try:
        memory, bank_id = configured_memory_store()
    except MemoryConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        yield IncidentMemoryAgent(memory, bank_id)
    finally:
        close = getattr(memory, "close", None)
        if close is not None:
            try:
                close()
            except MemoryServiceError:
                pass


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "memory": "not_checked"}


@app.post("/api/incidents/investigate", response_model=InvestigationResponse)
def investigate(incident: IncidentRequest) -> InvestigationResponse:
    try:
        started = perf_counter()
        with _agent() as agent:
            result = agent.investigate(incident)
        repository.save_investigation(incident, result, (perf_counter() - started) * 1000)
        return result
    except MemoryServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ToolPlanningError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/incidents/resolve", response_model=RetainResponse)
def resolve(request: ResolveIncidentRequest) -> RetainResponse:
    try:
        with _agent() as agent:
            agent.resolve(request)
            bank_id = agent.bank_id
    except MemoryServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    repository.save_resolution(
        request,
        bank_id,
        f"shadowops-incident-{request.incident.incident_id}-summary",
    )
    return RetainResponse(
        incident_id=request.incident.incident_id,
        retained=True,
        bank_id=agent.bank_id,
        document_id=f"shadowops-incident-{request.incident.incident_id}-summary",
        message="Hindsight confirmed the incident attempts and summary writes.",
    )


@app.post("/api/incidents/simulate-remediation", response_model=RemediationSimulationResponse)
def simulate(request: RemediationSimulationRequest) -> RemediationSimulationResponse:
    attempt = simulate_remediation(request.incident, request.action)
    repository.save_remediation(request.incident, attempt)
    return RemediationSimulationResponse(
        incident_id=request.incident.incident_id,
        attempt=attempt,
    )


@app.get("/api/dashboard")
def dashboard() -> dict:
    return repository.dashboard()


@app.get("/api/incidents")
def incidents() -> list[dict]:
    return repository.list_incidents()


@app.get("/api/system-health")
def system_health() -> list[dict]:
    return [service_health(service) for service in SERVICES]


@app.post("/api/demo/seed")
def seed_demo() -> dict:
    try:
        with _agent() as agent:
            for incident in DEMO_INCIDENTS:
                agent.resolve(incident)
                repository.save_resolution(
                    incident,
                    agent.bank_id,
                    f"shadowops-incident-{incident.incident.incident_id}-summary",
                )
            bank_id = agent.bank_id
    except MemoryServiceError as exc:
        raise HTTPException(status_code=503, detail=f"Demo seed stopped; Hindsight did not confirm all writes: {exc}") from exc
    return {
        "seeded_incidents": len(DEMO_INCIDENTS),
        "bank_id": bank_id,
        "incident_ids": [item.incident.incident_id for item in DEMO_INCIDENTS],
        "note": "Hindsight memories are real; reset only clears local app state and reseeds these stable demo documents.",
    }


@app.post("/api/demo/reset")
def reset_demo() -> dict:
    repository.reset_app_data()
    return seed_demo()


@app.post("/api/evaluation/run")
def evaluate(request: EvaluationRequest) -> dict:
    try:
        runs = []
        with _agent() as agent:
            for use_memory, mode in ((False, "without_memory"), (True, "with_memory")):
                started = perf_counter()
                result = agent.investigate(request.incident, use_memory=use_memory)
                latency_ms = (perf_counter() - started) * 1000
                result_data = result.model_dump(mode="json")
                run_id = str(uuid4())
                repository.record_evaluation(run_id, request.incident.incident_id, mode, latency_ms, result_data)
                outcomes = {
                    item.metadata.get("remediation_outcome")
                    for item in result.historical_memories
                }
                runs.append({
                    "run_id": run_id,
                    "mode": mode,
                    "latency_ms": round(latency_ms, 2),
                    "relevant_memories_returned": len(result.historical_memories),
                    "failed_approach_recalled": "failed" in outcomes,
                    "successful_approach_recalled": "successful" in outcomes,
                    "diagnosis": result.probable_cause,
                    "recommendation": result.recommendation,
                    "planner_mode": result.planner_mode,
                })
        return {"incident": request.incident.model_dump(mode="json"), "runs": runs}
    except MemoryServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ToolPlanningError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc