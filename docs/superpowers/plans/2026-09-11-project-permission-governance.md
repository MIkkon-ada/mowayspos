# Project Permission Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Do not dispatch subagents for this repository. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status (2026-09-13): Completed and re-audited.** Tasks 1–10 were delivered in commits `b366cab` through `8c22c1d`; the remaining `projectCloseUi.ts` duplicate policy was removed in `cda9bfa`. Fresh verification: 69 project-permission tests, 1909 backend tests (12 skipped), 89 frontend unit tests, 502 frontend contract tests, and production build all passed. CI configuration statically confirms required backend/frontend/build/PostgreSQL gates with no failure bypass patterns.

**Goal:** 在保持现有项目角色权限和 API 兼容的前提下，将项目域授权收口为后端纯策略、显式旧数据兼容层和统一前端展示策略。

**Architecture:** 新增无数据库依赖的项目权限 Policy，由访问 Service 加载身份、项目状态、角色和资源归属后调用；`project_members` 保持主数据地位，旧项目字符串字段仅在调用方显式允许且当前人员没有有效成员角色时回退。项目 Router 分组迁移，前端使用同名动作函数控制入口和按钮，后端始终执行最终授权。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, pytest, React 18, TypeScript, Vitest, Node.js test runner

---

## Scope and constraints

- 设计依据：`docs/superpowers/specs/2026-09-11-project-permission-governance-design.md`。
- 本轮只治理项目域权限，不迁移确认中心、会议、问题、成果或 AI 服务的业务策略。
- 保持现有 API 路径、HTTP 方法、成功响应字段、拒绝状态码和拒绝 `detail` 文案。
- 只新增响应顶层 `code`；旧客户端忽略该字段后行为不变。
- `company_ceo` 与 `project_ceo` 必须保持两个独立身份。
- 写操作默认严格读取 `project_members`，不得因兼容层扩大旧字段授权。
- 不新增数据库迁移，不调整生产表结构。
- 当前其他 worktree 可能存在用户修改；执行时在新的隔离 worktree 中完成，并且每次只暂存本任务列出的文件。
- 工作目录约定：未显式切换目录的 `python -m pytest` 命令从 `bowei_ai_dashboard` 运行；`npm` 命令从 `frontend` 运行；`git` 与仓库级 `rg` 命令从仓库根目录运行。

## Acceptance gates

- 后端项目权限矩阵测试覆盖全部项目动作的允许和拒绝路径。
- 项目 Router 的项目级写接口统一调用 `project_access`，不再新增内联角色组合判断。
- 旧角色字段仅由 `compatibility/project_roles.py` 读取，且默认不启用回退。
- 权限拒绝响应同时包含兼容 `detail` 和稳定 `code`。
- 前端项目入口和操作按钮统一消费 `domain/permissions.ts`。
- `python -m pytest tests -q`、`npm run test:all`、`npm run build`、`python -m alembic heads` 和 `git diff --check` 全部通过。

## Task 1: Freeze the existing project permission behavior

**Files:**

- Create: `bowei_ai_dashboard/tests/test_project_permission_characterization.py`
- Verify: `bowei_ai_dashboard/tests/test_role_boundary.py`
- Verify: `bowei_ai_dashboard/tests/test_project_close_request_permissions.py`
- Verify: `bowei_ai_dashboard/tests/test_full_role_lifecycle_audit.py`

- [ ] **Step 1: Run the existing role and lifecycle suites**

  Run from `bowei_ai_dashboard`:

  ```powershell
  python -m pytest tests/test_role_boundary.py tests/test_project_close_request_permissions.py tests/test_full_role_lifecycle_audit.py -q
  ```

  Expected: PASS. Save the test count in the execution notes; any pre-existing failure blocks implementation and must be diagnosed first.

- [ ] **Step 2: Add black-box characterization cases for project actions**

  Create `tests/test_project_permission_characterization.py` with an isolated SQLite fixture containing accounts for `admin`, `company_ceo`, `coach`, `owner`, `coordinator`, `member`, and `outsider`. Create one project with all four project roles and parameterize these public endpoint calls:

  ```python
  @pytest.mark.parametrize(
      ("actor", "call", "expected_status"),
      [
          ("owner", lambda db, p: list_members(p.id, current_user="owner", db=db), None),
          ("outsider", lambda db, p: list_members(p.id, current_user="outsider", db=db), 403),
          ("company_ceo", lambda db, p: dispatch_project(p.id, current_user="company_ceo", db=db), None),
          ("owner", lambda db, p: dispatch_project(p.id, current_user="owner", db=db), 403),
          ("member", lambda db, p: owner_submit_project_profile(p.id, _profile(), current_user="member", db=db), 403),
          ("company_ceo", lambda db, p: approve_project(p.id, current_user="company_ceo", db=db), 403),
      ],
  )
  def test_existing_project_action_boundaries(db, project, actor, call, expected_status):
      if expected_status is None:
          call(db, project)
          return
      with pytest.raises(HTTPException) as error:
          call(db, project)
      assert error.value.status_code == expected_status
  ```

  Keep each case independent by resetting the fixture per parameter. Add separate cases for member-change request, close request, close review, archive, delete, and technical kickoff so destructive or lifecycle-changing calls never share a project instance.

- [ ] **Step 3: Assert current status codes and detail strings**

  Add explicit assertions for the compatibility-sensitive denials:

  ```python
  assert_denial(update_project, actor="company_ceo", lifecycle="active", status=403,
                 detail="项目已下发，当前仅支持查看。如需调整，请走变更申请流程。")
  assert_denial(create_project_close_request, actor="member", lifecycle="active", status=403,
                 detail="仅项目负责人或超级管理员可执行此操作")
  assert_denial(archive_project, actor="company_ceo", lifecycle="ended", status=403,
                 detail="项目归档需提交公司管理审核。")
  ```

  Implement `assert_denial` in the same file so it invokes the supplied endpoint with the fixture payload and compares `HTTPException.status_code` and `detail` exactly.

- [ ] **Step 4: Run the characterization file**

  ```powershell
  python -m pytest tests/test_project_permission_characterization.py -q
  ```

  Expected: PASS against the pre-refactor implementation.

- [ ] **Step 5: Commit the frozen behavior**

  ```powershell
  git add bowei_ai_dashboard/tests/test_project_permission_characterization.py
  git commit -m "test: freeze project permission behavior"
  ```

## Task 2: Add the pure backend project permission policy

**Files:**

- Create: `bowei_ai_dashboard/app/domain/project_permissions.py`
- Create: `bowei_ai_dashboard/tests/test_project_permission_policy.py`

