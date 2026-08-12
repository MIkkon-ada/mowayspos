# 关键任务子任务执行页 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将关键任务点击后的唯一详情视角改造成确认效果图中的“关键任务执行页”，把月计划数据作为可选月份分组的子任务展示，并让执行过程与三个提交动作继续归属关键任务。

**Architecture:** 后端继续复用 `execution_schedules` 与现有 monthly-plans API，只放开 `plan_month=null` 并让查询、更新、删除包含未分月记录。前端保留 `monthlyPlans.ts` 作为兼容数据层，新建语义清晰的子任务工作区、详情抽屉、执行过程组件；`KeyTaskExecutionDetailView` 只负责组装页面和跳转到现有工作汇报页。

**Tech Stack:** FastAPI、Pydantic、SQLAlchemy、React 19、TypeScript、Tailwind CSS、Node test runner、Pytest、Vite。

---

## 文件职责

- `bowei_ai_dashboard/app/schemas.py`：允许子任务分组月份为空，并继续校验非空月份格式。
- `bowei_ai_dashboard/app/routers/monthly_plans.py`：让未分月记录参与列表、更新和删除。
- `bowei_ai_dashboard/tests/test_monthly_plans.py`：覆盖未分月创建、读取、更新和删除的后端行为。
- `frontend/src/api/monthlyPlans.ts`：将兼容数据层中的 `plan_month` 改为可空。
- `frontend/src/domain/monthPlans.ts`：提供安全的月份标签、分组和筛选工具。
- `frontend/src/domain/workReportEntry.ts`：集中生成复用现有工作汇报流程的深链。
- `frontend/src/components/task-management/KeyTaskSubtasksWorkspace.tsx`：渲染“子任务”工具栏、筛选和表格。
- `frontend/src/components/task-management/KeyTaskSubtaskDrawer.tsx`：渲染新增/编辑或只读子任务抽屉；只读态协作人不占整行。
- `frontend/src/components/task-management/KeyTaskExecutionTimeline.tsx`：统一渲染关键任务的工作汇报、成果、问题和会议纪要。
- `frontend/src/components/task-management/KeyTaskExecutionDetailView.tsx`：组装标题、四栏概览、子任务和执行过程。
- `frontend/src/pages/VoiceUpdatePage.tsx`、`frontend/src/features/voice-update/VoiceUpdateInputPanel.tsx`：接收提交入口意图并保留现有统一提取/提交逻辑。
- `frontend/tests/keyTaskSubtaskWorkspace.test.mjs`、`frontend/tests/keyTaskExecutionDetailLayout.test.mjs`、`frontend/tests/workReportEntry.test.mjs`：覆盖新布局、抽屉和深链。

### Task 1: 允许子任务不按月份分组

**Files:**
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Modify: `bowei_ai_dashboard/app/routers/monthly_plans.py`
- Test: `bowei_ai_dashboard/tests/test_monthly_plans.py`

- [ ] **Step 1: 写入未分月失败测试**

在 `test_monthly_plans.py` 增加：

```python
def test_month_plan_payload_allows_no_month_group():
    payload = schemas.MonthPlanCreatePayload(
        plan_month=None,
        title="不按月份推进权限梳理",
        expected_output="权限清单",
        assignee_id=2,
    )
    assert payload.plan_month is None


def test_month_plan_rows_include_ungrouped_records():
    from app.routers import monthly_plans
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        models.ExecutionSchedule(subtask_id=1, plan_type="month", plan_month=None, title="未分月", expected_output="x", assignee="A", status="未开始"),
        models.ExecutionSchedule(subtask_id=1, plan_type="month", plan_month="2026-08", title="八月", expected_output="x", assignee="A", status="未开始"),
    ])
    db.commit()
    assert {row.title for row in monthly_plans._month_plan_rows(1, db)} == {"未分月", "八月"}
```

- [ ] **Step 2: 运行测试并确认按预期失败**

