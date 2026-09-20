# Frontend V2 Parallel Development Implementation Plan

> **For agentic workers:** Execute this plan inline in the current task with verification checkpoints. Do not dispatch subagents or create additional tasks.

**Goal:** Create a complete, independently runnable frontend-v2 copy of the current frontend, connected to the existing backend through the same API contract and ready for gradual visual redesign.

**Architecture:** Keep frontend unchanged as the stable frontend on port 6004. Create frontend-v2 as an independent Vite + React + TypeScript application on port 6005; both frontends proxy /api to the existing backend at http://127.0.0.1:8011. The first implementation copies the current pages, API modules, types, assets, tests, and bundle-baseline data without changing backend code.

**Tech Stack:** React 19, TypeScript, Vite, React Router, Vitest, Node test runner, existing REST APIs, file upload/download, and WebSocket voice transcription.

---

## File map

### New files and directories

- frontend-v2/: complete V2 copy of the current frontend source and tests.
- frontend-v2/package.json: V2 package name and scripts.
- frontend-v2/package-lock.json: V2 lockfile with the V2 package name.
- frontend-v2/vite.config.ts: V2 dev port 6005 and proxy target 8011.
- frontend-v2/index.html: V2 document title.
- frontend-v2/README.md: V2 startup and development instructions.
- frontend-v2/start-frontend-v2-dev.bat: V2-only Windows development launcher.
- start-frontend-v2-dev.bat: repository-level launcher for the backend and V2 together.

### Files intentionally not modified

- frontend/: remains the old stable frontend.
- bowei_ai_dashboard/: backend and database behavior remain unchanged.
- start-dev.bat: existing old-frontend launcher remains unchanged.

### Copied functional boundaries

- frontend-v2/src/api/: request and response boundary with the backend.
- frontend-v2/src/types.ts: current API-facing types.
- frontend-v2/src/app/, src/layouts/, src/pages/, src/components/, src/features/, src/domain/, src/context/, src/config/, src/compatibility/, and src/utils/: current routes, UI, domain behavior, and utilities.
- frontend-v2/public/: logos, login assets, and other static assets.
- frontend-v2/tests/: current contract tests.
- frontend-v2/performance/: current bundle baseline.

## Task 1: Copy the stable frontend into an isolated V2 directory

**Files:**

- Create: frontend-v2/ by copying the tracked source and configuration from frontend/.
- Exclude: node_modules/, dist/, *.log, *.zip, *.tsbuildinfo, generated vite.config.js, and generated vite.config.d.ts.

- [ ] Step 1: Confirm the destination is unused.

Run from the repository root:

~~~
if (Test-Path .\frontend-v2) { throw 'frontend-v2 already exists; stop before overwriting it' }
~~~

Expected: the command exits without output.

- [ ] Step 2: Copy source, tests, assets, and configuration.

Run:

~~~
robocopy .\frontend .\frontend-v2 /E /XD node_modules dist /XF *.log *.zip *.tsbuildinfo vite.config.js vite.config.d.ts
if ($LASTEXITCODE -gt 7) { throw "robocopy failed with exit code $LASTEXITCODE" }
~~~

Expected: frontend-v2 contains src, public, tests, scripts, performance, package.json, and package-lock.json, but does not contain node_modules or dist.

- [ ] Step 3: Confirm old frontend files are untouched.

Run:

~~~
git status --short -- frontend
Test-Path .\frontend-v2\node_modules
Test-Path .\frontend-v2\dist
~~~

Expected: no status output for frontend; both Test-Path results are False.

- [ ] Step 4: Commit the isolated copy.

Run:

~~~
git add -- frontend-v2
git commit -m "chore: scaffold frontend v2 baseline"
~~~

Expected: one commit containing only the new frontend-v2 baseline.

## Task 2: Give V2 independent identity and port configuration

**Files:**

- Modify: frontend-v2/package.json
- Modify: frontend-v2/package-lock.json
- Modify: frontend-v2/vite.config.ts
- Modify: frontend-v2/index.html
- Modify: frontend-v2/README.md
- Create: frontend-v2/start-frontend-v2-dev.bat

