# 关键任务月计划工作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将关键任务详情升级为默认打开本月、按紧急程度排序的月计划执行工作台，同时保留现有三级任务结构和过程记录。

**Architecture:** 在现有 `execution_schedules` 表上扩展月计划的通用业务字段，新月计划固定以 `plan_type="month"` 存储；既有周计划接口和数据保持兼容。新增独立的月计划路由与前端 API，后端统一计算动态“已延期”和排序权重；关键任务详情组合新的月计划工作台、现有任务摘要与过程记录，不改工作推进表入口。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、Pydantic v2、React 19、TypeScript、Tailwind CSS、pytest、node:test、Vitest。

---

## File structure

- Create: `bowei_ai_dashboard/migrations/versions/a8b9c0d1e2f3_add_month_plan_fields.py` — 为现有执行安排表增加月计划字段，并让日期可选。
- Create: `bowei_ai_dashboard/app/routers/monthly_plans.py` — 月计划列表、创建、编辑和软删除 API；复用既有执行安排表与项目权限。
- Modify: `bowei_ai_dashboard/app/models.py` — 扩展 `ExecutionSchedule` ORM 字段。
- Modify: `bowei_ai_dashboard/app/schemas.py` — 定义月计划创建、更新和状态闭环校验模型。
- Modify: `bowei_ai_dashboard/app/main.py` — 注册月计划路由。
- Modify: `bowei_ai_dashboard/app/routers/subtasks.py` — 关键任务详情只保留已有执行安排兼容投影；不将月计划审计字段暴露给表单。
- Create: `bowei_ai_dashboard/tests/test_monthly_plans.py` — 模型、排序、权限、状态闭环和审计 API 测试。
- Create: `frontend/src/api/monthlyPlans.ts` — 月计划 TypeScript 类型及 HTTP 客户端。
- Create: `frontend/src/domain/monthPlans.ts` — 月份切换、显示状态、稳定排序和本月概览的纯函数。
- Create: `frontend/src/domain/monthPlans.test.ts` — 纯函数单元测试。
- Create: `frontend/src/components/task-management/MonthlyPlanDrawer.tsx` — 新建、查看和编辑月计划的抽屉。
- Create: `frontend/src/components/task-management/MonthlyPlanWorkspace.tsx` — 默认本月、月份切换、排序后的月计划主区域。
- Modify: `frontend/src/components/task-management/KeyTaskExecutionDetailView.tsx` — 改为任务摘要 + 月计划主区 + 概览/过程记录的工作台布局。
- Modify: `frontend/src/pages/TaskManagementPage.tsx` — 传入当前项目成员，并在进入关键任务详情前确保成员数据已加载。
- Modify: `frontend/tests/executionScheduleTimeline.test.mjs` — 删除对被替换时间轴的结构断言，改为月计划工作台结构断言。
- Modify: `frontend/tests/keyTaskExecutionDetailLayout.test.mjs` — 验证详情页保持原入口、任务摘要与过程记录，并集成月计划工作台。

## Compatibility decisions

- 当前 `ExecutionSchedule` 的周计划记录和 `/api/subtasks/{id}/execution-schedules` 接口不删除、不迁移语义；它们继续服务已有提醒与历史数据。
- 新工作台只读取 `plan_type="month"` 且具有 `plan_month` 的月计划记录；旧月度执行安排不会被删除，仍可由原执行安排接口读取。
- 新月计划不要求日期。若填写日期，必须同时填写开始与截止日期，截止日期不得早于开始日期；只有填写了截止日期的未完成计划才可能动态显示为“已延期”。
- 月计划状态只保存 `未开始`、`进行中`、`暂缓`、`已完成`、`已取消`；“已延期”仅是后端投影的动态显示状态，不写入数据库。

### Task 1: 扩展执行安排持久化模型

**Files:**
- Create: `bowei_ai_dashboard/migrations/versions/a8b9c0d1e2f3_add_month_plan_fields.py`
- Modify: `bowei_ai_dashboard/app/models.py:777-793`
- Test: `bowei_ai_dashboard/tests/test_monthly_plans.py`

- [ ] **Step 1: 写出失败的 ORM 字段测试**

在 `bowei_ai_dashboard/tests/test_monthly_plans.py` 写入：

