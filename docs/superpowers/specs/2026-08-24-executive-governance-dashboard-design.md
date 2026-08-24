# 首页执行治理驾驶舱设计

## 目标

将首页从“任务状态统计”调整为供企业教练和高层快速介入的执行治理界面。首页在一个屏幕内回答：现在需要谁采取什么动作、哪些 Initiative 健康度异常、每项关键工作由谁对结果负责。

## 已确认的设计原则

1. 行动优先：优先展示高层决策、PM 协调和责任人确认；任务总数和状态分布不再占据首要注意力。
2. Initiative 优先：以重点工作/KeyTask 作为首页的治理对象，而不是展开子任务流水。
3. 单点责任：每个 Initiative 只能有一位结果责任人；协同人以紧凑的头像组或数量信号呈现。
4. 里程碑和结果优先：健康状态必须结合下个节点和正式进展，不能单凭任务完成比例判断。
5. Evidence 下钻：协同提交、AI 汇总、责任人确认构成正式进展的来源；首页只展示确认覆盖/待确认信号，详情页展示完整链路。
6. 渐进披露：首页只保留短标题、责任人、截止时间和状态。背景、AI 推理与证据内容通过点击下钻，不能写成首页说明文字。

## 三家管理思想的产品映射

| 参考 | 首页的可见表达 | 下钻表达 |
| --- | --- | --- |
| McKinsey Transformation Office | Initiative、唯一结果责任人、下个里程碑、健康状态 | 里程碑计划、升级记录、跨项目治理节奏 |
| Bain Results Delivery Office | “需高层决策 / 需 PM 协调”及每项行动的推动角色 | 风险处置、决策记录、关闭结果 |
| IBM Targetprocess | 责任人旁的协同人数/头像组 | 角色、权限、任务分配和协同人的具体工作 |
| Moways | 待责任人确认及 Evidence 确认计数 | Evidence 原文、AI 草稿、人工确认历史 |

## 桌面端信息架构

保留现有顶部项目、月份筛选和周报导出控件，不改变其真实组件、交互和视觉样式。

1. **当前需要关注**：三张等宽信号卡，仅显示“需高层决策”“需 PM 协调”“待责任人确认”的数量和一句短标签。各卡点击进入既有决策、协调或确认中心。
2. **需要处理**：左侧主卡，最多三项。每项仅含事项名称、结果责任人、截止时间/等待时间和推动角色（高层、PM 或 Owner）。按高层决策、PM 协调、Owner 确认的顺序排列。
3. **项目健康**：右侧辅卡，最多三项。每项仅含项目名、下个里程碑和健康色（健康/关注/风险）；点击进入该项目范围的驾驶舱。
4. **重点 Initiative**：全宽紧凑列表，列为 Initiative、结果责任/协同、正式进展、下个节点、状态。协同人只显示最多三枚头像和总人数；Evidence 计数只在状态图标或简短计数中显示。

当某类信号为零时，信号卡仍保留但使用中性成功状态；“需要处理”不显示空白大卡，只显示一行“当前无待处理治理事项”。

## 数据与接口

现有 `GET /api/dashboard/overview` 已提供任务统计、问题统计、提交统计、项目卡片、角色队列、决策列表、风险列表和最近任务。新增或扩展一个显式的 `governance` 负载，避免前端基于模糊字段拼装治理语义：

```ts
governance: {
  signals: {
    pending_decisions: number
    pending_coordination: number
    pending_owner_confirmation: number
  }
  actions: Array<{
    id: string
    kind: 'decision' | 'coordination' | 'owner_confirmation'
    title: string
    accountable_owner: string
    due_at: string | null
    waiting_days: number | null
    route: string
  }>
  initiatives: Array<{
    task_id: number
    title: string
    accountable_owner: string
    collaborators: Array<{ id?: number; name: string }>
    official_progress: number | null
    next_milestone: string | null
    next_milestone_at: string | null
    health: 'healthy' | 'watch' | 'risk' | 'unstarted'
    evidence_confirmed: number
    evidence_total: number
  }>
}
```

全局和“我的项目”聚合必须基于同一结构；无权限用户不得收到决策、协同人或 Evidence 明细。现有 `role_queue` 保持兼容，不作为新 UI 的主要数据源。

## 前端实现边界

- 改造 `frontend/src/pages/DashboardPage.tsx` 的桌面内容；顶部筛选、响应式壳和现有导航路径保持不变。
- 扩展 `DashboardOverview` 类型及聚合逻辑，正确合并 `governance` 的信号、动作和 Initiative。
- 将治理区域拆为可测试的展示组件，数据转换函数与 JSX 分离。
- 不使用浏览器原生下拉替代真实项目选择器，也不添加临时 HTML 草图、深色大横幅或长篇 AI 摘要。
- 移动端维持现有结构；本次只在数据字段可复用时补齐轻量信号，不做移动端大改版。

## 交互

- 信号卡：决策 → `/project/:id/decisions`；协调 → `/project/:id/coordinate`；确认 → `/project/:id/confirm`。全局/我的项目范围不能可靠定位单个项目时，进入对应的现有聚合入口。
- “需要处理”行使用其 `route` 跳转；没有目标路由时禁用点击而非跳转到错误项目。
- Initiative 行跳转既有 KeyTask 工作台；头像组或 Evidence 信号不单独抢夺点击区域。
- 所有健康色同时配有文字标签，不能仅依赖颜色传达风险。

## 验收标准

1. 高层在首屏能看到三种治理信号、最多三项待处理事项和最多三项项目健康状态。
2. 每个 Initiative 行可辨认唯一责任人、协同规模、正式进展、下个节点和健康状态，且不出现解释段落。
3. 现有项目/月份筛选、导出周报、权限限制和导航路径不回归。
4. 零数据、无动作、无协同人、无里程碑和无 Evidence 均有紧凑空状态，不出现大面积空白卡。
5. 全局、我的项目和单项目模式的数字与行项目能稳定聚合，且不泄露无权限数据。
6. 为数据转换、排序、空状态和关键路由增加自动化测试；现有 Dashboard 相关测试继续通过。
