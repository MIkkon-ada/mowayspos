# Remaining Changes Review and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely turn the remaining mixed local changes into independently verified commits, exclude local artifacts, and push only release-ready commits.

**Architecture:** Treat each remaining subsystem as an isolated release unit. For every unit, inspect its exact diff, run its focused tests, stage only its owned hunks, review the staged diff, commit, and leave unrelated working-tree changes untouched. Production-facing changes receive an additional migration and deployment-contract gate before push.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy, Alembic, pytest, React 19, TypeScript, Vite, Node test runner, Docker Compose, GitHub Actions.

---

### Task 1: Freeze the post-meeting baseline

**Files:**
- Verify only: repository working tree
- Reference commit: `ae473b8 feat: add meeting kickoff and revision traceability`

- [ ] **Step 1: Confirm the meeting commit remains the current baseline**

Run:

```powershell
git log -1 --oneline
```

Expected: output begins with `ae473b8`.

- [ ] **Step 2: Record the remaining working-tree inventory**

Run:

```powershell
git status --short
git diff --stat
git diff --check
```

Expected: meeting files committed in `ae473b8` do not appear as modified; `git diff --check` reports no code whitespace errors that block staging.

- [ ] **Step 3: Confirm no files are accidentally staged**

Run:

```powershell
git diff --cached --name-only
```

Expected: no output.

### Task 2: Package achievement attachments and work-report evidence

**Files:**
- Create: `bowei_ai_dashboard/app/routers/achievement_attachments.py`
- Create: `bowei_ai_dashboard/migrations/versions/e8f9a0b1c2d3_add_achievement_attachments.py`
- Create: `bowei_ai_dashboard/tests/test_achievement_attachments.py`
- Create: `bowei_ai_dashboard/tests/test_work_report_achievement_attachment_flow.py`
- Create: `frontend/tests/achievementAttachmentsStructure.test.mjs`
- Modify: `bowei_ai_dashboard/app/main.py`
- Modify: `bowei_ai_dashboard/app/routers/achievement_submissions.py`
- Modify: `bowei_ai_dashboard/app/routers/confirmations.py`
- Modify: `docker-compose.prod.yml`
- Modify: `.gitignore`
- Modify: `frontend/src/api/achievements.ts`
- Modify: `frontend/src/pages/AchievementsPage.tsx`
- Modify: `frontend/src/types.ts` — stage only the `attachment_ids` hunk
- Modify: `frontend/src/features/voice-update/VoiceUpdateResultCard.tsx`
- Modify: `frontend/src/features/voice-update/VoiceUpdateTaskReportsSection.tsx`
- Modify: `frontend/src/features/voice-update/voiceUpdateResultTypes.ts`
- Modify: `frontend/src/api/updates.ts`
- Test: `frontend/tests/achievementLibraryOverview.test.mjs`
- Document: `docs/achievement-file-upload-plan.md`
- Document: `docs/superpowers/plans/2026-07-29-achievement-attachments.md`

- [ ] **Step 1: Review the attachment diff for storage and authorization boundaries**

Run:

```powershell
git diff -- bowei_ai_dashboard/app/routers/achievement_attachments.py bowei_ai_dashboard/app/routers/achievement_submissions.py bowei_ai_dashboard/app/routers/confirmations.py docker-compose.prod.yml frontend/src/api/achievements.ts frontend/src/pages/AchievementsPage.tsx
```

Expected: uploads are project-scoped, authorization is enforced server-side, soft deletion does not expose deleted blobs, and the production mount is `${MOWAYS_DATA_ROOT}/achievement-attachments`.

- [ ] **Step 2: Run attachment backend tests**

Run from `bowei_ai_dashboard`:

```powershell
python -m pytest tests/test_achievement_attachments.py tests/test_work_report_achievement_attachment_flow.py tests/test_ai_confirm_related_subtask_writeback.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run attachment frontend tests**

Run from `frontend`:

```powershell
node --test tests/achievementAttachmentsStructure.test.mjs tests/achievementLibraryOverview.test.mjs tests/workReportFlowPage.test.mjs
```

Expected: all tests pass.

- [ ] **Step 4: Verify production contracts and build**

Run:

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_production_runtime_contract.py tests/test_production_deployment_contract.py -q
Set-Location ..\frontend
npm run build
Set-Location ..
```

