# Work Plan Table Import Implementation Plan

> **For agentic workers:** This plan is executed inline in the current isolated worktree. The repository collaboration policy forbids creating or delegating subagents.

**Goal:** Make the Project Management batch importer accept the complete exported work plan table and persist the full Project → Workstream → Key Task hierarchy.

**Architecture:** Extract tabular parsing into a tested frontend module that normalizes both legacy and complete headers, carries forward merged-cell blanks, and returns normalized rows. Extend the backend import payload and transaction so each workstream becomes a `Task` and each key task becomes a `SubTask`, with validation and duplicate skipping before commit.

**Tech Stack:** React/TypeScript, Vitest, Node contract tests, FastAPI/Pydantic, SQLAlchemy, pytest, SQLite test sessions.

---

### Task 1: Add failing frontend parser tests

**Files:**
- Create: `frontend/src/features/settings/projectPlanImport.ts`
- Create: `frontend/tests/projectPlanImport.test.mjs`

- [ ] **Step 1: Define the expected normalized row contract in the test.**

The test input must use the exact exported headers from `PLAN_TABLE_BUSINESS_HEADERS`, with the second data row omitting the project and workstream cells to model merged Excel cells. Assert that both rows contain the inherited project/workstream and that start/end dates are combined into `plan_time`.

- [ ] **Step 2: Add the legacy-format compatibility test.**

Use headers `项目、关键任务、负责人、统筹人、计划时间、当前状态、问题` and assert that the parser creates a same-name workstream and key task so the old importer behavior remains available.

- [ ] **Step 3: Add invalid-row tests.**

Assert that rows missing project, workstream, or key task are returned in `errors` with their one-based source row number and are not included in `rows`.

- [ ] **Step 4: Run the tests and verify they fail for the missing module.**

Run: `npm run test:unit -- --run tests/projectPlanImport.test.mjs` from `frontend`.

Expected: FAIL because `projectPlanImport.ts` does not yet exist.

### Task 2: Implement normalized frontend parsing

**Files:**
- Modify: `frontend/src/features/settings/projectPlanImport.ts`
- Test: `frontend/tests/projectPlanImport.test.mjs`

- [ ] **Step 1: Implement header aliases and normalized types.**

Export `ProjectPlanImportRow`, `ProjectPlanImportError`, `ProjectPlanImportResult`, and `parseProjectPlanImportText(text: string)`. Map `项目/阶段`, `重点工作`, `关键任务`, `负责人/责任人`, `计划时间`, `计划开始时间`, `计划结束时间`, `协同/协同人/成员`, `状态/当前状态`, `完成情况`, `备注/问题` to one normalized shape.

- [ ] **Step 2: Implement row parsing with carry-forward values.**

Trim tab-separated cells, remember the latest non-empty project and workstream values, combine start/end into `plan_time` when no explicit plan time exists, and classify missing required fields as errors instead of silently dropping them.

- [ ] **Step 3: Run the parser tests and verify they pass.**

Run: `npm run test:unit -- --run tests/projectPlanImport.test.mjs` from `frontend`.

Expected: PASS for complete-format, legacy-format, carry-forward, and invalid-row cases.

### Task 3: Integrate the parser and preview into Project Management

