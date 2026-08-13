# OwnerSubmitModal Project Workbench UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将负责人完善立项信息界面改造成单列项目方案编排工作台，并在不改变 AI、Picker、提交链路的前提下增加可靠的重点工作折叠交互。

**Architecture:** 优先只修改 `OwnerSubmitModal.tsx`，使用 `Set<number>` 保存展开索引；新增、删除和 AI 合并分别维护该集合。AI 合并通过现有 `id/task_id` 稳定身份识别真正新增的重点工作。现有业务函数、API 调用和 Picker 行为保持原样。

**Tech Stack:** React 19、TypeScript、Tailwind CSS、Node.js `node:test` 结构测试、Vite。

---

### Task 1: 建立新版结构与交互测试红线

**Files:**
- Modify: `frontend/tests/ownerSubmitModalLayout.test.mjs`
- Verify unchanged: `frontend/tests/ownerSubmitAiIntegration.test.mjs`
- Verify unchanged: `frontend/tests/ownerSubmitAiPanelBehavior.test.mjs`

- [ ] **Step 1: 更新布局和交互结构断言**

在 `ownerSubmitModalLayout.test.mjs` 中用明确源码断言覆盖：单列结构、项目资料摘要、`expandedTaskIndexes` 初始值、只读折叠分支、空值占位、任务数、新增自动展开、删除索引左移、基于 `id/task_id` 的 AI 新项识别、备注列无 `max-w-[180px]`/`truncate`。

- [ ] **Step 2: 运行测试确认旧实现失败**

Run: `node --test tests/ownerSubmitModalLayout.test.mjs tests/ownerSubmitAiIntegration.test.mjs tests/ownerSubmitAiPanelBehavior.test.mjs`

Expected: 新布局测试因旧左右分栏和缺少折叠状态而 FAIL；两条 AI 业务保护线继续 PASS。

- [ ] **Step 3: 提交测试红线**

```bash
git add frontend/tests/ownerSubmitModalLayout.test.mjs
git commit -m "test: define owner submit workbench interactions"
```

### Task 2: 实现可靠的重点工作展开状态

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx:370-630`
- Test: `frontend/tests/ownerSubmitModalLayout.test.mjs`

- [ ] **Step 1: 增加最小本地 UI state 与切换函数**

增加初始包含索引 0 的 `expandedTaskIndexes`，并实现显式展开/收起切换。不得写入 payload。

- [ ] **Step 2: 让新增项自动展开且保留已有状态**

`addTaskDraft()` 使用更新前数组长度作为新增索引，并将该索引加入原 Set。

- [ ] **Step 3: 删除后修正所有展开索引**

删除索引前的值保留，删除索引后的值减一，被删除值移除；数据只剩一项时维持现有禁止删除行为。

- [ ] **Step 4: AI 合并按稳定身份识别新项**

在应用 `nextTasks` 前收集当前任务的 `id/task_id` 身份；合并后找出第一个没有匹配稳定身份的新任务。保留仍有效的展开索引，最多额外展开该一个新项。不得新增数据字段或改变合并结果。

- [ ] **Step 5: 运行结构测试**

Run: `node --test tests/ownerSubmitModalLayout.test.mjs`

Expected: 与状态维护相关的断言 PASS；尚未实现的 JSX 布局断言仍可 FAIL。

### Task 3: 将 Modal 重排为单列工作台

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx:720-1065`
- Test: `frontend/tests/ownerSubmitModalLayout.test.mjs`

- [ ] **Step 1: 重构工作台外壳和 Header**

保留 Modal、遮罩、关闭事件与 sticky footer；标题改为“填写项目方案”，副说明改为批准文案，降低圆角、阴影和遮罩重量。

- [ ] **Step 2: 将项目资料改为横向摘要**

移除 `lg:flex-row`、左侧 sticky pane 和 disabled 项目名称 input。以横向 grid 展示项目名称、`projectPeriod`、`fillForm.objectives`，保留弱化的 `<details>` 及全部原字段绑定。

- [ ] **Step 3: 建立全宽工作推进方案区域**

使用批准的短文案，将 AI 和新增重点工作按钮留在局部 Header，降低按钮视觉重量。保持 AI panel、错误恢复和合并预览原 JSX 行为。

- [ ] **Step 4: 实现折叠只读和展开编辑两种 JSX 分支**

折叠态不渲染 input、Picker、日期控件；显示两位编号、空值占位、目标摘要、`subtasks.length`、展开按钮和含删除项的弱化 `···` 菜单。卡片主体可点击展开，菜单阻止冒泡。展开态保留现有控件并增加收起入口。

- [ ] **Step 5: 压缩重点工作与关键任务密度**

重点工作标题和目标同行；表格列使用 26/14/16/15/24/5 比例，保留内部 `min-width` 和 overflow。备注 placeholder 改为“填写验收标准或说明”，移除 `max-w-[180px]` 与 `truncate`。Picker 只改 class，不改逻辑。

- [ ] **Step 6: 运行相关三组测试**

Run: `node --test tests/ownerSubmitModalLayout.test.mjs tests/ownerSubmitAiIntegration.test.mjs tests/ownerSubmitAiPanelBehavior.test.mjs`

Expected: 全部 PASS，且 AI 两个测试文件无业务断言削弱。

- [ ] **Step 7: 提交实现**

```bash
git add frontend/src/features/settings/OwnerSubmitModal.tsx frontend/tests/ownerSubmitModalLayout.test.mjs
git commit -m "feat: redesign owner submit project workbench"
```

### Task 4: 全量前端兼容与构建验证

**Files:**
- Verify: `frontend/src/features/settings/OwnerSubmitModal.tsx`
- Verify: `frontend/tests/*.test.mjs`

- [ ] **Step 1: 运行全部 Node 测试**

Run: `node --test tests/*.test.mjs`

Expected: 0 failed。

- [ ] **Step 2: 运行生产构建**

Run: `npm run build`

Expected: `tsc -b` 与 `vite build` 均以 exit 0 完成。

- [ ] **Step 3: 检查修改边界**

Run: `git diff --check && git status --short && git diff --stat HEAD~2..HEAD`

Expected: 无 whitespace error；除设计/计划文档外，仅 `OwnerSubmitModal.tsx` 和直接相关布局测试发生实现改动。

- [ ] **Step 4: 桌面宽度手工验收**

在 1440、1600、1920px 检查单列布局、折叠只读、新增展开、删除不串位、Picker Portal、AI 面板/预览和 sticky footer。若本地页面缺少可进入该 Modal 的可用数据或登录状态，在结果中如实记录未完成的手工项，不用伪造结论。

