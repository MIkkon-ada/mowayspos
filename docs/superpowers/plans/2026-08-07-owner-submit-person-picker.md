# 立项提交人员选择 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让立项工作台的关键任务负责人单选、协助人多选全系统人员，并在提交时原子地将新选择的人加入项目协同成员。

**Architecture:** 前端在 `OwnerSubmitModal` 加载有效人员，草稿记录人员 ID 和显示姓名；负责人使用 `<select>`，协助人使用多选复选框。`owner-submit` 请求把 ID 随工作推进草稿发到后端；后端先解析、校验并补充项目成员，再保存任务草稿，最后统一提交事务。

**Tech Stack:** React 19 + TypeScript、FastAPI + Pydantic、SQLAlchemy、pytest。

---

### Task 1: 为请求与后端成员同步建立回归测试

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_project_init_work_progress_draft.py`
- Modify: `bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py`

- [ ] **Step 1: 写出后端失败测试，描述负责人和多个协助人自动入项**

  在 `_seed_project_team` 的现有三位人员外，创建 ID 为 5、6、7 的启用人员；以 `assignee_id=5` 和 `helper_ids=[6, 7, 6]` 的关键任务草稿调用 `owner_submit_project_profile`。断言项目成员中 ID 5、6、7 都仅有一条 `role == "member"` 记录，且关键任务保存姓名快照：

  ```python
  assert {(m.person_id, m.role) for m in members} >= {(5, "member"), (6, "member"), (7, "member")}
  assert len([m for m in members if m.person_id == 6 and m.role == "member"]) == 1
  assert subtasks[0].assignee == "New Assignee"
  assert "Helper One" in subtasks[0].notes
  assert "Helper Two" in subtasks[0].notes
  ```

- [ ] **Step 2: 运行测试确认其因缺少 ID 字段和同步逻辑而失败**

  Run: `python -m pytest bowei_ai_dashboard/tests/test_project_init_work_progress_draft.py -q`

  Expected: FAIL，提示 Pydantic 不接受/忽略 `assignee_id` 或 `helper_ids`，或新增成员断言不成立。

- [ ] **Step 3: 写出前端结构失败测试**

  在 `test_project_init_work_progress_frontend.py` 新增断言，要求 API 类型和工作台源码包含：

  ```python
  for expected in ["assignee_id?: number", "helper_ids?: number[]"]:
      assert expected in api_source
  for expected in ["fetchPeople", "assigneeId", "helperIds", "multiple", "type=\"checkbox\""]:
      assert expected in source
  ```

  并断言关键任务负责人不再使用其原有的自由文本 `placeholder="负责人"` 输入。

- [ ] **Step 4: 运行结构测试确认失败**

  Run: `python -m pytest bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py -q`

  Expected: FAIL，缺少 `assignee_id`、`helper_ids` 与人员选择器实现。

### Task 2: 扩展草稿契约并原子同步项目成员

**Files:**
- Modify: `bowei_ai_dashboard/app/schemas.py:364-393`
- Modify: `bowei_ai_dashboard/app/routers/projects.py:579-645`
- Modify: `frontend/src/api/projects.ts:114-130`
- Test: `bowei_ai_dashboard/tests/test_project_init_work_progress_draft.py`

- [ ] **Step 1: 在草稿模型和前端请求类型加入人员 ID**

  将 `ProjectWorkProgressSubTaskDraft` 和 TypeScript 的 `ProjectWorkProgressSubTaskDraft` 扩展为：

  ```python
  assignee_id: int | None = None
  helper_ids: list[int] = Field(default_factory=list)
  ```

  ```ts
  assignee_id?: number
  helper_ids?: number[]
  ```

  保留 `assignee` 和 `helper` 字段作为旧客户端兼容输入及任务表的姓名快照。

- [ ] **Step 2: 实现人员 ID 解析与项目成员补齐**

  在 `_save_work_progress_draft` 前新增私有辅助函数，收集每条非空关键任务的负责人 ID 和协助人 ID，去除空值与重复值；每个 ID 必须对应 `is_active=True` 的 `models.Person`。任一无效 ID 抛出 `HTTPException(422, ...)`。

  对有效人员执行：

  ```python
  existing = db.query(models.ProjectMember).filter_by(
      project_id=project.id, person_id=person.id
  ).first()
  if not existing:
      db.add(models.ProjectMember(
          project_id=project.id,
          person_id=person.id,
          person_name_snapshot=person.name,
          role="member",
          joined_at=utc_now(),
      ))
  ```

  调用 `db.flush()` 后执行 `_sync_project_old_fields(project.id, db)`，使项目成员关系和旧展示字段一致。

- [ ] **Step 3: 以 ID 解析姓名并保存任务快照**

  对含 ID 的关键任务，以已校验的 `Person` 记录覆盖 `subtask.assignee` 和协助人的 `subtask.notes`；没有 ID 的旧请求继续使用原有姓名字段。协助人姓名按选择顺序用 `、` 拼接，再传入已有 `_helper_note`。同时将 `subtask.assignee_id` 直接写为提交的 ID，避免按同名人员反查。

- [ ] **Step 4: 运行后端测试确认通过**

  Run: `python -m pytest bowei_ai_dashboard/tests/test_project_init_work_progress_draft.py -q`

  Expected: PASS，包含既有的草稿保存、权限校验及新增的成员自动补齐断言。

### Task 3: 将工作台人员字段替换为选择控件

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx:1-160`
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx:445-460`
- Test: `bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py`

- [ ] **Step 1: 加载人员并扩展本地草稿**

  导入 `useEffect`、`fetchPeople` 与 `Person`；新增 `people`、`peopleLoading`、`peopleError` 状态，并在弹窗打开后调用 `fetchPeople()`。过滤 `person.is_active !== false` 的人员。

  将本地关键任务草稿定义改为：

  ```ts
  assignee: string
  assigneeId: number | ''
  helper: string
  helperIds: number[]
  ```

  当负责人变更时同步其姓名和 ID；协助人复选框切换时以 ID 去重并基于人员列表重建 `helper` 姓名字符串。负责人从协助人中排除，避免同一人重复担任两个角色。

- [ ] **Step 2: 在 `toPayloadDraft` 映射 ID 字段**

  对每一个子任务增加：

  ```ts
  assignee_id: subtask.assigneeId || undefined,
  helper_ids: subtask.helperIds,
  ```

  保留现有 `assignee` 和 `helper` 映射，确保旧审核页与展示逻辑不受影响。

- [ ] **Step 3: 实现单选负责人和多选协助人 UI**

  用一个原生 `<select>` 替换负责人 `<input>`，包含“请选择负责人”占位项、姓名和部门。协助人使用一个可展开的复选框列表，每一行 `type="checkbox"`；不渲染当前负责人对应的选项。无人员时显示加载/错误提示，加载失败时保留错误信息。

  `handleSubmit` 在 `peopleLoading` 或 `peopleError` 时显示 toast 并返回；每个有标题的关键任务若没有负责人 ID，显示“请选择关键任务负责人”并阻止提交。

- [ ] **Step 4: 运行前端结构测试确认通过**

  Run: `python -m pytest bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py bowei_ai_dashboard/tests/test_owner_submit_modal_semantics_frontend.py -q`

  Expected: PASS，既有工作台语义断言不回归，新增的人员 ID 和多选控件断言通过。

### Task 4: 验证原子失败与构建产物

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_project_init_work_progress_draft.py`
- Verify: `frontend/src/features/settings/OwnerSubmitModal.tsx`

