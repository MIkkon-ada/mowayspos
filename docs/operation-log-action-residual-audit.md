# Operation Log Action Residual Audit

## 1. 审计背景

本轮是 N3-B3-B/C/D/E 之后的 OperationLog.action / `crud.log` action 残留复查，只审计，不修复业务代码。

已完成的小步标准化：

- `e285050 fix: standardize confirmation log actions`
- `f86e464 fix: standardize subtask log actions`
- `0e58bc1 fix: standardize issue log actions`
- `51b6ec1 fix: standardize achievement log actions`

本轮检查范围：

- `bowei_ai_dashboard/app/**/*.py`
- `bowei_ai_dashboard/tests/**/*.py`
- `docs/operation-log-action-audit.md`
- 已新增的日志 action 静态测试文件

已执行搜索：

- `git grep -n "crud.log" bowei_ai_dashboard/app bowei_ai_dashboard/tests`
- `git grep -n "action=" bowei_ai_dashboard/app bowei_ai_dashboard/tests`
- `git grep -n -E 'action=.*[一-龥]' bowei_ai_dashboard/app bowei_ai_dashboard/tests`
- `git grep -n -E 'action=f|action = f' bowei_ai_dashboard/app bowei_ai_dashboard/tests`
- `git grep -n -E 'action="[^"]* [^"]*"' bowei_ai_dashboard/app bowei_ai_dashboard/tests`
- `git grep -n -E 'action="(create|update|delete|restore|approve|return|confirm|submit)"' bowei_ai_dashboard/app bowei_ai_dashboard/tests`

补充说明：上面的 grep 规则只能发现 `action=` 关键字形式；当前大量 `crud.log` action 是第 3 个位置参数。因此本轮同时使用 AST 提取所有真实 `crud.log(...)` 调用的 action 参数，避免漏判。

## 2. 已完成模块复查

| 模块 | 中文 action 残留 | 空格 action 残留 | f-string / 动态拼接残留 | 结论 |
|---|---:|---:|---:|---|
| `confirmations.py` | 无 | 无 | 无 | 已合格，均为静态英文稳定 code |
| `subtasks.py` | 无 | 无 | 无 | 已合格，均为静态英文稳定 code |
| `issues.py` | 无 | 无 | 无 | 已合格，均为静态英文稳定 code |
| `achievements.py` | 无 | 无 | 无 | 已合格，均为静态英文稳定 code |
| `achievement_submissions.py` | 无 | 无 | 无 | 已合格，均为静态英文稳定 code |

## 3. 全量残留清单

