import json

from backend.shadowops.models import IncidentRequest
from backend.shadowops.incident_agent import _symptom_relevance
from backend.shadowops.tool_calling import ToolCallingInvestigator, execute_tool_call


class StubGroqPlanner(ToolCallingInvestigator):
    def __init__(self, replies: list[dict[str, object]]) -> None:
        super().__init__(api_key="test-only")
        self._replies = iter(replies)

    def _request_tool_choice(self, messages: list[dict[str, object]]) -> dict[str, object]:
        return next(self._replies)


def test_rules_planner_selects_relevant_tools_and_returns_fixture_evidence(monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    incident = IncidentRequest(
        incident_id="INC-TOOL-1",
        service="checkout-service",
        symptoms="Checkout API returning 503; database pool is full",
    )

    plan = ToolCallingInvestigator().investigate(incident)
    names = {result.name for result in plan.tool_results}

    assert plan.planner_mode == "rules_fallback"
    assert {"get_service_health", "get_logs", "get_metrics", "get_dependency_health"} <= names
    assert "get_deployment_history" not in names
    metric_result = next(result.result for result in plan.tool_results if result.name == "get_metrics")
    assert metric_result["db_pool_used"] == metric_result["db_pool_capacity"]
    assert metric_result["db_waiters"] == 42


def test_malformed_and_unknown_tool_calls_return_structured_errors() -> None:
    malformed = execute_tool_call("get_metrics", "{not valid json")
    unknown = execute_tool_call("get_magic_metrics", json.dumps({"service": "checkout-service"}))

    assert malformed.error is not None
    assert malformed.result is None
    assert unknown.error == "Invalid tool call: ValueError"


def test_groq_tool_call_loop_handles_bad_arguments_and_executes_valid_call() -> None:
    planner = StubGroqPlanner(
        [
            {
                "role": "assistant",
                "tool_calls": [
                    {"id": "bad-1", "function": {"name": "get_metrics", "arguments": "{broken"}},
                    {"id": "good-1", "function": {"name": "get_service_health", "arguments": "{\"service\":\"checkout-service\"}"}},
                ],
            },
            {"role": "assistant", "content": "Investigation complete.", "tool_calls": []},
        ]
    )
    incident = IncidentRequest(
        incident_id="INC-GROQ-1",
        service="checkout-service",
        symptoms="503 errors",
    )

    plan = planner.investigate(incident)

    assert plan.planner_mode == "groq"
    assert len(plan.tool_results) == 2
    assert plan.tool_results[0].error is not None
    assert plan.tool_results[1].result == {
        "service": "checkout-service",
        "status": "degraded",
        "replicas_ready": 3,
        "replicas_total": 3,
        "uptime_percent": 99.2,
    }


def test_same_service_but_unrelated_dependency_memory_is_not_relevant() -> None:
    incident = IncidentRequest(
        incident_id="INC-RELEVANCE-1",
        service="checkout-service",
        symptoms="Checkout API returning HTTP 503; database connection pool is exhausted",
    )
    redis_memory = type("Memory", (), {
        "text": "Checkout requests timed out while Redis failover left stale cache connections.",
        "metadata": {"service": "checkout-service", "remediation_action": "Refresh Redis client connections"},
    })()
    pool_memory = type("Memory", (), {
        "text": "Checkout service returned HTTP 503 because the database connection pool was exhausted.",
        "metadata": {"service": "checkout-service", "remediation_action": "Expand database pool"},
    })()

    assert not _symptom_relevance(incident, redis_memory)
    assert _symptom_relevance(incident, pool_memory)
