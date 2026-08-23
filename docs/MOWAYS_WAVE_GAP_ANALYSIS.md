# Moways × McKinsey Wave 产品与系统差距分析

> 分析日期：2026-08-14
> 分析对象：当前仓库 `D:\项目整体备份\mowayspos-next-task` 的实际代码、数据模型、API、服务、前端路由/页面、AI/Agent、测试与现有文档。
> 分析目的：恢复 Moways 当前真实产品模型，判断其与 McKinsey Wave 类管理模型的差距，并给出不破坏现有语义边界的升级路线。
> 变更边界：本次只新增本分析文档，不修改业务代码、UI、数据库、迁移、PR 或提交。

## 1. Executive Summary

### 1.1 Moways 当前到底是什么

Moways 当前不是单纯的“项目任务管理工具”，也还不是完整的企业级 Portfolio/Transformation Management 平台。它的真实定位更接近：

> **以项目为边界、以 Workstream/KeyTask 为执行结构、以工作汇报/会议/附件为证据入口、以 AI 草稿和人工确认作治理闸门、以正式工作进度/成就/问题/计划回写为结果的项目执行治理平台。**

当前已经形成的主链路是：

```text
文字 / 语音 / 文档 / 会议
        ↓
AI 提取、匹配、证据校验、变更提案
        ↓
UpdateSubmission / Meeting Draft / Change Proposal
        ↓
负责人、统筹人、企业教练或 CEO 确认
        ↓
Task(Workstream) / SubTask(KeyTask) / Achievement / Issue / Schedule 回写
        ↓
通知、操作日志、Dashboard、项目关闭与归档
```

因此，Moways 已经具备“事实采集—审核—正式化”的局部执行闭环；但它尚未形成 Wave 类“战略目标—可衡量成功标准—项目执行—跨事项风险/依赖/决策—结果—业务影响/价值—管理动作”的管理执行闭环。

### 1.2 Wave-like 能力已有多少

已实现或接近可用的 Wave-like 能力包括：

- 项目生命周期治理：`draft → dispatched → pending_review → pending_kickoff → active → pending_close → ended → archived`。
- 项目角色与权限：公司 CEO、超级管理员、项目 CEO、负责人、统筹人、成员，并由后端做最终校验。
- 项目执行结构：Project → Workstream → KeyTask，并有周/月执行计划。
- AI 辅助事实提取：工作汇报、项目初始化材料、会议文本/文档均可形成草稿或分析结果。
- 人工确认和正式回写：AI 不直接写入核心业务表，确认中心负责审核、退回、转交、CEO 决策和写回。
- 会议变更集、启动会提案、证据片段、前后值校验、冻结快照、操作日志等可信治理机制。
- 问题/风险/待协调/需决策的统一事项入口，以及通知、提醒、待办队列。
- 项目关闭评估、未完成事项、剩余风险、交接计划、复盘材料和归档视图。

但这些能力主要服务于“单项目、单事项、单次写回”的执行治理，还没有上升为跨项目的经营管理驾驶舱。

### 1.3 项目管理能力与管理执行闭环的边界

当前 Moways 已经有两种不同成熟度的闭环：

1. **事项级闭环：已较明确。** 工作汇报/会议产生事实，AI 形成草稿，人确认后写入 Workstream、KeyTask、成就、问题和计划，并触发通知与日志。
2. **项目生命周期闭环：已较明确。** 立项、派发、负责人提交、企业教练审核、启动会确认、执行、关闭审核、结束和归档均有状态与权限边界。
3. **管理层闭环：尚未形成。** 系统不能稳定回答“哪个项目最需要管理注意、原因是什么、影响哪个目标/成功标准、谁应采取什么动作、何时复盘、实际结果与业务价值如何变化”。

因此，当前应称为“有治理能力的项目执行平台”，而不是 Wave 级“企业项目执行管理闭环平台”。

### 1.4 最重要的战略判断

Moways 不应复制 Wave 的复杂层级或完整企业转型模块。最有价值的升级方向是：

> **保留 Project → Workstream → KeyTask 的固定语义，沿着现有“证据采集—AI 感知—规则守门—Agent 提案—人工确认—正式回写”路径，把 Dashboard 升级为 Management Cockpit，并补齐目标/成功标准、风险/依赖/决策、结果/影响/价值之间的关联。**

Moways 最可形成差异化的资产不是再做一个任务树，而是把一线真实证据变成可审计、可解释、可行动的管理信号。

## 2. 当前实际业务模型

### 2.1 真实实体与固定语义

仓库的核心业务实体如下。当前没有 SQLAlchemy `relationship()` 形成的统一对象图，主要通过显式外键、ID、JSON 和兼容字段维持关系；这也是后续“证据可追溯”和跨对象管理分析的主要技术债。

| 业务语义 | 当前物理实体/字段 | 当前实际作用 |
|---|---|---|
| Project | `projects` | 项目名称、编码、目标描述、负责人、成员、日期、生命周期和关闭归档边界。 |
| Workstream（重点工作） | `tasks`，旧字段仍含 `special_project` | 项目下的一级执行工作，含负责人、完成标准、计划时间、状态和问题备注。 |
| KeyTask（关键任务） | `subtasks` | Workstream 下的关键任务，含负责人、状态和实际进展。 |
| Execution Plan | `execution_schedules`、月计划相关 API | KeyTask 的周/月计划、完成标准、预期输出、实际输出、延期原因、风险依赖和提醒。 |
| Work Report | `update_submission_batches`、`update_submissions` | 文字/语音/文件汇报的事实草稿与待确认记录，不等同于正式进度表。 |
| Meeting | `meetings` 及多类 transcript/analysis/revision 模型 | 会议原文、摘要、行动项、决策、风险、审阅、变更和版本记录。 |
| Issue | `issues` | 统一承载问题、风险、待协调、需决策，现阶段是类型化事项而非四套独立业务对象。 |
| Achievement | `achievements`、`achievement_submissions`、附件 | 已确认的成果/资产和来源归属，但还没有完整结果、影响、价值模型。 |
| Project Close | `project_close_requests` | 关闭摘要、目标结果、未完成事项、剩余风险、交接和复盘。 |
| Governance | `project_members`、成员变更申请、通知、`operation_logs` | 项目角色、审批权限、通知和审计。 |

