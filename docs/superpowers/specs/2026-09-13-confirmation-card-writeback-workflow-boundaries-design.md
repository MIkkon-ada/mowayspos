# 确认中心任务卡最终写回服务边界设计

## 目标

把 `confirm_task_card` 从 `bowei_ai_dashboard/app/routers/confirmations.py`
迁移为服务拥有的单一写回事务，同时保持既有 HTTP 契约、权限、任务卡状态、
Task/SubTask/Achievement/Issue 写入、审计与提交结果不变。

该项工作承接已完成的人工审阅服务化。卡片退回、转交、统筹反馈、教练批示与
问题中心转交已在 `confirmation_review_workflow.py` 中完成；本阶段只处理负责人对
一张可操作任务卡作最终确认并写入业务实体的路径。

## 已确认现状

`confirm_task_card` 当前在 Router 内依次执行：加载提交、项目业务可写检查、
确认中心权限与负责人权限检查、提交状态检查、从持久化 JSON 校验卡片状态、
合并前端编辑结果、解析项目上下文、写入单张任务卡对应的实体、更新卡片状态、
计算提交单完成状态、审计并提交。

`_write_single_task_report` 是该路径的实体写入核心，覆盖两种行为：

- `suggest_new_subtask`：在指定重点工作下创建关键任务，并按开关写入成果；
- 子任务进展或完成：校验关联、更新子任务进展/状态与父任务状态，并按开关写入
  Achievement 与 Issue。

它的安全不变量已经由现有测试覆盖：关联子任务必须属于目标项目与重点工作；
`pending_ceo_decision` 或 `transferred_to_coordinator` 不能被前端
`human_result` 覆盖绕过；只确认目标卡片；所有卡片确认后提交单才进入 confirmed。

## 方案比较

### 方案 A：仅把 `_write_single_task_report` 移到通用辅助模块

改动较小，但 Router 仍编排身份、JSON 防绕过、状态、审计与事务，写回边界依旧不
清晰，不能满足本轮“复杂命令由服务拥有”的目标。

### 方案 B：建立专用的任务卡写回工作流服务（采用）

新建 `services/confirmation_card_writeback_workflow.py`，公开一个
`confirm_task_card` 命令。该服务复用已验证的确认审阅访问辅助函数，自己拥有：
持久化卡片状态校验、编辑结果合并、项目解析、实体写入、任务卡/提交单状态、审计
和一次 `db.commit()`。Router 仅将 ID、Pydantic 请求、当前用户和 Session 转交。

为避免服务反向依赖 Router，卡片 JSON 合并、目标卡读取/状态标记、标题与所有卡片
完成判断等纯逻辑应由服务模块本地拥有或从确认审阅服务导出。写回服务可依赖
`services.workflow`、`services.project_resolution`、`services.notify`、
`routers.subtasks._sync_parent_task_status` 以及既有 domain 常量，但不能导入
`routers.confirmations`。

### 方案 C：同时迁移提交单级 `confirm`

可最大幅度缩减 Router，但提交单确认包含多种写入模式、历史兼容与跨实体去重，远大
于卡片确认的风险范围。与本次任务卡专用边界混合会降低可回归性，暂不采用。

## 服务契约与事务顺序

服务公开下列入口：

```python
def confirm_task_card(
    *,
    submission_id: int,
    card_index: int,
    payload: schemas.ConfirmRequest,
    current_user: str,
    db: Session,
) -> dict: ...
```

成功时返回既有形状：

```python
{"ok": True, "submission": crud.to_dict(row)}
```

事务顺序固定为：

`加载提交 → 项目可写 → 确认中心/负责人权限 → 提交状态 → 持久化卡片可操作状态 →
合并编辑结果且保留工作流字段 → 解析项目 → 写入单卡实体 → 标记卡片 confirmed →
计算提交单状态 → 审计 confirmation_card_approve → 一次提交 → 响应`

任何权限、状态、关联校验或实体写入异常都发生在提交之前；服务不得提前提交，也不
得通知或修改其他卡片。所有卡片确认时，保持 `confirmed_by`、`confirmed_at` 与
`SS.S_CONFIRMED` 的既有设置；否则保持 `SS.S_PENDING_OWNER`。

## 写回不变量

- 端点仍是 `POST /api/confirmations/{submission_id}/cards/{card_index}/confirm`，请求、
  响应、错误文本和状态码保持兼容；
- 只接受 `SS.OWNER_ACTIONABLE` 提交，并复用确认中心、项目业务可写和 owner-style
  权限规则；
- 以数据库的任务卡工作流字段为准。请求中的 `human_result` 只能编辑业务内容，不能
  删除、伪造或覆盖 `confirmation_*`、`coordinator_*`、`ceo_*` 字段，也不能改变卡片
  数量；
- `suggest_new_subtask` 继续写入父重点工作、来源提交、成果及关联子任务；
- 子任务进展/完成继续验证项目和 Task/SubTask 谱系，保留 `related_task_id` 指向父
  Task 而非 SubTask，并写入成果/问题的 `related_subtask_id`；
- 审计动作保持 `confirmation_card_approve`，`after` 保持 `card_index` 与 `task_id`；
- 成功路径恰好一次 `db.commit()`，不新增数据库 schema、迁移、API 或前端改动。

## 测试与验收

新增直接服务测试，以两张卡片的 SQLite 提交覆盖：只写入目标卡、非目标卡不变、
正常进展/完成的 Task/SubTask/Achievement/Issue 谱系、`suggest_new_subtask`、所有
卡片确认后的提交单状态、冻结项目与越权拒绝、以及 `human_result` 对待教练卡的
绕过拒绝。保留并运行既有卡片教练/统筹、相关子任务写回、公司 CEO 负责人权限和
确认审计回归。

验收不仅要求 Router 成为单个服务调用，还要求写回服务不导入
`app.routers.confirmations`，全量后端、前端测试和生产构建均通过。

## 非目标

- 不迁移提交单级 `confirm`；
- 不改变既有任务、关键任务、成果、问题的数据模型、去重策略或通知；
- 不调整确认中心 UI、权限策略、数据库 schema、Alembic 或异步流程。
