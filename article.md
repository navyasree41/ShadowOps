# I Used Hindsight to Remember Failed Remediation

## 1. Introduction

The most expensive incident response mistake is often not a bad diagnosis; it is repeating a fix that already failed because the outcome was never attached to the action. A stateless assistant can summarize today’s logs, but without durable memory it cannot tell the next responder that “increase database connections” made an unrelated order-service latency problem no better.

I built ShadowOps to explore that gap. Its central engineering idea is modest: retain actions with explicit outcomes, then retrieve those outcomes alongside fresh evidence the next time a similar incident appears. Hindsight supplies the persistent memory layer. The application records an attempt as failed, partial, or successful instead of collapsing all past activity into a generic incident summary.

There is an important boundary to the implementation: the repository models services and remediation deterministically. Operators trigger investigations and confirm outcomes; the application does not execute changes against production infrastructure. That makes the memory and workflow concrete without pretending the current code is an autonomous production remediation engine.

## 2. Architecture & Overview

The application has a React and TypeScript interface, a FastAPI backend, an incident agent, a set of simulated SRE tools, SQLite for operational records, and a Hindsight bank for long-term memory. Groq function calling can select investigation tools when configured. A rules-based planner is available when it is not. Both paths call a bounded tool set: service health, logs, metrics, deployment history, and dependency health.

The order matters. The agent first inspects current evidence, then makes a Hindsight recall query using the service, symptoms, and a compact rendering of tool results. It filters returned facts by service and symptom relevance. If a matching historical success exists, the recommendation names that action and includes recorded failures where available. Otherwise, it falls back to a diagnosis based on current evidence. A past incident is evidence to compare, not proof that the current incident has the same root cause.

