# Evaluation Method

## Purpose

Compare ShadowOps on the same incident with Hindsight recall intentionally omitted versus real Hindsight recall enabled. Both arms run fixture-backed tool investigation; only memory recall differs. Runs are persisted to SQLite and surfaced in the Evaluation view.

## Measured Fields

- Per-run elapsed time measured by the backend around investigation.
- Number of Hindsight facts returned and included in the `with_memory` result; baseline is zero by design.
- Whether returned facts contain explicit `remediation_outcome=failed` and `remediation_outcome=successful` metadata.
- Diagnosis, recommendation, planner mode, and actual tool results returned for each run.

The same request body and current service fixtures are passed to both arms. The optional Groq planner is called for each run, so planner choices/latency can vary; planner mode and selected tool evidence are included in the results. The baseline bypasses the Hindsight `recall` call, not Hindsight configuration validation or historical app records.

## Interpretation Limits

- One pair of runs is descriptive, not a benchmark and not evidence of a general performance gain.
- Hindsight recall ranking order/scores are not calibrated probabilities. ShadowOps does not display fabricated similarity percentages.
- “Facts returned” counts SDK recall result entries for that request, not unique incidents or the number of retained source documents.
- Latency includes fixture-tool planning, and the memory arm includes Hindsight network/recall latency. Network/model variability makes one-run comparisons noisy.
- The evaluation does not execute remediation or claim its recommended action caused recovery.
- The SQLite evaluation ledger is app-side state; the `with_memory` arm's returned facts come from the configured Hindsight API.

## Repeatable Use

1. Seed the dedicated demo bank.
2. Open Evaluation and leave the same incident payload fixed.
3. Run the comparison once or repeat it, retaining each measured pair.
4. Inspect both result cards and the stored run list on the page.
5. Avoid publishing generalized improvement claims unless a larger controlled evaluation is designed and run.
