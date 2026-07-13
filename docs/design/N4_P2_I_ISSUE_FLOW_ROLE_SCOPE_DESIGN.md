# N4-P2-I 问题中心角色可见范围与状态流转收口设计

> 状态：设计阶段（本轮不改代码）
> 分支：`n4-p2-i-issue-flow-role-scope-design`
> 作者：AI Audit + Design
> 日期：2026-07-13

---

## 1. 背景

N4-P2-E（AI 确认入库写 `related_subtask_id` + `company_ceo` 兼任项目 owner 确认权限修复）已合并 main。当前问题中心经过多轮增量开发，出现以下结构性问题：

- **"待协调"只是 issue_type，不是 status**，导致无法在看板中独立跟踪协调流程。
- **"待决策"同时作为 type 和 status**，两个概念在代码和前端混用。
- **普通成员 `list_issues` 能看到全项目问题**，缺少 reporter/owner/helper 过滤。
- **`/api/issues/mine` 已实现但前端未使用**。
- **`company_ceo` 拥有 `can_view_all` + `can_confirm_all`**，在部分端点可能权限过大。
- **项目角色在问题中心的读写权限模糊**（coordinator、project_ceo 能做/看不到什么不清晰）。

本轮目标是基于真实项目运营需求和最新业务口径，重新梳理设计，输出可执行的分阶段实施方案。

---

## 2. 当前代码现状（审计结果）

### 2.1 问题状态 (`issue_flow.py`)

```python
STATUS_PENDING          = "待处理"
STATUS_IN_PROGRESS      = "处理中"
STATUS_PENDING_DECISION = "待决策"
STATUS_RESOLVED         = "已解决"
STATUS_CLOSED           = "已关闭"
```

共 5 个状态。**没有"待协调"状态**。

### 2.2 问题类型 (`issue_flow.py`)

```python
TYPE_ISSUE       = "问题"
TYPE_RISK        = "风险"
TYPE_COORDINATE  = "待协调"      ← 这是 TYPE，不是 STATUS
TYPE_DECISION    = "需决策"      ← 与 STATUS_PENDING_DECISION 同名不同义
```

另有 `issue_type.py`（英文键映射层）：
```python
TYPE_ISSUE        = "issue"
TYPE_RISK         = "risk"
TYPE_COORDINATION = "coordination"    ← "待协调" 映射至此
TYPE_DECISION     = "decision"        ← "需决策" 映射至此
```

### 2.3 数据表结构 (`issues`)

| 字段 | 类型 | 用途 |
|------|------|------|
| `issue_type` | VARCHAR(40) | 当前存储中文：问题/风险/待协调/需决策 |
| `status` | VARCHAR(20) | 待处理/处理中/待决策/已解决/已关闭 |
| `priority` | VARCHAR(10) | 高/中/低 |
| `reporter` | VARCHAR(50) | 上报人（create_issue 硬编码为 current_user） |
| `owner` | VARCHAR(50) | 负责人/处理人 |
| `helper` | VARCHAR(100) | 协助人（字符串，非结构化） |
| `need_decision_by` | VARCHAR(50) | 需要谁来决策 |
| `resolution` | TEXT | 解决方案/备注 |
| `handler_reply` | TEXT | 处理人回复 |
| `related_task_id` | INTEGER | 关联重点工作 |
| `related_subtask_id` | INTEGER | 关联关键任务（N4-P2-E 写入） |
| `source_type` | VARCHAR(40) | 来源：人工录入/AI确认入库 |
| `feedback_required` | BOOLEAN | 是否需要反馈 |
| `feedback_result` | TEXT | 反馈结果 |

### 2.4 API 端点