Run: `python -m pytest bowei_ai_dashboard/tests/test_monthly_plans.py -q`

Expected: `MonthPlanCreatePayload` 拒绝 `None`，且 `_month_plan_rows` 未返回“未分月”。

- [ ] **Step 3: 最小化修改 schema 与查询约束**

将创建字段改为：

```python
plan_month: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
```

从 `_month_plan_rows` 查询中删除：

```python
models.ExecutionSchedule.plan_month.is_not(None),
```

并将更新、删除入口的存在性判断统一改为：

```python
if not row or row.is_deleted or row.plan_type != "month":
    raise HTTPException(404, "子任务不存在")
```

延期修改校验只在日期或月份发生真实变更时继续生效；`plan_month=None` 合法。

- [ ] **Step 4: 运行后端聚焦测试**

Run: `python -m pytest bowei_ai_dashboard/tests/test_monthly_plans.py -q`

Expected: 全部通过。

- [ ] **Step 5: 提交后端兼容改动**

```powershell
git add bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/app/routers/monthly_plans.py bowei_ai_dashboard/tests/test_monthly_plans.py
git commit -m "feat: allow ungrouped key task subtasks"
```

### Task 2: 建立可空月份与工作汇报深链契约

**Files:**
- Modify: `frontend/src/api/monthlyPlans.ts`
- Modify: `frontend/src/domain/monthPlans.ts`
- Create: `frontend/src/domain/workReportEntry.ts`
- Create: `frontend/tests/workReportEntry.test.mjs`
- Modify: `frontend/tests/executionScheduleTimeline.test.mjs`

- [ ] **Step 1: 写入前端数据契约失败测试**

新建 `workReportEntry.test.mjs`：

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const api = readFileSync(new URL('../src/api/monthlyPlans.ts', import.meta.url), 'utf8')
const entry = readFileSync(new URL('../src/domain/workReportEntry.ts', import.meta.url), 'utf8')

test('subtask grouping month is optional', () => {
  assert.match(api, /plan_month:\s*string\s*\|\s*null/)
})

test('work report entry keeps project and key task ownership', () => {
  assert.match(entry, /projectId/)
  assert.match(entry, /subtaskId/)
  assert.match(entry, /entryIntent/)
  assert.doesNotMatch(entry, /monthlyPlanId|planId/)
})
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `node --test frontend/tests/workReportEntry.test.mjs`

Expected: `plan_month` 仍为必填字符串且 `workReportEntry.ts` 不存在。

- [ ] **Step 3: 修改类型和月份工具**

在 `MonthlyPlan` 中使用：

```ts
plan_month: string | null
```

让 `monthTabs` 接受 `(string | null)[]` 并只处理非空月份；让标签函数安全处理空值：

```ts
export const formatMonthLabel = (month: string | null) => {
  if (!month) return '未分月'
  const [year, value] = month.split('-')
  return `${year} 年 ${Number(value)} 月`
}
```

- [ ] **Step 4: 新建工作汇报深链工具**

```ts
export type WorkReportEntryIntent = 'report' | 'issue' | 'achievement'

export function buildWorkReportEntryUrl(projectId: number, subtaskId: number, entryIntent: WorkReportEntryIntent) {
  const params = new URLSearchParams({
    projectId: String(projectId),
    subtaskId: String(subtaskId),
    entryIntent,
  })
  return `/work/submit?${params.toString()}`
}
```

- [ ] **Step 5: 运行契约测试**

Run: `node --test frontend/tests/workReportEntry.test.mjs frontend/tests/executionScheduleTimeline.test.mjs`

Expected: 全部通过。

- [ ] **Step 6: 提交数据契约改动**

```powershell
git add frontend/src/api/monthlyPlans.ts frontend/src/domain/monthPlans.ts frontend/src/domain/workReportEntry.ts frontend/tests/workReportEntry.test.mjs frontend/tests/executionScheduleTimeline.test.mjs
git commit -m "refactor: expose monthly plan data as optional subtask groups"
```

