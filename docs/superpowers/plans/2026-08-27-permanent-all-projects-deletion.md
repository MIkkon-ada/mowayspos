# 全部项目永久删除 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让技术管理员能够以双重确认永久删除任意状态的项目，并安全清理其数据库关联数据和已上传的附件文件。

**Architecture:** 在项目删除路由之外新增一个纯文件存储服务，集中解析三类上传根目录、将文件暂存至各自根目录内的隔离区、支持恢复和幂等销毁。路由先锁定项目、校验技术管理员和双重确认，随后暂存文件并在数据库事务中清除业务数据及写审计；提交后销毁隔离文件，若失败则返回已删除但待清理的标识，并由受保护重试端点只处理该操作 ID 的隔离目录。

**Tech Stack:** FastAPI、Pydantic、SQLAlchemy、pathlib/shutil、pytest、React、TypeScript、Vitest。

---

## File structure

- Create: `bowei_ai_dashboard/app/services/project_purge_storage.py` — 受控附件路径解析、暂存、恢复、销毁与按操作 ID 重试。
- Create: `bowei_ai_dashboard/tests/test_project_purge_storage.py` — 不依赖数据库的文件隔离与路径安全测试。
- Modify: `bowei_ai_dashboard/app/schemas.py` — 将项目删除请求扩展为项目名称和固定销毁文字两个确认项。
- Modify: `bowei_ai_dashboard/app/routers/projects.py` — 任意状态删除、项目行锁、文件暂存、审计、清理失败响应与重试端点。
- Modify: `bowei_ai_dashboard/tests/test_project_close_lifecycle_guards.py` — 后端权限、状态、确认、数据库清理、回滚和文件集成测试。
- Modify: `frontend/src/api/projects.ts` — 暴露 `deleteProject(projectId, confirmName, confirmPhrase)` 与响应类型。
- Modify: `frontend/src/api/projects.delete.test.ts` — 校验 DELETE 请求传递双重确认字段。
- Modify: `frontend/src/domain/projectDeletionPolicy.ts` — 所有状态均可由技术管理员删除，并检查两个确认值。
- Modify: `frontend/src/domain/projectDeletionPolicy.test.ts` — 覆盖所有状态和双重确认。
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx` — 全状态危险菜单、双输入弹窗、成功缓存清理及待清理提示。
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.delete.test.ts` — 覆盖 UI 文案、双输入和新 API 名称。

### Task 1: Define and test safe attachment quarantine behavior

**Files:**

- Create: `bowei_ai_dashboard/tests/test_project_purge_storage.py`

- [ ] **Step 1: Write the failing storage-service tests**

```python
from pathlib import Path
import pytest
from app.services.project_purge_storage import ProjectPurgeStorageError, destroy_staged_project_payloads, restore_staged_project_payloads, stage_project_payloads

def test_stage_then_destroy_removes_only_project_payloads(tmp_path: Path):
    root = tmp_path / "achievement"
    payload, other = root / "7" / "asset.bin", root / "8" / "keep.bin"
    payload.parent.mkdir(parents=True)
    other.parent.mkdir(parents=True)
    payload.write_bytes(b"delete")
    other.write_bytes(b"keep")
    staged = stage_project_payloads("00000000-0000-0000-0000-000000000007", [("achievement", root, "7/asset.bin")])
    assert not payload.exists()
    assert other.read_bytes() == b"keep"
    destroy_staged_project_payloads(staged)
    assert not (root / ".project-purge").exists()
    assert other.read_bytes() == b"keep"

def test_failed_stage_restores_and_rejects_escape_paths(tmp_path: Path):
    root, payload = tmp_path / "init", tmp_path / "init" / "7" / "init.pdf"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"source")
    with pytest.raises(ProjectPurgeStorageError):
        stage_project_payloads("00000000-0000-0000-0000-000000000008", [("init", root, "7/init.pdf"), ("init", root, "../outside")])
    assert payload.read_bytes() == b"source"
    restore_staged_project_payloads([])
```

- [ ] **Step 2: Run the test to prove it fails**

Run from `bowei_ai_dashboard`: `& .\\.venv\\Scripts\\python.exe -m pytest tests\\test_project_purge_storage.py -v`

Expected: collection fails with `ModuleNotFoundError: No module named 'app.services.project_purge_storage'`.

- [ ] **Step 3: Commit the failing test**

