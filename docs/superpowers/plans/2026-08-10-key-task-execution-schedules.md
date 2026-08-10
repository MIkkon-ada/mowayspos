# 关键任务周/月执行安排与提醒 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为关键任务创建带起止日期的周计划/月计划，默认用时间轴展示，并在开始日、截止前一天和逾期期间通过站内通知和企业微信提醒。

**Architecture:** 保持“项目 → 重点工作 → 关键任务”三级结构，新增独立的 `execution_schedules` 表，归属 `subtasks`。新 router 实施 CRUD 与既有权限/归档保护；每日扫描函数利用数据库唯一约束实现提醒幂等。关键任务详情加载安排，前端渲染可筛选的时间轴与编辑抽屉。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、Pydantic v2、React、TypeScript、Tailwind CSS、pytest、Node test、企业微信 HTTP API。

---

## File structure

- Create: `bowei_ai_dashboard/migrations/versions/b8d1e4c6a739_add_execution_schedules.py` — 新表和提醒发送记录。
- Modify: `bowei_ai_dashboard/app/models.py`、`app/schemas.py`、`app/main.py`、`app/routers/subtasks.py`、`app/services/wecom.py`。
- Create: `app/routers/execution_schedules.py`、`app/services/execution_schedule_reminders.py`。
- Create: `tests/test_execution_schedules.py`、`tests/test_execution_schedule_reminders.py`。
- Create: `frontend/src/api/executionSchedules.ts`、`frontend/src/components/task-management/ExecutionScheduleTimeline.tsx`、`frontend/tests/executionScheduleTimeline.test.mjs`。
- Modify: `frontend/src/api/subtasks.ts`、`frontend/src/components/task-management/KeyTaskExecutionDetailView.tsx`、`frontend/src/pages/TaskManagementPage.tsx`、`frontend/tests/keyTaskExecutionDetailLayout.test.mjs`、`bowei_ai_dashboard/docs/DEPLOYMENT_SOP.md`。

### Task 1: 持久化模型与迁移

**Files:**
- Create: `bowei_ai_dashboard/migrations/versions/b8d1e4c6a739_add_execution_schedules.py`
- Modify: `bowei_ai_dashboard/app/models.py`
- Test: `bowei_ai_dashboard/tests/test_execution_schedules.py`

- [ ] **Step 1: 写失败测试**

```python
def test_execution_schedule_reminder_is_unique(db):
    schedule = models.ExecutionSchedule(
        subtask_id=1, plan_type="week", title="访谈业务部门",
        start_date=date(2026, 8, 12), due_date=date(2026, 8, 16),
        assignee_id=2, assignee="李娜", created_by="pm",
    )
    db.add(schedule); db.commit()
    db.add_all([
        models.ExecutionScheduleReminder(schedule_id=schedule.id, reminder_kind="start", due_on=date(2026, 8, 12), recipient_id=2),
        models.ExecutionScheduleReminder(schedule_id=schedule.id, reminder_kind="start", due_on=date(2026, 8, 12), recipient_id=2),
    ])
    with pytest.raises(IntegrityError): db.commit()
```

- [ ] **Step 2: 确认测试失败**

Run: `cd bowei_ai_dashboard; pytest tests/test_execution_schedules.py::test_execution_schedule_reminder_is_unique -v`  
Expected: FAIL，模型尚不存在。

- [ ] **Step 3: 实现 ORM 与迁移**

在 `models.py` 的 `SubTask` 后定义 `ExecutionSchedule`（`subtask_id`、`plan_type`、`title`、`start_date`、`due_date`、`assignee_id`、`assignee`、`status`、`reminder_policy: JSON`、`created_by`、`updated_by`、`is_deleted`）和 `ExecutionScheduleReminder`（`schedule_id`、`reminder_kind`、`due_on`、`recipient_id`、`notification_id`、`wecom_error`）。为提醒表定义：
```python
__table_args__ = (
    UniqueConstraint("schedule_id", "reminder_kind", "due_on", "recipient_id", name="uq_execution_schedule_reminder"),
)
```
Alembic migration 使用 `revision = "b8d1e4c6a739"`、`down_revision = "d2e3f4a5b6c7"`，接在当前唯一主链 head 后，并用 `op.create_table` 创建两表和全部外键/索引，`downgrade` 反向删除。不要修改 `subtasks` 的既有字段。

- [ ] **Step 4: 验证并提交**

Run: `cd bowei_ai_dashboard; alembic upgrade head; pytest tests/test_execution_schedules.py::test_execution_schedule_reminder_is_unique -v`  
Expected: PASS。

