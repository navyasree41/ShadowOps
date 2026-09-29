from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class IncidentRequest(BaseModel):
    incident_id: str = Field(min_length=1, max_length=80)
    service: str = Field(min_length=1, max_length=120)
    symptoms: str = Field(min_length=1, max_length=2000)
    environment: str = Field(default="staging", min_length=1, max_length=80)
    deployment_version: str = Field(default="unknown", max_length=80)
    evidence: list[str] = Field(default_factory=list, max_length=20)


class RemediationAttempt(BaseModel):
    action: str = Field(min_length=1, max_length=500)
    outcome: Literal["failed", "partial", "successful"]
    details: str = Field(min_length=1, max_length=1000)
    duration_minutes: float | None = Field(default=None, ge=0)


class ResolveIncidentRequest(BaseModel):
    incident: IncidentRequest
    root_cause: str = Field(min_length=1, max_length=1000)
    remediation_attempts: list[RemediationAttempt] = Field(min_length=1, max_length=20)
    lesson: str = Field(min_length=1, max_length=1000)
    recovery_time_minutes: float | None = Field(default=None, ge=0)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RemediationSimulationRequest(BaseModel):
    incident: IncidentRequest
    action: str = Field(min_length=1, max_length=500)


class RecalledMemory(BaseModel):
    id: str
    text: str
    type: str | None = None
    context: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    rank: int


class InvestigationToolResult(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None


class InvestigationResponse(BaseModel):
    incident: IncidentRequest
    summary: str
    probable_cause: str
    recommendation: str
    confidence: Literal["low", "moderate"]
    memory_mode: Literal["with_memory", "without_memory"]
    planner_mode: Literal["groq", "rules_fallback", "groq_with_rules_fallback"]
    tool_results: list[InvestigationToolResult]
    historical_memories: list[RecalledMemory]
    memory_status: Literal["available", "empty"]


class RetainResponse(BaseModel):
    incident_id: str
    retained: bool
    bank_id: str
    document_id: str
    message: str


class RemediationSimulationResponse(BaseModel):
    incident_id: str
    attempt: RemediationAttempt
    simulation: str = "deterministic_demo"


class EvaluationRequest(BaseModel):
    incident: IncidentRequest


class DemoActionRequest(BaseModel):
    incident_id: str = Field(min_length=1, max_length=80)
    action: str = Field(min_length=1, max_length=500)