Run: `git add -- bowei_ai_dashboard/tests/test_project_purge_storage.py; git commit -m "test: define project purge storage safety"`

### Task 2: Implement the isolated file-purge service

**Files:**

- Create: `bowei_ai_dashboard/app/services/project_purge_storage.py`
- Test: `bowei_ai_dashboard/tests/test_project_purge_storage.py`

- [ ] **Step 1: Implement the safe stage, restore and destroy functions**

```python
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from shutil import rmtree
from uuid import UUID

class ProjectPurgeStorageError(RuntimeError): pass

@dataclass(frozen=True)
class StagedProjectPayload:
    cleanup_key: str
    root: Path
    source: Path
    staged: Path

def _safe_payload_path(root: Path, storage_key: str) -> Path:
    if not isinstance(storage_key, str) or not storage_key.strip() or "\\x00" in storage_key:
        raise ProjectPurgeStorageError("invalid project attachment storage key")
    root, path = root.resolve(), (root.resolve() / storage_key).resolve()
    if path == root or root not in path.parents:
        raise ProjectPurgeStorageError("invalid project attachment storage path")
    return path

def stage_project_payloads(cleanup_key: str, entries: list[tuple[str, Path, str]]) -> list[StagedProjectPayload]:
    UUID(cleanup_key)
    staged: list[StagedProjectPayload] = []
    try:
        for _kind, root, storage_key in entries:
            root, source = root.resolve(), _safe_payload_path(root, storage_key)
            if not source.exists(): continue
            target = (root / ".project-purge" / cleanup_key / source.relative_to(root)).resolve()
            quarantine = (root / ".project-purge" / cleanup_key).resolve()
            if quarantine not in target.parents: raise ProjectPurgeStorageError("invalid project purge quarantine path")
            target.parent.mkdir(parents=True, exist_ok=True)
            source.replace(target)
            staged.append(StagedProjectPayload(cleanup_key, root, source, target))
        return staged
    except Exception as exc:
        restore_staged_project_payloads(staged)
        if isinstance(exc, ProjectPurgeStorageError): raise
        raise ProjectPurgeStorageError("project attachment staging failed") from exc

def restore_staged_project_payloads(staged: list[StagedProjectPayload]) -> None:
    for item in reversed(staged):
        if item.staged.exists():
            item.source.parent.mkdir(parents=True, exist_ok=True)
            item.staged.replace(item.source)

def retry_project_payload_cleanup(cleanup_key: str, roots: list[Path]) -> bool:
    UUID(cleanup_key)
    for root in roots:
        base, target = (root.resolve() / ".project-purge").resolve(), (root.resolve() / ".project-purge" / cleanup_key).resolve()
        if base not in target.parents: raise ProjectPurgeStorageError("invalid project purge cleanup key")
        if target.exists(): rmtree(target)
        if base.exists() and not any(base.iterdir()): base.rmdir()
    return True

def destroy_staged_project_payloads(staged: list[StagedProjectPayload]) -> None:
    if staged: retry_project_payload_cleanup(staged[0].cleanup_key, list({item.root for item in staged}))
```

- [ ] **Step 2: Run the storage tests**

Run from `bowei_ai_dashboard`: `& .\\.venv\\Scripts\\python.exe -m pytest tests\\test_project_purge_storage.py -v`

Expected: PASS.

- [ ] **Step 3: Commit the service**

Run: `git add -- bowei_ai_dashboard/app/services/project_purge_storage.py bowei_ai_dashboard/tests/test_project_purge_storage.py; git commit -m "feat: stage project attachments before purge"`

### Task 3: Define all-status backend behavior with tests

**Files:**

- Modify: `bowei_ai_dashboard/app/schemas.py:362-364`
- Modify: `bowei_ai_dashboard/tests/test_project_close_lifecycle_guards.py:129-278`

- [ ] **Step 1: Replace the draft-only tests with all-status and double-confirmation tests**