- [ ] **Step 1: Write the failing matrix tests**

  Create `tests/test_project_permission_policy.py`:

  ```python
  from dataclasses import replace

  import pytest

  from app.domain.project_permissions import (
      A_ARCHIVE,
      A_BATCH_IMPORT,
      A_CANCEL_CLOSE_REQUEST,
      A_CREATE,
      A_DELETE,
      A_DISPATCH,
      A_EDIT_CLOSE_REQUEST,
      A_EDIT_SOURCE,
      A_MANAGE_MEMBERS_DIRECT,
      A_OWNER_SUBMIT,
      A_REQUEST_CLOSE,
      A_REQUEST_MEMBER_CHANGE,
      A_REVIEW_CLOSE_REQUEST,
      A_REVIEW_MEMBER_CHANGE,
      A_REVIEW_START,
      A_TECHNICAL_KICKOFF,
      A_VIEW,
      ProjectPermissionResource,
      ProjectPermissionSubject,
      decide_project_action,
  )

  ADMIN = ProjectPermissionSubject(is_tech_admin=True)
  COMPANY_CEO = ProjectPermissionSubject(is_company_ceo=True, person_id=2)
  COACH = ProjectPermissionSubject(person_id=3, project_roles=frozenset({"project_ceo"}))
  OWNER = ProjectPermissionSubject(person_id=4, project_roles=frozenset({"owner"}))
  MEMBER = ProjectPermissionSubject(person_id=5, project_roles=frozenset({"member"}))
  OUTSIDER = ProjectPermissionSubject(person_id=6)
  ACTIVE = ProjectPermissionResource(project_id=1, lifecycle="active")

  @pytest.mark.parametrize(
      ("action", "subject", "allowed"),
      [
          (A_VIEW, ADMIN, True),
          (A_VIEW, COMPANY_CEO, True),
          (A_VIEW, MEMBER, True),
          (A_VIEW, OUTSIDER, False),
          (A_CREATE, COMPANY_CEO, True),
          (A_CREATE, OWNER, False),
          (A_BATCH_IMPORT, ADMIN, True),
          (A_BATCH_IMPORT, COMPANY_CEO, False),
          (A_DISPATCH, COMPANY_CEO, True),
          (A_DISPATCH, OWNER, False),
          (A_MANAGE_MEMBERS_DIRECT, COMPANY_CEO, False),
          (A_OWNER_SUBMIT, OWNER, True),
          (A_OWNER_SUBMIT, MEMBER, False),
          (A_REVIEW_START, COACH, True),
          (A_REVIEW_START, COMPANY_CEO, False),
          (A_REQUEST_MEMBER_CHANGE, OWNER, True),
          (A_REQUEST_MEMBER_CHANGE, COACH, True),
          (A_REVIEW_MEMBER_CHANGE, COACH, True),
          (A_REVIEW_MEMBER_CHANGE, OWNER, False),
          (A_REQUEST_CLOSE, OWNER, True),
          (A_REVIEW_CLOSE_REQUEST, COACH, True),
          (A_ARCHIVE, ADMIN, True),
          (A_ARCHIVE, COMPANY_CEO, False),
          (A_DELETE, ADMIN, True),
          (A_TECHNICAL_KICKOFF, ADMIN, True),
      ],
  )
  def test_project_action_matrix(action, subject, allowed):
      assert decide_project_action(subject, ACTIVE, action).allowed is allowed

  def test_company_ceo_can_edit_source_only_in_draft():
      assert decide_project_action(COMPANY_CEO, replace(ACTIVE, lifecycle="draft"), A_EDIT_SOURCE).allowed
      decision = decide_project_action(COMPANY_CEO, ACTIVE, A_EDIT_SOURCE)
      assert not decision.allowed
      assert decision.status_code == 403

  def test_close_request_edit_requires_original_owner():
      owned = replace(ACTIVE, requester_person_id=OWNER.person_id)
      other = replace(ACTIVE, requester_person_id=999)
      assert decide_project_action(OWNER, owned, A_EDIT_CLOSE_REQUEST).allowed
      assert decide_project_action(OWNER, owned, A_CANCEL_CLOSE_REQUEST).allowed
      assert not decide_project_action(OWNER, other, A_EDIT_CLOSE_REQUEST).allowed
      assert decide_project_action(ADMIN, other, A_EDIT_CLOSE_REQUEST).allowed

  def test_company_ceo_is_not_project_coach():
      assert not decide_project_action(COMPANY_CEO, ACTIVE, A_REVIEW_START).allowed
      assert not decide_project_action(COMPANY_CEO, ACTIVE, A_REVIEW_CLOSE_REQUEST).allowed
  ```

- [ ] **Step 2: Run the policy tests and verify the import failure**

  ```powershell
  python -m pytest tests/test_project_permission_policy.py -q
  ```

  Expected: FAIL because `app.domain.project_permissions` does not exist.

- [ ] **Step 3: Implement the policy types and action vocabulary**

  Create `app/domain/project_permissions.py` with these public interfaces:

  ```python
  from __future__ import annotations

  from dataclasses import dataclass

  A_VIEW = "project.view"
  A_CREATE = "project.create"
  A_BATCH_IMPORT = "project.batch_import"
  A_EDIT_SOURCE = "project.edit_source"
  A_MANAGE_MEMBERS_DIRECT = "project.manage_members_direct"
  A_REQUEST_MEMBER_CHANGE = "project.request_member_change"
  A_REVIEW_MEMBER_CHANGE = "project.review_member_change"
  A_DISPATCH = "project.dispatch"
  A_OWNER_SUBMIT = "project.owner_submit"
  A_REVIEW_START = "project.review_start"
  A_REQUEST_CLOSE = "project.request_close"
  A_EDIT_CLOSE_REQUEST = "project.edit_close_request"
  A_CANCEL_CLOSE_REQUEST = "project.cancel_close_request"
  A_REVIEW_CLOSE_REQUEST = "project.review_close_request"
  A_ARCHIVE = "project.archive"
  A_DELETE = "project.delete"
  A_TECHNICAL_KICKOFF = "project.technical_kickoff"

  PROJECT_ROLES = frozenset({"owner", "coordinator", "member", "project_ceo"})

  @dataclass(frozen=True)
  class ProjectPermissionSubject:
      is_tech_admin: bool = False
      is_company_ceo: bool = False
      person_id: int | None = None
      project_roles: frozenset[str] = frozenset()

  @dataclass(frozen=True)
  class ProjectPermissionResource:
      project_id: int | None = None
      lifecycle: str = ""
      requester_person_id: int | None = None

  @dataclass(frozen=True)
  class PermissionDecision:
      allowed: bool
      status_code: int = 200
      code: str = ""
      detail: str = ""
  ```

  Implement `decide_project_action()` with explicit action groups:

  ```python
  _ADMIN_ONLY = {A_BATCH_IMPORT, A_ARCHIVE, A_DELETE, A_TECHNICAL_KICKOFF}
  _COMPANY_MANAGED = {A_CREATE, A_DISPATCH}
  _COACH_REVIEW = {A_REVIEW_MEMBER_CHANGE, A_REVIEW_START, A_REVIEW_CLOSE_REQUEST}
  _OWNER_ACTIONS = {A_OWNER_SUBMIT, A_REQUEST_CLOSE}

  def _allow() -> PermissionDecision:
      return PermissionDecision(True)

  def _deny(code: str, detail: str, status_code: int = 403) -> PermissionDecision:
      return PermissionDecision(False, status_code=status_code, code=code, detail=detail)

  def _admin_only_detail(action: str) -> str:
      if action == A_ARCHIVE:
          return "项目归档需提交公司管理审核。"
      return "仅超级管理员可执行此操作"

  def decide_project_action(subject, resource, action):
      roles = subject.project_roles & PROJECT_ROLES
      if subject.is_tech_admin:
          return PermissionDecision(True)
      if action == A_VIEW:
          return _allow() if subject.is_company_ceo or roles else _deny("PROJECT_ACCESS_DENIED", "permission denied — 仅项目成员可查看")
      if action in _ADMIN_ONLY:
          return _deny("PROJECT_ACTION_DENIED", _admin_only_detail(action))
      if action in _COMPANY_MANAGED:
          return _allow() if subject.is_company_ceo else _deny("PROJECT_ACTION_DENIED", "仅公司管理或超级管理员可执行此操作")
      if action in {A_EDIT_SOURCE, A_MANAGE_MEMBERS_DIRECT}:
          if subject.is_company_ceo and resource.lifecycle == "draft":
              return _allow()
          return _deny("PROJECT_ACTION_DENIED", "项目已下发，当前仅支持查看。如需调整，请走变更申请流程。")
      if action == A_REQUEST_MEMBER_CHANGE:
          return _allow() if roles & {"owner", "project_ceo"} else _deny("PROJECT_ACTION_DENIED", "仅项目负责人或企业教练可发起成员变更申请。")
      if action in _COACH_REVIEW:
          return _allow() if "project_ceo" in roles else _deny("PROJECT_ACTION_DENIED", "仅企业教练或超级管理员可执行此操作")
      if action in _OWNER_ACTIONS:
          return _allow() if "owner" in roles else _deny("PROJECT_ACTION_DENIED", "仅项目负责人或超级管理员可执行此操作")
      if action in {A_EDIT_CLOSE_REQUEST, A_CANCEL_CLOSE_REQUEST}:
          owned = subject.person_id is not None and subject.person_id == resource.requester_person_id and "owner" in roles
          return _allow() if owned else _deny("PROJECT_RESOURCE_OWNER_REQUIRED", "仅原申请人或超级管理员可执行此操作")
      raise ValueError(f"unknown project action: {action}")
  ```

  Implement `_allow`, `_deny`, and `_admin_only_detail` in the same module. `_admin_only_detail` must return the existing archive detail for `A_ARCHIVE` and `仅超级管理员可执行此操作` for the other technical-only actions.

