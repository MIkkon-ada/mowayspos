# Project-init rerun analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a project owner start a new AI analysis from the already uploaded project-init attachments after a successful preview.

**Architecture:** `OwnerSubmitAiPanel` already persists the attachment ids and owns the analysis creation/polling state. Add a preview-state action that calls the existing `startAnalysis` function, so it creates a new run with the same attachments and retains all existing upload, error, and polling behavior.

**Tech Stack:** React, TypeScript, Vitest structural tests, FastAPI integration already present.

---

### Task 1: Expose the rerun action in successful previews

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitAiPanel.tsx:688-724`
- Test: `bowei_ai_dashboard/tests/test_project_init_ai_frontend.py`

- [ ] **Step 1: Write the failing test**

```python
def test_owner_submit_ai_preview_offers_rerun_for_existing_attachments():
    source = _frontend_source("features/settings/OwnerSubmitAiPanel.tsx")
    assert "重新分析" in source
    assert "onClick={() => void startAnalysis()}" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& .\.venv\Scripts\python.exe -m pytest -q tests/test_project_init_ai_frontend.py::test_owner_submit_ai_preview_offers_rerun_for_existing_attachments`

Expected: FAIL because completed preview has no rerun action.

- [ ] **Step 3: Write minimal implementation**

```tsx
<button
  type="button"
  onClick={() => void startAnalysis()}
  disabled={disabled || applying || applySuccess}
  className="rounded-lg border border-blue-200 bg-white px-3 py-2 text-xs font-bold text-blue-700 hover:bg-blue-50 disabled:opacity-50"
>
  重新分析
</button>
```

Place the button in the completed preview header beside the existing model summary/action area. It must call `startAnalysis` instead of duplicating requests, retaining the attachment ids and normal run polling.

- [ ] **Step 4: Run tests to verify it passes**

Run: `& .\.venv\Scripts\python.exe -m pytest -q tests/test_project_init_ai_frontend.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/features/settings/OwnerSubmitAiPanel.tsx bowei_ai_dashboard/tests/test_project_init_ai_frontend.py docs/superpowers/plans/2026-08-30-project-init-rerun-analysis.md
git commit -m "feat: allow rerunning project-init AI analysis"
```
