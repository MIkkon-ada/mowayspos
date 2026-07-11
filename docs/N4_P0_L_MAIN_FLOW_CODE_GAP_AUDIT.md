# N4-P0-L 主流程代码差异审计报告

> 审计分支：`n4-p0-j-active-project-key-task-assignment`  
> 审计基准：`docs/N4_P0_BASELINE_MAIN_FLOW_STAGE_MAP.md`  
> 审计原则：本文所有“当前代码事实”均来自当前分支源码，不直接采用对话判断作为结论。无法从源码确认的内容明确标注“未能从当前代码确认”。本轮只审计，不修复。

## 1. 审计结论

当前分支已经包含四个主题：

1. N4-P0-I：工作汇报 `project_id` 绑定修复。
2. N4-P0-J：active 项目执行期补派关键任务。
3. N4-P0-K：AI 确认中心 reviewer 识别修复。
4. N4-P0-BASELINE：主流程阶段基准文档。

代码事实显示，I/J/K 都解决了对应的局部断点：

- 工作汇报前端会读取 URL `projectId`，无项目时阻止 AI 提取 / 提交，提取和提交请求均携带 `project_id`。
- 工作推进表前端在 active 项目下为 owner / coordinator / tech_admin 开放新增 / 编辑关键任务，责任人 / 协助人来自当前项目成员。
- AI 确认中心 reviewer 识别不再只依赖 `/project/:id` 场景下的 `currentCapabilities`，而是同时读取用户在任一项目的 `owner / coordinator / project_ceo` 角色和管理能力。

但从主流程基准看，仍存在若干未完全收口的差异：

- 当前没有从代码证实的 P0 阻断差异；工作汇报项目归属、负责人待确认视图、确认入库基本链路都有代码支撑。
- 最大 P1 差异是“关键任务归属未成为全链路强制业务约束”：前端有“必须有可汇报关键任务”的入口门槛和任务卡归属校验，但正式提交接口仍主要强制 `project_id`，未强制每次提交必须绑定具体 SubTask。
- 当前分支相对 `main` 已包含 4 个主题，建议拆 PR 或至少按提交拆分审阅，避免 I/J/K/文档互相牵连。

## 2. 当前代码与主流程基准的符合项