必须保留的边界：

```text
Project
  └─ Workstream（tasks / 重点工作）
       └─ KeyTask（subtasks / 关键任务）
            └─ ExecutionSchedule（周/月执行计划）
```

当前没有独立的 Portfolio、Program、Initiative、Epic、Milestone、第四层 Workstream 或 SubTask 的再拆层。后续 Wave 对标不得把这些概念直接塞入现有产品，导致用户理解、API、权限和数据迁移同时失真。

### 2.2 项目生命周期与治理

当前代码以 `projects.status` 为主写字段，并兼容 `lifecycle_status` 与 `is_active`。现行代码的关键流程是：

- CEO/技术管理员派发项目；要求项目 CEO 和负责人等成员信息满足条件。
- 负责人提交项目资料和执行草稿，进入 `pending_review`。
- 企业教练/技术管理员审核通过后进入 `pending_kickoff`，而非正常情况下直接 `active`。
- 启动会 Agent 产生提案；企业教练逐项审核并确认启动后，事务内写入批准的结构、发布启动会纪要并切换 `active`。
- `active` 项目允许正式汇报、执行期计划和普通会议。
- `pending_close` 与 `ended` 进入业务写冻结；关闭审核会检查未完成材料、待决策问题、待确认成果、成员变更等。
- 归档后只读，保留时间线、会议、操作和资产视图。

权限模型也已超过简单的“管理员/普通用户”：全局角色负责全局查看、确认、分配和设置权限；项目角色负责项目范围内的日常操作；项目 CEO 主要承担方向、审核和教练角色，不等同于日常任务负责人。前端 guard 仅是体验层，后端权限和生命周期校验才是事实边界。

### 2.3 当前业务数据流

#### 工作汇报流

1. 用户从 `/work/submit` 提交文字、语音、上传内容，选择项目，并在需要时绑定 Workstream/KeyTask。
2. `/api/updates/extract` 调用 `task.extraction` 能力，生成 AI 草稿，包含任务匹配、状态、事实片段、证据和归属判断。
3. `/api/updates` 或批量接口只保存 `UpdateSubmission`，不会直接改正式 Workstream/KeyTask。
4. 确认中心按负责人、统筹人、企业教练/CEO 权限展示队列，允许确认、退回、转交和决策。
5. 确认后才写入 Workstream、KeyTask、Achievement、Issue 或计划，并发通知、写操作日志。

这条链路是 Moways 当前最成熟、也最值得保护的“可信写回链路”。

#### 会议流

当前存在并行路径：

- 普通会议分析：文本 → `meeting.analysis` → 结构化会议结果 → 会议修订/审阅。
- 进度审阅：比较会议或汇报与现有计划，生成进展差异与待处理项。
- 会议变更集：冻结项目快照，生成带前值、提议值、证据和校验信息的提案，显式审阅后写回。
- 启动会 Agent：`pending_kickoff` 项目专用，生成 `KickoffChangeProposal`，确认启动后原子应用。
- 当前工作树中的项目会议文档路径：上传 DOCX → 提取文本 → 生成 `ProjectMeetingRun`/Meeting 草稿 → 形成审阅包和变更提案。

会议侧“有结构但未完全收敛”：严格的项目会议 Agent 契约、只读工具、有限步数和证据约束已存在；但是当前文档运行入口仍直接调用 `_do_analyze` 的通用模型分析，尚未接入完整的 Agent processing、审计 trace 和统一后台运行状态。

### 2.4 当前数据语义债

- `tasks` 的物理名称与 `special_project` 等旧字段仍存在，产品语义与数据库命名未完全统一。
- Project 成员既有 `owners`/`collaborators` 字符串兼容字段，也有规范化的 `ProjectMember`，存在双写/兼容查询成本。
- Issue 同时承载问题、风险、待协调和需决策；类型规范化已有，但风险的概率、影响、触发条件、缓解方案等字段未形成独立结构。
- Meeting 的行动项、决策、风险等部分仍以 JSON/自由文本承载，不能可靠地连接到目标、计划、负责人和结果。
- `UpdateSubmission`、Meeting transcript、附件、Achievement、Issue 和 OperationLog 各自有来源字段，但还没有统一 Evidence 抽象。
- 许多对象有 ID 关联，但没有统一的“事实—对象—版本—证据片段—确认人—写回结果”关系。

## 3. 当前 AI 实际状态

### 3.1 AI 基础设施

`app/ai/contracts.py` 已建立能力键和模型类型：

- `meeting.analysis`
- `task.extraction`
- `project.init.analysis`
- `speech.realtime`

`AIService` 通过能力策略选择主模型和备用模型，支持凭据管理、重试、调用日志和技术管理员配置。AI 结果一般先进入草稿、分析运行或提案对象，再由业务流程决定是否落库。

### 3.2 已实际运行的 AI 能力

| 能力 | 实际状态 | 产出 | 是否直接改核心业务表 |
|---|---|---|---|
| 工作汇报提取 | 已实现 | 任务匹配、状态、进展、证据、归属判断草稿 | 否，需确认中心 |
| 项目初始化分析 | 已实现 | 项目初始化建议、Workstream/KeyTask 草稿、人员候选 | 否，需负责人提交/审核 |
| 普通会议分析 | 已实现但契约不完全统一 | 摘要、行动项、决策、风险等会议草稿 | 正常路径不应直接写执行表 |
| 启动会 Agent | 已实现为受控流程 | 冻结快照、启动会提案、审核和原子写回 | 仅在确认启动时写回 |
| 项目会议严格 Agent | Agent 引擎和工具层已实现，业务入口尚未完整接入 | 严格 envelope、证据片段、有限工具调用、执行计划更新提案 | 当前没有形成完整生产闭环 |
| 语音识别 | 能力已注册 | 实时 ASR/文本 | 否，后续进入汇报或会议流 |

