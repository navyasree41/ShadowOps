import json
import os
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ValidationError

from . import simulated_environment
from .models import IncidentRequest, InvestigationToolResult


ServiceName = Literal[
    "checkout-service",
    "payment-service",
    "order-service",
    "auth-service",
    "notification-service",
]
MAX_TOOL_ROUNDS = 4
MAX_TOOL_CALLS = 12


class ToolArguments(BaseModel):
    service: ServiceName


@dataclass(frozen=True)
class PlannedInvestigation:
    planner_mode: str
    tool_results: list[InvestigationToolResult]


class ToolPlanningError(RuntimeError):
    pass


TOOL_DEFINITIONS = [
    {"type": "function", "function": {"name": "get_service_health", "description": "Check replica readiness and service status.", "parameters": {"type": "object", "properties": {"service": {"type": "string", "enum": list(simulated_environment.SERVICES)}}, "required": ["service"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "get_logs", "description": "Read recent structured log events for a service.", "parameters": {"type": "object", "properties": {"service": {"type": "string", "enum": list(simulated_environment.SERVICES)}}, "required": ["service"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "get_metrics", "description": "Read current error, latency, resource, and queue metrics for a service.", "parameters": {"type": "object", "properties": {"service": {"type": "string", "enum": list(simulated_environment.SERVICES)}}, "required": ["service"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "get_deployment_history", "description": "Read recent deployments and changes for a service.", "parameters": {"type": "object", "properties": {"service": {"type": "string", "enum": list(simulated_environment.SERVICES)}}, "required": ["service"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "get_dependency_health", "description": "Check health and latency of service dependencies.", "parameters": {"type": "object", "properties": {"service": {"type": "string", "enum": list(simulated_environment.SERVICES)}}, "required": ["service"], "additionalProperties": False}}},
]


TOOL_HANDLERS = {
    "get_service_health": simulated_environment.service_health,
    "get_logs": simulated_environment.service_logs,
    "get_metrics": simulated_environment.service_metrics,
    "get_deployment_history": simulated_environment.deployment_history,
    "get_dependency_health": simulated_environment.dependency_health,
}


def execute_tool_call(name: str, arguments_json: str) -> InvestigationToolResult:
    try:
        handler = TOOL_HANDLERS.get(name)
        if handler is None:
            raise ValueError(f"Unknown investigation tool: {name}")
        parsed = ToolArguments.model_validate_json(arguments_json)
        result = handler(parsed.service)
        return InvestigationToolResult(name=name, arguments=parsed.model_dump(), result=result)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return InvestigationToolResult(
            name=name or "unknown",
            arguments={},
            result=None,
            error=f"Invalid tool call: {type(exc).__name__}",
        )
    except Exception as exc:
        return InvestigationToolResult(
            name=name or "unknown",
            arguments={},
            result=None,
            error=f"Tool failed: {type(exc).__name__}",
        )


def _fallback_tool_names(incident: IncidentRequest) -> list[str]:
    symptoms = incident.symptoms.lower()
    selected = ["get_service_health"]
    error_terms = ("error", "503", "5xx", "timeout", "failure", "failed", "exception")
    metric_terms = ("error", "503", "5xx", "latency", "rate", "cpu", "memory", "pool", "queue", "backlog", "spike")
    dependency_terms = ("dependency", "upstream", "timeout", "503", "5xx", "connection")
    if any(term in symptoms for term in error_terms):
        selected.append("get_logs")
    if any(term in symptoms for term in metric_terms):
        selected.append("get_metrics")
    if any(term in symptoms for term in dependency_terms):
        selected.append("get_dependency_health")
    if any(term in symptoms for term in ("deploy", "release", "version", "after rollout")):
        selected.append("get_deployment_history")
    return selected


class ToolCallingInvestigator:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("GROQ_API_KEY", "").strip() or None
        self.model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    def investigate(self, incident: IncidentRequest) -> PlannedInvestigation:
        if not self.api_key:
            results = [
                execute_tool_call(name, json.dumps({"service": incident.service}))
                for name in _fallback_tool_names(incident)
            ]
            return PlannedInvestigation(planner_mode="rules_fallback", tool_results=results)

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are an incident investigation planner. Choose only the fixture-backed tools "
                    "needed to inspect the stated service and symptoms. Use tool calls before stopping. "
                    "Do not invent tool results or recommend remediation."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(incident.model_dump(mode="json")),
            },
        ]
        results: list[InvestigationToolResult] = []
        call_count = 0
        for _ in range(MAX_TOOL_ROUNDS):
            response_message = self._request_tool_choice(messages)
            tool_calls = response_message.get("tool_calls") or []
            if not isinstance(tool_calls, list):
                raise ToolPlanningError("Groq returned an invalid tool-call collection.")
            if not tool_calls:
                break
            messages.append(response_message)
            for call in tool_calls:
                if call_count >= MAX_TOOL_CALLS:
                    break
                call_count += 1
                function = call.get("function") if isinstance(call, dict) else {}
                function = function if isinstance(function, dict) else {}
                name = str(function.get("name", ""))
                arguments = function.get("arguments", "")
                if not isinstance(arguments, str):
                    arguments = json.dumps(arguments)
                result = execute_tool_call(name, arguments)
                results.append(result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(call.get("id", f"invalid-call-{call_count}")),
                        "content": json.dumps(result.result if result.error is None else {"error": result.error}),
                    }
                )
            if call_count >= MAX_TOOL_CALLS:
                break

        if not results:
            results = [
                execute_tool_call(name, json.dumps({"service": incident.service}))
                for name in _fallback_tool_names(incident)
            ]
            return PlannedInvestigation(planner_mode="groq_with_rules_fallback", tool_results=results)
        return PlannedInvestigation(planner_mode="groq", tool_results=results)

    def _request_tool_choice(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            response = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "tools": TOOL_DEFINITIONS,
                    "tool_choice": "auto",
                    "parallel_tool_calls": False,
                    "max_tokens": 500,
                },
                timeout=20.0,
            )
            response.raise_for_status()
            payload = response.json()
            return payload["choices"][0]["message"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise ToolPlanningError(f"Groq tool planning failed: {type(exc).__name__}") from exc
