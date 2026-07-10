# 默认值一致性审计（N3-B0.1）

审计日期：2026-07-10  
审计性质：只读盘点，不做迁移，不改业务逻辑

本次审计目标是确认 `model / schema / router` 的默认值是否一致，避免“绕过接口时的 ORM 默认值”和“正常创建时的请求默认值”出现分叉。

## 一、审计结论概览

| 对象名称 | model 默认值 | schema 默认值 | router 显式默认值 | 当前是否一致 | 是否参与业务判断 | 风险等级 | 是否建议修复 | 建议修复方式 |
|---|---|---|---|---|---|---|---|---|
| Project（生命周期） | `status="draft"`，`is_active=False` | `ProjectCreatePayload.status="draft"`，无 `is_active` 字段 | 项目创建 router 显式设为 `draft / False` | 是 | 是 | P1 | 否（已完成） | 保持现状；只维护同一口径 |
| Project（管理页） | `status="draft"`，`is_active=False` | `ProjectPayload.is_active=True` | `people.py` 的项目创建/更新直接写入 `payload.is_active` | 否 | 是 | P1 | 建议下一轮复核 | 若该 admin 入口确实需要“默认启用”，保留并在文档注明；若要与生命周期口径统一，可把默认值改为 `False` |
| Task / 重点工作 | `status="未开始"` | `TaskPayload.status="未开始"` | `tasks.py` 创建时默认跟随 payload | 是 | 是 | P2 | 否 | 保持现状 |
| SubTask / 关键任务 | `status="未开始"` | `SubTaskPayload.status="未开始"` | `subtasks.py` 创建时默认跟随 payload | 是 | 是 | P2 | 否 | 保持现状 |
| UpdateSubmission / 工作汇报 | `confirm_status="待确认"`，`title=""`，`source_type` 无默认 | `ExtractRequest` 无默认；`title` 为可选字段 | `updates.py` 创建时 `title=payload.title or "工作汇报"`，`confirm_status=SS.S_NEW` | 部分一致 | 是 | P2 | 建议保留 | `title` 作为展示默认可以保留在 router；`confirm_status` 与 model 已一致 |
| Issue / 问题 | `issue_type` 无默认，`status="待处理"`，`source_type="人工录入"` | `IssuePayload.issue_type="问题"`，`status="待处理"`，`source_type="人工录入"` | `issues.py` 创建时直接使用 payload | 是 | 是 | P2 | 否 | 保持现状 |
| Achievement / 成果 | `status="草稿"`，`source_type="人工录入"` | `AchievementPayload.status="计划中"`，`source_type="人工录入"` | `achievements.py` 创建时直接使用 payload | 否 | 是 | P2 | 建议下一轮逐个确认 | 先确认“成果”业务的真实首态是 `草稿` 还是 `计划中`；若确实以 `计划中` 为准，再统一 model 默认值 |
| Meeting / 会议 | `meeting_type=""`，`title=""`，`publish_status="draft"` | `MeetingPayload.meeting_type=""`，`title=""`，`publish_status="draft"` | `meetings.py` 创建时直接使用 payload | 是 | 是 | P2 | 否 | 保持现状 |
| Notification / 通知 | `recipient=""`，`body=""`，`link=""`，`is_read=False` | 无专用创建 payload | 通知写入点由各 router 直接构造 | 是 | 是 | P2 | 否 | 保持现状 |
| OperationLog / 操作日志 | `operator=""`，`action=""`，`target_type=""`，`note=""`，`before_json=""`，`after_json=""` | 无专用创建 payload | `crud.log(...)` 直接写入 | 是 | 否（审计记录） | P2 | 否 | 保持现状 |

## 二、逐项说明

### 1) Project / ProjectCreatePayload / 项目创建 router

