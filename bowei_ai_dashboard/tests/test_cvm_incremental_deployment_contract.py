from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github/workflows/cloud-cvm-incremental-deploy.yml"
OVERRIDE_PATH = REPOSITORY_ROOT / "docker-compose.prod.incremental.yml"
SCRIPT_PATH = REPOSITORY_ROOT / "scripts/cvm-incremental-deploy.sh"
RUNBOOK_PATH = REPOSITORY_ROOT / "docs/tencent-cvm-incremental-deploy.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_incremental_compose_mounts_only_application_runtime_targets():
    compose = _read(OVERRIDE_PATH)

    for expected in (
        "${MOWAYS_RUNTIME_ROOT:-/opt/mowayspos/runtime}/backend/app:/app/app:ro",
        "${MOWAYS_RUNTIME_ROOT:-/opt/mowayspos/runtime}/backend/migrations:/app/migrations:ro",
        "${MOWAYS_RUNTIME_ROOT:-/opt/mowayspos/runtime}/frontend-dist:/usr/share/nginx/html:ro",
    ):
        assert expected in compose
    assert "/app/data/achievement-attachments" in compose
    assert "/app/data/project-init-attachments" in compose
    assert "ports:" not in compose


def test_remote_script_is_no_build_and_has_health_checked_rollback():
    script = _read(SCRIPT_PATH)

    for expected in (
        "rsync -aH --delete",
        "--no-build --no-deps --force-recreate",
        "config --quiet",
        "alembic upgrade head",
        "http://127.0.0.1:18100/api/health",
        "restore_on_failure",
        ".last-successful-release",
    ):
        assert expected in script
    for forbidden in ("docker build", "docker pull", "docker login", "postgres:"):
        assert forbidden not in script


def test_workflow_is_manual_main_only_and_uses_pinned_cvm_secrets():
    workflow = _read(WORKFLOW_PATH)

    for expected in (
        "workflow_dispatch:",
        '[[ "$GITHUB_REF" == "refs/heads/main" ]]',
        "CVM_HOST",
        "CVM_USER",
        "CVM_SSH_KEY",
        "CVM_KNOWN_HOSTS",
        "StrictHostKeyChecking=yes",
        "npm run build",
        "rsync -az --delete",
        "cloud-p1b2b-a-ghcr-private-publish.yml",
    ):
        assert expected in workflow
    for forbidden in ("pull_request:", "docker build", "docker pull", "docker login"):
        assert forbidden not in workflow


def test_runbook_explains_component_selection_and_image_fallback():
    runbook = _read(RUNBOOK_PATH)

    for expected in (
        "CVM_HOST",
        "CVM_USER",
        "CVM_SSH_KEY",
        "CVM_KNOWN_HOSTS",
        "gh workflow run cloud-cvm-incremental-deploy.yml",
        "--ref main",
        "component=backend",
        "component=frontend",
        "run_migrations=true",
        "cloud-p1b2b-a-ghcr-private-publish.yml",
        "without rebuilding the application images",
    ):
        assert expected in runbook
