from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PUBLISH_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/cloud-p1b2b-a-ghcr-private-publish.yml"
P1B2A_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/cloud-p1b2a-gate.yml"
PUBLISH_DOCUMENTATION = REPOSITORY_ROOT / "docs/ghcr-private-image-publish.md"


def _publish_workflow() -> str:
    return PUBLISH_WORKFLOW.read_text(encoding="utf-8")


def _trigger_block(workflow: str) -> str:
    return workflow.split("on:\n", 1)[1].split("\npermissions:", 1)[0]


def _step_index(workflow: str, step_name: str) -> int:
    marker = f"- name: {step_name}"
    assert marker in workflow
    return workflow.index(marker)


def test_publish_workflow_is_manual_only():
    triggers = _trigger_block(_publish_workflow())

    assert re.fullmatch(r"\s+workflow_dispatch:\s*", triggers)
    for forbidden in (
        "push:",
        "pull_request:",
        "schedule:",
        "workflow_run:",
        "repository_dispatch:",
    ):
        assert forbidden not in triggers


def test_publish_workflow_has_top_level_serial_concurrency_lock():
    workflow = _publish_workflow()

    concurrency_index = workflow.index("\nconcurrency:\n")
    jobs_index = workflow.index("\njobs:\n")
    assert concurrency_index < jobs_index
    concurrency = workflow[concurrency_index:jobs_index]
    assert "group: cloud-p1b2b-a-ghcr-private-image-publish" in concurrency
    assert "cancel-in-progress: false" in concurrency


def test_publish_concurrency_group_is_fixed_across_commits_and_runs():
    workflow = _publish_workflow()
    concurrency = workflow.split("concurrency:\n", 1)[1].split("\njobs:\n", 1)[0]

    assert concurrency.count("group:") == 1
    for forbidden in (
        "github.sha",
        "github.ref",
        "github.run_id",
        "branch",
        "tag",
        "${{",
    ):
        assert forbidden not in concurrency


def test_publish_concurrency_does_not_cancel_the_active_publish():
    workflow = _publish_workflow()
    concurrency = workflow.split("concurrency:\n", 1)[1].split("\njobs:\n", 1)[0]

    assert re.search(r"^\s+cancel-in-progress:\s+false\s*$", concurrency, re.MULTILINE)
    assert "cancel-in-progress: true" not in concurrency


def test_publish_workflow_fails_closed_to_main_and_full_sha():
    workflow = _publish_workflow()

    assert "refs/heads/main" in workflow
    assert "^[0-9a-f]{40}$" in workflow
    assert "git rev-parse HEAD" in workflow


def test_publish_workflow_has_read_only_repository_permissions():
    workflow = _publish_workflow()

    permissions = workflow.split("permissions:\n", 1)[1].split("\nconcurrency:", 1)[0]
    assert permissions.strip() == "contents: read"
    for forbidden in (
        "packages: write",
        "actions: write",
        "contents: write",
        "id-token: write",
        "pull-requests: write",
    ):
        assert forbidden not in workflow


def test_publish_workflow_uses_dedicated_secret_not_github_token():
    workflow = _publish_workflow()

    assert "secrets.GHCR_PUBLISH_TOKEN" in workflow
    assert "github.repository_owner" in workflow
    assert "GITHUB_TOKEN" not in workflow
    assert "GHCR_PUBLISH_TOKEN:" not in workflow.split("steps:", 1)[0]


def test_publish_workflow_uses_exact_lowercase_image_names():
    workflow = _publish_workflow()

    for image in (
        "ghcr.io/mikkon-ada/mowayspos-backend",
        "ghcr.io/mikkon-ada/mowayspos-frontend",
        "ghcr.io/mikkon-ada/mowayspos-postgres",
    ):
        assert image in workflow

    assert "ghcr.io/MIkkon-ada" not in workflow


def test_backend_and_frontend_tags_use_only_the_full_commit_sha():
    workflow = _publish_workflow()

    assert 'BACKEND_TARGET="$BACKEND_REPOSITORY:$GITHUB_SHA"' in workflow
    assert 'FRONTEND_TARGET="$FRONTEND_REPOSITORY:$GITHUB_SHA"' in workflow
    assert "${GITHUB_SHA::" not in workflow
    for forbidden_tag in (":latest", ":main", ":production", ":stable"):
        assert forbidden_tag not in workflow


