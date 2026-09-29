# ShadowOps Demo Runbook

This runbook exercises real Hindsight retain/recall against the configured Cloud bank and deterministic simulated service tools. The app reset does not delete Cloud memories; it re-retains the same stable demo document IDs.

## Prerequisites

- `.env` at the repository root with a valid Hindsight Cloud URL, bank ID, and API key.
- Groq key configured to demonstrate LLM-selected functions. Without it the rules planner is visibly labeled and still exercises the structured tools.
- Python dependencies and frontend dependencies installed as described in the root README.

## Exact Demo Steps

1. **Start backend.** In terminal 1:
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn backend.shadowops.main:app --reload --host 127.0.0.1 --port 8000
   ```
2. **Start frontend.** In terminal 2:
   ```powershell
   npm --prefix frontend run dev
   ```
3. **Configure environment.** The backend reads root `.env`; set `HINDSIGHT_API_URL=https://api.hindsight.vectorize.io`, `HINDSIGHT_BANK_ID`, `HINDSIGHT_API_KEY`, and optionally `GROQ_API_KEY`/`GROQ_MODEL`. Keep secrets out of screen recordings.
4. **Seed Hindsight.** Open `http://127.0.0.1:5173`, select **Memory**, and choose **Seed 10 incidents**. Wait for success. This calls real synchronous retain operations and reports the selected bank ID. Confirm the resulting lesson records and confirmed write count.
5. **Open the demo incident.** Choose **Incidents**. The default incident is checkout-service with 503s and database pool saturation. Keep service as checkout-service; describe the signal as `Checkout API returning 503 errors; database pool is full`.
6. **Trigger investigation.** Click **Run investigation**. Show selected tool names and structured health/log/metric/deployment/dependency evidence. Show Hindsight facts in the adjacent memory panel. Facts carry source incident metadata; the recall score is not displayed as a probability.
7. **Show a failed remediation.** Keep or enter `Restart checkout service`, then choose **Run action**. The deterministic simulator records temporary recovery followed by recurrence as failed.
8. **Show a successful remediation.** Enter `Increase database connection pool` and run it. The simulator records stable recovery. Set the confirmed root cause and lesson fields to match the observed outcomes.
9. **Resolve and retain.** Choose **Resolve and retain outcome**. Wait for the successful Hindsight confirmation. This retains separate action documents plus the lesson summary and persists local incident state/write receipt.
10. **Trigger a similar incident.** Change the incident ID, keep checkout-service, and describe 503s/pool pressure again. Run investigation. Show a new real recall request returning the previous failed restart and successful pool adjustment, and point to the recommendation informed by these facts.
11. **Show learning views.** Open **Timeline** to show recorded attempts; **Memory** for confirmed writes and returned facts; **System health** for fixture signals; and **Evaluation** to compare identical memory-disabled and Hindsight-enabled runs.
12. **Reset/reseed if required.** Choose **Reset demo** from Overview or Memory. This clears only local SQLite state and reseeds the ten stable demo documents in Hindsight. It intentionally does not clear the bank or unrelated team data.

## Determinism and Limitations

- Simulated service signals and the checkout restart/pool outcomes are deterministic.
- Groq tool choice is model-driven and may vary; use the visibly labeled rules fallback when a deterministic tool plan is needed.
- Hindsight retrieval and extraction are real service operations and may vary with model/version/ranking. The runbook does not fake a returned memory.
- The seeded corpus contains ten resolved incidents spanning multiple failure families. The UI shows actual app-recorded interaction/evaluation data, not a fabricated 1/5/10/20 learning progression.
- If Hindsight is unreachable, unauthorized, or misconfigured, the UI surfaces the API error and no memory result is fabricated.
- Before recording, close notifications/unrelated windows and enlarge terminal/editor font. The content-guide video should be a 2–5 minute 1080p screen recording with voiceover, showing the problem, real memory retrieval, resolution, and one takeaway.
