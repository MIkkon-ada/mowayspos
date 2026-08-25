# 组织与分工公司角色切换 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让组织与分工的成员卡片在未选择专项时显示公司角色，并且仅在选择专项时显示当前专项角色。

**Architecture:** 修改 `CoordinatePage` 的主角色来源选择：无 `selectedProjectId` 时使用人员 `system_role` 的标签，有选中专项时保留既有的 `getRoleInProject` 结果。用一个源文件结构契约测试锁定导入、角色优先级表达式和成员卡片渲染点，防止项目角色再次成为默认值。

**Tech Stack:** React 19、TypeScript、Vite、Node `assert` 源文件结构测试。

---

## 文件结构

- 修改：`frontend/src/pages/CoordinatePage.tsx` — 选择成员主角色的显示来源。
- 新建：`frontend/tests/coordinateCompanyProjectRole.test.mjs` — 检查默认公司角色与项目选中角色的前端结构契约。

### Task 1: 角色展示结构契约

**Files:**
- Create: `frontend/tests/coordinateCompanyProjectRole.test.mjs`
- Test: `frontend/tests/coordinateCompanyProjectRole.test.mjs`

- [ ] **Step 1: 编写失败测试**

```js
import fs from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'

const source = fs.readFileSync(path.resolve(process.cwd(), 'src/pages/CoordinatePage.tsx'), 'utf8')

assert.match(source, /import\s*\{\s*systemRoleLabel\s*\}\s*from\s*'\.\.\/domain\/roles'/)
assert.match(source, /const companyRole = \{ label: systemRoleLabel\(p\.system_role\), cls: 'bg-slate-100 text-slate-700' \}/)
assert.match(source, /const \{ label: roleLabel, cls: roleCls \} = selectedProjectId \? \(roleInProject \?\? companyRole\) : companyRole/)
assert.ok(!source.includes('roleInProject ?? getBestRole(p)'), 'project roles must not be the default card role')
console.log('coordinate company/project role contract passed')
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `node tests/coordinateCompanyProjectRole.test.mjs`

Expected: FAIL，因为页面尚未导入 `systemRoleLabel`，且默认角色仍由 `getBestRole(p)` 推断。

### Task 2: 仅在选择专项时使用项目职位

**Files:**
- Modify: `frontend/src/pages/CoordinatePage.tsx:1-13`
- Modify: `frontend/src/pages/CoordinatePage.tsx:360-366`
- Test: `frontend/tests/coordinateCompanyProjectRole.test.mjs`

- [ ] **Step 1: 导入公司角色标签函数**

将现有角色标签导入保留为：

```ts
import { getProjectRoleLabel } from '../domain/roleLabels'
import { systemRoleLabel } from '../domain/roles'
```

- [ ] **Step 2: 用公司角色替换默认项目角色**

在成员卡片的 `map` 回调中，紧接现有 `roleInProject` 定义后，使用下列完整选择逻辑：

```ts
const roleInProject = selectedProjectId ? getRoleInProject(p, selectedProjectId) : null
const companyRole = { label: systemRoleLabel(p.system_role), cls: 'bg-slate-100 text-slate-700' }
const { label: roleLabel, cls: roleCls } = selectedProjectId
  ? (roleInProject ?? companyRole)
  : companyRole
```

不要改动 `getRoleInProject`、项目成员高亮、专项标签点击事件或现有项目角色颜色映射。

- [ ] **Step 3: 运行角色结构测试并确认通过**

Run: `node tests/coordinateCompanyProjectRole.test.mjs`

Expected: `coordinate company/project role contract passed`。

- [ ] **Step 4: 运行类型与生产构建验证**

Run: `npm run build`

Expected: 命令以 exit code 0 完成，TypeScript 与 Vite 构建无错误。

- [ ] **Step 5: 提交实现**

```bash
git add frontend/src/pages/CoordinatePage.tsx frontend/tests/coordinateCompanyProjectRole.test.mjs
git commit -m "feat: show company roles by default in coordinate view"
```
