# N4-P1-D 关键任务绑定口径设计

> **状态**: 只读审计 + 方案文档  
> **日期**: 2026-07-13  
> **分支**: n4-p1-d-key-task-binding-design  
> **底线**: 本轮不改任何业务代码、数据库、接口。

---

## 1. 背景与目标

### 背景

当前系统三层结构已确立：

- **Project（项目）** → 顶层，组织单位
- **Task（重点工作/Workstream）** → 中层，项目下的重点工作实体
- **SubTask（关键任务/KeyTask）** → 底层，重点工作下的可执行最小单位

工作汇报 → AI 提取 → 确认入库 → 成果/问题/工作推进表写入 这条主链路已经可以跑通，但"关键任务绑定"尚未成为全链路强制约束。

### 目标

1. 梳理当前"项目 → 重点工作 → 关键任务"与工作汇报、成果、问题、AI确认入库之间的绑定关系现状。
2. 确认是否需要强制绑定关键任务，以及怎么绑定。
3. 给出短中长三期方案建议，分层决策。

---

## 2. 当前三层结构口径

| 层级 | 代码实体 | 物理表 | 业务含义 | 关联字段 |
|------|----------|--------|----------|----------|
| 第1层 | Project | `projects` | 项目/专项 | `project_id` |
| 第2层 | Task (aka Workstream) | `tasks` | 重点工作 | `tasks.project_id → projects.id` |
| 第3层 | SubTask (aka KeyTask) | `subtasks` | 关键任务 | `subtasks.task_id → tasks.id` |

**严格边界**：
- Task **不等于**关键任务。Task = 重点工作，字段名 `key_task` 是历史遗留（实际存储的是重点工作名称）。
- SubTask **不等于**普通子任务。SubTask = 关键任务，是执行层的最小粒度。
- 不存在第四层。不新增 workstream 表。
- `special_project` 只是项目名的镜像字段，不作为归属来源。

---

## 3. 当前代码与数据库现状

### 3.1 数据库字段审计

以下为各核心表的 `related_task_id` / `related_subtask_id` 字段现状：

| 表 | related_task_id | 指向 | related_subtask_id | 指向 |
|----|-----------------|------|--------------------|------|
| `update_submissions` | `FK → tasks.id` | **重点工作** | **不存在** | — |
| `achievements` | `FK → tasks.id` | **重点工作** | **不存在** | — |
| `issues` | `FK → tasks.id` | **重点工作** | **不存在** | — |
| `achievement_submissions` | `FK → tasks.id` | 重点工作 | `Integer` (nullable) | **存在但后端 schema 未利用** |

**结论**: 当前整个系统链路中，`related_task_id` 全局指向 `tasks.id` = **重点工作**。没有任何一个核心表有 `related_subtask_id` 字段。唯一存在 `related_subtask_id` 的是 `achievement_submissions`（成果申报草稿表），但后端 `AchievementSubmissionPayload` schema 并未暴露此字段。

### 3.2 后端 Schema 审计

| Schema | related_task_id | related_subtask_id |
|--------|-----------------|---------------------|
| `AchievementPayload` | `int \| None = None` | **无** |
| `IssuePayload` | `int \| None = None` | **无** |
| `AchievementSubmissionPayload` | `int` (必填) | **无** |
| `ExtractRequest` | **无** (通过 `user_subtasks` 上下文传递) | — |
| `SubTaskDraftsPayload` | **无** | — |

**结论**: 后端 Pydantic schema 完全没有 `related_subtask_id`。即使前端发送 `related_subtask_id`，也会被 `model_dump()` 丢弃。

---

## 4. 工作汇报绑定现状

### 4.1 当前绑定层级

**工作汇报（update_submissions）当前只能绑定到重点工作（Task），不能绑定到关键任务（SubTask）。**

代码事实：

```python
# models.py:69
related_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
```

- `ForeignKey("tasks.id")` → 指向 `tasks` 表 → 重点工作
- 不存在 `related_subtask_id` 字段
- 不存在 `key_task_id` 字段

### 4.2 提交流程中的绑定

1. **前端 VoiceUpdatePage** (`useVoiceSubmission.ts`):
   - 要求用户确认 AI 提取后 `task_reports` 中每个卡片绑定到具体的 `matched_subtask_id` 或 `parent_task_id`
   - 归属不完整的卡片会报错阻止提交
   - 最终 `human_result.task_reports[]` 中携带 `matched_subtask_id`、`parent_task_id`、`parent_key_task`

