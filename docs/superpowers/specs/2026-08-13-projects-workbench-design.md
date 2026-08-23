# N10-P0-FE-PROJECTS-WORKBENCH 项目生命周期工作台设计

## 1. 背景与目标

当前项目管理首页以搜索栏和项目列表为主，用户需要自行从列表状态推断项目阶段和当前待办。本次改版将首页调整为项目生命周期工作台，围绕三个问题组织信息：

1. 当前有哪些项目；
2. 每个项目处于哪个业务阶段；
3. 当前登录用户有哪些项目需要处理。

本次范围仅限前端项目管理首页的信息架构、布局和展示逻辑，目标页面结构为：

`页面头部 → 状态概览 → 待我处理 → 全部项目`

页面以桌面宽屏为主要场景，保留基础响应式能力，不额外设计移动端专属布局。

## 2. 范围与不变约束

### 2.1 允许修改

- `frontend/src/features/settings/ProjectsMgmtSection.tsx` 及必要的纯展示辅助组件；
- 项目管理首页的前端状态、派生数据、布局和文案；
- 项目卡片/列表视图的本地切换状态。

### 2.2 明确不修改

- 数据库、migration 和数据库字段；
- 后端项目生命周期与 API 契约；
- 角色权限规则；
- 项目创建、下发、负责人完善、Coach 审核、执行、结束、归档的真实流程；
- Sidebar、Dashboard、工作推进表、我的任务及其他非项目管理首页模块；
- OwnerSubmitModal、ApprovalMaterialsWorkbenchModal、结束流程和归档流程的行为。

真实生命周期仍使用现有状态：

`draft / dispatched / pending_review / returned / active / pending_close / ended / archived`

不新增 `startup` 或其他虚假数据库状态。

## 3. 现状复用点

现有 `ProjectsMgmtSection` 已负责项目和成员加载、任务/子任务加载、角色过滤、搜索分页，以及所有项目流程 handler。本次复用以下能力：

- `getProjectPrimaryStatus()`：读取真实项目状态；
- `getProjectStatusBadge()`：展示真实状态 badge；
- `getProjectCloseMainAction()`：保留 active、pending_close、ended、archived 的原有主动作；
- 现有 `LifecycleCard`：扩展为首页默认卡片视图的生命周期卡片；
- 现有 `DetailPanel`：保持项目详情页的既有消费方式；
- 现有 OwnerSubmit、审核、结束和归档 handler；
- 现有 `searchQuery`、分页和项目表格列表能力；
- 已加载的 `projectTasksMap`、`projectSubtasksMap`，用于待办卡片材料缺项提示。

不创建 `NewLifecycleCard`、`ProjectCard2` 等重复卡片组件。

当前仓库的负责人完善入口实际由 `navigate(/home/projects/:id/owner-submit)` 打开 `OwnerSubmitWorkbench`，没有名为 `setOwnerFillProject` 的函数；本次沿用该现有路由作为需求中“继续负责人完善流程”的等价入口，不创建第二套负责人完善页面。

## 4. 页面信息架构

### 4.1 页面头部

删除顶部独立的大搜索框区域，替换为：

- 标题：`项目管理`；
- 副标题：`管理项目从立项、启动到执行与归档`；
- 右侧主操作：已有权限用户可见的 `新建项目`，继续调用 `setShowNew(true)`；
- `批量导入` 保留为次级操作，不抢占主操作层级。

### 4.2 项目状态概览

在标题下方展示五个轻量统计卡。它们只是首页展示分组，不是新的项目状态，也不驱动复杂 Tab 状态机：

| 展示分组 | 前端映射 |
| --- | --- |
| 全部项目 | `roleFilteredProjects.length` |
| 待完善 | `status === 'dispatched' || status === 'returned'` |
| 待审批 | `status === 'pending_review'` |
| 进行中 | `status === 'active'` |
| 已归档 | `status === 'archived'` |

`draft`、`pending_close`、`ended` 等状态不会因为没有独立统计卡而被过滤或丢失。

### 4.3 待我处理

只有当前用户确实拥有下一步处理权限的项目进入待办区。待办项目纵向排列，首屏最多展示 3 条；超过 3 条提供轻量的“查看全部待处理”入口或展开剩余项目，不修改后端分页。

待办卡片包含：

- 当前业务阶段和优先级提示；
- 项目名称；
- 面向当前角色的处理说明；
- 项目负责人和 Coach/项目 CEO 信息；
- 对 `dispatched / returned` 项目的四项材料缺项提示；
- 与真实流程对应的主操作按钮。

没有待办时不保留巨大空状态，仅显示紧凑提示或隐藏该区域。

### 4.4 全部项目

在待办区之后展示全部项目：

- 标题：`全部项目（数量）`；
- 搜索框移动到标题行右侧，保留 `searchQuery` 和现有过滤逻辑，宽度约 220–280px；
- `卡片视图 / 列表视图` 切换，新增本地 `viewMode`，默认 `card`；
- `list` 视图继续渲染现有项目表格和分页能力；
- `card` 视图按纵向项目卡片排列，不做瀑布流和小型多列商品卡布局。

## 5. 待办权限规则

待办派生逻辑使用现有角色来源和项目角色字段，不重新实现权限系统。