| 编号 | 基准口径 | 当前代码事实 | 涉及文件 |
|---|---|---|---|
| OK-01 | 项目新建应从 `draft` 开始 | `ProjectCreatePayload.status` 和 `lifecycle_status` 默认为 `draft`；普通创建路径调用 `_set_project_lifecycle(project, "draft")` | `bowei_ai_dashboard/app/schemas.py:204`；`bowei_ai_dashboard/app/routers/projects.py:776` |
| OK-02 | 立项下发进入 `dispatched` | `dispatch_project()` 调用 `_set_project_lifecycle(project, "dispatched")` 并写日志 `dispatch_project` | `bowei_ai_dashboard/app/routers/projects.py:1429` |
| OK-03 | 负责人提交立项资料后进入 `pending_review` | `owner_submit_project_profile()` 调用 `_set_project_lifecycle(project, "pending_review")` | `bowei_ai_dashboard/app/routers/projects.py:1471` |
| OK-04 | 工作推进表雏形复用 Task / SubTask | `_save_work_progress_draft()` 将 `work_progress_draft` 写入 `models.Task` 和 `models.SubTask` | `bowei_ai_dashboard/app/routers/projects.py:541` |
| OK-05 | 企业教练审核通过当前 V1.0 直接进入 `active` | `approve_project()` 调用 `_set_project_lifecycle(project, "active")`，并写 `kickoff_date / kickoff_by` | `bowei_ai_dashboard/app/routers/projects.py:1562` |
| OK-06 | active 后工作推进表作为执行入口 | `/work/tasks` 路由加载 `TaskManagementPage`，页面包含执行视图与计划表视图 | `frontend/src/app/routes.tsx:145`；`frontend/src/pages/TaskManagementPage.tsx:206` |
| OK-07 | 工作汇报主路径带 `project_id` | `VoiceUpdatePage` 读取 URL `projectId`；`useVoiceExtraction` 和 `useVoiceSubmission` 传 `project_id` | `frontend/src/pages/VoiceUpdatePage.tsx:57`；`frontend/src/features/voice-update/useVoiceExtraction.ts:131`；`frontend/src/features/voice-update/useVoiceSubmission.ts:128` |
| OK-08 | 非 active 项目不能提交正式工作汇报 | 前端使用 `isProjectActive()` 生成拦截提示；后端 `create_update()` 调用 `_require_project_active(project_id, db)` | `frontend/src/pages/VoiceUpdatePage.tsx:91`；`bowei_ai_dashboard/app/routers/updates.py:97`；`bowei_ai_dashboard/app/routers/updates.py:273` |
| OK-09 | 负责人可确认入库 | `confirm()` 检查 `_can_owner_style_action()`，并在确认后写 Task / SubTask / Achievement / Issue，最后设置 `row.confirm_status = SS.S_CONFIRMED` | `bowei_ai_dashboard/app/routers/confirmations.py:541` |
| OK-10 | 普通 member 不应确认别人提交 | 确认动作依赖 `can_confirm_submission_by_project()`，该函数只允许 tech_admin 或项目 owner；project_ceo/coordinator 不可确认 | `bowei_ai_dashboard/app/permissions.py:780`；`bowei_ai_dashboard/app/services/policy.py:52` |
| OK-11 | archived 项目应禁止继续写入 | `require_project_not_archived()` 已被 tasks / subtasks / updates / achievements / issues 多处写入口调用 | `bowei_ai_dashboard/app/archived_guard.py:25`；`bowei_ai_dashboard/app/routers/updates.py:272`；`bowei_ai_dashboard/app/routers/subtasks.py:415` |

## 3. P0 差异清单

本轮未发现能从当前代码直接确认的 P0 阻断差异。

说明：

- 工作汇报项目归属主路径已由前端固定携带 `project_id`，后端也在提交时拒绝无法解析项目的请求。
- 负责人待确认视图已通过 N4-P0-K 修复 reviewer 识别。
- 确认入库路径存在正式写入 Task / SubTask / Achievement / Issue 的代码。
- 未发现普通 member 可直接调用确认入库的代码事实。

需要注意：以下 P1 差异如果业务要求提高为“正式版强制条件”，可能升级为 P0。

## 4. P1 差异清单

### GAP-P1-01

差异编号：GAP-P1-01  
所属阶段：阶段 9：成员按关键任务提交进展  
基准口径：成员正式提交工作进展前，应有明确项目归属；更理想情况下，还应有明确关键任务归属。  
当前代码事实：`VoiceUpdatePage` 进入页面时调用 `fetchVoiceContext()` 检查用户是否有可汇报关键任务；但该首次检查没有传 `project_id`。`useVoiceSubmission()` 强制 `selectedProjectId`，并对已修改任务卡和建议新增关键任务做归属校验；但 `createUpdate` payload 只强制携带 `project_id`，没有强制每次提交都携带一个具体 `subtask_id`。  
涉及文件：`frontend/src/pages/VoiceUpdatePage.tsx:37`、`frontend/src/pages/VoiceUpdatePage.tsx:39`、`frontend/src/features/voice-update/useVoiceSubmission.ts:53`、`frontend/src/features/voice-update/useVoiceSubmission.ts:67`、`frontend/src/features/voice-update/useVoiceSubmission.ts:128`、`bowei_ai_dashboard/app/routers/updates.py:232`  
风险等级：P1  
是否阻断正式版：不一定；如果正式口径要求“每条汇报必须绑定具体关键任务”，则阻断。  
建议处理方式：后续 N4-P0-M 明确是否强制 SubTask 绑定；如强制，补前端选择和后端校验。  
是否建议本轮修复：否，仅审计。

### GAP-P1-02