- [ ] **Step 4: Run the policy tests**

  ```powershell
  python -m pytest tests/test_project_permission_policy.py -q
  ```

  Expected: PASS.

- [ ] **Step 5: Commit the pure policy**

  ```powershell
  git add bowei_ai_dashboard/app/domain/project_permissions.py bowei_ai_dashboard/tests/test_project_permission_policy.py
  git commit -m "feat: add project permission policy"
  ```

## Task 3: Isolate current and legacy project-role resolution

**Files:**

- Create: `bowei_ai_dashboard/app/compatibility/__init__.py`
- Create: `bowei_ai_dashboard/app/compatibility/project_roles.py`
- Create: `bowei_ai_dashboard/tests/test_project_role_compatibility.py`
- Modify: `bowei_ai_dashboard/app/permissions.py`

- [ ] **Step 1: Write failing compatibility tests**

  Create `tests/test_project_role_compatibility.py` with a temporary SQLite database and assert:

  ```python
  def test_project_members_are_authoritative(db, project, owner):
      db.add(ProjectMember(project_id=project.id, person_id=owner.id, role="owner"))
      project.collaborators = "旧字段成员"
      db.commit()
      resolution = resolve_project_roles(db, owner.id, project.id, allow_legacy=True)
      assert resolution.roles == frozenset({"owner"})
      assert resolution.source == "project_members"

  def test_legacy_fields_are_disabled_by_default(db, legacy_project, legacy_owner):
      resolution = resolve_project_roles(db, legacy_owner.id, legacy_project.id)
      assert resolution.roles == frozenset()
      assert resolution.source == "none"

  def test_legacy_fields_are_used_only_when_explicit_and_current_person_has_no_valid_roles(db, legacy_project, legacy_owner):
      resolution = resolve_project_roles(db, legacy_owner.id, legacy_project.id, allow_legacy=True)
      assert resolution.roles == frozenset({"owner"})
      assert resolution.source == "legacy_fields"

  def test_current_person_member_rows_disable_legacy_grants_for_that_person(db, project, legacy_owner):
      db.add(ProjectMember(project_id=project.id, person_id=legacy_owner.id, role="member"))
      project.owners = legacy_owner.name
      db.commit()
      resolution = resolve_project_roles(db, legacy_owner.id, project.id, allow_legacy=True)
      assert resolution.roles == frozenset({"member"})
      assert resolution.source == "project_members"

  def test_other_people_member_rows_do_not_disable_explicit_legacy_read_fallback(db, project, legacy_owner, member):
      db.add(ProjectMember(project_id=project.id, person_id=member.id, role="member"))
      project.owners = legacy_owner.name
      db.commit()
      resolution = resolve_project_roles(db, legacy_owner.id, project.id, allow_legacy=True)
      assert resolution.roles == frozenset({"owner"})
      assert resolution.source == "legacy_fields"
  ```

  Also test comma、Chinese-comma、顿号、slash、semicolon and newline separators, unknown roles, inactive people, and multi-role rows.

- [ ] **Step 2: Run and verify the missing-module failure**

  ```powershell
  python -m pytest tests/test_project_role_compatibility.py -q
  ```

  Expected: FAIL because `app.compatibility.project_roles` does not exist.

- [ ] **Step 3: Implement the role resolver**

  Create `app/compatibility/__init__.py` and `app/compatibility/project_roles.py`:

  ```python
  from dataclasses import dataclass
  import re
  from typing import Literal

  from sqlalchemy.orm import Session

  from .. import models

  VALID_PROJECT_ROLES = frozenset({"owner", "coordinator", "member", "project_ceo"})

  @dataclass(frozen=True)
  class ProjectRoleResolution:
      roles: frozenset[str]
      source: Literal["project_members", "legacy_fields", "none"]

  def resolve_project_roles(
      db: Session,
      person_id: int | None,
      project_id: int,
      *,
      allow_legacy: bool = False,
  ) -> ProjectRoleResolution:
      if person_id is None:
          return ProjectRoleResolution(frozenset(), "none")
      rows = db.query(models.ProjectMember).filter(
          models.ProjectMember.project_id == project_id,
          models.ProjectMember.person_id == person_id,
      ).all()
      valid_rows = [row for row in rows if row.role in VALID_PROJECT_ROLES]
      if valid_rows:
          roles = frozenset(row.role for row in valid_rows if row.person_id == person_id)
          return ProjectRoleResolution(roles, "project_members")
      if not allow_legacy:
          return ProjectRoleResolution(frozenset(), "none")
      project = db.get(models.Project, project_id)
      person = db.get(models.Person, person_id)
      if not project or not person or not person.is_active:
          return ProjectRoleResolution(frozenset(), "none")
      roles = _legacy_roles_for_name(person.name, project)
      return ProjectRoleResolution(frozenset(roles), "legacy_fields" if roles else "none")
  ```

  `_legacy_roles_for_name` must map `owners → owner`, exact `coordinator → coordinator`, and `collaborators → member` using one private `_split_names` helper. It must never synthesize `project_ceo`.

