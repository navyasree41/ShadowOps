import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import IncidentRequest, InvestigationResponse, RemediationAttempt, ResolveIncidentRequest


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IncidentRepository:
    def __init__(self, database_path: str | None = None) -> None:
        self.database_path = database_path or os.getenv("SHADOWOPS_DB_PATH", "data/shadowops.sqlite3")
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    service TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    investigation_json TEXT,
                    resolution_json TEXT
                );
                CREATE TABLE IF NOT EXISTS investigation_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    duration_ms REAL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS remediation_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
                    action TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    details TEXT NOT NULL,
                    duration_minutes REAL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hindsight_write_receipts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL REFERENCES incidents(incident_id) ON DELETE CASCADE,
                    bank_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    UNIQUE(bank_id, document_id)
                );
                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_incidents_updated ON incidents(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_attempts_outcome ON remediation_attempts(outcome);
                """
            )

    def save_investigation(
        self,
        incident: IncidentRequest,
        result: InvestigationResponse,
        latency_ms: float,
    ) -> None:
        timestamp = _now()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO incidents (incident_id, service, environment, status, created_at, updated_at, request_json, investigation_json)
                   VALUES (?, ?, ?, 'investigating', ?, ?, ?, ?)
                   ON CONFLICT(incident_id) DO UPDATE SET service=excluded.service, environment=excluded.environment,
                   status='investigating', updated_at=excluded.updated_at, request_json=excluded.request_json,
                   investigation_json=excluded.investigation_json""",
                (incident.incident_id, incident.service, incident.environment, timestamp, timestamp,
                 incident.model_dump_json(), result.model_dump_json()),
            )
            connection.execute("DELETE FROM investigation_actions WHERE incident_id=?", (incident.incident_id,))
            connection.executemany(
                """INSERT INTO investigation_actions (incident_id, tool_name, arguments_json, result_json, error, duration_ms, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (incident.incident_id, tool.name, json.dumps(tool.arguments),
                     json.dumps(tool.result) if tool.result is not None else None, tool.error,
                     latency_ms / max(1, len(result.tool_results)), timestamp)
                    for tool in result.tool_results
                ],
            )

    def save_remediation(self, incident: IncidentRequest, attempt: RemediationAttempt) -> None:
        timestamp = _now()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO incidents (incident_id, service, environment, status, created_at, updated_at, request_json)
                   VALUES (?, ?, ?, 'investigating', ?, ?, ?)
                   ON CONFLICT(incident_id) DO UPDATE SET updated_at=excluded.updated_at""",
                (incident.incident_id, incident.service, incident.environment, timestamp, timestamp, incident.model_dump_json()),
            )
            connection.execute(
                """INSERT INTO remediation_attempts (incident_id, action, outcome, details, duration_minutes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (incident.incident_id, attempt.action, attempt.outcome, attempt.details, attempt.duration_minutes, timestamp),
            )

    def save_resolution(self, request: ResolveIncidentRequest, bank_id: str, document_id: str) -> None:
        incident = request.incident
        timestamp = _now()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO incidents (incident_id, service, environment, status, created_at, updated_at, request_json, resolution_json)
                   VALUES (?, ?, ?, 'resolved', ?, ?, ?, ?)
                   ON CONFLICT(incident_id) DO UPDATE SET status='resolved', updated_at=excluded.updated_at,
                   request_json=excluded.request_json, resolution_json=excluded.resolution_json""",
                (incident.incident_id, incident.service, incident.environment, timestamp, timestamp,
                 incident.model_dump_json(), request.model_dump_json()),
            )
            connection.execute("DELETE FROM remediation_attempts WHERE incident_id=?", (incident.incident_id,))
            for attempt in request.remediation_attempts:
                connection.execute(
                    """INSERT INTO remediation_attempts (incident_id, action, outcome, details, duration_minutes, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (incident.incident_id, attempt.action, attempt.outcome, attempt.details, attempt.duration_minutes, timestamp),
                )
            connection.execute(
                """INSERT OR IGNORE INTO hindsight_write_receipts (incident_id, bank_id, document_id, completed_at)
                   VALUES (?, ?, ?, ?)""",
                (incident.incident_id, bank_id, document_id, timestamp),
            )

    def record_evaluation(self, run_id: str, incident_id: str, mode: str, latency_ms: float, result: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO evaluation_runs (id, incident_id, mode, latency_ms, result_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, incident_id, mode, latency_ms, json.dumps(result), _now()),
            )

    def update_incident_status(self, incident_id: str, status: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE incidents SET status=?, updated_at=? WHERE incident_id=?",
                (status, _now(), incident_id),
            )

    def dashboard(self) -> dict[str, Any]:
        with self._connect() as connection:
            incident_counts = connection.execute(
                "SELECT COUNT(*) AS total, SUM(CASE WHEN status != 'resolved' THEN 1 ELSE 0 END) AS active FROM incidents"
            ).fetchone()
            outcome_counts = connection.execute(
                "SELECT outcome, COUNT(*) AS count FROM remediation_attempts GROUP BY outcome"
            ).fetchall()
            receipt_count = connection.execute("SELECT COUNT(DISTINCT incident_id) AS count FROM hindsight_write_receipts").fetchone()
            incidents = connection.execute(
                "SELECT incident_id, service, environment, status, created_at, updated_at, request_json, investigation_json, resolution_json FROM incidents ORDER BY updated_at DESC LIMIT 100"
            ).fetchall()
            attempts = connection.execute(
                "SELECT incident_id, action, outcome, details, duration_minutes, created_at FROM remediation_attempts ORDER BY id DESC LIMIT 200"
            ).fetchall()
            investigations = connection.execute(
                "SELECT incident_id, tool_name, arguments_json, result_json, error, duration_ms, created_at FROM investigation_actions ORDER BY id DESC LIMIT 200"
            ).fetchall()
            evaluations = connection.execute(
                "SELECT id, incident_id, mode, latency_ms, result_json, created_at FROM evaluation_runs ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
        outcomes = {row["outcome"]: row["count"] for row in outcome_counts}
        return {
            "incident_total": incident_counts["total"] or 0,
            "active_incidents": incident_counts["active"] or 0,
            "remembered_incidents": receipt_count["count"] or 0,
            "remediation_counts": {key: outcomes.get(key, 0) for key in ("failed", "partial", "successful")},
            "incidents": [
                {
                    "incident_id": row["incident_id"], "service": row["service"], "environment": row["environment"],
                    "status": row["status"], "created_at": row["created_at"], "updated_at": row["updated_at"],
                    "request": json.loads(row["request_json"]),
                    "investigation": json.loads(row["investigation_json"]) if row["investigation_json"] else None,
                    "resolution": json.loads(row["resolution_json"]) if row["resolution_json"] else None,
                }
                for row in incidents
            ],
            "remediation_attempts": [dict(row) for row in attempts],
            "investigation_actions": [
                {**dict(row), "arguments": json.loads(row["arguments_json"]), "result": json.loads(row["result_json"]) if row["result_json"] else None}
                for row in investigations
            ],
            "evaluation_runs": [
                {**dict(row), "result": json.loads(row["result_json"])} for row in evaluations
            ],
        }

    def reset_app_data(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM evaluation_runs")
            connection.execute("DELETE FROM hindsight_write_receipts")
            connection.execute("DELETE FROM investigation_actions")
            connection.execute("DELETE FROM remediation_attempts")
            connection.execute("DELETE FROM incidents")

    def list_incidents(self) -> list[dict[str, Any]]:
        return self.dashboard()["incidents"]