def test_postgres_uses_explicit_amd64_digest_and_architecture_tag():
    workflow = _publish_workflow()

    assert "docker.io/library/postgres:16-alpine" in workflow
    assert "POSTGRES_UPSTREAM_INDEX_DIGEST" in workflow
    assert "POSTGRES_AMD64_DIGEST" in workflow
    assert 'POSTGRES_TAG="linux-amd64-sha256-${POSTGRES_AMD64_DIGEST#sha256:}"' in workflow
    for forbidden in (
        "mowayspos-postgres:16-alpine",
        "mowayspos-postgres:16",
        "mowayspos-postgres:latest",
    ):
        assert forbidden not in workflow


def test_postgres_amd64_digest_is_selected_once_from_the_upstream_index():
    workflow = _publish_workflow()

    assert 'docker buildx imagetools inspect "$POSTGRES_UPSTREAM"' in workflow
    assert '--raw "$POSTGRES_UPSTREAM_REPOSITORY@$POSTGRES_UPSTREAM_INDEX_DIGEST"' in workflow
    assert '.platform.os == "linux"' in workflow
    assert '.platform.architecture == "amd64"' in workflow
    assert "amd64_match_count" in workflow
    assert '[[ "$amd64_match_count" != "1" ]]' in workflow
    assert "docker image inspect" not in workflow.split(
        "- name: Resolve PostgreSQL upstream index and linux/amd64 manifest", 1
    )[1].split("- name:", 1)[0]


def test_postgres_pull_uses_linux_amd64_and_the_immutable_platform_digest():
    workflow = _publish_workflow()

    assert "docker pull --platform linux/amd64" in workflow
    assert '"$POSTGRES_UPSTREAM_REPOSITORY@$POSTGRES_AMD64_DIGEST"' in workflow
    assert 'docker pull "$POSTGRES_LOCAL"' not in workflow


def test_postgres_overwrite_and_remote_checks_use_amd64_not_index_digest():
    workflow = _publish_workflow()

    assert '"$remote_digest" != "$POSTGRES_AMD64_DIGEST"' in workflow
    assert '"$postgres_remote" != "$POSTGRES_AMD64_DIGEST"' in workflow
    assert '"$remote_digest" != "$POSTGRES_UPSTREAM_INDEX_DIGEST"' not in workflow
    assert '"$postgres_remote" != "$POSTGRES_UPSTREAM_INDEX_DIGEST"' not in workflow
    assert "postgres_upstream_index_digest=" in workflow
    assert "postgres_linux_amd64_digest=" in workflow
    assert "postgres_remote_digest=" in workflow


def test_postgres_documentation_states_single_platform_scope():
    documentation = PUBLISH_DOCUMENTATION.read_text(encoding="utf-8")

    for expected in (
        "multi-platform",
        "x86_64",
        "linux/amd64",
        "upstream index digest",
        "platform manifest digest",
        "not a complete multi-architecture mirror",
    ):
        assert expected in documentation


def test_all_scans_and_content_checks_finish_before_registry_login():
    workflow = _publish_workflow()
    login = _step_index(workflow, "Log in to GHCR after all gates pass")

    for name in (
        "Scan backend image for secrets",
        "Scan frontend image for secrets",
        "Scan PostgreSQL image for secrets",
        "Scan backend image for fixable vulnerabilities",
        "Scan frontend image for fixable vulnerabilities",
        "Scan PostgreSQL image for fixable vulnerabilities",
        "Enforce sanitized scan results",
        "Inspect image contents and Docker history",
    ):
        assert _step_index(workflow, name) < login


def test_secret_findings_fail_before_any_push_without_raw_output():
    workflow = _publish_workflow()

    assert "secret_findings" in workflow
    assert "Secret scan failed" in workflow
    assert "results_file" in workflow
    assert "format: json" in workflow
    assert _step_index(workflow, "Enforce sanitized scan results") < _step_index(
        workflow, "Push immutable images"
    )


