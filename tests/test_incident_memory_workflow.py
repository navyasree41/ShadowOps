from dataclasses import dataclass
from datetime import datetime

from fastapi.testclient import TestClient

from backend.shadowops import main
from backend.shadowops.hindsight_memory import HindsightSettings, MemoryConfigurationError


@dataclass
class Fact:
    id: str
    text: str
    type: str = "experience"
    context: str = "resolved SRE incident"
    metadata: dict[str, str] | None = None


class FakeMemoryStore:
    """Test double only; it does not represent a live Hindsight integration."""

    def __init__(self) -> None:
        self.documents: dict[str, tuple[str, dict[str, str]]] = {}

    def recall(self, query: str) -> list[Fact]:
        return [
            Fact(
                id=document_id,
                text=content,
                metadata=metadata,
            )
            for document_id, (content, metadata) in self.documents.items()
            if metadata.get("service") == "checkout-service"
        ]

    def retain(self, *, content: str, document_id: str, occurred_at: datetime, metadata: dict[str, str], service: str) -> None:
        self.documents[document_id] = (content, metadata)


def test_incident_a_learning_changes_incident_b_recommendation(monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    store = FakeMemoryStore()
    monkeypatch.setattr(main, "configured_memory_store", lambda: (store, "test-bank"))
    with TestClient(main.app) as client:
        incident_a = {
            "incident_id": "INC-001",
            "service": "checkout-service",
            "symptoms": "HTTP 503 responses; database pool at 100 percent",
            "environment": "staging",
            "deployment_version": "checkout-2.14.3",
            "evidence": ["max_connections_waiting=42", "p95_latency_ms=8400"],
        }

        first = client.post("/api/incidents/investigate", json=incident_a)
        assert first.status_code == 200
        first_result = first.json()
        assert first_result["memory_status"] == "empty"
        assert first_result["planner_mode"] == "rules_fallback"
        assert {result["name"] for result in first_result["tool_results"]} >= {
            "get_service_health",
            "get_logs",
            "get_metrics",
            "get_dependency_health",
        }
        assert "database connection pool saturation" in first_result["probable_cause"].lower()
        assert "No matching successful remediation" in first_result["recommendation"]

        failed_attempt = client.post(
            "/api/incidents/simulate-remediation",
            json={"incident": incident_a, "action": "Restart checkout service"},
        )
        successful_attempt = client.post(
            "/api/incidents/simulate-remediation",
            json={"incident": incident_a, "action": "Increase database connection pool"},
        )
        assert failed_attempt.json()["attempt"]["outcome"] == "failed"
        assert successful_attempt.json()["attempt"]["outcome"] == "successful"

        resolved = client.post(
            "/api/incidents/resolve",
            json={
                "incident": incident_a,
                "root_cause": "Database connection pool exhaustion",
                "remediation_attempts": [
                    failed_attempt.json()["attempt"],
                    successful_attempt.json()["attempt"],
                ],
                "lesson": "A restart only masks pool exhaustion; increasing pool capacity resolved it.",
                "recovery_time_minutes": 12,
                "occurred_at": "2026-09-28T10:30:00Z",
            },
        )
        assert resolved.status_code == 200
        assert resolved.json()["retained"] is True

        incident_b = {**incident_a, "incident_id": "INC-002", "symptoms": "Checkout API again returns 503"}
        second = client.post("/api/incidents/investigate", json=incident_b)
        assert second.status_code == 200
        second_result = second.json()
        assert second_result["memory_status"] == "available"
        assert "Increase database connection pool" in second_result["recommendation"]
        assert "Restart checkout service" in second_result["recommendation"]
        assert second_result["historical_memories"][0]["id"] == "shadowops-incident-INC-001-attempt-01"


def test_missing_hindsight_configuration_returns_setup_error(monkeypatch) -> None:
    def missing_configuration():
        raise MemoryConfigurationError("Configure HINDSIGHT_API_URL and HINDSIGHT_BANK_ID.")

    monkeypatch.setattr(main, "configured_memory_store", missing_configuration)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/incidents/investigate",
            json={
                "incident_id": "INC-EMPTY",
                "service": "checkout-service",
                "symptoms": "HTTP 503 responses",
            },
        )
    assert response.status_code == 503
    assert "HINDSIGHT_API_URL" in response.json()["detail"]


def test_hindsight_cloud_requires_api_key(monkeypatch) -> None:
    monkeypatch.setenv("HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io")
    monkeypatch.setenv("HINDSIGHT_BANK_ID", "shadowops-test")
    monkeypatch.delenv("HINDSIGHT_API_KEY", raising=False)

    try:
        HindsightSettings.from_environment()
    except MemoryConfigurationError as exc:
        assert "HINDSIGHT_API_KEY" in str(exc)
    else:
        raise AssertionError("Cloud configuration without an API key must be rejected.")