```python
DELETE_PHRASE = "永久删除"

@pytest.mark.parametrize("status", ["draft", "dispatched", "pending_kickoff", "pending_review", "returned", "active", "pending_close", "ended", "archived"])
def test_superadmin_can_permanently_delete_every_project_status(status: str):
    db, task_id, submission_id, change_id = _seed(status)
    result = projects.delete_project(1, schemas.ProjectDeletePayload(confirm_name="Project", confirm_phrase=DELETE_PHRASE), current_user="moways", db=db)
    assert result == {"ok": True, "project_id": 1, "cleanup_pending": False, "cleanup_key": None}
    assert db.get(models.Project, 1) is None
    assert db.get(models.Task, task_id) is None
    assert db.get(models.UpdateSubmission, submission_id) is None
    assert db.get(models.MemberChangeRequest, change_id) is None

def test_delete_requires_exact_name_and_destroy_phrase():
    db, *_ = _seed("active")
    with pytest.raises(HTTPException, match="确认名称"):
        projects.delete_project(1, schemas.ProjectDeletePayload(confirm_name="Project ", confirm_phrase=DELETE_PHRASE), "moways", db)
    with pytest.raises(HTTPException, match="永久删除"):
        projects.delete_project(1, schemas.ProjectDeletePayload(confirm_name="Project", confirm_phrase="删除"), "moways", db)
    assert db.get(models.Project, 1) is not None
```

Add a `tmp_path`/`monkeypatch` fixture that sets all three storage roots, seeds an `AchievementAttachment`, `ProjectInitAttachment`, and `MeetingDocumentSource` plus files, and asserts success removes each. Add a cleanup-failure test that monkeypatches `destroy_staged_project_payloads` to raise, asserts the project is absent and `cleanup_pending` is true, then verifies a technical administrator can retry only its returned `cleanup_key`.

- [ ] **Step 2: Run the focused test and prove the old contract fails**

Run from `bowei_ai_dashboard`: `& .\\.venv\\Scripts\\python.exe -m pytest tests\\test_project_close_lifecycle_guards.py -v`

Expected: FAIL because `ProjectDeletePayload` lacks `confirm_phrase` and `projects.delete_project` is not yet defined.

- [ ] **Step 3: Commit the failing tests**

Run: `git add -- bowei_ai_dashboard/tests/test_project_close_lifecycle_guards.py; git commit -m "test: cover permanent deletion for all project states"`

### Task 4: Implement backend deletion, recovery and retry

**Files:**

- Modify: `bowei_ai_dashboard/app/schemas.py:362-364`
- Modify: `bowei_ai_dashboard/app/routers/projects.py:1-80, 2064-2223`
- Test: `bowei_ai_dashboard/tests/test_project_close_lifecycle_guards.py`

- [ ] **Step 1: Extend the request body and add a project row lock**

```python
class ProjectDeletePayload(BaseModel):
    confirm_name: str = Field(..., min_length=1, max_length=100)
    confirm_phrase: str = Field(..., min_length=1, max_length=20)

def _lock_project_for_delete(project_id: int, db: Session) -> models.Project | None:
    return db.execute(select(models.Project).where(models.Project.id == project_id).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
```

- [ ] **Step 2: Replace the draft-only route**

```python
@router.delete("/{project_id}")
def delete_project(project_id: int, payload: schemas.ProjectDeletePayload, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    _require_super_admin(current_user, db)
    project = _lock_project_for_delete(project_id, db)
    if not project: raise HTTPException(404, "项目不存在")
    if payload.confirm_name != project.name: raise HTTPException(422, "确认名称与项目名称不一致")
    if payload.confirm_phrase != "永久删除": raise HTTPException(422, "请准确输入“永久删除”")
```

Collect only the project's `AchievementAttachment`, `ProjectInitAttachment`, and `MeetingDocumentSource` storage keys. Map each key to its configured root, create a UUID cleanup key, and call `stage_project_payloads` before `_delete_project_data`. Rename `_delete_draft_project_data` to `_delete_project_data`; retain its foreign-key deletion order but remove its draft-only wording and all lifecycle checks.

In the transaction, call `_delete_project_data`, write one `delete_project` audit log containing only the name, pre-delete normalized status, and cleanup key, then commit. On any exception before commit, call `db.rollback()` and `restore_staged_project_payloads(staged)` before re-raising. After commit, call `destroy_staged_project_payloads(staged)`; if it raises `ProjectPurgeStorageError`, log `delete_project_cleanup_pending`, commit that log, and return `{ "ok": True, "project_id": project_id, "cleanup_pending": True, "cleanup_key": cleanup_key }`. Otherwise return the same shape with `False` and `None`.

- [ ] **Step 3: Add a path-fixed retry endpoint**

