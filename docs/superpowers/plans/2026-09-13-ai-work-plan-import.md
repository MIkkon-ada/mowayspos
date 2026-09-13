# 通用 AI 工作计划导入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将项目管理中的工作计划导入升级为通用 AI 导入流程，支持文件上传、粘贴、非固定表头和非固定表名，并在人工确认后复用现有事务导入服务写入项目层级数据。

**Architecture:** 新增一个面向批量导入的 AI 预览接口，但复用现有 `project.init.analysis` 能力、文件解析器、结构化草稿合同和模型配置。AI 只生成带来源证据的 review draft；前端允许用户编辑/确认，确认后的草稿转换成现有 `BatchImportRow`，最后仍由 `project_plan_import.py` 负责权限后的校验、去重和原子写入。AI 不可用时，服务端尝试确定性表格投影，失败则返回可操作错误，不静默落库。

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, existing `AIService`/`project.init.analysis`, openpyxl/xlrd text parser, React + TypeScript, Vitest, pytest.

---

## Task 1: Lock the AI import contract with backend tests

**Files:**
- Create: `bowei_ai_dashboard/tests/test_project_plan_ai_import.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`

- [x] **Step 1: Write failing contract tests**

Add tests that define the public behavior before implementation. Each test must
construct a real `TestClient` request or a real draft object, assert the exact
status/result fields named below, and query the isolated test database after the
call to prove the preview path did not create business rows:

- `test_ai_preview_accepts_semantic_work_plan_without_fixed_table_name`: upload a
  multipart workbook with `主要工作 / 目标 / 验收标准与关键成果 / 关键任务 /
  推进流程`; assert HTTP 200, five normalized task groups, and no `Project` row.
- `test_ai_preview_can_use_existing_project_context`: seed one project and one
  task; pass its id; assert the response uses that project name and reports the
  existing task as duplicate context without changing its row count.
- `test_ai_preview_falls_back_to_deterministic_workbook_projection`: make the
  AI capability raise `AICapabilityNotConfigured`; upload a recognized xlsx;
  assert HTTP 200 and `fallback_mode == "deterministic"`.
- `test_ai_draft_to_batch_rows_preserves_hierarchy_and_evidence`: build one
  `ProjectPlanAiImportDraft` with one task and three subtasks; assert three
  `BatchImportRow` values, shared `workstream`, distinct `key_task`, and source
  location in `notes`.
- `test_ai_preview_never_mutates_database`: assert project, task, subtask, and
  issue counts are identical before and after preview, while invocation-log
  metadata may increase when a mocked AI call succeeds.

- [x] **Step 2: Run the focused tests and verify RED**

```powershell
cd D:\项目整体备份\mowayspos-next-task\bowei_ai_dashboard
..\.venv\Scripts\python.exe -m pytest tests/test_project_plan_ai_import.py -q
```

Expected: FAIL because the AI import preview contract and conversion service do not exist yet.

- [x] **Step 3: Define typed response schemas only**

Add bounded Pydantic schemas for an optional `project_name`, optional `target_project_id`, evidence, project profile, tasks, warnings, source files, provider/model name, and `fallback_mode`. Reject unknown fields and cap text/list sizes so an AI response cannot expand into an unbounded response.

- [x] **Step 4: Run the focused tests again**

Run the same pytest command. Expected: still FAIL at missing service/route assertions, with no schema construction errors.

- [x] **Step 5: Commit the contract**

```powershell
git add bowei_ai_dashboard/tests/test_project_plan_ai_import.py bowei_ai_dashboard/app/schemas.py
git commit -m "test: define ai work plan import contract"
```

## Task 2: Implement the backend AI preview service

**Files:**
- Create: `bowei_ai_dashboard/app/services/project_plan_ai_import.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_file_parser.py`
- Test: `bowei_ai_dashboard/tests/test_project_plan_ai_import.py`

- [x] **Step 1: Add file-format coverage tests**

Extend the red tests with `.csv`, `.tsv`, and `.xlsx` fixtures. Assert that `.csv` and `.tsv` use the bounded `SourceChunk` contract and `.xlsx` preserves worksheet range locations.

- [x] **Step 2: Implement parser extension support**

Update `parse_project_init_file()` so `.csv` and `.tsv` are accepted and routed through the bounded text reader. Keep the existing size, archive, worksheet, and extracted-character limits unchanged.

- [x] **Step 3: Implement review-only analysis**

Add `analyze_project_plan_upload(db, content, original_name, *, actor,
project_name="", target_project_id=None) -> ProjectPlanAiImportDraft`. The
function must validate extension/25 MiB size, use a temporary directory, parse
with `parse_project_init_file()`, build active-person and existing-task context,
call `generate_project_init_draft()` with `AIService(db)` and
`AIInvocationContext(actor=actor, resource_type="project_plan_import")`, and
never create project records. If AI is unavailable and sources are deterministic
spreadsheets, call `generate_structured_project_init_draft()` and mark
`fallback_mode="deterministic"`; otherwise return a safe error.

