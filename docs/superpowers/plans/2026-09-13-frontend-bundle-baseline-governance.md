# Frontend Bundle Baseline Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` in the current session task-by-task. Do not delegate to subagents for this repository.

**Goal:** Add a deterministic production-bundle baseline that protects initial-load resources and ensures ExcelJS remains dynamically loaded.

**Architecture:** Vite emits a manifest; a Node script resolves the `src/main.tsx` static-import closure and compares actual raw/gzip file sizes against committed logical budgets. The same script verifies the ExcelJS chunk is within its isolated budget and outside that entry closure. npm and CI invoke it only after a successful production build.

**Tech Stack:** Vite 6, TypeScript, Node.js ESM, Node `fs`/`zlib`/`node:test`, GitHub Actions.

---

## File structure

- Create: `frontend/performance/bundle-baseline.json`
- Create: `frontend/scripts/check-bundle-baseline.mjs`
- Create: `frontend/tests/bundleBaseline.test.mjs`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/package.json`
- Modify: `.github/workflows/cloud-p1b2a-gate.yml`
- Modify: `docs/superpowers/plans/2026-09-13-frontend-bundle-baseline-governance.md`

### Task 1: Fix the baseline artifact contract with a failing test

**Files:**

- Create: `frontend/tests/bundleBaseline.test.mjs`
- Create: `frontend/performance/bundle-baseline.json`

- [ ] **Step 1: Add the baseline JSON with the measured budgets.**

Create `frontend/performance/bundle-baseline.json`:

```json
{
  "initial_js": { "raw_bytes": 340000, "gzip_bytes": 110000 },
  "initial_css": { "raw_bytes": 110000, "gzip_bytes": 24000 },
  "largest_route_js": { "raw_bytes": 110000, "gzip_bytes": 32000 },
  "exceljs_dynamic_js": { "raw_bytes": 1000000, "gzip_bytes": 300000 }
}
```

- [ ] **Step 2: Write a failing analyzer-contract test.**

Create a temporary `dist/.vite/manifest.json` and fake assets. The desired module API is `analyzeBundle({ distDir, baselinePath })`. Test static import de-duplication, CSS accounting, and that a dynamic ExcelJS chunk stays outside the entry closure:

```js
const report = analyzeBundle({ distDir, baselinePath })
assert.deepEqual(report.initial.files, ['assets/index-a.js', 'assets/vendor-a.js'])
assert.equal(report.initial.js.rawBytes, 10)
assert.equal(report.initial.css.rawBytes, 3)
assert.equal(report.exceljs.file, 'assets/exceljs.min-a.js')
assert.equal(report.exceljs.isInitial, false)
```

The manifest fixture must make `src/main.tsx` the only `{ isEntry: true }` item, make `assets/index-a.js` import `vendor`, list `assets/index-a.css`, and expose ExcelJS only through `dynamicImports`.

- [ ] **Step 3: Add failing budget and isolation tests.**

Use the same fixture factory with one override per test:

```js
assert.throws(
  () => analyzeBundle({ distDir, baselinePath: tinyInitialBudget }),
  /initial_js raw bytes 10 exceed budget 9/,
)
assert.throws(
  () => analyzeBundle({ distDir, baselinePath: baselinePathWithExcel }),
  /exceljs dynamic chunk is part of the initial entry closure/,
)
assert.throws(
  () => analyzeBundle({ distDir, baselinePath: baselinePath }),
  /exceljs dynamic chunk is missing from the manifest/,
)
```

- [ ] **Step 4: Run the test and verify red.**

Run:

```powershell
Set-Location frontend
node --test tests/bundleBaseline.test.mjs
```

Expected: `ERR_MODULE_NOT_FOUND` for `scripts/check-bundle-baseline.mjs`.

- [ ] **Step 5: Commit the failing bundle-contract test and baseline.**

```powershell
git add frontend/performance/bundle-baseline.json frontend/tests/bundleBaseline.test.mjs
git diff --cached --check
git commit -m "test: define frontend bundle baseline contract"
```

### Task 2: Implement manifest-based bundle analysis

**Files:**

- Create: `frontend/scripts/check-bundle-baseline.mjs`
- Modify: `frontend/tests/bundleBaseline.test.mjs`

- [ ] **Step 1: Implement file-size and manifest helpers.**

Export functions from the ESM script and keep CLI execution behind an entry-point check:

```js
import { gzipSync } from 'node:zlib'
import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative } from 'node:path'

export function assetSize(distDir, file) {
  const contents = readFileSync(join(distDir, file))
  return { rawBytes: contents.byteLength, gzipBytes: gzipSync(contents).byteLength }
}