```python
from datetime import date

from app import models


def test_month_plan_persists_optional_dates_and_business_fields(db):
    row = models.ExecutionSchedule(
        subtask_id=1,
        plan_type="month",
        plan_month="2026-08",
        title="完成本月方案",
        expected_output="确认可执行方案",
        assignee="邹奇敏",
        assignee_id=2,
        collaborator_ids=[3, 4],
        status="进行中",
        progress_note="已完成首版",
        risk_dependency="等待合作方确认",
    )
    db.add(row)
    db.commit()
    loaded = db.get(models.ExecutionSchedule, row.id)

    assert loaded.plan_month == "2026-08"
    assert loaded.start_date is None
    assert loaded.due_date is None
    assert loaded.expected_output == "确认可执行方案"
    assert loaded.collaborator_ids == [3, 4]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd bowei_ai_dashboard; pytest tests/test_monthly_plans.py::test_month_plan_persists_optional_dates_and_business_fields -v`

Expected: FAIL，提示 `ExecutionSchedule` 尚无 `plan_month` 或其他月计划字段。

- [ ] **Step 3: 新建可升级的数据库迁移**

先确认当前链头，再创建迁移；当前仓库链头应为 `a6b7c8d9e0f1`：

```powershell
cd bowei_ai_dashboard
python -m alembic heads
```

在 `a8b9c0d1e2f3_add_month_plan_fields.py` 使用 `down_revision = "a6b7c8d9e0f1"`。迁移必须：

```python
def upgrade() -> None:
    with op.batch_alter_table("execution_schedules") as batch:
        batch.add_column(sa.Column("plan_month", sa.String(length=7), nullable=True))
        batch.add_column(sa.Column("expected_output", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("collaborator_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch.add_column(sa.Column("completion_criteria", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("progress_note", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("risk_dependency", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("actual_output", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("delay_reason", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
        batch.alter_column("start_date", existing_type=sa.Date(), nullable=True)
        batch.alter_column("due_date", existing_type=sa.Date(), nullable=True)
    op.create_index(
        "ix_execution_schedules_month_plan_lookup",
        "execution_schedules",
        ["subtask_id", "plan_type", "plan_month", "is_deleted"],
    )


def downgrade() -> None:
    op.drop_index("ix_execution_schedules_month_plan_lookup", table_name="execution_schedules")
    with op.batch_alter_table("execution_schedules") as batch:
        batch.alter_column("due_date", existing_type=sa.Date(), nullable=False)
        batch.alter_column("start_date", existing_type=sa.Date(), nullable=False)
        batch.drop_column("sort_order")
        batch.drop_column("delay_reason")
        batch.drop_column("actual_output")
        batch.drop_column("risk_dependency")
        batch.drop_column("progress_note")
        batch.drop_column("completion_criteria")
        batch.drop_column("collaborator_ids")
        batch.drop_column("expected_output")
        batch.drop_column("plan_month")
```

在迁移的 `upgrade()` 末尾，对 PostgreSQL 执行 `ALTER TABLE execution_schedules ALTER COLUMN ... DROP DEFAULT`，避免数据库层默认值成为新增业务记录的隐式行为；SQLite 保留批量迁移写入的既有值。不要回填旧记录的 `plan_month`，避免猜测历史周计划和旧月计划的真实归属月份。

- [ ] **Step 4: 更新 ORM，与迁移一一对应**

在 `ExecutionSchedule` 中新增如下字段，并将原日期改为可空：

```python
plan_month = Column(String(7), nullable=True, index=True)
start_date = Column(Date, nullable=True, index=True)
due_date = Column(Date, nullable=True, index=True)
expected_output = Column(Text, nullable=False, default="")
collaborator_ids = Column(JSON, nullable=False, default=list)
completion_criteria = Column(Text, nullable=False, default="")
progress_note = Column(Text, nullable=False, default="")
risk_dependency = Column(Text, nullable=False, default="")
actual_output = Column(Text, nullable=False, default="")
delay_reason = Column(Text, nullable=False, default="")
sort_order = Column(Integer, nullable=False, default=0)
```

保留 `reminder_policy`、`created_by`、`updated_by`、`is_deleted` 和提醒表，不把审计字段加入月计划表单模型。

- [ ] **Step 5: 应用迁移并确认 ORM 测试通过**

Run: `cd bowei_ai_dashboard; python -m alembic upgrade head; pytest tests/test_monthly_plans.py::test_month_plan_persists_optional_dates_and_business_fields -v`

Expected: PASS。

- [ ] **Step 6: 提交持久化改动**

