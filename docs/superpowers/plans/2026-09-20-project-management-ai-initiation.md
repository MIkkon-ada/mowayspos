# Project Management AI Initiation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Do not dispatch subagents for this repository.

**Goal:** Make project-management AI analysis visible and trustworthy while keeping every project on the existing `draft → dispatched → owner submit → coach review → active` lifecycle.

**Architecture:** Use the existing project-init attachment and analysis-run APIs as the only AI source of truth. Add a visible project-management entry that either starts a draft-project analysis or opens the existing editable project-plan workspace; keep AI output review-only until it is applied to a local draft and later submitted through the existing owner-submit transaction. Remove the disconnected `/ai-plan-import/*` frontend path and clean the duplicated project-init modal branch.

**Tech Stack:** React 19, TypeScript, React Router, Vite, Testing Library, Vitest, FastAPI, SQLAlchemy, pytest.

---

## File map

### Frontend files

- Create `frontend-v2/src/features/settings/projectAiEntry.ts` for pure entry-mode, project eligibility, and AI status helpers.
- Create `frontend-v2/src/features/settings/projectAiEntry.test.ts` for the helper contract.
- Create `frontend-v2/src/features/settings/ProjectAiEntryDialog.tsx` for the visible AI mode selector and project selector.
- Create `frontend-v2/src/features/settings/ProjectAiEntryDialog.test.tsx` for dialog behavior.
- Modify `frontend-v2/src/features/settings/ProjectsMgmtSection.tsx` to expose the entry, open the correct workflow, and display recoverable AI status.
- Modify `frontend-v2/src/features/settings/ProjectInitModal.tsx` to retain one reachable modal implementation and expose the AI action consistently for draft projects.
- Modify `frontend-v2/src/features/settings/OwnerSubmitAiPanel.tsx` to show the AI understanding summary before the task draft and preserve review-only/apply behavior.
- Modify `frontend-v2/src/features/settings/OwnerSubmitModal.tsx` to restore a saved latest AI draft when an owner opens an editable plan.
- Modify `frontend-v2/src/pages/TaskManagementPage.tsx` to rename the existing-project task import entry.
- Remove or stop importing the disconnected `projectPlanAiImport*` files after replacement coverage exists.

### Backend files

- Modify `bowei_ai_dashboard/app/routers/project_init_ai.py` so review-only attachment upload and analysis-run creation support `draft`, `dispatched`, and `returned` projects.
- Add `bowei_ai_dashboard/tests/test_project_init_ai_draft_lifecycle.py` for draft-stage upload and lifecycle invariants.
- Extend existing project-init analysis tests when latest-run draft recovery changes.

### Documentation

- Approved design: `docs/superpowers/specs/2026-09-20-project-management-ai-initiation-design.md`.
- This implementation plan: `docs/superpowers/plans/2026-09-20-project-management-ai-initiation.md`.

## Task 1: Add the pure project-AI entry model

**Files:**
- Create: `frontend-v2/src/features/settings/projectAiEntry.ts`
- Test: `frontend-v2/src/features/settings/projectAiEntry.test.ts`

- [ ] **Step 1: Write failing helper tests**

Test that `draft`, `dispatched`, and `returned` are AI-editable; `pending_review` and `active` are not. Test labels `processing → AI 分析中`, `completed → 待复核`, `failed → 分析失败`, and tone `completed → violet`.

- [ ] **Step 2: Run the focused test and confirm it fails**

```powershell
npm run test:unit -- src/features/settings/projectAiEntry.test.ts
```

Expected: FAIL because the helper module does not exist.

- [ ] **Step 3: Implement the minimal helper module**

Export:

```ts
export type ProjectAiStatus = 'queued' | 'processing' | 'retrying' | 'completed' | 'partial_failed' | 'failed' | 'none'
export type ProjectAiStatusTone = 'neutral' | 'blue' | 'violet' | 'amber' | 'red'
export function isProjectAiEditable(project: Pick<Project, 'status'>): boolean
export function getProjectAiStatusLabel(status: ProjectAiStatus): string
export function getProjectAiStatusTone(status: ProjectAiStatus): ProjectAiStatusTone
```

Map `none` to `未开始`, `queued` to `排队中`, `processing` to `AI 分析中`, `retrying` to `重试中`, `completed` to `待复核`, `partial_failed` to `部分失败`, and `failed` to `分析失败`.

- [ ] **Step 4: Run the focused test and confirm it passes**