- [ ] **Step 4: Delegate the strict compatibility facade**

  Change `permissions.get_all_project_roles` to preserve its strict behavior:

  ```python
  def get_all_project_roles(person_id: int, project_id: int, db) -> list[str]:
      resolution = resolve_project_roles(db, person_id, project_id, allow_legacy=False)
      return sorted(resolution.roles)
  ```

  Import `resolve_project_roles` at module scope. Do not remove `_fallback_ctx_role` or the confirmation-domain compatibility code in this task.

- [ ] **Step 5: Verify compatibility and existing role tests**

  ```powershell
  python -m pytest tests/test_project_role_compatibility.py tests/test_role_boundary.py tests/test_company_ceo_owner_confirmation_permission.py -q
  ```

  Expected: PASS.

- [ ] **Step 6: Commit the compatibility layer**

  ```powershell
  git add bowei_ai_dashboard/app/compatibility/__init__.py bowei_ai_dashboard/app/compatibility/project_roles.py bowei_ai_dashboard/app/permissions.py bowei_ai_dashboard/tests/test_project_role_compatibility.py
  git commit -m "refactor: isolate project role compatibility"
  ```

## Task 4: Add compatible machine-readable API errors

**Files:**

- Create: `bowei_ai_dashboard/app/api_errors.py`
- Create: `bowei_ai_dashboard/tests/test_coded_http_errors.py`
- Modify: `bowei_ai_dashboard/app/main.py`
- Modify: `bowei_ai_dashboard/app/permissions.py`
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/api/client.test.ts`

- [ ] **Step 1: Write failing backend response tests**

  Create `tests/test_coded_http_errors.py`:

  ```python
  from fastapi import FastAPI
  from fastapi.testclient import TestClient

  from app.api_errors import CodedHTTPException, coded_http_exception_handler

  def test_coded_http_exception_keeps_detail_and_adds_code():
      app = FastAPI()
      app.add_exception_handler(CodedHTTPException, coded_http_exception_handler)

      @app.get("/denied")
      def denied():
          raise CodedHTTPException(403, "PROJECT_ACTION_DENIED", "仅公司管理或超级管理员可执行此操作")

      response = TestClient(app).get("/denied")
      assert response.status_code == 403
      assert response.json() == {
          "detail": "仅公司管理或超级管理员可执行此操作",
          "code": "PROJECT_ACTION_DENIED",
      }

  def test_account_identity_errors_use_stable_codes(db):
      with pytest.raises(CodedHTTPException) as missing:
          require_login("missing-account", db)
      assert (missing.value.status_code, missing.value.code, missing.value.detail) == (
          401, "AUTHENTICATION_REQUIRED", "unauthorized",
      )
  ```

- [ ] **Step 2: Write the failing frontend client test**

  Create `frontend/src/api/client.test.ts` and mock `globalThis.fetch`:

  ```typescript
  import { afterEach, describe, expect, it, vi } from 'vitest'
  import { apiGet, ApiError } from './client'

  afterEach(() => vi.unstubAllGlobals())

  describe('ApiError code compatibility', () => {
    it('reads a stable top-level code and preserves the detail message', async () => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
        JSON.stringify({ detail: '仅项目成员可查看', code: 'PROJECT_ACCESS_DENIED' }),
        { status: 403, headers: { 'Content-Type': 'application/json' } },
      )))
      await expect(apiGet('/api/projects/7')).rejects.toMatchObject({
        status: 403,
        code: 'PROJECT_ACCESS_DENIED',
        message: '仅项目成员可查看',
      })
    })

    it('falls back to API_ERROR when old responses have only detail', async () => {
      const error = new ApiError(403, 'permission denied', { detail: 'permission denied' })
      expect(error.code).toBe('API_ERROR')
    })
  })
  ```

- [ ] **Step 3: Run both tests and verify failure**

  ```powershell
  Set-Location bowei_ai_dashboard
  python -m pytest tests/test_coded_http_errors.py -q
  Set-Location ../frontend
  npm run test:unit -- src/api/client.test.ts
  Set-Location ..
  ```

  Expected: backend import fails and frontend `ApiError.code` is missing.

- [ ] **Step 4: Implement and register the coded exception**

  Create `app/api_errors.py`:

  ```python
  from fastapi import HTTPException, Request
  from fastapi.responses import JSONResponse

  class CodedHTTPException(HTTPException):
      def __init__(self, status_code: int, code: str, detail: str):
          super().__init__(status_code=status_code, detail=detail)
          self.code = code

  async def coded_http_exception_handler(_request: Request, exc: CodedHTTPException):
      return JSONResponse(
          status_code=exc.status_code,
          content={"detail": exc.detail, "code": exc.code},
          headers=exc.headers,
      )
  ```

  In `app/main.py`, import both symbols and register the handler immediately after `app = FastAPI(...)`:

  ```python
  app.add_exception_handler(CodedHTTPException, coded_http_exception_handler)
  ```

  In `app/permissions.py`, replace only `_load_account_identity` authentication and disabled-account exceptions:

  ```python
  raise CodedHTTPException(401, "AUTHENTICATION_REQUIRED", "unauthorized")
  raise CodedHTTPException(403, "ACCOUNT_DISABLED", "account_disabled")
  ```

  Keep `database_required` and unrelated business exceptions unchanged.

- [ ] **Step 5: Extend the frontend error type**

  In `frontend/src/api/client.ts`:

  ```typescript
  export class ApiError extends Error {
    status: number
    body: unknown
    readonly code: string

    constructor(status: number, message: string, body: unknown) {
      super(message)
      this.name = 'ApiError'
      this.status = status
      this.body = body
      this.code = extractCode(body)
    }
  }

  function extractCode(body: unknown): string {
    if (!body || typeof body !== 'object') return 'API_ERROR'
    const code = (body as { code?: unknown }).code
    return typeof code === 'string' && code.trim() ? code.trim() : 'API_ERROR'
  }
  ```

- [ ] **Step 6: Verify and commit coded errors**

  ```powershell
  Set-Location bowei_ai_dashboard
  python -m pytest tests/test_coded_http_errors.py tests/test_production_runtime_security.py -q
  Set-Location ../frontend
  npm run test:unit -- src/api/client.test.ts
  Set-Location ..
  git add bowei_ai_dashboard/app/api_errors.py bowei_ai_dashboard/app/main.py bowei_ai_dashboard/app/permissions.py bowei_ai_dashboard/tests/test_coded_http_errors.py frontend/src/api/client.ts frontend/src/api/client.test.ts
  git commit -m "feat: add stable project permission errors"
  ```

## Task 5: Add the project access orchestration service

**Files:**

- Create: `bowei_ai_dashboard/app/services/project_access.py`
- Create: `bowei_ai_dashboard/tests/test_project_access_service.py`

- [ ] **Step 1: Write failing service tests**

  Create `tests/test_project_access_service.py` using the same isolated account/project fixture as the characterization tests:

  ```python
  def test_authorize_project_action_builds_multi_role_subject(db, seeded_project):
      access = authorize_project_action("owner_coach", seeded_project, A_REVIEW_START, db)
      assert access.subject.project_roles == frozenset({"owner", "project_ceo"})
      assert access.role_source == "project_members"

  def test_strict_write_action_does_not_use_legacy_owner(db, legacy_project):
      with pytest.raises(CodedHTTPException) as error:
          authorize_project_action("legacy_owner", legacy_project, A_OWNER_SUBMIT, db)
      assert error.value.code == "PROJECT_ACTION_DENIED"

  def test_explicit_legacy_view_can_use_legacy_owner(db, legacy_project):
      access = authorize_project_action("legacy_owner", legacy_project, A_VIEW, db, allow_legacy_roles=True)
      assert access.role_source == "legacy_fields"

  def test_company_ceo_cannot_review_as_project_coach(db, seeded_project):
      with pytest.raises(CodedHTTPException) as error:
          authorize_project_action("company_ceo", seeded_project, A_REVIEW_START, db)
      assert error.value.status_code == 403
      assert error.value.code == "PROJECT_ACTION_DENIED"
  ```

- [ ] **Step 2: Run and verify the missing service**

  ```powershell
  python -m pytest tests/test_project_access_service.py -q
  ```

  Expected: FAIL because `app.services.project_access` does not exist.

- [ ] **Step 3: Implement access context and authorization functions**

  Create `app/services/project_access.py`:

  ```python
  from dataclasses import dataclass

  from sqlalchemy.orm import Session

  from .. import models
  from ..api_errors import CodedHTTPException
  from ..compatibility.project_roles import resolve_project_roles
  from ..domain.project_permissions import (
      ProjectPermissionResource,
      ProjectPermissionSubject,
      decide_project_action,
  )
  from ..domain.project_lifecycle import normalize as normalize_lifecycle
  from ..permissions import get_user_context_from_db

  @dataclass(frozen=True)
  class ProjectAccessContext:
      context: dict
      subject: ProjectPermissionSubject
      resource: ProjectPermissionResource
      role_source: str

  def authorize_project_action(
      current_user: str,
      project: models.Project,
      action: str,
      db: Session,
      *,
      requester_person_id: int | None = None,
      allow_legacy_roles: bool = False,
      denial_detail: str | None = None,
  ) -> ProjectAccessContext:
      context = get_user_context_from_db(current_user, db)
      resolution = resolve_project_roles(
          db,
          context.get("person_id"),
          project.id,
          allow_legacy=allow_legacy_roles,
      )
      subject = ProjectPermissionSubject(
          is_tech_admin=bool(context.get("is_tech_admin")),
          is_company_ceo=bool(context.get("is_ceo")),
          person_id=context.get("person_id"),
          project_roles=resolution.roles,
      )
      resource = ProjectPermissionResource(
          project_id=project.id,
          lifecycle=normalize_lifecycle(project.status),
          requester_person_id=requester_person_id,
      )
      decision = decide_project_action(subject, resource, action)
      if not decision.allowed:
          raise CodedHTTPException(
              decision.status_code,
              decision.code,
              denial_detail if denial_detail is not None else decision.detail,
          )
      return ProjectAccessContext(context, subject, resource, resolution.source)
  ```

  Add `authorize_global_project_action(current_user, action, db)` for create, batch import and other no-project actions. It builds an empty resource and uses the same decision function.

  ```python
  def authorize_global_project_action(
      current_user: str,
      action: str,
      db: Session,
  ) -> ProjectAccessContext:
      context = get_user_context_from_db(current_user, db)
      subject = ProjectPermissionSubject(
          is_tech_admin=bool(context.get("is_tech_admin")),
          is_company_ceo=bool(context.get("is_ceo")),
          person_id=context.get("person_id"),
      )
      resource = ProjectPermissionResource()
      decision = decide_project_action(subject, resource, action)
      if not decision.allowed:
          raise CodedHTTPException(decision.status_code, decision.code, decision.detail)
      return ProjectAccessContext(context, subject, resource, "none")
  ```

- [ ] **Step 4: Run service and characterization tests**

  ```powershell
  python -m pytest tests/test_project_access_service.py tests/test_project_permission_characterization.py tests/test_project_permission_policy.py -q
  ```

  Expected: PASS.

- [ ] **Step 5: Commit the access service**

  ```powershell
  git add bowei_ai_dashboard/app/services/project_access.py bowei_ai_dashboard/tests/test_project_access_service.py
  git commit -m "feat: add project access service"
  ```

## Task 6: Migrate project reads, source editing, and member operations

**Files:**

- Modify: `bowei_ai_dashboard/app/routers/projects.py`
- Modify: `bowei_ai_dashboard/app/services/project_access.py`
- Modify: `bowei_ai_dashboard/tests/test_project_permission_characterization.py`
- Modify: `bowei_ai_dashboard/tests/test_project_access_service.py`
- Test: `bowei_ai_dashboard/tests/test_project_member_notifications.py`
- Test: `bowei_ai_dashboard/tests/test_project_close_lifecycle_guards.py`

- [ ] **Step 1: Add service-call assertions before changing Router code**

  Extend the characterization tests with `monkeypatch` spies and assert each endpoint calls the intended action once:

  ```python
  @pytest.mark.parametrize(
      ("endpoint_case", "action"),
      [
          ("get_project", A_VIEW),
          ("list_members", A_VIEW),
          ("project_capabilities", A_VIEW),
          ("update_project", A_EDIT_SOURCE),
          ("add_member", A_MANAGE_MEMBERS_DIRECT),
          ("update_member", A_MANAGE_MEMBERS_DIRECT),
          ("remove_member", A_MANAGE_MEMBERS_DIRECT),
          ("create_member_change", A_REQUEST_MEMBER_CHANGE),
          ("review_member_change", A_REVIEW_MEMBER_CHANGE),
      ],
  )
  def test_project_endpoint_uses_access_service(endpoint_case, action, access_spy):
      access_spy.invoke(endpoint_case)
      assert access_spy.actions == [action]
  ```

  Implement `access_spy` in the test file with explicit endpoint invocations and a monkeypatched `projects.authorize_project_action`; do not inspect source text.

- [ ] **Step 2: Run the new assertions and verify failure**

  ```powershell
  python -m pytest tests/test_project_permission_characterization.py -q
  ```

  Expected: FAIL because the Router still calls private `_require_*` helpers.

- [ ] **Step 3: Replace read and source-management checks**

  In `routers/projects.py`:

  - Replace `_can_view_project` in `get_project` and `list_members` with `authorize_project_action(..., A_VIEW, allow_legacy_roles=True)`.
  - Replace `require_project_access` in `project_capabilities` and member-change request listing with `A_VIEW`; pass each endpoint's current `detail` through `denial_detail` when the existing texts differ.
  - Keep list filtering batch-based; add one `resolve_visible_project_ids(context, db, allow_legacy=True)` helper in `project_access.py` so `list_projects` does not query per row.
  - Replace `_require_project_source_manager` in `update_project`, `add_member`, `update_member`, and `remove_member` with `A_EDIT_SOURCE` or `A_MANAGE_MEMBERS_DIRECT`.
  - Preserve each endpoint's existing project-not-found and close-frozen check order.

  Add this batch helper to `project_access.py` and test that it executes a bounded number of queries regardless of project count:

  ```python
  def resolve_visible_project_ids(context: dict, db: Session, *, allow_legacy: bool) -> frozenset[int] | None:
      if context.get("can_view_all"):
          return None
      person_id = context.get("person_id")
      member_ids = {
          int(row[0])
          for row in db.query(models.ProjectMember.project_id)
          .filter(models.ProjectMember.person_id == person_id)
          .distinct()
          .all()
      } if person_id is not None else set()
      if not allow_legacy:
          return frozenset(member_ids)
      legacy_names = [str(name) for name in context.get("visible_projects") or [] if str(name).strip()]
      legacy_ids = {
          int(row[0])
          for row in db.query(models.Project.id).filter(models.Project.name.in_(legacy_names)).all()
      } if legacy_names else set()
      return frozenset(member_ids | legacy_ids)
  ```

  `None` means全局可见；空集合 means无可见项目。`list_projects` consumes this result once and never calls a role query inside its filtering loop.

  The call shape must be:

  ```python
  authorize_project_action(
      current_user,
      project,
      A_MANAGE_MEMBERS_DIRECT,
      db,
      allow_legacy_roles=False,
  )
  ```

- [ ] **Step 4: Replace member-change authorization checks**

  Use `A_REQUEST_MEMBER_CHANGE` for creation and `A_REVIEW_MEMBER_CHANGE` for approve/reject. Use `A_VIEW` for listing requests. Preserve automatic approval when the authorized subject contains `project_ceo` or is a technical administrator:

  ```python
  access = authorize_project_action(current_user, project, A_REQUEST_MEMBER_CHANGE, db)
  auto_approve = access.subject.is_tech_admin or "project_ceo" in access.subject.project_roles
  ```

- [ ] **Step 5: Run focused project/member tests**

  ```powershell
  python -m pytest tests/test_project_permission_characterization.py tests/test_project_member_notifications.py tests/test_project_close_lifecycle_guards.py tests/test_role_boundary.py -q
  ```

  Expected: PASS with unchanged public behavior.

- [ ] **Step 6: Commit the first Router migration**

  ```powershell
  git add bowei_ai_dashboard/app/routers/projects.py bowei_ai_dashboard/app/services/project_access.py bowei_ai_dashboard/tests/test_project_permission_characterization.py bowei_ai_dashboard/tests/test_project_access_service.py
  git commit -m "refactor: centralize project member permissions"
  ```

## Task 7: Migrate project creation and start-lifecycle actions

**Files:**

- Modify: `bowei_ai_dashboard/app/routers/projects.py`
- Modify: `bowei_ai_dashboard/tests/test_project_permission_characterization.py`
- Test: `bowei_ai_dashboard/tests/test_full_role_lifecycle_audit.py`

- [ ] **Step 1: Add failing action-spy cases**

  Add cases for:

  ```python
  ("create_project", A_CREATE)
  ("batch_import_projects", A_BATCH_IMPORT)
  ("dispatch_project", A_DISPATCH)
  ("owner_submit_project_profile", A_OWNER_SUBMIT)
  ("return_project", A_REVIEW_START)
  ("approve_project", A_REVIEW_START)
  ("kickoff_project", A_TECHNICAL_KICKOFF)
  ```

  Run the characterization file and expect these new cases to fail before migration.

- [ ] **Step 2: Migrate global project actions**

  Replace `_require_ceo_or_tech_admin` and `_require_super_admin` at the relevant endpoints with:

  ```python
  authorize_global_project_action(current_user, A_CREATE, db)
  authorize_global_project_action(current_user, A_BATCH_IMPORT, db)
  authorize_global_project_action(current_user, A_TECHNICAL_KICKOFF, db)
  ```

  Keep unrelated technical-only purge cleanup on the existing helper until Task 8.

- [ ] **Step 3: Migrate dispatch, owner submit, and coach review**

  Call `authorize_project_action` with `A_DISPATCH`, `A_OWNER_SUBMIT`, or `A_REVIEW_START` after preserving the endpoint's current project lookup order. For owner submit, pass `denial_detail="permission denied"` to retain the existing `require_project_role` response. Convert existing project-lifecycle 409 denials in these migrated endpoints to `CodedHTTPException(409, "PROJECT_STATE_CONFLICT", existing_detail)` without changing `existing_detail`. Do not move date validation, required-role validation, work-progress resolution, notifications, audit logs or commits into the access service.

- [ ] **Step 4: Verify lifecycle behavior**

  ```powershell
  python -m pytest tests/test_project_permission_characterization.py tests/test_full_role_lifecycle_audit.py tests/test_project_init_work_progress_draft.py tests/test_project_lifecycle_simplification.py tests/test_role_boundary.py -q
  ```

  Expected: PASS; company management can dispatch but cannot approve as project coach.

- [ ] **Step 5: Commit the lifecycle authorization migration**

  ```powershell
  git add bowei_ai_dashboard/app/routers/projects.py bowei_ai_dashboard/tests/test_project_permission_characterization.py
  git commit -m "refactor: centralize project lifecycle permissions"
  ```

## Task 8: Migrate close, archive, delete, and cleanup authorization

**Files:**

- Modify: `bowei_ai_dashboard/app/routers/projects.py`
- Modify: `bowei_ai_dashboard/tests/test_project_permission_characterization.py`
- Test: `bowei_ai_dashboard/tests/test_project_close_request_permissions.py`
- Test: `bowei_ai_dashboard/tests/test_project_close_request_flow.py`
- Test: `bowei_ai_dashboard/tests/test_project_close_request_notifications.py`
- Test: `bowei_ai_dashboard/tests/test_project_close_lifecycle_guards.py`
- Test: `bowei_ai_dashboard/tests/test_project_purge_storage.py`

- [ ] **Step 1: Add failing action-spy cases for terminal lifecycle operations**

  Cover `A_REQUEST_CLOSE`, `A_EDIT_CLOSE_REQUEST`, `A_CANCEL_CLOSE_REQUEST`, `A_REVIEW_CLOSE_REQUEST`, `A_ARCHIVE`, and `A_DELETE`. For edit/cancel, pass `requester_person_id` from the locked request into the access service.

- [ ] **Step 2: Preserve lock ordering while replacing close helpers**

  For create close request, authorize the owner before mutation, then recheck lifecycle after `_lock_project_for_close`. For edit/cancel/review, load and lock project/request as currently implemented, then call:

  ```python
  authorize_project_action(
      current_user,
      project,
      A_EDIT_CLOSE_REQUEST,
      db,
      requester_person_id=request.requester_person_id,
  )
  ```

  Preserve `_ensure_pending_close_pair`, blocker evaluation, audit, notification, commit and rollback behavior. Convert the existing 409 lifecycle denials in these endpoints to `CodedHTTPException(409, "PROJECT_STATE_CONFLICT", existing_detail)` while preserving the text.

- [ ] **Step 3: Migrate archive, delete, and purge cleanup**

  Use `A_ARCHIVE` for archive and `A_DELETE` for both permanent deletion and purge-cleanup retry. Keep double confirmation, staged file recovery and lifecycle checks unchanged. Do not move filesystem cleanup into the permission service.

- [ ] **Step 4: Verify close and destructive-operation tests**

  ```powershell
  python -m pytest tests/test_project_permission_characterization.py tests/test_project_close_request_permissions.py tests/test_project_close_request_flow.py tests/test_project_close_request_notifications.py tests/test_project_close_lifecycle_guards.py tests/test_project_purge_storage.py -q
  ```

  Expected: PASS.

- [ ] **Step 5: Remove only now-unused project Router permission helpers**

  Use:

  ```powershell
  rg -n "_require_super_admin|_require_project_manager|_require_ceo_or_tech_admin|_require_project_coach_or_tech_admin|_require_project_source_manager|_require_archive_via_approval|_require_close_request_owner|_require_original_close_requester|_require_close_request_view" bowei_ai_dashboard/app/routers/projects.py
  ```

  Delete a helper only when it has no remaining call sites. Keep `permissions.py` functions still used by other routers.

- [ ] **Step 6: Commit the terminal lifecycle migration**

  ```powershell
  git add bowei_ai_dashboard/app/routers/projects.py bowei_ai_dashboard/tests/test_project_permission_characterization.py
  git commit -m "refactor: centralize project close permissions"
  ```

## Task 9: Consolidate frontend project permission decisions

**Files:**

- Modify: `frontend/src/domain/permissions.ts`
- Create: `frontend/src/domain/permissions.test.ts`
- Modify: `frontend/src/domain/projectCloseUi.ts`
- Create: `frontend/src/domain/projectCloseUi.test.ts`
- Modify: `frontend/src/app/guards/RequireCapability.tsx`
- Modify: `frontend/src/pages/ProjectAdminPage.tsx`
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx`
- Modify: `frontend/src/features/settings/ProjectCloseFlowDrawer.tsx`
- Modify: `frontend/src/pages/ProjectOwnerSubmitPage.tsx`

