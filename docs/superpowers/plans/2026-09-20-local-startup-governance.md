# Local Startup Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. This plan is executed inline in the current session; no subagents are used.

**Goal:** Make the local 6004/6005/8011 development stack start only after readiness checks, use explicit runtime configuration, and support safe shutdown.

**Architecture:** Add one PowerShell orchestration script for the V2 stack. It validates ports, launches the V2 backend and frontend, polls readiness endpoints, records only the launched process IDs, and opens the browser after readiness. Keep the existing Python backend safe launcher as the single source for local DB/CORS values and leave business code untouched.

**Tech Stack:** PowerShell, Windows process APIs, Python/Uvicorn, Vite, Node built-in tests, Vitest, existing HTTP health endpoints.

---

### Task 1: Add startup contract tests

**Files:**
- Modify: `frontend-v2/tests/authFlow.test.mjs`

- [ ] **Step 1: Write failing tests**

Add assertions that the root V2 launcher delegates to `start-v2-dev.ps1`, that the PowerShell script checks ports `6005` and `8011`, polls `/api/health`, and records a state file under `.runtime`.

- [ ] **Step 2: Run the targeted test**

Run: `node --test tests/authFlow.test.mjs`

Expected: FAIL because the orchestration script and delegation do not exist yet.

### Task 2: Implement the PowerShell V2 startup orchestrator

**Files:**
- Create: `start-v2-dev.ps1`
- Modify: `start-frontend-v2-dev.bat`
- Modify: `.gitignore`

- [ ] **Step 1: Implement explicit configuration and port checks**

The script uses `$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path`, ports `6005` and `8011`, and refuses to start when either port is already listening. It creates `.runtime`, starts `bowei_ai_dashboard/start-backend-v2-dev.bat` and `frontend-v2/start-frontend-v2-dev.bat` with `Start-Process`, and stores the process IDs in `.runtime/v2-dev-processes.json`.

- [ ] **Step 2: Implement readiness polling**

Poll `http://127.0.0.1:8011/api/health` until JSON `status` is `ok`, then poll `http://127.0.0.1:6005/` until HTTP 200. Use a 60-second deadline and throw a message naming the failed endpoint.

- [ ] **Step 3: Delegate the batch entry point**

Replace the root batch file's `start` plus fixed `timeout /t 6` flow with:

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-v2-dev.ps1"
```

- [ ] **Step 4: Ignore runtime state**

Add `.runtime/` to `.gitignore` without changing existing ignore rules.

### Task 3: Add safe shutdown

**Files:**
- Create: `stop-v2-dev.ps1`
- Create: `stop-frontend-v2-dev.bat`
- Modify: `frontend-v2/tests/authFlow.test.mjs`

- [ ] **Step 1: Add the failing shutdown contract**

Assert that the stop script reads `.runtime/v2-dev-processes.json`, stops only recorded process IDs when present, and removes the state file.

- [ ] **Step 2: Implement bounded shutdown**

Read the state file as JSON, call `Stop-Process -Id` only for existing recorded processes, ignore already-exited processes, and remove the state file. Never scan or kill all processes on ports or all `node`/`python` processes.

- [ ] **Step 3: Add the batch wrapper and run the targeted test**

The wrapper calls `powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-v2-dev.ps1"`. Run `node --test tests/authFlow.test.mjs` and expect all tests to pass.

### Task 4: Verify the complete startup path

**Files:**
- No production files.

- [ ] **Step 1: Validate script syntax and contracts**

Run:

```powershell
node --test frontend-v2/tests/authFlow.test.mjs
git diff --check
```

- [ ] **Step 2: Stop any existing V2 processes using the new script**

Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\stop-v2-dev.ps1` and confirm it only uses the recorded state file.

- [ ] **Step 3: Start the V2 stack using the new entry point**

Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\start-v2-dev.ps1` and confirm it reports backend health and frontend HTTP 200 before opening the browser.

- [ ] **Step 4: Run the existing V2 validation suite**

Run from `frontend-v2`:

```powershell
npm run build
npm run test:all
```

Expected: build succeeds; unit tests and contract tests have zero failures.

- [ ] **Step 5: Commit the focused change**

```powershell
git add start-v2-dev.ps1 stop-v2-dev.ps1 stop-frontend-v2-dev.bat start-frontend-v2-dev.bat frontend-v2/tests/authFlow.test.mjs .gitignore docs/superpowers/specs/2026-09-20-local-startup-governance-design.md docs/superpowers/plans/2026-09-20-local-startup-governance.md
git commit -m "chore: make local v2 startup reliable"
```
