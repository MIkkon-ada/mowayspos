# Project Init AI-First Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make structured project-init imports call AI first, use deterministic extraction only as a verified fallback, and expose the real processing mode in the UI.

**Architecture:** Keep workbook parsing and deterministic row extraction as pure preprocessing/fallback services. Route all normal parsed sources through `generate_project_init_draft` when an AI caller is available; let that function fall back to a complete structured draft on AI service or validation failure. Persist `processing_mode` in run metadata and render a truthful one-line notice in both import review surfaces.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, React, TypeScript, Vitest, Testing Library.

---

### Task 1: Lock the AI-first service contract with failing tests

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_project_init_ai_agent.py`
- Modify: `bowei_ai_dashboard/tests/test_project_plan_ai_import.py`

- [ ] **Step 1: Replace the old bypass expectation with an AI-first test**

In `test_project_init_ai_agent.py`, change the existing recognized-work-plan test so its injected `llm_call` returns a valid evidence-bound draft and assert the call occurs, the returned title comes from the AI response, and the result provider is not `local-rule`:

```python
def test_recognized_work_plan_rows_use_ai_when_an_ai_caller_is_available():
    spreadsheet_row = {
        "attachment_id": 7,
        "file_name": "推进表.xlsx",
        "location": "'推进表'!A2:J2",
        "text": (
            "专项\t关键任务\t关键成果\t完成标准\t统筹人\t负责人\t协同成员\t计划时间\t当前状态\t问题与协调\n"
            "专项甲\t任务甲\t成果甲\t标准甲\t张三\t李四\t王五\t2026-06-01\t进行中\t备注甲"
        ),
    }
    calls: list[str] = []

    def llm(prompt: str) -> str:
        calls.append(prompt)
        return json.dumps({
            "tasks": [raw_task(
                title="AI 语义识别工作",
                evidence=[{"attachment_id": 7, "file_name": "推进表.xlsx", "location": "'推进表'!A2:J2"}],
            )]
        }, ensure_ascii=False)

    result = generate_project_init_draft([spreadsheet_row], [], [], llm_call=llm)

    assert calls
    assert result.tasks[0].title == "AI 语义识别工作"
    assert result.provider == "injected"
    assert result.provider != "local-rule"
```

- [ ] **Step 2: Add the AI-unavailable fallback assertion**

Add a test using `llm_call` that raises `AIUpstreamError` and assert the structured result is returned with `provider == "local-rule"` and `model_name == "structured-spreadsheet-fallback"`.

- [ ] **Step 3: Run the focused tests and verify they fail for the current reason**

Run:

```powershell
python -m pytest bowei_ai_dashboard/tests/test_project_init_ai_agent.py -k "recognized_work_plan_rows_use_ai_when_an_ai_caller_is_available or AI_unavailable_fallback" -q
```

Expected: the AI-first test fails because the current fast path returns the structured result without calling `llm_call`.

- [ ] **Step 4: Add the project-plan service regression test**

In `bowei_ai_dashboard/tests/test_project_plan_ai_import.py`, add a test where `generate_project_init_draft` returns `_fake_draft()` and assert `fallback_mode == "ai"`; add a companion test where it raises `AICapabilityNotConfigured` and the structured fallback is returned with `fallback_mode == "deterministic"`.

### Task 2: Change the shared pipeline to AI-first with deterministic fallback

**Files:**
- Modify: `bowei_ai_dashboard/app/services/project_init_ai_pipeline.py`
- Modify: `bowei_ai_dashboard/app/services/project_plan_ai_import.py`
- Test: `bowei_ai_dashboard/tests/test_project_init_ai_agent.py`
- Test: `bowei_ai_dashboard/tests/test_project_plan_ai_import.py`

- [ ] **Step 1: Remove only the production fast-path short circuit when an AI caller exists**

In `generate_project_init_draft`, keep the existing structured extraction for the no-caller compatibility case, but only return it before model analysis when both `llm_call` and `ai_service` are `None`:

```python
structured_draft = _structured_spreadsheet_fallback(
    source_values,
    people,
    indexed_tasks,
    "local-rule",
    model_name="structured-spreadsheet",
    require_full_coverage=True,
)
if llm_call is None and ai_service is None and structured_draft is not None:
    return structured_draft