2. **后端 create_update** (`updates.py:202`):
   - `UpdateSubmission` 创建时 **不** 设置 `related_task_id`：
     ```python
     row = models.UpdateSubmission(
         project_id=project_id,
         ...
         # related_task_id 未设置！初始为 None
     )
     ```
   - `related_task_id` 只在确认入库时才被赋值
   - SubTask 信息以 JSON 格式存放在 `human_result_json` 的 `task_reports[]` 中

### 4.3 数据样例

数据库中 `update_submissions` 样例：
```
(id, project_id, related_task_id, submitter, confirm_status, ...)
(9, 19, 8, '吴肖', '已入库', ...)
(8, 19, 7, '吴肖', '已入库', ...)
```

### 4.4 结论

| 问题 | 答案 |
|------|------|
| 是否必填 project_id？ | 前端强制，后端422拒绝无project_id |
| related_task_id 指向 Task 还是 SubTask？ | **Task（重点工作）** |
| 是否存在 related_subtask_id？ | **否** |
| 前端提交时是否允许选择关键任务？ | 允许（通过 task_reports 卡片编辑），但仅存 JSON |
| 后端是否保存关键任务？ | 仅 JSON 保存，不落 `related_subtask_id` 字段 |

---

## 5. AI 确认入库绑定现状

### 5.1 确认入库写入逻辑总览

确认入库 (`POST /api/confirmations/{id}/confirm`) 的核心分支：

| 写入模式 | 条件 | 写入对象 | related_task_id 赋值 |
|----------|------|----------|---------------------|
| `subtask_update` | `target_subtask_id` 存在 | 更新已有 SubTask 状态/进度 | `parent_task.id`（重点工作） |
| `subtask_new` | `target_task_id` 存在 | 在已有 Task 下新建 SubTask | `parent_task.id`（重点工作） |
| `task_new` | `write_task=true` 且 `key_task` 有值 | 新建 Task（重点工作） | `task.id` |
| `task_reports` | `task_reports[]` 非空 | 多卡片处理 | 见下文 |

### 5.2 task_reports 多卡片处理

对于每个 `task_reports` 中的卡片：

```python
# confirmations.py:706-829
for report in task_reports_list:
    item_rt = report.get("result_type")

    if item_rt == "suggest_new_subtask":
        # 在 owner 指定的 parent_task（重点工作）下新建 SubTask
        new_sub = models.SubTask(task_id=parent_task.id, ...)
        row.related_task_id = parent_task.id  # ← 重点工作 ID

    elif item_rt in ("subtask_progress", "subtask_complete", None):
        subtask = db.get(models.SubTask, matched_subtask_id)
        # 更新 SubTask 的状态/进度
        row.related_task_id = parent.id  # ← 重点工作 ID (subtask.task_id)
        
        # 写入成果 → related_task_id = task_id (重点工作ID)
        W.fulfill_or_create_achievement(db, ..., task_id=task_id, ...)
        
        # 写入问题 → related_task_id = subtask.task_id (重点工作ID)
        issue = models.Issue(
            related_task_id=subtask.task_id,  # ← subtask.task_id = 重点工作ID
            ...
        )
```

### 5.3 结论

**确认入库时，所有写入的 related_task_id 全部指向重点工作（Task），不是关键任务（SubTask）。**

即使汇报内容关联到了具体的 `matched_subtask_id`（关键任务），最终：
- `achievements.related_task_id` = 重点工作 ID
- `issues.related_task_id` = 重点工作 ID
- `update_submissions.related_task_id` = 重点工作 ID

---

## 6. 成果库绑定现状

### 6.1 数据库

```python
# models.py:104
related_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
```

只有 `related_task_id`（→ Task/重点工作），无 `related_subtask_id`。

### 6.2 前端展示

`AchievementsPage.tsx` 第 542 行：

```tsx
<p className="truncate">{taskName(tasks, item.related_task_id)}</p>
<p className="text-xs text-slate-400">关键任务：暂未关联</p>
```

- 第1行显示**重点工作名称**（通过 `related_task_id` 查 `tasks.key_task`）
- 第2行**硬编码**显示"暂未关联"

详情弹窗同样：
```tsx
// 第 599 行
<Info label="关联关键任务" value="暂未关联" span />
```

### 6.3 手动登记表单

```tsx
// 第 656-657 行
<FormSelect label="关联关键任务" value={...} disabled>
  <option value="">暂未关联</option>
</FormSelect>
```

表单中有"关联关键任务"下拉框，但被 `disabled` 属性锁死为不可操作。下拉项只有"暂未关联"。

