# Application-images-only security release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** Publish remediated backend and frontend GHCR images while guaranteeing that the release workflow and existing-database update instructions do not modify PostgreSQL or run a migration.

**Architecture:** The backend image updates Debian packages and uses fixed Python pins. The GHCR workflow is reduced to a two-image, fail-closed audit/publish flow. The CVM guide adds a bounded application-only procedure that targets application services with \`--no-deps\`.

**Tech Stack:** GitHub Actions, Docker/BuildKit, Trivy, Python 3.12, pytest, Debian slim, GHCR.

---

## File structure

- Modify \`bowei_ai_dashboard/requirements.txt\` and \`Dockerfile.backend\`: security-fixed runtime inputs.
- Modify \`bowei_ai_dashboard/tests/test_backend_image_dependency_contract.py\`: dependency and base-image regression contract.
- Modify \`.github/workflows/cloud-p1b2b-a-ghcr-private-publish.yml\`: backend/frontend only release pipeline.
- Modify \`bowei_ai_dashboard/tests/test_ghcr_private_publish_contract.py\`: two-image workflow regression contract.
- Modify \`docs/ghcr-private-image-publish.md\`: two-package release guide.
- Modify \`docs/tencent-cvm-first-deploy.md\` and \`bowei_ai_dashboard/tests/test_production_deployment_contract.py\`: no-database-change application update procedure.

### Task 1: Remediate backend image inputs

**Files:**

- Modify: \`bowei_ai_dashboard/tests/test_backend_image_dependency_contract.py\`
- Modify: \`bowei_ai_dashboard/requirements.txt\`
- Modify: \`Dockerfile.backend\`

- [ ] **Step 1: Write the failing regression tests**

Append to \`test_backend_image_dependency_contract.py\`:

\`\`\`python
def test_backend_security_dependency_pins_use_the_scanner_fixed_versions():
    requirements = REQUIREMENTS_PATH.read_text(encoding="utf-8")
    lines = {
        line.strip().split("==", 1)[0].lower(): line.strip()
        for line in requirements.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert lines["pypdf"] == "pypdf==6.14.2"
    assert lines["cryptography"] == "cryptography==50.0.0"


def test_backend_dockerfile_applies_debian_security_updates_before_installing_packages():
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")

    assert "apt-get upgrade -y --no-install-recommends" in dockerfile
    assert dockerfile.index("apt-get upgrade -y --no-install-recommends") < dockerfile.index(
        "apt-get install -y --no-install-recommends antiword"
    )
    assert dockerfile.index("apt-get install -y --no-install-recommends antiword") < dockerfile.index(
        "pip install --no-cache-dir -r requirements.txt"
    )
\`\`\`

- [ ] **Step 2: Verify red**

Run: \`python -m pytest bowei_ai_dashboard/tests/test_backend_image_dependency_contract.py -q\`

Expected: failure because the pins are \`pypdf==6.1.0\` / \`cryptography==46.0.5\`, and the Dockerfile lacks \`apt-get upgrade\`.

- [ ] **Step 3: Apply the smallest remediation**

Set the two requirement lines exactly:

\`\`\`text
cryptography==50.0.0
pypdf==6.14.2
\`\`\`

Replace the Dockerfile package layer with:

\`\`\`dockerfile
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends antiword \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt
\`\`\`

- [ ] **Step 4: Verify green and build**

Run:

\`\`\`powershell
python -m pytest bowei_ai_dashboard/tests/test_backend_image_dependency_contract.py bowei_ai_dashboard/tests/test_ai_config_crypto.py bowei_ai_dashboard/tests/test_project_init_file_parser.py bowei_ai_dashboard/tests/test_work_report_document_text.py -q
docker build --pull --no-cache -f Dockerfile.backend -t mowayspos-backend-security-check .
docker image rm mowayspos-backend-security-check
\`\`\`

Expected: all selected tests pass, build exits 0, and the temporary local image is removed.

- [ ] **Step 5: Commit**

\`\`\`powershell
git add bowei_ai_dashboard/requirements.txt Dockerfile.backend bowei_ai_dashboard/tests/test_backend_image_dependency_contract.py
git commit -m "fix: remediate backend image dependencies"
\`\`\`

### Task 2: Make GHCR publishing application-image-only

**Files:**

- Modify: \`bowei_ai_dashboard/tests/test_ghcr_private_publish_contract.py\`
- Modify: \`.github/workflows/cloud-p1b2b-a-ghcr-private-publish.yml\`
- Modify: \`docs/ghcr-private-image-publish.md\`

- [ ] **Step 1: Replace obsolete PostgreSQL expectations with failing two-image tests**

Delete \`POSTGRES_GO_CVES\` and every \`test_gosu_*\`, \`test_postgres_*\`, PostgreSQL-manifest, and PostgreSQL-exception assertion in \`test_ghcr_private_publish_contract.py\`. Keep the generic trigger, operation, secret, immutable-tag, push-order, and cleanup tests. Add:

\`\`\`python
def test_publish_workflow_audits_only_application_images():
    workflow = _publish_workflow()

    for expected in (
        "BACKEND_REPOSITORY: ghcr.io/mikkon-ada/mowayspos-backend",
        "FRONTEND_REPOSITORY: ghcr.io/mikkon-ada/mowayspos-frontend",
        'for image in ("backend", "frontend"):',
        "Scan backend image for fixable vulnerabilities",
        "Scan frontend image for fixable vulnerabilities",
    ):
        assert expected in workflow
    for forbidden in (
        "POSTGRES_REPOSITORY",
        "POSTGRES_UPSTREAM",
        "mowayspos-postgres",
        "gosu",
        "govulncheck",
    ):
        assert forbidden not in workflow


def test_publish_workflow_publishes_and_verifies_only_backend_and_frontend_packages():
    workflow = _publish_workflow()
    package_check = _step_block(workflow, "Verify GHCR packages are private")
    cleanup = _step_block(workflow, "Cleanup publish credentials and temporary images")

    assert 'for package in mowayspos-backend mowayspos-frontend; do' in package_check
    assert 'mowayspos-backend|mowayspos-frontend) expected_tag="$GITHUB_SHA" ;;' in package_check
    assert 'verify_pushed_digest "$BACKEND_TARGET"' in workflow
    assert 'verify_pushed_digest "$FRONTEND_TARGET"' in workflow
    assert 'refs=("$BACKEND_LOCAL" "$FRONTEND_LOCAL")' in cleanup
    assert "POSTGRES_" not in cleanup
\`\`\`

- [ ] **Step 2: Verify red**

Run: \`python -m pytest bowei_ai_dashboard/tests/test_ghcr_private_publish_contract.py -q\`

Expected: failures from PostgreSQL environment variables, scan steps, gosu logic, package loop, and documentation.

- [ ] **Step 3: Implement the two-image workflow**

In \`.github/workflows/cloud-p1b2b-a-ghcr-private-publish.yml\`:

1. Retain only backend/frontend repositories and local image variables.
2. Retain checkout, branch/SHA validation, operation validation, both builds, four Trivy scans, content/history validation, audit-only success, login, immutable tags, retag, push, remote digest checks, package privacy checks, and always-run cleanup.
3. Delete every PostgreSQL resolution, pull, gosu/go analysis, Trivy scan, scanner exception, tag, push, manifest verifier, package, and cleanup reference.
4. Make the sanitized finding loop exactly \`for image in ("backend", "frontend"):\`; any secret or fixable HIGH/CRITICAL finding fails.
5. Make immutable tags, pushes, remote digest checks, and private-package checks operate only on backend and frontend. The package loop must be:

\`\`\`bash
for package in mowayspos-backend mowayspos-frontend; do
  # existing metadata and mutable-tag checks
  case "$package" in
    mowayspos-backend|mowayspos-frontend) expected_tag="$GITHUB_SHA" ;;
    *) echo "Unexpected package name." >&2; exit 1 ;;
  esac
done
\`\`\`

6. Replace \`docs/ghcr-private-image-publish.md\` with a concise guide that names only the two application packages, explains audit vs publish, requires zero secret/fixable HIGH/CRITICAL findings, uses a full commit SHA tag, and states exactly: “The workflow does not publish, pull, recreate, or migrate PostgreSQL.”

- [ ] **Step 4: Verify green**

Run:

\`\`\`powershell
python -m pytest bowei_ai_dashboard/tests/test_ghcr_private_publish_contract.py -q
python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/cloud-p1b2b-a-ghcr-private-publish.yml').read_text(encoding='utf-8')); print('workflow_yaml=ok')"
\`\`\`

Expected: all contract tests pass and the parser prints \`workflow_yaml=ok\`.

- [ ] **Step 5: Commit**

\`\`\`powershell
git add .github/workflows/cloud-p1b2b-a-ghcr-private-publish.yml bowei_ai_dashboard/tests/test_ghcr_private_publish_contract.py docs/ghcr-private-image-publish.md
git commit -m "fix: publish application images only"
\`\`\`

### Task 3: Add the no-database-change CVM update procedure

**Files:**

- Modify: \`bowei_ai_dashboard/tests/test_production_deployment_contract.py\`
- Modify: \`docs/tencent-cvm-first-deploy.md\`

- [ ] **Step 1: Write the failing bounded-section test**

Add:

\`\`\`python
def _application_only_update_section(doc: str) -> str:
    match = re.search(
        r"## Existing database: application image update only\n(?P<body>.*?)(?=\n## |\Z)",
        doc,
        flags=re.DOTALL,
    )
    assert match, "missing existing-database application update section"
    return match.group("body")


def test_existing_database_update_never_targets_postgres_or_runs_migrations():
    section = _application_only_update_section(_read(DEPLOYMENT_DOC_PATH))

    assert "pull backend-permissions-init backend frontend" in section
    assert 'up -d --no-build --no-deps backend-permissions-init' in section
    assert 'up -d --no-build --no-deps backend frontend' in section
    for forbidden in ("alembic", "postgres", "MOWAYS_POSTGRES_IMAGE", "docker compose pull"):
        assert forbidden not in section
\`\`\`

- [ ] **Step 2: Verify red**

Run: \`python -m pytest bowei_ai_dashboard/tests/test_production_deployment_contract.py -q\`

Expected: failure because the bounded section does not exist.

- [ ] **Step 3: Add the procedure immediately below the guide introduction**

Insert:

\`\`\`markdown
## Existing database: application image update only

Use this procedure only when the CVM already has a healthy Moways database and
its data volume. It updates application images only: it does not pull, start,
recreate, or modify the database service, and it does not run a schema
migration. Preserve the current database connection values and
\`AI_CONFIG_ENCRYPTION_KEY\` in \`/opt/mowayspos/production.env\`.

\`\`\`bash
set -euo pipefail
cd /opt/mowayspos
dc=(
  docker compose
  --env-file /opt/mowayspos/production.env
  -f docker-compose.prod.yml
)
"${dc[@]}" config --quiet
"${dc[@]}" pull backend-permissions-init backend frontend
"${dc[@]}" up -d --no-build --no-deps backend-permissions-init
"${dc[@]}" up -d --no-build --no-deps backend frontend
curl --fail --silent --show-error http://127.0.0.1:18100/api/health
\`\`\`
\`\`\`

Keep all existing first-deployment instructions below this new section unchanged.

- [ ] **Step 4: Verify green**

Run:

\`\`\`powershell
python -m pytest bowei_ai_dashboard/tests/test_production_deployment_contract.py bowei_ai_dashboard/tests/test_production_runtime_contract.py -q
\`\`\`

Expected: every test passes, including the bounded no-database-change check.

- [ ] **Step 5: Commit**

\`\`\`powershell
git add docs/tencent-cvm-first-deploy.md bowei_ai_dashboard/tests/test_production_deployment_contract.py
git commit -m "docs: add application-only CVM update path"
\`\`\`

### Task 4: Final verification and controlled audit

**Files:** Verify only the files changed in Tasks 1–3.

- [ ] **Step 1: Run all changed-file contracts**

\`\`\`powershell
git diff main...HEAD --check
python -m pytest bowei_ai_dashboard/tests/test_backend_image_dependency_contract.py bowei_ai_dashboard/tests/test_ghcr_private_publish_contract.py bowei_ai_dashboard/tests/test_production_deployment_contract.py bowei_ai_dashboard/tests/test_production_runtime_contract.py -q
\`\`\`

Expected: clean diff and zero test failures.

- [ ] **Step 2: Run the CI backend suite**

Run: \`python -m pytest bowei_ai_dashboard/tests -q\`

Expected: no new failures versus the known CI baseline; stop and investigate any new failure.

- [ ] **Step 3: Confirm release scope**

Run:

\`\`\`powershell
git status --short
git log --oneline main..HEAD
git diff --stat main...HEAD
\`\`\`

Expected: no Compose, migration, database, or CVM mutation is included or performed.

- [ ] **Step 4: Submit and audit**

Push a PR to \`main\`; wait for required checks. After merge, dispatch only \`operation=audit\`. Do not run \`publish\` unless the audit succeeds and the user separately requests publication.
