from dataclasses import dataclass
from datetime import datetime

from fastapi.testclient import TestClient

from backend.shadowops import main
from backend.shadowops.repository import IncidentRepository


@dataclass
class Fact:
    id: str
    text: str
    type: str = "experience"
    context: str = "resolved SRE incident"
    metadata: dict[str, str] | None = None


class FakeMemoryStore:
    """Test-only memory double; only the live Cloud test verifies Hindsight persistence."""

    def __init__(self) -> None:
        self.documents: dict[str, tuple[str, dict[str, str]]] = {}
        self.recall_calls = 0

    def retain(self, *, content: str, document_id: str, occurred_at: datetime, metadata: dict[str, str], service: str) -> None:
        self.documents[document_id] = (content, metadata)

    def recall(self, query: str) -> list[Fact]:
        self.recall_calls += 1
        return [
            Fact(document_id, content, metadata=metadata)
            for document_id, (content, metadata) in self.documents.items()
            if metadata.get("service") == "checkout-service"
        ]


def test_demo_seed_evaluation_and_reset_are_derived_and_repeatable(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    memory = FakeMemoryStore()
    repository = IncidentRepository(str(tmp_path / "shadowops.sqlite3"))
    monkeypatch.setattr(main, "repository", repository)
    monkeypatch.setattr(main, "configured_memory_store", lambda: (memory, "test-bank"))

    with TestClient(main.app) as client:
        seeded = client.post("/api/demo/seed")
        assert seeded.status_code == 200
        assert seeded.json()["seeded_incidents"] == 10
        assert client.get("/api/dashboard").json()["remembered_incidents"] == 10

        evaluation = client.post(
            "/api/evaluation/run",
            json={"incident": {
                "incident_id": "EVAL-CHECKOUT-1",
                "service": "checkout-service",
                "symptoms": "Checkout API returning 503; database pool is full",
            }},
        )
        assert evaluation.status_code == 200
        runs = evaluation.json()["runs"]
        assert [run["mode"] for run in runs] == ["without_memory", "with_memory"]
        assert runs[0]["relevant_memories_returned"] == 0
        assert runs[1]["relevant_memories_returned"] > 0
        assert memory.recall_calls == 1
        assert len(client.get("/api/dashboard").json()["evaluation_runs"]) == 2

        reset = client.post("/api/demo/reset")
        assert reset.status_code == 200
        dashboard = client.get("/api/dashboard").json()
        assert dashboard["remembered_incidents"] == 10
        assert dashboard["evaluation_runs"] == []
        assert len(memory.documents) == 30


def test_dashboard_counts_resolution_attempts_once(monkeypatch, tmp_path) -> None:
    memory = FakeMemoryStore()
    repository = IncidentRepository(str(tmp_path / "counts.sqlite3"))
    monkeypatch.setattr(main, "repository", repository)
    monkeypatch.setattr(main, "configured_memory_store", lambda: (memory, "test-bank"))

    incident = {
        "incident_id": "COUNT-001",
        "service": "checkout-service",
        "symptoms": "503 and database pool full",
    }
    with TestClient(main.app) as client:
        simulated = client.post(
            "/api/incidents/simulate-remediation",
            json={"incident": incident, "action": "Restart checkout service"},
        )
        assert simulated.status_code == 200
        response = client.post(
            "/api/incidents/resolve",
            json={
                "incident": incident,
                "root_cause": "Pool exhaustion",
                "remediation_attempts": [simulated.json()["attempt"]],
                "lesson": "Restarting did not resolve the pool issue.",
            },
        )
        assert response.status_code == 200
        dashboard = client.get("/api/dashboard").json()
        assert dashboard["remediation_counts"]["failed"] == 1
        assert dashboard["remembered_incidents"] == 1