### 6.4 确认入库链路

确认入库时调用 `W.fulfill_or_create_achievement()`，其参数 `related_task_id` 传入的是 **重点工作 ID**（`task_id`），不存在传入 SubTask ID 的路径。

### 6.5 结论

| 问题 | 答案 |
|------|------|
| 是前端没传？ | 前端有 `related_subtask_id` 表单字段，但 `disabled` 且永远传 `null` |
| 是后端 schema 不支持？ | **是**。`AchievementPayload` 无 `related_subtask_id` |
| 是数据库表无字段？ | **是**。`achievements` 表无 `related_subtask_id` 列 |
| 是确认入库链路没写？ | **是**。确认入库时只传 Task ID |
| 是手动登记没写？ | **是**。手动登记表单 disabled |

**根因链**: 数据库无列 → 后端 Schema 无字段 → 确认入库链路只传 Task ID → 前端 disabled 展示"暂未关联"

---

## 7. 问题中心绑定现状

### 7.1 数据库

```python
# models.py:159
related_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
```

只有 `related_task_id`（→ Task/重点工作），无 `related_subtask_id`。

### 7.2 前端展示

`IssuesPage.tsx` 第 482 行：

```tsx
<p>关联重点工作：{taskNameForId(tasks, item.related_task_id)}</p>
<p className="text-slate-400">关键任务：暂未关联</p>
```

同上，第1行显示重点工作名称，第2行硬编码"暂未关联"。

### 7.3 手动登记表单

```tsx
// 第 785-787 行
<label>关联关键任务</label>
<select>
  <option>暂未关联</option>
</select>
```

下拉选项只有"暂未关联"，不可选。

### 7.4 确认入库链路

确认入库创建 Issue：
```python
# confirmations.py:392-393
issue = models.Issue(
    related_task_id=subtask.task_id,  # subtask.task_id = 重点工作 ID
    ...
)
```

### 7.5 结论

与成果库完全一致：数据库无列 → Schema 不支持 → 确认入库只写 Task ID → 前端显示"暂未关联"。

---

## 8. 工作推进表展示现状

### 8.1 TaskManagementPage 展示层级

`TaskManagementPage.tsx` 展示两层：

1. **重点工作列表** (`fetchTasks()` → `/api/tasks`)
   - 对应表 `tasks`，每条是一个重点工作（Workstream）
   - 显示字段：`key_task`（重点工作名称）、`owner`、`coordinator`、`status`

2. **每个重点工作下的关键任务列表** (`fetchSubTasks(taskId)` → `/api/tasks/{id}/subtasks`)
   - 对应表 `subtasks`，每条是一个关键任务（KeyTask）
   - 显示字段：`title`（关键任务名称）、`assignee`、`status`

### 8.2 关键任务列表来源

- API: `GET /api/tasks/{task_id}/subtasks`
- 返回: `SubTask[]`（不含 `related_task_id`，因为 `subtasks` 表本身没有此字段）

### 8.3 从工作汇报跳回关键任务

`MyTasksPage.tsx` 支持查看某个 SubTask 的详细信息和关联的汇报/成果/问题：

```typescript
// subtasks.py:358-396
// GET /api/subtasks/{id}/detail 返回:
// - source_submission（来源汇报）
// - related_achievements（关联成果，通过 achievements.related_task_id == subtask.task_id 查询）
// - related_issues（关联问题，通过 issues.related_task_id == subtask.task_id 查询）
```

注意：这里查询成果/问题时用的是 `related_task_id == subtask.task_id`，而 `subtask.task_id` 是 **重点工作 ID**。因此只能查到关联到同一重点工作的所有成果，无法精确到具体关键任务。

---

## 9. 当前风险与差距

### 9.1 串位风险

| 风险 | 现状 | 严重度 |
|------|------|--------|
| `related_task_id` 可能属于其他 project | 确认入库时 `related_task_id` 来自 `subtask.task_id`（通过父 Task 的 project_id 间接校验），但创建 Issue 时无显式校验 | **中** |
| 创建成果时是否校验 project_id 一致性 | `fulfill_or_create_achievement` 进行名称匹配去重，无 project_id 显式校验 | **中** |
| 工作汇报时是否校验 related_task_id 与 project_id | 前端 `task_reports` 有 project 上下文，后端无显式校验 | **低** |

### 9.2 核心差距

