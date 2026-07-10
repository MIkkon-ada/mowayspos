# Moways-SOP 语义契约文档

> 本文档是 Moways-SOP 项目的命名与语义总准则，约束前端展示名、后端字段名、数据库表名、接口值、权限角色之间的对应关系。
> 任何新增页面、接口、字段、角色前，必须先对照本文档确认归属的业务对象与数据权威源。

| 项 | 值 |
|---|---|
| 文档版本 | S1 |
| 生效范围 | 前端 `frontend/`、后端 `bowei_ai_dashboard/`、数据库、接口 |
| 前序工作 | N1 产品名统一、N2 三层结构展示口径统一、N3 角色文案统一、people/project_members 一致性修复 |

---

## 1. 产品命名口径

| 概念 | 标准文案 | 说明 |
|---|---|---|
| 产品英文名 | `Moways-SOP` | 用于 FastAPI title、日志、产品标识 |
| 中文系统名 | `Moways 项目协同平台` | 用于登录页标题、侧边栏副标题等系统通用位置 |
| 当前案例项目名 | `博维 AI 升级项目驾驶舱` | 仅作为具体项目/案例名称，**不作为系统通用名** |

### 弃用名称（禁止再作为系统通用名出现）

- `Moways-POS` —— 已替换为 `Moways-SOP`
- `项目运营管理系统` —— 已替换为 `Moways 项目协同平台`
- `AI项目驾驶舱` —— 已替换为 `Moways 项目协同平台`（系统位）；案例名中的"驾驶舱"仅保留在具体项目名称里

### 前端集中常量

产品名、系统名、案例名、业务对象名、入口名统一收敛到：

```
frontend/src/domain/displayNames.ts
```

包括：`PRODUCT_NAME_EN`、`SYSTEM_NAME_CN`、`CASE_NAME`、`WORKSTREAM_LABEL`、`KEY_TASK_LABEL`、`AI_CONFIRM_CENTER_LABEL`、`WORK_REPORT_LABEL`。

---

## 2. 业务对象语义表

| 业务对象（展示名） | 模型类 | 数据库表 | 后端路由 | 前端展示 |
|---|---|---|---|---|
| 项目 | `Project` | `projects` | `projects.py` | 项目 |
| 重点工作 | `Task` | `tasks` | `dashboard.py` / `updates.py` | 重点工作 |
| 关键任务 | `SubTask` | `subtasks` | `updates.py` / `confirmations.py` | 关键任务 |
| 工作汇报 | `UpdateSubmission` | `update_submissions` | `updates.py` | 工作汇报 |
| AI 确认中心 | — | — | `confirmations.py` | AI 确认中心 |
| 成果库 | `Achievement` | `achievements` | `achievements.py` | 成果库 |
| 问题与决策 | `Issue` | `issues` | `issues.py` | 问题与决策 |

### 特别说明

- **`tasks` 表当前业务语义是"重点工作"**，是第二层业务对象。技术字段名 `task` 保留，但用户可见文案统一为"重点工作"。
- **`subtasks` 表当前业务语义是"关键任务"**，是第三层业务对象。技术字段名 `subtask` 保留，但用户可见文案统一为"关键任务"。
- **`subtask` 不是第四层"子任务"**。项目中不存在"子任务"这一业务层级；注释、文档、UI 中禁止再用"子任务"指代 `subtasks`。
- `update_submissions` 承载工作汇报提交（语音/文字），其 `source_type` 值见第 5 节。
- AI 确认中心（`confirmations.py`）是对工作汇报提交进行确认/退回/转交/企业教练决策的流转中枢，不是独立数据表。

---

## 3. 角色语义表

| 技术 key | 展示文案 | 层级 |
|---|---|---|
| `super_admin` | 系统管理员 | 系统级 |
| `project_ceo` |  企业教练 | 项目级 |
| `owner` | 项目负责人 | 项目级 |
| `coordinator` | 统筹人 | 项目级 |
| `member` | 协同成员 | 项目级 |

### 特别说明

- **`project_ceo` 是历史技术 key，不代表公司 CEO**。其业务语义是项目层面的指导/督导/决策支持角色，展示为"企业教练"。
- **用户界面不要显示"项目 CEO"**。角色 badge、人员选择器、权限提示等一律走 `roleLabels.ts`。
- 如果确实指公司最高层决策人（如系统设置权限中的"全局 CEO"，对应 `is_ceo` 字段），应显示为"公司 CEO"或"高层决策"，**不要与 `project_ceo` 混为一谈**。
- 确认中心流转到 `project_ceo` 决策的动作文案统一为"企业教练"（如"转交企业教练"、"上报企业教练决策"、"企业教练批示"）。

