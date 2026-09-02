# CVM Nginx Entry Point Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the production frontend image start Nginx without executing the blocked IPv6 default-listener initializer.

**Architecture:** Preserve the official Nginx entrypoint and all existing application configuration. Remove only `10-listen-on-ipv6-by-default.sh` during the production image build, so the remaining official initialization scripts and the configured Nginx daemon continue normally.

**Tech Stack:** Docker multi-stage build, Nginx Alpine, pytest deployment contracts, Vite.

---

### Task 1: Define the deployment regression contract

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_production_runtime_contract.py`
- Test: `bowei_ai_dashboard/tests/test_production_runtime_contract.py`

- [ ] **Step 1: Write the failing test**

Add this test after `test_frontend_dockerfile_uses_tracked_lockfile_with_npm_ci`:

```python
def test_frontend_dockerfile_disables_only_the_blocked_ipv6_entrypoint_hook():
    dockerfile = _read("Dockerfile.frontend")

    assert "rm -f /docker-entrypoint.d/10-listen-on-ipv6-by-default.sh" in dockerfile
    assert "ENTRYPOINT" not in dockerfile
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m pytest bowei_ai_dashboard/tests/test_production_runtime_contract.py::test_frontend_dockerfile_disables_only_the_blocked_ipv6_entrypoint_hook -q`

Expected: FAIL because the Dockerfile does not yet remove the blocked hook.

- [ ] **Step 3: Commit the regression test**

```bash
git add bowei_ai_dashboard/tests/test_production_runtime_contract.py
git commit -m "test: cover nginx ipv6 entrypoint workaround"
```

### Task 2: Apply the smallest frontend image change

**Files:**
- Modify: `Dockerfile.frontend`
- Test: `bowei_ai_dashboard/tests/test_production_runtime_contract.py`

- [ ] **Step 1: Add the production-stage hook removal**

Replace the production base-image instruction with:

```dockerfile
FROM nginx:alpine
RUN rm -f /docker-entrypoint.d/10-listen-on-ipv6-by-default.sh \
    && apk upgrade --no-cache
```

- [ ] **Step 2: Run the focused test and verify it passes**

Run: `python -m pytest bowei_ai_dashboard/tests/test_production_runtime_contract.py::test_frontend_dockerfile_disables_only_the_blocked_ipv6_entrypoint_hook -q`

Expected: PASS.

- [ ] **Step 3: Commit the implementation**

```bash
git add Dockerfile.frontend
git commit -m "fix: bypass blocked nginx ipv6 entrypoint hook"
```

### Task 3: Verify the release artifact before CVM switch

**Files:**
- Verify: `Dockerfile.frontend`
- Verify: `nginx.conf`
- Verify: `frontend/`

- [ ] **Step 1: Run the production runtime contract suite**

Run: `python -m pytest bowei_ai_dashboard/tests/test_production_runtime_contract.py bowei_ai_dashboard/tests/test_production_deployment_contract.py -q`

Expected: PASS with no failed deployment contract.

- [ ] **Step 2: Build the frontend bundle**

Run: `npm --prefix frontend run build`

Expected: exit code 0 and a Vite production bundle in `frontend/dist`.

- [ ] **Step 3: Run the repository runtime gate on the pushed branch**

Push the branch and let `.github/workflows/cloud-p1b2a-gate.yml` run. Its
`Build frontend image without cache`, `Frontend image nginx configuration`, and
`Complete Compose smoke and port isolation` steps build the image, run
`nginx -t`, wait for `mowayspos-frontend` to become healthy, and verify `/` and
`/api/health` through `127.0.0.1:18100`.

Expected: the workflow succeeds with the frontend health check healthy.

### Task 4: Publish and apply the immutable release

**Files:**
- Verify: `.github/workflows/`
- Verify: `docs/tencent-cvm-first-deploy.md`

- [ ] **Step 1: Merge the verified implementation commit into `main` and publish with the existing immutable-image workflow**

Push the verified branch, merge its implementation commit into `main`, then run
`.github/workflows/cloud-p1b2b-a-ghcr-private-publish.yml` with
`operation=publish`. The workflow only publishes tags equal to the full
`main` commit SHA; it builds the images before login, scans them, rejects any
existing tag, pushes the immutable backend and frontend tags, and verifies the
remote digests.

- [ ] **Step 2: On CVM, pull the immutable release and update only the application image tag**

Run from `/opt/mowayspos`:

```bash
set -euo pipefail
read -r -p 'Verified full main commit SHA: ' release_sha
printf '%s\n' "$release_sha" | grep -Eq '^[0-9a-f]{40}$'
dc=(docker compose --env-file /opt/mowayspos/production.env -f /opt/mowayspos/docker-compose.prod.yml)
MOWAYS_IMAGE_TAG="$release_sha" "${dc[@]}" pull backend frontend
sed -i "s/^MOWAYS_IMAGE_TAG=.*/MOWAYS_IMAGE_TAG=$release_sha/" /opt/mowayspos/production.env
grep -Fx "MOWAYS_IMAGE_TAG=$release_sha" /opt/mowayspos/production.env
```

- [ ] **Step 3: Recreate the application containers and verify all runtime boundaries**

Run:

```bash
"${dc[@]}" up -d --no-build --no-deps backend frontend
docker inspect --format '{{.Name}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' mowayspos-postgres mowayspos-backend mowayspos-frontend
curl --fail --silent --show-error http://127.0.0.1:18100/ >/dev/null
curl --fail --silent --show-error http://127.0.0.1:18100/api/health
test "$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:18100/api/auth/me)" = "401"
```

Expected: the frontend is healthy without changing PostgreSQL data, host Nginx, DNS, TLS, or unrelated host services.