```

The code must then resolve `llm_call` or `ai_service` and attempt AI whenever a caller was supplied.

- [ ] **Step 2: Broaden fallback handling to configuration and upstream errors**

Import `AIServiceError` from `app.ai.contracts` and change the batch invocation exception branch to catch `AIServiceError` together with `ProjectInitAiError`. When a complete structured fallback exists, return it with `provider="local-rule"` and `model_name="structured-spreadsheet-fallback"`; otherwise re-raise the original failure.

- [ ] **Step 3: Run the focused backend tests**

Run:

```powershell
python -m pytest bowei_ai_dashboard/tests/test_project_init_ai_agent.py bowei_ai_dashboard/tests/test_project_plan_ai_import.py -q
```

Expected: the new AI-first and fallback tests pass; any old tests that explicitly assert AI bypass are updated to the new contract rather than weakening the implementation.

### Task 3: Route owner-submit analysis through the shared AI-first pipeline

**Files:**
- Modify: `bowei_ai_dashboard/app/services/project_init_analysis.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_ai_pipeline.py`
- Modify: `bowei_ai_dashboard/tests/test_project_init_analysis.py`

- [ ] **Step 1: Add a worker test proving standard Excel calls AI**

Update `test_worker_uses_structured_workbook_draft_only_without_vision_sources` so regular, overview, and inline-overview workbooks provide a valid mocked `generate_project_init_draft` result and assert that it is called. Keep the complex workbook case asserting that visual analysis is called first.

- [ ] **Step 2: Change the worker’s normal path**

In `process_analysis_run`, always instantiate `AIService(db)` before the normal text path. Remove the `if not vision_sources: result = generate_structured_project_init_draft(...)` short circuit. Leave the vision branch intact; if it does not produce a result, call `generate_project_init_draft(..., ai_service=ai_service, invocation_context=context)`.

- [ ] **Step 3: Persist the actual processing mode**

Extend `_result_metadata` with:

```python
"processing_mode": "deterministic_fallback"
if provider == "local-rule" or model_name in {"structured-spreadsheet", "structured-spreadsheet-fallback", "semantic-source-repair"}
else "ai",
```

The existing provider/model fields remain unchanged for compatibility. Add `ai_unavailable_fallback` to `analysis_route.reason_codes` only when the final result is deterministic and the worker used the AI-first path.

- [ ] **Step 4: Run worker and routing tests**

Run:

```powershell
python -m pytest bowei_ai_dashboard/tests/test_project_init_analysis.py bowei_ai_dashboard/tests/test_project_init_analysis_routing.py -q
```

Expected: standard workbooks show an AI model call in the mocked path; complex workbooks still use vision; deterministic fallback tests still show `structured-spreadsheet-fallback`.

### Task 4: Show truthful processing-mode notices in the frontend

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitAiPanel.tsx`
- Modify: `frontend/src/features/settings/OwnerSubmitAiPanel.retry.test.tsx`
- Modify: `frontend/src/features/settings/ProjectPlanAiImportDialog.tsx` only if the shared wording needs alignment
- Modify: `frontend/src/features/settings/ProjectPlanAiImportDialog.test.tsx` only if the wording changes

- [ ] **Step 1: Add a frontend test for both metadata states**

Add `processing_mode: 'ai'` to the AI fixture and assert the preview contains `AI 已参与分析，结果仅供核对，确认后再写入。`. Add a deterministic fixture with `processing_mode: 'deterministic_fallback'` and assert it contains `AI 当前不可用，已自动切换为规则提取，请重点核对关键字段。`.

- [ ] **Step 2: Implement a pure notice helper**

Add a helper beside `analysisReviewNotice`:

```tsx
function analysisModeNotice(run: ProjectInitAnalysisRun): string {
  return run.result_metadata.processing_mode === 'deterministic_fallback'
    ? 'AI 当前不可用，已自动切换为规则提取，请重点核对关键字段。'
    : run.result_metadata.processing_mode === 'ai'
      ? 'AI 已参与分析，结果仅供核对，确认后再写入。'
      : ''
}
```

- [ ] **Step 3: Render the notice in the preview**

Render the helper’s result under the technical-details block and before the existing complex-layout review notice, using a neutral blue style for AI success and the existing amber style for deterministic fallback.

- [ ] **Step 4: Run frontend focused tests**

Run:

```powershell
Set-Location frontend
npm test -- --run src/features/settings/OwnerSubmitAiPanel.retry.test.tsx src/features/settings/ProjectPlanAiImportDialog.test.tsx
```

Expected: both AI-success and deterministic-fallback notices render correctly.

### Task 5: Full verification and local smoke check

**Files:**
- Modify: `docs/superpowers/plans/2026-09-14-project-init-ai-first.md` to check completed steps only after verification

- [ ] **Step 1: Run the focused backend suite again**

```powershell
python -m pytest bowei_ai_dashboard/tests/test_project_init_ai_agent.py bowei_ai_dashboard/tests/test_project_plan_ai_import.py bowei_ai_dashboard/tests/test_project_init_analysis.py -q
```

- [ ] **Step 2: Run the focused frontend suite again**

```powershell
Set-Location frontend
npm test -- --run src/features/settings/OwnerSubmitAiPanel.retry.test.tsx src/features/settings/ProjectPlanAiImportDialog.test.tsx
```

- [ ] **Step 3: Verify the local database after one owner-submit run**

Query `project_init_analysis_runs` read-only and confirm the new result has either `processing_mode=ai` with an AI attempt in `model_attempts`, or `processing_mode=deterministic_fallback` with `provider=local-rule` and the warning reason code. Do not modify the database during verification.

- [ ] **Step 4: Inspect the final diff**

Run `git diff --check` and `git status --short`. Confirm unrelated pre-existing changes remain untouched and report exact tests and runtime evidence.
