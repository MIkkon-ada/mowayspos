# Complete Meeting Analysis Implementation Plan

> **For agentic workers:** Execute inline in the current session. Preserve all pre-existing workspace changes and do not commit the mixed worktree.

**Goal:** Ensure every factual item in a meeting document is preserved and receives a validated project-analysis disposition before the run is marked complete.

**Architecture:** Keep source extraction deterministic for recognized standard minutes and treat project analysis as a separate, bounded step. Split large source inventories into small fact batches, merge their project-analysis results with globally unique lineage IDs, and enforce a final whole-document coverage gate. Add bounded response repair and provider truncation diagnostics.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, DeepSeek-compatible chat adapter, pytest.

---

### Task 1: Bound malformed-output recovery and expose truncation metadata

**Files:**
- Modify: `bowei_ai_dashboard/app/services/project_meeting_agent.py`
- Modify: `bowei_ai_dashboard/app/ai/adapters.py`
- Modify: `bowei_ai_dashboard/app/ai/service.py`
- Modify: `bowei_ai_dashboard/app/services/project_meeting_agent_processing.py`
- Test: `bowei_ai_dashboard/tests/test_project_meeting_agent.py`
- Test: `bowei_ai_dashboard/tests/test_ai_adapters.py`

- [x] Add bounded repair coverage and classify a final length-limited response as a distinct safe error.
- [x] Capture provider finish reason and token usage through the adapter, AI service, and meeting-agent provider without storing prompts or source text in diagnostic events.
- [x] Implement bounded repairs while preserving current model-level output limits; leave the shared model limit unchanged. Retain tool lookup results in repair prompts and identify any prior output truncation.
- [x] Run focused tests and reprocess the previously failing 2026-08-03 Word upload through the compact analyzer.

### Task 2: Require complete source-fact coverage before review

**Files:**
- Modify: `bowei_ai_dashboard/app/services/standard_meeting_minutes.py`
- Modify: `bowei_ai_dashboard/app/services/project_meeting_agent_processing.py`
- Test: `bowei_ai_dashboard/tests/test_standard_meeting_minutes.py`
- Test: `bowei_ai_dashboard/tests/test_project_meeting_agent_processing.py`

- [x] Add tests that every decision, current action, and prior-action fact extracted from a recognized standard Word is represented exactly once in the final AI analysis layers.
- [x] Implement deterministic source-fact IDs and server-computed Word evidence spans; compare the parsed fact set against matched, unmatched, and needs-confirmation dispositions; reject missing, duplicate, unknown, wrong-type, or altered-content facts.
- [x] Split standard-minute inventories into batches of eight, run project lookup per batch, ask AI for a compact disposition/match/delta classification, and compile evidence and lineage IDs on the server. Keep the run incomplete if any batch or final coverage check fails.
- [x] Run focused tests for complete coverage, duplicates, omissions, and retries.

### Task 3: Preserve complete source minutes

**Files:**
- Modify: `bowei_ai_dashboard/app/services/project_meeting_agent_processing.py`
- Test: `bowei_ai_dashboard/tests/test_project_meeting_agent_processing.py`

- [x] Analysis coverage validation runs before result normalization and review-draft creation; retain the exact Word-derived formal minutes in the merged result.
- [x] Verify processing integration leaves failed/incomplete analysis outside `pending_review` and reuses the unedited draft for a successful retry.
- [x] Run backend meeting-agent, tool matching, processing, standard-minutes, and adapter suites; local backend health returned 200.

**Acceptance run:** The 2026-08-03 Word upload completed as run 12 in `pending_review`. All 34 deterministic fact IDs appeared exactly once; every fact kept its original text and valid Word evidence. The analysis produced 21 project matches/deltas, 8 unmatched facts, and 5 items requiring confirmation. The formal Word metadata matched the review draft, and the retry reused the existing meeting draft.

**Scope note:** This change does not add persisted per-fact checkpoints or resumable model batches. A retry re-runs the bounded analysis against the deterministic source inventory; incomplete output remains failed and cannot become a review draft. This keeps the work isolated from the existing run lifecycle and avoids changing the 8,192-token model configuration globally.

### Follow-up: Word to work-progress review

- [x] Correct compact-analysis project evidence identifiers so matches validate against the frozen task snapshot.
- [x] Project validated Word facts onto the full key-task hierarchy. Decisions and risks stay visible; progress and action facts become field-level suggestions with exact Word evidence.
- [x] Persist review proposals and show a grouped work-progress preview with current progress, Word suggestions, and per-task selection.
- [x] Let the project owner publish and sync selected progress in one transaction. Unlinked facts stay in the minutes by default; optional task linking merges into an existing task suggestion.
- [x] Show confirmed meeting progress in the work-progress table through the latest confirmed execution event.
- [x] Safely backfill the untouched local 2026-08-03 pending draft after backing up the SQLite database. Its 21 source matches are now valid, but only Word action rows are projected to work progress.
- [x] Rebuild that untouched review package from the Word's 17 original action rows. Eight have sufficiently supported task matches, and nine retain an explicit task-review choice; the weak Tencent ticket match is no longer selected for writeback. Decisions, discussion, and risks remain in the minutes.
- [x] Show all 17 Word action rows in source order with their original code, owner, tracker, and due date; persist that metadata with a confirmed meeting progress event and display it in the work-progress table.
- [x] Compile the backend modules and build the frontend. Both local ports, 8011 and 6005, respond.

The existing published 2026-07-27 minutes were not rewritten. The in-app browser session is expired, so the final authenticated visual review remains for the project owner.

## Self-review

- Source content remains authoritative; the model does not overwrite parsed standard-minute fields.
- Analysis alone creates no project writes. Selected progress is written only when the owner publishes and synchronizes it.
- No workspace-wide reset, migration, deployment, or commit is part of this task.
