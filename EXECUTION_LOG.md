# Execution Log — FactMesh Pipeline

Tracking minute-to-minute details of the execution process for the FactMesh Pipeline.

## 2026-09-08 01:03
- **Action**: Committed all codebase files for Phases 1-9 to Git.
- **Details**: `git add . && git commit -m "feat: complete phases 1 to 9 (backend and frontend scaffold)"` was executed successfully. 63 files changed, 10523 insertions.
- **Action**: Updated `task.md` to check off completed items from Phase 1 through 9.
- **Action**: Verified Docker Desktop status, found it unresponsive. Sent automated restart instructions.

## 2026-09-08 01:16
- **Action**: Received screenshot from user showing WSL timeout issue within Docker Desktop.
- **Details**: Executed `wsl --shutdown` via PowerShell to forcefully kill the frozen Windows Subsystem for Linux backend. Advised user to click "Restart" on the Docker dialog.

## 2026-09-08 01:46
- **Action**: User confirmed Docker Engine is fully running.
- **Action**: Initiated `docker compose up -d` to spin up PostgreSQL container with pgvector extension.
- **Status**: Waiting for PostgreSQL initialization to complete.

## 2026-09-08 01:49
- **Action**: Container `factmesh-db` started successfully.
- **Action**: Ran `reset_db.py` to initialize PostgreSQL and create all init.sql schemas.
- **Action**: Initiated Phase 10 End-to-End run by launching seed_and_run_demo.py in the background.
- **Status**: Currently ingesting the 6 starter PDFs, extracting facts using Claude, generating embeddings, and mapping cross-document relationships.

## 2026-09-08 01:51
- **Action**: End-to-end ingestion completed with 511 issues and 0 facts extracted.
- **Error**: Found Anthropic API authentication error "Could not resolve authentication method."
- **Status**: The pipeline requires an ANTHROPIC_API_KEY to run the extraction engine (Claude). Pausing to request key from the user.

## 2026-09-08 18:28
- **Action**: User provided GitHub username (PrathamMittal07) and Gemini API key.
- **Warning**: Gemini API key format incorrect (starts with 'AQ.' instead of 'AIza'). Flagged to user, awaiting correct key.
- **Action**: Added GitHub remote: https://github.com/PrathamMittal07/FACTMESH.git

## 2026-09-08 18:29
- **Action**: Full scan of all source files for any Claude/Anthropic references.
- **Found**: 8 references across pipeline.py, matcher.py, architecture.md, README.md.

## 2026-09-08 18:30
- **Action**: Fixed all Claude/Anthropic references:
  - pipeline.py comments updated to reference Gemini
  - matcher.py docstring updated
  - architecture.md fully updated (Claude -> Gemini, Anthropic -> Google)
  - README.md completely rewritten with correct Gemini setup

## 2026-09-08 18:35
- **Final verification scan**: Zero Claude/Anthropic references in any source file.
- **Commits made**:
  - 4ecf4e5: chore: remove all remaining Claude/Anthropic references from source and docs
  - 0093ee2: feat: migrate LLM from Anthropic Claude to Google Gemini 2.0 Flash
  - c1997a1: feat: complete phases 1 to 9 (backend and frontend scaffold)
- **Status**: Awaiting correct Gemini API key (AIza...) before pushing to GitHub and running ingestion.

## 2026-09-08 19:55 — Session handoff to OpenCode, full audit
- **Verified**: `git log` shows 4 commits; `origin` remote set to `https://github.com/PrathamMittal07/FACTMESH.git`; local `master` is in sync with `origin/master` (already pushed).
- **Verified**: Docker container `factmesh-db` (pgvector/pg16) healthy, up 18h.
- **Verified**: `backend/.env` exists with GEMINI_API_KEY (AQ.-prefix), GEMINI_MODEL=gemini-3.6-flash, DB URL, thresholds.
- **Verified**: Zero Claude/Anthropic references in the codebase (grep clean).
- **Verified**: All scaffold files present — backend (parser, extractor, prompts, embedder, matcher, reconciler, pipeline, 4 API routers, schemas, config, session, models), frontend (5 pages + 4 components + api lib), scripts, sample_data (6 PDFs, ~20MB, gitignored).
- **Restored** `frontend/CLAUDE.md` (1-line `@AGENTS.md` pointer Antigravity had deleted) to keep the tree clean.
- **Note**: `sample_data/*.pdf` is gitignored → PDFs stay local, repo stays light. User confirmed: keep gitignored.

