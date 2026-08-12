# Multi-source Meeting Minutes Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a scrollable meeting-minutes creation workspace that accepts Word/TXT, supplemental text, and optional audio together before generating a generic AI minutes draft.

**Architecture:** The backend exposes one authenticated document-text extraction endpoint for `.docx` and `.txt`, returning plain text without persisting uploads. The frontend keeps each source separate, combines labelled non-empty sources for the existing analysis endpoint, then preserves user-entered meeting metadata during review and save.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, Python standard-library ZIP/XML parsing, React/TypeScript, Vite, node:test, pytest.

---

### Task 1: Document source extraction

**Files:**
- Create: `bowei_ai_dashboard/app/services/meeting_document_text.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_document_text.py`
- Modify: `bowei_ai_dashboard/app/routers/meetings.py`

- [ ] Write failing tests for `.txt` and `.docx` text extraction plus a rejected `.pdf`.
- [ ] Run `pytest tests/test_meeting_document_text.py -q` and confirm import failure.
- [ ] Implement extension validation, a 10 MB limit, UTF-8 text decoding, and paragraph-preserving Word XML parsing.
- [ ] Add `POST /api/meetings/extract-document-text`, protected by login and project access.
- [ ] Run the focused pytest file and confirm all cases pass.

### Task 2: Persist the new meeting metadata

**Files:**
- Modify: `bowei_ai_dashboard/app/models.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Create: `bowei_ai_dashboard/migrations/versions/<revision>_add_meeting_location_and_cc.py`
- Modify: `frontend/src/types.ts`

- [ ] Write a model/payload test proving `location` and `copied_to` round-trip as meeting fields.
- [ ] Run the focused pytest test and confirm it fails because the fields are absent.
- [ ] Add nullable-safe string columns, schema fields, and migration upgrade/downgrade operations.
- [ ] Update the frontend meeting type to match the API payload.
- [ ] Re-run the focused pytest test and confirm it passes.

### Task 3: Multi-source input workspace

**Files:**
- Modify: `frontend/src/api/meetings.ts`
- Modify: `frontend/src/features/meeting/NewMeetingModal.tsx`
- Create: `frontend/tests/newMeetingMultiSource.test.mjs`

- [ ] Write static behavior tests asserting six selectable types, separated host/participant fields, document API upload, `accept` values excluding PDF, and labelled source merging.
- [ ] Run `node --test tests/newMeetingMultiSource.test.mjs` and confirm the checks fail.
- [ ] Add the document upload client and replace the constrained input screen with the full-height scrollable workspace.
- [ ] Keep document text, supplemental text, and audio transcription independent; enable generation when any source exists and merge only non-empty labelled sources.
- [ ] Preserve selected meeting type and manually supplied metadata when AI results enter review; save location and copied-to metadata.
- [ ] Re-run the focused node test and confirm it passes.

### Task 4: Verification

**Files:**
- Verify only

- [ ] Run focused backend and frontend tests.
- [ ] Run `npm run build` from `frontend`.
- [ ] Start or reuse the local frontend/backend and visually inspect the full-page input flow.