| 端点 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/api/issues` | GET | `require_project_access` | 返回项目全部问题（无角色过滤） |
| `/api/issues` | POST | `require_project_access` | 创建问题，reporter=current_user |
| `/api/issues/mine` | GET | 任意登录用户 | 返回当前用户上报的问题 |
| `/api/issues/{id}` | GET | `require_project_access` | 查看单条问题 |
| `/api/issues/{id}` | PUT | owner 或 reporter 本人 | 编辑问题 |
| `/api/issues/{id}` | DELETE | owner 或 admin | 删除问题 |
| `/api/issues/{id}/status` | PATCH | owner | 修改状态 |
| `/api/issues/{id}/resolve` | PATCH | owner | 标记已解决 |
| `/api/issues/{id}/close` | PATCH | owner 或 admin | 关闭问题 |
| `/api/issues/{id}/assign-helper` | PATCH | owner | 指定协助人 |
| `/api/issues/{id}/request-ceo` | PATCH | owner 或 coordinator | 上报 Coach 决策 |

### 2.5 前端问题中心 (`IssuesPage.tsx`)

- 主入口：项目问题中心 Kanban（5列：待处理/处理中/待决策/已解决/已关闭）
- 调用 `fetchIssues(projectId)` → `/api/issues?project_id=xxx`（全项目问题）
- **不调用 `/api/issues/mine`**
- 新增问题弹窗：允许选择 `issue_type`（问题/风险/待协调/需决策）、`priority`、`owner`
- 操作按钮：开始处理、指定协助人、上报 Coach、标记已解决、关闭问题

### 2.6 通知 (`notify.py`)

| 触发事件 | 通知对象 | 通知类型 |
|----------|----------|----------|
| 创建问题 | 项目 owner+coordinator | `issue_reported` |
| 解决问题 | reporter（如非操作人） | `issue_resolved` |
| 关闭问题 | reporter（如非操作人） | `issue_closed` |
| 上报 Coach | 项目 project_ceo 列表 | `issue_needs_decision` |

---

## 3. 当前问题流转现状

```
新增问题 → status = "待处理"（或"待决策"，取决于 issue_type）
  ├─ owner 开始处理 → "处理中"
  ├─ owner/coordinator 上报 Coach → "待决策"
  ├─ owner 解决 → "已解决"
  └─ owner 关闭 → "已关闭"
