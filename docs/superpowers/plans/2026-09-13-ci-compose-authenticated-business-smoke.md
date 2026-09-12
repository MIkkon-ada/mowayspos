# CI Compose Authenticated Business Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` in the current session task-by-task. Do not delegate to subagents for this repository.

**Goal:** Add a fail-closed authenticated business smoke to the existing PostgreSQL Compose CI gate without changing production behavior.

**Architecture:** A standard-library Python script runs inside the backend image but sends all requests through the `frontend` nginx service. It initializes only the disposable migrated CI database through the public setup endpoint, then verifies admin access and ordinary-user denial with manually replayed secure session cookies.

**Tech Stack:** Python 3.12 stdlib, FastAPI HTTP API, Docker Compose, GitHub Actions, pytest.

---

## File structure

- Create: `bowei_ai_dashboard/scripts/ci_compose_business_smoke.py`
- Create: `bowei_ai_dashboard/tests/test_ci_compose_business_smoke.py`
- Modify: `.github/workflows/cloud-p1b2a-gate.yml`
- Modify: `docs/superpowers/plans/2026-09-13-ci-compose-authenticated-business-smoke.md`

### Task 1: Define a failing HTTP-sequence contract

- [ ] **Step 1: Write a temporary-server test.**

Create `tests/test_ci_compose_business_smoke.py` using `http.server.ThreadingHTTPServer`. The handler records request method/path/cookie and returns the expected setup, login, authenticated list and deny responses. Import the proposed `SmokeClient` and `run_smoke`; assert the request sequence includes `/api/setup/status`, `/api/setup/init`, `/api/auth/login`, `/api/auth/me`, `/api/projects`, `/api/tasks?project_id=`, `/api/updates?project_id=`, `/api/confirmations/pending`, `/api/meetings?project_id=`, `/api/issues?project_id=`, `/api/achievements?project_id=`, and a normal-user `POST /api/projects` returning 403. Assert the recorded authenticated requests contain the session cookie value but no password is printed.

- [ ] **Step 2: Verify red.**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_ci_compose_business_smoke.py -q
```

Expected: missing `scripts.ci_compose_business_smoke` module.

- [ ] **Step 3: Commit the failing contract.**

```powershell
git add bowei_ai_dashboard/tests/test_ci_compose_business_smoke.py
git diff --cached --check
git commit -m "test: define CI authenticated business smoke"
```

### Task 2: Implement the container-safe client and scenario

- [ ] **Step 1: Implement `SmokeClient`.**

Use `urllib.request` with an explicit JSON body and headers. `request(method, path, body=None, session=None, expected_status=200)` must JSON-decode successful responses, parse only the session cookie value from `Set-Cookie`, redact `Cookie`, `password`, and response headers from exceptions, and raise if the exact expected status differs.

- [ ] **Step 2: Implement `run_smoke(base_url)`.**

Use fixed CI-only values: admin `ci_smoke_admin`, member `ci_smoke_member`, project `CI Compose Business Smoke`. Initialize only if status says uninitialized; otherwise reject the unexpected non-disposable database. Login the admin, call `/api/auth/me`, create the ordinary account via `/api/accounts`, create the draft project with the minimal `ProjectCreatePayload`, then call each named read endpoint with the project ID. Login the ordinary account and require its project-create request to return 403.

- [ ] **Step 3: Add a CLI entry point.**

Require `--base-url`; normalize its trailing slash; print only `smoke ok: METHOD path status` values and return 0. No production imports, database writes outside public API calls, or external network calls are allowed.

- [ ] **Step 4: Verify green.**

```powershell
python -m pytest tests/test_ci_compose_business_smoke.py -q
```

- [ ] **Step 5: Commit the smoke client.**

```powershell
git add bowei_ai_dashboard/scripts/ci_compose_business_smoke.py bowei_ai_dashboard/tests/test_ci_compose_business_smoke.py
git diff --cached --check
git commit -m "feat: add CI authenticated business smoke"
```

### Task 3: Make CI execute the smoke through nginx

- [ ] **Step 1: Add a failing workflow source contract.**

Extend `tests/test_ci_compose_business_smoke.py` to read the workflow. Assert it contains exactly one `exec -T backend python scripts/ci_compose_business_smoke.py --base-url http://frontend`, appears after `"${dc[@]}" up -d frontend` and its health wait, before the host-port assertion, and has no `continue-on-error` nearby.

- [ ] **Step 2: Verify red.**

```powershell
python -m pytest tests/test_ci_compose_business_smoke.py -q
```

- [ ] **Step 3: Insert the fail-closed CI command.**

In `Complete Compose smoke and port isolation`, immediately after frontend health succeeds and before `curl` host checks, insert the exact Docker Compose execution command. Do not alter migration, image build, ownership or cleanup steps.

- [ ] **Step 4: Run source and backend regressions.**

```powershell
python -m pytest tests/test_ci_compose_business_smoke.py tests/test_production_runtime_contract.py tests/test_production_runtime_security.py -q
```

- [ ] **Step 5: Commit CI integration.**

```powershell
git add .github/workflows/cloud-p1b2a-gate.yml bowei_ai_dashboard/tests/test_ci_compose_business_smoke.py
git diff --cached --check
git commit -m "ci: smoke authenticated business flows"
```

### Task 4: Delivery evidence

- [ ] **Step 1: Run full local suites.**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests -q
Set-Location ..\frontend
npm run test:all
npm run test:bundle
Set-Location ..
git diff --check
git status --short
```

- [ ] **Step 2: Attempt the Docker Compose smoke only if the local daemon is available.**

```powershell
docker version --format '{{.Server.Version}}'
```

If unavailable, record the exact daemon error and retain remote CI execution as required evidence. Do not enable Docker Desktop, alter its settings, or manufacture a local result.

- [ ] **Step 3: Record totals and commit.**

```powershell
git add docs/superpowers/plans/2026-09-13-ci-compose-authenticated-business-smoke.md
git diff --cached --check
git commit -m "docs: record CI business smoke verification"
```