差异编号：GAP-P1-02  
所属阶段：阶段 10：AI 提取  
基准口径：AI 不应作为项目归属判断主路径；AI 负责提取内容，不负责决定业务归属。  
当前代码事实：前端主路径已携带 `project_id`；但后端 `create_update()` 在 `project_id is None` 且有 `human_result` 时，仍尝试从 `special_project` 或 `task_reports.parent_task_id` 反查项目。API 类型里 `project_id` 仍是可选。  
涉及文件：`frontend/src/api/updates.ts:4`、`frontend/src/api/updates.ts:106`、`bowei_ai_dashboard/app/routers/updates.py:247`、`bowei_ai_dashboard/app/routers/updates.py:267`  
风险等级：P1  
是否阻断正式版：否，但容易被误用为主路径。  
建议处理方式：保留兼容路径时明确标注 legacy fallback；正式入口继续强制前端传 `project_id`。  
是否建议本轮修复：否，仅审计。

### GAP-P1-03

差异编号：GAP-P1-03  
所属阶段：阶段 8：关键任务派发  
基准口径：执行期补派关键任务应只发生在 active 项目。  
当前代码事实：前端 `canAssignSubTasks()` 要求 `isProjectActive(taskProject)` 且具备 `canManageProjectWork()`；后端 `create_subtask()` / `update_subtask()` 调用 `_check_subtask_struct_write()` 和 `require_project_not_archived()`，但未看到后端显式 `_require_project_active()` 校验。  
涉及文件：`frontend/src/pages/TaskManagementPage.tsx:413`、`frontend/src/pages/TaskManagementPage.tsx:422`、`frontend/src/domain/taskPermission.ts:16`、`bowei_ai_dashboard/app/routers/subtasks.py:143`、`bowei_ai_dashboard/app/routers/subtasks.py:402`、`bowei_ai_dashboard/app/routers/subtasks.py:415`、`bowei_ai_dashboard/app/routers/subtasks.py:491`  
风险等级：P1  
是否阻断正式版：否，但后端边界不够硬。  
建议处理方式：后续补一个只读审计或小修，确认 SubTask 结构写入是否应强制 active。  
是否建议本轮修复：否，仅审计。

### GAP-P1-04

差异编号：GAP-P1-04  
所属阶段：阶段 6：启动确认 / 启动会  
基准口径：理想流程中，企业教练审核后的工作推进表雏形应经过启动确认 / 启动会成为正式执行版。V1.0 可暂以企业教练审核通过作为雏形确认成执行版。  
当前代码事实：`approve_project()` 直接 `_set_project_lifecycle(project, "active")`；代码中存在 `kickoff_project()` 技术兜底和会议纪要 `meeting_type=kickoff`，但未看到独立 `pending_kickoff` / `kickoff_review` 生命周期状态。  
涉及文件：`bowei_ai_dashboard/app/routers/projects.py:1562`、`bowei_ai_dashboard/app/routers/projects.py:1616`、`frontend/src/features/meeting/NewMeetingModal.tsx:295`、`bowei_ai_dashboard/app/routers/meetings.py:517`  
风险等级：P1  
是否阻断正式版：V1.0 不阻断；增强版需要设计。  
建议处理方式：保持文档口径，不用会议类型替代生命周期状态；后续 N4-P1 设计启动确认状态。  
是否建议本轮修复：否，仅审计。

### GAP-P1-05

差异编号：GAP-P1-05  
所属阶段：阶段 11：负责人确认入库  
基准口径：AI 确认中心应是“待确认处理台”，不是“我的提交记录中心”。  
当前代码事实：N4-P0-K 已修复 reviewer 识别：`isReviewer` 读取 `currentCapabilities`、`currentUser` 管理能力、`globalUserRoles` 和任一项目角色；但 `ConfirmPage` 仍保留 `viewMode` 的 `mine / all` 双视图，并始终显示“我的提交”按钮。  
涉及文件：`frontend/src/pages/ConfirmPage.tsx:28`、`frontend/src/pages/ConfirmPage.tsx:212`、`frontend/src/pages/ConfirmPage.tsx:247`、`frontend/src/pages/ConfirmPage.tsx:257`、`frontend/src/pages/ConfirmPage.tsx:635`、`frontend/src/pages/ConfirmPage.tsx:638`  
风险等级：P1  
是否阻断正式版：否，但职责边界容易混淆。  
建议处理方式：后续 N4-P0-N 将“我的提交”降级或迁移到工作汇报 / 我的任务，确认中心默认聚焦待确认。  
是否建议本轮修复：否，仅审计。