- [x] **Step 4: Implement draft-to-import conversion**

Add `draft_to_batch_rows(draft, *, project_name_override="") ->
list[schemas.BatchImportRow]`. Map task title to `workstream`, task goal to
`key_achievement`, acceptance criteria to `completion_standard`,
process/evidence to `notes`, and each subtask title to `key_task`. Prefer
subtask owner/date/status, then parent task values. Reject empty
project/workstream/key-task values before conversion.

- [x] **Step 5: Run backend tests to verify GREEN**

```powershell
cd D:\项目整体备份\mowayspos-next-task\bowei_ai_dashboard
..\.venv\Scripts\python.exe -m pytest tests/test_project_plan_ai_import.py -q
```

Expected: all focused tests pass without changing the production database.

- [x] **Step 6: Commit the service**

```powershell
git add bowei_ai_dashboard/app/services/project_plan_ai_import.py bowei_ai_dashboard/app/services/project_init_file_parser.py bowei_ai_dashboard/tests/test_project_plan_ai_import.py
git commit -m "feat: add review-only ai work plan analysis"
```

## Task 3: Expose authenticated preview and safe import endpoints

**Files:**
- Create: `bowei_ai_dashboard/app/routers/project_plan_ai_import.py`
- Modify: `bowei_ai_dashboard/app/main.py`
- Modify: `bowei_ai_dashboard/app/routers/projects.py` only for shared authorization/conversion
- Test: `bowei_ai_dashboard/tests/test_project_plan_ai_import.py`

- [x] **Step 1: Add route tests**

Cover multipart preview, global batch-import permission, no database mutation during preview, bounded malformed-AI errors, confirmed apply delegation to `import_project_plan_rows`, and duplicate re-apply counts.

- [x] **Step 2: Implement preview route**

Use `UploadFile`/`File`, `authorize_global_project_action(current_user, A_BATCH_IMPORT, db)`, and the service from Task 2. Keep the invocation context resource type `project_plan_import`; never expose API keys or raw upstream errors.

- [x] **Step 3: Implement apply route**

Accept only confirmed normalized `BatchImportRow` values, enforce the same permission, and call `import_project_plan_rows`. Do not trust client-supplied AI IDs, confidence, duplicate flags, or evidence as authority.

- [x] **Step 4: Register the router and run tests**

```powershell
cd D:\项目整体备份\mowayspos-next-task\bowei_ai_dashboard
..\.venv\Scripts\python.exe -m pytest tests/test_project_plan_ai_import.py tests/test_project_permission_characterization.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the API**

```powershell
git add bowei_ai_dashboard/app/routers/project_plan_ai_import.py bowei_ai_dashboard/app/main.py bowei_ai_dashboard/app/routers/projects.py bowei_ai_dashboard/tests/test_project_plan_ai_import.py
git commit -m "feat: expose ai work plan import preview api"
```

## Task 4: Add frontend API types and pure draft conversion tests

**Files:**
- Create: `frontend/src/api/projectPlanAiImport.ts`
- Create: `frontend/src/features/settings/projectPlanAiImportDraft.ts`
- Create: `frontend/src/features/settings/projectPlanAiImportDraft.test.ts`

- [x] **Step 1: Write failing frontend tests**

Test FormData construction, target/project-name options, task/subtask-to-row conversion, parent fallback for blank subtask values, evidence notes, missing-field errors, and preservation of user edits.

- [x] **Step 2: Implement API decoder and calls**

Add typed `previewAiProjectPlan(file, options)` and `applyAiProjectPlan(rows)` functions, validating response shape at the boundary in the same style as `projectInitAi.ts`. Distinguish AI unavailable from validation errors.

- [x] **Step 3: Implement pure draft conversion**

Keep conversion outside the page component. Use `BatchImportRow`, map project profile/tasks/subtasks/status/dates/owners/collaborators/evidence, and retain evidence source labels in notes.

- [x] **Step 4: Run focused frontend tests**

```powershell
cd D:\项目整体备份\mowayspos-next-task\frontend
npm run test:unit -- --run src/features/settings/projectPlanAiImportDraft.test.ts
```

Expected: PASS after minimal implementation.

- [x] **Step 5: Commit frontend contracts**

```powershell
git add frontend/src/api/projectPlanAiImport.ts frontend/src/features/settings/projectPlanAiImportDraft.ts frontend/src/features/settings/projectPlanAiImportDraft.test.ts
git commit -m "feat: add ai work plan import frontend contract"
```

## Task 5: Build the import review experience

**Files:**
- Create: `frontend/src/features/settings/ProjectPlanAiImportDialog.tsx`
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx`
- Modify: the existing project-management styles file if needed
- Create: `frontend/src/features/settings/ProjectPlanAiImportDialog.test.tsx` if supported by the test setup
- Modify: `frontend/tests/projectPlanImportUiContract.test.mjs`

