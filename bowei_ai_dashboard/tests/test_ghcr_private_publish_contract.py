from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PUBLISH_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/cloud-p1b2b-a-ghcr-private-publish.yml"
PUBLISH_DOCUMENTATION = REPOSITORY_ROOT / "docs/ghcr-private-image-publish.md"


def _workflow() -> str:
    return PUBLISH_WORKFLOW.read_text(encoding="utf-8")


def _step_block(workflow: str, step_name: str) -> str:
    marker = f"      - name: {step_name}"
    assert marker in workflow
    return workflow.split(marker, 1)[1].split("\n      - name:", 1)[0]


def _step_index(workflow: str, step_name: str) -> int:
    marker = f"- name: {step_name}"
    assert marker in workflow
    return workflow.index(marker)


def test_workflow_is_manual_and_main_restricted():
    workflow = _workflow()

    assert "workflow_dispatch:" in workflow
    assert "operation:" in workflow
    assert "audit" in workflow and "publish" in workflow
    assert '[[ "$GITHUB_REF" == "refs/heads/main" ]]' in workflow
    assert '[[ "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]]' in workflow
    for forbidden in ("pull_request:", "schedule:", "\non:\n  push:"):
        assert forbidden not in workflow


def test_publish_workflow_audits_only_application_images():
    workflow = _workflow()

    for expected in (
        "BACKEND_REPOSITORY: ghcr.io/mikkon-ada/mowayspos-backend",
        "FRONTEND_REPOSITORY: ghcr.io/mikkon-ada/mowayspos-frontend",
        'for image in ("backend", "frontend"):',
        "Scan backend image for secrets",
        "Scan frontend image for secrets",
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
        "alembic",
    ):
        assert forbidden not in workflow


def test_audit_fails_closed_for_secret_or_fixable_high_critical_findings():
    workflow = _workflow()
    enforce = _step_block(workflow, "Enforce sanitized scan results")

    assert 'for image in ("backend", "frontend"):' in enforce
    assert 'item.get("Severity") in {"HIGH", "CRITICAL"}' in enforce
    assert 'bool((item.get("FixedVersion") or "").strip())' in enforce
    assert "failed = failed or bool(secrets) or bool(records)" in enforce
    assert "raise SystemExit(1 if failed else 0)" in enforce
    assert "allowlist" not in enforce.lower()
    assert "vex" not in enforce.lower()


def test_audit_cannot_access_the_registry_or_push():
    workflow = _workflow()
    audit = _step_block(workflow, "Report audit-only success")

    assert "audit_only=ok" in audit
    for name in (
        "Log in to GHCR after all gates pass",
        "Check immutable tags before publishing",
        "Retag validated images",
        "Push immutable images",
        "Verify remote image digests",
        "Verify GHCR packages are private",
    ):
        block = _step_block(workflow, name)
        assert "inputs.operation == 'publish'" in block
    assert _step_index(workflow, "Enforce sanitized scan results") < _step_index(
        workflow, "Log in to GHCR after all gates pass"
    )


def test_publish_uses_immutable_sha_tags_for_only_two_private_packages():
    workflow = _workflow()
    immutable = _step_block(workflow, "Check immutable tags before publishing")
    packages = _step_block(workflow, "Verify GHCR packages are private")

    assert 'BACKEND_TARGET="$BACKEND_REPOSITORY:$GITHUB_SHA"' in immutable
    assert 'FRONTEND_TARGET="$FRONTEND_REPOSITORY:$GITHUB_SHA"' in immutable
    assert 'for package in mowayspos-backend mowayspos-frontend; do' in packages
    assert 'mowayspos-backend|mowayspos-frontend) expected_tag="$GITHUB_SHA"' in packages
    assert "latest" in packages and "main" in packages and "production" in packages
    assert "GHCR_PUBLISH_TOKEN" in workflow
    assert "GHCR_PUBLISH_TOKEN:" not in workflow.split("steps:", 1)[0]


def test_cleanup_removes_only_temporary_application_images():
    cleanup = _step_block(_workflow(), "Cleanup publish credentials and temporary images")

    assert "if: always()" in cleanup
    assert "docker logout ghcr.io" in cleanup
    assert 'refs=("$BACKEND_LOCAL" "$FRONTEND_LOCAL")' in cleanup
    assert "docker image rm" in cleanup
    for forbidden in ("POSTGRES_", "docker system prune", "docker image prune", "docker volume prune"):
        assert forbidden not in cleanup


def test_publish_documentation_describes_only_application_images_and_database_boundary():
    documentation = PUBLISH_DOCUMENTATION.read_text(encoding="utf-8")

    for expected in (
        "ghcr.io/mikkon-ada/mowayspos-backend",
        "ghcr.io/mikkon-ada/mowayspos-frontend",
        "does not publish, pull, recreate, or migrate PostgreSQL",
        "fixable HIGH/CRITICAL",
        "40-character commit SHA",
    ):
        assert expected in documentation
    for forbidden in ("mowayspos-postgres", "gosu", "govulncheck"):
        assert forbidden not in documentation
