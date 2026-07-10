# 状态与类型值审计（N3-A）

审计日期：2026-07-10  
审计性质：只读盘点，不做迁移，不改业务代码

本次审计覆盖：

- `bowei_ai_dashboard/app/models.py`
- `bowei_ai_dashboard/app/schemas.py`
- `bowei_ai_dashboard/app/domain/`
- `bowei_ai_dashboard/app/routers/`
- `bowei_ai_dashboard/app/services/`
- `bowei_ai_dashboard/app/permissions.py`
- `bowei_ai_dashboard/tests/`
- 只读观察 `frontend/src/domain/` 的状态标签映射

## 一、状态 / 类型总表

说明：

- “是否参与后端判断”指是否会进入 normalize、权限、流转、筛选、入库判断。
- “是否写入数据库”指是否会被 ORM / SQLAlchemy / 日志表 / 通知表持久化。
- “是否暴露给前端”指是否会经由 API 返回给前端，或被前端标签映射消费。
- 风险等级只用于后续分层治理，不代表本轮要修改。

### 1) 项目生命周期状态

> 当前项目生命周期实际写入 `projects.status` + `projects.is_active`。  
> 现状下 `Project` ORM 默认值已修正为 `draft / False`，但 `ProjectCreatePayload.status` 在 `app/schemas.py` 里仍是 `"active"`，这是本次盘点里最需要注意的“默认值不一致”点。

| 类别 | 当前值 | 中文含义 | 出现位置 | 是否参与后端判断 | 是否写入数据库 | 是否暴露给前端 | 是否建议改成英文 key | 建议标准 key | 兼容别名建议 | 风险等级 |
|---|---|---|---|---|---|---|---|---|---|---|
| 项目生命周期 | `draft` | 草稿 / 待派发 | `app/models.py`, `app/routers/projects.py`, `frontend/src/domain/projectLifecycleStatus.ts` | 是 | 是 | 是 | 已是英文 key | `draft` | 保持与 `pending_review` 等并列 | P1 |
| 项目生命周期 | `dispatched` | 已派发 / 已发起项目流程 | `app/routers/projects.py` | 是 | 是 | 是 | 已是英文 key | `dispatched` | 与旧接口返回保持兼容 | P2 |
| 项目生命周期 | `pending_review` | 待审核 / 待确认立项 | `app/routers/projects.py`, `frontend/src/domain/projectLifecycleStatus.ts` | 是 | 是 | 是 | 已是英文 key | `pending_review` | 保持与 `returned`、`draft` 并列 | P2 |
| 项目生命周期 | `returned` | 已退回 / 需修改后重提 | `app/routers/projects.py` | 是 | 是 | 是 | 已是英文 key | `returned` | 与“驳回/退回”旧文案兼容 | P2 |
| 项目生命周期 | `active` | 已通过审核并进入执行 | `app/models.py`, `app/routers/projects.py`, `app/routers/updates.py` | 是 | 是 | 是 | 已是英文 key | `active` | 保持 `is_active=True` 语义 | P1 |
| 项目生命周期 | `archived` | 归档 / 停止活跃 | `app/routers/projects.py`, `frontend/src/domain/projectLifecycleStatus.ts` | 是 | 是 | 是 | 已是英文 key | `archived` | 与 `is_active=False` 历史兼容 | P2 |

### 2) 任务 / 重点工作 / SubTask 状态

| 类别 | 当前值 | 中文含义 | 出现位置 | 是否参与后端判断 | 是否写入数据库 | 是否暴露给前端 | 是否建议改成英文 key | 建议标准 key | 兼容别名建议 | 风险等级 |
|---|---|---|---|---|---|---|---|---|---|---|
| 任务状态 | `未开始` | 还未启动 | `app/domain/task_status.py`, `app/models.py`, `app/routers/tasks.py`, `app/routers/subtasks.py`, `frontend/src/domain/myTasksFlow.ts` | 是 | 是 | 是 | 是，属于后续候选 | `not_started` | `not_started`, `notstarted`, `未启动` | P1 |
| 任务状态 | `进行中` | 正在推进 | 同上 | 是 | 是 | 是 | 是，属于后续候选 | `in_progress` | `推进中`, `in_progress` | P1 |
| 任务状态 | `已完成` | 已完成 | 同上 | 是 | 是 | 是 | 是，属于后续候选 | `completed` | `完成`, `completed` | P1 |
| 任务状态 | `延期` | 超期 / 延期 | 同上 | 是 | 是 | 是 | 是，属于后续候选 | `delayed` | `已延期`, `delayed` | P2 |
| 任务状态 | `暂缓` | 暂停推进 | 同上 | 是 | 是 | 是 | 是，属于后续候选 | `paused` | `暂停`, `已暂停`, `paused` | P2 |
| 任务状态 | `已归档` | 已归档 | 同上 | 是 | 是 | 是 | 是，属于后续候选 | `archived` | `archived` | P2 |