```bash
git add bowei_ai_dashboard/app/models.py bowei_ai_dashboard/migrations/versions/b8d1e4c6a739_add_execution_schedules.py bowei_ai_dashboard/tests/test_execution_schedules.py
git commit -m "feat: add execution schedule persistence"
```

### Task 2: Schema、CRUD 和权限

**Files:**
- Modify: `bowei_ai_dashboard/app/schemas.py`、`app/main.py`
- Create: `bowei_ai_dashboard/app/routers/execution_schedules.py`
- Test: `bowei_ai_dashboard/tests/test_execution_schedules.py`

- [ ] **Step 1: 写失败测试**

```python
def test_create_schedule_rejects_invalid_dates(client_as_member, subtask):
    r = client_as_member.post(f"/api/subtasks/{subtask.id}/execution-schedules", json={
        "plan_type": "week", "title": "访谈", "start_date": "2026-08-16",
        "due_date": "2026-08-12", "assignee_id": 2,
    })
    assert r.status_code == 422

def test_unrelated_member_cannot_create_schedule(client_as_other_member, subtask):
    assert client_as_other_member.post(f"/api/subtasks/{subtask.id}/execution-schedules", json=VALID_SCHEDULE).status_code == 403
```

- [ ] **Step 2: 确认失败**

Run: `cd bowei_ai_dashboard; pytest tests/test_execution_schedules.py -v`  
Expected: FAIL，路由不存在。

- [ ] **Step 3: 定义模型和 CRUD**

新增：
```python
class ExecutionSchedulePayload(BaseModel):
    plan_type: Literal["week", "month"]
    title: str = Field(..., min_length=1, max_length=200)
    start_date: date
    due_date: date
    assignee_id: int | None = None
    assignee: str = Field(default="", max_length=50)
    status: Literal["待开始", "进行中", "已完成", "已取消"] = "待开始"
    reminder_policy: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_range(self):
        if self.due_date < self.start_date:
            raise ValueError("截止日期不得早于开始日期")
        return self
```
实现 GET/POST `/api/subtasks/{subtask_id}/execution-schedules` 和 PATCH/DELETE `/api/execution-schedules/{id}`。写操作加载父 `SubTask/Task`，调用 `require_project_business_writable`，允许 tech admin、项目 owner/coordinator 或关键任务负责人；普通成员返回 403。负责人必须属于项目，否则 422。删除软删除，创建/更新写入操作者，所有写操作 `crud.log`。列表/详情额外返回 `is_overdue`、`is_due_soon`。在 `main.py` 注册 router。

- [ ] **Step 4: 验证并提交**

Run: `cd bowei_ai_dashboard; pytest tests/test_execution_schedules.py -v`  
Expected: PASS，包含 owner、coordinator、负责人、普通成员与归档项目。

```bash
git add bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/app/routers/execution_schedules.py bowei_ai_dashboard/app/main.py bowei_ai_dashboard/tests/test_execution_schedules.py
git commit -m "feat: manage key task execution schedules"
```

### Task 3: 提醒服务和企业微信降级

**Files:**
- Create: `bowei_ai_dashboard/app/services/execution_schedule_reminders.py`
- Modify: `bowei_ai_dashboard/app/services/wecom.py`、`app/routers/subtasks.py`
- Test: `bowei_ai_dashboard/tests/test_execution_schedule_reminders.py`

- [ ] **Step 1: 写失败测试**

```python
def test_scan_generates_start_due_soon_and_overdue_once(db, monkeypatch):
    monkeypatch.setattr(reminders, "send_wecom_notice", lambda **_: None)
    reminders.scan_execution_schedule_reminders(db, today=date(2026, 8, 12))
    assert notification_types(db) == {"execution_schedule_start", "execution_schedule_due_soon", "execution_schedule_overdue"}
    before = db.query(models.ExecutionScheduleReminder).count()
    reminders.scan_execution_schedule_reminders(db, today=date(2026, 8, 12))
    assert db.query(models.ExecutionScheduleReminder).count() == before

def test_wecom_failure_keeps_in_app_notification(db, monkeypatch):
    monkeypatch.setattr(reminders, "send_wecom_notice", side_effect=WecomError("offline"))
    reminders.scan_execution_schedule_reminders(db, today=date(2026, 8, 12))
    assert db.query(models.Notification).count() == 1
    assert db.query(models.ExecutionScheduleReminder).one().wecom_error == "offline"
```

- [ ] **Step 2: 确认失败**

