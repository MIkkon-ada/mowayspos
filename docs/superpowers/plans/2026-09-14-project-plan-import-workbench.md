# 项目立项工作推进表导入工作台实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用项目概览 + AI 任务树工作台替换现有工作计划导入复核弹窗。

**Architecture:** 保留现有预览、行转换和确认导入 API，将 `ProjectPlanAiImportDialog` 改为全屏工作台。工作台在导入前显示来源入口，分析后使用 `BatchImportRow[]` 作为唯一可编辑数据源，并从预览 evidence 构造来源抽屉。

**Tech Stack:** React 19, TypeScript, Tailwind utility classes, Vitest, Testing Library, existing project-plan import APIs.

---

### Task 1: 锁定工作台交互契约

**Files:**
- Modify: `frontend/src/features/settings/ProjectPlanAiImportDialog.test.tsx`
- Modify: `frontend/tests/projectPlanImportUiContract.test.mjs`

- [ ] **Step 1: 写失败测试**

增加断言：工作台包含“项目概览”“工作推进方案”“任务树”“原文对照”“逐项采纳”等结构；规则降级时显示明确提示；任务来源按钮可见；确认导入在未采纳时不可用。

- [ ] **Step 2: 运行测试确认失败**

```powershell
npm run test:unit -- --run src/features/settings/ProjectPlanAiImportDialog.test.tsx
node --test tests/projectPlanImportUiContract.test.mjs
```

预期：新工作台断言因当前紧凑弹窗尚不存在而失败。

### Task 2: 实现工作台状态和来源模型

**Files:**
- Modify: `frontend/src/features/settings/ProjectPlanAiImportDialog.tsx`

- [ ] **Step 1: 增加工作台状态**

增加重点工作折叠/采纳状态、来源抽屉状态和任务来源映射；继续使用现有 `rows` 保存编辑内容。

- [ ] **Step 2: 实现导入前工作台**

保留文件上传、粘贴表格、已有项目/新项目选择和“开始分析”，但把容器改为全屏工作台风格，标题改为“项目立项 · 导入工作推进表”。

- [ ] **Step 3: 实现分析后概览和任务树**

左侧渲染项目概览和来源文件；右侧渲染统计卡片、重点工作卡片和关键任务行；提供编辑、来源查看、单项采纳和一键采纳。

- [ ] **Step 4: 实现来源抽屉和降级提示**

从 evidence 渲染来源文件、定位和摘要；`fallback_mode === 'deterministic'` 时显示规则提取提示。

- [ ] **Step 5: 实现确认限制**

只有所有重点工作采纳、项目名/重点工作/关键任务不为空且处于 review 阶段时，确认导入按钮才可用。

### Task 3: 验证和人工查看

**Files:**
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx` only if the entry label/semantics need alignment.

- [ ] **Step 1: 运行前端单元和契约测试**

```powershell
npm run test:all
```

- [ ] **Step 2: 运行构建和格式检查**

```powershell
npm run build
git diff --check
```

- [ ] **Step 3: 使用本地热更新验证**

打开 `http://127.0.0.1:6004/home/projects`，进入“导入工作推进表”，确认导入前、分析中、复核、来源抽屉、规则降级和确认按钮状态。