> 说明：任务状态现在是中文 canonical 值，业务代码靠 `task_status.normalize()` 做别名归一。这个设计能稳定运行，但未来做英文 key 化时必须保留 normalize 兼容层。

### 3) 确认中心 / 提交流转状态

| 类别 | 当前值 | 中文含义 | 出现位置 | 是否参与后端判断 | 是否写入数据库 | 是否暴露给前端 | 是否建议改成英文 key | 建议标准 key | 兼容别名建议 | 风险等级 |
|---|---|---|---|---|---|---|---|---|---|---|
| 提交状态 | `待确认` | 新提交 / 待处理 | `app/domain/submission_status.py`, `app/routers/confirmations.py`, `app/routers/updates.py`, `frontend/src/domain/submissionStatus.ts` | 是 | 是 | 是 | 是，后续候选 | `pending_submission` | `pending_owner_review` 语义近似但不建议直接混用 | P1 |
| 提交状态 | `待负责人审核` | 待 owner 审核 | 同上 | 是 | 是 | 是 | 是，后续候选 | `pending_owner_review` | `pending_owner_review`, `resubmitted`, `已重新提交`, `提交人已确认` | P1 |
| 提交状态 | `已打回提交人` | 已退回给提交人 | 同上 | 是 | 是 | 是 | 是，后续候选 | `returned_to_submitter` | `returned_to_submitter`, `已打回`, `已退回` | P1 |
| 提交状态 | `已撤回` | 提交人撤回 | 同上 | 是 | 是 | 是 | 是，后续候选 | `withdrawn` | `withdrawn`, `withdrawn_editable` | P2 |
| 提交状态 | `不入库` | 明确不写入业务数据 | 同上 | 是 | 是 | 是 | 是，后续候选 | `permanently_rejected` | 历史别名 `已归档`、`已退回` 不建议再扩散 | P1 |
| 提交状态 | `已转交统筹人` | 转交统筹人处理 | 同上 | 是 | 是 | 是 | 是，后续候选 | `waiting_coordinator_feedback` | `transferred_to_coordinator` | P1 |
| 提交状态 | `统筹人已反馈` | 统筹人反馈完成 | 同上 | 是 | 是 | 是 | 是，后续候选 | `coordinator_feedback_given` | `coordinator_feedback_given` | P1 |
| 提交状态 | `待CEO决策` | 当前业务语义：等待项目企业教练决策 | 同上 | 是 | 是 | 是 | 是，后续候选 | `waiting_project_coach_decision` | `pending_ceo_decision`（legacy alias） | P0/P1 |
| 提交状态 | `CEO已批示` | 企业教练已批示 | 同上 | 是 | 是 | 是 | 是，后续候选 | `project_coach_decided` | `ceo_decided`（legacy alias） | P1 |
| 提交状态 | `已入库` | 确认写入业务数据 | 同上 | 是 | 是 | 是 | 是，后续候选 | `confirmed_and_stored` | `stored`, `approved_for_storage`, `已确认`, `已确认入库` | P1 |
| 提交状态 | `需修改` | 需要修改后再流转 | 同上 | 是 | 是 | 是 | 是，后续候选 | `needs_revision` | 作为内部路由态保留 | P2 |

> 重要备注：`WAITING_CEO_DECISION` 这个常量名仍然是 legacy name，但当前业务语义已经明确是“等待项目企业教练决策”。这类命名适合在下一轮做兼容式重命名，而不是在本轮硬改。

### 4) 问题类型 / 问题状态 / 决策类型