The [Hindsight GitHub](https://github.com/vectorize-io/hindsight) project provides the memory system used by the backend. Its [Hindsight docs](https://hindsight.vectorize.io/) describe the retain and recall interfaces. This fits the broader distinction in [Vectorize agent memory](https://vectorize.io/what-is-agent-memory): operational memory is information an agent can carry across tasks, rather than just text from its current prompt.

SQLite and Hindsight have separate jobs. SQLite drives incident lists, timelines, tool traces, evaluation runs, dashboard counts, and write receipts. Hindsight is where the backend asks for semantic historical facts. A SQLite row saying an incident was resolved is not represented as a Hindsight recall result; the UI displays recalled facts only when Hindsight returns them.

## 3. Core Technical Deep Dive: Closed-Loop Vector Retention

“RAG” is not, by itself, a remediation strategy. Retrieving a chunk that says “we increased the pool” does not tell a responder whether the action was attempted, whether it worked, or whether it was even related to the observed bottleneck. A naive incident corpus can make this worse: failed experiments and successful fixes sit beside each other as equally plausible text.

I therefore retain each remediation attempt as its own Hindsight document. The document text carries the incident, symptoms, action, outcome, observed result, and duration. Metadata carries stable fields such as `incident_id`, `service`, `remediation_action`, `remediation_outcome`, and `attempt_number`. The summary is stored separately with the root cause and lesson. Stable document IDs make a repeat retain replace the corresponding document rather than multiplying identical attempts.

That outcome metadata is important for negative memory. During recall, the agent does not need to guess from prose that an action failed. `_historical_action` first checks `remediation_outcome`; when the metadata says `failed`, the action is not returned as a successful candidate. When a successful action is available, the recommendation includes the distinct failed actions as cautionary context. This is a small but useful guard against treating “we did this” as “this fixed it.”

The loop is closed at the application workflow level: investigate, present current and historical evidence, record remediation outcomes, and retain the resolved incident. It is not yet a closed-loop controller that changes real infrastructure and verifies recovery by querying live telemetry after each change. In the current repository, service signals are fixtures and the user confirms the outcome in the UI. I consider that boundary part of the design, not something to obscure with autonomous language.

The first run against an empty or unmatched bank can return zero relevant facts. The system then has to rely on current evidence and an operator’s recorded resolution. Once retained, a later similar request can retrieve the incident’s tagged outcomes. The repository’s seeded examples make this distinction useful: an order-service incident records that increasing database connections failed because database latency was already normal, then records a rollback as successful. A subsequent investigation with similar rollout and latency evidence can retrieve the failed tuning attempt and successful rollback as separate facts. Likewise, checkout history distinguishes a restart that only buys four minutes from increasing a saturated pool.

These examples are stored histories, not benchmark claims. Retrieval can return no facts, rank facts differently, or surface an imperfect match. That is why the agent checks service and symptom relevance after recall and the UI shows provenance instead of presenting a memory as certainty.

## 4. Code Walkthrough

### Build a recall query from the current incident

In `backend/shadowops/incident_agent.py`, the agent investigates first, compresses tool results, and asks Hindsight for outcomes relevant to the current service:

```python
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
```

This is not a raw “search for the service name” query. It includes selected current evidence and asks for both failed and successful outcomes. The second-stage checks are simple lexical and metadata filters; they are not a claim of perfect incident similarity.

### What the remediation check actually does

The current `simulate_remediation` function in the same file returns a deterministic outcome for the checkout scenario. For a 503/pool incident, a restart is marked failed and a pool increase successful. The relevant branch is:

```python
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
```

This is the outcome source for the simulated workflow. It is not a post-action telemetry check: no new metrics query runs after a remediation, and no real service health is verified. The operator also has to select a status and provide notes in the frontend modal. A production implementation should replace this deterministic result with an authorized action runner plus fresh, time-bounded health checks and explicit rollback behavior.

### Retain each attempt and its outcome

When the operator resolves an incident, `IncidentMemoryAgent.resolve` writes each attempt separately. The core retain call is:

```python
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
```

The Hindsight adapter makes a synchronous write and checks the response’s success flag before treating it as confirmed:

```python
response = self._client.retain(
    bank_id=self._bank_id,
    content=content,
    context="resolved SRE incident",
    timestamp=occurred_at,
    document_id=document_id,
    metadata=metadata,
    tags=[f"service:{service}"],
    retain_async=False,
)
if not getattr(response, "success", False):
    raise MemoryServiceError("Hindsight did not confirm the incident memory write.")
```

After all attempt documents, the agent retains a summary document containing the root cause and lesson. Only then does the API save the resolution and write receipt to SQLite and return a successful response. There is no model retraining payload here: retained outcomes become future retrieval evidence; they do not update model weights.

## 5. Live Behavior & Results

With an empty bank, a first checkout investigation may show no relevant facts. The agent still inspects the fixture data: pool use is 100 of 100, 42 requests are waiting, and logs include connection acquisition timeouts. That evidence supports investigating pool saturation. It does not depend on memory being present.

The operator can then record two attempts. A restart returns a temporary drop in errors followed by recurrence after four minutes. Increasing the pool returns stable connections in the deterministic scenario. At resolution, the backend retains both attempts and a separate summary. A later query for a similar checkout incident can recall those outcomes, distinguish the failed restart from the successful pool change, and recommend checking the historical success against current evidence.

The seeded order-service history captures a different negative lesson. The database was healthy, so increasing database connections did not improve application latency; the successful action was rolling back the serialization regression. This is a useful example of why memory needs context as well as outcome labels. “Database tuning failed” is actionable only when attached to evidence that the database was not the bottleneck.

I avoid reporting a numerical accuracy or recovery-time improvement from these examples. The fixture outcomes are deterministic, but Hindsight recall depends on the configured service and returned facts. The evaluation page runs one memory-disabled and one memory-enabled investigation for the same input and records their measurements. That gives an inspectable comparison, not a statistically meaningful performance study.

## 6. Lessons Learned

1. **Store outcomes at the action level.** An incident can contain a failed workaround and a successful fix. A single final status loses the history needed to avoid repeating the failed step.
2. **Separate memory from the operational ledger.** Use a transactional database for UI state and receipts; use the memory system for cross-incident recall. Do not label a local database query as a memory recall.
3. **Make provenance visible.** Show returned text and metadata, and keep historical evidence distinct from current telemetry. Similar symptoms do not guarantee an identical root cause.
4. **Do not confuse retain with learning model weights.** This workflow improves what evidence is available in a later investigation; it does not retrain the LLM.
5. **Close the real-world loop before claiming automation.** A production remediation engine needs authorization, guarded actions, fresh post-action telemetry, timeout handling, rollback, and an auditable human override. Recording an operator-selected outcome is a useful foundation, but it is not closed-loop autonomous recovery.

The most practical use of negative memory is not to make an agent sound more certain. It is to give the next responder a durable, inspectable reason not to repeat a failed action—and enough current evidence to decide whether the old lesson applies.