Run: `cd bowei_ai_dashboard; pytest tests/test_execution_schedule_reminders.py -v`  
Expected: FAIL，服务不存在。

- [ ] **Step 3: 实现扫描**

以 `ZoneInfo("Asia/Shanghai")` 计算日期。对有效、未删除、活跃项目内的安排：开始日生成 `start`，截止前一天生成 `due_soon`，截止日已过且状态不是已完成/已取消则生成 `overdue`。开始日接收人仅安排负责人；其余两类为安排负责人、关键任务负责人和项目 owner 的去重集合。先用嵌套事务插入唯一提醒记录；冲突则跳过，成功后用 `notify.send` 写入对应 type 和 `/project/{project_id}/tasks?subtaskId={subtask_id}&scheduleId={schedule_id}` 深链。企业微信失败只回填 `wecom_error`，不回滚站内通知。

在 `wecom.py` 加 `send_text_message(userids, content)`：过滤空 userid，以 access token 调用 `/message/send`，POST payload：
```python
{"touser": "|".join(userids), "msgtype": "text", "agentid": int(s.wecom_agent_id), "text": {"content": content}}
```
非零 errcode 抛 `WecomError`。在关键任务 detail 响应中按 `start_date, due_date, id` 附带未删除安排。

- [ ] **Step 4: 验证并提交**

Run: `cd bowei_ai_dashboard; pytest tests/test_execution_schedule_reminders.py tests/test_execution_schedules.py -v`  
Expected: PASS。

```bash
git add bowei_ai_dashboard/app/services/execution_schedule_reminders.py bowei_ai_dashboard/app/services/wecom.py bowei_ai_dashboard/app/routers/subtasks.py bowei_ai_dashboard/tests/test_execution_schedule_reminders.py
git commit -m "feat: remind execution schedule owners"
```

### Task 4: 每日调度与部署

**Files:**
- Modify: `bowei_ai_dashboard/app/main.py`、`bowei_ai_dashboard/docs/DEPLOYMENT_SOP.md`
- Test: `bowei_ai_dashboard/tests/test_execution_schedule_reminders.py`

- [ ] **Step 1: 写失败测试**

```python
def test_reminder_runner_starts_once(monkeypatch):
    monkeypatch.setattr(main, "run_execution_schedule_reminder_scan", lambda: None)
    main.start_execution_schedule_reminder_runner()
    assert main._execution_schedule_reminder_task is not None
```

- [ ] **Step 2: 确认失败**

Run: `cd bowei_ai_dashboard; pytest tests/test_execution_schedule_reminders.py::test_reminder_runner_starts_once -v`  
Expected: FAIL，runner 不存在。

- [ ] **Step 3: 接入 runner**

在 lifespan 启动一个 `asyncio.create_task` 循环：启动后执行一次 `asyncio.to_thread(run_execution_schedule_reminder_scan)`，随后睡眠到下一个中国时区 09:00；在 lifespan 的 `finally` cancel 并 await task。扫描异常写 logger 且不能终止循环。SOP 明确生产只运行一个 runner 副本；多副本时仅专用 worker 启用 runner，唯一索引仍防御重复。要求企业微信环境变量与 `people.wecom_userid`，缺 userid 时只发站内通知。

- [ ] **Step 4: 验证并提交**

Run: `cd bowei_ai_dashboard; pytest tests/test_execution_schedule_reminders.py -v`  
Expected: PASS。

```bash
git add bowei_ai_dashboard/app/main.py bowei_ai_dashboard/docs/DEPLOYMENT_SOP.md bowei_ai_dashboard/tests/test_execution_schedule_reminders.py
git commit -m "feat: schedule daily execution reminders"
```

### Task 5: 前端 API、时间轴与抽屉

**Files:**
- Create: `frontend/src/api/executionSchedules.ts`、`frontend/src/components/task-management/ExecutionScheduleTimeline.tsx`
- Modify: `frontend/src/api/subtasks.ts`
- Test: `frontend/tests/executionScheduleTimeline.test.mjs`

- [ ] **Step 1: 写失败测试**

```javascript
test('timeline exposes filters, labels, colors, and create action', () => {
  const source = read('src/components/task-management/ExecutionScheduleTimeline.tsx')
  assert.match(source, /全部.*待开始.*进行中.*已逾期.*已完成/s)
  assert.match(source, /aria-label=.*状态/)
  assert.match(source, /新建执行安排/)
  assert.match(source, /week.*month/s)
})
```

- [ ] **Step 2: 确认失败**