- `bowei_ai_dashboard/app/models.py`：`Project.status="draft"`，`Project.is_active=False`
- `bowei_ai_dashboard/app/schemas.py`：`ProjectCreatePayload.status="draft"`
- `bowei_ai_dashboard/app/routers/projects.py`：创建项目时显式落为 `draft / False`

结论：一致，且与 N2 / N3-B0 的修复口径一致。

### 2) Project / ProjectPayload / 管理页项目创建与更新

- `bowei_ai_dashboard/app/models.py`：`Project.status="draft"`，`Project.is_active=False`
- `bowei_ai_dashboard/app/schemas.py`：`ProjectPayload.is_active=True`
- `bowei_ai_dashboard/app/routers/people.py`：创建与更新时直接写入 `payload.is_active`

结论：默认值不一致，但这条路由属于管理页项目维护入口，不是主项目生命周期创建入口。当前更像“管理后台的默认勾选值”，不建议在本轮直接改。

### 3) Task / SubTask

- `Task.status`、`TaskPayload.status`、`BatchImportRow.status`：均为 `未开始`
- `SubTask.status`、`SubTaskPayload.status`：均为 `未开始`

结论：一致。

### 4) UpdateSubmission / 工作汇报

- `UpdateSubmission.confirm_status="待确认"`
- `ExtractRequest` 没有为 `title` / `source_type` 提供模型默认
- `updates.py` 创建时会把 `title` 缺省为 `工作汇报`
- `updates.py` 创建时把 `confirm_status` 显式设为 `SS.S_NEW`

结论：

- `confirm_status` 一致。
- `title` 的默认值是 router 级别的展示默认，不是 model/schema 层默认；这不属于业务冲突，但建议在后续统一文档里注明“展示默认”与“持久化默认”的区别。

### 5) Issue / 问题

- `Issue.status="待处理"`
- `IssuePayload.status="待处理"`
- `IssuePayload.issue_type="问题"`
- `IssuePayload.source_type="人工录入"`

结论：一致。

### 6) Achievement / 成果

- `Achievement.status="草稿"`
- `AchievementPayload.status="计划中"`
- `AchievementPayload.source_type="人工录入"`
- `achievements.py` 创建时直接把 payload 写入 ORM

结论：这里存在明确的默认值不一致。  
这是本轮审计里最值得继续确认的一处，因为它直接影响“新成果创建后最初显示为草稿还是计划中”。

建议：下一轮先确认业务口径，再决定是改 schema 默认值还是改 model 默认值；不要两边各留一个不同起点。

### 7) Meeting / 会议

- `Meeting.publish_status="draft"`
- `MeetingPayload.publish_status="draft"`
- 会议创建 router 未引入另一套默认值

结论：一致。

### 8) Notification / OperationLog

- 通知和操作日志都没有独立的创建 payload 默认值分叉
- 它们的默认值主要是空字符串 / `False`

结论：没有发现明显默认值冲突。

## 三、风险判断

### 当前最高风险默认值问题

1. `AchievementPayload.status="计划中"` vs `Achievement.status="草稿"`
2. `ProjectPayload.is_active=True` vs `Project.is_active=False`

其中第 1 项更像“业务首态口径不一致”；第 2 项更像“管理页默认勾选值和生命周期默认值不同”。

### 是否需要立即修复

当前不建议在本轮直接改业务代码。原因是：

- `Project` 生命周期口径已经在 N2 / N3-B0 固定下来；
- `Achievement` 的“首态”到底是 `草稿` 还是 `计划中`，仅凭默认值本身还不足以下结论；
- `ProjectPayload.is_active` 可能是管理页入口的刻意默认值，不一定是 bug。

### 明确结论

本轮结论选项：`B. 发现少量小问题，建议下一轮逐个修`

理由：

- 大多数对象的默认值已经对齐；
- 存在少量 schema / model / router 默认值不一致，但暂未达到“必须立刻修改”的程度；
- 下一轮优先建议先确认 `Achievement` 与 `ProjectPayload.is_active` 的业务口径，再决定是否统一默认值。
