# Permanent Draft Project Deletion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a technical administrator permanently delete a draft project and all project-scoped business records only after an exact-name confirmation.

**Architecture:** The FastAPI projects router owns the authorization, lifecycle guard, dependency-first deletion, and audit record in one transaction. The project-management screen adds a dangerous menu item and an exact-name confirmation dialog; its API client sends the confirmation body, then refreshes the in-memory project list after success.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite/PostgreSQL-compatible ORM queries, React 19, TypeScript, Vitest, pytest.

---

### Task 1: Specify and prove the backend safety contract

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_project_close_lifecycle_guards.py`
- Modify: `bowei_ai_dashboard/app/routers/projects.py:231-239, 2064-2087`

- [ ] **Step 1: Write failing tests for successful draft deletion and the status guard**

  Add a small fixture that creates a `draft` project with one `ProjectMember`, `Task`, `UpdateSubmission`, and `MemberChangeRequest`. Add tests shaped as follows:

  ```python
  def test_superadmin_can_permanently_delete_draft_project_and_direct_records():
      db, task_id, submission_id, change_id = _seed("draft")

      result = projects.delete_draft_project(
          1,
          schemas.ProjectDeletePayload(confirm_name="Project"),
          current_user="moways",
          db=db,
      )

      assert result == {"ok": True, "project_id": 1}
      assert db.get(models.Project, 1) is None
      assert db.get(models.Task, task_id) is None
      assert db.get(models.UpdateSubmission, submission_id) is None
      assert db.get(models.MemberChangeRequest, change_id) is None
      assert db.query(models.ProjectMember).filter_by(project_id=1).count() == 0


  @pytest.mark.parametrize("status", ["dispatched", "active", "pending_close", "ended", "archived"])
  def test_delete_rejects_non_draft_project(status: str):
      db, *_ = _seed(status)

      with pytest.raises(HTTPException) as exc:
          projects.delete_draft_project(
              1,
              schemas.ProjectDeletePayload(confirm_name="Project"),
              current_user="moways",
              db=db,
          )

      assert exc.value.status_code == 409
      assert db.get(models.Project, 1) is not None
  ```

- [ ] **Step 2: Run the two tests to verify RED**

  Run:

  ```powershell
  & .\bowei_ai_dashboard\.venv\Scripts\python.exe -m pytest bowei_ai_dashboard\tests\test_project_close_lifecycle_guards.py -k "permanently_delete or delete_rejects" -v
  ```

  Expected: collection fails because `ProjectDeletePayload` and `delete_draft_project` do not exist.

- [ ] **Step 3: Add the request schema and guarded route skeleton**

  In `bowei_ai_dashboard/app/schemas.py`, directly after `ProjectPatchPayload`, add:

  ```python
  class ProjectDeletePayload(BaseModel):
      confirm_name: str = Field(..., min_length=1, max_length=100)
  ```

  In `projects.py`, before the archive route, add the endpoint shell. It must use the existing `_require_super_admin`, must re-read the project from the database, and must reject non-drafts before mutation:

  ```python
  @router.delete("/{project_id}")
  def delete_draft_project(
      project_id: int,
      payload: schemas.ProjectDeletePayload,
      current_user: str = Depends(get_current_user_name),
      db: Session = Depends(get_db),
  ):
      _require_super_admin(current_user, db)
      project = db.get(models.Project, project_id)
      if not project:
          raise HTTPException(404, "项目不存在")
      if PL.normalize(project.status) != PL.S_DRAFT:
          raise HTTPException(409, "仅草稿项目可以永久删除")
      if payload.confirm_name != project.name:
          raise HTTPException(422, "确认名称与项目名称不一致")
      # Task 2 supplies the deletion helper.
      _delete_draft_project_data(project, db)
      crud.log(db, current_user, "delete_project", "project", project_id,
               {"name": project.name, "status": "draft"}, {}, project_id=project_id)
      db.commit()
      return {"ok": True, "project_id": project_id}
  ```

- [ ] **Step 4: Run the same focused backend tests to verify GREEN**

  Run the Step 2 command. Expected: both new cases pass once Task 2’s helper is present.

- [ ] **Step 5: Commit the schema, route contract, and tests**

  ```powershell
  git add bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/app/routers/projects.py bowei_ai_dashboard/tests/test_project_close_lifecycle_guards.py
  git commit -m "feat: guard permanent draft project deletion"
  ```

### Task 2: Delete every project-scoped dependency transactionally

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/projects.py: immediately above delete_draft_project`
- Modify: `bowei_ai_dashboard/tests/test_project_close_lifecycle_guards.py`