Run: `cd frontend; node --test tests/executionScheduleTimeline.test.mjs`  
Expected: FAIL，组件不存在。

- [ ] **Step 3: 实现 API 和组件**

客户端导出 `ExecutionSchedule`、`ExecutionSchedulePayload` 和 fetch/create/update/delete，沿用 `apiGet/apiPost/apiPatch/apiDelete`。时间轴按开始/截止日排序、显示周/月标签、事项、日期、负责人。状态优先级为 `is_overdue → 已逾期`、`is_due_soon → 即将到期`、否则持久 status。固定语义化映射：待开始灰蓝、进行中蓝、即将到期橙、已逾期红、已完成绿；每个节点都有文字、图标和 `aria-label`。提供“全部/待开始/进行中/已逾期/已完成”筛选。抽屉用 `input type="date"`、周/月选择、负责人选择；提交前检查日期范围，成功后调用 `onChanged`。

- [ ] **Step 4: 验证并提交**

Run: `cd frontend; node --test tests/executionScheduleTimeline.test.mjs; npx tsc --noEmit`  
Expected: PASS。

```bash
git add frontend/src/api/executionSchedules.ts frontend/src/api/subtasks.ts frontend/src/components/task-management/ExecutionScheduleTimeline.tsx frontend/tests/executionScheduleTimeline.test.mjs
git commit -m "feat: add execution schedule timeline"
```

### Task 6: 关键任务详情集成与回归

**Files:**
- Modify: `frontend/src/components/task-management/KeyTaskExecutionDetailView.tsx`、`frontend/src/pages/TaskManagementPage.tsx`
- Modify: `frontend/tests/keyTaskExecutionDetailLayout.test.mjs`

- [ ] **Step 1: 写失败测试**

```javascript
test('key task detail embeds execution schedule timeline', () => {
  const detail = read('src/components/task-management/KeyTaskExecutionDetailView.tsx')
  assert.match(detail, /ExecutionScheduleTimeline/)
  assert.match(detail, /执行安排/)
  assert.match(detail, /工作汇报记录/)
})
```

- [ ] **Step 2: 确认失败**

Run: `cd frontend; node --test tests/keyTaskExecutionDetailLayout.test.mjs`  
Expected: FAIL，详情页未集成时间轴。

- [ ] **Step 3: 实现集成**

给详情视图传入 `canManageSchedules` 和 `onSchedulesChanged`，在工作汇报前渲染：
```tsx
<ExecutionScheduleTimeline
  subtaskId={subTask.id}
  schedules={subTask.execution_schedules ?? []}
  canManage={canManageSchedules}
  onChanged={onSchedulesChanged}
/>
```
页面回调必须重新 `fetchSubtaskDetail(selectedSubTask.id)` 再写入 state，不能手工拼接，确保后端派生的逾期字段更新。

- [ ] **Step 4: 执行完整验证**

Run: `cd bowei_ai_dashboard; alembic upgrade head; pytest tests/test_execution_schedules.py tests/test_execution_schedule_reminders.py tests/test_subtask_log_actions.py -v`  
Expected: PASS。

Run: `cd frontend; node --test tests/keyTaskExecutionDetailLayout.test.mjs tests/executionScheduleTimeline.test.mjs; npm run build`  
Expected: PASS，Vite 构建成功。

- [ ] **Step 5: 手工验收并提交**

在 active 项目中创建一条周计划和一条月计划，验证五种视觉状态、筛选、权限拒绝、通知深链、企业微信失败降级和归档停止。将结果追加到部署 SOP。

```bash
git add frontend/src/components/task-management/KeyTaskExecutionDetailView.tsx frontend/src/pages/TaskManagementPage.tsx frontend/tests/keyTaskExecutionDetailLayout.test.mjs bowei_ai_dashboard/docs/DEPLOYMENT_SOP.md
git commit -m "feat: show execution plans in key task detail"
```

## Plan self-review

- 覆盖性：Task 1–2 实现数据、权限、审计和归档保护；Task 3–4 实现三类提醒、幂等、企业微信降级和可靠调度；Task 5–6 实现时间轴、状态颜色/文字/图标、筛选、编辑与验证。
- 一致性：执行安排统一使用 `ExecutionSchedule`、`ExecutionSchedulePayload`，持久状态仅为待开始、进行中、已完成、已取消；逾期和即将到期均为后端派生。
- 范围：不增加任务主层级、不改既有 `subtasks` 字段、不包含 AI 自动拆分、外部日历或复杂循环规则。
