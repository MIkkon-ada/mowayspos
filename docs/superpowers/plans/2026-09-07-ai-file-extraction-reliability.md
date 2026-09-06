# AI File Extraction Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every advertised AI document format truthful, expose meeting formats consistently, and add bounded Vision OCR fallback for scanned project-init PDFs.

**Architecture:** Keep existing text parsers as the primary route. Add a dedicated PDF-to-PNG renderer used only when the project-init parser returns no textual chunks for a PDF, then reuse the existing evidence-bound Vision draft generator. Keep format selection UI configuration in one frontend module and preserve backend route-specific limits.

**Tech Stack:** FastAPI, SQLAlchemy, pypdf, Poppler, Pillow, React, TypeScript, pytest, Vitest/static Node tests.

---

### Task 1: Define tested PDF Vision fallback

**Files:**
- Create: `bowei_ai_dashboard/app/services/project_init_pdf_renderer.py`
- Create: `bowei_ai_dashboard/tests/test_project_init_pdf_renderer.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_analysis.py`
- Modify: `bowei_ai_dashboard/tests/test_project_init_analysis.py`
- Modify: `bowei_ai_dashboard/requirements.txt`

- [ ] Write tests proving a two-page PDF renders bounded PNGs, rejects an over-limit page count, and that an otherwise textless PDF invokes the existing Vision draft route then removes temporary images.
- [ ] Run those tests and observe failure because the renderer and scanned-PDF route do not exist.
- [ ] Implement a `render_project_init_pdf_images(path, output_directory, max_images=8)` renderer using Poppler; cap pages, image dimensions, per-image pixels and total pixels.
- [ ] In `process_analysis_run`, classify a PDF with no text chunks as a Vision source, add a non-business page-location evidence chunk, call the existing Vision generator, and retain `vision_with_review` metadata.
- [ ] Run the new tests and the existing project-init analysis tests.

### Task 2: Make project-init Vision opt-in generic

**Files:**
- Modify: `bowei_ai_dashboard/app/ai/service.py`
- Modify: `bowei_ai_dashboard/tests/test_ai_service.py`

- [ ] Write a failing test for the new `vision_project_init_analysis` model config flag while retaining the legacy workbook flag.
- [ ] Update candidate filtering to accept either explicit flag, without changing capability or provider restrictions.
- [ ] Run AI service tests.

### Task 3: Correct document format promises

**Files:**
- Create: `frontend/src/config/aiDocumentFormats.ts`
- Modify: `frontend/src/features/meeting/NewMeetingModal.tsx`
- Modify: `frontend/src/features/voice-update/VoiceUpdateInputPanel.tsx`
- Modify: `frontend/src/components/key-task-workspace/ExecutionPlanCreateDrawer.tsx`
- Modify: `frontend/src/features/settings/OwnerSubmitAiPanel.tsx`
- Modify: `bowei_ai_dashboard/app/services/project_init_file_parser.py`
- Modify: `bowei_ai_dashboard/app/services/meeting_document_text.py`
- Create: `frontend/tests/aiDocumentFormats.test.mjs`
- Modify: `bowei_ai_dashboard/tests/test_project_init_file_parser.py`
- Modify: `bowei_ai_dashboard/tests/test_meeting_document_text.py`

- [ ] Write failing frontend checks requiring every upload control to use the shared format module and requiring meeting formats to include `.docx,.txt,.xlsx`.
- [ ] Write failing backend tests requiring an actionable `antiword` dependency error and an accurate meeting Excel support message.
- [ ] Add the frontend format module and replace duplicated `accept` strings and labels.
- [ ] Normalize the backend errors, leaving each workflow's intentionally different supported format set unchanged.
- [ ] Run frontend format checks and backend parser tests.

### Task 4: Verify without changing business flow

**Files:**
- Verify: `bowei_ai_dashboard/tests/test_project_init_file_parser.py`
- Verify: `bowei_ai_dashboard/tests/test_project_init_analysis.py`
- Verify: `bowei_ai_dashboard/tests/test_project_init_pdf_renderer.py`
- Verify: `bowei_ai_dashboard/tests/test_work_report_document_text.py`
- Verify: `bowei_ai_dashboard/tests/test_meeting_document_text.py`
- Verify: `bowei_ai_dashboard/tests/test_task_plan_proposals.py`
- Verify: `frontend/tests/aiDocumentFormats.test.mjs`

- [ ] Run focused backend tests, frontend build and relevant static tests.
- [ ] Run the complete backend suite and `git diff --check`.