- [ ] **Step 1: 添加无效人员 ID 原子失败测试**

  以不存在的 `assignee_id=9999` 提交草稿，并断言抛出 `HTTPException` 422、项目状态仍是 `dispatched`、`Task` 和 `ProjectMember` 数量不变：

  ```python
  with pytest.raises(HTTPException) as exc:
      owner_submit_project_profile(1, payload, current_user="owner", db=db)
  assert exc.value.status_code == 422
  assert db.get(models.Project, 1).status == "dispatched"
  assert db.query(models.Task).filter_by(project_id=1).count() == 0
  ```

- [ ] **Step 2: 运行专项后端测试确认通过**

  Run: `python -m pytest bowei_ai_dashboard/tests/test_project_init_work_progress_draft.py -q`

  Expected: PASS，验证任意人员 ID 无效时不写入成员、项目字段或草稿。

- [ ] **Step 3: 运行完整相关测试与前端构建**

  Run: `python -m pytest bowei_ai_dashboard/tests/test_project_init_work_progress_draft.py bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py bowei_ai_dashboard/tests/test_owner_submit_modal_semantics_frontend.py -q`

  Expected: PASS。

  Run: `npm run build`

  Working directory: `frontend`

  Expected: TypeScript 编译和 Vite 打包成功。

- [ ] **Step 4: 提交实现**

  ```bash
  git add bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/app/routers/projects.py \
    bowei_ai_dashboard/tests/test_project_init_work_progress_draft.py \
    bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py \
    frontend/src/api/projects.ts frontend/src/features/settings/OwnerSubmitModal.tsx
  git commit -m "feat: select people in owner submission"
  ```