**Files:**
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx`
- Modify: `frontend/src/api/projects.ts`
- Create: `frontend/tests/projectPlanImportUiContract.test.mjs`

- [ ] **Step 1: Replace the page-local parser and row type.**

Import `parseProjectPlanImportText` and use its normalized result. Remove the duplicated `IMPORT_COL_MAP` and `parseImportText` implementation.

- [ ] **Step 2: Expand the preview state.**

Track parser errors and show counts for valid rows, distinct workstreams, key tasks, and invalid rows. Render the actual normalized fields in the preview and disable confirmation while blocking errors exist.

- [ ] **Step 3: Add the UI contract assertions.**

Assert that the component imports the parser, displays “重点工作”和“关键任务” counts, displays row errors, and submits normalized rows through the batch import API.

- [ ] **Step 4: Run the frontend unit and contract tests.**

Run: `npm run test:all` from `frontend`.

Expected: PASS with the existing suite plus the new parser/UI contract tests.

### Task 4: Add failing backend hierarchy and duplicate tests

**Files:**
- Create: `bowei_ai_dashboard/tests/test_project_work_plan_import.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`

- [ ] **Step 1: Write the complete-format payload test.**

Use an in-memory SQLite session with the existing project-permission seed. Submit two rows for one workstream and one row for a second workstream. Assert the result counts one project, two tasks, three subtasks, and that each subtask points to its expected task.

- [ ] **Step 2: Write the duplicate and atomicity tests.**

Import the same payload twice and assert the second result reports skipped rows without increasing `Task` or `SubTask` counts. Submit one valid row and one row missing a required field and assert the endpoint raises a validation error and leaves all counts unchanged.

- [ ] **Step 3: Run the new backend tests and verify they fail.**

Run: `$env:APP_ENV='test'; $env:ALLOW_TEST_MEMORY_DATABASE='I_UNDERSTAND_THIS_IS_TEST_ONLY'; $env:DATABASE_URL='sqlite:///:memory:'; .\.venv\Scripts\python.exe -m pytest tests/test_project_work_plan_import.py -q` from `bowei_ai_dashboard`.

Expected: FAIL because the schema and importer do not yet create `SubTask` hierarchy or reject partial imports.

### Task 5: Implement backend normalized import and transaction safety

**Files:**
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Modify: `bowei_ai_dashboard/app/routers/projects.py`
- Create: `bowei_ai_dashboard/app/services/project_plan_import.py`

- [ ] **Step 1: Add the normalized backend row fields.**

Extend `BatchImportRow` with `workstream`, `project_objective`, `plan_start`, `plan_end`, and `notes`, while retaining existing fields for compatibility.

- [ ] **Step 2: Create a focused import service.**

Implement `import_project_plan_rows(db, rows, current_user)`. It must validate required fields before mutation, resolve or create projects, reuse workstreams by project/name, skip existing key tasks by parent/name, create `SubTask` rows with `assignee`, `plan_time`, `status`, `completion_criteria`, and `notes`, and return created/skipped/error counts. Use `db.begin_nested()` or an explicit rollback path so no partial data remains on validation failure.

- [ ] **Step 3: Keep the router as an authorization boundary.**

Have `batch_import_projects` authorize the caller and delegate all parsing-independent business logic to the service. Preserve the existing response keys and add `subtasks_created` and `duplicates_skipped`.

- [ ] **Step 4: Run the backend tests and verify they pass.**

Run the command from Task 4.

Expected: PASS for hierarchy, duplicate handling, legacy rows, issue creation, and atomic validation.

### Task 6: Verify end-to-end behavior and update documentation

**Files:**
- Modify: `docs/full-flow-manual-acceptance-runbook.md`
- Modify: `docs/full-flow-manual-acceptance-checklist.md`
- Modify: `docs/superpowers/audits/2026-09-13-system-stabilization-completion-audit.md`

- [ ] **Step 1: Run focused frontend tests.**

Run the parser/UI tests and `npm run test:all` from `frontend`.

- [ ] **Step 2: Run focused backend tests.**

Run the new importer tests plus the existing project permission characterization tests from `bowei_ai_dashboard`.

- [ ] **Step 3: Run a real exported-table simulation in an isolated test database.**

Copy the 14-column work plan header and two data rows into the parser, send the normalized rows through the backend service, then query `Project`, `Task`, and `SubTask` counts. Confirm the workstream/key-task names, assignees, plan time, collaborator notes, and issue text.

- [ ] **Step 4: Update acceptance documentation.**

Document the complete-table paste path, preview checks, duplicate behavior, and expected hierarchy in the runbook and checklist.

- [ ] **Step 5: Run the relevant regression suite and inspect the diff.**

Run backend project/import tests, frontend `npm run test:all`, `npm run build`, and `git diff --check`. Confirm no production database file changed.

- [ ] **Step 6: Commit the implementation.**

Use commit message: `feat: support complete work plan table import`.