### GAP-P1-06

差异编号：GAP-P1-06  
所属阶段：阶段 1：项目创建  
基准口径：项目创建应从 `draft` 开始，不应绕过立项生命周期直接 active。  
当前代码事实：普通创建路径是 `draft`；但项目批量导入路径创建新项目后调用 `_set_project_lifecycle(proj, "active")`，同时创建任务和问题。  
涉及文件：`bowei_ai_dashboard/app/routers/projects.py:776`、`bowei_ai_dashboard/app/routers/projects.py:867`、`bowei_ai_dashboard/app/routers/projects.py:895`、`bowei_ai_dashboard/app/routers/projects.py:912`  
风险等级：P1  
是否阻断正式版：否，但会绕过立项下发 / 审核。  
建议处理方式：确认批量导入是否仅限历史/管理员初始化；如仍是正式入口，应单独设计其生命周期口径。  
是否建议本轮修复：否，仅审计。

### GAP-P1-07

差异编号：GAP-P1-07  
所属阶段：阶段 12：成果 / 问题 / 工作推进表 / 驾驶舱回流  
基准口径：确认入库后，成果、问题、工作推进表、驾驶舱应能看到确认后的正式数据。  
当前代码事实：`confirm()` 有写入 Achievement / Issue / Task / SubTask 的代码；Dashboard 后端查询 Task、Issue、Achievement、UpdateSubmission 并计算统计。但本轮未做真实端到端数据冒烟，无法从静态代码确认所有前端展示字段都与确认结果一致。  
涉及文件：`bowei_ai_dashboard/app/routers/confirmations.py:541`、`bowei_ai_dashboard/app/routers/dashboard.py:282`、`bowei_ai_dashboard/app/routers/dashboard.py:298`、`bowei_ai_dashboard/app/routers/dashboard.py:308`、`bowei_ai_dashboard/app/routers/dashboard.py:314`、`frontend/src/pages/DashboardPage.tsx:451`  
风险等级：P1  
是否阻断正式版：未能从当前代码确认；需要真实回流验收。  
建议处理方式：后续 N4-P0-O 做端到端验收，覆盖成果、问题、工作推进表、驾驶舱。  
是否建议本轮修复：否，仅审计。

## 5. P2 差异清单

### GAP-P2-01

差异编号：GAP-P2-01  
所属阶段：阶段 11：负责人确认入库  
基准口径：待确认处理入口应清楚，不让 reviewer 与 submitter 视角混淆。  
当前代码事实：确认中心顶部仍以两个按钮切换“我的提交 / 待确认”，未能从当前代码确认有更明确的信息架构拆分。  
涉及文件：`frontend/src/pages/ConfirmPage.tsx:635`  
风险等级：P2  
是否阻断正式版：否。  
建议处理方式：后续交互优化，把“我的提交”移出确认中心主视图或弱化为辅助入口。  
是否建议本轮修复：否，仅审计。

### GAP-P2-02

差异编号：GAP-P2-02  
所属阶段：阶段 6：启动确认 / 启动会  
基准口径：启动会的核心材料是工作推进表雏形。  
当前代码事实：会议纪要支持 kickoff 类型，但未能从当前代码确认 kickoff 会议与具体工作推进表雏形之间有结构化关联。  
涉及文件：`frontend/src/features/meeting/NewMeetingModal.tsx:295`、`bowei_ai_dashboard/app/routers/meetings.py:517`  
风险等级：P2  
是否阻断正式版：否。  
建议处理方式：后续启动会增强时再设计会议与执行版确认的关系。  
是否建议本轮修复：否，仅审计。