```bash
git add bowei_ai_dashboard/app/models.py bowei_ai_dashboard/migrations/versions/a8b9c0d1e2f3_add_month_plan_fields.py bowei_ai_dashboard/tests/test_monthly_plans.py
git commit -m "feat: extend execution schedules for monthly plans"
```

### Task 2: 实现月计划 API、状态闭环和审计

**Files:**
- Create: `bowei_ai_dashboard/app/routers/monthly_plans.py`
- Modify: `bowei_ai_dashboard/app/schemas.py:669`
- Modify: `bowei_ai_dashboard/app/main.py:51,531`
- Test: `bowei_ai_dashboard/tests/test_monthly_plans.py`

- [ ] **Step 1: 写出失败的模型校验和排序投影测试**

追加以下测试：

```python
import pytest
from datetime import date

from app import schemas
from app.routers import monthly_plans


def test_month_plan_payload_requires_month_title_output_and_owner():
    with pytest.raises(ValueError, match="计划月份"):
        schemas.MonthPlanCreatePayload(
            plan_month="2026-13", title="", expected_output="", assignee_id=None
        )


def test_completed_month_plan_requires_actual_output():
    with pytest.raises(ValueError, match="实际产出"):
        schemas.MonthPlanCreatePayload(
            plan_month="2026-08", title="完成方案", expected_output="方案定稿",
            assignee_id=2, status="已完成", actual_output="",
        )


def test_month_plan_projection_uses_dynamic_overdue_and_required_order():
    rows = [
        models.ExecutionSchedule(id=1, subtask_id=1, plan_type="month", plan_month="2026-08", title="完成", expected_output="x", assignee="A", status="已完成"),
        models.ExecutionSchedule(id=2, subtask_id=1, plan_type="month", plan_month="2026-08", title="暂缓", expected_output="x", assignee="A", status="暂缓"),
        models.ExecutionSchedule(id=3, subtask_id=1, plan_type="month", plan_month="2026-08", title="逾期", expected_output="x", assignee="A", status="进行中", start_date=date(2026, 8, 1), due_date=date(2026, 8, 10)),
        models.ExecutionSchedule(id=4, subtask_id=1, plan_type="month", plan_month="2026-08", title="进行中", expected_output="x", assignee="A", status="进行中"),
        models.ExecutionSchedule(id=5, subtask_id=1, plan_type="month", plan_month="2026-08", title="未开始", expected_output="x", assignee="A", status="未开始"),
    ]
    result = monthly_plans.sort_month_plans(rows, today=date(2026, 8, 12))

    assert [row.id for row in result] == [3, 4, 2, 5, 1]
    assert monthly_plans.to_month_plan_dict(result[0], today=date(2026, 8, 12))["display_status"] == "已延期"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd bowei_ai_dashboard; pytest tests/test_monthly_plans.py -v`

Expected: FAIL，提示 `MonthPlanCreatePayload`、`sort_month_plans` 或 `monthly_plans` 路由尚不存在。

- [ ] **Step 3: 定义明确、可复用的 Pydantic 输入模型**

在 `schemas.py` 添加以下常量和模型。`MonthPlanUpdatePayload` 所有业务字段为可选，供 PATCH 使用；创建模型用 `Field` 和验证器强制四项必填业务字段。

```python
MONTH_PLAN_STATUSES = Literal["未开始", "进行中", "暂缓", "已完成", "已取消"]


class MonthPlanCreatePayload(BaseModel):
    plan_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    title: str = Field(min_length=1, max_length=200)
    expected_output: str = Field(min_length=1)
    assignee_id: int = Field(gt=0)
    collaborator_ids: list[int] = Field(default_factory=list)
    status: MONTH_PLAN_STATUSES = "未开始"
    start_date: date | None = None
    due_date: date | None = None
    completion_criteria: str = ""
    progress_note: str = ""
    risk_dependency: str = ""
    actual_output: str = ""
    delay_reason: str = ""
    sort_order: int = 0

    @model_validator(mode="after")
    def validate_month_plan(self):
        if bool(self.start_date) != bool(self.due_date):
            raise ValueError("开始日期和截止日期需同时填写")
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValueError("截止日期不得早于开始日期")
        if self.status == "已完成" and not self.actual_output.strip():
            raise ValueError("已完成的月计划必须填写实际产出")
        if self.assignee_id in self.collaborator_ids:
            raise ValueError("执行负责人不能同时作为协作人")
        if len(self.collaborator_ids) != len(set(self.collaborator_ids)):
            raise ValueError("协作人不能重复")
        return self
```