| 差距 | 描述 |
|------|------|
| **关键任务不可绑定** | 整个系统链路的 `related_task_id` 全部指向 `tasks.id`（重点工作），没有任何机制将成果/问题/汇报绑定到具体 SubTask |
| **前端占位符** | 成果库、问题中心的"关键任务：暂未关联"是硬编码，不是数据驱动的 |
| **后端 Schema 缺字段** | `AchievementPayload`、`IssuePayload` 均无 `related_subtask_id` |
| **确认入库只写 Task 级** | 确认入库的成果/问题写入只传 Task ID，SubTask 信息丢失 |
| **SubTask 详情反向查询不准** | `GET /api/subtasks/{id}/detail` 通过 `related_task_id == subtask.task_id` 查关联数据，实为重点工作级别查询 |

---

## 10. 产品口径建议

### 10.1 工作汇报是否必须绑定关键任务？

**建议：分三类处理**

| 场景 | 是否强制绑定 | 理由 |
|------|-------------|------|
| 普通成员正式汇报 | **是**（通过 `task_reports` 的 `matched_subtask_id`） | 成员汇报必须说明对哪个关键任务的进展 |
| 统筹人/协助人补充汇报 | **是**（同上） | 补充汇报同样应关联到具体关键任务 |
| 负责人管理性更新或项目级总结 | **否** | 负责人可能需要做项目整体进展汇报，不针对单个关键任务 |

**V1 实现**：前端 `task_reports` 卡片编辑已强制要求 `matched_subtask_id`，但不强制在 `update_submissions` 表存储。**当前需要新增的是后端持久化 `related_subtask_id`**。

### 10.2 成果是否必须绑定关键任务？

**建议：分情况**

| 场景 | 是否强制 | 说明 |
|------|---------|------|
| AI 确认入库成果（关联到具体任务卡） | **是** | 卡片已经绑定了关键任务，写入时应保留关联 |
| 手动登记成果（指定了关键任务） | **是** | 用户手动选择时应绑定 |
| 手动登记成果（不指定关键任务，仅项目级） | **否** | "项目级成果"是合理需求 |
| 项目级成果但不属于某个关键任务 | **否** | 如项目文档、会议纪要等全局性成果 |

### 10.3 问题是否必须绑定关键任务？

**建议：分情况**

| 场景 | 是否强制 | 说明 |
|------|---------|------|
| 执行问题（某关键任务的阻塞/风险） | **是** | 必须关联到具体关键任务 |
| 风险/待决策事项（可能跨关键任务） | **建议但不强制** | 可绑定到重点工作级别 |
| 项目级问题（不属于某个关键任务） | **否** | 如项目资源问题、人员问题 |

### 10.4 汇报涉及多个关键任务怎么处理？

**推荐方案：拆成多条结构化确认卡（当前已实现）**

当前 `task_reports[]` 设计已经天然支持一个汇报拆成多张确认卡，每张卡绑定一个关键任务。**这个架构是正确的，不需要改动。**

如果未来需要更复杂的关联（如一个关键任务同时产出成果和问题），当前设计也已支持：每张卡内可同时包含 `achievements` 和 `subtask_issues`。

### 10.5 AI 建议新增关键任务时，原始汇报挂哪里？

**推荐：确认后生成新关键任务，原始汇报通过 `source_submission_id` 追溯，成果/问题关联到新关键任务**

当前实现（`confirmations.py:713-753`）：
1. 负责人选择归属 `parent_task_id`（重点工作）
2. 确认入库时创建新 SubTask（`source_submission_id=row.id`）
3. 成果写入时 `related_task_id=parent_task.id`

**建议增强**：在新增 `related_subtask_id` 后，新关键任务的成果/问题也应关联到新创建的 SubTask ID，而非仅挂到重点工作。

### 10.6 是否需要新增数据库字段？

**建议：是。最小字段设计如下：**

| 表 | 新增字段 | 类型 | 说明 |
|----|---------|------|------|
| `update_submissions` | `related_subtask_id` | `Integer, FK → subtasks.id, nullable=True` | 汇报关联的关键任务 ID |
| `achievements` | `related_subtask_id` | `Integer, FK → subtasks.id, nullable=True` | 成果关联的关键任务 ID |
| `issues` | `related_subtask_id` | `Integer, FK → subtasks.id, nullable=True` | 问题关联的关键任务 ID |

前端：
- 成果登记/问题登记表单启用"关联关键任务"下拉框
- 成果库/问题中心列表和详情展示关键任务名称

**但本轮不实现。**

### 10.7 是否可以短期不改数据库？

**可以。建议 V1 过渡方案：**