```

**缺少的流转**：
- 没有"待协调"状态（协调只能靠 type 标记，不体现在看板列中）
- 已解决 → 已关闭 之间缺少确认环节
- 关闭后无法重开

---

## 4. 当前角色可见范围现状

| 角色 | list_issues 可见范围 | 问题详情 | 新增问题 | 修改状态 | 解决/关闭 | 上报 Coach |
|------|---------------------|----------|----------|----------|-----------|------------|
| normal_member | 项目全部问题 ⚠️ | ✅ | ✅ | ❌ | ❌ | ❌ |
| coordinator | 项目全部问题 | ✅ | ✅ | ❌ | ❌ | ✅ |
| owner | 项目全部问题 | ✅ | ✅ | ✅ | ✅ | ✅ |
| project_ceo | 项目全部问题 | ✅ | ✅ | ❌ | ❌ | ❌（只能查看） |
| company_ceo | 全局（can_view_all） | ✅ | ✅ | ❌（非owner） | ❌（非owner） | ❌（非owner） |
| tech_admin | 全局（所有权限） | ✅ | ✅ | ✅ | ✅ | ✅ |

### ⚠️ 当前风险点

1. **普通成员可见全项目问题**：`list_issues` 无 reporter/owner/helper 过滤，任何人只要有项目访问权限即看到该项目全部问题。业务上，成员之间的问题可能存在敏感信息（如涉及人事、绩效等）。
2. **company_ceo 全局可见但操作受限**：`can_view_all` + `can_confirm_all` 在 permissions 层有全局标记，但 issues 写端点通过 `require_project_role(OWNER_KEY)` 收口，ceo 非 owner 时会被拒绝。**但 permissions 层的全局标记在语义上容易造成误解**。
3. **"待协调"/"待决策"混用**：`issue_type="待协调"` + `status="处理中"` 和 `issue_type="需决策"` + `status="待决策"` 是两套体系，前端看板只有 status 维度，导致协调类问题无法在看板中独立追踪。
4. **用户新增时可自由选择 type/priority/status**：与"普通成员只上报不负责分级"的口径矛盾。

---

## 5. 当前问题总结

1. **"待协调"是 type 不是 status** → 看板无法体现协调列
2. **"待决策" type 和 status 同名不同义** → 语义混淆
3. **普通成员看到全项目问题** → 信息泄露风险
4. **用户新增时可选择 issue_type/priority/status** → 超出普通成员职责
5. **`/api/issues/mine` 闲置** → 前端未使用
6. **project_ceo/coordinator 的读写边界** → 不够清晰
7. **company_ceo 权限标记过大** → `can_view_all` + `can_confirm_all` 全域

---

## 6. 新业务口径

### 6.1 问题新增口径

**普通成员（所有项目成员）新增问题时只填：**

| 字段 | 必填 | 说明 |
|------|------|------|
| 项目归属 | ✅ | project_id |
| 关联重点工作 | ❌ | related_task_id，可选 |
| 关联关键任务 | ❌ | related_subtask_id，可选 |
| 问题描述 | ✅ | description |
| 期望解决时间 | ❌ | expected_resolve_time |
| 附件/链接 | ❌ | 当前无附件能力，后续迭代 |

**新增时系统自动设定：**
- `reporter = current_user`
- `status = "待处理"`
- `issue_type = "问题"`（普通成员不可选）
- `priority = "中"`（普通成员不可选）
- `source_type = "人工录入"`
- `owner = ""`（由负责人后续指派）

**用户不负责：**
- 选择问题等级（priority）
- 选择问题类型（issue_type）：待协调/需决策/风险由负责人判断
- 选择待决策/待协调路径
- 指定 handler/helper

### 6.2 负责人分流口径

**项目负责人（owner）/ PM 可以：**

| 操作 | 接口 | 说明 |
|------|------|------|
| 设为处理中 | PATCH /status → "处理中" | 开始处理 |
| 设为待协调 | PATCH /status → "待协调" | 需内部协调 |
| 设为待决策 | PATCH /request-ceo | 上报 Coach |
| 指定 owner | PUT /{id} | 修改处理人 |
| 指定 helper | PATCH /assign-helper | 指定协助人 |
| 调整 priority | PUT /{id} | 高/中/低 |
| 调整 issue_type | PUT /{id} | 问题→风险/待协调/需决策（由 PM 判断） |
| 标记已解决 | PATCH /resolve | 问题已处理 |
| 关闭问题 | PATCH /close | 确认关闭 |

### 6.3 待协调定义

**待协调 = 项目内部可解决，但需要其他成员 / 协助人 / 统筹人参与处理。**

典型场景：
1. 需要成员补资料
2. 需要协助人一起处理关键任务
3. 需要统筹人协调资源
4. 需要其他项目成员补充信息
5. 跨重点工作（Workstream）协调

**推荐：待协调应该做成 `status`**，理由：
- 协调是一个流程阶段，不是问题性质
- 做成 status 可以直接看板化追踪（Kanban 列新增"待协调"）
- 协调完成后可以回到"处理中"或直接解决
- 与"待决策"一致——两者都是流程节点，已证明 status 是正确的载体
- issue_type 保留为问题性质分类（问题/风险），与流程状态解耦

### 6.4 待决策定义

**待决策 = 超出负责人直接处理范围，需要 Coach/企业教练判断、拍板、给资源或调整方向。**

典型场景：
1. 是否调整项目目标
2. 是否延期关键任务
3. 是否追加资源
4. 是否变更交付范围
5. 是否影响项目是否继续推进
6. 跨项目协调需要高层拍板

**当前"待决策"作为 status 是正确的**，不需要改为 type。

### 6.5 风险定义

**风险暂不单独建模块。建议作为 `issue_type = "风险"` 处理。**

| 维度 | 问题 | 风险 |
|------|------|------|
| 性质 | 已经发生 | 尚未发生但可能发生 |
| 影响 | 目标/进度/质量/资源 | 目标/进度/质量/资源 |
| 处理方式 | 解决问题 | 预警 + 预防措施 |
| 入口 | 同问题中心 | 同问题中心（issue_type=风险） |

**建议：**
1. ✅ 保留 `issue_type = "风险"`
2. ✅ 不新增 Risk Center
3. ✅ 不新增风险状态机（共用问题状态机）
4. 前端可在 Kanban 中通过 type badge 区分"风险"卡片

---

## 7. 推荐状态机

```
                     ┌──────────┐
         普通成员上报  │  待处理   │ ← 默认入口
                     └────┬─────┘
                          │ owner 指派
              ┌───────────┼───────────┐
              ▼           ▼           ▼
         ┌──────────┐ ┌──────────┐ ┌──────────┐
         │  处理中   │ │  待协调   │ │  待决策   │ ← owner 上报 Coach
         └────┬─────┘ └────┬─────┘ └────┬─────┘
              │           │ 协调完成    │ Coach 决策完成
              │           ▼ 后可回     │
              │      ┌──────────┐      │
              └──────┤  处理中   │◄─────┘
                     └────┬─────┘
                          │ owner 解决
                          ▼
                     ┌──────────┐
                     │  已解决   │
                     └────┬─────┘
                          │ owner 确认关闭
                          ▼
                     ┌──────────┐
                     │  已关闭   │
                     └──────────┘