- [ ] **Step 1: Write the frontend action-matrix tests**

  Add `frontend/src/domain/permissions.test.ts`:

  ```typescript
  import { describe, expect, it } from 'vitest'
  import { canProjectAction, type ProjectPermissionInput } from './permissions'

  const input = (patch: Partial<ProjectPermissionInput> = {}): ProjectPermissionInput => ({
    isTechAdmin: false,
    isCompanyCeo: false,
    personId: 7,
    projectRoles: [],
    lifecycle: 'active',
    requesterPersonId: null,
    ...patch,
  })

  describe('project permission display matrix', () => {
    it('separates company management from project coach review', () => {
      expect(canProjectAction('project.dispatch', input({ isCompanyCeo: true, lifecycle: 'draft' }))).toBe(true)
      expect(canProjectAction('project.review_start', input({ isCompanyCeo: true }))).toBe(false)
      expect(canProjectAction('project.review_start', input({ projectRoles: ['project_ceo'] }))).toBe(true)
    })

    it('allows only the original owner to edit a close request', () => {
      expect(canProjectAction('project.edit_close_request', input({ projectRoles: ['owner'], requesterPersonId: 7 }))).toBe(true)
      expect(canProjectAction('project.edit_close_request', input({ projectRoles: ['owner'], requesterPersonId: 8 }))).toBe(false)
    })

    it('keeps archive and delete technical-admin only', () => {
      expect(canProjectAction('project.archive', input({ isTechAdmin: true, lifecycle: 'ended' }))).toBe(true)
      expect(canProjectAction('project.archive', input({ isCompanyCeo: true, lifecycle: 'ended' }))).toBe(false)
      expect(canProjectAction('project.delete', input({ projectRoles: ['owner'] }))).toBe(false)
    })
  })
  ```

  Create `frontend/src/domain/projectCloseUi.test.ts` to lock the existing labels and delegate decisions:

  ```typescript
  import { describe, expect, it } from 'vitest'
  import {
    canCreateProjectCloseRequest,
    canEditProjectCloseRequest,
    canReviewProjectCloseRequest,
    getProjectCloseMainAction,
  } from './projectCloseUi'

  const owner = { isSuperAdmin: false, isCompanyCeo: false, isRealProjectCeo: false, isRealOwner: true }
  const coach = { isSuperAdmin: false, isCompanyCeo: false, isRealProjectCeo: true, isRealOwner: false }

  describe('project close UI compatibility', () => {
    it('keeps the current lifecycle action labels', () => {
      expect(getProjectCloseMainAction('active', owner)).toEqual({ type: 'workProgress', label: '进入工作推进表' })
      expect(getProjectCloseMainAction('pending_close', coach)).toEqual({ type: 'closeReview', label: '审核结束申请' })
      expect(getProjectCloseMainAction('archived', owner)).toEqual({ type: 'projectArchive', label: '查看项目档案' })
    })

    it('delegates create, edit and review permission without widening roles', () => {
      expect(canCreateProjectCloseRequest('active', owner)).toBe(true)
      expect(canEditProjectCloseRequest('pending_close', 7, 7, owner)).toBe(true)
      expect(canReviewProjectCloseRequest('pending_close', coach)).toBe(true)
      expect(canReviewProjectCloseRequest('pending_close', owner)).toBe(false)
    })
  })
  ```

