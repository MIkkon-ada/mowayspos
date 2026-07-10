# operation log action code 审计

审计时间：2026-07-10

## 审计背景

本轮只审计 `operation_logs.action` / `crud.log(...)` 的使用情况，为后续统一英文 action code 做准备。

本轮没有修改业务代码，没有迁移历史日志，没有调整接口、权限、前端或数据库结构。

## 机制现状

- `crud.log(...)` 写入 `models.OperationLog.action`。
- `OperationLog.action` 是 `String(80)`，无数据库枚举约束。
- `/api/logs/global?action=...` 使用 `OperationLog.action.contains(action)` 做日志检索。
- 当前没有发现权限、流程状态、业务统计直接依赖某个 action 精确值。

因此，本轮发现的问题主要影响审计检索、统计口径和后续维护一致性；默认不评为 P0。

## 总览表

| 模块 | 文件 | 当前 action 写法 | 英文/中文/模糊英文 | 是否写入 operation_logs | 是否参与查询/筛选/统计 | 是否建议修复 | 建议标准 action code | 风险等级 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| operation log 基础设施 | `app/crud.py`, `app/models.py`, `app/routers/logs.py` | `action` 原样写入；全局日志按 `contains(action)` 查询 | 混合承载 | 是 | 是，日志检索 | 建议后续兼容读取 | 不适用 | P2 |
| meetings | `app/routers/meetings.py` | `meeting_create`, `meeting_update`, `meeting_publish`, `meeting_return`, `meeting_save_draft`, `meeting_delete` | 英文稳定 code | 是 | 仅日志检索 | 否 | 保持现状 | P2 |
| tasks | `app/routers/tasks.py` | `task_create`, `task_update`, `task_close`, `task_delete`, `task_restore`；另有 `大纲导入任务` | 大多英文，少量中文 | 是 | 仅日志/任务日志读取 | 是 | `task_outline_import` | P2 |
| subtasks | `app/routers/subtasks.py` | `create subtask`, `update subtask`, `update subtask status`, `delete subtask`, `restore subtask`, `reopen task for new subtask`；另有同步父任务状态中文 action | 模糊英文/中文 | 是 | 仅日志读取 | 是 | `subtask_create`, `subtask_update`, `subtask_update_status`, `subtask_delete`, `subtask_restore`, `task_reopen_for_subtask`, `task_sync_status_from_subtasks` | P2 |
| confirmations | `app/routers/confirmations.py` | `保存确认修改`, `AI确认写入`, `确认写入业务数据`, `打回提交人补充`, `提交人重新提交`, `提交人撤回`, `标记不入库`, `转交统筹人给意见`, `统筹人反馈意见`, `上报企业教练决策`, `企业教练批示`, `标记需人工处理`, `指定责任人：xxx`；另有 `confirm task card`, `reject task card`, `transfer task card to coordinator`, `escalate task card to ceo` | 中文/模糊英文/动态字符串 | 是 | 仅日志检索 | 是 | `submission_save_edit`, `submission_ai_write_task`, `submission_confirm_write`, `submission_return_to_submitter`, `submission_resubmit`, `submission_withdraw`, `submission_reject_final`, `submission_transfer_to_coordinator`, `submission_coordinator_feedback`, `submission_escalate_to_coach`, `submission_coach_decision`, `submission_mark_unrecognized`, `submission_assign_owner`, `submission_card_confirm`, `submission_card_reject`, `submission_card_transfer_to_coordinator`, `submission_card_escalate_to_coach` | P1 |
| issues | `app/routers/issues.py` | `新建问题`, `修改问题`, `删除问题`, `更新问题状态`, `标记已解决`, `关闭问题`, `指派协助人`, `上报企业教练决策` | 中文 | 是 | 仅日志检索 | 是 | `issue_create`, `issue_update`, `issue_delete`, `issue_update_status`, `issue_resolve`, `issue_close`, `issue_assign_helper`, `issue_escalate_to_coach` | P2 |
| achievements | `app/routers/achievements.py` | `新建成果`, `修改成果`, `删除成果` | 中文 | 是 | 仅日志检索 | 是 | `achievement_create`, `achievement_update`, `achievement_delete` | P2 |
| achievement submissions | `app/routers/achievement_submissions.py` | `提交成果审核`, `确认成果入库`, `退回成果`, `撤回成果提交` | 中文 | 是 | 仅日志检索 | 是 | `achievement_submission_create`, `achievement_submission_approve`, `achievement_submission_return`, `achievement_submission_withdraw` | P2 |
| projects lifecycle | `app/routers/projects.py` | `create_project`, `update_project`, `archive_project`, `dispatch_project`, `owner_submit_project`, `return_project`, `approve_project`, `kickoff_project` | 英文稳定 code | 是 | 仅日志检索 | 小幅建议 | 可统一为 `project_create`, `project_update`, `project_archive`, `project_dispatch`, `project_submit_for_review`, `project_return`, `project_approve`, `project_kickoff` | P2 |
| projects batch import | `app/routers/projects.py` | `批量导入建项`, `批量导入建任务` | 中文 | 是 | 仅日志检索 | 是 | `project_batch_import_create_project`, `project_batch_import_create_task` | P2 |
| project members | `app/routers/projects.py` | `add_project_member`, `update_project_member`, `remove_project_member`, `approve_member_change_auto`, `create_member_change_request`, `approve_member_change`, `reject_member_change` | 英文稳定 code | 是 | 仅日志检索 | 小幅建议 | 可保留，或统一为 `project_member_add`, `project_member_update`, `project_member_remove`, `member_change_request_create`, `member_change_request_approve`, `member_change_request_reject` | P2 |
| people | `app/routers/people.py` | `create`, `update`, `delete`, `batch_create` 写到 `person`；另有 `create/update/delete` 写到 `project` | 模糊英文 | 是 | 仅日志检索 | 是 | `person_create`, `person_update`, `person_delete`, `person_batch_create`; 另核实 project 写入是否应迁到 projects 模块命名 | P2 |
| accounts | `app/routers/accounts.py` | `create`, `reset_password`, `update_status` | 模糊英文/部分合格 | 是 | 仅日志检索 | 是 | `account_create`, `account_reset_password`, `account_update_status` | P2 |
| updates | `app/routers/updates.py` | 未发现 `crud.log(...)` | 无 | 否 | 否 | 否 | 不适用 | 无需处理 |
| dashboard | `app/routers/dashboard.py` | 未发现 `crud.log(...)` | 无 | 否 | 否 | 否 | 不适用 | 无需处理 |
| settings | `app/routers/platform_settings.py`, settings 相关 | 未发现 `crud.log(...)` | 无 | 否 | 否 | 可后续视需要补审计日志 | `platform_settings_update` | P2 |