```

### 状态列表（推荐）

| # | 状态 | 英文键 | 说明 |
|---|------|--------|------|
| 1 | 待处理 | pending | 新增默认状态 |
| 2 | 处理中 | in_progress | 处理人已接手 |
| 3 | 待协调 | coordinating | **新增** — 需内部协调 |
| 4 | 待决策 | pending_decision | 需要 Coach 决策 |
| 5 | 已解决 | resolved | 问题已处理 |
| 6 | 已关闭 | closed | 确认关闭（终态） |

### 状态流转规则

| 当前状态 | 可流转到 | 触发者 |
|----------|----------|--------|
| 待处理 | 处理中 | owner |
| 待处理 | 待协调 | owner |
| 待处理 | 待决策 | owner（上报 Coach） |
| 待处理 | 已关闭 | owner（直接关闭无效问题） |
| 处理中 | 待协调 | owner |
| 处理中 | 待决策 | owner |
| 处理中 | 已解决 | owner |
| 待协调 | 处理中 | owner（协调完成） |
| 待协调 | 待决策 | owner |
| 待协调 | 已解决 | owner |
| 待决策 | 处理中 | owner（Coach 决策后回收） |
| 待决策 | 已解决 | owner |
| 待决策 | 已关闭 | owner |
| 已解决 | 已关闭 | owner（确认关闭） |

### 关键决策

| 问题 | 推荐 | 理由 |
|------|------|------|
| 待协调是否必须有 helper？ | **是** | 无 helper 的"待协调"无意义 |
| 待协调是否可以回到处理中？ | **是** | 协调完成后回收 |
| 待决策由谁触发？ | **owner** 或 **coordinator** | 保持当前权限 |
| 待决策由谁处理？ | **project_ceo / Coach** | Coach 给决策意见后 owner 回收 |
| 已解决后由谁关闭？ | **owner** | 当前已实现 |
| 关闭后是否允许重开？ | **本轮不做** | 保持终态不可逆（PR5 如有需求再议） |
| Coach 能否直接关闭？ | **否** | Coach 通过决策意见影响，关闭由 owner 执行 |

---

## 8. 推荐角色可见范围

### 8.1 normal_member / 普通成员

| 能力 | 允许 | 说明 |
|------|------|------|
| 新增问题 | ✅ | 项目所有成员可新增 |
| 看项目全部问题 | ❌ | **收口**：只看自己相关的 |
| 看自己上报的问题 | ✅ | reporter=自己 |
| 看分配给自己处理的问题 | ✅ | owner=自己 |
| 看自己作为协助人的问题 | ✅ | helper=自己 |
| 修改问题 | ✅ | 仅限自己上报的问题 |
| 补充说明/回复 | ❌（本轮不做） | 后续 PR 支持 |
| 修改状态 | ❌ | |
| 解决/关闭 | ❌ | |
| 上报 Coach | ❌ | |

### 8.2 coordinator / 统筹人

| 能力 | 允许 | 说明 |
|------|------|------|
| 新增问题 | ✅ | |
| 看项目内待协调问题 | ✅ | status="待协调" |
| 看自己相关问题 | ✅ | reporter/owner/helper |
| 看项目全部问题 | ⚠️ **推荐看全项目** | 统筹人需要全局了解项目风险 |
| 上报 Coach | ✅ | 与 owner 共享此权限 |
| 修改问题状态 | ❌ | 协调而非处理 |
| 解决/关闭 | ❌ | |

### 8.3 owner / 项目负责人 PM

| 能力 | 允许 | 说明 |
|------|------|------|
| 新增问题 | ✅ | |
| 看项目全部问题 | ✅ | |
| 全量操作 | ✅ | 分流/分派/协调/解决/关闭/上报Coach |

### 8.4 project_ceo / Coach / 企业教练

| 能力 | 允许 | 说明 |
|------|------|------|
| 新增问题 | ✅ | |
| 看项目全部问题 | ✅ | 重点看待决策/风险 |
| 给决策意见 | ✅ | 通过 issue 评论/决议字段 |
| 直接关闭问题 | ❌ | 决策意见 vs 执行分离 |
| 直接修改状态 | ❌ | |
| 上报 Coach | ❌ | 自己就是 Coach |

### 8.5 company_ceo

| 能力 | 允许 | 说明 |
|------|------|------|
| 看全局概览 | ✅ | 统计面板 |
| 看项目全部问题 | ✅ | can_view_all |
| 新增问题 | ❌（不推荐） | 应通过项目成员身份操作 |
| 日常处理问题 | ❌ | 不默认参与 |
| 如同时是项目 owner | 按 owner 权限 | 已通过 N4-P2-E 修复 |
| 如非 owner | 只读 | 查看不处理 |

### 8.6 tech_admin / super_admin

| 能力 | 允许 | 说明 |
|------|------|------|
| 全局查看和维护 | ✅ | |
| 处理异常数据 | ✅ | |
| 业务默认处理人 | ❌ | 不替代业务角色 |

---

## 9. 推荐权限动作矩阵

| 动作 | member | coordinator | owner | project_ceo | company_ceo | tech_admin |
|------|--------|-------------|-------|-------------|-------------|------------|
| 新增问题 | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| 查看项目全部问题 | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 查看自己相关问题 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 修改自己上报的问题 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 修改他人上报的问题 | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| 开始处理 | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| 设为待协调 | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| 指定协助人 | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| 调整优先级/类型 | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| 上报 Coach | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ |
| Coach 决策 | — | — | — | ✅ | ❌ | ✅ |
| 标记已解决 | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| 关闭问题 | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| 删除问题 | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |

---

## 10. 数据字段影响

### 10.1 issue_type 保留但收口

| issue_type | 旧用途 | 新用途 |
|------------|--------|--------|
| 问题 | 普通问题 | ✅ 保留 |
| 风险 | 风险预警 | ✅ 保留 |
| 待协调 | 协调事项 **type** | ❌ 改为 **status** |
| 需决策 | 决策事项 **type** | ❌ 改为 **status**（已有 STATUS_PENDING_DECISION） |

**迁移策略**：
- 旧数据：`issue_type="待协调"` 且 `status="处理中"` → `issue_type="问题"`, `status="待协调"`
- 旧数据：`issue_type="需决策"` 且 `status="待决策"` → `issue_type="问题"`, `status="待决策"`
- 旧数据：`issue_type="需决策"` 且 `status!="待决策"` → `issue_type="问题"`，手动检查

### 10.2 需新增 status

| 新增 | 值 | 说明 |
|------|-----|------|
| STATUS_COORDINATING | "待协调" | 在 issue_flow.py 中新增 |

### 10.3 不需改数据库

- 不改表结构
- 状态值存储格式不变（字符串）
- issue_type 旧值兼容（前端 badge 保留旧 type 展示）

---

## 11. API 影响

### 11.1 需要修改的接口

| 接口 | 修改项 |
|------|--------|
| `GET /api/issues?project_id=xxx` | 按角色过滤 visible 范围（普通成员只看 reporter/owner/helper 相关） |
| `POST /api/issues` | 收口：普通成员不能选 issue_type/priority/status |
| `GET /api/issues/mine` | 增强：加上 owner=自己 和 helper=自己 的问题 |

### 11.2 不需要新增接口

- 当前接口集已覆盖所需操作
- 待协调流转通过 `PATCH /status` 实现

### 11.3 可能新增的接口（后续 PR）

| 接口 | 用途 | PR |
|------|------|------|
| `PATCH /issues/{id}/decide` | Coach 给决策意见 | PR5 |
| `PATCH /issues/{id}/reply` | 成员补充回复 | PR5 |

---

## 12. 前端页面影响

### 12.1 IssuesPage Kanban

| 改动 | 说明 | PR |
|------|------|------|
| 新增"待协调"列 | KANBAN_COLUMNS 增加"待协调" | PR2 |
| 收口新增表单 | 普通用户不显示 issue_type/priority/status 选择 | PR3 |
| 角色差异展示 | 普通成员默认只看到"我的相关问题"视图 | PR4 |

### 12.2 新增"我的相关问题"视图

- 入口：IssuesPage 子 tab 或独立视图
- 查询：`GET /api/issues?project_id=xxx&my_related=true`
- 后端过滤：`reporter=current_user OR owner=current_user OR helper=current_user`

---

## 13. 通知影响

| 新增通知 | 触发事件 | 通知对象 |
|----------|----------|----------|
| `issue_coordinating` | 问题进入"待协调" | helper |
| `issue_coordination_done` | 协调完成 | owner |
| `issue_decided` | Coach 给出决策意见 | owner |

现有通知保持不变。

---

## 14. 兼容策略

### 14.1 issue_type 旧值兼容

| 旧 issue_type | 兼容方式 |
|---------------|----------|
| "待协调" | 前端 badge 仍展示，但新问题不再允许选择此 type |
| "需决策" | 同"待决策" badge，新问题不再允许选择此 type |

### 14.2 旧数据迁移

```python
# 一次性迁移脚本（PR2 时执行，不在本轮）
def migrate_issue_type_to_status(db):
    # issue_type="待协调" + status="处理中" → status="待协调", issue_type="问题"
    # issue_type="需决策" → status="待决策", issue_type="问题"
    pass
