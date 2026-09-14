# CVM Incremental Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manually-triggered GitHub Actions path that synchronizes ordinary backend/frontend code changes to the CVM without rebuilding application images.

**Architecture:** Keep the immutable GHCR images as the runtime base. Mount CVM-managed backend source and frontend `dist` directories through a Compose override, stage files with `rsync`, and let a remote shell script perform backup, activation, health verification, and rollback.

**Tech Stack:** GitHub Actions, Bash, OpenSSH, rsync, Docker Compose, Python pytest, Vite.

---

### Task 1: Add the incremental runtime contract

**Files:**
- Create: `docker-compose.prod.incremental.yml`
- Create: `scripts/cvm-incremental-deploy.sh`

- [ ] **Step 1: Add read-only runtime mounts**

Create the Compose override with backend code and migrations mounted from `${MOWAYS_RUNTIME_ROOT:-/opt/mowayspos/runtime}` and frontend static files mounted from the same root. Keep the existing attachment mounts in the backend service so the override cannot discard them.

- [ ] **Step 2: Add the remote activation script**

Implement exact component paths for `backend`, `frontend`, and `all`. The script must back up active directories, sync staging with `rsync --archive --hard-links --delete`, run `docker compose config --quiet`, optionally run `backend alembic upgrade head`, recreate only the selected application containers with `--no-build --no-deps`, wait for healthy status, check `/api/health`, and restore the backup on any failure.

- [ ] **Step 3: Validate shell and Compose text locally**

Run:

```powershell
bash -n scripts/cvm-incremental-deploy.sh
git diff --check
```

Expected: both commands exit with status 0.

- [ ] **Step 4: Commit the runtime contract**

```powershell
git add docker-compose.prod.incremental.yml scripts/cvm-incremental-deploy.sh
git commit -m "feat: add CVM incremental runtime contract"
```

### Task 2: Add the GitHub Actions synchronization workflow

**Files:**
- Create: `.github/workflows/cloud-cvm-incremental-deploy.yml`
- Modify: `.github/workflows/cloud-p1b2a-gate.yml`

- [ ] **Step 1: Add a manual main-only Workflow**

Create a `workflow_dispatch` Workflow with `component`, `base_sha`, and `run_migrations` inputs. Validate that the ref is `refs/heads/main`, the checkout SHA is complete, the component is valid, and the changed range does not include dependency, Docker, Nginx, or production Compose files.

- [ ] **Step 2: Build only the selected frontend artifact**

For `frontend` or `all`, install Node 24 with the existing lockfile, run `npm ci`, and run `npm run build`. Do not run Docker build or image publish steps.

- [ ] **Step 3: Transfer and activate the selected component**

Create an SSH key and known-hosts file from Secrets, preflight `/opt/mowayspos`, upload only the selected staging trees plus the Compose override and remote activation script, then invoke the remote script with `RELEASE_SHA`, `COMPONENT`, and `RUN_MIGRATIONS`.

- [ ] **Step 4: Make the production gate aware of deployment-contract changes**

Add the new Workflow, override Compose file, remote script, and design/runbook paths to the existing production gate `pull_request.paths` list so changes to this mechanism cannot bypass the gate.

- [ ] **Step 5: Commit the Workflow**

```powershell
git add .github/workflows/cloud-cvm-incremental-deploy.yml .github/workflows/cloud-p1b2a-gate.yml
git commit -m "feat: add GitHub Actions CVM incremental deploy"
```

### Task 3: Add the lightweight contract test and operator runbook

**Files:**
- Create: `bowei_ai_dashboard/tests/test_cvm_incremental_deployment_contract.py`
- Create: `docs/tencent-cvm-incremental-deploy.md`
- Modify: `docs/production-runtime-contract.md`

- [ ] **Step 1: Write contract assertions**

Assert that the override mounts only the three intended application targets, the remote script contains `--no-build`, `--no-deps`, health verification, rollback, and no `docker build`/`docker pull`, and the Workflow references all four required Secrets and the main-branch guard.

- [ ] **Step 2: Write the operator runbook**

Document the one-time CVM directory preparation, required GitHub Secrets, the exact `gh workflow run` command, component selection, migration switch, and the fallback command to use the existing GHCR image workflow when the change touches dependencies or image configuration.

- [ ] **Step 3: Add the runbook to the production contract references**

Link the incremental runbook from `docs/production-runtime-contract.md` and state that it does not replace the immutable image path for dependency or base-runtime changes.

- [ ] **Step 4: Run the focused contract test**

```powershell
python -m pytest bowei_ai_dashboard/tests/test_cvm_incremental_deployment_contract.py -q
```

Expected: all contract assertions pass.

- [ ] **Step 5: Commit tests and documentation**

```powershell
git add bowei_ai_dashboard/tests/test_cvm_incremental_deployment_contract.py docs/tencent-cvm-incremental-deploy.md docs/production-runtime-contract.md
git commit -m "docs: document CVM incremental deployment"
```

### Task 4: Verify the complete local change

**Files:**
- No new files.

- [ ] **Step 1: Run only the relevant checks**

```powershell
bash -n scripts/cvm-incremental-deploy.sh
python -m pytest bowei_ai_dashboard/tests/test_cvm_incremental_deployment_contract.py -q
git diff --check
```

- [ ] **Step 2: Inspect the final diff**

```powershell
git status --short
git diff origin/main...HEAD --stat
git log --oneline --decorate -6
```

Expected: only the incremental deployment workflow, Compose override, remote script, contract test, and documentation are present; no production credential or image tag is committed.

- [ ] **Step 3: Report deployment prerequisites**

Report that code is ready on the branch, but no CVM deployment was executed because the four SSH Secrets are external to the repository and were not available to this local session.

