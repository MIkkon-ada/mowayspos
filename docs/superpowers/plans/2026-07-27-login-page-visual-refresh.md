# Login Page Visual Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the login page around the supplied MOWAYS logo and 3D illustration while preserving every existing authentication interaction.

**Architecture:** Keep the existing `LoginPanel` state and handlers in `AppLayout.tsx`; replace only decorative assets and styles. Keep visual rules in the existing login CSS section of `styles.css`, with a desktop two-column composition that collapses to the established form-only layout below 1180px. Add source-contract tests for assets, interaction hooks, and responsive rules.

**Tech Stack:** React 19, TypeScript, Vite, CSS, Node.js built-in test runner.

---

### Task 1: Add supplied assets and the visual contract test

**Files:**
- Create: `frontend/public/login-hero.png`
- Create: `frontend/tests/loginPageVisualStructure.test.mjs`
- Modify: `frontend/src/layouts/AppLayout.tsx`

- [ ] **Step 1: Write the failing test**

```js
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const source = fs.readFileSync(path.join(frontendRoot, 'src/layouts/AppLayout.tsx'), 'utf8')
const css = fs.readFileSync(path.join(frontendRoot, 'src/styles.css'), 'utf8')

test('login page loads the supplied logo and 3D hero assets', () => {
  assert.match(source, /src="\/reference-login\.png"/)
  assert.match(source, /src="\/login-hero\.png"/)
  assert.ok(fs.existsSync(path.join(frontendRoot, 'public/reference-login.png')))
  assert.ok(fs.existsSync(path.join(frontendRoot, 'public/login-hero.png')))
})

test('login page keeps form interactions and responsive form-only layout', () => {
  assert.match(source, /onSubmit=\{handleSubmit\}/)
  assert.match(source, /onClick=\{handleWecomLogin\}/)
  assert.match(source, /onClick=\{\(\) => setShowPassword/)
  assert.match(css, /@media \(max-width: 1180px\)[\s\S]*?\.login-brand-panel \{\s*display: none;/)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test frontend/tests/loginPageVisualStructure.test.mjs`

Expected: FAIL because the page still references `/bowei-logo.png`, renders `HeroIllustration`, and `public/login-hero.png` does not exist.

- [ ] **Step 3: Add the image and switch decorative URLs**

Copy the supplied original to `frontend/public/login-hero.png`. In `LoginPanel`, replace the legacy asset URL and inline illustration with:

```tsx
<img src="/reference-login.png" alt="MOWAYS logo" className="login-logo-img" onError={handleLogoError} />
<div className="login-hero">
  <img src="/login-hero.png" alt="Project collaboration platform illustration" className="login-hero-illustration" />
</div>
```

Delete `HeroIllustration` only after the PNG is in use. Retain `LogoFallback` for an actual failed image request.

- [ ] **Step 4: Run the test to verify it passes**

Run: `node --test frontend/tests/loginPageVisualStructure.test.mjs`

Expected: PASS with two passing subtests.

- [ ] **Step 5: Commit**

```bash
git add frontend/public/login-hero.png frontend/src/layouts/AppLayout.tsx frontend/tests/loginPageVisualStructure.test.mjs
git commit -m "feat: use supplied login branding assets"
```

### Task 2: Align the 1920px desktop visual composition

**Files:**
- Modify: `frontend/src/styles.css`
- Modify: `frontend/tests/loginPageVisualStructure.test.mjs`

- [ ] **Step 1: Extend the failing test**

```js
test('login page defines the 1920px desktop composition', () => {
  assert.match(css, /\.login-body \{[\s\S]*?max-width: 1760px;/)
  assert.match(css, /\.login-card \{[\s\S]*?max-width: 596px;/)
  assert.match(css, /\.login-hero-illustration \{[\s\S]*?object-fit: contain;/)
  assert.match(css, /\.login-submit \{[\s\S]*?linear-gradient\(90deg,/)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test frontend/tests/loginPageVisualStructure.test.mjs`

Expected: FAIL because the shell is 1440px wide, card is 420px wide, the illustration has no `object-fit`, and the submit button is solid blue.

- [ ] **Step 3: Implement desktop-first CSS**

Update only the `.login-*` CSS rules, preserving all state selectors:

```css
.login-body {
  grid-template-columns: minmax(0, 1.12fr) minmax(560px, 0.88fr);
  max-width: 1760px;
  padding: 0 84px;
}
.login-card {
  max-width: 596px;
  padding: 64px 58px 54px;
  border-radius: 28px;
}
.login-hero-illustration {
  width: min(100%, 760px);
  max-width: none;
  max-height: 46vh;
  object-fit: contain;
  object-position: center;
}
.login-submit {
  background: linear-gradient(90deg, #1467f4 0%, #1768ef 100%);
}
```

Tune only existing login background gradients, dot opacity, feature spacing, title scale, card shadow, and input heights so 1920 × 1080 matches the reference hierarchy. Do not alter form handlers, fields, disabled conditions, or enterprise-WeChat flow.

- [ ] **Step 4: Run the test to verify it passes**

Run: `node --test frontend/tests/loginPageVisualStructure.test.mjs`

Expected: PASS with three passing subtests.

- [ ] **Step 5: Build**

Run: `npm run build` from `frontend`.

Expected: TypeScript and Vite exit with code 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/styles.css frontend/tests/loginPageVisualStructure.test.mjs
git commit -m "feat: align login page with desktop visual reference"
```

### Task 3: Browser-level visual and interaction verification

**Files:**
- No source changes expected.

- [ ] **Step 1: Start the development server**

Run: `npm run dev -- --host 127.0.0.1` from `frontend`.

Expected: Vite serves `http://127.0.0.1:6001`.

- [ ] **Step 2: Capture desktop and mobile screenshots**

```bash
npx playwright screenshot --viewport-size=1920,1080 http://127.0.0.1:6001/login ../test-screenshots/login-refresh-desktop.png
npx playwright screenshot --viewport-size=390,844 http://127.0.0.1:6001/login ../test-screenshots/login-refresh-mobile.png
```

Expected: desktop contains branding and illustration; mobile contains a complete usable login form without horizontal scrolling.

- [ ] **Step 3: Verify real interaction states**

Without submitting production credentials, confirm: an empty form keeps the submit button disabled; both fields enable it; the eye button changes the password input type; “忘记密码” expands the existing help panel; and 企业微信 remains clickable.

- [ ] **Step 4: Run the full frontend checks**

```bash
node --test tests/*.test.mjs
npm run build
```

Working directory: `frontend`.

Expected: all Node tests pass and the production build exits 0.

- [ ] **Step 5: Review handoff scope**

Run: `git status --short`

Expected: only intended asset, login source, stylesheet, regression test, and accepted screenshots are changed.