## 建议 action code 命名规范

建议统一使用：

- 小写英文
- 下划线分隔
- `domain_entity + verb` 或 `domain_entity + workflow_action`
- 不包含用户输入、姓名、标题等动态内容
- 展示文案放在前端或映射表，不放在 action code

建议样例：

- `project_create`
- `project_dispatch`
- `project_submit_for_review`
- `project_approve`
- `project_return`
- `task_create`
- `task_update`
- `subtask_create`
- `subtask_update_status`
- `submission_confirm`
- `submission_return`
- `submission_escalate_to_coach`
- `submission_coach_decision`
- `issue_create`
- `issue_escalate_to_coach`
- `issue_coach_decision`
- `achievement_create`
- `achievement_submission_approve`
- `meeting_create`

## 分模块结论

### projects.py

- 存在中文 action：批量导入相关。
- 存在命名不完全统一的英文 action：`create_project` 与建议的 `project_create` 风格相反，但可读性尚可。
- 建议下一轮小步修复批量导入中文 action，生命周期 action 可后续统一。
- 不影响前端流程；会影响历史日志检索口径。

### tasks.py

- 大多数 action 已是稳定英文 code。
- 残留中文 action：`大纲导入任务`。
- 建议下一轮修为 `task_outline_import`。
- 不影响业务流程。

### subtasks.py

- 存在中文 action：同步父任务状态。
- 存在模糊英文 action：`create subtask`, `update subtask`, `delete subtask` 等使用空格短语。
- 建议下一轮统一为 `subtask_*` 和 `task_sync_*`。
- 不影响业务流程，但会让日志查询和统计不稳定。

### updates.py

- 未发现 `crud.log(...)`。
- 本轮无需修复。

### confirmations.py

- 中文 action 最集中，且包含动态 action：`指定责任人：{payload.assignee}`。
- 也存在空格英文短语：`confirm task card`, `reject task card`。
- 建议作为后续优先修复模块，因为确认中心流程多、审计价值高。
- 当前未发现 action 参与权限或状态判断，因此不评 P0。

### achievements.py

- 存在中文 action：新建、修改、删除成果。
- 建议统一为 `achievement_create/update/delete`。
- 不影响业务流程。

### achievement_submissions.py

- 存在中文 action：提交审核、确认入库、退回、撤回。
- 建议统一为 `achievement_submission_*`。
- 不影响业务流程。

### issues.py

- 存在中文 action，覆盖创建、修改、删除、状态更新、解决、关闭、指派、上报企业教练。
- 建议统一为 `issue_*`。
- 当前没有发现 action 参与问题流转判断；问题流转依赖 status / role / project 权限。

### meetings.py

- 已基本合格，使用稳定英文 code。
- 不建议本轮后续修复。

### accounts / people / settings

- accounts / people 存在 `create`, `update`, `delete` 这种模糊英文 action。
- settings 当前未发现日志写入。
- 建议后续统一为 `account_*`、`person_*`，settings 如需审计可补 `platform_settings_update`。

## 总结结论

结论：B. 发现 P1/P2 中文 action，建议后续小步收口。

最高风险点：

- P1：`confirmations.py` 中大量中文 action、空格英文 action 和动态 action，影响确认中心审计检索和后续统计口径。
- P2：`issues.py`、`achievements.py`、`achievement_submissions.py`、`subtasks.py`、`people.py` 等模块存在中文或模糊英文 action。

没有发现 P0：

- 没有发现 operation log action 参与权限判断。
- 没有发现 operation log action 参与核心业务流转。
- 仅发现 `/api/logs/global` 支持按 action 字符串 contains 查询，因此 action 不统一会影响审计搜索，但不会阻断核心流程。