- [x] **Step 1: Add UI contract tests**

Assert file picker plus paste area, existing-project selector/new-project name, AI analyzing state, AI/fallback indicator, counts, warnings/unmapped fields, editable normalized rows, confirmation disabled on errors, and no write before confirmation.

- [x] **Step 2: Implement the dialog state machine**

Use only:

```text
idle → reading → analyzing → review → importing → success
                         ↘ error
```

Keep the draft open after analysis, preserve edits when the target changes, and show an explicit fallback notice.

- [x] **Step 3: Implement the review table**

Use a compact operations layout matching the existing project-management surface: progress header, source/model badge, warning strip, counts, then an editable table grouped by workstream. Put evidence/source location in expandable detail cells.

- [x] **Step 4: Wire file upload, paste, preview, and apply**

File upload uses the AI preview endpoint. Paste creates a UTF-8 `.tsv` `File` and uses the same endpoint. Apply sends only the edited normalized rows to the atomic import service.

- [x] **Step 5: Run frontend tests and build**

```powershell
cd D:\项目整体备份\mowayspos-next-task\frontend
npm run test:unit -- --run src/features/settings/projectPlanAiImportDraft.test.ts src/features/settings/ProjectPlanAiImportDialog.test.tsx
node --test tests/projectPlanImportUiContract.test.mjs
npm run build
```

Expected: focused tests and build pass; pre-existing bundle-size warnings may remain unchanged.

- [ ] **Step 6: Commit the review UI**

```powershell
git add frontend/src/features/settings/ProjectPlanAiImportDialog.tsx frontend/src/features/settings/ProjectsMgmtSection.tsx frontend/tests/projectPlanImportUiContract.test.mjs
git commit -m "feat: add ai work plan import review dialog"
```

## Task 6: Verify real formats and regression behavior

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_project_plan_ai_import.py`
- Modify: `frontend/src/features/settings/projectPlanAiImportDraft.test.ts`
- Modify: `docs/full-flow-manual-acceptance-runbook.md`
- Modify: `docs/full-flow-manual-acceptance-checklist.md`

- [ ] **Step 1: Add fixture-driven coverage**

Cover the supplied `主要工作 / 目标 / 验收标准与关键成果 / 关键任务 / 推进流程` shape, no-title input, project-column-only input, renamed fields such as `工作包 / 主责人 / 执行事项`, merged blank cells, two sheets, and repeated import.

- [x] **Step 2: Run backend regression tests**

```powershell
cd D:\项目整体备份\mowayspos-next-task\bowei_ai_dashboard
..\.venv\Scripts\python.exe -m pytest tests/test_project_plan_ai_import.py tests/test_project_work_plan_import.py tests/test_project_permission_characterization.py -q
```

- [x] **Step 3: Run frontend regression tests**

```powershell
cd D:\项目整体备份\mowayspos-next-task\frontend
npm run test:all
npm run build
```

- [x] **Step 4: Run diff and workspace checks**

```powershell
cd D:\项目整体备份\mowayspos-next-task
git diff --check
git status --short
git diff HEAD~6..HEAD --stat
```

Confirm no production database or supplied workbook is committed.

- [x] **Step 5: Update the manual runbook**

Document the AI flow, AI-unavailable fallback, low-confidence/manual correction, duplicate re-import, and supplied workbook shape.

- [x] **Step 6: Commit verification docs**

```powershell
git add bowei_ai_dashboard/tests/test_project_plan_ai_import.py frontend/src/features/settings/projectPlanAiImportDraft.test.ts docs/full-flow-manual-acceptance-runbook.md docs/full-flow-manual-acceptance-checklist.md
git commit -m "test: cover ai work plan import formats"
```

## Task 7: Final verification and handoff

- [x] **Step 1: Run the complete relevant verification set fresh**

```powershell
cd D:\项目整体备份\mowayspos-next-task\bowei_ai_dashboard
..\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm run test:all
npm run build
cd ..
git diff --check
git status --short
```

- [x] **Step 2: Inspect the final implementation**

Verify preview does not mutate projects/tasks, apply is the only write path, existing batch import behavior is unchanged, AI invocation logs use `project_plan_import`, and the UI never claims AI success when fallback/manual mode was used.

- [x] **Step 3: Commit only after verification**

Do not commit the local database backup or the supplied workbook. Commit only intended source/docs/test changes after the fresh checks pass.

- [ ] **Step 4: Report the result**

Report the implemented flow, exact files/commits, tests, and any remaining limitation. State whether final acceptance used a configured AI model or deterministic fallback; do not imply a live AI call was made if the environment had no configured model.
