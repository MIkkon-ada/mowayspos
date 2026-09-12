# Project Init AI Agent Module Boundaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Do not dispatch subagents for this repository. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split project-init AI drafting internals by responsibility while retaining the `project_init_ai_agent` import surface and behavior.

**Architecture:** `project_init_ai_agent.py` becomes a compatibility facade. New internal modules own contracts, deterministic normalization, spreadsheet extraction, and model-call orchestration. Dependencies flow from the facade to internals, never back to the facade.

**Tech Stack:** Python, Pydantic 2, FastAPI service layer, pytest.

---

## Task 1: Freeze compatibility and extract contracts

**Files:**

- Create: `bowei_ai_dashboard/tests/test_project_init_ai_module_boundaries.py`
- Create: `bowei_ai_dashboard/app/services/project_init_ai_contracts.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_ai_agent.py`

- [x] **Step 1: Write a failing import-identity test.**

```python
from app.services import project_init_ai_agent as facade


def test_facade_reexports_contract_types():
    from app.services import project_init_ai_contracts as contracts

    assert facade.AgentTask is contracts.AgentTask
    assert facade.AgentSubTask is contracts.AgentSubTask
    assert facade.Evidence is contracts.Evidence
    assert facade.ProjectInitAiResult is contracts.ProjectInitAiResult
    assert facade.ProjectInitAiError is contracts.ProjectInitAiError
    assert facade.SourceChunk.__module__ == "app.services.project_init_file_parser"
```

- [x] **Step 2: Verify the test is red.**

Run `python -m pytest tests/test_project_init_ai_module_boundaries.py -q` from `bowei_ai_dashboard`.

Expected: import failure because `project_init_ai_contracts` does not exist.

- [x] **Step 3: Move only protocol definitions.**

Move without changing bodies: constants; the three `ProjectInitAi*` error classes; `_safe_validation_errors`; `AgentWarning`, `Evidence`, `PersonCandidate`, `AgentSubTask`, `AgentTask`, `ProjectProfileDraft`, `ProjectInitAiResult`, and `_RawEnvelope`. The new module owns the existing Pydantic imports and only imports `SourceChunk` from `project_init_file_parser` when required for types.

Replace definitions in the facade with imports equivalent to:

```python
from .project_init_ai_contracts import AgentTask, AgentSubTask, Evidence, PersonCandidate
from .project_init_ai_contracts import ProjectInitAiError, ProjectInitAiEmptyResult
from .project_init_ai_contracts import ProjectInitAiInvalidDraft, ProjectInitAiResult
from .project_init_file_parser import SourceChunk
```

- [x] **Step 4: Verify and commit.**

Run `python -m pytest tests/test_project_init_ai_module_boundaries.py tests/test_project_init_ai_agent.py -q`; expected: pass.

```powershell
git add app/services/project_init_ai_contracts.py app/services/project_init_ai_agent.py tests/test_project_init_ai_module_boundaries.py
git commit -m "refactor: extract project init AI contracts"
```

## Task 2: Extract deterministic normalization

**Files:**

- Create: `bowei_ai_dashboard/app/services/project_init_ai_normalization.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_ai_agent.py`
- Modify: `bowei_ai_dashboard/tests/test_project_init_ai_module_boundaries.py`

- [x] **Step 1: Write the next failing compatibility test.**

```python
def test_facade_reexports_normalization_helpers():
    from app.services import project_init_ai_normalization as normalization

    assert facade.normalize_agent_result is normalization.normalize_agent_result
    assert facade._merge_tasks is normalization._merge_tasks
    assert facade.has_cross_batch_task_conflict is normalization.has_cross_batch_task_conflict
```

- [x] **Step 2: Verify it is red.**

Run `python -m pytest tests/test_project_init_ai_module_boundaries.py -q`.

Expected: import failure because `project_init_ai_normalization` does not exist.

- [x] **Step 3: Move the full pure reconciliation group.**

Move unchanged from the current agent file: `_normalise_name`, `_normalise_title`, `has_cross_batch_task_conflict`, `_is_calendar_date`, `_normalise_start_only_dates`, `_source_label`, `_person_candidates`, `_warning`, `_match_person`, every `_dedupe_*`, `_merge_non_empty`, `_merge_subtask_values`, `_merge_task_values`, `_merge_tasks`, `_source_parts`, `_source_index`, `_safe_evidence`, `_safe_evidence_list`, `_reconcile_project_profile`, `_merge_project_profiles`, `_existing_task_index`, `_classify_duplicate`, `_reconcile_task`, and `normalize_agent_result`.

The new module imports types from `project_init_ai_contracts` and `SourceChunk` directly; it must not import the facade or AIService. The facade re-exports the moved functions.

- [x] **Step 4: Verify and commit.**

Run `python -m pytest tests/test_project_init_ai_module_boundaries.py tests/test_project_init_ai_agent.py -q`; expected: pass for people matching, evidence, dates and duplicate behavior.

```powershell
git add app/services/project_init_ai_normalization.py app/services/project_init_ai_agent.py tests/test_project_init_ai_module_boundaries.py
git commit -m "refactor: isolate project init AI normalization"
```

## Task 3: Extract deterministic spreadsheet processing

**Files:**

- Create: `bowei_ai_dashboard/app/services/project_init_ai_spreadsheet.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_ai_agent.py`
- Modify: `bowei_ai_dashboard/tests/test_project_init_ai_module_boundaries.py`