```python
@router.post("/purge-cleanups/{cleanup_key}/retry")
def retry_project_purge_cleanup(cleanup_key: str, current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    _require_super_admin(current_user, db)
    cleaned = retry_project_payload_cleanup(cleanup_key, _project_purge_storage_roots())
    crud.log(db, current_user, "retry_project_cleanup", "project_purge_cleanup", None, {"cleanup_key": cleanup_key}, {"cleaned": cleaned})
    db.commit()
    return {"ok": True, "cleanup_key": cleanup_key, "cleanup_pending": not cleaned}
```

`_project_purge_storage_roots()` must return exactly the achievement, project-init and meeting-document roots from environment-backed server configuration. It must accept no path from the request. Convert invalid UUID or containment errors to 422 with no exposed filesystem path; return the pending state for I/O cleanup errors.

- [ ] **Step 4: Run focused backend tests**

Run from `bowei_ai_dashboard`: `& .\\.venv\\Scripts\\python.exe -m pytest tests\\test_project_purge_storage.py tests\\test_project_close_lifecycle_guards.py tests\\test_achievement_attachments.py tests\\test_project_init_attachments.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the backend**

Run: `git add -- bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/app/routers/projects.py bowei_ai_dashboard/tests/test_project_close_lifecycle_guards.py; git commit -m "feat: allow protected purge of any project state"`

### Task 5: Update frontend contract and deletion policy

**Files:**

- Modify: `frontend/src/api/projects.ts:75-77`
- Modify: `frontend/src/api/projects.delete.test.ts`
- Modify: `frontend/src/domain/projectDeletionPolicy.ts`
- Modify: `frontend/src/domain/projectDeletionPolicy.test.ts`

- [ ] **Step 1: Write the failing API and policy tests**

```ts
import { canPermanentlyDeleteProject, isProjectDeletionConfirmed } from './projectDeletionPolicy'

it('allows a technical administrator to delete every lifecycle state', () => {
  for (const status of ['draft', 'dispatched', 'pending_kickoff', 'pending_review', 'returned', 'active', 'pending_close', 'ended', 'archived']) {
    expect(canPermanentlyDeleteProject(status, true)).toBe(true)
    expect(canPermanentlyDeleteProject(status, false)).toBe(false)
  }
})

it('requires exact project name and destroy phrase', () => {
  expect(isProjectDeletionConfirmed('测试项目', '测试项目', '永久删除')).toBe(true)
  expect(isProjectDeletionConfirmed('测试项目', '测试项目 ', '永久删除')).toBe(false)
  expect(isProjectDeletionConfirmed('测试项目', '测试项目', '删除')).toBe(false)
})
```

In `projects.delete.test.ts`, require `export function deleteProject` and `confirm_name: confirmName, confirm_phrase: confirmPhrase` in the API source.

- [ ] **Step 2: Run the test to prove it fails**

Run from `frontend`: `npm run test:unit -- src/api/projects.delete.test.ts src/domain/projectDeletionPolicy.test.ts`

Expected: FAIL because the API has one confirmation and the policy is draft-only.

- [ ] **Step 3: Implement the API contract and pure policy**

```ts
export type ProjectDeleteResult = { ok: boolean; project_id: number; cleanup_pending: boolean; cleanup_key: string | null }

export function deleteProject(projectId: number, confirmName: string, confirmPhrase: string): Promise<ProjectDeleteResult> {
  return apiDelete(`/api/projects/${projectId}`, { confirm_name: confirmName, confirm_phrase: confirmPhrase })
}
```

```ts
export function canPermanentlyDeleteProject(_status: string, isSuperAdmin: boolean): boolean {
  return isSuperAdmin
}

export function isProjectDeletionConfirmed(projectName: string, confirmation: string, phrase: string): boolean {
  return projectName === confirmation && phrase === '永久删除'
}
```

- [ ] **Step 4: Run the frontend contract tests**

Run from `frontend`: `npm run test:unit -- src/api/projects.delete.test.ts src/domain/projectDeletionPolicy.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit the frontend contract**

Run: `git add -- frontend/src/api/projects.ts frontend/src/api/projects.delete.test.ts frontend/src/domain/projectDeletionPolicy.ts frontend/src/domain/projectDeletionPolicy.test.ts; git commit -m "feat: require two confirmations for project deletion"`

### Task 6: Update the project-management destructive dialog

**Files:**

- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx:1-35, 372-377, 728-760, 1100-1128, 1245-1320`
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.delete.test.ts`