- [ ] **Step 1: Write a failing cleanup-and-rollback test**

  Extend the test fixture with a `ProjectInitAttachment`, `ProjectInitAnalysisRun`, and `KeyTaskExecutionEvent` where model fields permit. Verify each is absent after deletion. Add a rollback test that monkeypatches `_delete_draft_project_data` to raise after the route begins and verifies `db.get(models.Project, 1)` remains present after `db.rollback()`.

  ```python
  def test_delete_rolls_back_when_dependency_cleanup_fails(monkeypatch):
      db, *_ = _seed("draft")

      def fail_after_cleanup(project, session):
          session.query(models.ProjectMember).filter_by(project_id=project.id).delete()
          raise RuntimeError("simulated cleanup failure")

      monkeypatch.setattr(projects, "_delete_draft_project_data", fail_after_cleanup)
      with pytest.raises(RuntimeError):
          projects.delete_draft_project(1, schemas.ProjectDeletePayload(confirm_name="Project"), "moways", db)
      db.rollback()
      assert db.get(models.Project, 1) is not None
      assert db.query(models.ProjectMember).filter_by(project_id=1).count() == 3
  ```

- [ ] **Step 2: Run the cleanup tests to verify RED**

  Run:

  ```powershell
  & .\bowei_ai_dashboard\.venv\Scripts\python.exe -m pytest bowei_ai_dashboard\tests\test_project_close_lifecycle_guards.py -k "permanently_delete or rolls_back" -v
  ```

  Expected: cleanup assertions fail because the route has no dependency deletion helper or rollback handling.