## 2026-09-08 20:00 — API key format dispute resolved by testing
- **Claim under test**: user reported Google AI Studio keys now use `AQ.` prefix (citing Google forum + dev.to). Prior log assumed `AIza...` required.
- **Test**: `genai.list_models()` with the stored key → **auth-ok, 54 models**. The `AQ.` key is valid. Prior assumption was wrong.
- **Test**: full model list confirms **`models/gemini-3.6-flash` exists** with `generateContent` support. Prior suspicion of a hallucinated name was wrong.
- **Root cause of yesterday's 0-fact run** was the missing Anthropic key, not the Gemini key format.

## 2026-09-08 20:05 — Quota wall discovered (free tier exhausted)
- **Probe**: single JSON-mode `generate_content` on `gemini-3.6-flash` → **429** `generate_content_free_tier_requests, limit: 20`.
- **Smoked**: 25-min retry loop never cleared — the free-tier window for this model is exhausted (Antigravity's earlier runs consumed it), not a per-minute blip.
- **Fix**: new `backend/app/llm_retry.py` — pacing (`LLM_BATCH_DELAY_SEC=4.0`) + exponential backoff honouring the server's `retry in Ns` hint + **fail-fast abort** when the server demands >30s twice in a row (prevents repeat 25-min burns). Wired into `fact_extractor.py` and `reconciler.py`.
- **Fallback model found**: `gemini-2.5-flash-lite` is retired for this key (404, suggests `gemini-3.5-flash-lite`); **one probe on `gemini-3.5-flash-lite` succeeded** with JSON mode.
- **Decision**: `backend/.env` temporarily set to `GEMINI_MODEL=gemini-3.5-flash-lite` (local-only, gitignored). Canonical default `gemini-3.6-flash` kept in `.env.example` files.

## 2026-09-08 20:10 — Config bug: `.env` never loaded from repo root
- **Symptom**: smoke run logged `DefaultCredentialsError: No API_KEY` on all 6 batches → 0 facts, 27 bogus `llm_refused` issues.
- **Root cause**: `config.py` used relative `env_file=".env"`, which only resolves when CWD is `backend/`. Running scripts from the repo root silently loaded zero settings.
- **Fix**: absolute path `Path(__file__).resolve().parent.parent / ".env"` (first attempt used one `.parent` too many — caught and corrected by re-test).
- **Hardening**: `extract_facts_from_pages` and `reconcile_fact_pair` now raise a clear `RuntimeError` when `GEMINI_API_KEY` is missing, instead of producing dozens of cryptic per-batch issues.
- **New settings**: `LLM_BATCH_DELAY_SEC`, `LLM_MAX_RETRIES`, `LLM_RETRY_BASE_SEC` added to `config.py`, `backend/.env`, and both `.env.example` files.

## 2026-09-08 20:45 — SMOKE TEST PASSED (27-page earnings deck, gemini-3.5-flash-lite)
- **Result**: `03-delhivery-q4-fy24-earnings-presentation.pdf` → **169 facts, 22 issues, 0 relationships** (correct: first doc, matcher excludes same-document pairs), 39,645 tokens, ~2 min.
- **Quality spot-check**: facts look grounded and plausible (e.g. BSE scrip code 543529, NSE symbol DELHIVERY, 1,432 ESOP holders, verbatim evidence quotes, confidence scores).
- **Embeddings**: `all-mpnet-base-v2` loaded locally, 768-dim vectors stored via pgvector.

## 2026-09-08 20:50 — API + Frontend verified end-to-end
- **FastAPI** (`localhost:8000`): `/api/health` → ok; `/api/documents` → 1 doc, status done, fact_count 169, issue_count 22; `/api/facts`, `/api/issues` → real smoke data; `/api/relationships` → `[]` (correct).
- **Next.js** (`localhost:3000`): homepage initially **500** — Turbopack cannot parse `@import url(...fonts.googleapis...)` in `globals.css`. **Fix**: removed the CSS `@import`, loaded Inter via `next/font/google` in `layout.tsx` (also removes a runtime external request). After fix: **200 on all 5 routes** (`/`, `/relationships`, `/issues`, `/documents/[id]`, `/facts/[id]`).

## 2026-09-08 20:55 — Commit + push
- **Commit**: `fix: quota-safe Gemini pipeline + verified smoke test (169 facts)` — covers `llm_retry.py` (new), config `.env` fix + fail-fast guards + pacing settings, frontend font fix, `.env.example` updates, and this log.
- **Status after push**: Phase 10 smoke verified. **Full 6-PDF run (Phase 10) is BLOCKED on quota** — needs either (a) free-tier reset for `gemini-3.6-flash`/`gemini-3.5-flash-lite`, (b) a fresh API key, or (c) billing enabled. User decision pending.

2026-09-09 09:20
Action: Addressed quota exhaustion bug by scoping pipeline and applying Option A.
Details: 
1. Killed runaway ingestion task (940).
2. Modified pipeline.py to wait session.commit() immediately after Step 4 (extracting facts). This ensures facts are safely committed regardless of reconciliation outcomes.
3. Updated .env to lower SIMILARITY_K from 10 to 4 while preserving SIMILARITY_THRESHOLD=0.85.
4. Scoped down seed_and_run_demo.py to only process  1-delhivery-prospectus,  2-delhivery-annual-report,  1-india-economic-survey, and  3-imf-india-2025-article-iv.
Status: Re-running ingestion up to Step 7 (candidate pairs) to check new pair count.

2026-09-09 10:06
Action: Fired off the final, scoped ingestion run.
Details: 
1. Confirmed safe abort mechanisms: patched llm_retry.py to immediately abort and raise if the error message contains 'quota' instead of getting stuck in a 10-minute retry loop. Also fixed the pipeline.py exception block to avoid an IntegrityError that was masking the actual error.
2. Verified final pair count projection for K=1 and SIMILARITY_THRESHOLD=0.87: Doc 6 (60 pairs) + Doc 4 (122 pairs) = 182 total macro pairs. This guarantees full reconciliation of the macro docs, leaving ~298 API calls for Doc 2's relationships.
3. Started seed_and_run_demo.py in background task processing: IMF (Doc 6) -> Economic Survey (Doc 4) -> Delhivery Annual Report (Doc 2).

2026-09-09 10:16
Action: Monitoring final pipeline run.
Details: 
1. Document 6 ( 3-imf-india-2025-article-iv-excerpt.pdf) successfully completed! It extracted its facts, checked candidate pairs, and created 46 cross-document relationships (corroborations and contradictions).
2. The pipeline is currently on Document 4 ( 1-india-economic-survey-2024-25-excerpt.pdf), currently at Batch 3/12 of extraction. 

2026-09-09 10:20
Action: Monitoring final pipeline run.
Details: 
1. Document 4 ( 1-india-economic-survey-2024-25-excerpt.pdf) finished extraction and is now running reconciliation! It generated exactly 80 candidate pairs (fewer than the projected 122 because Document 2 is not yet in the DB).
2. It has successfully reconciled the first 5 pairs, including finding two strong contradicts flags between the Economic Survey's global GDP projections vs the IMF's global GDP projections! 
