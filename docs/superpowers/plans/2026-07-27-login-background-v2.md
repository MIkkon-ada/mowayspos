# 登录页左侧背景 V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用无文字的用户提供插画底图和可响应式网页文字，构成统一的登录页左侧视觉区。

**Architecture:** 以非破坏性生成的 PNG 作为 `login-background-v2.png`，由 `.login-bg` 负责覆盖桌面背景；左侧 React 结构只保留标题和副标题，删除独立 Logo 与单独 Hero 图片。登录表单的事件处理和窄屏隐藏策略不变。

**Tech Stack:** React、TypeScript、CSS、Vite、Node test runner、built-in image generation editing。

---

### Task 1: 生成无文字背景资产

**Files:**
- Create: `frontend/public/login-background-v2.png`
- Test: `frontend/tests/loginPageVisualStructure.test.mjs`

- [x] **Step 1: 写入失败的资产契约**

```js
test('login page uses the supplied text-free background asset', () => {
  assert.match(source, /login-background-v2\.png/)
  assert.ok(fs.existsSync(path.join(frontendRoot, 'public/login-background-v2.png')))
})
```

- [x] **Step 2: 运行契约并确认失败**

Run: `node --test tests/loginPageVisualStructure.test.mjs`

Expected: FAIL，因为页面和 `public` 目录尚不存在 `login-background-v2.png` 引用。

- [x] **Step 3: 使用图像编辑生成无文字底图**

使用用户提供的 `codex-clipboard-07b214c4-4745-4352-9e8a-277c657092d0.png` 作为编辑目标，生成同尺寸画布。提示词必须要求：仅删除“项目管理协同平台”、副标题和蓝色短线；完整保留 3D 平台、三枚图标、城市、网格、波纹、留白、色彩、构图和光影；无新文字、无水印。将选定 PNG 非破坏性保存为 `frontend/public/login-background-v2.png`。

- [x] **Step 4: 检查生成结果**

在图片查看器中确认旧文字无残留，且核心插画和底部波纹未变化。

### Task 2: 用背景层和网页文字重组左侧视觉区

**Files:**
- Modify: `frontend/src/layouts/AppLayout.tsx:311-341`
- Modify: `frontend/src/styles.css:142-300`
- Test: `frontend/tests/loginPageVisualStructure.test.mjs`

- [x] **Step 1: 写入失败的结构契约**

```js
test('login brand panel keeps editable copy but no standalone logo or hero image', () => {
  assert.match(source, /<h1 className="login-title-cn">项目管理协同平台<\/h1>/)
  assert.doesNotMatch(source, /reference-login\.png/)
  assert.doesNotMatch(source, /login-hero\.png/)
  assert.match(css, /background-image:\s*url\('\/login-background-v2\.png'\)/)
})
```

- [x] **Step 2: 运行契约并确认失败**

Run: `node --test tests/loginPageVisualStructure.test.mjs`

Expected: FAIL，因为旧结构仍渲染独立 Logo 与 Hero，CSS 尚未引用新背景。

- [x] **Step 3: 最小化修改页面结构与 CSS**

删除 `.login-logo`、`LogoFallback`、`HeroIllustration` 和 `login-hero` 图片节点，仅保留 `login-brand-text` 中的可编辑标题、副标题与短线。把 `/login-background-v2.png` 作为 `.login-bg` 的背景图，桌面下使用 `cover` 与左下优先定位；清除旧渐变和伪元素干扰。让 `.login-brand-panel` 内文字定位在底图原文字的留白位置；保留 `@media (max-width: 1180px)` 隐藏该区域。

- [x] **Step 4: 运行结构契约并确认通过**

Run: `node --test tests/loginPageVisualStructure.test.mjs`

Expected: PASS。

### Task 3: 视觉与回归验证

**Files:**
- Modify: `test-screenshots/login-refresh-desktop.png`
- Modify: `test-screenshots/login-refresh-mobile.png`

- [x] **Step 1: 生成 1920×1080 桌面截图**

启动 Vite 并打开 `/login`，使用 1920×1080 截图。确认右侧卡片不遮挡平台，左侧标题可读，且没有单独 MOWAYS 图片块。

- [x] **Step 2: 生成移动端截图**

使用 390×844 截图。确认左侧场景仍按既有规则隐藏，表单可用。

- [x] **Step 3: 执行完整验证**

Run: `$taskTests = Get-ChildItem -Path tests -Filter *.test.mjs | Select-Object -ExpandProperty FullName; node --test $taskTests; npm run build`

Expected: 全部 Node 测试通过，TypeScript 与 Vite 生产构建通过。
