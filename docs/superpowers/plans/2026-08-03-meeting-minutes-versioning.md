# Meeting Minutes Versioning and Traceability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve original meeting transcripts and every saved meeting-minutes revision while making extracted work items auditable before task writeback.

**Architecture:** Add an immutable `meeting_revisions` table linked to `meetings`. The existing meeting row remains the latest-version compatibility projection, while every create/save operation appends a full revision; legacy rows receive a pre-versioning snapshot on their first edit. Add read-only revision APIs and a lightweight history panel without changing the existing meeting workflow.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, React/TypeScript, pytest, Node-based frontend structure tests.

---

### Task 1: Define the immutable revision contract

**Files:**
- Create: `bowei_ai_dashboard/tests/test_meeting_revision_model.py`
- Modify: `bowei_ai_dashboard/app/models.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`

- [ ] **Step 1: Write failing model/schema tests**

Test that a revision stores the complete minutes snapshot, has a meeting foreign key, has a monotonically assigned version number, and exposes read-only response fields without making the original transcript optional.

- [ ] **Step 2: Run the focused tests and confirm the expected failure**

Run: `pytest bowei_ai_dashboard/tests/test_meeting_revision_model.py -q`

Expected: FAIL because `MeetingRevision` and its response schema do not exist.

- [ ] **Step 3: Add the minimal SQLAlchemy model and Pydantic response schema**

Add an immutable revision model containing the meeting metadata/content fields, `version_no`, `is_legacy_snapshot`, `saved_by`, `saved_at`, and `publish_status`. Keep the existing `Meeting` fields intact for compatibility.

- [ ] **Step 4: Run the focused tests and confirm they pass**

Run: `pytest bowei_ai_dashboard/tests/test_meeting_revision_model.py -q`

Expected: PASS.

### Task 2: Add the migration and revision persistence helper

**Files:**
- Create: `bowei_ai_dashboard/migrations/versions/<new_revision>_add_meeting_revisions.py`
- Create: `bowei_ai_dashboard/app/services/meeting_revisions.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_revision_service.py`

- [ ] **Step 1: Write failing service tests**

Cover three behaviors: first save creates `V1`; a later save creates the next version without mutating the previous snapshot; editing a legacy meeting first creates a system-upgrade snapshot and then `V1`.

- [ ] **Step 2: Run the service tests and confirm they fail for the missing helper**

Run: `pytest bowei_ai_dashboard/tests/test_meeting_revision_service.py -q`

Expected: FAIL because the revision service and table are missing.

- [ ] **Step 3: Implement migration and append-only persistence**

Create the table with a unique `(meeting_id, version_no)` constraint, indexes for meeting/time lookup, and fields required to reconstruct a complete minutes version. Implement a helper that snapshots the current meeting row, creates the legacy snapshot when needed, appends the requested revision, and updates the compatibility projection only after the revision is inserted.

- [ ] **Step 4: Run the service tests and confirm they pass**

Run: `pytest bowei_ai_dashboard/tests/test_meeting_revision_service.py -q`

Expected: PASS.

### Task 3: Wire create/update APIs to append revisions

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/meetings.py`
- Modify: `bowei_ai_dashboard/tests/test_meeting_draft_review.py`

- [ ] **Step 1: Add failing API-level tests**

Assert that creating a meeting produces `V1`, updating it produces `V2`, the first update of an existing legacy row preserves the old content as a legacy snapshot, and no update changes the stored original transcript.

- [ ] **Step 2: Run the API tests and confirm failure**

Run: `pytest bowei_ai_dashboard/tests/test_meeting_draft_review.py -q`

Expected: FAIL on revision count/history assertions.

- [ ] **Step 3: Integrate the persistence helper into create/update paths**

Use one transaction for revision insert plus current-row projection update. Make the original transcript immutable after the first create. Ensure existing permission, archive, notification, audit, and kickoff behavior remains unchanged.

- [ ] **Step 4: Run the API tests and confirm they pass**

Run: `pytest bowei_ai_dashboard/tests/test_meeting_draft_review.py -q`

Expected: PASS.

### Task 4: Expose read-only revision history

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/meetings.py`
- Modify: `bowei_ai_dashboard/frontend/src/api/meetings.ts`
- Modify: `bowei_ai_dashboard/frontend/src/types.ts`
- Create: `bowei_ai_dashboard/tests/test_meeting_revision_api.py`

- [ ] **Step 1: Write failing endpoint and type tests**

Verify listing revisions is ordered newest first, returns complete snapshots, respects the same project access/draft visibility rules, and provides a single revision detail endpoint.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `pytest bowei_ai_dashboard/tests/test_meeting_revision_api.py -q`

Expected: FAIL because the history endpoints do not exist.

- [ ] **Step 3: Add read-only list/detail endpoints and client types**

Return revision metadata plus full content, including original transcript reference and save actor/time. Do not add delete or overwrite endpoints.

- [ ] **Step 4: Run the focused tests and confirm they pass**

Run: `pytest bowei_ai_dashboard/tests/test_meeting_revision_api.py -q`

Expected: PASS.

### Task 5: Add evidence-aware extraction and history UI

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/meetings.py`
- Modify: `frontend/src/features/meeting/NewMeetingModal.tsx`
- Modify: `frontend/src/pages/MeetingPage.tsx`
- Modify: `frontend/src/features/meeting/meetingShared.tsx`
- Create: `frontend/tests/meetingRevisionHistory.test.mjs`

- [ ] **Step 1: Write failing frontend structure tests**

Assert that the meeting page exposes a history entry point, renders version labels, and keeps the original transcript section visible alongside the current minutes.

- [ ] **Step 2: Run the frontend tests and confirm failure**

Run: `node --test frontend/tests/meetingRevisionHistory.test.mjs`

Expected: FAIL because the history UI and client call are missing.

- [ ] **Step 3: Add evidence fields to extraction and display immutable history**

Extend action/decision/risk extraction to retain source evidence and explicit `待确认` values when owner/date/evidence is absent. Add a read-only version history panel and revision viewer; keep save behavior unchanged from the user’s perspective.

- [ ] **Step 4: Run frontend tests and focused backend extraction tests**

Run: `node --test frontend/tests/meetingRevisionHistory.test.mjs; pytest bowei_ai_dashboard/tests/test_meeting_draft_review.py bowei_ai_dashboard/tests/test_meeting_revision_model.py bowei_ai_dashboard/tests/test_meeting_revision_service.py bowei_ai_dashboard/tests/test_meeting_revision_api.py -q`

Expected: PASS.

### Task 6: Full verification and migration safety review

**Files:**
- Modify: `docs/BACKEND_API_REGISTRY.md` if endpoint documentation is required by the existing convention.

- [ ] **Step 1: Run migration dry checks and backend tests**

Run: `alembic -c bowei_ai_dashboard/alembic.ini upgrade head` in the project’s configured test database context, then run the focused and full relevant pytest suites.

- [ ] **Step 2: Run frontend type/build checks**

Run the existing frontend test and build commands from `frontend/package.json`.

- [ ] **Step 3: Inspect diff and verify requirement coverage**

Confirm original transcripts are never overwritten, every save appends a revision, legacy data is preserved on first edit, old revisions have no mutation path, and every extracted item can display source evidence or `待确认`.