Expected: production contract tests pass and Vite build exits with code 0.

- [ ] **Step 5: Stage only the attachment unit and review it**

Run `git add` with the exact files listed in this task, then run:

```powershell
git diff --cached --name-only
git diff --cached --check
git diff --cached --stat
```

Expected: no meeting, task-management, LLM, database, WAV, snapshot, or build-artifact files are staged.

- [ ] **Step 6: Commit the attachment unit**

Run:

```powershell
git commit -m "feat: add achievement attachment evidence flow"
```

Expected: one commit containing only attachment and work-report evidence files.

### Task 3: Package task-management execution and plan-table views

**Files:**
- Create: `frontend/src/components/task-management/ExecutionProgressView.tsx`
- Create: `frontend/src/components/task-management/KeyTaskExecutionDetailView.tsx`
- Create: `frontend/src/components/task-management/PlanTableView.tsx`
- Create: `frontend/tests/keyTaskExecutionDetailLayout.test.mjs`
- Modify: `frontend/src/components/task-management/PlanTableViewV2.tsx`
- Modify: `frontend/src/components/task-management/planTableExcelV2.css`
- Modify: `frontend/src/pages/TaskManagementPage.tsx`
- Modify: `frontend/src/api/subtasks.ts`
- Modify: `bowei_ai_dashboard/app/routers/subtasks.py`
- Modify: `frontend/tests/workProgressExcelView.test.mjs`
- Modify: `bowei_ai_dashboard/tests/test_work_progress_plan_table_frontend.py`
- Document: `docs/superpowers/plans/2026-07-28-key-task-detail.md`

- [ ] **Step 1: Inspect task view ownership and read/write boundaries**

Run:

```powershell
git diff -- frontend/src/pages/TaskManagementPage.tsx frontend/src/components/task-management/PlanTableViewV2.tsx frontend/src/api/subtasks.ts bowei_ai_dashboard/app/routers/subtasks.py
```

Expected: archived projects remain read-only, key-task details reuse existing APIs, and no new global write path bypasses project permissions.

- [ ] **Step 2: Run backend structural tests**

Run from `bowei_ai_dashboard`:

```powershell
python -m pytest tests/test_work_progress_plan_table_frontend.py tests/test_project_close_request_model.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run frontend task-view tests and build**

Run from `frontend`:

```powershell
node --test tests/workProgressExcelView.test.mjs tests/keyTaskExecutionDetailLayout.test.mjs
npm run build
```

Expected: tests pass and build exits with code 0.

- [ ] **Step 4: Browser acceptance**

Verify in the local app:

1. Open an active project in 工作推进表.
2. Switch between execution and plan-table views.
3. Open a key-task detail.
4. Confirm archived projects show no create/edit controls.
5. Confirm table search and zoom do not lose the selected project.

Expected: no white screen, navigation loss, or unauthorized write control.

- [ ] **Step 5: Stage, inspect, and commit**

Run:

```powershell
git diff --cached --check
git diff --cached --name-only
git commit -m "feat: add task execution and plan table views"
```

Expected: the commit contains only task-management files.

### Task 4: Package confirmation-center, issue, and navigation redesign

**Files:**
- Modify: `frontend/src/layouts/AppLayout.tsx`
- Modify: `frontend/src/pages/ConfirmPage.tsx`
- Modify: `frontend/src/pages/IssuesPage.tsx`
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `bowei_ai_dashboard/tests/test_confirm_*.py`
- Modify: `bowei_ai_dashboard/tests/test_confirmation_*.py`
- Modify: `bowei_ai_dashboard/tests/test_issue_*.py`
- Create: `frontend/tests/issueProjectBadge.test.mjs`
- Modify: `frontend/tests/authFlow.test.mjs`
- Modify: `frontend/tests/sidebarCompactLayout.test.mjs`

- [ ] **Step 1: Review deleted test assertions before accepting the redesign**

Run:

```powershell
git diff --numstat -- bowei_ai_dashboard/tests/test_confirm_*.py bowei_ai_dashboard/tests/test_confirmation_*.py bowei_ai_dashboard/tests/test_issue_*.py
git diff -- bowei_ai_dashboard/tests/test_confirmation_coordinator_view_frontend.py bowei_ai_dashboard/tests/test_issue_member_view_frontend.py
```

Expected: removed assertions correspond to intentionally removed UI concepts; permission and write-path assertions remain covered elsewhere. If coverage disappeared without replacement, stop this task and restore equivalent assertions before staging.

- [ ] **Step 2: Run confirmation and issue regression tests**

Run from `bowei_ai_dashboard`:

```powershell
python -m pytest tests/test_confirm_center_reviewer_scope_frontend.py tests/test_confirm_center_role_scope_frontend.py tests/test_confirm_coach_view_frontend.py tests/test_confirmation_card_coordinator_frontend.py tests/test_confirmation_coordinator_view_frontend.py tests/test_confirmation_submission_feedback_frontend.py tests/test_confirmation_submission_level_frontend.py tests/test_confirmation_write_scope_frontend.py tests/test_issue_action_driven_flow_frontend.py tests/test_issue_coordinating_status.py tests/test_issue_create_form_scope_frontend.py tests/test_issue_member_view_frontend.py tests/test_issue_role_visibility_scope.py tests/test_project_issue_kanban_frontend.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run frontend navigation tests and build**