- [ ] **Step 2: Run and verify failure**

  ```powershell
  npm run test:unit -- src/domain/permissions.test.ts
  ```

  Expected: FAIL because `canProjectAction` and `ProjectPermissionInput` do not exist.

- [ ] **Step 3: Implement the frontend project action policy**

  Extend `permissions.ts` with the same action union used by the backend:

  ```typescript
  export type ProjectAction =
    | 'project.view'
    | 'project.create'
    | 'project.batch_import'
    | 'project.edit_source'
    | 'project.manage_members_direct'
    | 'project.request_member_change'
    | 'project.review_member_change'
    | 'project.dispatch'
    | 'project.owner_submit'
    | 'project.review_start'
    | 'project.request_close'
    | 'project.edit_close_request'
    | 'project.cancel_close_request'
    | 'project.review_close_request'
    | 'project.archive'
    | 'project.delete'
    | 'project.technical_kickoff'

  export type ProjectPermissionInput = {
    isTechAdmin?: boolean
    isCompanyCeo?: boolean
    personId?: number | null
    projectRoles?: readonly string[] | null
    lifecycle?: string | null
    requesterPersonId?: number | null
  }
  ```

  Implement one exhaustive `switch (action)` matching the backend role matrix and current UI lifecycle gates:

  ```typescript
  export function canProjectAction(action: ProjectAction, input: ProjectPermissionInput): boolean {
    const roles = input.projectRoles ?? []
    const has = (...allowed: ProjectRole[]) => roles.some((role) => allowed.includes(role as ProjectRole))
    const tech = Boolean(input.isTechAdmin)
    const companyCeo = Boolean(input.isCompanyCeo)
    const lifecycle = input.lifecycle ?? ''

    switch (action) {
      case 'project.view':
        return tech || companyCeo || has('owner', 'coordinator', 'member', 'project_ceo')
      case 'project.create':
        return tech || companyCeo
      case 'project.batch_import':
      case 'project.delete':
        return tech
      case 'project.edit_source':
      case 'project.manage_members_direct':
        return tech || (companyCeo && lifecycle === 'draft')
      case 'project.request_member_change':
        return !['draft', 'pending_close', 'ended', 'archived'].includes(lifecycle) && (tech || has('owner', 'project_ceo'))
      case 'project.review_member_change':
        return !['pending_close', 'ended', 'archived'].includes(lifecycle) && (tech || has('project_ceo'))
      case 'project.dispatch':
        return lifecycle === 'draft' && (tech || companyCeo)
      case 'project.owner_submit':
        return ['dispatched', 'returned'].includes(lifecycle) && (tech || has('owner'))
      case 'project.review_start':
        return !['pending_close', 'ended', 'archived'].includes(lifecycle) && (tech || has('project_ceo'))
      case 'project.request_close':
        return lifecycle === 'active' && (tech || has('owner'))
      case 'project.edit_close_request':
      case 'project.cancel_close_request':
        return lifecycle === 'pending_close' && (
          tech || (has('owner') && input.personId != null && input.personId === input.requesterPersonId)
        )
      case 'project.review_close_request':
        return lifecycle === 'pending_close' && (tech || has('project_ceo'))
      case 'project.archive':
        return lifecycle === 'ended' && tech
      case 'project.technical_kickoff':
        return !['pending_close', 'ended', 'archived'].includes(lifecycle) && tech
    }
  }
  ```

  TypeScript's exhaustive union makes unknown actions a compile error; do not add a permissive default.