### 3.3 AI、Rule、Agent 的实际边界

后续必须保持三分法：

| 类型 | 应负责的事情 | Moways 当前情况 |
|---|---|---|
| Rule | 权限、生命周期、状态转换、截止日期、负责人归属、数据完整性、证据格式、合法写回和法律/审计要求 | 已有较强基础，分散在权限、生命周期、确认、变更集和写回服务中；需要统一为可复用规则层。 |
| AI | 从文本/文档理解事实、判断语义、识别风险信号、解释偏差、推断影响候选 | 当前主要是提取、分类、匹配、标准化；对因果、影响、价值和跨项目优先级判断不足。 |
| Agent | 按项目上下文检索、调用只读工具、串联事实、生成提案、选择下一步动作 | 启动会和项目会议已有受控 Agent 设计；项目会议 Agent 目前尚未完成后台处理、审计、API 接入和统一写回。 |

必须坚持：AI/Agent 只产生事实草稿、解释或提案；Rule 负责守门；人工确认负责关键业务写回。不能以“Agent 已调用工具”作为“业务动作已完成”。

### 3.4 当前 AI 的主要缺口

1. 缺少统一的证据引用对象；自由文本 `evidence_quote` 与结构化候选并存，主流程不总是强制验证。
2. 缺少统一的事实类型契约，会议里的 action/decision/risk/issue 与正式 Issue/Task 的语义映射不够稳定。
3. 缺少项目健康度、偏差原因、目标影响、价值变化等管理分析能力。
4. 受控 Agent 引擎已有，但业务接入和运行审计没有闭合，不能把“代码存在”列为“企业 Agent 能力已上线”。
5. 现有 AI 调用日志能记录调用，但还不能完整回答某个提案使用了哪个快照、哪几次工具调用、哪些证据片段、哪个模型响应、谁确认以及最终写回了什么。

### 3.5 测试与证据边界

本次分析使用了两组定向后端测试作为代码事实的交叉验证：

- Agent 契约/工具边界、会议变更集、启动会 Agent 与写回：`60 passed`；
- 会议分钟、变更集写回、进度审阅、工作汇报写回、项目关闭：`49 passed`。

全量 `python -m pytest -q` 在当前工作树中因部分运行时/外部场景较慢，未在限定时间内完成，因此本报告不宣称全量测试通过。前端采用仓库现有的 Node contract test 脚本做了会议分钟、启动会、确认中心和工作汇报页面的定向验证；这些结果只用于确认现有链路的结构证据，不替代浏览器验收。

## 4. McKinsey Wave 管理模型

本报告把 Wave 作为能力参照，不把营销页面等同于可直接复制的产品规格。McKinsey 官方对 Wave 的描述集中在以下能力：以目标和结果为导向的项目/计划管理，端到端 Initiative 跟踪，实时单一事实源，识别问题和清除阻碍，明确所有权，风险预测，批准流程，高级报告，业务影响/价值跟踪，以及面向管理者的 AI coaching 和自定义 Agent。

