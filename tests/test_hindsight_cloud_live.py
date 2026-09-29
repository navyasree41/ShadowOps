import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.shadowops import main
from backend.shadowops.hindsight_memory import (
    HINDSIGHT_CLOUD_API_URL,
    HindsightSettings,
    configured_memory_store,
)


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_HINDSIGHT_CLOUD_E2E") != "1",
    reason="Set RUN_HINDSIGHT_CLOUD_E2E=1 to run against the real Hindsight Cloud API.",
)


@pytest.fixture
def live_client():
    with TestClient(main.app) as client:
        yield client


def test_hindsight_cloud_incident_memory_lifecycle(live_client: TestClient) -> None:
    settings = HindsightSettings.from_environment()
    assert settings.api_url.rstrip("/") == HINDSIGHT_CLOUD_API_URL
    assert settings.api_key, "HINDSIGHT_API_KEY must be configured for Cloud."

    run_id = uuid4().hex
    historical_id = f"CLOUD-E2E-{run_id}-A"
    current_id = f"CLOUD-E2E-{run_id}-B"
    historical_lesson = f"For Cloud validation {run_id}, expanding the checkout database pool resolved saturation."
    new_lesson = f"Cloud validation {run_id}: hold checkout pool at 180 connections after verifying sustained recovery."
    client = live_client

    historical = {
        "incident_id": historical_id,
        "service": "checkout-service",
        "symptoms": f"HTTP 503 with database pool exhaustion; validation marker {run_id}",
        "environment": "staging",
        "deployment_version": "checkout-cloud-test-1",
        "evidence": ["pool_waiters=37", "checkout_503_rate=0.82"],
    }
    stored_history = client.post(
        "/api/incidents/resolve",
        json={
            "incident": historical,
            "root_cause": "Database connection pool exhaustion",
            "remediation_attempts": [
                {
                    "action": "Restart checkout-service",
                    "outcome": "failed",
                    "details": "503 responses returned after four minutes.",
                    "duration_minutes": 4,
                },
                {
                    "action": "Expand checkout database pool",
                    "outcome": "successful",
                    "details": "Pool waiters cleared and 503 responses stopped.",
                    "duration_minutes": 11,
                },
            ],
            "lesson": historical_lesson,
            "recovery_time_minutes": 11,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert stored_history.status_code == 200, stored_history.text
    assert stored_history.json()["retained"] is True

    current = {
        **historical,
        "incident_id": current_id,
        "symptoms": f"Checkout 503 rate rising; pool waiters elevated; marker {run_id}",
        "deployment_version": "checkout-cloud-test-2",
    }
    investigation = client.post("/api/incidents/investigate", json=current)
    assert investigation.status_code == 200, investigation.text
    investigation_data = investigation.json()
    recalled_history = investigation_data["historical_memories"]
    relevant_fact_text = " ".join(memory["text"].lower() for memory in recalled_history)
    assert recalled_history, "The live Hindsight recall must return historical facts."
    assert "503" in relevant_fact_text and ("pool" in relevant_fact_text or "database" in relevant_fact_text), (
        "Returned Hindsight facts must contain relevant checkout 503/database-pool history."
    )
    assert "Expand checkout database pool" in investigation_data["recommendation"]
    assert "Restart checkout-service" in investigation_data["recommendation"]

    stored_outcome = client.post(
        "/api/incidents/resolve",
        json={
            "incident": current,
            "root_cause": "Recurring database connection pool saturation",
            "remediation_attempts": [
                {
                    "action": "Hold checkout pool at 180 connections",
                    "outcome": "successful",
                    "details": "Sustained recovery verified against the simulated health check.",
                    "duration_minutes": 9,
                }
            ],
            "lesson": new_lesson,
            "recovery_time_minutes": 9,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert stored_outcome.status_code == 200, stored_outcome.text
    assert stored_outcome.json()["retained"] is True

    memory, bank_id = configured_memory_store()
    new_lesson_facts = memory.recall(
        f"{current_id} {new_lesson} checkout service incident lesson"
    )
    recalled_lesson = [
        fact
        for fact in new_lesson_facts
        if (getattr(fact, "metadata", None) or {}).get("incident_id") == current_id
        and (getattr(fact, "metadata", None) or {}).get("record_kind") == "incident_summary"
    ]
    assert recalled_lesson, f"The new incident summary was not recalled from Cloud bank {bank_id}."
    assert any((getattr(fact, "metadata", None) or {}).get("lesson") == new_lesson for fact in recalled_lesson)