- [ ] **Step 4: Preserve current helper exports as adapters**

  Keep current signatures and behavior while delegating:

  ```typescript
  export function canManageProjects(user: CurrentUserLike, roles?: readonly string[] | null): boolean {
    return canProjectAction('project.create', {
      isTechAdmin: user?.is_tech_admin,
      isCompanyCeo: user?.is_ceo,
      projectRoles: roles,
    }) || hasProjectRole(roles, 'project_ceo')
  }

  export function canWriteProjectMainData(user: CurrentUserLike, roles: readonly string[] | null | undefined): boolean {
    return canProjectAction('project.owner_submit', {
      isTechAdmin: user?.is_tech_admin,
      projectRoles: roles,
      lifecycle: 'dispatched',
    })
  }
  ```

  `projectCloseUi.ts` remains responsible for choosing labels, but its create/edit/review booleans delegate to `canProjectAction` using the supplied status and role flags.

- [ ] **Step 5: Migrate project UI call sites**

  In the listed guard/pages/components, replace inline combinations such as:

  ```typescript
  currentUser?.is_tech_admin || roles.includes('owner')
  ```

  with named `canProjectAction` calls. Build a single `ProjectPermissionInput` per selected project and reuse it within the component. Do not hide API errors solely because a button is hidden.

- [ ] **Step 6: Verify frontend permissions and project UI**

  ```powershell
  npm run test:unit -- src/domain/permissions.test.ts src/domain/projectCloseUi.test.ts
  npm run test:contracts
  npm run build
  ```

  Expected: PASS. Existing ExcelJS chunk-size warning may remain visible.