`MonthPlanUpdatePayload` 复用同一字段集合，但通过 `model_validator` 只校验本次同时传入的日期和“本次传入状态为已完成时必须同步传入实际产出”。路由在合并旧值后再次调用创建模型，确保 PATCH 不会绕过完整闭环校验。

- [ ] **Step 4: 实现月计划路由和项目成员校验**

在 `monthly_plans.py`：

1. 复用 `execution_schedules._parent`、`execution_schedules._require_write` 和 `require_project_business_writable`，避免复制权限规则。
2. 新增 `_project_member_ids(project_id, db)`，查询 `ProjectMember` 并返回去重的 `person_id` 集合。
3. 在每次创建和更新时确认执行负责人和协作人都属于该项目；否则返回 `422 "负责人或协作人不属于该项目"`。
4. 用 `is_overdue(row, today)` 和如下固定权重计算投影状态和排序：

```python
DISPLAY_STATUS_RANK = {"已延期": 0, "进行中": 1, "暂缓": 2, "未开始": 3, "已完成": 4, "已取消": 5}

def display_status(row, today: date) -> str:
    if row.status not in {"已完成", "已取消"} and row.due_date and row.due_date < today:
        return "已延期"
    return row.status

def month_plan_sort_key(row, today: date):
    return (
        DISPLAY_STATUS_RANK[display_status(row, today)],
        row.due_date is None,
        row.due_date or date.max,
        row.sort_order,
        row.created_at or datetime.min,
        row.id,
    )
```

5. 实现以下端点：

```text
GET    /api/subtasks/{subtask_id}/monthly-plans?month=YYYY-MM
POST   /api/subtasks/{subtask_id}/monthly-plans
PATCH  /api/monthly-plans/{plan_id}
DELETE /api/monthly-plans/{plan_id}
```

6. `GET` 只读取 `plan_type="month"`、`plan_month IS NOT NULL`、未软删除记录，按 `month_plan_sort_key` 返回；响应不包含 `created_by`、`updated_by`。
7. `POST` 强制写入 `plan_type="month"`，从 `Person` 快照写入 `assignee`，以 `crud.log(..., "monthly_plan_create", "execution_schedule", ...)` 记录审计。
8. `PATCH` 合并已存记录和输入后重新通过 `MonthPlanCreatePayload` 校验；若更新前为动态已延期，且请求变更 `due_date` 或 `plan_month`，必须在同一请求携带非空 `delay_reason`，否则返回 `422 "调整已延期计划时必须填写延期原因"`。成功后写 `updated_by` 和 `monthly_plan_update` 操作日志。
9. `DELETE` 软删除、更新 `updated_by` 并写 `monthly_plan_delete` 操作日志。

在 `main.py` 导入 `monthly_plans` 并执行 `app.include_router(monthly_plans.router)`。

- [ ] **Step 5: 添加端到端 API 行为测试**

在 `test_monthly_plans.py` 使用现有登录测试 fixture 创建项目成员、关键任务和人员，覆盖：

```python
def test_month_plan_api_rejects_non_project_assignee(client_as_owner, seeded_subtask):
    response = client_as_owner.post(
        f"/api/subtasks/{seeded_subtask.id}/monthly-plans",
        json={"plan_month": "2026-08", "title": "本月事项", "expected_output": "结果", "assignee_id": 999},
    )
    assert response.status_code == 422


def test_month_plan_api_returns_overdue_first(client_as_owner, seeded_subtask):
    # 创建同月的已完成、未开始、暂缓、进行中和历史截止日进行中记录。
    response = client_as_owner.get(f"/api/subtasks/{seeded_subtask.id}/monthly-plans?month=2026-08")
    assert response.status_code == 200
    assert [item["display_status"] for item in response.json()] == ["已延期", "进行中", "暂缓", "未开始", "已完成"]
```

额外断言：普通项目成员 POST 返回 403；关键任务负责人能 POST；归档项目 POST 返回 409/403（与 `require_project_business_writable` 的现有约定一致）；完成计划缺少 `actual_output` 返回 422；延期计划改期缺少 `delay_reason` 返回 422；成功的 POST/PATCH/DELETE 各新增一条 `OperationLog`，且日志的 `before_json` / `after_json` 包含业务字段。

- [ ] **Step 6: 运行后端回归测试**