def test_fixable_high_and_critical_vulnerabilities_block_publish():
    workflow = _publish_workflow()

    assert "severity: HIGH,CRITICAL" in workflow
    assert "ignore-unfixed: true" in workflow
    assert "fixable_vulnerabilities" in workflow
    assert "Fixable HIGH/CRITICAL vulnerabilities found" in workflow


def test_publish_checks_remote_tags_before_any_push():
    workflow = _publish_workflow()

    assert "Refusing to overwrite existing immutable tag" in workflow
    assert "POSTGRES_SHOULD_PUSH" in workflow
    assert _step_index(workflow, "Check immutable tags before publishing") < _step_index(
        workflow, "Push immutable images"
    )


def test_publish_verifies_remote_digests_and_private_visibility():
    workflow = _publish_workflow()

    assert "Verify remote image digests" in workflow
    assert "Verify GHCR packages are private" in workflow
    assert 'test "$visibility" = "private"' in workflow
    assert "packages/container" in workflow


def test_publish_does_not_add_source_association_label():
    workflow = _publish_workflow()

    assert "--label org.opencontainers.image.source" not in workflow
    assert "LABEL org.opencontainers.image.source" not in workflow
    assert "Image source association label is forbidden" in workflow
    assert "https://github.com/MIkkon-ada/mowayspos" not in workflow


def test_publish_does_not_upload_sensitive_or_verbose_artifacts():
    workflow = _publish_workflow()

    for forbidden in (
        "actions/upload-artifact",
        "docker save",
        ".tar",
        "~/.docker/config.json",
        "sbom",
        "full scan report",
    ):
        assert forbidden.lower() not in workflow.lower()


def test_publish_has_no_production_or_cloud_credentials():
    workflow = _publish_workflow()

    for forbidden in (
        "DB_PASSWORD",
        "DATABASE_URL",
        "ANTHROPIC_API_KEY",
        "DASHSCOPE_API_KEY",
        "DEEPSEEK_API_KEY",
        "ZHIPUAI_API_KEY",
        "TENCENT",
        "SSH_KEY",
    ):
        assert forbidden not in workflow


def test_all_external_actions_are_pinned_to_full_commit_shas():
    workflow = _publish_workflow()
    uses = re.findall(r"^\s*uses:\s*([^\s]+)$", workflow, re.MULTILINE)

    assert uses
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", item) for item in uses)


def test_publish_checks_backend_frontend_and_postgres_contents():
    workflow = _publish_workflow()

    for expected in (
        "backend image content check failed",
        "frontend image content check failed",
        "postgres image content check failed",
        "private key",
        "Docker history check failed",
    ):
        assert expected in workflow


def test_publish_logs_out_and_removes_only_temporary_publish_images():
    workflow = _publish_workflow()

    assert "if: always()" in workflow
    assert "docker logout ghcr.io" in workflow
    assert "docker image rm" in workflow
    for forbidden in ("docker system prune", "docker image prune", "docker volume prune"):
        assert forbidden not in workflow


def test_p1b2a_gate_tracks_the_new_publish_contract_files():
    workflow = P1B2A_WORKFLOW.read_text(encoding="utf-8")

    for expected in (
        ".github/workflows/cloud-p1b2b-a-ghcr-private-publish.yml",
        "bowei_ai_dashboard/tests/test_ghcr_private_publish_contract.py",
        "docs/ghcr-private-image-publish.md",
    ):
        assert expected in workflow


def test_p1b2a_gate_keeps_existing_runtime_business_steps():
    workflow = P1B2A_WORKFLOW.read_text(encoding="utf-8")

    for step in (
        "Prepare isolated runtime",
        "P1B2A production runtime tests",
        "Backend full pytest with known structural baseline",
        "Build backend image without cache",
        "Build frontend image without cache",
        "PostgreSQL 16 migration gate",
        "Complete Compose smoke and port isolation",
        "LLM configuration survives backend recreation",
        "Cleanup isolated runtime",
    ):
        assert f"- name: {step}" in workflow