- [ ] Step 1: Change the V2 package name.

In frontend-v2/package.json, change only the package name to:

~~~
"name": "bowei-ai-frontend-v2"
~~~

Keep all existing scripts and dependency versions unchanged.

- [ ] Step 2: Change the Vite development port.

In frontend-v2/vite.config.ts, change port: 6004 to:

~~~
port: 6005,
~~~

Keep the API proxy target, ws: true, and the manifest build setting unchanged.

- [ ] Step 3: Distinguish the browser title.

In frontend-v2/index.html, change the title to:

~~~
<title>博维AI驾驶舱 V2</title>
~~~

Keep the root element, module entry, meta tags, and asset references unchanged.

- [ ] Step 4: Update the V2 README.

frontend-v2/README.md must state that V2 runs on http://127.0.0.1:6005, uses the backend at http://127.0.0.1:8011, requires consistent 127.0.0.1 host usage because of the host-only bowei_session Cookie, and supports npm install, npm run dev, npm run build, npm run test:unit, npm run test:contracts, and npm run test:all.

- [ ] Step 5: Add the V2-only launcher.

Create frontend-v2/start-frontend-v2-dev.bat:

~~~
@echo off
setlocal

cd /d %~dp0

if not exist node_modules (
  npm install
)

npm run dev

endlocal
~~~

- [ ] Step 6: Regenerate V2 lockfile metadata.

Run from frontend-v2:

~~~
npm install --package-lock-only --ignore-scripts
~~~

Expected: package-lock.json names the project bowei-ai-frontend-v2; dependency versions remain compatible with the copied lockfile.

- [ ] Step 7: Commit the V2 runtime configuration.

Run from the repository root:

~~~
git add -- frontend-v2/package.json frontend-v2/package-lock.json frontend-v2/vite.config.ts frontend-v2/index.html frontend-v2/README.md frontend-v2/start-frontend-v2-dev.bat
git commit -m "chore: configure frontend v2 runtime"
~~~

Expected: the commit contains only V2 identity, port, documentation, and launcher changes.

## Task 3: Add a repository-level V2 startup command

**Files:**

- Create: start-frontend-v2-dev.bat

- [ ] Step 1: Create the V2 full-stack launcher.

Create start-frontend-v2-dev.bat:

~~~
@echo off
setlocal
cd /d %~dp0

echo ===================================
echo   博维 AI 驾驶舱 V2 开发环境
echo ===================================

start "博维-V2后端" cmd /k ""%~dp0bowei_ai_dashboard\start-backend-dev.bat""
start "博维-V2前端" cmd /k ""%~dp0frontend-v2\start-frontend-v2-dev.bat""

timeout /t 6 /nobreak > nul
start "" "http://127.0.0.1:6005"

echo.
echo 已启动：
echo   后端：http://127.0.0.1:8011
echo   V2前端：http://127.0.0.1:6005
pause
endlocal
~~~

- [ ] Step 2: Verify the old launcher is unchanged.

Run:

~~~
git diff -- start-dev.bat
~~~

Expected: no output.

- [ ] Step 3: Commit the launcher.

Run:

~~~
git add -- start-frontend-v2-dev.bat
git commit -m "chore: add frontend v2 dev launcher"
~~~

Expected: one new repository-level launcher commit.

## Task 4: Install V2 dependencies and verify the baseline

**Files:**

- Read: frontend-v2/package.json
- Read: frontend-v2/vite.config.ts
- Read: frontend-v2/src/api/client.ts
- Read: frontend-v2/src/app/routes.tsx

- [ ] Step 1: Install the locked dependency set.

Run from frontend-v2:

~~~
npm ci
~~~

Expected: exit code 0, with node_modules created under frontend-v2; the old frontend/node_modules is not modified.

- [ ] Step 2: Run TypeScript and production build checks.

Run:

~~~
npm run build
~~~

Expected: exit code 0 and frontend-v2/dist/index.html exists.

- [ ] Step 3: Run V2 unit tests.

Run:

~~~
npm run test:unit
~~~

Expected: exit code 0; the copied Vitest tests execute from the V2 directory.