Run: `cd bowei_ai_dashboard; pytest tests/test_monthly_plans.py tests/test_execution_schedules.py -v`

Expected: PASS，旧执行安排测试继续通过。

- [ ] **Step 7: 提交 API 改动**

```bash
git add bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/app/routers/monthly_plans.py bowei_ai_dashboard/app/main.py bowei_ai_dashboard/tests/test_monthly_plans.py
git commit -m "feat: add monthly plan APIs"
```

### Task 3: 建立前端 API 和可测试的月份、排序领域逻辑

**Files:**
- Create: `frontend/src/api/monthlyPlans.ts`
- Create: `frontend/src/domain/monthPlans.ts`
- Create: `frontend/src/domain/monthPlans.test.ts`

- [ ] **Step 1: 为月计划领域函数写失败单元测试**

在 `frontend/src/domain/monthPlans.test.ts` 写入：

```ts
import { describe, expect, it } from 'vitest'
import { monthPlanStatus, sortMonthPlans, monthTabs } from './monthPlans'
import type { MonthlyPlan } from '../api/monthlyPlans'

const plan = (id: number, status: MonthlyPlan['status'], due_date: string | null = null): MonthlyPlan => ({
  id, subtask_id: 1, plan_month: '2026-08', title: String(id), expected_output: '产出',
  assignee: '邹奇敏', assignee_id: 2, collaborator_ids: [], collaborators: [], status,
  start_date: due_date, due_date, completion_criteria: '', progress_note: '', risk_dependency: '',
  actual_output: '', delay_reason: '', sort_order: 0, is_overdue: false, display_status: status,
})

describe('month plans', () => {
  it('sorts overdue, in progress, paused, not started and completed in management order', () => {
    const overdue = { ...plan(1, '进行中', '2026-08-10'), is_overdue: true, display_status: '已延期' as const }
    expect(sortMonthPlans([plan(5, '已完成'), plan(4, '未开始'), plan(3, '暂缓'), plan(2, '进行中'), overdue]))
      .toMatchObject([{ id: 1 }, { id: 2 }, { id: 3 }, { id: 4 }, { id: 5 }])
  })

  it('uses the current month first and includes stored neighbouring months', () => {
    expect(monthTabs('2026-08', ['2026-06', '2026-10'])).toEqual(['2026-06', '2026-07', '2026-08', '2026-09', '2026-10'])
  })

  it('takes the server overdue projection as the visible status', () => {
    expect(monthPlanStatus({ ...plan(1, '进行中'), is_overdue: true, display_status: '已延期' })).toBe('已延期')
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend; npm run test:unit -- src/domain/monthPlans.test.ts`

Expected: FAIL，提示 `monthlyPlans.ts` 和 `monthPlans.ts` 尚不存在。

- [ ] **Step 3: 定义 HTTP 类型与客户端**

在 `frontend/src/api/monthlyPlans.ts` 定义：

```ts
export type MonthPlanStatus = '未开始' | '进行中' | '暂缓' | '已完成' | '已取消'
export type MonthPlanDisplayStatus = MonthPlanStatus | '已延期'

export type MonthlyPlan = {
  id: number; subtask_id: number; plan_month: string; title: string; expected_output: string
  assignee: string; assignee_id: number; collaborator_ids: number[]; collaborators: string[]
  status: MonthPlanStatus; display_status: MonthPlanDisplayStatus; is_overdue: boolean
  start_date: string | null; due_date: string | null; completion_criteria: string
  progress_note: string; risk_dependency: string; actual_output: string
  delay_reason: string; sort_order: number
}

export type MonthlyPlanPayload = Omit<MonthlyPlan, 'id' | 'subtask_id' | 'assignee' | 'collaborators' | 'display_status' | 'is_overdue'>
```

用 `apiGet`、`apiPost`、`apiPatch`、`apiDelete` 封装四个端点；`fetchMonthlyPlans(subtaskId, month?)` 仅在 `month` 有值时拼接 `?month=${encodeURIComponent(month)}`。

- [ ] **Step 4: 实现无副作用的显示与排序函数**

在 `monthPlans.ts` 导出以下规则：