| 类别 | 当前值 | 中文含义 | 出现位置 | 是否参与后端判断 | 是否写入数据库 | 是否暴露给前端 | 是否建议改成英文 key | 建议标准 key | 兼容别名建议 | 风险等级 |
|---|---|---|---|---|---|---|---|---|---|---|
| 问题类型 | `问题` | 普通问题 | `app/domain/issue_flow.py`, `app/routers/issues.py`, `app/routers/confirmations.py` | 是 | 是 | 是 | 是，后续候选 | `issue` | `问题` | P2 |
| 问题类型 | `风险` | 风险项 | 同上 | 是 | 是 | 是 | 是，后续候选 | `risk` | `风险` | P2 |
| 问题类型 | `待协调` | 协调事项 | 同上 | 是 | 是 | 是 | 是，后续候选 | `coordination` | `待协调`, `需协调` | P2 |
| 问题类型 | `需决策` | 决策事项 | 同上 | 是 | 是 | 是 | 是，后续候选 | `decision` | `需决策`, `决策事项`, `需CEO决策`, `待CEO决策` | P1 |
| 问题状态 | `待处理` | 尚未处理 | 同上 | 是 | 是 | 是 | 是，后续候选 | `pending` | `待处理` | P2 |
| 问题状态 | `处理中` | 正在处理 | 同上 | 是 | 是 | 是 | 是，后续候选 | `in_progress` | `处理中`, `处理` | P2 |
| 问题状态 | `待决策` | 等待决策 | 同上 | 是 | 是 | 是 | 是，后续候选 | `pending_decision` | `待决策`, `待CEO决策` | P1 |
| 问题状态 | `已解决` | 已解决 | 同上 | 是 | 是 | 是 | 是，后续候选 | `resolved` | `已解决`, `已决策`, `已完成` | P2 |
| 问题状态 | `已关闭` | 已关闭 | 同上 | 是 | 是 | 是 | 是，后续候选 | `closed` | `已关闭`, `关闭` | P2 |

> 说明：问题流转的“类型”和“状态”都已经有 normalize 映射，但和确认中心一样，中文 canonical + legacy alias 混用仍然存在，后续做英文 key 化必须保留兼容层。

### 5) AI / 汇报结果类型（`result_type`）

| 类别 | 当前值 | 中文含义 | 出现位置 | 是否参与后端判断 | 是否写入数据库 | 是否暴露给前端 | 是否建议改成英文 key | 建议标准 key | 兼容别名建议 | 风险等级 |
|---|---|---|---|---|---|---|---|---|---|---|
| 结果类型 | `subtask_progress` | 子任务进展 | `app/domain/submission_result_type.py`, `app/routers/confirmations.py`, `frontend/src/domain/confirmationFlow.ts` | 是 | 是 | 是 | 已是英文 key | `subtask_progress` | 保持现状 | P2 |
| 结果类型 | `subtask_complete` | 子任务完成 | 同上 | 是 | 是 | 是 | 已是英文 key | `subtask_complete` | 保持现状 | P2 |
| 结果类型 | `subtask_status_update` | 子任务状态变更 | 同上 | 是 | 是 | 是 | 已是英文 key | `subtask_status_update` | 保持现状 | P2 |
| 结果类型 | `suggest_new_subtask` | 建议新增子任务 | 同上 | 是 | 是 | 是 | 已是英文 key | `suggest_new_subtask` | 保持现状 | P2 |
| 结果类型 | `task_issue` | 重点工作问题 | 同上 | 是 | 是 | 是 | 已是英文 key | `task_issue` | 保持现状 | P2 |
| 结果类型 | `project_issue` | 项目问题 / 风险 | 同上 | 是 | 是 | 是 | 已是英文 key | `project_issue` | 保持现状 | P2 |
| 结果类型 | `achievement` | 成果 | 同上 | 是 | 是 | 是 | 已是英文 key | `achievement` | 保持现状 | P2 |
| 结果类型 | `unknown` | 未识别 | 同上 | 是 | 是 | 是 | 已是英文 key | `unknown` | 保持现状 | P2 |

> 说明：`result_type` 这一组是当前最适合继续保持英文 key 的区域，前端也已经按英文 key 分类，属于较稳的一层。

### 6) 操作日志 action code