### 前端集中映射

角色展示统一收敛到：

```
frontend/src/domain/roleLabels.ts
```

包括 `PROJECT_ROLE_LABELS`、`getProjectRoleLabel(role)`、`formatProjectRoleLabels(roles)`。各页面禁止再本地硬编码角色中文名。

---

## 4. 人员、账号、项目成员关系语义表

| 实体 | 模型类 | 数据库表 | 语义 | 是否权威 |
|---|---|---|---|---|
| 人员档案 | `Person` | `people` | 人员身份信息（姓名、部门、联系方式） | 人员身份权威源 |
| 登录账号 | `Account` | `accounts` | 登录凭证、系统角色（`system_role`）、是否管理员 | 登录能力权威源 |
| 项目成员 | `ProjectMember` | `project_members` | 项目内的角色分工（`role` + `person_id`） | **项目角色权威源** |
| 项目旧字段 | — | `projects.owners` / `coordinator` / `collaborators` | 旧兼容展示字段（文本快照） | 非权威，仅展示兜底 |

### 权威来源划分

- **项目角色以 `project_members` 为准**：`project_members.role` 取值为 `owner` / `coordinator` / `member` / `project_ceo`，是项目权限和项目分工的权威依据。
- **登录能力以 `accounts` 为准**：`people` 表存在不等于可登录；只有 `accounts` 中有对应记录且未停用才能登录。
- **人员身份以 `people` 为准**：`accounts.person_id` 指向 `people.id`，人员档案的增删改以 `people` 为准。
- `projects.owners` / `coordinator` / `collaborators` 是旧兼容的文本展示字段（逗号分隔姓名），**不作为权限判断依据**，仅在没有 `project_members` 数据时作展示兜底。

### 数据完整性约束

- `project_members.person_id` 必须对应 `people.id`，**不允许孤儿记录**（person_id 指向不存在或已删除的 people）。
- `accounts.person_id` 应对应 `people.id`。
- 删除 `people` 记录前，必须先清理或迁移关联的 `project_members`、`accounts` 记录。

### system_role 与 project role 的区别

- `accounts.system_role`（如 `普通成员` / `超级管理员` / `组长CEO`）是**账号级系统角色**，属数据字段值，不要与项目级角色（owner/coordinator/member/project_ceo）混淆。
- `普通成员` 是 `system_role` 的取值，**不是** `member`（协同成员）的展示名。人员管理页面的"普通成员"选项属 `system_role` 数据契约，保留不动。

---

## 5. 接口值和状态常量保留规则

以下内容属前后端契约或数据契约，**本轮及后续命名统一工作中暂不改**：

### 5.1 source_type 值

- `source_type: '语音更新'` / `'文字更新'`
- 这是 `update_submissions.source_type` 的接口字段值，前后端共享。
- 用户可见的"汇报入口"展示名已统一为"工作汇报"，但 `source_type` 的**值本身保留**'语音更新'/'文字更新'不动。

### 5.2 状态常量

`bowei_ai_dashboard/app/domain/submission_status.py` 与 `frontend/src/domain/submissionStatus.ts` 中的状态常量值保留不动，例如：

| 常量 | 值 |
|---|---|
| `S_PENDING_OWNER` | `待负责人审核` |
| `S_WAITING_COORDINATOR` | `已转交统筹人` |
| `S_WAITING_CEO` | `待CEO决策` |
| `S_CEO_DECIDED` | `CEO已批示` |
| `S_CONFIRMED` | `已入库` |

- 这些中文值是前后端状态契约，前端用技术常量（`SS.S_WAITING_CEO` 等）做判断，展示文案另写。
- 状态值中的"CEO"指 `project_ceo` 角色，但**值本身不改**；展示层已统一为"企业教练"相关文案。

### 5.3 技术字段名

- `task` / `subtask` 作为技术字段名（类型名、变量名、API 字段名）保留。
- `task_id` / `subtask_id` / `parent_task_id` 等字段名保留。

### 5.4 数据库表名

- `tasks` / `subtasks` / `update_submissions` / `project_members` / `people` / `accounts` 等表名保留不动。

### 5.5 角色 key

- `project_ceo` 作为技术 key 保留（权限判断、`project_members.role`、`_public_project_roles` 映射等）。
- `owner` / `coordinator` / `member` / `super_admin` 作为技术 key 保留。