- [ ] Step 4: Run V2 contract tests.

Run:

~~~
npm run test:contracts
~~~

Expected: exit code 0; source-path assertions resolve against frontend-v2, while backend compatibility assertions continue to resolve against the repository bowei_ai_dashboard directory.

- [ ] Step 5: Run the bundle baseline check.

Run:

~~~
npm run test:bundle
~~~

Expected: exit code 0; V2 produces its own dist and passes the copied bundle budget.

- [ ] Step 6: Commit the verified baseline state.

Do not add frontend-v2/node_modules or frontend-v2/dist. Run:

~~~
git status --short
git add -- frontend-v2
git commit -m "test: verify frontend v2 baseline"
~~~

Expected: only tracked V2 source, configuration, and test files are committed; generated dependencies and build output remain ignored.

## Task 5: Verify both frontends can coexist against the same backend

**Files:**

- Read: frontend/vite.config.ts
- Read: frontend-v2/vite.config.ts
- Read: frontend/README.md
- Read: frontend-v2/README.md

- [ ] Step 1: Start the backend and both frontend servers.

Use three terminals from the repository root:

~~~
& .\bowei_ai_dashboard\start-backend-dev.bat
~~~

~~~
Set-Location .\frontend
npm run dev
~~~

~~~
Set-Location .\frontend-v2
npm run dev
~~~

Expected: old frontend reports http://127.0.0.1:6004/; V2 reports http://127.0.0.1:6005/; both proxy /api to http://127.0.0.1:8011.

- [ ] Step 2: Check both HTML entry points.

Run after both Vite servers are ready:

~~~
(Invoke-WebRequest http://127.0.0.1:6004 -UseBasicParsing).StatusCode
(Invoke-WebRequest http://127.0.0.1:6005 -UseBasicParsing).StatusCode
~~~

Expected: both commands print 200.

- [ ] Step 3: Verify API proxy reachability.

Use the same host form for browser access and check the login page in both URLs. Confirm that each page loads without a Vite proxy error and that a development login can reach the existing /api/auth/me flow.

Expected: both frontends can use the same backend account; V2 does not require a new backend route.

- [ ] Step 4: Confirm no old frontend regression.

Run:

~~~
git diff -- frontend
git status --short
~~~

Expected: no diff under frontend; only intended V2 files and any pre-existing user files are present.

- [ ] Step 5: Record coexistence verification.

If no source changes were needed, record the verification in the task report rather than creating an empty commit. If a V2-only fix is required, commit it with:

~~~
git add -- frontend-v2 start-frontend-v2-dev.bat
git commit -m "fix: make frontend v2 coexist with legacy frontend"
~~~

## Task 6: Establish the visual-redesign starting point

**Files:**

- Modify later: frontend-v2/src/styles.css
- Modify later: frontend-v2/src/layouts/AppLayout.tsx
- Modify later: frontend-v2/src/layouts/ProjectLayout.tsx
- Modify later: frontend-v2/src/components/Sidebar.tsx

- [ ] Step 1: Do not change visual behavior during baseline creation.

Keep the first V2 commit functionally equivalent to the old frontend. This gives every later visual change a known-good reference.

- [ ] Step 2: Use only V2 for visual experiments after baseline verification.

Begin with the application shell and shared style variables before changing individual business pages.

- [ ] Step 3: Use focused verification for each visual change.

For a style-only change, use V2 hot reload first, then run npm run build. Run the affected module tests and the full suite at module milestones or before delivery, rather than after every CSS edit.

## Final verification checklist

- [ ] frontend/ remains unchanged and remains the old stable frontend.
- [ ] frontend-v2/ exists with copied routes, API modules, types, assets, tests, and bundle baseline.
- [ ] V2 uses port 6005; old frontend uses port 6004.
- [ ] Both Vite configurations proxy /api to http://127.0.0.1:8011.
- [ ] V2 has no tracked node_modules, dist, logs, or generated TypeScript build artifacts.
- [ ] V2 build, unit tests, contract tests, and bundle check have recorded results.
- [ ] Both frontends can be opened against the same development backend.
- [ ] No production deployment or backend/database change is part of this baseline creation.

