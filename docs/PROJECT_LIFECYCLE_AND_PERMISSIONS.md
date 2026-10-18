# 项目生命周期、权限与字段口径

本文是当前实现口径的核对入口。项目状态以 `Project.status` 和后端生命周期服务为准；操作者是否允许某项动作由项目权限/工作流权限决策器判断，路由还会检查该动作的合法前置状态和数据约束。权限通过不等于状态合法。

代码证据以 `bowei_ai_dashboard/app/domain/project_lifecycle.py`、`project_permissions.py`、`workflow_permissions.py`、`app/routers/projects.py` 与相应测试为准。本文件只描述已能从当前代码和测试证实的行为；未验证的部署数据不作推断。

## 状态与常规迁移

| 状态键 | 界面名称 | 常规含义 | 新流程用途 |
|---|---|---|---|
| `draft` | 草稿 | 公司管理已建项，仍在团队配置和下发前 | 新建项目的默认状态 |
| `dispatched` | 已派发 | 已完成团队配置，等待负责人提交立项资料与工作计划 | 常规前置阶段；`dispatch_project` 只接受 `draft` |
| `pending_review` | 待审核 | 负责人已提交立项资料和工作计划，等待本项目企业教练审核 | 审核通过或退回的唯一正常前置状态 |
| `returned` | 已退回 | 审核退回，负责人可修改并再次提交 | `owner_submit_project_profile` 接受后回到 `pending_review` |
| `active` | 进行中 | 项目正式执行 | 常规审核通过目标；结束申请的唯一正常前置状态 |
| `pending_close` | 结束审核中 | 结束申请待企业教练审核，业务写入冻结 | 取消/退回回到 `active`；批准进入 `ended` |
| `ended` | 已结束 | 结束审核通过，业务写入冻结 | 仅技术管理员可进一步归档 |
| `archived` | 已归档 | 结束后的归档状态 | 终态；不允许普通业务写入 |
| `pending_kickoff` | 执行中（历史状态） | 旧数据兼容状态 | 当前常规审核不会写入此状态；部分执行能力仍兼容读取 |

常规状态迁移如下。括号内是执行迁移的入口；角色和额外条件见后文。

```text
draft --公司管理下发--> dispatched
dispatched --负责人提交--> pending_review
pending_review --企业教练通过--> active
pending_review --企业教练退回--> returned
returned --负责人重新提交--> pending_review
active --负责人申请结束--> pending_close
pending_close --负责人取消 / 企业教练退回--> active
pending_close --企业教练批准--> ended
ended --技术管理员归档--> archived
```

主要入口和前置条件：

| 迁移 | 接口/函数 | 必要条件 |
|---|---|---|
| 新建 → `draft` | `POST /api/projects` / `create_project` | 公司管理或技术管理员；请求中的初始状态字段不会改变默认 `draft` |
| `draft` → `dispatched` | `POST /api/projects/{id}/dispatch` | 公司管理/技术管理员；须有 `project_ceo` 与 `owner`，目标、开始日期有效；结束日期可空但若填写须不早于开始日期 |
| `dispatched` 或 `returned` → `pending_review` | `POST /api/projects/{id}/owner-submit` | 项目负责人/技术管理员；须提供至少一条重点工作及其关键任务，工作计划人员须能解析 |
| `pending_review` → `active` | `POST /api/projects/{id}/approve` | 本项目企业教练/技术管理员；不得从其他状态审核通过 |
| `pending_review` → `returned` | `POST /api/projects/{id}/return` | 本项目企业教练/技术管理员；不得从其他状态退回 |
| `active` → `pending_close` | `POST /api/projects/{id}/close-requests` | 项目负责人/技术管理员；结束材料有效且无阻断项，无其他待审结束申请 |
| `pending_close` → `active` | `.../close-requests/{request_id}/cancel` 或 `/reject` | 原申请负责人可取消；本项目企业教练/技术管理员可退回；项目和申请必须仍配对待审 |
| `pending_close` → `ended` | `.../close-requests/{request_id}/approve` | 本项目企业教练/技术管理员；结束材料和阻断项复核通过 |
| `ended` → `archived` | `POST /api/projects/{id}/archive` | 技术管理员；仅 `ended` 可归档 |

### 兼容与特权迁移

- `pending_kickoff` 保留在状态词汇、前端显示和部分执行能力里，以承接历史记录；新的立项审核通过直接写 `active`，启动会本身是项目会议/提案审核流程，不是 `pending_kickoff → active` 的常规门槛。
- `dispatched` 是当前常规立项链路的真实阶段。后端 `is_execution_available()` 为兼容旧执行记录仍把它视为执行结构可用；正式汇报提交仍仅允许 `active`。
- `POST /api/projects/{id}/kickoff` 是技术管理员专用兜底入口，可把非结束冻结、非归档项目直接设为 `active` 并记录启动时间/操作者。它绕过常规立项审核，不能用于日常启动。
- 批量导入接口可由技术管理员一次性建项并设为 `active`，属于导入路径，不是常规立项迁移。
- 通用 `PATCH /api/projects/{id}` 可更新资料，不拥有状态迁移权。为旧客户端兼容，提交与当前状态相同的 `status` 或 `lifecycle_status` 可接受；请求试图改变状态返回 409。审核通过/退回也只允许 `pending_review`。