- [ ] **Step 1: Write the failing UI-source test**

```ts
expect(source).toContain('canPermanentlyDeleteProject')
expect(source).toContain('请输入“永久删除”以确认')
expect(source).toContain("const [deletePhrase, setDeletePhrase] = useState('')")
expect(source).toContain('deleteProject(projectId, deleteConfirmation, deletePhrase)')
expect(source).toContain("toast.warning('项目数据已删除，附件文件正在等待清理')")
```

- [ ] **Step 2: Run the UI test to prove it fails**

Run from `frontend`: `npm run test:unit -- src/features/settings/ProjectsMgmtSection.delete.test.ts`

Expected: FAIL because the dialog has only one input and calls `deleteDraftProject`.

- [ ] **Step 3: Implement the two-input dialog and state update**

Replace the draft-only import and menu predicate with `deleteProject` and `canPermanentlyDeleteProject(status, roles.isSuperAdmin)`. Add `deletePhrase` state, reset it on menu open and in `closeDeleteDialog`, and add a second disabled-while-loading input with `id="delete-project-phrase"`, label `请输入“永久删除”以确认`, and `autoComplete="off"`.

```ts
const confirmed = isProjectDeletionConfirmed(project.name, confirmation, phrase)
const result = await deleteProject(projectId, deleteConfirmation, deletePhrase)
```

Keep the existing removal of the project from `projects`, `members`, `projectTasksMap`, and `projectSubtasksMap`, then call `reloadProjects()`. Show `toast.success('项目已永久删除')` when `result.cleanup_pending` is false, otherwise `toast.warning('项目数据已删除，附件文件正在等待清理')`. Do not show cleanup keys or filesystem paths in the ordinary UI.

- [ ] **Step 4: Run UI test and production build**

Run from `frontend`: `npm run test:unit -- src/features/settings/ProjectsMgmtSection.delete.test.ts`

Expected: PASS.

Run from `frontend`: `npm run build`

Expected: exit code 0; the existing Vite chunk-size warning is acceptable if it is the only warning.

- [ ] **Step 5: Commit the UI**

Run: `git add -- frontend/src/features/settings/ProjectsMgmtSection.tsx frontend/src/features/settings/ProjectsMgmtSection.delete.test.ts; git commit -m "feat: expose protected project purge for all states"`

### Task 7: Full verification and controlled local acceptance

**Files:**

- Modify only a feature file above if a focused test exposes a defect; preserve all unrelated user-owned dirty files.

- [ ] **Step 1: Run the complete focused backend suite**

Run from `bowei_ai_dashboard`: `& .\\.venv\\Scripts\\python.exe -m pytest tests\\test_project_purge_storage.py tests\\test_project_close_lifecycle_guards.py tests\\test_project_close_request_flow.py tests\\test_project_close_request_permissions.py tests\\test_achievement_attachments.py tests\\test_project_init_attachments.py -v`

Expected: PASS with no skipped permanent-deletion test.

- [ ] **Step 2: Run every frontend test touched by the feature**

Run from `frontend`: `npm run test:unit -- src/api/projects.delete.test.ts src/domain/projectDeletionPolicy.test.ts src/features/settings/ProjectsMgmtSection.delete.test.ts`

Expected: PASS.

- [ ] **Step 3: Run the production frontend build**

Run from `frontend`: `npm run build`

Expected: exit code 0; report any new warning or error separately from the known chunk-size warning.

- [ ] **Step 4: Perform one safe local acceptance test**

Create a new project named `永久删除验收-20260827` while signed in as a technical administrator. Add only disposable test files through the available achievement, project-init and meeting-document flows. Delete that exact project with its full name and the phrase `永久删除`. Verify it is absent after a page refresh and the three test files no longer exist below their configured upload roots. Do not select, open the delete dialog for, or delete any pre-existing project.

If the endpoint returns `cleanup_pending: true`, call only `POST /api/projects/purge-cleanups/{cleanup_key}/retry` as the same technical administrator; verify the project stays absent and the dedicated quarantine directory disappears.

- [ ] **Step 5: Review only intended changes and commit final fixes**

Run: `git diff --check; git status --short; git log --oneline -5`

Expected: no accidental staging of `local_backup.db`, `backups/`, unrelated AI configuration edits, parser edits, or existing untracked plan files. Commit only feature files changed to correct a verification defect.