> 这里按“业务家族”盘点，不逐条展开 60+ 个原始值；但原始值本身已经全部扫描到。  
> 日志 action 现在是最明显的“混合编码”区域：既有稳定英文 code，也有大量中文动词短语。它们主要用于审计，不直接决定业务流程，但会影响可搜索性、统计口径和后续英文 key 化。

| 类别 | 当前值 | 中文含义 | 出现位置 | 是否参与后端判断 | 是否写入数据库 | 是否暴露给前端 | 是否建议改成英文 key | 建议标准 key | 兼容别名建议 | 风险等级 |
|---|---|---|---|---|---|---|---|---|---|---|
| 系统/账号 | `create`, `update`, `delete`, `update_status`, `reset_password`, `batch_create` | 通用系统动作 | `app/routers/accounts.py`, `app/routers/people.py` 等 | 否 | 是 | 否（通常只在审计页） | 已是英文 key | 保持现状 | 无 | P2 |
| 项目管理 | `create_project`, `update_project`, `archive_project`, `dispatch_project`, `owner_submit_project`, `return_project`, `approve_project`, `kickoff_project` | 项目生命周期动作 | `app/routers/projects.py` | 否 | 是 | 否 | 已是英文 key | 保持现状 | 无 | P2 |
| 项目成员 | `add_project_member`, `update_project_member`, `remove_project_member`, `approve_member_change`, `approve_member_change_auto`, `reject_member_change`, `create_member_change_request` | 成员与变更 | `app/routers/projects.py` | 否 | 是 | 否 | 已是英文 key | 保持现状 | 无 | P2 |
| 会议 | `meeting_create`, `meeting_update`, `meeting_delete`, `meeting_update_status`, `meeting_publish`, `meeting_return`, `meeting_save_draft`, `meeting` | 会议流转 | `app/routers/meetings.py` | 否 | 是 | 否 | 已是英文 key / 混有少量旧值 | 建议统一到稳定英文 | 旧值 `meeting` 仅保留兼容 | P2 |
| 任务 / 子任务 | `task_create`, `task_delete`, `task_restore`, `subtask_delete`, `create subtask`, `update subtask`, `大纲导入任务` | 任务与子任务操作 | `app/routers/tasks.py`, `app/routers/subtasks.py` | 否 | 是 | 否 | 部分已是英文，部分仍是旧值 | `task_create`, `task_update`, `task_delete`, `task_restore`, `subtask_*` | `create subtask`, `update subtask`, `大纲导入任务` | P1 |
| 确认中心 | `保存确认修改`, `确认写入业务数据`, `AI确认写入`, `打回提交人补充`, `提交人重新提交`, `提交人撤回`, `标记不入库`, `转交统筹人给意见`, `统筹人反馈意见`, `上报企业教练决策`, `企业教练批示`, `标记需人工处理`, `确认成果入库`, `退回成果`, `撤回成果提交`, `提交成果审核` | 提交/确认/流转动作 | `app/routers/confirmations.py`, `app/routers/achievement_submissions.py` | 否 | 是 | 否 | 建议改成英文 stable code | `confirmation_*`, `submission_*`, `coordinator_*`, `coach_*` | 所有中文动作名都应作为兼容旧值保留一段时间 | P1 |
| 问题 | `新建问题`, `修改问题`, `删除问题`, `更新问题状态`, `标记已解决`, `关闭问题`, `指派协助人`, `上报企业教练决策` | 问题流转动作 | `app/routers/issues.py` | 否 | 是 | 否 | 建议改成英文 stable code | `issue_create`, `issue_update`, `issue_delete`, `issue_resolve`, `issue_close`, `issue_assign`, `issue_escalate` | 中文动作名保留兼容 | P1 |
| 成果 | `新建成果`, `修改成果`, `删除成果` | 成果操作 | `app/routers/achievements.py` | 否 | 是 | 否 | 建议改成英文 stable code | `achievement_create`, `achievement_update`, `achievement_delete` | 中文动作名保留兼容 | P2 |
| 批量导入 | `批量导入建项`, `批量导入建任务` | 导入动作 | `app/routers/projects.py` | 否 | 是 | 否 | 建议改成英文 stable code | `batch_import_project`, `batch_import_task` | 中文动作名保留兼容 | P2 |

