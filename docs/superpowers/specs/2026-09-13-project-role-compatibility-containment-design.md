# 项目角色历史兼容收口设计

## 目标

保持旧项目以 `owners`、`coordinator`、`collaborators` 字段提供的只读访问不变，但不再让 Router 或通用项目访问服务传播 `allow_legacy` 开关或按旧项目名称计算可见性。历史字段的解析、回退选择和兼容 API 均只存在于 `app.compatibility.project_roles`。

## 已确认问题

`app.compatibility.project_roles` 已正确实现显式、只读的旧角色回退；但 `app.services.project_access` 暴露 `allow_legacy_roles` 和 `allow_legacy`，而 `routers/projects.py` 在列表、详情、成员读取和成员变更读取中直接选择该开关。这使兼容策略从其专用边界扩散到正常业务服务和 HTTP 适配层。

## 选择

保留现有回退行为，不删除旧字段，也不扩大写权限。采用“兼容门面 + 严格核心”方案：

1. `project_access` 只保留严格的成员表授权/可见性，以及一个不携带历史语义的内部解析结果入口；
2. `project_roles` 新增兼容门面，负责构造带旧字段回退的角色解析，调用严格核心，并提供兼容可见项目 ID；
3. `projects` 路由仅调用 compatibility 模块的语义化读取 API，不再出现 `allow_legacy`、旧名称集合或旧字段回退逻辑。

相比立即移除回退，该方案不会让尚未迁移的项目成员失去只读访问；相比保留布尔参数，它把策略选择限制在可审阅的单一目录。

## 行为与边界

- `authorize_project_action` 继续只按 `project_members` 授权；旧记录不得取得任何写权限。
- compatibility 门面仅用于 `A_VIEW`，并保留 `ProjectAccessContext.role_source == "legacy_fields"` 的可观测性。
- 项目列表仍合并成员表可见项目与旧字段命中的项目；归档/草稿过滤和排序保持 Router 当前行为。
- 项目详情、成员列表和成员变更列表继续允许旧字段拥有者读取，但不改动任何写端点。
- 不修改表结构、迁移、API 路径、状态码或前端代码。

## 验收

- 服务模块中不再有 `allow_legacy` 参数或基于 `visible_projects` 的名称回退。
- Router 不再出现 `allow_legacy`；其四个读取点均委托 compatibility 门面。
- 旧字段拥有者可查看项目、成员和成员变更；同一用户仍不能通过严格写操作获得权限。
- 当前成员表角色、公司 CEO、项目草稿可见性与完整后端回归保持通过。