参考： [Wave 官方概览](https://www.mckinsey.com/capabilities/transformation/how-we-help-clients/wave/overview)、[Wave 2：从创意到执行与实际影响](https://www.mckinsey.com/about-us/new-at-mckinsey-blog/riding-wave-2-into-the-digital-age)、[Wave on AWS：目标、执行与持续管理](https://www.mckinsey.com/about-us/new-at-mckinsey-blog/simplifying-ai-transformation-at-scale-wave-by-mckinsey-launches-on-aws-marketplace)、[McKinsey Ability to Execute](https://www.mckinsey.com/capabilities/transformation/how-we-help-clients/ability-to-execute)。

### 4.1 Wave 能力分层

可以把 Wave-like 管理模型归纳为六层：

1. **Outcome/Goal：** 从战略目标、成功标准和目标结果出发。
2. **Execution Structure：** 以 Initiative、Milestone、Workstream 等结构组织执行，支持进度预测。
3. **Reality/Evidence：** 汇集一线进展、财务/运营指标、风险和依赖，形成单一事实源。
4. **Management Sensemaking：** 找出偏差、瓶颈、根因、影响和需要升级的事项。
5. **Decision/Action：** 明确决策、责任人、截止日期、批准流程和下一步行动。
6. **Result/Impact/Value：** 追踪完成结果、业务影响、收益、价值实现和持续改进。

Wave 的重点不是多一层任务树，而是让管理者能从目标到执行、从执行到影响，持续知道“哪里偏了、为什么偏、谁处理、处理后是否改善”。

## 5. Wave–Moways 核心连接

### 5.1 当前连接图

```text
Moways 现状：
项目目标/描述
    → Workstream(tasks)
    → KeyTask(subtasks)
    → 周/月计划
    → 汇报/会议/附件事实
    → AI 草稿/提案
    → 人工确认
    → 正式进度/成就/问题/计划
    → Dashboard/关闭/归档

Wave 参照：
目标/成功标准
    → Initiative/执行结构/里程碑
    → 实际进展与预测
    → 风险/依赖/决策/行动
    → 管理注意与升级
    → 结果/影响/价值
    → 持续管理与教练
```

Moways 已覆盖 Wave 的“执行结构、事实入口、审批治理、部分行动回写”，但缺少 Wave 最关键的管理解释层和结果价值层。

### 5.2 Moways 现有优势

- **证据入口贴近真实工作。** 不是只填状态，支持文字、语音、文件和会议原文。
- **写回边界清晰。** `UpdateSubmission` 与确认中心将 AI 草稿和正式表分开，避免模型直接破坏主数据。
- **项目治理完整度较高。** 角色、项目生命周期、启动会、关闭审核、冻结写入、通知和日志均有实现。
- **变更提案可信机制较好。** 冻结快照、前值、后值、证据范围、校验和显式确认是成为 Agent 平台的良好基础。
- **已有企业教练/CEO 角色语义。** 这比通用任务系统更接近“组织执行治理”。
- **数据沉淀方向正确。** 工作进度、成就、问题、会议和归档逐渐形成项目执行档案。

## 6. 核心差距

### 6.1 目标与成功标准不是一等公民

Project 有 `objectives`、描述、日期和完成标准，但没有可查询、可追踪、可被实际证据引用的 Goal/Success Criteria 结构。当前“完成”更多是任务状态或人工描述，不能稳定回答“项目完成是否等于目标达成”。

建议先把 Goal/Success Criteria 做成 Project 的结构化语义或 JSON/字段扩展，不急于新增 Portfolio/Program/Initiative 层。

### 6.2 Milestone 缺失，但不能通过新增第四层解决

`ExecutionSchedule` 已承载计划日期、预期输出、完成标准、实际输出、延期原因和风险依赖，具有弱 Milestone 能力；但没有统一的 milestone 标识、验收状态、预测日期、关键路径或与成功标准的关联。

建议把“里程碑”定义为 KeyTask/ExecutionSchedule 的一种业务属性或视图，不新增一棵任务树。

### 6.3 Risk、Dependency、Decision、Action 没有统一管理对象

Issue 已能区分“问题、风险、待协调、需决策”，但四者仍主要共享一张表。会议里的风险/决策/行动项又存在 JSON 形式，造成：

- 不能可靠统计某个目标受哪些风险影响；
- 不能把依赖的提供方、被依赖方、阻塞关系和解除条件结构化；
- 不能追踪一个决策从提出、批准到执行结果；
- 不能把行动项统一归属到 KeyTask、负责人、截止日和证据。

### 6.4 Evidence 是分散能力，不是统一抽象

当前已有 transcript source/revision、附件、submission 原文、AI 结果、会议证据、变更集证据和操作日志，但缺少跨来源统一的 Evidence Envelope。结果是同一事实在不同流程中的可信级别、引用位置、版本和确认状态难以比较。

这不意味着必须立即新增 `evidence` 表。第一阶段可以以现有来源为底层，建立统一 Pydantic/服务层抽象；当需要跨来源检索、留存、权限、哈希和版本查询时再物化为表。

### 6.5 Dashboard 还不是 Management Cockpit

`/api/dashboard/overview` 以及前端 Dashboard 已能展示项目卡片、任务数量、完成率、成就、开放问题、待确认、近期任务和延迟任务。这是 Reporting Dashboard + Work Queue。

它还不能稳定输出管理者需要的五元组：

```text
注意对象 → 原因/证据 → 受影响目标或计划 → 责任人 → 下一步动作/升级人
```

因此当前 Dashboard 能告诉用户“有多少未完成”，但不能可靠告诉用户“哪个项目最值得现在介入、为什么、介入后要做什么”。

### 6.6 结果、影响、价值层缺失

Achievement 是成果资产库，但不等于 Result/Impact/Value。Project close 有 `objective_result`、`unfinished_items`、`remaining_risks` 和复盘字段，是很好的结果入口，但目前是关闭阶段文本，不是从执行中持续计算的管理数据。

需要区分：

- Result：交付了什么、是否达到完成标准；
- Impact：对目标、业务指标或组织能力产生了什么影响；
- Value：影响是否转化为可量化收益、成本节约、收入、质量或能力提升。

## 7. Moways 强项

### 7.1 可信写回链路

“AI 提取不入主表，人工确认后写回”是当前最强的产品原则。确认中心既有角色化队列，也有批次、卡片、状态、通知和审计，适合作为未来所有 Agent 输出的统一治理闸门。

### 7.2 启动会和关闭流程

`pending_kickoff` 使项目在执行前拥有真实的启动门槛；`pending_close`/`ended` 的冻结和关闭评估使项目不会被简单标记完成。这两端治理是很多轻量 PM 工具缺失的能力。

### 7.3 会议变更集和证据校验

变更集不是把会议结果直接覆盖到任务表，而是保留快照、前后值、证据引用、目标校验、成员校验和审核状态。这是把“会议纪要”升级为“可审计管理动作”的正确方向。

### 7.4 角色语义

企业 CEO、企业教练、项目 CEO、负责人、统筹人和成员不是装饰性角色，而是已经参与项目启动、确认、审批、关闭和日常写回。后续 Management Cockpit 可以自然地按角色产生不同注意队列。

## 8. 关键缺口清单

按影响排序，最需要补齐的不是更多页面，而是以下管理语义：

1. **统一 Evidence Envelope。** 让任何事实都能引用来源、版本、精确片段、对象、提交人、确认人和写回结果。
2. **目标/成功标准可追踪化。** 不改变任务层级，先让项目目标能够被计划、结果和管理注意引用。
3. **Plan vs Reality。** 计划日期/完成标准/预期输出与实际输出/延期/风险的比较要统一。
4. **Attention/Cause/Impact/Action。** 把 Dashboard 从统计页升级为管理注意中心。
5. **风险/依赖/决策/行动的最小结构。** 先统一语义和关系，再决定是否各自建表。
6. **Agent 生产化接入。** 当前严格 Agent 代码必须接入后台运行、审计、模型调用记录、失败重试和变更集，才能成为业务能力。
7. **结果/影响/价值。** 先做结果和目标影响，再在有真实业务数据时做收益/财务/价值层。

## 9. Goal / Milestone / Risk / Dependency / Result / Value

### 9.1 推荐的最小语义映射

| 概念 | Moways 当前承载 | 判断 | 推荐方向 |
|---|---|---|---|
| Goal | `Project.objectives` 等文本 | 仅有文本承载 | 先结构化为项目目标集合或目标字段，不新增 Portfolio 层。 |
| Success Criteria | Task 完成标准、SubTask/计划完成标准、关闭目标结果 | 部分实现 | 统一字段语义，并允许引用 Goal。 |
| Project | `projects` | 已实现 | 保持为顶层业务边界。 |
| Workstream | `tasks` | 已实现 | 保持重点工作语义，逐步清理旧命名。 |
| KeyTask | `subtasks` | 已实现 | 保持关键任务语义，不新增第四层。 |
| Milestone | ExecutionSchedule/完成标准 | 数据承载但能力不完整 | 以 KeyTask/计划属性实现里程碑视图。 |
| Risk | `issues.issue_type=风险`、会议风险 JSON | 部分实现 | 先增加概率/影响/触发/缓解/状态等最小结构。 |
| Dependency | `risk_dependency` 文本及相关任务字段 | 弱承载 | 先做关联类型和阻塞/被阻塞关系，避免先做复杂网络图。 |
| Decision | `issue_type=需决策`、会议决策 JSON、CEO 决策流 | 部分实现 | 固化提出—评估—批准—执行—结果链路。 |
| Action | Task/SubTask/ExecutionSchedule/会议行动项 | 部分实现 | 统一责任人、截止日、来源、状态和回写目标。 |
| Result | 实际输出、成果、关闭目标结果 | 部分实现 | 形成计划结果与验收结果的结构化对比。 |
| Impact | 尚无统一字段 | 未实现 | P1 先做目标影响/项目健康影响，量化指标后置。 |
| Value | 尚无统一模型 | 未实现 | 仅在业务有可信指标来源后做 P2，不能先做空泛 ROI。 |

### 9.2 Evidence 是否需要新表

推荐采用两阶段策略：

**P0：不新增表，先建统一抽象。** 在服务层定义 EvidenceRef/EvidenceEnvelope，统一包装：

- `source_type`：汇报、会议、文档、附件、操作日志、外部导入；
- `source_id` 与 revision/run ID；
- 原始内容哈希或版本标识；
- 精确 quote/span/locator；
- 关联 Project、Workstream、KeyTask、Issue、Achievement 或 proposal；
- evidence status：原始、AI 提取、人工确认、已回写、被撤回；
- 提交人、确认人、时间和权限范围。

**P1：在查询和留存压力出现时物化。** 如果需要跨来源检索、统一权限、证据覆盖率统计、保留策略、哈希校验或审计导出，再新增 `evidence_refs`/`evidence_links` 等表。新表的目的应是统一 provenance，不应创建新的业务层级。

## 10. Dashboard → Management Cockpit

### 10.1 当前 Dashboard 能回答什么

- 项目数量、任务数量、完成数量和完成率；
- 开放问题、高优先级问题、待 CEO 决策；
- 待确认提交、近期任务、延迟任务；
- 近期成就和项目卡片；
- 全局、我的项目、项目范围过滤。

### 10.2 Management Cockpit 必须新增什么

Cockpit 不应只是增加图表，而应围绕“注意队列”组织：

| Cockpit 卡片 | 计算来源 | 管理输出 |
|---|---|---|
| 项目健康与趋势 | 生命周期、计划 vs 实际、逾期、问题、汇报新鲜度 | 健康状态、趋势和置信度 |
| 当前最需介入项目 | 逾期、阻塞、待决策、关键任务、证据缺失、目标影响 | 为什么现在要看 |
| 目标受影响 | Goal/Success Criteria 与 Workstream/Issue/Decision 关系 | 哪个目标可能偏离 |
| 风险与依赖 | Issue、风险字段、计划风险依赖、阻塞关系 | 触发条件、影响、缓解和升级人 |
| 待决策 | 需决策事项、CEO/教练队列、截止时间 | 决策上下文与建议下一步 |
| 待执行动作 | 确认中心、会议行动、提案、逾期计划 | 责任人、截止日、来源和状态 |
| 证据新鲜度 | 最近汇报/会议/附件与证据覆盖 | 哪些判断缺少一手事实 |
| 结果/影响 | 完成标准、实际输出、目标结果和已确认成果 | 交付结果与目标影响变化 |

### 10.3 建议的 Cockpit 输出契约

每条管理注意至少返回：

```json
{
  "attention_type": "deadline_risk",
  "severity": "high",
  "project_id": 1,
  "target_type": "key_task",
  "target_id": 12,
  "reason": "计划日期已过且最近一次汇报缺少实际输出",
  "evidence_refs": [],
  "impact_target_id": null,
  "owner_id": 3,
  "recommended_next_action": "负责人补充实际输出并确认延期原因",
  "escalation_role": "project_ceo",
  "confidence": "rule_based"
}
```

其中原因、截止、权限、责任人和状态由 Rule 计算；影响候选和建议解释可由 AI 辅助；任何写回动作仍通过确认中心或变更集。

## 11. Evidence 模型

### 11.1 Evidence 的产品定义

Evidence 不是“在 AI 结果里多放一段引用”，而是“支撑一条事实或管理判断的可审计来源”。一条 Evidence 应能回答：

1. 来源是什么；
2. 原文版本是什么；
3. 原文哪一段支持该事实；
4. 该事实关联哪个项目对象；
5. 是 AI 提取、人工提供还是系统计算；
6. 谁确认过；
7. 是否已写入正式业务对象；
8. 后续是否被撤回、修订或失效。

### 11.2 当前 Evidence 能力等级

- 会议 transcript source/revision/run：已有来源和版本基础。
- 工作汇报原文、批次、提交人、AI/human JSON：已有来源，但跨实体引用不统一。
- 变更集和启动会：证据约束最强，已有片段校验和前后值。
- 附件与成就：有来源关联，但缺少统一证据定位和确认链。
- Dashboard 统计：多数是聚合结果，缺少可下钻到原始事实的原因链。

### 11.3 P0 证据覆盖率

建议在不新增层级的前提下，先度量：

- 任务进度事实有证据的比例；
- AI 提案有精确证据片段的比例；
- 已写回事项可追溯回原始提交/会议的比例；
- 管理注意可追溯到 Rule 输入或 Evidence 的比例；
- 被退回、撤回和修订事实的可见比例。

没有 Evidence 质量指标，Management Cockpit 容易变成另一个不可解释的评分页。

## 12. Rule / AI / Agent 边界

### 12.1 Rule 必须做什么

- 权限和项目范围；
- 生命周期和冻结；
- 状态机及合法转换；
- 负责人、成员、审批人校验；
- 截止日期、逾期、提醒和通知；
- KeyTask/Workstream 绑定完整性；
- Evidence span 是否来自指定原文；
- 变更集前值是否仍然有效；
- 写回是否需要人工确认；
- 关闭前置条件和审计要求。

### 12.2 AI 可以做什么

- 从文字/文档中提取事实；
- 对象匹配和重复合并建议；
- 将自然语言映射到已有业务类型；
- 解释计划与实际差异；
- 识别风险/依赖/决策候选；
- 生成项目健康度的自然语言解释；
- 提供目标影响和下一步动作候选，但标明依据和置信度。

### 12.3 Agent 可以做什么

- 在一个冻结项目快照中检索 Project、成员、Workstream、KeyTask、计划、近期汇报和会议；
- 串联多个只读工具，构造事实链；
- 生成会议结果、进展判断、风险或变更提案；
- 选择下一步“需要谁确认什么”，但不能跳过治理闸门；
- 在明确的工具白名单、步数上限、证据约束和审计上下文下工作。

### 12.4 不应由 AI/Agent 直接决定

- 改变项目生命周期；
- 直接确认正式工作进度；
- 自动转移负责人或成员；
- 关闭项目、关闭风险或批准 CEO 决策；
- 在没有 Evidence 的情况下补全目标、结果或价值；
- 将自然语言中提到的人名直接变成系统用户；
- 将不确定的会议行动项直接写入 KeyTask。

## 13. Change Proposal & 确认中心升级

当前确认中心已经是 Moways 的核心治理产品，应从“AI 提交审核页”升级为“Change Proposal Center”。

### 13.1 当前已有

- 负责人确认、统筹人反馈、CEO 决策等状态；
- 批次与卡片级操作；
- 任务/关键任务/成就/问题写回；
- 会议变更集和启动会变更提案；
- 审核预览、通知和操作日志。

### 13.2 建议升级

每个提案统一显示：

```text
事实来源 → 证据片段 → 当前值 → 建议值 → 影响对象 → 影响说明
       → 规则校验 → 责任人 → 审核人 → 写回动作 → 写回结果
```

提案类型可以包括：

- 进度更新；
- KeyTask 创建/修改；
- 执行计划日期或实际输出变化；
- 风险/依赖/决策/行动项；
- 目标或成功标准关联；
- 会议纪要结构化结果；
- 项目健康度解释和升级建议。

但不建议一次性让确认中心承载所有新实体。P0 先统一 Proposal Envelope 和 EvidenceRef，再按已有写回服务扩展；P1 再加入目标影响和跨对象变更；P2 才考虑复杂价值或资源调整提案。

## 14. 完整能力矩阵

| Wave 能力 | Wave 强度 | Moways 当前状态 | 主要差距 | 是否值得补齐 | 优先级 | 改造成本 | 现有数据结构影响 |
|---|---|---|---|---|---|---|---|
| Goal | 核心能力 | 部分实现 | Project objectives 是文本，缺少可追踪目标 | 是 | P0/P1 | 中 | Project 字段/服务层 |
| Success Criteria | 核心能力 | 部分实现 | 分散在 Task/SubTask/Close 文本 | 是 | P0 | 中 | 统一字段和引用 |
| Project | 核心能力 | 已实现 | 跨项目管理视图弱 | 是 | P0 | 低-中 | 保持现有表 |
| Workstream | 强执行能力 | 已实现 | 旧命名和兼容字段 | 是 | P0 | 中 | 语义清理，不改层级 |
| KeyTask | 强执行能力 | 已实现 | 绑定和计划/结果关系需统一 | 是 | P0 | 中 | SubTask/外键 |
| Milestone | 核心执行能力 | 仅有数据承载 | 无统一里程碑语义和预测 | 是 | P1 | 中 | KeyTask/计划属性优先 |
| Update | 现实输入能力 | 已实现 | 计划 vs 实际关联和证据统一不足 | 是 | P0 | 中 | UpdateSubmission 扩展 |
| Meeting | 现实输入能力 | 已实现但并行 | 普通分析、文档 Agent、启动会路径未完全收敛 | 是 | P0 | 中-高 | Run/Revision/Proposal |
| Evidence | 核心可信能力 | 部分实现 | 无统一 Envelope/跨来源查询 | 是 | P0 | 中 | 先服务层，后可新表 |
| Achievement | 结果承载 | 已实现 | 不是 Result/Impact/Value | 是 | P1 | 中 | Achievement 关联扩展 |
| Issue | 管理事项 | 已实现 | 问题/风险/协调/决策共表且字段弱 | 是 | P0/P1 | 中 | Issue 最小字段扩展 |
| Risk | 核心管理能力 | 部分实现 | 缺概率、影响、触发、缓解、趋势 | 是 | P1 | 中 | Issue 类型化扩展 |
| Dependency | 核心管理能力 | 弱承载 | 主要是文本 risk_dependency | 是 | P1 | 中-高 | 关联表或关系字段 |
| Decision | 核心管理能力 | 部分实现 | 提出到批准到执行结果链路不统一 | 是 | P1 | 中 | Issue/Proposal 优先 |
| Action | 核心执行能力 | 部分实现 | 会议行动项与计划/责任人关系不稳定 | 是 | P0/P1 | 中 | Proposal/KeyTask/计划 |
| Result | 核心结果能力 | 部分实现 | 实际输出与目标结果未持续关联 | 是 | P1 | 中 | 计划/成就/关闭字段 |
| Impact | Wave 高价值能力 | 未实现 | 无目标影响和指标关联 | 是 | P1 | 高 | 新字段/指标关系 |
| Value | Wave 高价值能力 | 未实现 | 无可信收益/财务/业务指标 | 有条件 | P2 | 高 | 后置指标模型 |
| Reporting Dashboard | 辅助能力 | 已实现 | 统计多，解释和下钻少 | 是 | P0 | 低-中 | API 聚合扩展 |
| Management Cockpit | 核心管理能力 | 未实现 | 无注意—原因—影响—行动闭环 | 是 | P0 | 中-高 | 新聚合服务/页面 |
| AI Extraction | 辅助/输入能力 | 已实现 | 证据和契约统一不足 | 是 | P0 | 中 | AI result/Envelope |
| AI Analysis | 核心感知能力 | 部分实现 | 偏差、影响、价值分析弱 | 是 | P1 | 中-高 | Analysis Run/解释 |
| Agent | Wave 增强能力 | 受控代码存在，业务未完全接入 | 缺后台运行、审计、集成和统一审批 | 是 | P0 | 高 | Run/Trace/Proposal |
| Rule Engine | 治理基础 | 已实现但分散 | 规则未集中、难复用、难解释 | 是 | P0 | 中 | 服务层/规则输出 |
| Human Confirmation | 治理核心 | 已实现 | 需要统一所有 Proposal 类型 | 是 | P0 | 中 | 确认中心扩展 |
| Governance/Cadence | 核心管理能力 | 部分实现 | 项目级较强，跨项目管理节奏弱 | 是 | P1 | 中 | 通知/队列/报表 |

状态定义：`已实现` 表示有实际代码/API/页面/测试证据；`部分实现` 表示存在实体或流程但尚未形成完整业务能力；`仅有数据承载` 表示有字段或表但缺管理语义；`未实现` 表示当前没有可用闭环；`受控代码存在，业务未完全接入` 不等于已上线 Agent 能力。

## 15. P0 / P1 / P2 路线图

### P0：先建立可信管理注意闭环

1. **Evidence Envelope。** 在现有 UpdateSubmission、Meeting、附件、Issue、Achievement 和 OperationLog 之上统一来源、版本、精确片段、对象和确认状态。
2. **统一 Proposal/Change Set。** 将工作汇报、会议变更、启动会提案和未来 Agent 结果统一为“建议值—证据—规则校验—审核—写回”模型。
3. **Management Cockpit v1。** 用现有数据计算健康、逾期、阻塞、待决策、证据缺失和确认积压，输出注意原因、责任人、影响对象和下一步动作。
4. **补强计划 vs 实际。** 统一 ExecutionSchedule 的计划日期、预期输出、实际输出、延期原因、风险依赖和最近证据。
5. **整合项目会议 Agent。** 补齐后台处理服务、运行抢占、失败重试、模型/工具 trace、审计字段、结果规范化和变更集生成，再接入当前文档运行入口。
6. **规则集中化。** 将权限、生命周期、状态、目标绑定、Evidence 合法性和写回前置条件抽成可测试规则服务。
7. **减少主流程猜测。** 项目/Workstream/KeyTask 绑定应成为正式汇报的主路径，现有项目推断和旧字段兼容逻辑应降级为迁移兼容，而不是新的事实来源。

P0 的产品结果：管理者第一次能看到“现在最需要介入什么，以及证据和下一步动作是什么”；AI/Agent 的结果第一次能通过同一确认中心安全写回。

### P1：从注意队列进入管理执行闭环

1. Project 目标和 Success Criteria 结构化，并与 Workstream/KeyTask/Issue/Result 建立引用。
2. 用 KeyTask/ExecutionSchedule 属性实现 Milestone 视图、预测日期和完成验收，不新增第四层。
3. 将 Issue 的风险/依赖/决策/行动最小结构固化，建立阻塞、被阻塞、升级和结果关联。
4. 将项目健康度从静态规则升级为 Rule + AI 解释：趋势、证据新鲜度、偏差原因和可能目标影响。
5. 建立企业教练、项目 CEO、负责人和统筹人的角色化管理节奏与复盘队列。
6. 将 Achievement 与 Result/Success Criteria 关联，能回答“成果是否满足目标”。
7. 把 Agent 扩展为项目分析和下一步行动提案，但仍只读检索、受限工具、人工确认写回。

### P2：在有业务数据后扩展价值管理

1. 业务指标、收益、成本、质量、交付效率和能力提升的 Value 模型。
2. 跨项目优先级、容量、资源和依赖网络；只有组织确实需要 Portfolio/Program 管理时才考虑独立层级。
3. Benchmarking、财务追踪、收益实现预测和高阶预测分析。
4. AI coaching：围绕具体证据给出管理者可执行的教练建议，并保留理由、风险和人工采纳记录。

## 16. 不建议复制 Wave 的能力

### 16.1 不复制新的层级体系

不建议引入 Portfolio → Program → Initiative → Epic → Task → SubTask，或把 Milestone 强行做成新的任务层。Moways 已经通过 Project → Workstream → KeyTask 建立了固定产品语义，新增层级会引发：

- 用户不知道任务应放在哪一级；
- 当前 API、确认中心、权限和 Dashboard 全部需要重构；
- 旧数据迁移和字段兼容成本高；
- 实际管理问题没有因此解决。

### 16.2 不先复制复杂财务/资源能力

如果当前没有稳定的财务、容量、人员工时和收益数据，先做复杂 financial tracking、资源优化和 ROI 计算只会制造伪精确。应先做好证据、结果和目标影响，再在真实数据源成熟时扩展。

### 16.3 不复制“自上而下替代一线事实”的模式

Moways 的差异化来自一线汇报、会议原文、附件和人工确认。不能为了像 Wave 而只保留管理者填报的状态，或让 AI 用目标文本替代现场事实。

### 16.4 不做无边界自治 Agent

不建议让 Agent 直接改项目状态、创建/关闭任务、转移负责人、关闭风险或确认成果。Moways 现有确认中心、变更集和启动会审核是治理资产，应继续保留。

## 17. 推荐的目标 Moways 业务模型

### 17.1 目标模型

```text
Project
  ├─ Goal / Success Criteria（先做项目内结构化语义）
  ├─ Workstream（tasks）
  │    └─ KeyTask（subtasks）
  │          └─ ExecutionSchedule / Milestone 属性
  ├─ Evidence Envelope（统一包装现有来源）
  ├─ Issue / Risk / Dependency / Decision / Action（最小类型化关系）
  ├─ Result / Achievement
  └─ Impact / Value（后置）

Evidence → AI Sense → Rule Gate → Agent Proposal → Human Confirmation → Writeback
                         ↓
              Management Cockpit / Role Queue / Audit
```

### 17.2 推荐的产品定位

> **Moways 是证据驱动、规则守门、AI 感知、Agent 提案、人工确认、项目闭环回写的企业项目执行与管理平台。**

这一定义比“AI 项目管理工具”准确，也比“Wave 的本地复制版”更符合当前资产和演进方向。

### 17.3 目标工作循环

```text
设定项目目标与成功标准
  → 组织 Workstream/KeyTask/计划
  → 采集真实证据
  → 规则识别逾期、缺失和阻塞
  → AI 解释偏差、影响和风险候选
  → Agent 检索上下文并提出变更/行动
  → 负责人/教练/CEO 确认
  → 正式写回与通知
  → 追踪结果、目标影响和后续管理动作
```

## 18. DB / API / 页面影响

以下是按推荐事项划分的影响范围。字母表示：A=产品语义，B=前端展示，C=后端字段，D=新实体/表，E=规则/服务，F=AI，G=Agent。

| 建议 | 影响类型 | DB/API 影响 | 页面影响 | 备注 |
|---|---|---|---|---|
| Evidence Envelope | A/C/E，后续可 D | 新增统一 schema/服务；现有来源 API 增加 EvidenceRefs；P1 再评估物化表 | 汇报、会议、确认中心显示来源、片段、版本 | P0 不必立即新表 |
| Proposal/Change Set 统一 | A/C/E | 统一提案 envelope、状态和写回结果；复用现有变更集/确认 API | 确认中心升级为证据+影响+动作审阅 | 不改变 Project 层级 |
| Management Cockpit | A/B/E | Dashboard overview 增加 attention、reason、impact、owner、next_action | 新增管理注意区、下钻和角色队列 | 不是单纯增加图表 |
| Goal/Success Criteria | A/C，可能 D | 先扩 Project 字段或结构化 JSON；后续按查询需求建表 | 项目详情、项目提交、Cockpit、关闭页 | 不新增 Portfolio/Program |
| Milestone | A/C/E | 优先扩 KeyTask/ExecutionSchedule 属性和计算服务 | 计划视图/项目时间线 | 不新增第四层 |
| Risk/Dependency/Decision/Action | A/C/E，部分可 D | Issue 最小字段扩展；跨对象关系成熟后再拆关联表 | Issue 中心、会议审阅、确认中心、Cockpit | 先统一语义再拆表 |
| Result/Impact | A/C/F | Result 先复用实际输出/成果/关闭结果；Impact 后置结构化 | 项目详情、关闭归档、Cockpit | Value 需真实指标来源 |
| Meeting Agent 生产化 | E/F/G/C，可能 D | 新增 processing、trace、run audit、模型/工具记录；接入现有 ProjectMeetingRun | 文档审阅工作台、运行状态、错误/重试 | 当前引擎不能直接算已上线 |
| Rule 服务集中化 | E | 抽出 lifecycle/permission/evidence/writeback 校验；API 行为保持兼容 | 展示规则原因和阻断信息 | 先服务层，少改页面 |
| Role Cockpit | B/E | 复用现有角色和队列，增加角色化聚合 API | CEO/教练/负责人/统筹人不同入口 | 不新增角色体系 |
| Value 管理 | C/D/F | P2 才考虑指标、收益、财务或外部数据表 | 价值看板、收益复盘 | 当前不应提前建设 |

### 18.1 需要特别注意的代码/文档差异

- 旧的 `N4_P0_BASELINE_MAIN_FLOW_STAGE_MAP.md` 与部分审计文档仍描述“审核通过直接 active”或“没有 pending_kickoff”；当前代码和 `PROJECT_FLOW_BOUNDARY.md` 已实现 `pending_kickoff` 与启动会确认。以代码和最新边界文档为准，旧文档应视为过期审计材料。
- `meetings.py` 的当前通用分析路径仍存在把 `confirmed_items` 映射到 `risk_items_json` 的字段风险；现有会议 Agent 差距文档已明确列出，该问题不能被“有会议 Agent”掩盖。
- `project_meeting_agent.py`、contracts 和 tools 已存在且定向测试通过；但缺少计划中列出的 `project_meeting_agent_processing.py`、后台运行持久化、完整 API 集成和 Agent audit migration。因此报告将其标为“受控代码存在、业务未完全接入”。
- 当前工作树有大量未提交改动，特别是会议/项目会议工作流。上述判断基于当前工作树实际代码，并不把未提交改动误称为稳定主干能力。

## 19. 结论

Moways 当前已经走过“任务表 + Dashboard”的阶段：它有项目生命周期、项目角色、Workstream/KeyTask 执行结构、工作汇报、会议、AI 草稿、人工确认、正式回写、问题/成就、通知、关闭与归档。其核心产品资产是“真实工作证据经过治理后进入正式执行数据”。

但 Moways 尚未达到 Wave 类企业管理执行平台的关键标准：

- 目标和成功标准尚未成为可追踪结构；
- 里程碑、风险、依赖、决策、行动之间缺少统一关系；
- Evidence 分散，管理判断难以下钻；
- Dashboard 仍主要是统计和队列，不是 Management Cockpit；
- 结果、影响、价值未形成持续管理层；
- Agent 代码已有边界，但生产化接入和业务写回闭环尚未完成。

下一阶段不应从“复制 Wave 的对象层级”开始，而应从现有最强链路继续推进：

> **用统一 Evidence 支撑事实，用 Rule 守住权限/状态/写回，用 AI 解释语义和偏差，用受控 Agent 检索上下文并提出行动，用确认中心完成治理，最后把结果和目标影响反馈到 Management Cockpit。**

最终目标不是让 Moways 看起来像 Wave，而是让 Moways 成为更适合自身组织运行方式的：

> **AI 驱动的企业项目执行与管理闭环平台。**