```

**迁移不在本轮执行**。本轮仅设计。

### 14.3 向后兼容

- 旧数据 status 不强制修改
- 前端 Kanban 列动态适应 status 值
- `issue_flow.py` 增加"待协调"→STATUS_COORDINATING 映射

---

## 15. 分阶段实施计划

### PR1：文档与测试基线（本轮）

- ✅ 输出本设计文档
- ❌ 不改业务代码
- ❌ 不改数据库
- 新增测试用例覆盖新状态机边界

### PR2：状态机最小调整

**改动范围**：
- `issue_flow.py`：新增 `STATUS_COORDINATING = "待协调"`
- `issues.py`：`patch_status` 允许流向待协调
- 前端 `IssuesPage.tsx`：Kanban 增加"待协调"列、STATUS_STYLE 增加样式
- 测试：新状态流转用例

**不改**：可见范围、新增表单、旧数据迁移

### PR3：新增问题表单收口

**改动范围**：
- `issues.py`：`create_issue` 收口——普通成员（非 owner）创建时忽略 payload 中的 issue_type/priority/status，强制设为默认值
- 前端 `IssuesPage.tsx`：新增弹窗按角色显示不同字段（普通成员只看到描述+关联任务）
- 测试：权限边界用例

**不改**：可见范围、旧数据

### PR4：角色可见范围收口

**改动范围**：
- `issues.py`：`list_issues` 按角色过滤：
  - 普通成员：`reporter=current_user OR owner=current_user OR helper=current_user`
  - coordinator：项目全部问题（推荐放全量）
  - owner/project_ceo：项目全部问题
- `issues.py`：`list_my_issues` 增强为 `reporter OR owner OR helper`
- 前端：IssuesPage 普通成员默认视图调整
- 测试：可见范围用例

**不改**：旧数据、状态机

### PR5：处理动作细化

**改动范围**：
- `issues.py`：Coordinator 处理反馈能力
- `issues.py`：新增 `PATCH /{id}/decide`（Coach 决策意见）
- `issues.py`：新增 `PATCH /{id}/reply`（成员补充回复）
- `notify.py`：新增协调通知、决策通知
- 前端：Coach 决策面板、成员回复入口
- 测试：全权限矩阵覆盖

### 推荐顺序

1. **PR1**（本轮）→ 设计文档
2. **PR2** → 状态机（最小改动，最大价值）
3. **PR3** → 表单收口（安全性）
4. **PR4** → 可见范围收口（安全性 + 业务需求）
5. **PR5** → 处理动作细化（体验优化）

---

## 16. 不做事项

| # | 事项 | 原因 |
|---|------|------|
| 1 | 本轮不改代码 | 设计阶段 |
| 2 | 本轮不改数据库 | 设计阶段 |
| 3 | 本轮不新增接口 | 设计阶段 |
| 4 | 不新增风险中心 | 风险通过 issue_type 管理 |
| 5 | 不让普通成员判断等级 | 与业务口径矛盾 |
| 6 | 不让普通成员直接选择待决策 | 需要 owner 判断 |
| 7 | 不让 company_ceo 默认处理所有项目问题 | ceo 看全局但不参与日常 |
| 8 | 不把 Coach 等同于 PM | Coach 决策 vs PM 执行 |
| 9 | 不把待协调和待决策混用 | 协调是项目内，决策需 Coach |
| 10 | 不破坏现有 related_subtask_id 绑定链路 | N4-P2-E 已验证 |
| 11 | 不把风险单独做成新模块 | 共用问题中心 |
| 12 | 不新增 migration | 本轮只设计 |

---

## 17. 风险点

| 风险 | 级别 | 缓解措施 |
|------|------|----------|
| 旧 issue_type="待协调"/"需决策" 数据兼容 | 中 | 前端 badge 保留旧 type 展示 + 迁移脚本 |
| 可见范围收口后用户感知变化 | 低 | 普通成员仍可通过 `/mine` 查看自己的问题 |
| 状态机扩展后前端 Kanban 列数变化 | 低 | 从 5 列变 6 列（增加"待协调"），UI 可适应 |

---

## 18. 最终建议

1. **"待协调"应新增为 status**，从 issue_type 中移除
2. **"需决策"作为 issue_type 应废弃**，统一使用 status="待决策"
3. **普通成员可见范围收口**为 reporter/owner/helper 三者交集
4. **普通成员新增时不可选 issue_type/priority/status**
5. **coordinator 可见全项目问题**（而非仅待协调），便于全局了解
6. **project_ceo 只做决策，不做执行**（不关问题、不改状态）
7. **company_ceo 非 owner 时只读**
8. **分 5 个 PR 逐步实施**，先状态机再收口最后细化
9. **风险不单独建模块**，共用问题中心 issue_type=风险
10. **不改数据库结构**，纯逻辑层调整
