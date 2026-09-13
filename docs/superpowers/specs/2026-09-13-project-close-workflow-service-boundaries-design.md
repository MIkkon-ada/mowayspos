# 项目结项工作流服务边界设计

## 目标

将项目结束申请的创建、编辑、撤回、审批、退回和读取链路从
`bowei_ai_dashboard/app/routers/projects.py` 提取到专门的服务边界中。提取后保持全部既有 HTTP 路径、响应字段、错误码、锁顺序、审计事件、通知收件人和生命周期转换不变。

这是系统稳定化第二阶段中项目域的下一步：让 Router 只解析 HTTP 输入和返回响应，让结项工作流拥有其业务事务边界。

## 已确认现状

当前 `projects.py` 的 1,670–2,153 行同时承担以下职责：

- 对 `projects` 与 `project_close_requests` 的行锁和请求归属校验；
- 项目动作授权、申请材料验证和结项阻塞项计算；
- `active → pending_close → ended/active` 状态转换；
- 审计前后快照与站内通知；
- 结束申请 DTO 的装配和读模型筛选。

已有 `project_close.py` 提供结项阻塞项计算和业务冻结判定，`project_access.py` 提供项目动作授权；它们是新服务应复用的稳定依赖。现有路由测试已经覆盖允许、拒绝、并发锁、审批、退回、撤回、归档前置条件及通知行为。

## 方案比较

### 方案 A：只移动工具函数

将锁、DTO 和通知工具函数挪到新文件，但命令端点继续在 Router 编排。改动最小，但状态转换、事务提交和授权仍分散在 HTTP 层，无法达到服务边界目标。

### 方案 B：提取完整的结项工作流服务（采用）

新增 `services/project_close_workflow.py`，由它承载查询、命令、锁、授权、材料校验、状态转换、审计、通知和一次性提交。Router 仅把路径参数、Pydantic payload、当前用户和 DB Session 传递给服务。项目物理兼容列的同步通过一个显式 lifecycle writer 依赖注入，保持现有 `status` / `lifecycle_status` / `is_active` 写入行为。

此方案为事务提供单一所有者，并保留现有数据库兼容写入，风险和收益平衡最好。

### 方案 C：重写项目状态机与关闭 API

一次性把项目生命周期、归档、删除和结项 API 全部改为新的领域模型。长期抽象更统一，但会同时改变大量稳定契约，不适合在已恢复绿线的系统中执行。

## 目标边界

新增服务公开六个用例：

- `create_close_request`
- `list_close_requests`
- `get_close_request`
- `update_close_request`
- `cancel_close_request`
- `approve_close_request` 与 `reject_close_request`

服务内部拥有以下私有职责：行锁、请求归属、响应 DTO、材料快照、通知去重和待审核状态一致性检查。它复用 `authorize_project_action`、`evaluate_project_close`、`material_values`、`serialize_residual_items` 与既有通知服务。

服务以 `LifecycleWriter` 协议接受一次回调：`(project, lifecycle_status, *, db, project_id) -> str`。在第一步中 Router 传入其既有的 `_set_project_lifecycle`；这明确隔离了旧物理列的同步策略，后续可单独提取，而不会让关闭服务依赖 Router 模块。

仅读取端的旧项目可见性规则仍位于 Router，因此查询服务以 `view_authorizer(current_user, project, db) -> dict` 注入该规则。服务不会反向导入 Router；命令端继续直接复用 `project_access.authorize_project_action`。

## 数据流和事务

写入路径统一为：

`Router → ProjectCloseWorkflow command → pre-authorization → project/request row lock → material/state validation → mutation/lifecycle write → audit → notifications → one DB commit → response DTO`

任何验证或通知准备错误都发生在 commit 前；调用方继续收到原有异常。服务不执行后台任务，也不吞掉异常。所有成功命令只提交一次，并在提交后刷新申请记录。

读取路径为：

`Router → ProjectCloseWorkflow query → project view authorization → DTO with live blockers/warnings`

这保持前端对实时结项阻塞信息的依赖。

## 兼容性与安全不变量

- 保留七个现有项目结项端点的 URL、HTTP 方法、状态码、错误码和 JSON 字段。
- 仅项目负责人可发起/编辑/撤回自己的申请；企业教练或超级管理员才可审核。
- 只有 `active` 项目可创建申请；申请待审核时项目必须为 `pending_close`；批准后为 `ended`，撤回或退回后恢复 `active`。
- 每条状态变化仍生成原有 `OperationLog.action`，通知仍排除操作者并去重。
- 服务不会处理项目归档或永久删除；这两个独立流程在本次范围外。

## 测试与验收

除现有结项、权限和生命周期测试外，增加边界回归测试，证明 Router 已委托服务、服务持有全部关闭命令、以及生命周期写入回调仍同步三个兼容状态字段。验收需包括：

- 定向项目结项、权限、通知和归档阻塞测试；
- 后端完整 pytest；
- `git diff --check`；
- 前端无需改动，现有前端全量测试与生产构建继续作为交付基线证据。

## 非目标

- 不修改数据库 schema 或 Alembic 迁移；
- 不重命名历史物理列或 API；
- 不改变项目归档、永久删除、成员管理或项目初始化 AI 的职责；
- 不把通知改为异步队列。
