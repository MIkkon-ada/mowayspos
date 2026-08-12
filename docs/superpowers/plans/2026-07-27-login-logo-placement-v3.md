# 登录页 Logo 位置 V3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在桌面登录页左上区域融入正式 MOWAYS Logo，同时保持移动端表单优先。

**Architecture:** `AppLayout.tsx` 在 `login-brand-content` 中渲染正式 Logo；CSS 以固定的页面边距和与标题相同的左边缘定义其位置。Logo 原文件的白色背景通过 `mix-blend-mode: multiply` 融入浅色底图，不新增任何图片卡片。

**Tech Stack:** React、TypeScript、CSS、Vite、Node test runner、Playwright 截图。

---

### Task 1: 用测试锁定 Logo 的桌面与移动行为

**Files:**
- Modify: `frontend/tests/loginPageVisualStructure.test.mjs`
- Test: `frontend/tests/loginPageVisualStructure.test.mjs`

- [ ] **Step 1: 写入失败契约**

```js
test('desktop brand area renders the official logo without a card treatment', () => {
  assert.match(source, /src="\/reference-login\.png"/)
  assert.match(css, /\.login-logo-img \{[\s\S]*?mix-blend-mode: multiply;/)
  assert.match(css, /\.login-logo \{[\s\S]*?width: 160px;/)
})
```

- [ ] **Step 2: 确认失败**

Run: `node --test tests/loginPageVisualStructure.test.mjs`

Expected: FAIL，因为当前背景版没有渲染 Logo。

- [ ] **Step 3: 接入 Logo 并实现最小 CSS**

在 `login-brand-content` 的最上方渲染 `<img src="/reference-login.png" alt="MOWAYS 博维咨询" className="login-logo-img" />`。将 `.login-logo` 定义为 160px 宽、位于内容区开头、无背景、无边框、无阴影；`.login-logo-img` 使用 `mix-blend-mode: multiply` 和 `object-fit: contain`。保留 `@media (max-width: 1180px)` 对整个 `login-brand-panel` 的隐藏规则。

- [ ] **Step 4: 确认契约通过**

Run: `node --test tests/loginPageVisualStructure.test.mjs`

Expected: PASS。

### Task 2: 视觉和生产验证

**Files:**
- Modify: `test-screenshots/login-refresh-desktop-v3.png`
- Modify: `test-screenshots/login-refresh-mobile-v3.png`

- [ ] **Step 1: 截取桌面成品**

在 `/login` 使用 1920×1080 截图。确认 Logo 在左上、与标题左边缘对齐、没有白底矩形，且不遮挡标题。

- [ ] **Step 2: 截取移动端成品**

在 `/login` 使用 390×844 截图。确认 Logo 和左侧插画均隐藏，仅保留表单。

- [ ] **Step 3: 执行回归验证**

Run: `$taskTests = Get-ChildItem -Path tests -Filter *.test.mjs | Select-Object -ExpandProperty FullName; node --test $taskTests; npm run build`

Expected: 全部 Node 测试通过，生产构建通过。