```ts
const STATUS_RANK = { 已延期: 0, 进行中: 1, 暂缓: 2, 未开始: 3, 已完成: 4, 已取消: 5 } as const

export const currentMonthKey = (now = new Date()) =>
  `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`

export const monthPlanStatus = (plan: MonthlyPlan) => plan.display_status

export function sortMonthPlans(plans: MonthlyPlan[]) {
  return [...plans].sort((left, right) =>
    STATUS_RANK[monthPlanStatus(left)] - STATUS_RANK[monthPlanStatus(right)] ||
    Number(left.due_date == null) - Number(right.due_date == null) ||
    (left.due_date ?? '9999-12-31').localeCompare(right.due_date ?? '9999-12-31') ||
    left.sort_order - right.sort_order || left.id - right.id,
  )
}
```

`monthTabs(currentMonth, storedMonths)` 返回当前月前后各一个月、已存月份的去重升序集合；不生成无边界的全年标签。`formatMonthLabel('2026-08')` 返回 `2026 年 8 月`。

- [ ] **Step 5: 运行前端领域测试**

Run: `cd frontend; npm run test:unit -- src/domain/monthPlans.test.ts`

Expected: PASS。

- [ ] **Step 6: 提交前端领域层**

```bash
git add frontend/src/api/monthlyPlans.ts frontend/src/domain/monthPlans.ts frontend/src/domain/monthPlans.test.ts
git commit -m "feat: add monthly plan frontend domain"
```

### Task 4: 构建月计划主区和详情编辑抽屉

**Files:**
- Create: `frontend/src/components/task-management/MonthlyPlanDrawer.tsx`
- Create: `frontend/src/components/task-management/MonthlyPlanWorkspace.tsx`
- Modify: `frontend/tests/executionScheduleTimeline.test.mjs`

- [ ] **Step 1: 写出失败的结构测试**

将 `frontend/tests/executionScheduleTimeline.test.mjs` 改名内容为月计划工作台断言：

```js
test('monthly plan workspace defaults to the current month and exposes monthly-plan actions', () => {
  const source = read('src/components/task-management/MonthlyPlanWorkspace.tsx')
  assert.match(source, /currentMonthKey/)
  assert.match(source, /monthTabs/)
  assert.match(source, /sortMonthPlans/)
  assert.match(source, /新增月计划/)
  assert.match(source, /已延期.*进行中.*暂缓.*未开始.*已完成/s)
  assert.match(source, /MonthlyPlanDrawer/)
})

test('monthly plan drawer only presents business fields, never audit fields', () => {
  const source = read('src/components/task-management/MonthlyPlanDrawer.tsx')
  assert.match(source, /预期产出/)
  assert.match(source, /执行负责人/)
  assert.match(source, /实际产出/)
  assert.doesNotMatch(source, /created_by|updated_by|创建人|最后修改人/)
})
```

- [ ] **Step 2: 运行结构测试确认失败**

Run: `cd frontend; node --test tests/executionScheduleTimeline.test.mjs`

Expected: FAIL，提示 `MonthlyPlanWorkspace.tsx` 尚不存在。

- [ ] **Step 3: 实现月计划抽屉**

`MonthlyPlanDrawer.tsx` 接收 `{ plan, selectedMonth, defaultAssigneeId, members, canManage, onSave, onClose }`：

- 新建时默认 `plan_month=selectedMonth`、负责人为关键任务负责人；编辑时读入记录。
- 第一屏只显示并强制校验“计划月份、计划名称、预期产出、执行负责人、状态”。
- 以“补充信息”折叠区显示起止日期、协作人、完成标准、进展说明、风险与依赖、实际产出、延期原因、排序号。
- 当选择“已完成”且实际产出为空时，在提交前显示 `请填写实际产出`；当修改动态延期计划的日期或月份时，展示延期原因输入并阻止空提交。
- `canManage=false` 时只读显示，不渲染保存和删除按钮。
- 不渲染、接收或回传 `created_by`、`updated_by`、创建时间、更新时间等审计字段。

表单提交必须从 `FormData` 组装：

```ts
const payload: MonthlyPlanPayload = {
  plan_month: String(data.get('plan_month')),
  title: String(data.get('title')).trim(),
  expected_output: String(data.get('expected_output')).trim(),
  assignee_id: Number(data.get('assignee_id')),
  collaborator_ids: selectedCollaboratorIds,
  status: String(data.get('status')) as MonthPlanStatus,
  start_date: String(data.get('start_date') || '') || null,
  due_date: String(data.get('due_date') || '') || null,
  completion_criteria: String(data.get('completion_criteria') || '').trim(),
  progress_note: String(data.get('progress_note') || '').trim(),
  risk_dependency: String(data.get('risk_dependency') || '').trim(),
  actual_output: String(data.get('actual_output') || '').trim(),
  delay_reason: String(data.get('delay_reason') || '').trim(),
  sort_order: Number(data.get('sort_order') || 0),
}
```