### Task 3: 重建子任务工作区和详情抽屉

**Files:**
- Create: `frontend/src/components/task-management/KeyTaskSubtasksWorkspace.tsx`
- Create: `frontend/src/components/task-management/KeyTaskSubtaskDrawer.tsx`
- Remove after replacement: `frontend/src/components/task-management/MonthlyPlanWorkspace.tsx`
- Remove after replacement: `frontend/src/components/task-management/MonthlyPlanDrawer.tsx`
- Create: `frontend/tests/keyTaskSubtaskWorkspace.test.mjs`

- [ ] **Step 1: 写入工作区结构失败测试**

测试必须断言：

```js
assert.match(workspace, />子任务</)
assert.match(workspace, /全部子任务/)
assert.match(workspace, /新增子任务/)
assert.match(workspace, /未分月/)
assert.match(drawer, /子任务详情/)
assert.match(drawer, /负责人[\s\S]*协作人/)
assert.doesNotMatch(drawer, /<Field label="协作人">[\s\S]*select/)
```

- [ ] **Step 2: 运行测试并确认组件缺失而失败**

Run: `node --test frontend/tests/keyTaskSubtaskWorkspace.test.mjs`

Expected: 新组件文件不存在。

- [ ] **Step 3: 实现子任务工作区**

工作区维护 `view: 'all' | month-string`，列表规则为：

```ts
const rows = sortMonthPlans(
  selectedGroup === 'all'
    ? plans
    : plans.filter((plan) => plan.plan_month === selectedGroup),
)
```

渲染效果图字段：状态、子任务事项、负责人、分组、时间安排、进度、操作。分组使用 `formatMonthLabel(plan.plan_month)`；创建时默认 `plan_month=null`，用户可选月份。

- [ ] **Step 4: 实现详情与编辑抽屉**

只读详情顶部使用两列紧凑元数据：

```tsx
<dl className="grid grid-cols-2 gap-x-6 gap-y-3">
  <div><dt>负责人</dt><dd>{plan.assignee}</dd></div>
  <div><dt>协作人</dt><dd>{plan.collaborators.join('、') || '无'}</dd></div>
</dl>
```

只读态不得渲染协作人选择框；点击编辑后才渲染多选控件。表单的月份选择包含：

```tsx
<option value="">不按月份</option>
```

保存时把空字符串转换为 `null`。

- [ ] **Step 5: 运行组件测试并修正到通过**

Run: `node --test frontend/tests/keyTaskSubtaskWorkspace.test.mjs`

Expected: 全部通过。

- [ ] **Step 6: 提交子任务组件**

```powershell
git add frontend/src/components/task-management/KeyTaskSubtasksWorkspace.tsx frontend/src/components/task-management/KeyTaskSubtaskDrawer.tsx frontend/tests/keyTaskSubtaskWorkspace.test.mjs
git commit -m "feat: add key task subtask workspace"
```

### Task 4: 建立关键任务执行过程时间线

**Files:**
- Create: `frontend/src/components/task-management/KeyTaskExecutionTimeline.tsx`
- Modify: `frontend/tests/keyTaskExecutionDetailLayout.test.mjs`

- [ ] **Step 1: 写入执行过程筛选失败测试**

断言组件同时支持：