## 6. 按阶段差异审计

| 阶段 | 基准口径 | 当前代码事实 | 结论 |
|---|---|---|---|
| 1 项目创建 | 创建项目壳子和角色配置，默认 draft | 普通创建强制 draft；批量导入会直接 active | 普通路径符合；批量导入为 P1 差异 |
| 2 立项下发 | 进入 dispatched | `dispatch_project()` 设置 dispatched | 符合 |
| 3 负责人完善立项信息 | OwnerSubmitModal 提交立项资料 | `ownerSubmitProfile()` 提交到 owner-submit | 符合 |
| 4 工作推进表雏形 | 复用 Task / SubTask | `_save_work_progress_draft()` 写 Task/SubTask | 符合 |
| 5 企业教练审核 | pending_review → active / returned | `approve_project()` → active；`return_project()` → returned | 符合 V1.0 口径 |
| 6 启动确认 / 启动会 | 理想增强阶段 | 当前无独立生命周期状态；存在 kickoff 会议类型 | P1/P2 增强项 |
| 7 执行版工作推进表 | active 后执行展示 | `/work/tasks` + TaskManagementPage | 符合 |
| 8 关键任务派发 | active 后 owner/coordinator 派发 | 前端 active 校验；后端 owner/coordinator/tech_admin + archived 拦截 | P1：后端 active 边界待补审 |
| 9 成员提交进展 | 绑定项目，理想绑定关键任务 | project_id 已绑定；SubTask 绑定非全链路强制 | P1 |
| 10 AI 提取 | 提取内容，不定归属 | 前端带 project_id；后端仍有反查兜底 | P1 兼容残留 |
| 11 负责人确认入库 | 待确认处理台 | reviewer 识别已修；仍保留“我的提交” | P1/P2 |
| 12 回流 | 正式数据回流多模块 | 代码写入多表；未做真实端到端展示验收 | P1 验收项 |
| 13 归档 | archived 后禁止写入 | 多处使用 archived guard | 基本符合；建议全量写入口复查 |

## 7. 按模块职责差异审计

### 7.1 项目管理

基准口径：负责项目创建、角色配置、下发、审核、生命周期流转；不负责执行期日常进展和入库。  
代码事实：`ProjectsMgmtSection` 渲染项目队列、下发、审核材料、审核通过/退回、归档；执行期入口通过按钮跳转到 `/work/tasks`。  
涉及文件：`frontend/src/features/settings/ProjectsMgmtSection.tsx:218`、`frontend/src/features/settings/ProjectsMgmtSection.tsx:543`、`frontend/src/features/settings/ProjectsMgmtSection.tsx:562`、`frontend/src/features/settings/ProjectsMgmtSection.tsx:588`。  
结论：基本符合；未发现项目管理页直接承担确认入库。

### 7.2 OwnerSubmitModal

基准口径：负责立项资料和工作推进表雏形，不负责日常汇报。  
代码事实：`OwnerSubmitModal` 构造 `work_progress_draft` 并调用 `ownerSubmitProfile()`；未看到它调用工作汇报或确认中心接口。  
涉及文件：`frontend/src/features/settings/OwnerSubmitModal.tsx:125`、`frontend/src/features/settings/OwnerSubmitModal.tsx:220`。  
结论：符合。

### 7.3 工作推进表

基准口径：负责执行期 Task / SubTask 管理和进展回流查看，不承担立项审批。  
代码事实：`TaskManagementPage` 加载 tasks/subtasks、支持执行视图/计划表视图、新增关键任务、读取 `fetchTaskUpdates()`；未看到其调用项目审核接口。  
涉及文件：`frontend/src/pages/TaskManagementPage.tsx:4`、`frontend/src/pages/TaskManagementPage.tsx:16`、`frontend/src/pages/TaskManagementPage.tsx:537`、`frontend/src/pages/TaskManagementPage.tsx:915`。  
结论：基本符合。