- [x] **Step 1: Write the failing structured-generator test.**

```python
def test_facade_reexports_structured_spreadsheet_generator():
    from app.services import project_init_ai_spreadsheet as spreadsheet

    assert facade.generate_structured_project_init_draft is spreadsheet.generate_structured_project_init_draft
```

- [x] **Step 2: Verify it is red.**

Run `python -m pytest tests/test_project_init_ai_module_boundaries.py -q`.

Expected: import failure because `project_init_ai_spreadsheet` does not exist.

- [x] **Step 3: Move all worksheet-only behavior.**

Move unchanged: `_column_number`, `_worksheet_range`, `_enclosed_worksheet_sources`, `_repair_coarse_worksheet_evidence`, `_repair_batch_evidence`, `_spreadsheet_plan_dates`, `_explicit_spreadsheet_date`, `_bounded_spreadsheet_text`, `_split_numbered_spreadsheet_items`, `_split_helper_names`, `_normalise_spreadsheet_header`, `_normalise_work_plan_row`, `_structured_spreadsheet_rows`, `_structured_spreadsheet_fallback`, and `generate_structured_project_init_draft`.

The module imports contracts and normalization helpers directly. It retains the current rule that every meaningful structured source must be recognized before returning a fast-path result. The facade re-exports the public generator and any currently imported worksheet helper.

- [x] **Step 4: Verify and commit.**

Run `python -m pytest tests/test_project_init_ai_module_boundaries.py tests/test_project_init_ai_agent.py tests/test_project_init_analysis.py -q`; expected: pass for rejected sheets, column coverage, fast path, and vision route.

```powershell
git add app/services/project_init_ai_spreadsheet.py app/services/project_init_ai_agent.py tests/test_project_init_ai_module_boundaries.py
git commit -m "refactor: isolate project init spreadsheet drafting"
```

## Task 4: Extract the model-call pipeline

**Files:**

- Create: `bowei_ai_dashboard/app/services/project_init_ai_pipeline.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_ai_agent.py`
- Modify: `bowei_ai_dashboard/tests/test_project_init_ai_module_boundaries.py`

- [x] **Step 1: Write the failing pipeline-identity test.**

```python
def test_facade_reexports_pipeline_entry_points():
    from app.services import project_init_ai_pipeline as pipeline

    assert facade.generate_project_init_draft is pipeline.generate_project_init_draft
    assert facade._parse_json_response is pipeline._parse_json_response
    assert facade._classify_raw_draft_envelope is pipeline._classify_raw_draft_envelope
```

- [x] **Step 2: Verify it is red.**

Run `python -m pytest tests/test_project_init_ai_module_boundaries.py -q`.

Expected: import failure because `project_init_ai_pipeline` does not exist.

- [x] **Step 3: Move orchestration without altering calls.**

Move unchanged: `_split_batches`, `_context_prompt`, `_semantic_workbook_batch`, `_requires_semantic_ai_route`, `_missing_semantic_fields`, `_semantic_repair_prompt`, `_final_merge_prompt`, LLM payload constants and normalizers, `_JsonResponseError`, `_parse_json_response`, `_classify_raw_draft_envelope`, `_evidence_traceability_error`, `_validate_evidence_group`, `_validate_batch_sources`, `_invoke_llm`, and `generate_project_init_draft`.

The pipeline imports contracts, normalization, and spreadsheet modules directly. It only constructs `AIService` through existing `service_factory` / `llm_call` seams. The facade contains imports and re-exports only; neither generator signature, prompt, timeout, model-selection, fallback nor safe diagnostic behavior may change.

- [x] **Step 4: Verify and commit.**

Run `python -m pytest tests/test_project_init_ai_module_boundaries.py tests/test_project_init_ai_agent.py tests/test_project_init_analysis.py tests/test_ai_capability_integration.py -q`; expected: pass with identical capability, fallback, JSON-diagnostic and persisted-worker behavior.

```powershell
git add app/services/project_init_ai_pipeline.py app/services/project_init_ai_agent.py tests/test_project_init_ai_module_boundaries.py
git commit -m "refactor: isolate project init AI pipeline"
```

## Task 5: Full delivery gate

- [x] **Step 1: Run all affected backend suites.**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_init_ai_module_boundaries.py tests/test_project_init_ai_agent.py tests/test_project_init_analysis.py tests/test_project_init_work_progress_draft.py tests/test_ai_capability_integration.py -q
```

Expected: exit code 0 with no changed draft or fallback behavior.

- [x] **Step 2: Run complete delivery verification.**

```powershell
python -m pytest tests -q
Set-Location ..\frontend
npm run test:all
npm run build
Set-Location ..
git diff --check
git status --short
```

Expected: all commands exit 0; the existing ExcelJS chunk-size warning may remain.

**Recorded 2026-09-13:** affected backend suites: **184 passed**; complete backend suite:
**1916 passed, 12 skipped** in 497.45 seconds; frontend: **89 unit tests passed**,
**502 contract tests passed**, and the production build passed. `git diff --check`
passed; the frontend build retained only the expected ExcelJS bundle-size warning.

- [x] **Step 3: Record results and commit.**

Update this plan with actual totals, then run:

```powershell
git add docs/superpowers/plans/2026-09-13-project-init-ai-agent-module-boundaries.md
git commit -m "docs: record project init AI boundary verification"
```