```js
for (const label of ['执行过程', '全部', '工作汇报', '成果', '问题', '会议纪要']) {
  assert.match(timeline, new RegExp(label))
}
assert.match(timeline, /related_achievements/)
assert.match(timeline, /related_issues/)
assert.match(timeline, /work_reports/)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `node --test frontend/tests/keyTaskExecutionDetailLayout.test.mjs`

Expected: `KeyTaskExecutionTimeline.tsx` 缺失。

- [ ] **Step 3: 实现统一事件投影和筛选**

创建统一事件类型：

```ts
type ExecutionEvent = {
  id: string
  kind: 'report' | 'achievement' | 'issue' | 'meeting'
  title: string
  summary: string
  actor: string
  createdAt: string | null
}
```

从 `work_reports`、`related_achievements`、`related_issues` 投影、合并并按时间倒序；没有会议纪要关联数据时，会议纪要筛选显示空状态，不伪造记录。

- [ ] **Step 4: 运行测试**

Run: `node --test frontend/tests/keyTaskExecutionDetailLayout.test.mjs`

Expected: 执行过程结构测试通过。

- [ ] **Step 5: 提交执行过程组件**

```powershell
git add frontend/src/components/task-management/KeyTaskExecutionTimeline.tsx frontend/tests/keyTaskExecutionDetailLayout.test.mjs
git commit -m "feat: add key task execution timeline"
```

### Task 5: 按效果图组装关键任务执行页

**Files:**
- Modify: `frontend/src/components/task-management/KeyTaskExecutionDetailView.tsx`
- Modify: `frontend/src/pages/TaskManagementPage.tsx`
- Modify: `frontend/tests/keyTaskExecutionDetailLayout.test.mjs`
- Modify: `frontend/tests/workProgressExcelView.test.mjs`

- [ ] **Step 1: 写入页面语义和布局失败测试**

断言：

```js
for (const label of ['负责人', '协作人', '开始时间', '状态', '子任务', '执行过程']) {
  assert.match(detail, new RegExp(label))
}
assert.doesNotMatch(detail, /整体状态|过程记录|月计划工作台/)
assert.match(detail, /KeyTaskSubtasksWorkspace/)
assert.match(detail, /KeyTaskExecutionTimeline/)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `node --test frontend/tests/keyTaskExecutionDetailLayout.test.mjs frontend/tests/workProgressExcelView.test.mjs`

Expected: 旧布局用词和旧组件导致失败。

- [ ] **Step 3: 重写页面组装**

`KeyTaskExecutionDetailView` 使用 `useNavigate()`，并生成三种现有工作汇报入口：

```ts
const openWorkReport = (intent: WorkReportEntryIntent) => {
  if (!project?.id) return
  navigate(buildWorkReportEntryUrl(project.id, subTask.id, intent))
}
```

页面只组合：标题区、四栏概览、`KeyTaskSubtasksWorkspace`、`KeyTaskExecutionTimeline`。四栏字段按效果图固定为负责人、协作人、开始时间、状态。

- [ ] **Step 4: 清除替换后的旧月计划 UI 组件**

确认没有 import 后删除：

```text
frontend/src/components/task-management/MonthlyPlanWorkspace.tsx
frontend/src/components/task-management/MonthlyPlanDrawer.tsx
```

API 和数据库兼容命名暂不重命名，避免无意义迁移。

- [ ] **Step 5: 运行页面聚焦测试**

Run: `node --test frontend/tests/keyTaskExecutionDetailLayout.test.mjs frontend/tests/workProgressExcelView.test.mjs frontend/tests/keyTaskSubtaskWorkspace.test.mjs`

Expected: 全部通过。

- [ ] **Step 6: 提交页面改造**

```powershell
git add frontend/src/components/task-management/KeyTaskExecutionDetailView.tsx frontend/src/components/task-management/KeyTaskExecutionTimeline.tsx frontend/src/components/task-management/KeyTaskSubtasksWorkspace.tsx frontend/src/components/task-management/KeyTaskSubtaskDrawer.tsx frontend/src/pages/TaskManagementPage.tsx frontend/tests/keyTaskExecutionDetailLayout.test.mjs frontend/tests/workProgressExcelView.test.mjs
git add -u frontend/src/components/task-management/MonthlyPlanWorkspace.tsx frontend/src/components/task-management/MonthlyPlanDrawer.tsx
git commit -m "feat: redesign key task execution page"
```

### Task 6: 让三个动作进入现有工作汇报三条路径

**Files:**
- Modify: `frontend/src/pages/VoiceUpdatePage.tsx`
- Modify: `frontend/src/features/voice-update/VoiceUpdateInputPanel.tsx`
- Modify: `frontend/tests/workReportFlowPage.test.mjs`
- Modify: `frontend/tests/workReportEntry.test.mjs`

