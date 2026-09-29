import re
import json
from datetime import datetime

from .hindsight_memory import MemoryFact, MemoryStore
from .models import (
    IncidentRequest,
    InvestigationResponse,
    InvestigationToolResult,
    RecalledMemory,
    RemediationAttempt,
    ResolveIncidentRequest,
)
from .tool_calling import ToolCallingInvestigator, ToolPlanningError


SUCCESS_MARKERS = ("successful remediation:", "successful action:", "resolved by:", "worked:")
FAILURE_MARKERS = ("failed remediation:", "failed action:", "failure:")
MEMORY_STOP_WORDS = {
    "a", "about", "after", "again", "and", "api", "at", "be", "by", "during", "for",
    "from", "in", "incident", "is", "it", "of", "on", "or", "our", "service", "the",
    "this", "to", "was", "were", "with", "checkout", "errors", "error", "returning",
}
HIGH_SIGNAL_TERMS = {"503", "429", "timeout", "timeouts", "exhaustion", "backlog", "throttle", "throttling"}


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _fact_metadata(fact: MemoryFact) -> dict[str, str]:
    metadata = getattr(fact, "metadata", None) or {}
    return {str(key): str(value) for key, value in metadata.items()}


def _service_matches(incident: IncidentRequest, fact: MemoryFact) -> bool:
    metadata = _fact_metadata(fact)
    service = metadata.get("service", "")
    text = _normalized(fact.text)
    service_text = _normalized(incident.service)
    return _normalized(service) == service_text or service_text in text


def _symptom_relevance(incident: IncidentRequest, fact: MemoryFact) -> bool:
    incident_text = " ".join([incident.symptoms, *incident.evidence])
    incident_terms = {
        token for token in re.findall(r"[a-z0-9]+", incident_text.lower())
        if token not in MEMORY_STOP_WORDS and len(token) > 2
    }
    memory_text = " ".join(
        [
            fact.text,
            *_fact_metadata(fact).values(),
        ]
    )
    memory_terms = {
        token for token in re.findall(r"[a-z0-9]+", memory_text.lower())
        if token not in MEMORY_STOP_WORDS and len(token) > 2
    }
    overlap = incident_terms & memory_terms
    return len(overlap) >= 2 or bool(overlap & HIGH_SIGNAL_TERMS)


def _labeled_lines(text: str, markers: tuple[str, ...]) -> list[str]:
    selected: list[str] = []
    for line in text.splitlines():
        normalized = line.strip().lower()
        if any(marker in normalized for marker in markers):
            selected.append(line.strip())
    return selected


class IncidentMemoryAgent:
    """Small deterministic reasoning step grounded only in current input and recalled facts."""

    def __init__(
        self,
        memory: MemoryStore,
        bank_id: str,
        tool_investigator: ToolCallingInvestigator | None = None,
    ) -> None:
        self._memory = memory
        self.bank_id = bank_id
        self._tool_investigator = tool_investigator or ToolCallingInvestigator()

    def investigate(self, incident: IncidentRequest, use_memory: bool = True) -> InvestigationResponse:
        plan = self._tool_investigator.investigate(incident)
        facts = []
        matches = []
        if use_memory:
            evidence_context = _compact_tool_evidence(plan.tool_results)
            query = (
                f"Resolved incidents for service {incident.service}: symptoms {incident.symptoms[:300]}. "
                f"Current investigation evidence: {evidence_context}. "
                f"Find previous failed and successful remediation outcomes and lessons."
            )
            facts = self._memory.recall(query)
            matches = [
                fact for fact in facts
                if _service_matches(incident, fact) and _symptom_relevance(incident, fact)
            ]
        memories = [
            RecalledMemory(
                id=str(getattr(fact, "id", "unknown")),
                text=str(fact.text),
                type=getattr(fact, "type", None),
                context=getattr(fact, "context", None),
                metadata=_fact_metadata(fact),
                rank=rank,
            )
            for rank, fact in enumerate(matches, start=1)
        ]

        successful = _unique_actions(
            _historical_action(fact, "successful", SUCCESS_MARKERS)
            for fact in matches
            if _historical_action(fact, "successful", SUCCESS_MARKERS)
        )
        failed = _unique_actions(
            _historical_action(fact, "failed", FAILURE_MARKERS)
            for fact in matches
            if _historical_action(fact, "failed", FAILURE_MARKERS)
        )
        if successful:
            failed_text = " Previous failed attempts: " + "; ".join(failed) if failed else ""
            recommendation = "Historical evidence favors " + "; ".join(successful) + ". Verify this against the current tool evidence before acting." + failed_text
            probable_cause = "A similar service incident has a recorded historical resolution; verify it against current evidence."
            confidence = "moderate"
        else:
            probable_cause, recommendation, confidence = _diagnose_current_evidence(
                incident,
                plan.tool_results,
            )

        return InvestigationResponse(
            incident=incident,
            summary=f"Investigating {incident.service}: {incident.symptoms}",
            probable_cause=probable_cause,
            recommendation=recommendation,
            confidence=confidence,
            memory_mode="with_memory" if use_memory else "without_memory",
            planner_mode=plan.planner_mode,
            tool_results=plan.tool_results,
            historical_memories=memories,
            memory_status="available" if memories else "empty",
        )

    def resolve(self, request: ResolveIncidentRequest) -> None:
        incident = request.incident
        base_id = f"shadowops-incident-{incident.incident_id}"
        common_metadata = {
            "incident_id": incident.incident_id,
            "service": incident.service,
            "environment": incident.environment,
        }
        for index, attempt in enumerate(request.remediation_attempts, start=1):
            document_id = f"{base_id}-attempt-{index:02d}"
            duration = (
                f" Recovery duration: {attempt.duration_minutes:g} minutes."
                if attempt.duration_minutes is not None
                else ""
            )
            content = (
                f"Incident {incident.incident_id} affected {incident.service}. "
                f"Symptoms: {incident.symptoms}. Remediation action: {attempt.action}. "
                f"Outcome: {attempt.outcome}. Observed result: {attempt.details}.{duration}"
            )
            self._memory.retain(
                content=content,
                document_id=document_id,
                occurred_at=request.occurred_at,
                metadata={
                    **common_metadata,
                    "record_kind": "remediation_attempt",
                    "remediation_action": attempt.action,
                    "remediation_outcome": attempt.outcome,
                    "attempt_number": str(index),
                },
                service=incident.service,
            )

        summary_content = "\n".join(
            [
                f"Incident {incident.incident_id} affected {incident.service} in {incident.environment}.",
                f"Symptoms: {incident.symptoms}.",
                f"Final root cause: {request.root_cause}.",
                f"Lesson learned: {request.lesson}.",
                "Evidence: " + "; ".join(incident.evidence) if incident.evidence else "Evidence: none recorded.",
            ]
        )
        self._memory.retain(
            content=summary_content,
            document_id=f"{base_id}-summary",
            occurred_at=request.occurred_at,
            metadata={
                **common_metadata,
                "record_kind": "incident_summary",
                "root_cause": request.root_cause,
                "lesson": request.lesson,
                "resolution_status": "resolved",
            },
            service=incident.service,
        )