Run from `frontend`:

```powershell
node --test tests/authFlow.test.mjs tests/sidebarCompactLayout.test.mjs tests/issueProjectBadge.test.mjs
npm run build
```

Expected: all tests pass and build exits with code 0.

- [ ] **Step 4: Browser acceptance by role**

Verify at least:

1. Super administrator can open dashboard, confirmation center, issues, and settings.
2. Ordinary member lands in personal tasks and does not see privileged write actions.
3. Confirmation queue selection keeps the middle and action panels synchronized.
4. Issue pages preserve project context and role visibility.

Expected: role boundaries match backend permissions and navigation never grants authority by URL alone.

- [ ] **Step 5: Stage, inspect, and commit**

Run:

```powershell
git diff --cached --check
git diff --cached --stat
git commit -m "feat: refine confirmation and issue workspaces"
```

Expected: one isolated UI and permission-contract commit.

### Task 5: Package login and database compatibility changes

**Files:**
- Create: `bowei_ai_dashboard/tests/test_wecom_login_urls.py`
- Create: `frontend/tests/loginPageVisualStructure.test.mjs`
- Create: `bowei_ai_dashboard/migrations/versions/1b2c3d4e5f6a_restore_project_objectives.py`
- Modify: `bowei_ai_dashboard/migrations/versions/c8e4f2a7d901_restore_current_project_profile_columns.py`
- Modify: `bowei_ai_dashboard/tests/test_sqlite_to_postgres_migration.py`
- Modify: `frontend/tests/projectContextFallback.test.mjs`
- Modify: `frontend/tests/projectDetailLoading.test.mjs`
- Do not commit: `login.yaml`, `login-filled.yml`, `login-snap.yml`, `prod-login.yaml`, `prod-login-filled.yaml`

- [ ] **Step 1: Verify migration graph**

Run from the repository root:

```powershell
python -m alembic -c bowei_ai_dashboard/alembic.ini heads
python -m alembic -c bowei_ai_dashboard/alembic.ini branches
```

Expected: exactly one migration head and no unmerged branch created by compatibility migrations.

- [ ] **Step 2: Run authentication and migration tests**

Run from `bowei_ai_dashboard`:

```powershell
python -m pytest tests/test_wecom_login_urls.py tests/test_auth_import_contract.py tests/test_sqlite_to_postgres_migration.py tests/test_alembic_database_safety.py -q
```

Expected: all non-environment integration tests pass; PostgreSQL-only skips are documented as skips.

- [ ] **Step 3: Run login frontend test and build**

Run from `frontend`:

```powershell
node --test tests/loginPageVisualStructure.test.mjs tests/authFlow.test.mjs tests/projectContextFallback.test.mjs tests/projectDetailLoading.test.mjs
npm run build
```

Expected: tests pass and build exits with code 0.

- [ ] **Step 4: Stage only source, migrations, and tests**

Expected: no YAML browser snapshots or database files are staged.

- [ ] **Step 5: Commit compatibility changes**

Run:

```powershell
git commit -m "fix: preserve login and project compatibility"
```

Expected: one compatibility commit.

### Task 6: Isolate LLM production configuration for a separate decision