- [ ] **Step 1: 写入入口意图失败测试**

断言工作汇报页读取：

```js
assert.match(page, /searchParams\.get\('entryIntent'\)/)
assert.match(page, /entryIntent=\{entryIntent\}/)
assert.match(panel, /entryIntent/)
assert.match(panel, /问题与风险/)
assert.match(panel, /取得的成果/)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `node --test frontend/tests/workReportEntry.test.mjs frontend/tests/workReportFlowPage.test.mjs`

Expected: 页面尚未读取 `entryIntent`。

- [ ] **Step 3: 接入意图但复用同一提交逻辑**

`VoiceUpdatePage` 解析合法意图：

```ts
const entryIntent = ['report', 'issue', 'achievement'].includes(searchParams.get('entryIntent') || '')
  ? searchParams.get('entryIntent') as WorkReportEntryIntent
  : 'report'
```

传入输入面板；面板仅改变提示重点，不改变现有 AI 提取和最终提交接口：

```ts
const promptByIntent = {
  report: '请输入本次完成、下一步计划、遇到的问题和形成的成果…',
  issue: '请描述当前问题、影响、已尝试措施和需要的支持…',
  achievement: '请描述形成的成果、版本、用途和相关说明…',
}
```

- [ ] **Step 4: 运行工作汇报回归测试**

Run: `node --test frontend/tests/workReportEntry.test.mjs frontend/tests/workReportFlowPage.test.mjs`

Expected: 全部通过；三个入口仍使用同一个提交页面和接口。

- [ ] **Step 5: 提交工作汇报入口改动**

```powershell
git add frontend/src/pages/VoiceUpdatePage.tsx frontend/src/features/voice-update/VoiceUpdateInputPanel.tsx frontend/src/domain/workReportEntry.ts frontend/tests/workReportEntry.test.mjs frontend/tests/workReportFlowPage.test.mjs
git commit -m "feat: add focused key task work report entries"
```

### Task 7: 全量验证与真实页面视觉验收

**Files:**
- Modify only if verification finds defects in files already listed above.

- [ ] **Step 1: 运行后端测试**

Run: `python -m pytest bowei_ai_dashboard/tests/test_monthly_plans.py bowei_ai_dashboard/tests/test_execution_schedule_schema_reconcile.py -q`

Expected: 0 failures。

- [ ] **Step 2: 运行前端聚焦测试**

Run: `node --test frontend/tests/keyTaskSubtaskWorkspace.test.mjs frontend/tests/keyTaskExecutionDetailLayout.test.mjs frontend/tests/workProgressExcelView.test.mjs frontend/tests/workReportEntry.test.mjs frontend/tests/workReportFlowPage.test.mjs`

Expected: 0 failures。

- [ ] **Step 3: 运行生产构建**

Run: `npm run build`

Working directory: `frontend`

Expected: Vite build exit code 0。

- [ ] **Step 4: 浏览器验证桌面布局**

打开 `http://127.0.0.1:6001/work/tasks?projectId=1`，从工作推进表点击关键任务，验证：

- 标题和四栏概览与效果图一致；
- “子任务”和“执行过程”是两个主模块；
- “全部子任务”包含按月和未分月记录；
- 子任务详情中负责人和协作人并排，无整行协作人选择框；
- 三个动作跳转到 `/work/submit` 并带 `projectId`、`subtaskId` 和正确 `entryIntent`。

- [ ] **Step 5: 浏览器验证窄屏布局**

将视口缩至约 390px 宽，验证概览卡片换行、表格可横向滚动、抽屉占满可用宽度且按钮不溢出。

- [ ] **Step 6: 检查差异范围**

Run: `git status --short` and `git diff --check`

Expected: 无空白错误；与本任务无关的 AI 配置改动仍保持原样且未被纳入提交。