## 角色 × 动作 × 状态矩阵

全局角色名与项目角色名属于不同层级：`company_ceo` 表示公司管理；`super_admin`/账号 `is_tech_admin` 在业务上下文中具有技术管理员能力；项目角色存于 `project_members.role`，键为 `owner`、`coordinator`、`member`、`project_ceo`。同一人员可以有多个项目角色；显示优先级不替代逐动作授权判断。

| 动作 | 公司管理 `company_ceo` | 技术管理员 `super_admin` / `is_tech_admin` | 项目负责人 `owner` | 企业教练 `project_ceo` | 统筹人 `coordinator` | 成员 `member` | 额外状态/资源约束 |
|---|---|---|---|---|---|---|---|
| 查看项目 | 全局可见 | 全局可见 | 本项目成员可见 | 本项目成员可见 | 本项目成员可见 | 本项目成员可见 | 查看本身不因终态自动撤权；数据操作接口另有权限 |
| 创建项目 | 允许 | 允许 | — | — | — | — | 新项目仍从 `draft` 建立 |
| 批量导入项目 | — | 允许 | — | — | — | — | 技术管理员专用；导入新项目会直接建为 `active` 并写入导入业务数据，属于绕过常规立项的迁移/导入例外 |
| 编辑基础资料、直接配置团队 | 仅 `draft` | 技术管理员可越过角色决策 | — | — | — | — | 已下发后走成员变更申请流程 |
| 下发项目 | 允许 | 允许 | — | — | — | — | 仅 `draft`，须先配置负责人和企业教练及有效目标、日期 |
| 提交/重提立项方案 | — | 允许 | 允许 | — | — | — | 仅 `dispatched` / `returned`；进入 `pending_review` |
| 审核立项、通过或退回 | 仅同时持有本项目企业教练角色时可执行 | 允许 | — | 本项目角色允许 | — | — | 只允许 `pending_review`；通过到 `active`，退回到 `returned` |
| 发起成员变更申请 | — | 允许 | 允许 | 允许 | — | — | 已结束冻结或归档时由生命周期守卫拒绝写入 |
| 审核成员变更 | — | 允许 | — | 允许 | — | — | 还须满足成员变更申请本身的待审状态 |
| 申请结束 | — | 允许 | 允许 | — | — | — | 只允许 `active`；有未完确认、待决策问题、待审成果/成员申请等阻断时拒绝 |
| 编辑/取消结束申请 | — | 允许 | 仅原申请人且仍为本项目负责人 | — | — | — | 申请与项目必须仍处于配对待审状态 |
| 审核结束申请 | — | 允许 | — | 允许 | — | — | 项目 `pending_close` 且申请 `pending`；批准到 `ended`，退回到 `active` |
| 归档项目 | — | 允许 | — | — | — | — | 仅 `ended` |
| 删除项目 | — | 允许 | — | — | — | — | 技术管理员专用；要求二次确认并锁定项目，但当前路由未按生命周期限制，可删除任意状态项目，属于破坏性全局操作 |
| 技术启动兜底 | — | 允许 | — | — | — | — | 不可用于 `pending_close`、`ended`、`archived`；可绕过常规立项审核，需留审计记录 |

其他工作流的已核实角色边界：

| 工作流动作 | 允许角色（技术管理员也可执行，除非动作明确绑定原提交人） | 说明 |
|---|---|---|
| 查看汇报确认记录 | 公司管理、负责人、统筹人、企业教练、原提交人 | 全局可见不等于具有最终确认权 |
| 确认汇报入库/打回/上报企业教练 | 项目负责人 | 企业教练、统筹人不继承负责人最终确认权限 |
| 统筹反馈 | 项目统筹人 | 只反馈，不做最终确认 |
| 企业教练决策 | 本项目企业教练 | 处理被负责人上报的决策事项 |
| 创建会议 | 负责人、统筹人、项目成员 | 会议创建另受 `require_project_business_writable` 结束冻结守卫 |
| 编辑会议 | 会议创建人或项目负责人 | 会议本身状态还需符合编辑规则 |
| 发布会议/审核或应用会议变更 | 项目负责人 | 高影响回写动作由负责人执行 |
| 审核会议进展 | 项目负责人或统筹人 | 不等于拥有立项/结束审核权 |
| 提交启动会审核包 | 项目负责人 | 需要执行结构可用：`active`、常规方案完善阶段 `dispatched`、历史 `pending_kickoff` |
| 确认启动会 | 本项目企业教练 | 启动会确认审核提案；常规立项审核已将项目设为 `active` |

权限表依据：`decide_project_action()`、`decide_workflow_action()` 与相关路由中的额外状态守卫。技术管理员的角色绕行不代表可绕过结束冻结、归档及各路由明确规定的资源状态检查；技术启动和批量导入是专门例外。