### 5.6 路由路径

- `/escalate-ceo`、`/ceo-decide` 等历史路由路径保留不动。

### 5.7 ntype / tab 技术值

- `ntype="escalate_ceo"` / `"ceo_decided"`、tab `"ceo"` 等技术值保留不动。

---

## 6. 禁止全局替换清单

为避免"为统一展示名而破坏契约"，以下操作**明确禁止**：

- ❌ 不允许把 `tasks` 表直接改成 `workstreams`。
- ❌ 不允许把 `subtasks` 表直接改成 `key_tasks`。
- ❌ 不允许把 `project_ceo` 技术 key 直接改成 `coach`。
- ❌ 不允许把 `source_type` 值直接改成"工作汇报"。
- ❌ 不允许把状态常量值（如"待CEO决策"）直接改成"待企业教练决策"。
- ❌ 不允许为了展示文案统一而修改数据库字段、接口字段、状态值或权限逻辑。
- ❌ 不允许把 `system_role` 的"普通成员"当作项目角色 `member` 处理。
- ❌ 不允许在权限判断中用中文展示名（如 `role === '项目负责人'`）替代技术 key。
- ❌ 不允许新增"子任务"这一业务层级或相关字段。

### 正确做法

- 表名/字段名/技术 key 不动，只改用户可见文案。
- 用户可见文案走 `displayNames.ts` / `roleLabels.ts` 集中映射。
- 权限判断走技术 key（`owner` / `project_ceo` 等），不依赖中文。

---

## 7. 后续开发规则

### 7.1 展示文案

- 用户可见文案（产品名、系统名、业务对象名、入口名）优先使用 `frontend/src/domain/displayNames.ts` 中的常量。
- 角色展示优先使用 `frontend/src/domain/roleLabels.ts` 中的 `getProjectRoleLabel` / `PROJECT_ROLE_LABELS`。
- 禁止在页面、弹窗、按钮、toast、空状态、通知文案中直接硬编码角色中文名或产品名。

### 7.2 权限判断

- 权限判断应使用技术 key（`owner` / `coordinator` / `member` / `project_ceo` / `super_admin`），**不应依赖中文展示名**。
- 如发现中文角色名参与权限判断（如 `role === '项目负责人'`），**必须先列为风险，不得擅自改逻辑**：
  - 先判断该中文值是否来自后端数据契约；
  - 若后端确实返回中文 role 值，本轮保留，在任务报告中列为"后续权限 key 化风险"；
  - 若已有稳定技术 key，则改为技术 key 判断，并确保展示仍走 `roleLabels.ts`。

### 7.3 新增页面/接口前的确认

新增页面前必须确认：

1. 该页面属于哪个**业务对象**（对应第 2 节语义表）；
2. 该页面依赖哪个**数据权威源**（对应第 4 节）：
   - 涉及项目角色 → 以 `project_members` 为准；
   - 涉及登录能力 → 以 `accounts` 为准；
   - 涉及人员身份 → 以 `people` 为准；
3. 该页面用到哪些**保留不变的契约值**（source_type、状态常量、技术 key），不得擅自改动。

### 7.4 命名一致性检查清单

提交代码前，对照检查：

- [ ] 新增的用户可见文案是否引用了 `displayNames.ts` / `roleLabels.ts`？
- [ ] 是否出现了"项目 CEO"、"子任务"、"Moways-POS"、"项目运营管理系统"、"AI项目驾驶舱"等弃用词？
- [ ] 权限判断是否依赖了中文展示名？
- [ ] 是否误改了表名、字段名、状态值、source_type、路由路径？
- [ ] 新增的 `project_members.person_id` 是否对应有效的 `people.id`？

---

## 附录：历史决策记录

| 轮次 | 内容 | 结果 |
|---|---|---|
| N1 | 产品名统一 | Moways-POS→Moways-SOP，项目运营管理系统→Moways 项目协同平台，AI项目驾驶舱→系统名 |
| N2 | 三层结构展示口径统一 | task→重点工作，subtask→关键任务，子任务→关键任务，确认中心→AI 确认中心，语音更新入口→工作汇报 |
| N3 | 角色文案统一 | owner→项目负责人，project_ceo→企业教练，CEO 流转文案→企业教练 |
| people/project_members | 人员关系一致性修复 | project_members 为项目角色权威源，清理孤儿记录 |

> 后续如有口径调整，请在本文档对应章节更新，并追加历史决策记录。