- [ ] **Step 4: 实现月计划主区域**

`MonthlyPlanWorkspace.tsx` 接收 `{ subtaskId, defaultAssigneeId, members, canManage, onChanged }`。实现：

1. 首次加载调用 `fetchMonthlyPlans(subtaskId)`；`selectedMonth` 初始值为 `currentMonthKey()`，而不是最早有记录的月份。
2. 使用 `monthTabs(currentMonthKey(), plans.map(plan => plan.plan_month))` 渲染月份标签；当前月标签文案追加“（本月）”。
3. 对 `plans.filter(plan => plan.plan_month === selectedMonth)` 调用 `sortMonthPlans`。空结果渲染“本月暂无计划分支”和“新增月计划”按钮。
4. 每条列表项展示：状态色条、计划名称、预期产出、执行负责人、日期或“未设置日期”、进展说明/风险摘要、文字状态标签。色条映射固定为延期红、进行中蓝、暂缓橙、未开始灰、完成绿，并始终同时显示文字状态。
5. 点击行打开抽屉；创建、更新、删除成功后用接口返回值更新本地 `plans`，并调用 `onChanged()` 让父级刷新摘要。
6. 失败时通过现有 `toast.error` 显示 API 返回错误；保存时禁用重复提交。

不要继续渲染 `ExecutionScheduleTimeline`，也不要在月计划区提供周/月类型选择器。

- [ ] **Step 5: 运行前端结构与单元测试**

Run: `cd frontend; node --test tests/executionScheduleTimeline.test.mjs; npm run test:unit -- src/domain/monthPlans.test.ts`

Expected: PASS。

- [ ] **Step 6: 提交月计划界面组件**

```bash
git add frontend/src/components/task-management/MonthlyPlanDrawer.tsx frontend/src/components/task-management/MonthlyPlanWorkspace.tsx frontend/tests/executionScheduleTimeline.test.mjs
git commit -m "feat: add key task monthly plan workspace"
```

### Task 5: 整合关键任务执行工作台并保留过程记录

**Files:**
- Modify: `frontend/src/components/task-management/KeyTaskExecutionDetailView.tsx`
- Modify: `frontend/src/pages/TaskManagementPage.tsx:557-566,1045-1053`
- Modify: `frontend/tests/keyTaskExecutionDetailLayout.test.mjs`

- [ ] **Step 1: 写出失败的关键任务详情结构测试**

将 `keyTaskExecutionDetailLayout.test.mjs` 中最后一个测试替换为：

```js
test('key task detail is a monthly-plan workbench while retaining task context and process records', () => {
  const detail = read('src/components/task-management/KeyTaskExecutionDetailView.tsx')
  const page = read('src/pages/TaskManagementPage.tsx')
  assert.match(detail, /返回工作推进表/)
  assert.match(detail, /直接负责人/)
  assert.match(detail, /MonthlyPlanWorkspace/)
  assert.match(detail, /关键任务概览/)
  assert.match(detail, /工作汇报记录/)
  assert.doesNotMatch(detail, /ExecutionScheduleTimeline/)
  assert.match(page, /projectMembers=\{projectMembersByProject/)
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend; node --test tests/keyTaskExecutionDetailLayout.test.mjs`

Expected: FAIL，提示当前详情页仍引用 `ExecutionScheduleTimeline` 或未传入项目成员。

- [ ] **Step 3: 重组详情页面的稳定布局**

在 `KeyTaskExecutionDetailView.tsx`：

1. 移除 `ExecutionScheduleTimeline` 引入，改为 `MonthlyPlanWorkspace`。
2. 扩充 props：`projectMembers: ProjectMember[]`；由 `subTask.assignee_id` 或通过成员名匹配得到 `defaultAssigneeId`。
3. 顶部保留当前返回按钮，文案固定为“← 返回工作推进表”；任务摘要卡展示重点工作、关键任务名称、直接负责人、整体状态、计划周期、完成标准。
4. 桌面端使用 `xl:grid-cols-[minmax(0,1fr)_300px]`：左侧第一块是 `MonthlyPlanWorkspace`；原评价标准和工作汇报记录置于“过程记录”区域，保持可访问；右侧只保留“关键任务概览”、最新汇报时间、成果摘要。
5. 在右侧概览基于月计划数据或子组件刷新结果显示“本月计划数、需关注项、本月完成数、最新更新时间”。“需关注项”只计动态已延期状态；完成数仅计算 `已完成`。
6. 保留原 `AchievementList` 和完整工作汇报记录，不把其内容混入月计划行；没有记录时保留空状态。