- [ ] **Step 7: Commit frontend consolidation**

  ```powershell
  git add frontend/src/domain/permissions.ts frontend/src/domain/permissions.test.ts frontend/src/domain/projectCloseUi.ts frontend/src/domain/projectCloseUi.test.ts frontend/src/app/guards/RequireCapability.tsx frontend/src/pages/ProjectAdminPage.tsx frontend/src/features/settings/ProjectsMgmtSection.tsx frontend/src/features/settings/ProjectCloseFlowDrawer.tsx frontend/src/pages/ProjectOwnerSubmitPage.tsx
  git commit -m "refactor: unify frontend project permissions"
  ```

## Task 10: Audit direct permission logic and run the complete gate

**Files:**

- Modify only if an audit finds an in-scope missed call site.
- Verify: `bowei_ai_dashboard/app/routers/projects.py`
- Verify: `bowei_ai_dashboard/app/permissions.py`
- Verify: `frontend/src/domain/permissions.ts`
- Verify: `.github/workflows/cloud-p1b2a-gate.yml`

- [ ] **Step 1: Audit backend project-role reads**

  ```powershell
  rg -n "get_all_project_roles|project_members|\.owners|\.coordinator|\.collaborators|is_tech_admin|is_ceo" bowei_ai_dashboard/app/routers/projects.py
  ```

  Expected: role loading and role combination checks are absent from endpoint bodies, except response construction, notifications, member synchronization and explicitly documented non-authorization uses. Every project write endpoint must call `authorize_project_action` or `authorize_global_project_action`.

- [ ] **Step 2: Audit frontend inline role combinations**

  ```powershell
  rg -n "is_tech_admin.*owner|owner.*is_tech_admin|includes\('project_ceo'\)|includes\('owner'\)|is_ceo" frontend/src/app/guards/RequireCapability.tsx frontend/src/pages/ProjectAdminPage.tsx frontend/src/features/settings/ProjectsMgmtSection.tsx frontend/src/features/settings/ProjectCloseFlowDrawer.tsx frontend/src/pages/ProjectOwnerSubmitPage.tsx
  ```

  Expected: no in-scope authorization expression remains outside `domain/permissions.ts`; role values may remain for labels and payload construction.

- [ ] **Step 3: Run the complete backend suite**

  ```powershell
  Set-Location bowei_ai_dashboard
  python -m pytest tests -q
  Set-Location ..
  ```

  Expected: exit 0. Existing circular meeting/document foreign-key warnings remain visible and are not converted into ignored failures.

- [ ] **Step 4: Run the complete frontend suite and build**

  ```powershell
  Set-Location frontend
  npm run test:all
  npm run build
  Set-Location ..
  ```

  Expected: both commands exit 0.

- [ ] **Step 5: Verify migration and patch hygiene**

  ```powershell
  Set-Location bowei_ai_dashboard
  python -m alembic heads
  Set-Location ..
  git diff --check
  git status --short
  ```

  Expected: exactly one Alembic head, no whitespace errors, and no migration file added. Only plan-listed files and pre-existing user changes may appear.

- [ ] **Step 6: Verify CI remains fail closed**

  ```powershell
  rg -n "python -m pytest tests -q|npm run test:all|npm run build|PostgreSQL 16 migration gate" .github/workflows/cloud-p1b2a-gate.yml
  rg -n "known structural baseline|allowed = \{|continue-on-error|mapfile|node --test" .github/workflows/cloud-p1b2a-gate.yml
  ```

  Expected: required gates match; bypass patterns have no matches.

- [ ] **Step 7: Commit any final in-scope audit correction**

  If Step 1 or Step 2 required an in-scope correction, stage only those exact files and commit:

  ```powershell
  git commit -m "test: complete project permission audit"
  ```

  If no correction was required, do not create an empty commit.

## Deferred findings

- Confirmation-center role visibility and decisions remain in `services/policy.py` and existing `permissions.py` functions until the confirmation/meeting governance plan.
- Meeting/document circular foreign keys remain unchanged.
- A permission difference discovered by characterization is documented for review; it is not fixed inside a refactor commit.
- Removing old project string columns requires a separate data-coverage report and database migration design.
- Database-configurable RBAC, tenant-specific policy editing and permission administration UI are intentionally out of scope.
