# 当前分支定向验收证据（2026-10-18）

## 版本与范围

- 分支：`codex/project-work-progress-wbs`
- 代码基线：`061b446`（问题处置操作与项目角色对齐）；本分支也包含项目角色同步和详情页结束流程入口修复。后续 `a46e6b7`、`4f4b4a8`、`fff1ccd` 只更新验收/设计文档，没有改动产品代码。
- 本记录汇总当前分支代码门禁和本地隔离浏览器验证，不替代验收表中的逐项签收，也不代表生产版本。下方按时间追加的记录优先；首轮验证中的旧结论均为当时状态。

## 已取得的证据

| 范围 | 检查 | 结果 | 证据边界 |
| --- | --- | --- | --- |
| H04 后端全量门禁 | `python -m pytest -q` | **2082 passed, 12 skipped**，42 warnings，673.67 秒 | 当前工作区后端全套通过；警告包含 SQLite 循环外键排序等 SQLAlchemy 提示，未导致测试失败 |
| H04 V2 单元测试 | `npm.cmd run test:unit` | **175 passed**（54 个测试文件） | 前端单元覆盖，不代表浏览器完整业务验收 |
| H04 V2 契约测试 | `npm.cmd run test:contracts` | **527 passed** | 修正了六个与当前组件结构、退回重提行为不一致的旧源码断言；产品代码未变 |
| H04 V2 构建及包体积 | `npm.cmd run test:bundle` | 构建通过，bundle 预算通过 | ExcelJS 仍有较大的动态 chunk 提示，但预算门槛通过 |
| 本地隔离运行环境 | 临时 SQLite 执行 Alembic 到 head；后端 8011、V2 6005 健康检查 | 通过 | 数据库位于 `%LOCALAPPDATA%\Temp\mowayspos-acceptance-20261018\acceptance.sqlite`，不是仓库数据库或生产库 |
| V2 浏览器初始化与登录 | 在临时库创建合成管理员并登录 | 通过 | 首次因手动启动未带本地 CORS 白名单而返回 `origin_not_allowed`；按 `run_local_backend_safe.py` 的本地白名单重启后初始化和登录成功。该错误是本次验收启动参数遗漏，未发现为产品代码缺陷 |
| H03 立项到执行的浏览器主链 | 合成项目 ID 1：建草稿 → 下发负责人 → 保存工作计划 → 送企业教练审核 → 审核通过 | **状态链通过**：草稿 → 已派发 → 待审核 → 进行中 | 使用同一个合成超级管理员兼任负责人和教练；能证明页面状态流转及材料回显，不能证明不同账号的权限隔离或真实组织角色交接 |
| C06 工作推进表项目回显 | 从项目详情进入 `/work/tasks?projectId=1`，检查重点工作、任务、负责人和日期；刷新后等待数据加载，再执行浏览器前进/返回 | **通过** | URL 和选择项目控件保留项目；任务行在数据加载完成后回显。短于 400ms 的检查过早，等待 1.5 秒后确认页面数据正常 |
| C10 工作推进表汇报状态 | 后端投影专项 | 6 passed | 覆盖已确认、待处理、空汇报、旧项目名称映射和跨项目错链；不覆盖真实账号浏览器操作 |
| C10 工作推进表展示 | `PlanTableViewV2` 专项 | 10 passed | 验证无汇报与待确认状态分开显示，待确认正文不显示为正式进展 |
| C08 关键任务风险标记 | `KeyTaskExecutionWorkspace` 风险操作专项 | 3 passed | 组件验证标记窗口可取消不写入、失败后保留原因并可重试、解除需要明确确认；未覆盖验收标准要求的目标正式浏览器实机操作 |
| C10 前端交付 | TypeScript/Vite 构建、bundle 预算 | 通过 | ExcelJS 仍有非首屏大 chunk 警告；包体积门槛检查通过 |
| D01-D04、D08、E01、E04、G01-G02、H03 的部分 API 主链 | 多角色生命周期及汇报回写测试 | 14 passed | 隔离 SQLite 直接调用 API；覆盖下发、方案审核、成员提交、统筹/教练流转、PM 确认、问题与成果关联、结束申请与审批；D05 重提见下一行；不含问题独立处理状态闭环、会议全链路或真实浏览器会话 |
| D05 退回汇报修改重提 | 提交人身份与通知模块 + 原记录修订专项 | 28 passed；退回详情组件 1 passed | 同一提交记录可修改正文后重回待负责人审核；审计日志保留原文与修订文；前端提交原 ID 和修订正文；验证未提前创建问题/成果。**部分实现**：重提当前未基于新正文重新生成结构化 AI 结果；仍未覆盖真实浏览器双角色操作 |
| E01、E04 回写与附件绑定 | 汇报确认、资产回写和成果附件专项 | 5 passed | 验证问题/成果归属、跨项目错链拒绝、重复确认防重、附件转入成果；不含成果库真实下载、外部存储可读性和附件越权访问 |
| F01-F03、F05 会议文档和选择性回写 | 文档存取、分析确认、变更应用与启动会边界专项 | 10 passed | 当前代码保留 Word 表格行列及分页符；覆盖证据绑定、人工选择后写入、防重复、待审核项目保护与历史启动兼容；不含真实 AI 质量抽检、浏览器截图和多页真实文档覆盖率核对 |
| G04 归档权限和状态边界 | 两个归档相关测试模块筛选 | 11 passed，76 deselected | 验证非技术管理员受限、已结束项目才可归档等代码规则；不替代生产审计日志或真实账号操作 |
| H04 全量门禁 | 后端全量 pytest、V2 全量单元、全量契约、生产构建及 bundle 预算 | **通过** | 这是代码门禁通过，不等同于 60 项验收标准全部通过 |