- [ ] **Step 4: 在页面入口确保成员可用并传递**

在 `TaskManagementPage.tsx` 的 `focusSubTask` 内，先根据该关键任务的父重点工作解析项目，调用 `ensureProjectMembersLoaded(projectId)`，再加载详情。渲染 `KeyTaskExecutionDetailView` 时传入：

```tsx
projectMembers={projectMembersByProject[focusedProject?.id ?? 0] ?? []}
```

保留现有 `canManageSchedules` 权限计算作为新月计划 `canManage` 的值；不改变表格、执行进度视图或 `clearSelection()` 返回行为。

- [ ] **Step 5: 运行前端回归与构建**

Run: `cd frontend; node --test tests/executionScheduleTimeline.test.mjs tests/keyTaskExecutionDetailLayout.test.mjs; npm run test:unit; npm run build`

Expected: 所有 node:test、Vitest 测试和 TypeScript/Vite 生产构建均 PASS。

- [ ] **Step 6: 进行浏览器视觉验收**

使用本地开发服务进入一个包含关键任务的项目，检查：

1. 从工作推进表点击关键任务后，默认标签为当前自然月。
2. 同月五种状态的顺序为：已延期、进行中、暂缓、未开始、已完成。
3. 月份切换、空状态、新建、编辑、完成时实际产出校验、延期改期原因校验均可用。
4. 窄屏下主区和概览纵向堆叠，无横向裁切；返回后仍处于原工作推进表视图。
5. 普通成员界面没有保存/删除入口；具备权限者可编辑。

- [ ] **Step 7: 提交页面整合**

```bash
git add frontend/src/components/task-management/KeyTaskExecutionDetailView.tsx frontend/src/pages/TaskManagementPage.tsx frontend/tests/keyTaskExecutionDetailLayout.test.mjs
git commit -m "feat: redesign key task detail as monthly plan workbench"
```

### Task 6: 完整回归、迁移验证与发布说明

**Files:**
- Modify: `bowei_ai_dashboard/docs/DEPLOYMENT_SOP.md`
- Test: `bowei_ai_dashboard/tests/test_monthly_plans.py`
- Test: `bowei_ai_dashboard/tests/test_execution_schedules.py`

- [ ] **Step 1: 写入发布前检查项**

在 `DEPLOYMENT_SOP.md` 的数据库升级步骤后新增以下发布检查：

```markdown
### 关键任务月计划工作台

1. 执行 `python -m alembic upgrade head`，确认 `a8b9c0d1e2f3` 已应用。
2. 打开任一活动项目的关键任务详情，确认默认进入当前月的“月计划”。
3. 新建一个无日期月计划，并新建一个有截止日期的月计划；确认前者不显示延期、后者逾期时显示“已延期”。
4. 用项目负责人、关键任务负责人和普通成员分别检查创建/编辑权限。
5. 在操作日志确认月计划创建、更新和删除分别生成 `monthly_plan_create`、`monthly_plan_update`、`monthly_plan_delete` 记录。
```

- [ ] **Step 2: 运行完整验证**

Run:

```powershell
cd bowei_ai_dashboard
python -m alembic upgrade head
pytest tests/test_monthly_plans.py tests/test_execution_schedules.py -v
cd ..\frontend
node --test tests/executionScheduleTimeline.test.mjs tests/keyTaskExecutionDetailLayout.test.mjs
npm run test:unit
npm run build
```

Expected: Alembic 成功升级；pytest、node:test、Vitest、TypeScript/Vite 构建全部 PASS。

- [ ] **Step 3: 检查迁移链和工作区范围**

Run:

```powershell
cd bowei_ai_dashboard
python -m alembic heads
cd ..
git diff --check
git status --short
```

Expected: `a8b9c0d1e2f3 (head)` 为唯一迁移链头；无空白错误；仅包含本计划文件变更及用户原有未提交变更。

- [ ] **Step 4: 提交文档与最终验证结果**

```bash
git add bowei_ai_dashboard/docs/DEPLOYMENT_SOP.md
git commit -m "docs: add monthly plan rollout checks"
```