### 7.4 工作汇报

基准口径：负责成员提交进展和 AI 提取，不直接正式入库。  
代码事实：`VoiceUpdatePage` 使用 `useVoiceExtraction` 和 `useVoiceSubmission`；提交产生 `UpdateSubmission`，正式入库在 confirmations。  
涉及文件：`frontend/src/pages/VoiceUpdatePage.tsx:11`、`frontend/src/pages/VoiceUpdatePage.tsx:164`、`bowei_ai_dashboard/app/routers/updates.py:329`。  
结论：符合，但关键任务归属仍需收口。

### 7.5 AI 确认中心

基准口径：负责待确认处理，不做提交记录中心。  
代码事实：`ConfirmPage` 既有 `fetchMyUpdates()` 的 mine 视图，也有 `getPending()` 的 all 视图。  
涉及文件：`frontend/src/pages/ConfirmPage.tsx:300`、`frontend/src/pages/ConfirmPage.tsx:313`、`frontend/src/pages/ConfirmPage.tsx:635`。  
结论：处理能力符合；产品职责仍混杂。

### 7.6 成果库 / 问题中心 / 驾驶舱

基准口径：展示确认后的正式数据。  
代码事实：成果页调用 `fetchAchievements()`；问题页调用对应 issues API；驾驶舱后端聚合 Task、Issue、Achievement、UpdateSubmission。  
涉及文件：`frontend/src/pages/AchievementsPage.tsx:106`、`frontend/src/pages/IssuesPage.tsx:580`、`bowei_ai_dashboard/app/routers/dashboard.py:282`、`bowei_ai_dashboard/app/routers/dashboard.py:298`、`bowei_ai_dashboard/app/routers/dashboard.py:308`。  
结论：有代码支撑；展示完整性需端到端验收。

## 8. 权限边界审计

| 权限点 | 当前代码事实 | 结论 |
|---|---|---|
| company_ceo 不自动等同 project_ceo | `can_ceo_decide_by_project()` 注释和逻辑只允许 tech_admin 或项目 `project_ceo`；company_ceo 仅保留全局查看能力 | 决策处理边界符合 |
| owner 确认入库 | `can_confirm_submission_by_project()` 允许 tech_admin 或项目 owner | 符合 |
| coordinator 处理统筹反馈 | `can_coordinator_feedback_by_project()` 要求项目 coordinator | 符合 |
| project_ceo 处理企业教练决策 | `can_ceo_decide_by_project()` 要求项目 project_ceo | 符合 |
| member 不能确认别人提交 | 确认动作通过 `_can_owner_style_action()` / `can_confirm()`；member 无 owner 角色不能通过 | 符合 |
| pending 列表可见性 | `role_allows_batch()` 对 `can_view_all` 直接放行列表；处理动作仍另走确认权限函数 | 需要人工验收“可见”和“可处理”是否符合产品预期 |

涉及文件：`bowei_ai_dashboard/app/permissions.py:780`、`bowei_ai_dashboard/app/permissions.py:800`、`bowei_ai_dashboard/app/permissions.py:828`、`bowei_ai_dashboard/app/services/policy.py:146`、`bowei_ai_dashboard/app/services/policy.py:164`、`bowei_ai_dashboard/app/routers/confirmations.py:219`。

## 9. 数据回流审计

| 回流目标 | 当前代码事实 | 是否从代码确认 |
|---|---|---|
| 工作推进表 Task | `confirm()` 可创建或更新 Task，并记录 `source_submission_id` | 已确认 |
| 工作推进表 SubTask | `confirm()` 可更新已有 SubTask、创建新 SubTask、同步父任务状态 | 已确认 |
| 成果库 Achievement | `confirm()` 调用 `W.fulfill_or_create_achievement()` 或创建成果 | 已确认 |
| 问题中心 Issue | `confirm()` 创建 `models.Issue` | 已确认 |
| 驾驶舱统计 | dashboard 查询 Task / Issue / Achievement / UpdateSubmission | 静态代码确认查询存在；未做真实数据回流冒烟 |