> 结论：日志 action 不是“能不能运行”的风险点，但它是后续做英文 key 化、统一审计口径、统一检索的重点整治对象。

### 7) 通知 type

| 类别 | 当前值 | 中文含义 | 出现位置 | 是否参与后端判断 | 是否写入数据库 | 是否暴露给前端 | 是否建议改成英文 key | 建议标准 key | 兼容别名建议 | 风险等级 |
|---|---|---|---|---|---|---|---|---|---|---|
| 通知 type | `submission_pending` | 提交待处理 | `app/routers/updates.py`, `app/routers/confirmations.py`, `app/routers/projects.py` | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `submission_confirmed` | 提交已确认 | 同上 | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `submission_rejected` | 提交被打回 | 同上 | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `submission_resubmitted` | 提交人重新提交 | 同上 | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `submission_assigned` | 分配给责任人 | 同上 | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `coordinator_feedback` | 统筹人反馈 | 同上 | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `escalate_ceo` | 上报企业教练决策 | 同上 | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P1 |
| 通知 type | `ceo_decided` | 企业教练已批示 | 同上 | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P1 |
| 通知 type | `issue_reported` | 问题已上报 | `app/routers/issues.py` | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `issue_resolved` | 问题已解决 | 同上 | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `issue_closed` | 问题已关闭 | 同上 | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `issue_needs_decision` | 问题需要决策 | 同上 | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `achievement_confirmed` | 成果已确认 | `app/routers/achievement_submissions.py` | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `achievement_rejected` | 成果被退回 | 同上 | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `meeting_published` | 会议已发布 | `app/routers/meetings.py` | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `meeting_action` | 会议动作提醒 | 同上 | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `project_dispatch` | 项目已派发 | `app/routers/projects.py` | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `project_returned` | 项目已退回 | 同上 | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `project_kickoff` | 项目已启动 / 立项通过 | 同上 | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `subtask_assigned` | 子任务分配 | `app/routers/subtasks.py` | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |
| 通知 type | `subtask_completed` | 子任务完成 | 同上 | 是 | 是 | 是 | 已是英文 key | 保持现状 | 无 | P2 |

> 说明：通知 `title/body` 只是展示文案，可以继续保留中文，不需要英文化；真正需要统一的是 `type` 这个稳定 key。

### 8) 其他模型 / 流程状态（补充盘点）

| 类别 | 当前值 | 中文含义 | 出现位置 | 是否参与后端判断 | 是否写入数据库 | 是否暴露给前端 | 是否建议改成英文 key | 建议标准 key | 兼容别名建议 | 风险等级 |
|---|---|---|---|---|---|---|---|---|---|---|
| 会议发布状态 | `draft` / `published` / `returned` | 会议草稿 / 已发布 / 已退回 | `app/models.py`, `app/routers/meetings.py` | 是 | 是 | 是 | 已是英文 key | 保持现状 | 保持现状 | P2 |
| 子任务草稿状态 | `pending` / `approved` / `rejected` | 待审 / 已审 / 拒绝 | `app/models.py`, `app/routers/subtask_drafts.py` | 是 | 是 | 是 | 已是英文 key | 保持现状 | 保持现状 | P2 |
| 成员变更请求状态 | `pending` / `approved` / `rejected` | 待处理 / 已通过 / 已拒绝 | `app/models.py`, `app/routers/projects.py` | 是 | 是 | 是 | 已是英文 key | 保持现状 | 保持现状 | P2 |
| 账号状态 | `active` / `disabled` | 启用 / 禁用 | `app/models.py`, `app/routers/accounts.py` | 是 | 是 | 是 | 已是英文 key | 保持现状 | 保持现状 | P2 |
| `ProjectCreatePayload.status` 默认值 | `active`（历史默认） | 与当前项目生命周期默认值不一致 | `app/schemas.py` | 是 | 否（请求体默认，不是 DB 默认） | 是 | 已是英文 key，但默认值需要对齐 | `draft` | 与 `Project` ORM 默认值、创建流程对齐 | P1 |

### 9) AI 提示词里的中文