- [ ] **Step 3: Implement one dependency-first helper with explicit model order**

  Add `_delete_draft_project_data(project, db)` and call it only after all guards pass. Collect IDs before deletion, then delete descendants by their real parent key rather than assuming every model has `project_id`:

  ```python
  def _ids(model, column, project_id):
      return [row[0] for row in db.query(column).filter(model.project_id == project_id).all()]

  project_id = project.id
  task_ids = _ids(models.Task, models.Task.id, project_id)
  subtask_ids = [row[0] for row in db.query(models.SubTask.id).filter(models.SubTask.task_id.in_(task_ids)).all()]
  schedule_ids = [row[0] for row in db.query(models.ExecutionSchedule.id).filter(models.ExecutionSchedule.subtask_id.in_(subtask_ids)).all()]
  meeting_ids = _ids(models.Meeting, models.Meeting.id, project_id)
  skill_run_ids = _ids(models.MeetingSkillRun, models.MeetingSkillRun.id, project_id)
  clarification_ids = [row[0] for row in db.query(models.MeetingSkillClarification.id).filter(models.MeetingSkillClarification.run_id.in_(skill_run_ids)).all()]
  analysis_run_ids = _ids(models.MeetingAnalysisRun, models.MeetingAnalysisRun.id, project_id)
  change_set_ids = _ids(models.MeetingChangeSet, models.MeetingChangeSet.id, project_id)

  db.query(models.ExecutionScheduleReminder).filter(models.ExecutionScheduleReminder.schedule_id.in_(schedule_ids)).delete(synchronize_session=False)
  db.query(models.KeyTaskExecutionEvent).filter(models.KeyTaskExecutionEvent.project_id == project_id).delete(synchronize_session=False)
  db.query(models.ExecutionSchedule).filter(models.ExecutionSchedule.id.in_(schedule_ids)).delete(synchronize_session=False)
  db.query(models.SubTask).filter(models.SubTask.id.in_(subtask_ids)).delete(synchronize_session=False)
  db.query(models.MeetingSkillClarificationAnswerRevision).filter(models.MeetingSkillClarificationAnswerRevision.question_id.in_(clarification_ids)).delete(synchronize_session=False)
  db.query(models.MeetingSkillResolvedFact).filter(models.MeetingSkillResolvedFact.run_id.in_(skill_run_ids)).delete(synchronize_session=False)
  db.query(models.MeetingSkillClarification).filter(models.MeetingSkillClarification.run_id.in_(skill_run_ids)).delete(synchronize_session=False)
  db.query(models.MeetingSkillInputSnapshot).filter(models.MeetingSkillInputSnapshot.run_id.in_(skill_run_ids)).delete(synchronize_session=False)
  db.query(models.MeetingSkillRun).filter(models.MeetingSkillRun.id.in_(skill_run_ids)).delete(synchronize_session=False)
  db.query(models.MeetingAnalysisCandidate).filter(models.MeetingAnalysisCandidate.run_id.in_(analysis_run_ids)).delete(synchronize_session=False)
  db.query(models.MeetingRevision).filter(models.MeetingRevision.meeting_id.in_(meeting_ids)).delete(synchronize_session=False)
  db.query(models.MeetingReviewEvent).filter(models.MeetingReviewEvent.meeting_id.in_(meeting_ids)).delete(synchronize_session=False)
  db.query(models.MeetingTranscriptRevision).filter(models.MeetingTranscriptRevision.meeting_id.in_(meeting_ids)).delete(synchronize_session=False)
  db.query(models.MeetingTranscriptSource).filter(models.MeetingTranscriptSource.meeting_id.in_(meeting_ids)).delete(synchronize_session=False)
  db.query(models.MeetingChangeProposal).filter(models.MeetingChangeProposal.change_set_id.in_(change_set_ids)).delete(synchronize_session=False)
  ```

  Continue with direct project rows in dependency order: `AchievementAttachment`, `AchievementSubmission`, `Achievement`, `ProjectMeetingRun`, `MeetingAnalysisRun`, `MeetingProgressReview`, `MeetingChangeSet`, `KickoffAgentRun`, `MeetingDocumentSource`, `Meeting`, `ProjectInitAnalysisRun`, `ProjectInitAttachment`, `UpdateSubmission`, `Issue`, `ProjectCloseRequest`, `MemberChangeRequest`, `ProjectMember`, `SubTaskDraft`, `Task`, and `Notification`. Delete only rows whose `project_id == project_id`; do not delete existing `OperationLog` rows. Finally call `db.delete(project)`. Wrap the route body in `try: ... except Exception: db.rollback(); raise` so no partial deletion can persist.

- [ ] **Step 4: Run the focused cleanup suite to verify GREEN**

  Run the Step 2 command. Expected: all deletion, lifecycle-rejection, confirmation, and rollback cases pass.

- [ ] **Step 5: Run related lifecycle regression tests**

  Run:

  ```powershell
  & .\bowei_ai_dashboard\.venv\Scripts\python.exe -m pytest bowei_ai_dashboard\tests\test_project_close_lifecycle_guards.py bowei_ai_dashboard\tests\test_project_close_request_flow.py bowei_ai_dashboard\tests\test_project_close_request_permissions.py -v
  ```

  Expected: all tests pass; archive behavior remains limited to ended projects.

- [ ] **Step 6: Commit the transactional cleanup helper**

  ```powershell
  git add bowei_ai_dashboard/app/routers/projects.py bowei_ai_dashboard/tests/test_project_close_lifecycle_guards.py
  git commit -m "feat: purge draft project dependencies transactionally"
  ```

### Task 3: Add the typed frontend client and API tests

**Files:**
- Modify: `frontend/src/api/projects.ts:1-75`
- Create: `frontend/src/api/projects.delete.test.ts`

