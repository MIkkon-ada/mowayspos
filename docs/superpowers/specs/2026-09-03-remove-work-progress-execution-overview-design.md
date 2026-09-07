# 删除工作推进表执行视角设计

## 背景

工作推进表当前同时提供“表格视图”和“执行详情”模式。执行详情模式包含一个重点工作汇总概览 `ExecutionProgressView`，并且与关键任务执行工作台共用 `viewMode` 状态。现确认只删除工作推进表的执行视角概览，不删除关键任务执行详情工作台及其执行数据能力。

## 目标

1. 工作推进表只展示计划表视图，不再显示“执行详情”模式入口。
2. 计划表桌面端和移动端点击关键任务后，继续打开现有 `KeyTaskExecutionDetailView` / `KeyTaskExecutionWorkspace`。
3. 保留关键任务详情中的当前进展、任务计划、成果、问题、推进记录、风险和权限控制。
4. 保留工作推进表现有的项目筛选、状态/负责人筛选、搜索、导出、从大纲导入和回收站能力；这些入口不能因为移除执行模式而消失。
5. 不修改后端接口、数据库结构、权限规则、汇报确认入库链路或“我的任务”入口。

## 非目标

- 不保留或重构 `ExecutionProgressView` 的重点工作汇总概览。
- 不删除 `KeyTaskExecutionWorkspace`、执行计划接口、执行事件接口或关键任务详情数据。
- 不新增路由，不改变 `/work/tasks` 的导航入口。
- 不顺带调整计划表列、视觉样式或回收站业务规则。

## 设计

### 页面状态与数据流

移除 `TaskManagementPage` 中仅用于“计划/执行”二选一的 `viewMode` 状态、执行模式专属的子任务预加载 effect、模式切换按钮和 `ExecutionProgressView` 分支。计划表的 `ensurePlanTableSubTasksLoaded` 继续作为唯一的批量子任务加载入口，保证筛选、负责人选项、计划表行和导出所需数据完整。

关键任务详情不再通过 `viewMode='execution'` 进入，而由 `selectedSubTask` / `subDetailLoading` 直接表达。保留现有 `openSubDetail → focusSubTask → fetchSubtaskDetail` 流程；`KeyTaskExecutionDetailView` 的渲染条件改为选中关键任务后直接成立。返回操作清除选中状态并回到计划表。计划表、移动端任务列表、重点工作详情中的关键任务入口继续复用 `openSubDetail`。

执行详情打开时继续隐藏工作推进表顶部工具栏，避免计划表工具栏与全屏执行工作台同时出现；加载详情期间沿用现有加载状态，不改变错误回退到基础关键任务数据的行为。

### 操作入口

当前“导出表格”“从大纲导入”和回收站相关控件包在 `viewMode === 'execution'` 条件下。移除执行模式时，将这些控件从模式条件中解耦，保持原有权限条件、回调、筛选清理和项目上下文逻辑。回收站仍使用 `showDeleted` 和现有软删除/恢复接口，不新增 API 或数据状态。

计划表视图继续使用 `PlanTableViewV2`；其表格数据、关键任务点击、项目标准和新增重点工作能力不变。若操作控件需要在计划表工具栏重新承载，只调整入口位置，不改变导出格式、导入流程或权限判断。

### 删除与保留的文件边界

- 删除：`frontend/src/components/task-management/ExecutionProgressView.tsx`。
- 修改：`frontend/src/pages/TaskManagementPage.tsx`，移除执行概览和模式状态，保留详情与计划表流程，迁移操作入口。
- 保留：`frontend/src/components/task-management/PlanTableViewV2.tsx`、`frontend/src/components/task-management/KeyTaskExecutionDetailView.tsx`、`frontend/src/components/key-task-workspace/**`、相关 API 和后端实现。

## 错误处理与权限

- 详情加载失败时沿用当前 `fetchSubtaskDetail(...).catch(() => ({ ...st }))` 回退。
- 项目权限、归档项目只读限制、执行计划管理权限和风险权限沿用现有判断。
- 回收站权限仍由前端入口可见性和后端校验共同保证；普通成员不能因入口迁移而获得回收站能力。
- 不因删除概览而新增全局任务请求，继续遵守项目上下文限制。

## 测试设计

更新现有前端结构测试，覆盖：

1. 工作推进表源码不再引入或渲染 `ExecutionProgressView`，不再暴露“执行详情”模式按钮。
2. 工作推进表保留 `PlanTableViewV2`、计划表子任务批量加载和表格筛选/导出相关 wiring。
3. 计划表和移动端关键任务入口仍调用 `openSubDetail`，页面仍渲染 `KeyTaskExecutionDetailView`，且详情不依赖 `viewMode`。
4. 执行工作台自身的计划、成果、问题、推进记录、风险和权限测试继续通过。
5. 操作菜单、导入、导出、回收站入口的现有权限和回调 wiring 未被删除。

验证顺序：先运行受影响的 Node 结构测试和前端单元测试，再运行 TypeScript 构建；如涉及回收站入口迁移，补充对应结构断言。

## 验收标准

- 打开工作推进表时只能看到计划表内容，不出现“执行详情”切换入口或执行概览卡片。
- 桌面端、移动端和重点工作详情中的关键任务均可打开同一个关键任务执行详情工作台。
- 关键任务执行详情的加载、返回、编辑、计划操作、提交更新、成果/问题/推进记录展示和权限限制与改动前一致。
- 导出、从大纲导入和有权限用户的回收站入口仍可用；无权限用户仍不可见。
- 相关测试与生产构建通过，且不修改工作区中与本需求无关的现有变更。