| 类别 | 当前值 | 中文含义 | 出现位置 | 是否参与后端判断 | 是否写入数据库 | 是否暴露给前端 | 是否建议改成英文 key | 建议标准 key | 兼容别名建议 | 风险等级 |
|---|---|---|---|---|---|---|---|---|---|---|
| AI 提示词 | 中文自然语言 prompt / 说明文 | 给 LLM 的任务说明 | `app/routers/meetings.py`, `app/routers/confirmations.py` 等 | 否（应只作为提示语） | 否 | 否 | 不需要 | 保持中文 | 不适用 | P2 |

> 结论：AI 提示词可以继续中文，但不能参与状态判断、权限判断或数据库 key 比较。

## 二、迁移建议

### A. 立即应修

这些点不是“本轮要改”，而是“后续必须优先治理”的事实风险：

1. `ProjectCreatePayload.status = "active"` 与当前 `Project` ORM 默认值 `draft / False` 不一致。
2. `WAITING_CEO_DECISION` 仍是 legacy 命名，业务语义已明确为“等待项目企业教练决策”。
3. `待CEO决策` / `pending_ceo_decision` / `ceo_decided` 这组确认中心状态与“project coach”语义之间存在历史命名偏差。
4. `crud.log.action` 里仍有大量中文 action code，尤其集中在确认中心、问题、成果、子任务。
5. `source_type` 的取值非常混杂，且部分值会进入 extractor / workflow 分支，不适合直接做粗暴替换。

### B. 兼容保留

这些值可以继续保留旧数据，后续用 normalize helper 兼容：

- `submission_status.normalize()`
- `issue_flow.normalize_type()` / `normalize_status()`
- `task_status.normalize()`
- `frontend/src/domain/*` 的标签映射
- 会议发布状态、成员变更请求状态、账号状态这类已是英文 key 的值

建议保留的兼容别名包括：

- `pending_ceo_decision`
- `ceo_decided`
- `returned_to_submitter`
- `withdrawn_editable`
- `transferred_to_coordinator`
- `coordinator_feedback_given`
- `已重新提交`
- `已打回`
- `需CEO决策`
- `待CEO决策`
- `完成` / `已完成`
- `暂停` / `已暂停`
- `推进中` / `进行中`

### C. 只展示

这些中文可以保留，不需要本轮英文化：

- 通知 `title` / `body`
- AI prompt 文本
- 前端标签文案
- 用户看到的说明性文本、按钮文案、日志展示文案

## 三、下一轮 N3-B 建议范围

只列建议，不执行：

1. 给 `submission_status`、`issue_flow`、`task_status`、`source_type` 补统一的 normalize/helper 层。
2. 把 `ProjectCreatePayload.status` 的默认值与 `Project` ORM 默认值统一起来，避免请求层和模型层语义分裂。
3. 逐步把中文 `crud.log.action` 迁移到稳定英文 key，并保留旧值兼容读取。
4. 盘点 `source_type` 的所有业务分支，确认哪些是展示值，哪些是真正影响流程的判断值。
5. 统一前端标签映射的 key 命名，避免“后端中文 canonical、前端英文 key、老数据别名”三套口径同时存在。

## 四、明确结论

### 当前最危险的值

1. `ProjectCreatePayload.status = "active"`：和当前项目创建默认语义不一致，是最直接的默认值风险。
2. `待CEO决策` / `pending_ceo_decision` / `WAITING_CEO_DECISION`：这是最容易继续污染项目企业教练语义的地方。
3. `crud.log.action` 中的中文动作名：已经能跑，但审计和检索口径不统一。
4. `source_type`：部分值会影响提取与流转逻辑，不能简单按展示字段处理。

### 可以以后再迁移的值

- `result_type`（已经是英文 key，最稳）
- `notification type`（已经是英文 key）
- 会议发布状态、成员变更请求状态、账号状态（已经是英文 key）
- 项目生命周期状态本身（已是英文 key，但要维持 `draft / active / archived` 的语义）

### 可以保留的中文

- 展示文案
- 通知标题/正文
- AI 提示词
- 前端标签
- 历史别名，只要走 normalize 兼容层

### 是否建议下一轮开始做 normalize helper

建议。  
尤其是确认中心、问题流转、任务状态、`source_type`、以及 `crud.log.action` 这几组值，已经具备“要么统一 key、要么统一 normalize”的条件了。下一轮应优先做兼容式 normalize，而不是直接批量替换历史数据。