## 首轮验证时的未通过项（已由下方追加证据更新）

1. 验收标准 HTML 的 60 项记录默认均为“本次未验收”。历史记录和自动化测试结果没有自动改写为本次签收。
2. 首轮浏览器仅使用合成超级管理员账号；该缺口已由下方追加的独立合成 PM、教练、成员及技术管理员浏览器证据部分补齐。生产组织账号验收仍未完成。
3. 首轮尚未完成完整执行回写、问题处理和归档；下方追加记录已补齐这些主链的本地隔离浏览器证据，但负向分支、会议全链路、成果库附件真实读取及 H06 PostgreSQL 迁移恢复仍待验证。首轮当时 Docker Desktop 不可用；后续启动尝试的最新结果见文末追加记录。

## 可复现的定向命令

在 `bowei_ai_dashboard` 执行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_work_progress_latest_submission.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_full_role_lifecycle_audit.py tests/test_execution_submission_to_work_progress_flow.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_submission_submitter_identity_flow.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_confirmation_asset_writeback.py tests/test_achievement_attachments.py -k "w1_report_assets_write_once_with_subtask_attribution or cross_project_matched_subtask_is_rejected_without_asset_write or second_confirm_is_rejected_and_does_not_duplicate_assets or confirming_submission_moves_bound_attachment_to_achievement or submission_confirmation_creates_one_achievement" -q
.\.venv\Scripts\python.exe -m pytest tests/test_meeting_document_text.py tests/test_meeting_progress_review_api.py::test_analyze_persists_pending_evidence_bound_rows tests/test_meeting_progress_review_api.py::test_confirm_review_updates_subtask_and_marks_accepted -q
.\.venv\Scripts\python.exe -m pytest tests/test_project_meeting_minutes_service.py::test_meeting_document_storage_hashes_reads_and_rejects_unsafe_inputs tests/test_meeting_progress_review_api.py::test_analyze_persists_pending_evidence_bound_rows tests/test_meeting_progress_review_api.py::test_confirm_review_updates_subtask_and_marks_accepted tests/test_meeting_change_set_writeback.py::test_execution_requires_owner_explicit_selection_and_nonblocked_rows tests/test_meeting_change_set_writeback.py::test_patch_revalidates_and_selected_four_actions_execute_with_audit tests/test_meeting_change_set_writeback.py::test_stale_selected_target_rejects_entire_batch_without_partial_create tests/test_meeting_change_set_writeback.py::test_saved_meeting_requires_reviewed_selection_before_any_plan_write tests/test_kickoff_writeback.py::test_active_project_allows_normal_meeting_creation tests/test_kickoff_writeback.py::test_active_project_allows_kickoff_event tests/test_kickoff_writeback.py::test_legacy_pending_kickoff_project_allows_normal_meeting_creation -q
.\.venv\Scripts\python.exe -m pytest tests/test_project_close_lifecycle_guards.py tests/test_project_permission_characterization.py -k archive -q
.\.venv\Scripts\python.exe -m compileall -q app\routers\subtasks.py
.\.venv\Scripts\python.exe -m compileall -q app\services\meeting_document_text.py
```

在 `frontend-v2` 执行：

```powershell
npm.cmd run test:unit -- --run src/components/task-management/PlanTableViewV2.test.tsx
npm.cmd run test:unit -- --run src/features/voice-update/VoiceUpdateDetailDrawer.test.tsx
npm.cmd run build
npm.cmd run check:bundle:dist
```

**首轮判定（已更新）：** 当时仅验证了单一合成管理员下的立项主链。后续独立账号、汇报回写、问题处置和项目归档证据见下文；H06 和 60 项逐项签收仍未完成，因此项目整体尚未验收通过。

## 追加验证（2026-10-18，独立账号和汇报回写）

本节以独立合成账号在 V2 浏览器操作，使用隔离 SQLite。与上面的旧记录相比，负责人、教练和成员现在由三个不同账号执行。

| 范围 | 检查 | 结果 | 证据边界 |
| --- | --- | --- | --- |
| A01、B03、B07、B11、H03 立项交接 | 管理员建项并配置三种角色；普通 PM 保存、提交计划；独立教练审核通过 | **通过该合成项目主链**：草稿 → 已派发 → 待审核 → 进行中；任务负责人正确显示为成员账号 | 本地临时库中的合成用户和合成项目；不替代生产组织用户验收 |
| D01 汇报归属 | 成员从 `/work/submit?projectId=2&subtaskId=2` 提交，负责人确认中心回显同一项目、任务、提交人和原文证据 | **通过** | 记录 ID 1，项目 ID 2，任务 ID 2；本地临时库 |
| D03 未确认隔离 | 提交后先检查 `/work/tasks?projectId=2` | **通过**：显示“待确认”和“暂无已确认进展”，未将待确认正文当作正式进展 |
| D04、C10 确认回写 | 负责人账号点击“确认当前任务卡入库”后再次检查推进表 | **通过**：确认接口 200，状态“已入库”，确认人为验收负责人；推进表显示提交正文和提交人 |
| D04 刷新稳定性 | 刷新推进表 | **通过一次性展示**：已确认进展和任务各显示一次 |
| A03 / H03 服务端权限负向检查 | 成员账号读取 `/api/confirmations/pending?project_id=2` | **通过**：服务端返回 403 `permission denied` |
| D06 AI 配置失败边界 | 检查成员汇报页的提取模型状态 | **当前环境受阻**：显示“未配置模型”，真实 AI 提取按钮禁用，无法完成真实模型验收 |
| D01-D04 继续链路的模拟边界 | 为完成确认中心、确认写入和推进表展示验证，仅在验收浏览器拦截 `/api/updates/extract` 并返回标明“验收浏览器模拟提取”的结构化内容；提交、确认、数据库状态和正式进度投影均走真实本地服务 | **流程后半段通过；真实 AI 提取未验收** | 不调用外部模型；模拟的提取内容不能作为 AI 质量、匹配准确率或真实模型连通性的通过证据 |
| A03 / B03 团队成员更新缺陷 | 编辑项目角色时以服务端新取成员列表、先新增再移除、失败后刷新缓存；浏览器在合成项目中替换负责人、教练、成员 | **缺陷修复后通过手工复测** | 防止移除最后一名负责人触发后端约束并留下部分删除；隔离库浏览器复测，不代表多租户/生产数据库验证 |
| G01-G04 项目结束、审批和归档 | 项目 2 的 1/1 项任务经成员汇报和 PM 确认后完成；PM 填写结束材料提交；独立教练批准；技术管理员归档 | **通过隔离浏览器状态链**：active → pending_close → ended → archived；提交和审批均未返回阻断项，归档接口返回 200 | 项目结束申请 ID 1，PM/教练为不同合成账号；技术管理员执行归档；只证明结束/归档主链，未覆盖退回重提、未完成事项和结束阻断的负向分支 |
| G01 详情页结束入口 | 复测项目详情页“申请项目结束”按钮 | **修复后通过**：抽屉已正常打开 | 首次复测发现页面只维护打开状态和回调，没有渲染结束流程抽屉；本次加了组件回归测试 |
| E01-E04 问题处置主链 | 成员上报并关联项目/重点工作；PM 指派协助人、升级需决策事项；项目教练提交意见；PM 确认意见并解决 | **通过隔离浏览器状态链**：待处理 → 待协调 → 待决策 → 待负责人确认 → 已解决；各写操作接口返回 200，操作意见与负责人确认均保存在问题记录 | 合成项目 1、问题 ID 1；未覆盖风险事项、退回重提、关闭问题和跨项目越权矩阵 |
| E03 问题权限与角色按钮 | 分别以负责人和项目教练打开同一问题详情 | **修复后通过**：负责人只显示其可执行的分派/升级/解决操作；项目教练在决策状态显示“提交处理意见” | 修复前负责人看得到但点了被 403 拒绝的提交意见按钮，教练则完全看不到操作区 |

### 本次缺陷修复和最小回归验证

角色同步原先使用客户端缓存并先删除旧成员，可能在删除最后一名负责人时失败；部分旧成员已删除后，下一次重试又会拿着过期 ID。当前分支改为先读取服务端现状、先补齐新角色再移除旧角色，并在失败后刷新缓存。

新增一个针对性回归用例，验证同步逻辑使用新取成员、添加先于删除。本次修改后该用例通过（1 passed）；`npm.cmd run build` 通过，`npm.cmd run check:bundle:dist` 通过。构建仍提示 ExcelJS 动态 chunk 较大，与之前一致。先前的后端全量和前端全量 H04 结果早于此代码修改，不应视为本次修改后的全量复测。

项目详情页中结束入口的状态从未用于渲染抽屉，是另一个导致 G01 卡住的缺陷。现在详情页挂载现有结束流程抽屉，并在抽屉完成操作后刷新项目状态；新增用例覆盖详情页按钮打开抽屉，连同原有项目详情测试共 4 项通过。后续追加改动后的生产构建和 bundle 预算检查均已通过。

问题处置链路另发现一处真实后端缺陷：项目角色查询函数需要人员 ID，路由却把用户名传入；同时中文存储类型“需决策”与英文枚举 `decision` 直接比较，导致教练无论在前端还是后端都无法完成意见提交。现已按解析后的 `person_id` 查角色，并对问题类型做规范化判断；IssueDetail 按负责人、统筹人、项目教练和当前事项类型展示允许的操作。`tests/test_issue_action_driven_flow.py` 定向测试 19 项通过；前端定向测试共 8 项通过；生产构建和 bundle 预算检查通过。

**最新判定：独立账号立项交接、成员提交到负责人确认和正式进度展示、确认前隔离、成员服务端权限拒绝、问题处置主链，以及项目结束—教练批准—管理员归档主链已取得本地浏览器证据；真实 AI 提取仍因环境未配置模型而阻塞。会议、问题/结束流程负向分支、H06 PostgreSQL 迁移恢复演练及其余验收标准未完成，项目整体仍未达到全部验收通过。**

## 追加复核（2026-10-18，项目隔离与结束负向分支）

| 范围 | 检查 | 结果 | 证据边界 |
| --- | --- | --- | --- |
| A02 项目详情访问隔离 | 隔离内存库调用 `get_project`：成员和项目外账号各一次 | **通过定向检查**：成员读取项目 ID 1；项目外账号收到 403 | 合成数据、直接调用路由函数，不是浏览器 HTTP 会话；生产账号和跨租户验证未完成 |
| A02 / G01 / G02 角色及结束分支回归 | `test_project_view_is_limited_to_project_members_or_global_admin`、结束申请退回/取消/批准历史、创建与批准阶段阻断复核、结束阻断模块 | **8 passed** | 代码级后端回归；不替代真实页面操作或目标数据库验证 |
| B09 立项计划退回修订重提 | `test_http_save_return_resubmit_approve_keeps_the_same_tasks` | **1 passed**：负责人取回原方案与退回意见，修订并重提后教练批准；关键工作和子任务原位更新且无重复 | API 级 TestClient 验证；浏览器呈现和真实组织账号验收未完成 |
| H06 PostgreSQL 运行时门禁 | 启动 Docker Desktop 并查询 Docker Engine | **未通过环境准备**：Docker Desktop 后端在启动 Inference manager 时报告 `dockerInference` 监听路径语法错误；`docker info` 未能返回，未创建容器、数据库或卷 | 没有对现有数据库或持久卷执行任何操作；修复本机 Docker Desktop 启动问题后仍需执行 PostgreSQL 16 迁移、备份恢复及冒烟 |

本次没有修改产品代码。Docker Desktop 启动失败属于本机验收环境问题，不构成 H06 通过证据；目标 PostgreSQL 迁移恢复仍未验收。

**更新判定（本次追加后）：** A02 项目详情访问拒绝、B09 立项方案退回修订重提 API 链，以及 G01/G02 结束流程负向代码回归已取得定向证据；Docker Desktop 启动失败，H06、真实 AI 样本评价、会议全链路及 60 项逐项签收仍未完成，项目整体尚未验收通过。

## 追加验证（2026-10-18，真实 AI 汇报提取探针）

之前记录的“未配置模型”来自临时验收 SQLite 库，该库没有导入 AI 模型配置。重新只读检查项目本机开发库后，确认 `task.extraction` 能力策略启用，主模型与加密凭据存在。为避免把验收数据写入开发库，本次先将数据库以 SQLite backup 复制到系统临时目录，再通过当前代码的 `AIService` 和 `extract_work_report_agent` 对一条合成汇报执行一次真实模型调用；调用日志只写入临时副本，结束后删除临时目录。

| 范围 | 检查 | 结果 | 证据边界 |
| --- | --- | --- | --- |
| D02 / D06 工作汇报 AI 正常提取 | 合成汇报“今天完成了用户管理页面与用户接口的联调……”，候选任务 ID 840001；真实调用 `task.extraction` | **探针通过**：模型 `deepseek-deepseek-v4-pro` 返回 1 张任务卡，匹配候选 ID 840001，并返回 2 段证据 | 验证当前凭据可调用、单条输入可完成结构化提取和任务匹配；不代表 AI 样本质量验收、模型容错/回退验收或浏览器端页面到数据库的完整链路 |
| 开发库保护 | 对源数据库执行探针前后 SHA-256 比对 | **未变化** | AI 调用和审计日志都在临时副本中；临时副本已删除 |

因此，当前开发库中的 AI 配置可用；此前临时验收环境的“模型未配置”不能代表本机开发环境。真实 AI 样本评价、浏览器完整汇报/会议链路、H06 PostgreSQL 迁移恢复和 60 项逐条签收仍未完成，项目整体仍未验收通过。

## 最新复核（2026-10-18，本机数据库版本与启动）

本机启动脚本默认连接 `bowei_ai_dashboard/bowei_ai_dashboard.db`。当前开发库 Alembic 版本为 `x5y6z7a8b9c0`，代码 head 为 `y6z7a8b9c0d1`；`projects` 表缺少 `owner_plan_drafts`。因此本机后端能完成启动，但执行计划提醒后台扫描时报 `no such column: projects.owner_plan_drafts`。本次启动后已停止服务，8011 端口当前无监听。正常启动期间应用运行了会话清理；没有创建验收项目、任务或汇报记录。

为验证修复路径，在系统临时目录通过 SQLite backup 建立主库副本，仅对副本执行 `alembic upgrade head`：迁移从 `x5y6z7a8b9c0` 成功到 `y6z7a8b9c0d1`，完整性检查为 `ok`，项目/重点工作/关键任务记录数分别保持 4/11/48，新增 `owner_plan_drafts` 列。副本已删除。该结果证明 SQLite 副本迁移可行，不证明受保护的本机主库已迁移，也不替代 PostgreSQL H06 演练。

本机主库被数据库安全规则标记为受保护库。将其迁移前必须先生成可恢复备份，并使用项目安全门要求的明确授权；本次未执行主库迁移。当前 6005/8011 本地页面链路因此尚未恢复验证。优先后续动作是授权并执行本机 SQLite 备份—迁移—健康检查，再继续浏览器验收；PostgreSQL H06 与 60 项逐条签收仍未完成。

## 追加复核（2026-10-18，工作推进表延期口径）

在迁移后的隔离版 V2 页面查看工作推进表：所选项目显示 22 项关键任务、0 项延期、1 项未解决问题。只读检查副本数据发现，部分旧计划时间为无年份的“月.日”文本，结构化字段为 `due_kind=unknown`、`due_date=null`。后端仅在 `due_kind=exact` 且明确 `due_date` 早于今天时设置 `is_overdue`；工作推进表汇总和“延期”筛选都依据该标志或人工状态“延期”。因此页面的 0 项是当前严格口径的结果，不能据此证明这些计划没有逾期；页面也没有解释“年份不明、无法判定”，管理者无法区分“无延期”和“日期未明确”。

这与 C09“模糊或缺日期不得臆造截止日”的要求有关。尚需确定：当项目周期能唯一推导年份时，是否允许据此补足旧计划日期；无法唯一推导时则需保持待确认。未作此业务口径决定前，不应把旧文本直接计入延期，也不应把当前 0 项当作延期验收通过。

## 追加复核（2026-10-18，延期筛选页面行为）

在同一隔离版 V2 浏览器页面实际勾选“延期”快速筛选后，页面显示“当前条件下没有匹配的重点工作或关键任务”，顶部仍显示 0 项延期；点击“重置筛选”后，22 项关键任务恢复显示，未解决问题仍为 1 项。该页面行为与当前严格日期判定口径一致，但由于上述月.日计划尚未明确年份，不能作为“项目无延期”的验收证据。浏览器继续停留在工作推进表完整视图供复核；本次未写入业务数据。

另复查 H06 本地验收环境：`docker info --format '{{.ServerVersion}}'` 无法连接 `dockerDesktopLinuxEngine` 命名管道，提示目标路径不存在。PostgreSQL 容器及迁移恢复演练仍无法启动，H06 继续未验收。

## 追加复核（2026-10-18，会议 AI 审核工作台）

在 6005 隔离验收副本中只读检查现存的项目会议草稿及其审核页面。该副本最新留存分析为 `project-meeting-agent-v4-batched-complete-analysis`，但记录时间为 2026-10-08，并非本次新上传触发的实时分析。页面保留 Word 的 17 项待办，其中 8 项映射到现有关键任务、9 项待核对归属；工作推进表预览显示 5 项建议，其中复选框当前预选。页面提供“审核通过并同步推进表”和“仅发布会议纪要”两个明确操作；本次没有执行发布或同步。

这证明现有留存样例可以呈现原文待办、任务匹配、未关联事项和选择性同步界面；它不证明本次代码版本对新上传文档的真实 AI 提取、人工选择与服务端写回闭环，也不构成会议内容业务签收。F01-F03 仍未完成端到端验收。复选框预选行为需在业务验收中确认是否符合“人工核对后选择”的口径。

## 追加复核（2026-10-18，会议实时分析失败与表单保留）

在临时预览 SQLite 中用合成会议文档新建一次分析，run 13 状态为 `failed`，错误码 `provider_error`，错误信息为 `provider invocation failed: AI upstream request failed`；对应 AI invocation log 137 的 capability 为 `meeting.analysis`，attempt 1，状态 `failed`，耗时 2ms，错误码 `AI_UPSTREAM_UNKNOWN`。同库历史 run 12 / invocation 136 曾在 2026-10-08 成功，不能代替本次实时服务验收，也不足以定位本次上游失败根因。未再次调用模型，未保存会议草稿或同步工作推进表。

失败后对新建会议表单做只读 DOM 检查：标题“隔离验收样例：任务进度核对会”和地点仍保留，日期输入值为空。代码中的 `followDocumentRun` 失败分支会切回输入步骤，并未显式重置表单；当前证据因此确认了用户可见的数据保留异常，但尚未解释受控表单状态与日期控件为何不一致。会议分析失败时的表单保留仍需先补充可重复的组件级复现，F01-F03 不通过。

## 追加复核（2026-10-18，会议失败后日期字段复现）

新增针对真实前端组件的定向测试，覆盖填写主题、ISO 日期 `2026-10-18`、地点，上传会议文档，新建分析任务后由状态接口返回 `provider_error` 的完整失败路径。当前组件在失败后保留三个输入值，测试通过；代码失败分支只清除待查 run、展示错误并切回输入步骤，没有重置 `form`。因此目前未能在组件层复现日期被清空，不能据此修改生产代码。先前隔离浏览器观察只记录了失败后的日期输入为空，未记录提交前该原生日期输入的 DOM 值；真实 AI 上游仍失败，日期字段异常的根因和可重复条件未定，F01-F03 仍未验收。

## 追加复核（2026-10-18，工作推进表 WBS 主视图）

在当前 6005 隔离预览中用有效项目 ID 4 打开工作推进表。浏览器 DOM 显示 26 项关键任务、0 项已完成、0 项延期、0 项未解决问题；重点工作可折叠分组，未汇报任务明确显示“尚未汇报”，并提供搜索、延期/风险/问题筛选和任务详情入口。1280×720 桌面视口下主表宽 1099px，页面 body 未发生横向溢出，截图检查列标题与行内容可见。该项目样例没有能验证异常状态的任务，因此本次只证明桌面布局和空进展提示，不证明延期/风险/问题数据准确，也不替代 C09。

V2 定向工作推进表测试 33 项通过；`npm.cmd run build` 通过 TypeScript 与 Vite 构建；`npm.cmd run check:bundle:dist` 通过包体积门槛。构建仍提示单个 chunk 超过 500kB，但 ExcelJS 位于非首屏动态 chunk，当前基线检查通过。

计划文档 `2026-09-20-project-work-progress-wbs.md` 写有可见 WBS 编号列；当前 `PlanTableViewV2` 主表使用重点工作分组，专项契约明确不显示“WBS编号”列。此处属于旧计划与当前界面范围的差异，本次验证不将 WBS 编号显示判为通过，也未擅自恢复该列。当前状态应以 2026-10-12 工作推进表优化评审和本分支代码为准，后续验收需明确 WBS 编号是否仍是业务要求。

## 追加复核（2026-10-18，待确认日期标识）

针对旧计划中 `due_kind=unknown/fuzzy`、无结构化截止日期的任务，工作推进表现在单独显示“待确认日期”，增加对应数量和快速筛选；延期统计仍只认明确到期且已过期的日期或人工标注延期，不从项目周期推断年份。手机任务卡也复用同一判断并显示提示。隔离预览项目 4 的 26 项未完成任务显示为待确认日期；筛选后 26 项任务匹配，延期筛选为 0 项，切回“全部”后 26 项恢复。已完成任务不计入待确认日期。该实现避免将日期未知误报为未延期或自动制造截止日期，但日期补全仍需业务人员核实，因此 C09 尚未取得业务验收通过。

验证：`tests/projectWorkProgressWbs.test.mjs` 11 项通过；推进表与移动任务卡定向单元测试 11 项通过；`npm.cmd run build` 与 `npm.cmd run check:bundle:dist` 通过。浏览器验证只使用隔离预览和合成项目数据，未修改业务库。项目总体仍有多项未验收，不能据此判定整体通过。

## 追加复核（2026-10-18，C08 风险标记状态即时同步）

复现到详情面板的风险标记保存/解除成功后，工作推进表父页面仍保留旧 `taskSubMap` 投影；关闭详情仅清理选中项，列表要等整页刷新才更新。已在风险写入成功后通知父页面重新读取子任务，并在加载失败时提示“风险已保存，但工作推进表刷新失败；请刷新页面重试”，避免误报风险写入失败。

修复后在全新隔离 SQLite 环境、合成管理员账号和 V2 内置浏览器复验：模拟 API 停止时保存失败，输入原因保留；恢复 API 后重试成功，详情显示“有风险”及原因并生成审计事件；推进表在关闭详情前即显示“有风险”，风险计数从 0 变为 1；“有风险”筛选命中该任务。再明确解除后审计记录新增“关键任务风险标记已解除”，同一筛选不再匹配该任务，恢复“全部”视图后行内风险状态清除。隔离库和合成数据，不涉及 6005/8011 绑定的数据库。

验证：风险标记定向单元测试 3 项通过；`npm.cmd run build` 的 TypeScript 与 Vite 构建通过（仍有既有单个 chunk 大于 500kB 的提示）；`git diff --check` 通过。**C08 仍为部分验证**：本次只覆盖内置浏览器与单一合成管理员角色，尚未在验收标准要求的目标正式浏览器/多角色环境完成权限矩阵与审计复核，不将其记为签收；项目 60 项验收表仍未签收。

## 追加验收（2026-10-18，C06 项目切换与导航上下文）

在 Edge 中使用临时隔离 SQLite 和合成管理员账号建立两个已进入执行阶段的样例项目：项目 1“隔离验收样例-风险标记-20261018”含任务“验证风险标记可创建与解除”；项目 2“隔离验收样例-项目切换-20261018”含不同任务“验证项目切换后任务范围一致”。从项目 2 的推进表切换到项目 1 后，地址变为 `?projectId=1`，选择器显示项目 1，表格只显示项目 1 的重点工作和任务；刷新后仍是项目 1。打开任务详情显示所属项目 1，关闭后仍回到项目 1。浏览器后退恢复 `?projectId=2` 和项目 2 专属任务，前进恢复 `?projectId=1` 和项目 1 专属任务。

后端访问日志与页面状态一致：切换时分别成功读取 `/api/tasks?project_id=1`、`/api/tasks?project_id=2` 以及对应项目的 `/api/subtasks?project_id=1/2`，均为 200；切换稳定后页面继续使用当前项目 ID。临时数据库启动明确显示 `protected: false`，未连接 6005/8011 业务数据库。

判定：**C06 本次隔离环境验收通过**。验收表 C06 行记录了操作结果、版本、执行人与日期，并由证据公式计入有效通过。边界：两个项目都由同一合成超级管理员建项与审核，没有证明生产账号或角色隔离。验收总览当前为 1/60 项有效通过、59 项未验收、P0 未完成 40 项；整批仍为“验收进行中”，签收结论保持“未签收”。
