# Hindsight Architecture for ShadowOps

Status: Implemented and verified against the configured Hindsight Cloud API on 2026-09-29. The application uses `hindsight-client` and request-scoped synchronous client cleanup; the Cloud end-to-end test asserts real returned incident metadata and lesson facts. Re-check SDK/API behavior when upgrading dependencies.

## Role in ShadowOps

Hindsight is the persistent organizational memory for resolved incidents. It is not the incident database, a transcript cache, or a decorative “memory found” label. ShadowOps writes evidence-rich incident outcomes to Hindsight and uses actual recalled facts to influence later investigations and recommendations. A later incident must be able to show the retrieved memory text and source metadata before it claims historical learning.

The app's Groq/tool-calling agent remains responsible for investigating current simulated systems and generating the current incident report. Hindsight's `recall` returns facts to that agent. Hindsight `reflect` is a documented optional reasoning operation, not required for the first vertical slice; use it only if it improves the evidence-backed workflow and its citations are shown.

## Verified Official Interface

Official pages reviewed:

- [Python client](https://hindsight.vectorize.io/sdks/python)
- [Quick start](https://hindsight.vectorize.io/developer/api/quickstart)
- [Retain API](https://hindsight.vectorize.io/developer/api/retain)
- [Recall API](https://hindsight.vectorize.io/developer/api/recall)
- [Memory banks](https://hindsight.vectorize.io/developer/api/memory-banks)
- [Installation and Windows setup](https://hindsight.vectorize.io/developer/installation)
- [Reflect guide](https://hindsight.vectorize.io/developer/reflect)
- [Memory Defense](https://hindsight.vectorize.io/developer/memory-defense)

Documented Python pattern:

```python
from hindsight_client import Hindsight

client = Hindsight(base_url="http://localhost:8888", api_key="...")
client.retain(bank_id="shadowops-demo", content="...", context="resolved incident")
response = client.recall(bank_id="shadowops-demo", query="...")
for memory in response.results:
    print(memory.text, memory.type, memory.metadata)
```

The documented client package is `hindsight-client`. The client supports a `base_url`, timeout, and optional bearer `api_key`; Hindsight Cloud's official API base URL is `https://api.hindsight.vectorize.io` and Cloud access requires an API key. The local API commonly runs on `http://localhost:8888`, where the key can be omitted if the local service has no auth configured. A bank is created automatically by its first write; reads of a nonexistent bank return 404. The Cloud API key is obtained from the Hindsight Cloud account/control plane; never place it in source, command arguments, or frontend configuration.

ShadowOps backend configuration is deliberately explicit: `HINDSIGHT_API_URL` (Cloud URL above), `HINDSIGHT_API_KEY` (Cloud bearer key), and `HINDSIGHT_BANK_ID` (dedicated bank, e.g. `shadowops-demo`). The opt-in test flag `RUN_HINDSIGHT_CLOUD_E2E=1` enables the live integration test; it is not a Hindsight credential. `.env.example` contains names and non-secret defaults only; actual credentials belong only in ignored `.env`.

`retain` accepts content, context, timestamp, metadata, tags, and caller-supplied `document_id`. Reusing a `document_id` replaces the prior document by default and prevents duplicate incident memories on safe repeat submissions. Synchronous retain returns a completion response; async retain returns an operation ID and requires status polling. For the judge demo, use synchronous writes where feasible and do not call a write “remembered” until it completed successfully.

`recall` takes a natural-language query and returns structured facts in `response.results`, including fact ID, text, type (`world`, `experience`, `observation`), context, metadata, tags, entities, timestamps, document/chunk IDs, and ranking scores where enabled. Retrieval runs semantic, keyword, graph, and temporal strategies, then fuses/reranks. Ranking scores are relative to a query and must not be displayed as calibrated percentages.

Hindsight requires an LLM provider for fact extraction, entity resolution, and related memory operations. Keep this server-side configuration distinct from ShadowOps's own agent model configuration. A configured Hindsight server may use Groq or another supported provider; the application LLM can be independently configured. Hindsight Cloud or a locally running Hindsight service are acceptable. With local Windows development, the official installation guide documents native Windows support and Docker options.

## Memory Bank and Scoping

- Use one dedicated team/organization bank for shared operational knowledge, e.g. `shadowops-demo` in local/demo configuration. Do not create one bank per chat or incident; the point is to connect incidents over time.
- Configure a bank mission so extraction focuses on service symptoms, alerts, evidence, hypotheses, attempted remediations, outcomes, root cause, recovery, recurrence, and lessons.
- Configure the observations mission, if supported/enabled, to synthesize recurring incident patterns without erasing contradictory or newer evidence.
- Use stable metadata and tags to support provenance and querying. Candidate tags: `service:checkout-service`, `environment:staging`, `incident:INC-001`; candidate metadata: `incident_id`, `service`, `environment`, `deployment_version`, `root_cause`, `resolution_status`, and app-owned `document_id`.
- Do not assume metadata is a server-side recall filter. The current Recall API docs describe tag filtering; use query text and documented tags for Hindsight scoping, then enrich/validate against the application incident record.
- Avoid service/team isolation mistakes: recall tags have documented inclusion behavior and untagged memories may still be included in some modes. Choose a consistent organization-bank policy, explicit matching mode, and test it.

## What ShadowOps Retains

On incident resolution, construct a compact, chronological, readable incident-learning narrative from validated application records. Include:

- stable incident ID, timestamp/time window, service, environment, deployment version;
- symptoms, alerts, representative log evidence, metrics, and dependency/service health;
- hypotheses and investigation actions, with the evidence each action returned;
- every remediation attempt and explicit outcome (`failed`, `partial`, or `successful`), including duration of any temporary recovery;
- final root cause, successful remediation, recovery time, recurrence status, lesson, and confidence/source evidence.

The narrative should clearly label failed and successful attempts. Do not flatten them into an ambiguous list. Include real simulated observations, not fabricated claims. Treat LLM-generated hypotheses as hypotheses until the simulated environment produces outcome evidence.

Each remediation attempt is retained as its own document with a deterministic ID, timestamp, context, and structured metadata (`incident_id`, `service`, `remediation_action`, `remediation_outcome`, and attempt number). A separate deterministic incident-summary document carries the root cause and lesson. This lets the application classify attempts from metadata returned with actual recalled Hindsight facts even if fact extraction paraphrases the prose. Stable IDs make retries idempotent. Verify every synchronous retain completion response; return success only after all attempt and summary writes succeed.

## Recall and Decision Path

1. The user submits a new incident; create its app-owned incident record.
2. The agent calls investigation tools selectively for logs, metrics, deployment history, service health, and dependency health.
3. Once it has the current symptom/evidence summary, call Hindsight recall with a query that includes service, symptoms, key terms/status codes, and deployment context. Use a bounded token budget; consider raw experiences and observations where available.
4. Preserve actual returned memory facts, IDs, metadata, and timing in the investigation trace. Empty results are a legitimate empty-memory outcome, not a reason to fabricate one.
5. Give retrieved facts and current tool outputs to the configured agent model. Require the recommendation to distinguish current evidence from historical evidence and report failed versus successful prior actions separately.
6. Show in the UI which Hindsight facts were returned and how they affected the proposed next step. Do not call a recalled memory a confirmed root cause for the new incident.
7. After remediation is simulated and its outcome is recorded, retain the updated incident learning. A future incident should retrieve it through a real recall call.

The intentionally memory-free evaluation arm omits the recall step by design while keeping the same current incident, simulated tools, model configuration, and task instructions. This is distinct from missing Hindsight credentials/service: configuration failure must be explicit and must not silently downgrade the normal “with memory” workflow.

## Reset, Seeding, and Data Integrity

- Keep demo incidents in a dedicated bank and use stable per-incident `document_id`s so seeding can safely rerun without duplicate memories.
- The reset action must use documented Hindsight operations to clear/recreate the dedicated demo bank or replace only the demo's known documents; it must not delete unrelated team memory. Select and test the exact official SDK operation before coding.
- Reset local app state and Hindsight demo memory together, then make a real recall probe to verify the expected empty/reseeded state.
- Historical-result cards may be rendered only from facts returned by Hindsight. A write receipt or app database row is not itself proof that recall returned a memory.
- If Hindsight is missing, unreachable, unauthorized, or returns an error, show a setup/service state and preserve the incident trace. Do not present local seed data as Hindsight memory.

## Application Metrics vs Hindsight Memory

Hindsight is not the transactional source for dashboard counters and remediation workflow state. Store incidents, tool outputs, remediation attempts/outcomes, timestamps, evaluation runs, and successful Hindsight write receipts in an application database (planned: SQLite for local demo). Calculate operational totals and timeline from those actual records. A “remembered incident” count should count distinct incident write receipts whose synchronous Hindsight retain completed successfully, and should be labeled as app-tracked successful writes. A “recalled memory” should count facts actually returned by a recall response for that request. Failed/successful remediation totals come from recorded outcomes, not inferred from the model's prose.

Do not infer Hindsight bank totals from seeded fixture counts. Where UI requires Hindsight fact counts, query a documented Hindsight listing/stats endpoint and clearly label the exact unit counted; validate behavior against the selected version. Do not claim that one retain produces exactly one fact.

## Credentials, Privacy, and Reliability

- Configure Hindsight API URL/key and Hindsight server's own model-provider key outside source control; keep all access on the backend. The browser receives neither secret.
- Add placeholders only to `.env.example`; ignore `.env` and local database files. Never log credentials or full authorization headers.
- Incident logs may contain tokens, customer identifiers, or internal hostnames. Strip/avoid real secrets and use realistic synthetic data. Consider enabling Hindsight's documented per-bank Memory Defense sensitive-data redaction; it is opt-in and does not retroactively scrub existing memories, so it is not a substitute for input sanitization.
- Set timeouts and handle network, auth, missing-bank, LLM extraction, and malformed response errors. Keep request/incident IDs and call duration in logs without secrets.
- For async retain, track the operation until completed before showing successful retention. Avoid duplicate operations on retries; use stable IDs/idempotence as supported.

## Why Hindsight Is Essential

The key improvement is cumulative, evidence-backed learning: a new incident can retrieve what previously happened, distinguish a temporary restart from a durable pool-size fix, and adjust the recommendation based on the historical outcome. A plain relational DB can keep the incident ledger and UI state, but it does not provide the semantic, keyword, entity/graph, temporal recall and evolving cross-incident memory used in the agent's reasoning. Replacing Hindsight with local JSON, a chat transcript, or only vector search would remove the required memory mechanism and invalidate the central product behavior.