**只强制绑定重点工作（当前已实现），关键任务仅前端展示占位（当前状态）。**

理由：
1. 当前系统主流程可运行：汇报 → AI 提取 → 确认入库 → 成果/问题/工作推进表写入
2. `related_task_id`（重点工作级绑定）已覆盖大部分业务需求
3. 关键任务级绑定的业务价值是"更精细化追溯和管理"，不是"阻断性功能"
4. 可以在不改数据库的前提下，先在前端做展示增强（如从 `human_result_json.task_reports[].parent_key_task` 提取展示）

**不建议立刻强制**，因为没有数据库字段支撑的强制是无意义的。

---

## 11. 推荐方案

### 方案 A：不改数据库的短期方案（当前 V1.0）

**改什么**：
- 成果库/问题中心前端去掉"暂未关联"硬编码，改为从 `source_submission_id` → `human_result_json.task_reports[].matched_subtask_title` 反向推导关键任务名称（只读展示，不可筛选）
- 确认中心详情在"我的提交记录"视图展示各确认卡关联的关键任务名称
- 文档说明：当前"关联关键任务"为只读追溯展示，不强制

**不改什么**：
- 数据库结构
- 后端 Schema
- API 接口
- 前端表单逻辑

**优点**：
- 零数据库变更
- 零后端变更
- 前端小改动
- 立即消除"暂未关联"的困惑

**缺点**：
- 展示数据来自 JSON，性能差、不可索引、不可筛选
- 仍然是"假关联"，数据不可靠
- 不能做"按关键任务筛选成果/问题"

**适合什么阶段**：**目前就是 V1.0 阶段**

### 方案 B：最小数据库增强方案

**新增字段**：

| 表 | 新增 |
|----|------|
| `update_submissions` | `related_subtask_id` (FK → subtasks.id, nullable) |
| `achievements` | `related_subtask_id` (FK → subtasks.id, nullable) |
| `issues` | `related_subtask_id` (FK → subtasks.id, nullable) |

**接口兼容**：
- `AchievementPayload` 新增 `related_subtask_id: int | None = None`
- `IssuePayload` 新增 `related_subtask_id: int | None = None`
- `GET /api/achievements` 返回中包含 `related_subtask_id`
- `GET /api/issues` 返回中包含 `related_subtask_id`
- 筛选参数增加 `related_subtask_id`
- 确认入库路径中 `fulfill_or_create_achievement` 新增 `related_subtask_id` 参数
- 确认入库创建 Issue 时写入 `related_subtask_id`

**前端页面**：
- 成果登记/问题登记表单启用"关联关键任务"下拉框
- 成果库/问题中心列表显示关键任务名称
- 确认中心确认入库时保留 `matched_subtask_id` → `related_subtask_id`

**数据迁移**：
- 三个新字段均为 `nullable=True`，默认 NULL，无需回填历史数据
- 老数据 `related_subtask_id=NULL`，前端展示"未指定"

**风险**：
- 确认入库链路是复杂分支逻辑，新增参数需谨慎测试所有模式（`task_new`、`subtask_update`、`subtask_new`、`task_reports`）
- `fulfill_or_create_achievement` 有去重逻辑，需确保不影响
- 前端下拉框选项需动态加载 `fetchSubTasks(taskId)`

### 方案 C：完整关键任务绑定方案

在方案 B 基础上增加：

**工作汇报端**：
- `UpdateSubmission` 创建时即写入 `related_subtask_id`（从 `task_reports[0].matched_subtask_id`）
- 多卡片的汇报，支持 `related_subtask_id` 指向主关键任务

**确认中心端**：
- 确认入库时根据每张确认卡写入 `related_subtask_id` 到成果/问题
- AI 新增关键任务后，成果/问题回填新关键任务 ID

**前端增强**：
- 工作推进表从成果/问题反向追溯（点击成果可看到关联的关键任务）
- 关键任务详情展示名下所有成果/问题/汇报
- 筛选器增加"按关键任务筛选"

**优点**：全链路可追溯、数据完整性最高

**缺点**：改动范围大、需要更多测试、确认中心复杂分支需要重构

---

## 12. 不推荐方案

| 方案 | 为什么不推荐 |
|------|-------------|
| 强制所有场景绑定关键任务 | 项目级成果、管理性汇报不应被强制绑定 |
| 新增 `Tasks.related_subtask_id` 反向字段 | subtask 已通过 `task_id` 关联 Task，反向字段冗余 |
| 把 `related_task_id` 改为指向 SubTask | 破坏已有绑定关系，且 SubTask 无法独立于 Task 存在 |
| 把所有"暂未关联"文字直接删除 | 用户会疑惑为什么没有这个信息，需要替代文案 |