**Files:**
- Modify candidate: `bowei_ai_dashboard/app/routers/llm_config.py`
- Future design candidates: `bowei_ai_dashboard/app/llm_config.py`, `bowei_ai_dashboard/app/settings.py`, `frontend/src/features/settings/LLMConfigSection.tsx`, `frontend/src/pages/VoiceUpdatePage.tsx`

- [ ] **Step 1: Keep the current LLM router change out of the preceding commits**

Run:

```powershell
git status --short bowei_ai_dashboard/app/routers/llm_config.py
```

Expected: the file remains modified and unstaged until the persistence design is approved.

- [ ] **Step 2: Confirm the required behavior before implementation**

Required priority:

```text
explicit frontend provider > administrator default provider > code fallback
```

Required persistence behavior:

```text
frontend/backend image replacement must not erase provider settings or API credentials
```

- [ ] **Step 3: Create and approve a dedicated LLM configuration design**

The design must choose between encrypted database storage and a persistent host-mounted secret file, define production key rotation, and define deployment initialization as “create only when absent.” Do not implement or commit the current production restriction until this design is approved.

### Task 7: Quarantine local-only artifacts without deleting user data

**Files to keep untracked:**
- `local_backup.db`
- `bowei_ai_dashboard/bowei_ai_dashboard.db.backup-before-meeting-revisions-20260803`
- `frontend/dist.zip`
- `_inspect_db.py`
- `_tmp_query.py`
- `.superpowers/`
- `tmp/`
- `*.yml` and `*.yaml` browser snapshots at repository root

- [ ] **Step 1: Confirm none of the artifacts are staged**

Run:

```powershell
git diff --cached --name-only | Select-String -Pattern '(^tmp/|\.db$|dist\.zip|\.yml$|\.yaml$|^\.superpowers/|^_.*\.py$)'
```

Expected: no output.

- [ ] **Step 2: Extend `.gitignore` only for reproducible local artifacts**

Add narrowly scoped entries for generated ASR output, local browser snapshots, local database backups, and frontend archives. Do not ignore source tests, migrations, acceptance documents, or production configuration examples.

- [ ] **Step 3: Verify artifacts still exist locally**

Run:

```powershell
Test-Path local_backup.db
Test-Path tmp/asr-corpus-generated/manifest.json
Test-Path frontend/dist.zip
```

Expected: existing files remain on disk; this task does not delete them.

- [ ] **Step 4: Commit ignore rules separately**

Run:

```powershell
git commit -m "chore: ignore local test and inspection artifacts"
```

Expected: only `.gitignore` is committed.

### Task 8: Final integration gate and push decision

**Files:**
- Verify: all committed source and tests
- Do not include: Task 6 LLM change unless separately approved and committed

- [ ] **Step 1: Confirm the working tree contains only intentionally deferred files**

Run:

```powershell
git status --short
git log --oneline -8
```

Expected: no release source remains accidentally unstaged; deferred LLM work and intentionally retained local artifacts are explicitly identified.

- [ ] **Step 2: Run the backend integration gate**

Run from `bowei_ai_dashboard`:

```powershell
python -m compileall -q app
python -m pytest tests/test_production_runtime_contract.py tests/test_production_runtime_security.py tests/test_production_deployment_contract.py tests/test_auth_import_contract.py tests/test_database_safety_gate.py tests/test_alembic_database_safety.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run changed-feature backend tests**

Run the attachment, task, confirmation, issue, meeting, login, and migration test files listed in Tasks 2–5.

Expected: all tests pass; environment-dependent PostgreSQL tests may skip only with an explicit skip reason.

- [ ] **Step 4: Run the frontend integration gate**

Run from `frontend`:

```powershell
node --test tests/*.test.mjs
npm run build
```

Expected: all tests pass and build exits with code 0. The existing bundle-size warning is non-blocking unless a chunk exceeds the deployment platform limit.

- [ ] **Step 5: Review commits to be pushed**

Run:

```powershell
git log --oneline --decorate origin/HEAD..HEAD
git diff --stat origin/HEAD..HEAD
```

Expected: only reviewed commits appear; no API keys, databases, snapshots, WAV files, or build archives are included.

- [ ] **Step 6: Push the current branch only after explicit approval**

Run:

```powershell
git push -u origin codex/today-clean-20260724
```

Expected: push succeeds and GitHub Actions runs against the reviewed branch. Do not push directly to the production branch from this plan.