- [ ] **Step 1: Write a failing API-client test**

  Mock the shared API client and assert the new function uses DELETE with the exact confirmation object:

  ```ts
  it('sends the exact-name confirmation to the project delete endpoint', async () => {
    await deleteDraftProject(37, '测试项目')
    expect(apiDelete).toHaveBeenCalledWith('/api/projects/37', { confirm_name: '测试项目' })
  })
  ```

- [ ] **Step 2: Run the frontend test to verify RED**

  Run:

  ```powershell
  Set-Location frontend
  npm run test:unit -- src/api/projects.delete.test.ts
  ```

  Expected: the test fails because `deleteDraftProject` is not exported.

- [ ] **Step 3: Add the minimal typed API function**

  In `frontend/src/api/client.ts`, replace the existing one-argument helper with:

  ```ts
  export function apiDelete<T>(path: string, body?: unknown): Promise<T> {
    return request<T>('DELETE', path, body)
  }
  ```

  In `frontend/src/api/projects.ts`, after `archiveProject`, add:

  ```ts
  export function deleteDraftProject(projectId: number, confirmName: string): Promise<{ ok: boolean; project_id: number }> {
    return apiDelete(`/api/projects/${projectId}`, { confirm_name: confirmName })
  }
  ```

- [ ] **Step 4: Run the API-client test to verify GREEN**

  Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Commit the client contract**

  ```powershell
  git add frontend/src/api/projects.ts frontend/src/api/projects.delete.test.ts frontend/src/api/client.ts
  git commit -m "feat: add confirmed draft project deletion client"
  ```

### Task 4: Add the safe deletion dialog to project management