```powershell
npm run test:unit -- src/features/settings/projectAiEntry.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit the pure model**

```powershell
git add frontend-v2/src/features/settings/projectAiEntry.ts frontend-v2/src/features/settings/projectAiEntry.test.ts
git commit -m "feat: add project ai entry state model"
```

## Task 2: Remove the duplicate project-init modal implementation

**Files:**
- Modify: `frontend-v2/src/features/settings/ProjectInitModal.tsx:145-535`
- Modify: `frontend-v2/tests/projectInitModalLayout.test.mjs`

- [ ] **Step 1: Add a structural regression test**

Assert that `ProjectInitModal.tsx` contains exactly two `return createPortal(` occurrences: one for `ProjectInitModal` and one for `ProjectPeoplePickerPopover`. Also assert that the reachable modal contains `project-init-workbench`, `AI 分析立项资料`, `确认立项`, and `REQUIRED_TEAM_ROLES`.

- [ ] **Step 2: Run the structural test and confirm it fails**

```powershell
npm run test:contracts -- tests/projectInitModalLayout.test.mjs
```

Expected: FAIL because the file currently contains an unreachable second project-init portal branch.

- [ ] **Step 3: Delete only the unreachable old branch**

Remove the second `return createPortal(` block inside `ProjectInitModal`, from the old “Header - 新设计” implementation through its closing portal. Keep the first reachable modal implementation and the separate people-picker implementation.

- [ ] **Step 4: Run the structural and TypeScript checks**

```powershell
npm run test:contracts -- tests/projectInitModalLayout.test.mjs
npm run build
```

Expected: both commands pass.

- [ ] **Step 5: Commit the modal cleanup**

```powershell
git add frontend-v2/src/features/settings/ProjectInitModal.tsx frontend-v2/tests/projectInitModalLayout.test.mjs
git commit -m "refactor: remove unreachable project init modal"
```

## Task 3: Allow review-only AI analysis for draft projects

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/project_init_ai.py:49`
- Test: `bowei_ai_dashboard/tests/test_project_init_ai_draft_lifecycle.py`

- [ ] **Step 1: Write a backend integration test for draft attachment upload**

Create a temporary SQLite database, one active account/person, one `draft` project, and an owner project member. Upload a valid text file with the owner session to `/api/projects/1/init-attachments`. Assert status `201`, one persisted attachment, and unchanged project status `draft`. Also assert that an `active` project still returns `409` with `project lifecycle is not editable`.

- [ ] **Step 2: Run the focused test and confirm the draft case fails**

```powershell
pytest tests/test_project_init_ai_draft_lifecycle.py -q
```

Expected: FAIL for the draft upload because `draft` is not in the allowed lifecycle set.

- [ ] **Step 3: Expand only the review-only editable lifecycle set**

Change:

```python
_EDITABLE_LIFECYCLES = {"dispatched", "returned"}
```

to:

```python
_EDITABLE_LIFECYCLES = {"draft", "dispatched", "returned"}
```

Do not change analysis apply or any project/task/member write path. No lifecycle transition is added.

- [ ] **Step 4: Run focused backend regression tests**

```powershell
pytest tests/test_project_init_ai_draft_lifecycle.py tests/test_project_init_attachments.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the backend lifecycle permission change**

```powershell
git add bowei_ai_dashboard/app/routers/project_init_ai.py bowei_ai_dashboard/tests/test_project_init_ai_draft_lifecycle.py
git commit -m "feat: allow review-only ai analysis for draft projects"
```

## Task 4: Build the visible AI entry dialog

**Files:**
- Create: `frontend-v2/src/features/settings/ProjectAiEntryDialog.tsx`
- Create: `frontend-v2/src/features/settings/ProjectAiEntryDialog.test.tsx`
- Modify: `frontend-v2/src/features/settings/projectAiEntry.ts`

- [ ] **Step 1: Write failing component tests**

Test that the dialog renders `AI 分析项目方案`, `为新项目生成方案`, and `完善已有项目方案`; calls `onStartNew`; lists only `draft`, `dispatched`, and `returned` projects; calls `onSelectProject(projectId)`; and never renders `批量导入`.

- [ ] **Step 2: Run the focused component test and confirm it fails**

```powershell
npm run test:unit -- src/features/settings/ProjectAiEntryDialog.test.tsx
```

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement the dialog**

Use:

```ts
type Props = {
  open: boolean
  projects: Project[]
  onClose: () => void
  onStartNew: () => void
  onSelectProject: (projectId: number) => void
}
```

Explain that AI only generates a reviewable draft and formal startup still requires owner submission and coach approval. Keep the project selector explicit.

- [ ] **Step 4: Run the focused test and confirm it passes**

```powershell
npm run test:unit -- src/features/settings/ProjectAiEntryDialog.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit the entry dialog**

```powershell
git add frontend-v2/src/features/settings/ProjectAiEntryDialog.tsx frontend-v2/src/features/settings/ProjectAiEntryDialog.test.tsx frontend-v2/src/features/settings/projectAiEntry.ts
git commit -m "feat: add visible project ai entry dialog"
```

## Task 5: Connect project management to the real AI workflow

**Files:**
- Modify: `frontend-v2/src/features/settings/ProjectsMgmtSection.tsx`
- Modify: `frontend-v2/tests/projectsWorkbenchStructure.test.mjs`

- [ ] **Step 1: Add the project-management contract assertions**

Assert that the section exposes `AI 分析项目方案`, uses `ProjectAiEntryDialog`, and does not reference `/api/projects/ai-plan-import/` or the old `批量导入` label.

- [ ] **Step 2: Run the contract test and confirm it fails**

```powershell
npm run test:contracts -- tests/projectsWorkbenchStructure.test.mjs
```

Expected: FAIL because project management still opens the disconnected batch-import dialog.

- [ ] **Step 3: Replace the disconnected entry with the real workflow**

Add local state for the AI entry dialog and the selected project workflow. Load the latest analysis run for eligible projects with the existing `getLatestInitAnalysisRun` API, and render status badges using the pure helper from Task 1. Replace the header action with `AI 分析项目方案`; selecting “为新项目生成方案” opens the existing draft-project init modal, while selecting an existing eligible project opens its editable project-init workflow. Do not call the old `/ai-plan-import/*` API.

- [ ] **Step 4: Verify the entry and production build**

```powershell
npm run test:contracts -- tests/projectsWorkbenchStructure.test.mjs
npm run build
```

Expected: both commands pass, and the project-management page has one visible AI entry with recoverable analysis status.

- [ ] **Step 5: Commit the project-management integration**

```powershell
git add frontend-v2/src/features/settings/ProjectsMgmtSection.tsx frontend-v2/tests/projectsWorkbenchStructure.test.mjs
git commit -m "feat: connect project management to project init ai workflow"
```

## Task 6: Show AI understanding before task review

**Files:**
- Create: `frontend-v2/src/features/settings/projectInitAiUnderstanding.ts`
- Create: `frontend-v2/src/features/settings/projectInitAiUnderstanding.test.ts`
- Modify: `frontend-v2/src/features/settings/OwnerSubmitAiPanel.tsx`
- Modify: existing `OwnerSubmitAiPanel` tests

- [ ] **Step 1: Write failing pure-model tests**

Test that a completed analysis is transformed into visible sections for background, objectives, expected outcomes, scope, people, dates, inference, and warnings; missing fields produce explicit “待确认” items rather than disappearing.

- [ ] **Step 2: Run the focused test and confirm it fails**

```powershell
npm run test:unit -- src/features/settings/projectInitAiUnderstanding.test.ts
```

Expected: FAIL because the understanding model does not exist.

- [ ] **Step 3: Implement the understanding model and panel stage**

Create a pure `buildProjectInitUnderstanding` mapper from the existing analysis-run payload. Update `OwnerSubmitAiPanel` so the first completed-result view is an explicit `AI 对项目的理解` summary, followed by a clear `继续核对方案` action that reveals the task draft. Keep warnings/evidence visible, and keep the panel review-only until the user explicitly applies the draft through the existing callback.

- [ ] **Step 4: Verify focused AI panel behavior**

```powershell
npm run test:unit -- src/features/settings/projectInitAiUnderstanding.test.ts src/features/settings/OwnerSubmitAiPanel.retry.test.tsx
npm run build
```

Expected: PASS; no analysis result is silently treated as a formal project start.

- [ ] **Step 5: Commit the understanding stage**

```powershell
git add frontend-v2/src/features/settings/projectInitAiUnderstanding.ts frontend-v2/src/features/settings/projectInitAiUnderstanding.test.ts frontend-v2/src/features/settings/OwnerSubmitAiPanel.tsx frontend-v2/src/features/settings/OwnerSubmitAiPanel.retry.test.tsx
git commit -m "feat: show ai understanding before project task review"
```

## Task 7: Recover saved AI drafts for owner submission

**Files:**
- Modify: `frontend-v2/src/features/settings/OwnerSubmitModal.tsx`
- Create: `frontend-v2/src/features/settings/OwnerSubmitModal.recovery.test.tsx`

- [ ] **Step 1: Add a failing recovery test**

Mock a completed or partial-failed latest analysis run for a `dispatched` or `returned` project. Assert that opening the owner-submit workbench restores the task draft locally and still requires the existing owner-submit action to persist it.

- [ ] **Step 2: Run the focused test and confirm it fails**

```powershell
npm run test:unit -- src/features/settings/OwnerSubmitModal.recovery.test.tsx
```

Expected: FAIL because the owner-submit workbench currently starts with an empty local task draft.

- [ ] **Step 3: Restore only the local draft**

Fetch the latest run only for `dispatched` and `returned` projects, convert its task draft through the existing task-shape conversion, and populate local `draftTasks`. Do not call `applyInitAnalysisRun` during recovery. Preserve the existing owner-submit transaction and lifecycle validation.

- [ ] **Step 4: Verify recovery and lifecycle boundaries**

```powershell
npm run test:unit -- src/features/settings/OwnerSubmitModal.recovery.test.tsx
npm run build
```

Expected: PASS; recovered AI content remains local until the owner submits for coach review.

- [ ] **Step 5: Commit draft recovery**

```powershell
git add frontend-v2/src/features/settings/OwnerSubmitModal.tsx frontend-v2/src/features/settings/OwnerSubmitModal.recovery.test.tsx
git commit -m "feat: recover project ai draft for owner submit"
```

## Task 8: Clarify existing-project task import and remove the disconnected path

**Files:**
- Modify: `frontend-v2/src/pages/TaskManagementPage.tsx`
- Modify: `frontend-v2/tests/projectPlanImportUiContract.test.mjs`
- Remove or stop importing: `frontend-v2/src/features/settings/ProjectPlanAiImportDialog.tsx`, `projectPlanAiImport.ts`, `projectPlanAiImportDraft.ts`, `projectPlanAiImportView.ts`, and obsolete tests after replacement coverage exists

- [ ] **Step 1: Update the UI contract**

Rename the existing-project task entry to `向已有项目补充任务` and make the contract test assert that it is distinct from `AI 分析项目方案`.

- [ ] **Step 2: Run the contract and full frontend tests**

```powershell
npm run test:contracts -- tests/projectPlanImportUiContract.test.mjs
npm run test:all
```

Expected: the label test initially fails, then the full suite passes after the rename and stale disconnected path is removed.

- [ ] **Step 3: Remove dead imports/files only after coverage is green**

Delete the old AI plan import modules if no source or test imports remain. Search the repository for `ai-plan-import` and require zero frontend references. Do not remove the real project-init AI API client.

- [ ] **Step 4: Commit the wording and cleanup**

```powershell
git add frontend-v2/src/pages/TaskManagementPage.tsx frontend-v2/tests/projectPlanImportUiContract.test.mjs
git add -u frontend-v2/src/features/settings
git commit -m "refactor: separate existing task import from project ai analysis"
```

## Task 9: Verify the complete closed loop

**Files:**
- No planned source changes; verification and manual acceptance only.

- [ ] **Step 1: Run backend verification**

```powershell
pytest bowei_ai_dashboard/tests/test_project_init_ai_draft_lifecycle.py bowei_ai_dashboard/tests/test_project_init_attachments.py -q
pytest bowei_ai_dashboard/tests -q
```

Expected: focused lifecycle tests and the backend suite pass.

- [ ] **Step 2: Run frontend verification**

```powershell
Set-Location frontend-v2
npm run test:all
npm run build
npm run check:bundle:dist
```

Expected: all frontend tests, production build, and bundle checks pass.

- [ ] **Step 3: Start the local system and inspect the real UI**

```powershell
Set-Location ..
.\start-v2-dev.ps1
```

Verify the frontend on port `6005`, the backend health endpoint, and that the browser console/network has no request to `/api/projects/ai-plan-import/*`.

- [ ] **Step 4: Exercise the lifecycle manually**

Use the actual UI in this order: `项目管理 → AI 分析项目方案 → 为新项目生成方案 → 创建 draft → 上传资料 → AI 对项目的理解 → 继续核对方案 → 应用草稿 → 下发 → 负责人恢复草稿 → 提交审核 → 教练批准 → active`. Also verify that an existing project uses `向已有项目补充任务` only for adding tasks, and that a failed/partial AI run remains visible with retry and warning evidence.

- [ ] **Step 5: Review repository state before handoff**

```powershell
git status --short
git log --oneline -8
```

Expected: only intended commits and changes are present; never add `frontend-v2/.workbuddy-ai/`.
