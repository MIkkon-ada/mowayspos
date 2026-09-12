# 会议变更集评审与执行工作流边界设计

## 目标

将会议变更集的读取、人工编辑和已审核变更执行，从 `app/routers/meetings.py` 移到独立的应用服务，同时保持既有 HTTP 路径、状态码、响应载荷、权限规则、审计记录和事务语义不变。

本次只治理常规会议的三条接口：

- `GET /api/meetings/{row_id}/change-set`
- `PATCH /api/meetings/{row_id}/change-set/proposals/{proposal_id}`
- `POST /api/meetings/{row_id}/change-set/execute`

项目文档会议的发布/退回/执行复核流程（`POST /{meeting_id}/review`）以及变更集生成、AI 解析、文档存储不属于本次范围。

## 当前边界与问题

`meeting_change_set.py` 已经是明确的领域规则服务：它验证提案、校验冻结快照和实时目标、标记冲突、领取并发执行权、写回工作流实体，并且阻止已结束项目的业务写入。

但 `meetings.py` 仍在三个接口中混合了以下应用层职责：

- 从会话用户加载会议并判定草稿可见性；
- 以工作流权限区分“评审变更”和“应用变更”；
- 选择普通提案编辑或项目会议谱系编辑；
- 为每个实际执行的提案写入不可缺失的审计记录；
- 提交事务并组装对外响应载荷。

这使路由同时是 HTTP 适配器、授权编排器、事务边界和审计协调器。若继续在路由中维护，后续新增变更动作或权限规则会使 `meetings.py` 的高风险写入路径继续扩大。

## 方案选择

比较过三种方案：

1. 把所有逻辑继续留在路由中，只增加测试。风险最低，但不能缩小路由职责，不满足架构治理目标。
2. 把权限、审计和载荷函数塞进 `meeting_change_set.py`。文件数量少，但会把应用协调、HTTP 权限语义和底层实体规则重新耦合。
3. 新增 `meeting_change_set_review_workflow.py` 作为应用服务，复用现有领域服务。推荐此方案：职责单一、能保持接口兼容，也不会令底层规则服务反向依赖路由。

选择方案 3。

## 架构

新增的 `app/services/meeting_change_set_review_workflow.py` 公开三个命令：

- `get_meeting_change_set(row_id, current_user, db)`
- `patch_meeting_change_proposal(row_id, proposal_id, payload, current_user, db)`
- `execute_meeting_change_set(row_id, payload, current_user, db)`

服务内部拥有以下私有协作能力：

- 安全 JSON 反序列化和稳定的 proposal/change-set 响应载荷组装；
- 按会议读取权限加载会议，保持草稿、项目访问、全局技术管理员/CEO 的现有规则；
- 按变更集归属加载提案，避免跨会议编辑；
- 用 `A_MEETING_REVIEW_CHANGES` 保护编辑，用 `A_MEETING_APPLY_CHANGES` 保护执行；
- 对谱系提案调用 `edit_project_meeting_lineage_proposal`，对普通提案调用 `edit_meeting_change_proposal`；
- 调用既有 `execute_meeting_change_set` 后，逐条写入 `meeting_change_execute` 审计，并在同一事务中提交。

路由仅保留装饰器、请求依赖和一次服务调用。它不得再直接查询 `MeetingChangeSet` 或 `MeetingChangeProposal`，不得自行提交本范围内事务。

## 数据流与事务

### 读取

服务认证用户后加载可读会议，再按 `meeting_id` 查找变更集。不存在会议或变更集时，分别保持 `404`。返回的 proposal 载荷字段与当前完全一致，包括 `target`、`before`、`proposed`、`validation`、`execution_status`、`lineage` 与仅冲突时展示的 `conflict_reason`。

### 编辑

服务先验证会议、变更集和提案属于同一条路径。含 `lineage_json` 的项目会议提案必须通过 `A_MEETING_REVIEW_CHANGES`，并使用谱系编辑器保留冻结基线与人工编辑历史；无谱系提案使用通用编辑器重新验证会议证据。服务只在编辑成功后提交一次并刷新提案。

### 执行

服务先执行 `A_MEETING_APPLY_CHANGES` 工作流权限校验，再调用既有领域服务。领域服务仍负责 owner 角色、项目关闭冻结、空选择、重复 ID、待执行状态、重新验证、冲突、并发领取和实体写回。

领域服务返回的每一条已执行提案均须产生一条 `OperationLog`：动作 `meeting_change_execute`、目标 `meeting_change_proposal`、项目 ID、执行前的 `before/proposed/evidence` 和执行后的 `result_target_id/execution_status`。日志与实体写回在同一个 `db.commit()` 中提交；任何异常均不产生部分审计或部分写回。

## 依赖方向

`meeting_change_set_review_workflow.py` 可依赖 models、crud、permissions、project resolution、workflow permissions 和 `meeting_change_set.py`，但不得导入 `app.routers.meetings`。为避免循环依赖，响应载荷和会议读取辅助函数应在新工作流服务内实现，而不是从路由复用。

`meeting_change_set.py` 保持领域层：不得导入新工作流服务、FastAPI 路由或 HTTP 请求对象。

## 错误与兼容性

- 不增加端点、迁移、数据库列或前端协议字段。
- 保留当前 `403`、`404`、`409`、`422` 的具体判定与错误文本。
- 无变更集、跨会议 proposal、不可见草稿、没有评审权限、没有应用权限、冻结项目、被阻塞/已领取/冲突提案均必须拒绝且不写入业务实体。
- 空 `proposal_ids` 仍返回当前变更集载荷，不生成审计记录，不改变状态。

## 验证策略

先用直接服务测试固定应用边界，再复用端点集成测试固定 HTTP 契约。

- 服务测试覆盖：正常编辑、谱系编辑分流、跨会议提案 `404`、编辑与执行权限、冻结项目、空选择、逐条审计和单次提交后的响应载荷。
- 既有 `test_meeting_change_set_writeback.py` 覆盖四种变更执行、重验证、批量原子性、父任务同步与审计。
- 既有 `test_project_meeting_review_writeback.py` 覆盖项目会议谱系和项目文档会议独立复核流未被影响。
- 完成后运行会议相关聚焦测试、完整后端 pytest、前端完整测试和生产构建。

## 非目标

- 不重写 `meeting_change_set.py` 的校验、锁定或写回实现。
- 不迁移 `POST /{meeting_id}/review` 的项目文档会议流程。
- 不改变任何角色、会议可见性或项目生命周期规则。
- 不做 AI 提示词、前端 UI 或性能优化。