**Files:**
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx:1-32, 351-365, 1048-1064`
- Create: `frontend/src/domain/projectDeletionPolicy.ts`
- Create: `frontend/src/domain/projectDeletionPolicy.test.ts`
- Create: `frontend/src/features/settings/ProjectsMgmtSection.delete.test.ts`

- [ ] **Step 1: Write failing policy and structure tests for visibility and confirmation gating**

  Create a pure policy test that defines the intended predicates before UI code exists:

  ```ts
  import { describe, expect, it } from 'vitest'
  import { canPermanentlyDeleteDraftProject, isProjectDeletionConfirmed } from './projectDeletionPolicy'

  describe('project deletion policy', () => {
    it('allows only a technical administrator to delete a draft project', () => {
      expect(canPermanentlyDeleteDraftProject('draft', true)).toBe(true)
      expect(canPermanentlyDeleteDraftProject('draft', false)).toBe(false)
      expect(canPermanentlyDeleteDraftProject('active', true)).toBe(false)
    })

    it('requires the exact project name without trimming or case normalization', () => {
      expect(isProjectDeletionConfirmed('测试项目', '测试项目')).toBe(true)
      expect(isProjectDeletionConfirmed('测试项目', '测试项目 ')).toBe(false)
      expect(isProjectDeletionConfirmed('测试项目', '错误名称')).toBe(false)
    })
  })
  ```

  Create a structure test using `fs.readFileSync('src/features/settings/ProjectsMgmtSection.tsx', 'utf8')`. Assert the source uses the policy helpers, contains `永久删除项目`, contains the accessible input label `请输入项目名称以确认`, calls `deleteDraftProject`, and uses `disabled={!isProjectDeletionConfirmed` for the final delete button.

- [ ] **Step 2: Run the UI test to verify RED**

  Run:

  ```powershell
  Set-Location frontend
  npm run test:unit -- src/domain/projectDeletionPolicy.test.ts src/features/settings/ProjectsMgmtSection.delete.test.ts
  ```

  Expected: tests fail because `projectDeletionPolicy` and the deletion UI do not exist.

- [ ] **Step 3: Add local dialog state, dangerous menu item, and success refresh**

  Import `deleteDraftProject`. Add these states beside the existing more-menu state:

  ```ts
  const [deleteCandidate, setDeleteCandidate] = useState<Project | null>(null)
  const [deleteConfirmation, setDeleteConfirmation] = useState('')
  const [deletingProject, setDeletingProject] = useState(false)
  ```

  Create `projectDeletionPolicy.ts` with:

  ```ts
  export function canPermanentlyDeleteDraftProject(status: string, isSuperAdmin: boolean): boolean {
    return isSuperAdmin && status === 'draft'
  }

  export function isProjectDeletionConfirmed(projectName: string, confirmation: string): boolean {
    return projectName === confirmation
  }
  ```

  Import both helpers in `ProjectsMgmtSection.tsx`. Add “永久删除项目” with `tone: 'danger'` only when `canPermanentlyDeleteDraftProject(status, roles.isSuperAdmin)`. Its handler closes the menu and initializes `deleteCandidate` and `deleteConfirmation`. Render an accessible modal with: the project name, an irreversible warning, an input labelled `请输入项目名称以确认`, a cancel button, and a danger button disabled unless `isProjectDeletionConfirmed(deleteCandidate.name, deleteConfirmation)` or `deletingProject`.

  The submit handler must set the busy state, call `deleteDraftProject(deleteCandidate.id, deleteConfirmation)`, remove the matching project from `projects`, remove its entries from `members`, `projectTasksMap`, and `projectSubtasksMap`, call `reloadProjects()`, close/reset the dialog, and call `toast.success('项目已永久删除')`. In `catch`, show the backend’s safe message through the existing toast/error convention and leave the dialog open. In `finally`, clear only the busy state.

- [ ] **Step 4: Run the UI test to verify GREEN**

  Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Add a successful-deletion source-contract test and rerun**

  Extend `ProjectsMgmtSection.delete.test.ts` to assert that the success path filters the deleted ID from `projects`, calls `reloadProjects()`, closes `setDeleteCandidate(null)`, and emits `toast.success('项目已永久删除')`. Run the Step 2 command again. Expected: all policy and UI source-contract tests pass.

- [ ] **Step 6: Commit the project-management UI**

  ```powershell
  git add frontend/src/features/settings/ProjectsMgmtSection.tsx frontend/src/domain/projectDeletionPolicy.ts frontend/src/domain/projectDeletionPolicy.test.ts frontend/src/features/settings/ProjectsMgmtSection.delete.test.ts
  git commit -m "feat: add permanent draft project deletion dialog"
  ```

### Task 5: End-to-end verification and manual safety check

**Files:**
- No production-file changes expected.

- [ ] **Step 1: Run all targeted automated tests**

  Run:

  ```powershell
  & .\bowei_ai_dashboard\.venv\Scripts\python.exe -m pytest bowei_ai_dashboard\tests\test_project_close_lifecycle_guards.py -v
  Set-Location frontend
  npm run test:unit -- src/api/projects.delete.test.ts src/domain/projectDeletionPolicy.test.ts src/features/settings/ProjectsMgmtSection.delete.test.ts
  npm run build
  ```

  Expected: pytest passes, both Vitest files pass, and TypeScript/Vite build succeeds.

- [ ] **Step 2: Verify against the running local service without touching an existing project**

  Create a new uniquely named draft project through the normal UI, refresh Project Management, open `⋯`, verify that only the technical administrator sees “永久删除项目”, enter an incorrect confirmation first, then enter the exact new name. Verify the project disappears after success and a page refresh does not restore it.

- [ ] **Step 3: Record verification evidence and commit any necessary test-only correction**

  If verification exposes a defect, add a failing regression test first, apply the smallest correction, rerun Step 1, then commit the corrected router, frontend component, API client, and their corresponding test files:

  ```powershell
  git add bowei_ai_dashboard/app/routers/projects.py bowei_ai_dashboard/tests/test_project_close_lifecycle_guards.py frontend/src/api/client.ts frontend/src/api/projects.ts frontend/src/api/projects.delete.test.ts frontend/src/domain/projectDeletionPolicy.ts frontend/src/domain/projectDeletionPolicy.test.ts frontend/src/features/settings/ProjectsMgmtSection.tsx frontend/src/features/settings/ProjectsMgmtSection.delete.test.ts
  git commit -m "fix: verify permanent draft project deletion"
  ```