def _historical_action(fact: MemoryFact, outcome: str, markers: tuple[str, ...]) -> str | None:
    metadata = _fact_metadata(fact)
    if metadata.get("remediation_outcome", "").lower() == outcome:
        return metadata.get("remediation_action") or fact.text
    if metadata.get("remediation_outcome"):
        return None
    matching_lines = _labeled_lines(fact.text, markers)
    return "; ".join(matching_lines) if matching_lines else None


def _unique_actions(actions) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for action in actions:
        normalized = _normalized(action)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(action)
    return result


def _diagnose_current_evidence(
    incident: IncidentRequest,
    tool_results: list[InvestigationToolResult],
) -> tuple[str, str, str]:
    metrics = next(
        (item.result for item in tool_results if item.name == "get_metrics" and item.result),
        {},
    )
    logs = next(
        (item.result for item in tool_results if item.name == "get_logs" and item.result),
        {},
    )
    dependencies = next(
        (item.result for item in tool_results if item.name == "get_dependency_health" and item.result),
        {},
    )
    if metrics.get("db_pool_used", 0) >= metrics.get("db_pool_capacity", 1) and metrics.get("db_waiters", 0) > 0:
        cause = "Database connection pool saturation"
        recommendation = (
            "Current metrics show the database pool at capacity with waiting requests. "
            "Inspect pool sizing and database connection limits before selecting a remediation. "
            "No matching successful remediation was returned by Hindsight."
        )
        if dependencies.get("dependencies"):
            recommendation += " Dependency health was also checked; compare the database signal with the other dependencies."
        return cause, recommendation, "moderate"
    if logs.get("entries") or metrics:
        return (
            "Current logs and metrics contain incident signals, but they do not establish a root cause.",
            "No matching successful remediation was returned by Hindsight. Compare the collected logs, metrics, deployment history, and dependency status before changing the service.",
            "low",
        )
    return (
        "Insufficient current evidence to identify a root cause.",
        "No current investigation evidence or matching successful remediation was available. Check the service and symptom details.",
        "low",
    )


def _compact_tool_evidence(tool_results: list[InvestigationToolResult]) -> str:
    summaries: list[str] = []
    for item in tool_results:
        if item.error:
            summaries.append(f"{item.name}: unavailable")
        elif item.result:
            payload = json.dumps(item.result, sort_keys=True, separators=(",", ":"))
            summaries.append(f"{item.name}: {payload[:220]}")
    return "; ".join(summaries)[:900]


def simulate_remediation(incident: IncidentRequest, action: str) -> RemediationAttempt:
    action_text = _normalized(action)
    symptom_text = _normalized(incident.symptoms)
    if incident.service == "checkout-service" and "503" in symptom_text and "pool" in symptom_text:
        if "restart" in action_text:
            return RemediationAttempt(
                action=action,
                outcome="failed",
                details="Error rate fell briefly, then 503 responses returned after four minutes.",
                duration_minutes=4,
            )
        if "pool" in action_text and any(word in action_text for word in ("increase", "raise", "scale", "expand")):
            return RemediationAttempt(
                action=action,
                outcome="successful",
                details="Database connections stabilized and checkout 503 responses stopped.",
                duration_minutes=12,
            )
    return RemediationAttempt(
        action=action,
        outcome="partial",
        details="No deterministic outcome is configured for this action and incident pattern.",
    )