| 文件 | 行/位置 | 当前 action | 问题类型 | 是否写入 operation_logs | 是否参与业务判断 | 风险等级 | 建议标准 action code | 建议下一轮是否修 |
|---|---:|---|---|---|---|---|---|---|
| `app/routers/accounts.py` | 170 | `create` | 模糊英文 | 是 | 否 | P2 | `account_create` | 是，适合小步修 |
| `app/routers/accounts.py` | 199 | `reset_password` | 模糊英文 | 是 | 否 | P2 | `account_reset_password` | 是，适合小步修 |
| `app/routers/accounts.py` | 221 | `update_status` | 模糊英文 | 是 | 否 | P2 | `account_update_status` | 是，适合小步修 |
| `app/routers/people.py` | 205 | `create` | 模糊英文 | 是 | 否 | P2 | `project_create_legacy_people_router` 或后续按上下文确认 | 是，但需先确认该 router 中 project 语义 |
| `app/routers/people.py` | 241 | `update` | 模糊英文 | 是 | 否 | P2 | `project_update_legacy_people_router` 或后续按上下文确认 | 是，但需先确认该 router 中 project 语义 |
| `app/routers/people.py` | 267 | `delete` | 模糊英文 | 是 | 否 | P2 | `project_delete_legacy_people_router` 或后续按上下文确认 | 是，但需先确认该 router 中 project 语义 |
| `app/routers/people.py` | 302 | `batch_create` | 模糊英文 | 是 | 否 | P2 | `person_batch_create` | 是，适合小步修 |
| `app/routers/people.py` | 340 | `create` | 模糊英文 | 是 | 否 | P2 | `person_create` | 是，适合小步修 |
| `app/routers/people.py` | 394 | `update` | 模糊英文 | 是 | 否 | P2 | `person_update` | 是，适合小步修 |
| `app/routers/people.py` | 419 | `delete` | 模糊英文 | 是 | 否 | P2 | `person_delete` | 是，适合小步修 |
| `app/routers/projects.py` | 730 | `create_project` | 无问题，但命名顺序与新规范不完全一致 | 是 | 否 | 无需处理 | 可选后续统一为 `project_create` | 否，非优先 |
| `app/routers/projects.py` | 784 | `批量导入建项` | 中文 | 是 | 否 | P1 | `project_batch_import` | 是，建议优先 |
| `app/routers/projects.py` | 806 | `批量导入建任务` | 中文 | 是 | 否 | P1 | `task_batch_import_from_project_outline` | 是，建议与 projects.py 一起修 |
| `app/routers/projects.py` | 895 | `add_project_member` | 无问题 | 是 | 否 | 无需处理 | 可选后续统一为 `project_member_add` | 否 |
| `app/routers/projects.py` | 937 | `update_project_member` | 无问题 | 是 | 否 | 无需处理 | 可选后续统一为 `project_member_update` | 否 |
| `app/routers/projects.py` | 969 | `remove_project_member` | 无问题 | 是 | 否 | 无需处理 | 可选后续统一为 `project_member_remove` | 否 |
| `app/routers/projects.py` | 1106 | `approve_member_change_auto` | 无问题 | 是 | 否 | 无需处理 | 可选后续统一为 `project_member_change_auto_approve` | 否 |
| `app/routers/projects.py` | 1108 | `create_member_change_request` | 无问题 | 是 | 否 | 无需处理 | 可选后续统一为 `project_member_change_request_create` | 否 |
| `app/routers/projects.py` | 1189 | `approve_member_change` | 无问题 | 是 | 否 | 无需处理 | 可选后续统一为 `project_member_change_approve` | 否 |
| `app/routers/projects.py` | 1219 | `reject_member_change` | 无问题 | 是 | 否 | 无需处理 | 可选后续统一为 `project_member_change_reject` | 否 |
| `app/routers/projects.py` | 1292 | `update_project` | 无问题 | 是 | 否 | 无需处理 | 可选后续统一为 `project_update` | 否 |
| `app/routers/projects.py` | 1320 | `archive_project` | 无问题 | 是 | 否 | 无需处理 | 可选后续统一为 `project_archive` | 否 |
| `app/routers/projects.py` | 1375 | `dispatch_project` | 无问题 | 是 | 否 | 无需处理 | 可选后续统一为 `project_dispatch` | 否 |
| `app/routers/projects.py` | 1412 | `owner_submit_project` | 无问题 | 是 | 否 | 无需处理 | 可选后续统一为 `project_owner_submit` | 否 |
| `app/routers/projects.py` | 1463 | `return_project` | 无问题 | 是 | 否 | 无需处理 | 可选后续统一为 `project_return` | 否 |
| `app/routers/projects.py` | 1517 | `approve_project` | 无问题 | 是 | 否 | 无需处理 | 可选后续统一为 `project_approve` | 否 |
| `app/routers/projects.py` | 1561 | `kickoff_project` | 无问题 | 是 | 否 | 无需处理 | 可选后续统一为 `project_kickoff` | 否 |
| `app/routers/tasks.py` | 285 | `task_create` | 无问题 | 是 | 否 | 无需处理 | `task_create` | 否 |
| `app/routers/tasks.py` | 370 | `action`，本地值为 `task_close` / `task_update` | 本地变量 action | 是 | 否 | P2 | 可保留，或后续静态测试允许白名单变量 | 否，非优先 |
| `app/routers/tasks.py` | 396 | `task_delete` | 无问题 | 是 | 否 | 无需处理 | `task_delete` | 否 |
| `app/routers/tasks.py` | 407 | `subtask_delete` | 无问题 | 是 | 否 | 无需处理 | `subtask_delete` | 否 |
| `app/routers/tasks.py` | 443 | `action`，本地值为 `task_close` / `task_update_status` | 本地变量 action | 是 | 否 | P2 | 可保留，或后续静态测试允许白名单变量 | 否，非优先 |
| `app/routers/tasks.py` | 471 | `task_restore` | 无问题 | 是 | 否 | 无需处理 | `task_restore` | 否 |
| `app/routers/tasks.py` | 487 | `subtask_restore` | 无问题 | 是 | 否 | 无需处理 | `subtask_restore` | 否 |
| `app/routers/tasks.py` | 617 | `大纲导入任务` | 中文 | 是 | 否 | P1 | `task_import_from_outline` | 是，建议优先 |
| `app/routers/meetings.py` | 153 | `meeting_create` | 无问题 | 是 | 否 | 无需处理 | `meeting_create` | 否 |
| `app/routers/meetings.py` | 267 | `meeting_update` | 无问题 | 是 | 否 | 无需处理 | `meeting_update` | 否 |
| `app/routers/meetings.py` | 306 | `action`，本地映射为 `meeting_publish` / `meeting_return` / `meeting_update` | 本地变量 action | 是 | 否 | P2 | 可保留，或后续静态测试允许白名单变量 | 否，非优先 |
| `app/routers/meetings.py` | 366 | `meeting_delete` | 无问题 | 是 | 否 | 无需处理 | `meeting_delete` | 否 |
| `app/crud.py` | 37 | `action=action` | 模型字段写入，不是调用点 action | 是 | 否 | 无需处理 | 不适用 | 否 |
| `app/routers/projects.py` | 1065, 1080 | `action="add"` | 非 `crud.log`，属于 member change request 业务字段 | 否 | 是，业务对象字段 | 无需处理 | 不适用 | 否 |
| `tests/test_*_log_actions.py` | 多处 | 测试断言中的 `action` 文本 | 测试扫描文案 | 否 | 否 | 无需处理 | 不适用 | 否 |

