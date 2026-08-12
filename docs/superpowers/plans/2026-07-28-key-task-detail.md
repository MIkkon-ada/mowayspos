# Key Task Detail Implementation Plan

**Goal:** Replace the execution-detail page with the approved report-driven key-task detail layout.

**Architecture:** Reuse `SubTaskDetail` returned by `GET /api/subtasks/{id}/detail`. Render optional criteria only when present; use `work_reports` as the sole progress history; render achievements in the sidebar.

**Files:**
- Modify `frontend/src/components/task-management/KeyTaskExecutionDetailView.tsx`
- Modify `frontend/tests/workProgressExcelView.test.mjs`

1. Add a static test asserting the detail view contains report-driven sections and no preset step component.
2. Replace the fixed four-step progress UI with a responsive header, compact context strip, optional criteria card, report history, and sidebar overview/results.
3. Run the focused Node test and inspect the frontend page.