涉及文件：`bowei_ai_dashboard/app/routers/confirmations.py:541`、`bowei_ai_dashboard/app/routers/dashboard.py:282`、`bowei_ai_dashboard/app/routers/dashboard.py:298`、`bowei_ai_dashboard/app/routers/dashboard.py:308`、`bowei_ai_dashboard/app/routers/dashboard.py:314`。

## 10. 当前分支 I / J / K 改动是否建议拆分合并

当前分支相对 `main` 包含 4 个提交：

- `9c63d6f fix: bind project context for work submissions`
- `adcc8ba feat: assign key tasks in active work progress`
- `345697f fix: show pending confirmations for project reviewers`
- `c45d58d docs: define main flow stage baseline`

当前分支相对 `main` 修改文件包括：

- 工作汇报：`VoiceUpdatePage.tsx`、`useVoiceExtraction.ts`、`useVoiceSubmission.ts`、`VoiceUpdateSubmitPanel.tsx`、`authFlow.ts`、相关测试。
- 工作推进表：`TaskManagementPage.tsx`、相关测试。
- 确认中心：`ConfirmPage.tsx`、相关测试。
- 文档：`docs/N4_P0_BASELINE_MAIN_FLOW_STAGE_MAP.md`。

结论：当前分支已经过大，建议拆 PR。

建议拆分顺序：

1. docs 基准文档：可先单独合并，风险最低。
2. N4-P0-I 工作汇报项目绑定：建议单独 PR；合并前需要真实人工冒烟 active 提交、非 active 拦截、多 active 选择、单 active 自动选中。
3. N4-P0-J 执行期关键任务派发：建议单独 PR；合并前需要 owner UI 补派、member 无派发入口、责任人/协助人显示、后端权限冒烟。
4. N4-P0-K 确认中心 reviewer 修复：建议单独 PR；合并前需要 owner 能看到成员待确认、member 只能看自己的提交、`?projectId=` 范围加载冒烟。

是否建议合并：

| 项 | 建议 | 原因 |
|---|---|---|
| docs 基准文档 | 建议先合并 | 文档-only，作为后续判断依据 |
| N4-P0-I | 建议合并，但需人工冒烟 | 代码事实显示主路径已带 project_id；仍需真实账号验证 |
| N4-P0-J | 建议合并，但需人工冒烟；后端 active 边界作为后续 P1 | 前端和权限主路径已实现；后端 active 强边界未收口 |
| N4-P0-K | 建议合并，但需人工冒烟 | reviewer 识别代码已修；需用真实 owner/member 验证列表和处理权限 |

## 11. 后续修复顺序建议

1. 先合并或单独发布 docs 基准文档。
2. 对 N4-P0-I 做真实 UI/API 冒烟，确认工作汇报项目绑定稳定。
3. 对 N4-P0-K 做真实 owner/member 冒烟，确认待确认视图和权限。
4. 对 N4-P0-J 做真实 owner/member 冒烟，确认 active 项目补派关键任务。
5. N4-P0-M：明确并实现成员汇报关键任务绑定口径。
6. N4-P0-O：确认入库回流完整性验收。
7. N4-P0-N：确认中心职责收口，弱化或迁移“我的提交”。
8. N4-P1：设计启动确认 / 启动会状态增强。

## 12. 禁止继续盲改的事项

1. 不要在未确认主流程阶段边界前继续局部修页面。
2. 不要新增第四层任务。
3. 不要新增 Workstream 表。
4. 不要让 AI 成为项目归属主路径。
5. 不要让非 active 项目提交正式工作汇报。
6. 不要把 AI 确认中心继续扩展成“我的提交记录中心”。
7. 不要把项目管理页做成工作推进表。
8. 不要把工作推进表做成立项审批页。
9. 不要把批量导入 active 路径当作普通项目创建流程。
10. 不要在同一个 PR 里继续混入 I/J/K 之外的新功能修复。