## 4. 下一轮优先级建议

1. **优先修 `tasks.py`**
   - 原因：仍有中文 action：`大纲导入任务`。
   - 风险：P1。当前未发现参与权限、流程状态或核心业务判断，但会影响审计检索和日志统计。
   - 是否适合小步修：适合。只需收口 `tasks.py` 的 `crud.log` action，并补 `tests/test_task_log_actions.py`。
   - 注意：`tasks.py` 里有两个本地变量 `action`，值来自固定英文 code：`task_close` / `task_update` / `task_update_status`。下一轮如加静态测试，需要允许这种本地白名单变量，或把调用处展开成固定分支。

2. **其次修 `projects.py`**
   - 原因：仍有中文 action：`批量导入建项`、`批量导入建任务`。
   - 风险：P1。当前未发现参与业务判断，但项目/任务导入日志是重要审计线索。
   - 是否适合小步修：适合。建议只处理 `projects.py` 中中文 action，不顺手改项目生命周期 action 命名顺序。
   - 建议 code：`project_batch_import`、`task_batch_import_from_project_outline`。

3. **再修 `accounts.py`**
   - 原因：`create`、`reset_password`、`update_status` 模块语义不完整。
   - 风险：P2。影响审计检索一致性，但目标类型已有 `account`。
   - 是否适合小步修：适合。建议新增 `tests/test_account_log_actions.py`。

4. **最后修 `people.py`**
   - 原因：有多处 `create` / `update` / `delete` / `batch_create` 模糊 action。
   - 风险：P2。该文件同时包含 project/person 两类 target，需要先按上下文确认命名，不建议和账号模块混在一轮。
   - 是否适合小步修：适合，但应单独一轮处理。

## 5. 是否发现 action 参与业务判断

未发现 `OperationLog.action` 参与权限、流程状态、核心业务流转判断。

发现的 action 使用方式：

- `app/routers/logs.py` 支持按 `OperationLog.action.contains(action)` 查询日志。
- `app/routers/tasks.py` 的任务日志接口返回 `action` 给前端展示或审计查看。
- `app/routers/projects.py` 中 `action="add"` 是 member change request 的业务字段，不是 `OperationLog.action`，不属于本轮日志 action 标准化对象。

因此，本轮发现的最高风险为 P1；主要影响审计检索、统计一致性和后续规范化，不直接阻断业务流程。

## 6. 明确结论

**B. 仍有 P1/P2 残留，建议继续小步修。**

当前最高风险残留：

- `tasks.py:617`：`大纲导入任务`，中文 action，P1。
- `projects.py:784`：`批量导入建项`，中文 action，P1。
- `projects.py:806`：`批量导入建任务`，中文 action，P1。

可以后续处理：

- `accounts.py` 的模糊英文 action：`create`、`reset_password`、`update_status`。
- `people.py` 的模糊英文 action：`create`、`update`、`delete`、`batch_create`。
- `tasks.py` / `meetings.py` 的本地变量 action：当前值来自稳定英文 code，不是动态用户内容，非优先。
