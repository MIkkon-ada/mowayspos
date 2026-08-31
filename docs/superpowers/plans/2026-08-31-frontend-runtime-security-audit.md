# Frontend runtime security audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the frontend runtime image packages so the GitHub audit no longer reports the fixable OpenSSL findings, without publishing an image.

**Architecture:** Keep the existing two-stage Vite and Nginx build. Add one Alpine package-upgrade instruction only in the final Nginx runtime stage, leaving the application build stage, Nginx configuration, and image entrypoint unchanged.

**Tech Stack:** Docker, Nginx Alpine, GitHub Actions, Trivy.

---

### Task 1: Upgrade runtime security packages

**Files:**
- Modify: `Dockerfile.frontend:14-15`
- Test: GitHub Actions workflow `CLOUD P1B2B-A private GHCR image publish` in `audit` mode

- [ ] **Step 1: Verify the current vulnerability gate fails**

Run: `gh run view 33346322443 --repo MIkkon-ada/mowayspos --log-failed`

Expected: the audit reports `frontend_fixable_high_critical=2` for `libcrypto3` and `libssl3`.

- [ ] **Step 2: Add the minimal runtime-layer upgrade**

Add directly after the final runtime-stage base image:

```dockerfile
FROM nginx:alpine
RUN apk upgrade --no-cache
```

Do not modify the Node build stage, `nginx.conf`, `EXPOSE`, or `CMD`.

- [ ] **Step 3: Build the frontend image locally**

Run: `docker build --pull --no-cache -f Dockerfile.frontend -t mowayspos-frontend-security-audit:local .`

Expected: exit code 0 and a runnable Nginx image.

- [ ] **Step 4: Verify Nginx configuration**

Run: `docker run --rm --add-host backend:127.0.0.1 mowayspos-frontend-security-audit:local nginx -t`

Expected: `syntax is ok` and `test is successful`.

- [ ] **Step 5: Commit the remediation**

```bash
git add Dockerfile.frontend docs/superpowers/specs/2026-08-31-frontend-runtime-security-audit-design.md docs/superpowers/plans/2026-08-31-frontend-runtime-security-audit.md
git commit -m "fix: upgrade frontend runtime security packages"
```

### Task 2: Verify through GitHub Actions audit

**Files:**
- Modify: none
- Test: GitHub Actions run for the remediation branch

- [ ] **Step 1: Push the remediation branch and create a pull request**

Run:

```bash
git push -u origin codex/security-audit-nginx-20260831
gh pr create --repo MIkkon-ada/mowayspos --base main --head codex/security-audit-nginx-20260831 --title "fix: upgrade frontend runtime security packages"
```

Expected: GitHub creates a PR against `main`.

- [ ] **Step 2: Merge the approved PR**

Run:

```bash
$prNumber = gh pr list --repo MIkkon-ada/mowayspos --head codex/security-audit-nginx-20260831 --state open --json number --jq '.[0].number'
gh pr merge $prNumber --repo MIkkon-ada/mowayspos --merge
```

Expected: the remediation is merged into `main` without publishing images.

- [ ] **Step 3: Dispatch the audit workflow on `main`**

Run:

```bash
gh workflow run 'CLOUD P1B2B-A private GHCR image publish' --repo MIkkon-ada/mowayspos --ref main -f operation=audit
gh run list --repo MIkkon-ada/mowayspos --workflow 'CLOUD P1B2B-A private GHCR image publish' --branch main --event workflow_dispatch --limit 1
```

Expected: the workflow runs in audit mode and no image-push steps execute.

- [ ] **Step 4: Confirm the audit passes**

Run:

```bash
$runId = gh run list --repo MIkkon-ada/mowayspos --workflow 'CLOUD P1B2B-A private GHCR image publish' --branch main --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId'
gh run watch $runId --repo MIkkon-ada/mowayspos --exit-status
```

Expected: `frontend_secret_findings=0`, `frontend_fixable_high_critical=0`, and `audit_only=ok`.