## 业务写入的状态边界

| 业务路径 | 当前生命周期条件 | 代码入口/守卫 |
|---|---|---|
| 正式提交工作汇报、获取可汇报上下文 | 必须为 `active`。历史 `pending_kickoff` 不等价于可提交汇报 | `updates._require_project_active()`；`POST /api/updates`、`GET /api/updates/voice-context` |
| AI 汇报提取预览 | 只生成建议，不写正式业务表；项目范围仍需访问检查 | `POST /api/updates/extract` |
| 重点工作下关键任务结构写入 | 需 `is_execution_available()`，即 `active`、兼容的 `dispatched` 或历史 `pending_kickoff`；并受角色守卫 | `subtasks._check_subtask_struct_write()` |
| 普通会议创建/编辑/发布及任务、问题等业务写入 | 具体路由角色规则之外，统一业务写保护拒绝 `pending_close`、`ended`、`archived`；各路由可能再加更严格状态条件 | `require_project_business_writable()` 与 `require_project_not_archived()` |
| “我的任务”汇总 | 当前项目可见范围内只汇总 `active` 与兼容的 `pending_kickoff` | `app/services/my_tasks.py` |
| 工作推进表可选列配置 | 仅改变项目级展示字段，不改变业务数据或生命周期；接口以项目查看权限校验，当前不限制项目终态 | `GET/PATCH /api/projects/{id}/work-progress-columns` |

`require_project_business_writable()` 的精确范围是关闭审核冻结与归档防护；它本身不表示项目处于可正式汇报的 `active` 阶段。调用方若需要 active-only 或 execution-available，必须另外调用相应守卫。

## 项目字段词典

| 字段 | 物理/接口口径 | 用途与约束 |
|---|---|---|
| `id` | `projects.id`，模型主键 | 项目稳定标识；接口外键和授权应优先使用它 |
| `name` | `projects.name`，非空且唯一 | 展示名称；不应替代项目 ID 做关联授权 |
| `code` | 模型字段/接口字符串 | 可读项目编码；当前未见唯一性约束，不作为主键 |
| `description` | 模型字段/接口字符串 | 项目简介 |
| `objectives` | 可选迁移扩展列/接口字段 | 项目目标；下发时必须非空 |
| `start_date`、`end_date` | `VARCHAR`/文本式 `YYYY-MM-DD` 字段 | 下发入口验证格式；结束日期可空，若有值不得早于开始日期 |
| `status` | `projects.status`，模型字段，规范状态写入口 | 项目当前生命周期；新建默认 `draft`；后端 `status` 优先于兼容字段读取 |
| `lifecycle_status` | 可选旧库列和接口兼容字段，非当前 SQLAlchemy `Project` 模型主字段 | `_set_project_lifecycle()` 尽可能与 `status` 同步；不得与 `status` 并列当作另一套状态机 |
| `is_active` | 模型布尔兼容字段 | 生命周期写入时派生为 `status == active`；不可用它区分全部九种状态，读取旧记录时才作为缺少状态列时的回退 |
| `project_type`、`client_name`、`background`、`expected_outcomes` | 立项资料接口字段；当前模型未声明，路由通过列存在检查写入可选迁移列 | 不同数据库/历史 schema 可能暂缺；API 无该列时默认空值/跳过写入 |
| `kickoff_date`、`kickoff_by`、`initiated_by` | 当前响应和路由可选读取/写入的兼容资料列 | `kickoff_date/by` 记录启动事件事实，不决定当前生命周期 |
| `coordinator`、`owners`、`collaborators` | 旧项目字符串字段 | 仅兼容展示/迁移；当前授权角色来源为 `project_members`，包含 `person_id` 与 role |
| `sort_order` | 模型整数 | 项目列表排序，不影响权限或阶段 |
| `work_progress_optional_columns` | 模型 JSON 数组 | 项目工作推进表显示配置，只允许 `expectedOutcome`、`goal`、`boweiRole` |
| `created_at`、`updated_at` | 时间戳 mixin | 记录生命周期之外的创建和更新时间 |

数据库迁移文件只能说明代码预期结构，不能证明某个实际数据库已经应用迁移。对本地、测试或生产库核对前，须读取该环境实际 Alembic 版本和 schema。

## 主要代码与测试证据

- 生命周期定义：`bowei_ai_dashboard/app/domain/project_lifecycle.py`
- 项目动作决策：`bowei_ai_dashboard/app/domain/project_permissions.py`
- 工作流动作决策：`bowei_ai_dashboard/app/domain/workflow_permissions.py`
- 状态写入口与项目字段投影：`bowei_ai_dashboard/app/routers/projects.py`
- 关闭冻结与项目结束阻断：`bowei_ai_dashboard/app/services/project_close.py`
- 行为回归：`bowei_ai_dashboard/tests/test_project_lifecycle_simplification.py`、`test_project_permission_characterization.py`、`test_full_role_lifecycle_audit.py`、`test_project_close_lifecycle_guards.py`