---

## 13. 分阶段实施计划

| 阶段 | 内容 | 预估工时 |
|------|------|----------|
| **P1（立即）** | 当前审计 + 方案文档（本文档） | ✅ 已完成 |
| **P2（短期）** | 方案 A：前端去硬编码，"暂未关联"改为"当前仅支持重点工作关联" | 0.5d |
| **P2（短期）** | 确认中心详情展示 task_reports 中关键任务名称 | 0.5d |
| **P3（中期）** | 方案 B：数据库+Schema+接口+确认入库+前端表单 全链路新增 `related_subtask_id` | 3-5d |
| **P4（长期）** | 方案 C：全链路强制绑定 + 反向追溯 + 筛选器增强 | 5-8d |

---

## 14. 是否需要改数据库

**P1 审计阶段：不需要。**

**P3 实现阶段（方案 B/C）：需要。**
- 新增 3 个字段：`update_submissions.related_subtask_id`、`achievements.related_subtask_id`、`issues.related_subtask_id`
- 均为 `nullable=True`，不影响现有数据

---

## 15. 是否需要改接口

**P1 审计阶段：不需要。**

**P3 实现阶段（方案 B/C）：需要。**
- `AchievementPayload`、`IssuePayload` 新增 `related_subtask_id`
- 成果/问题列表接口返回新增字段
- 确认入库 `fulfill_or_create_achievement` 新增参数
- 确认入库创建 Issue 路径新增字段写入

---

## 16. 兼容与迁移建议

1. **字段默认 NULL**：所有新增字段 `nullable=True`，历史数据不受影响。
2. **API 向前兼容**：前端未传 `related_subtask_id` 时行为不变。
3. **前端渐进增强**：先改"暂未关联"占位文案，再逐步启用表单下拉框。
4. **不需要数据回填**：历史数据的"关联关键任务"无法从 JSON 可靠推断，保持 NULL 即可。

---

## 17. 测试建议

### P1 阶段（本文档）
- 无新测试需要，纯审计文档

### P2 阶段（方案 A）
- `AchievementsPage.spec.tsx`：验证不再硬编码"暂未关联"
- `IssuesPage.spec.tsx`：同上
- `ConfirmPage.spec.tsx`：验证"我的提交记录"视图展示关键任务名称

### P3 阶段（方案 B）
- `test_confirmations.py`：验证确认入库各模式正确写入 `related_subtask_id`
- `test_achievements.py`：验证手动登记和列表查询包含 `related_subtask_id`
- `test_issues.py`：同上
- 前端 E2E：验证成果登记/问题登记表单下拉框可选择关键任务
- 数据一致性测试：`related_subtask_id` 指向的 SubTask 必须属于 `related_task_id` 指向的 Task

---

## 18. 最终结论

### 18.1 现状总结

| 维度 | 当前状态 |
|------|---------|
| 工作汇报是否能绑定关键任务 | **能**（通过 `human_result_json.task_reports[].matched_subtask_id` 记录在 JSON 中，不落表） |
| 成果是否能绑定关键任务 | **不能**（`achievements` 表无 `related_subtask_id`，后端 Schema 不支持） |
| 问题是否能绑定关键任务 | **不能**（`issues` 表无 `related_subtask_id`，后端 Schema 不支持） |
| `related_task_id` 实际指向 | **重点工作（Task）** |
| 是否需要新增字段 | **是**（`related_subtask_id` × 3） |
| 当前最大差距 | 数据库缺少字段 → 整个链路无法持久化关键任务绑定 |

### 18.2 推荐

| 决策 | 建议 |
|------|------|
| **是否进入下一轮开发？** | **是**，但分阶段 |
| **先做 A / B / C 哪个？** | **先做 A**（4-8h），再做 **B**（3-5d） |
| **为什么？** | A 消除用户困惑（成本极低、零风险），B 建立数据基础设施后 C 才可行 |
| **什么时候做 C？** | B 稳定上线后，根据业务反馈决定优先级 |

### 18.3 关键结论一句话

> 当前系统"关键任务绑定"的最大瓶颈不在代码逻辑，而在数据库缺少 `related_subtask_id` 字段。前端可短期通过 JSON 反推展示消除"暂未关联"困惑，中期通过新增 3 个可选字段建立全链路绑定能力。