| 真实状态 | 进入待办的角色 | 文案/主要动作 |
| --- | --- | --- |
| `draft` | 技术管理员或公司 CEO | 项目尚未下发，请继续完善项目信息并完成下发；沿用编辑/下发流程 |
| `dispatched` | `isRealOwner === true` | 项目已下发，等待您完善项目计划；`继续完善项目` → 现有 `/home/projects/:id/owner-submit` 入口 |
| `returned` | `isRealOwner === true` | 项目已被企业教练退回，请根据审核意见修改后重新提交；`修改项目计划` → 原 OwnerSubmit 流程 |
| `pending_review` | `isRealProjectCeo || isSuperAdmin` | 负责人已提交项目计划，等待您审核；`审核项目` → 现有审核 Modal |
| `active` | 不进入 | 保持执行中项目卡片和工作推进入口 |
| `pending_close` | 不新增首页待办规则 | 保留 `getProjectCloseMainAction()` 现有结束审核入口 |
| `ended` | 不新增首页待办规则 | 保留查看结束档案入口 |
| `archived` | 不进入 | 保留查看项目档案入口 |

普通成员或负责人可以看到 `pending_review` 项目卡片，但不会因状态本身而进入“待我处理”。

## 6. 材料缺项派生

不新增接口或数据库字段。对 `dispatched / returned` 项目，使用现有加载数据计算四项展示缺项：

- 项目目标：`project.objectives` 非空；
- 项目周期：`project.start_date` 与 `project.end_date` 均已填写；
- 重点工作：对应项目的 `tasks.length > 0`；
- 关键任务：对应项目的 `subtasks.length > 0`。

待办卡片显示“尚有 N 项信息待完善”和缺项清单。该信息只用于前端提示，不作为新的业务校验或状态字段。

## 7. 生命周期卡片设计

现有 `LifecycleCard` 扩展为默认项目卡片，卡片展示重点为：

- 项目名称；
- 当前业务阶段；
- 当前真实状态 badge；
- 项目负责人；
- Coach/项目 CEO；
- 项目周期；
- 生命周期节点位置；
- 下一步动作。

业务阶段与真实状态分开显示：

| 真实状态 | 业务阶段展示 |
| --- | --- |
| `draft / dispatched / pending_review / returned` | 立项准备阶段 |
| `active` | 执行阶段 |
| `pending_close` | 结束阶段 |
| `ended` | 结束完成 / 待归档 |
| `archived` | 归档阶段 |

进度条固定展示五个概念节点：

`立项准备 → 启动 → 执行 → 结束 → 归档`

“启动”只是展示节点，不对应新增的 lifecycle status。无法准确判断启动节点时，不伪造当前状态。

项目卡片整体和右下角统一的 `进入项目` 按钮均导航到 `/home/projects/:id`。明确的业务按钮必须阻止冒泡后调用原有 handler，避免同时触发详情跳转。

## 8. 视觉与响应式约束

- 页面背景保持现有浅灰风格，建议 `#F8FAFC`；
- 主内容宽度约 1280–1440px；
- 主卡片使用白底、浅色边框、10–14px 圆角和轻阴影；
- 沿用现有蓝色主按钮；
- 状态色只用于 badge、图标和少量强调；
- 不引入新的 UI 框架；
- 不使用大渐变、巨大阴影、过多装饰图标或彩虹色；
- 宽屏下项目卡片不强制拉成过长的横向空白；
- 小屏仅通过现有 flex/grid 换行和纵向堆叠保持可用。

## 9. 实现边界与文件策略

优先修改 `ProjectsMgmtSection.tsx`。如果新增 JSX 或派生逻辑明显降低可读性，再拆出纯展示组件或辅助函数，但不搬动现有流程逻辑。优先顺序为：

1. 纯函数和类型：统计分组、待办规则、阶段映射、材料缺项；
2. 现有 `LifecycleCard` 的展示扩展；
3. 首页主布局和 `viewMode`；
4. 保持列表、弹窗及流程 handler 原样可用。

## 10. 测试策略

先为新增纯函数编写 Vitest 测试并确认测试在实现前按预期失败，再实现最小逻辑并回归：

- 统计分组不丢失未被顶部统计覆盖的状态；
- `draft / dispatched / returned / pending_review` 的角色化待办边界；
- `active / pending_close / ended / archived` 不被错误扩展为待办；
- 生命周期阶段映射不包含虚构的 `startup` 状态；
- 材料缺项四项计算；
- 构建通过，现有项目管理相关测试通过。

必要时只更新因本次明确 UI 结构改版而过时的结构断言，不删除业务验证。

## 11. 验收标准

1. 首页不再首先呈现独立大搜索框和单行表格；
2. 顶部有项目管理标题和生命周期说明；
3. 有五项项目概览统计；
4. 有角色驱动的“待我处理”；
5. `dispatched` 的真实负责人可看到“继续完善项目”；
6. 页面不再出现“完善材料”；
7. 默认卡片视图，列表模式仍可用；
8. 卡片显示生命周期位置及真实状态解释；
9. 搜索、新建项目、批量导入仍可用；
10. OwnerSubmit、审核、结束和归档流程不受影响；
11. 不修改后端、数据库、API 或真实生命周期状态。