export function manifestEntry(manifest) {
  const entries = Object.entries(manifest).filter(([, value]) => value.isEntry)
  if (entries.length !== 1 || entries[0][0] !== 'src/main.tsx') {
    throw new Error('manifest must contain exactly one src/main.tsx entry')
  }
  return entries[0][1]
}
```

- [ ] **Step 2: Implement the static closure and reports.**

Only follow `imports`, never `dynamicImports`. Add files to a `Set` before recursing to avoid double-counting. For every entry in the closure, count `file` when it ends in `.js` and every `css` value when it ends in `.css`. Return sorted relative filenames and `{ rawBytes, gzipBytes }` totals.

Locate the Excel entry by an output filename matching `/^assets\/exceljs\.min-.*\.js$/`. Require exactly one match. Set `isInitial` from membership in the closure's JavaScript file set. For route chunks, consider every manifest `file` ending in `.js` that is neither in the static closure nor the ExcelJS file; record the maximum one and fail if it exceeds `largest_route_js`.

- [ ] **Step 3: Implement explicit budget failures and CLI output.**

Use one helper for stable error wording:

```js
function requireBudget(label, actual, budget) {
  if (actual.rawBytes > budget.raw_bytes) {
    throw new Error(`${label} raw bytes ${actual.rawBytes} exceed budget ${budget.raw_bytes}`)
  }
  if (actual.gzipBytes > budget.gzip_bytes) {
    throw new Error(`${label} gzip bytes ${actual.gzipBytes} exceed budget ${budget.gzip_bytes}`)
  }
}
```

Call it for `initial_js`, `initial_css`, `largest_route_js`, and `exceljs_dynamic_js`. After ExcelJS budget validation, throw exactly `exceljs dynamic chunk is part of the initial entry closure` when `isInitial` is true. The CLI must default to `dist` and `performance/bundle-baseline.json`, print JSON with `initial`, `largestRoute`, and `exceljs`, and exit 1 with `bundle baseline failed: <message>` on any error.

- [ ] **Step 4: Run unit tests and verify green.**

Run:

```powershell
Set-Location frontend
node --test tests/bundleBaseline.test.mjs
```

Expected: all manifest fixture, budget, and ExcelJS isolation tests pass.

- [ ] **Step 5: Commit the analyzer.**

```powershell
git add frontend/scripts/check-bundle-baseline.mjs frontend/tests/bundleBaseline.test.mjs
git diff --cached --check
git commit -m "feat: add frontend bundle baseline analyzer"
```

### Task 3: Integrate Vite, npm, and CI

**Files:**

- Modify: `frontend/vite.config.ts`
- Modify: `frontend/package.json`
- Modify: `.github/workflows/cloud-p1b2a-gate.yml`
- Modify: `frontend/tests/bundleBaseline.test.mjs`

- [ ] **Step 1: Add a failing build-artifact test.**

Add a source contract that expects Vite's build configuration to enable a manifest and the package scripts to expose both commands:

```js
const viteConfig = readFileSync('vite.config.ts', 'utf8')
const packageJson = JSON.parse(readFileSync('package.json', 'utf8'))
assert.match(viteConfig, /build:\s*\{\s*manifest:\s*true/s)
assert.equal(packageJson.scripts['check:bundle:dist'], 'node scripts/check-bundle-baseline.mjs')
assert.equal(packageJson.scripts['test:bundle'], 'npm run build && npm run check:bundle:dist')
```

- [ ] **Step 2: Verify red.**

Run:

```powershell
Set-Location frontend
node --test tests/bundleBaseline.test.mjs
```

Expected: the manifest and package-script assertions fail.

- [ ] **Step 3: Enable the manifest and scripts.**

Extend the existing Vite config without changing its server proxy:

```ts
build: {
  manifest: true,
},
```

Add these exact package commands:

```json
"check:bundle:dist": "node scripts/check-bundle-baseline.mjs",
"test:bundle": "npm run build && npm run check:bundle:dist"
```

- [ ] **Step 4: Make the CI gate fail closed on bundle baseline regressions.**

Immediately after the existing `Frontend build` step in `.github/workflows/cloud-p1b2a-gate.yml`, add:

```yaml
      - name: Frontend bundle baseline
        working-directory: frontend
        run: npm run check:bundle:dist
```

Do not add `continue-on-error`, a bypass, a warning-only branch, or a second frontend build.

- [ ] **Step 5: Run the real build baseline and complete frontend tests.**

Run:

```powershell
Set-Location frontend
npm run test:bundle
npm run test:all
npm run build
Set-Location ..
```

Expected: baseline JSON reports initial JS/CSS, the largest route, and an isolated ExcelJS resource; all commands exit 0.

- [ ] **Step 6: Commit integration.**

```powershell
git add frontend/vite.config.ts frontend/package.json .github/workflows/cloud-p1b2a-gate.yml frontend/tests/bundleBaseline.test.mjs
git diff --cached --check
git commit -m "ci: enforce frontend bundle baseline"
```

### Task 4: Delivery evidence

**Files:**

- Modify: `docs/superpowers/plans/2026-09-13-frontend-bundle-baseline-governance.md`

- [ ] **Step 1: Run the full repository gate.**

Run:

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests -q
Set-Location ..\frontend
npm run test:bundle
npm run test:all
Set-Location ..
git diff --check
git status --short
```

Expected: backend and frontend suites pass; the manifest baseline succeeds; all generated `dist` files remain untracked.

- [ ] **Step 2: Record exact measurements and commit.**

Append the analyzer's exact JSON output, test totals, command durations, and the fact that PostgreSQL execution remains CI-owned because Docker Desktop is not running locally. Mark completed steps and run:

```powershell
git add docs/superpowers/plans/2026-09-13-frontend-bundle-baseline-governance.md
git diff --cached --check
git commit -m "docs: record frontend bundle baseline verification"
```
