from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PUBLISH_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/cloud-p1b2b-a-ghcr-private-publish.yml"
P1B2A_WORKFLOW = REPOSITORY_ROOT / ".github/workflows/cloud-p1b2a-gate.yml"
PUBLISH_DOCUMENTATION = REPOSITORY_ROOT / "docs/ghcr-private-image-publish.md"
BACKEND_REQUIREMENTS = REPOSITORY_ROOT / "bowei_ai_dashboard/requirements.txt"
BACKEND_DOCKERFILE = REPOSITORY_ROOT / "Dockerfile.backend"

POSTGRES_GO_CVES = (
    "CVE-2025-68121",
    "CVE-2025-61726",
    "CVE-2025-61729",
    "CVE-2026-25679",
    "CVE-2026-27145",
    "CVE-2026-32280",
    "CVE-2026-32281",
    "CVE-2026-32283",
    "CVE-2026-33811",
    "CVE-2026-33814",
    "CVE-2026-39820",
    "CVE-2026-39822",
    "CVE-2026-39836",
    "CVE-2026-42499",
    "CVE-2026-42504",
)


def _publish_workflow() -> str:
    return PUBLISH_WORKFLOW.read_text(encoding="utf-8")


def _trigger_block(workflow: str) -> str:
    return workflow.split("on:\n", 1)[1].split("\npermissions:", 1)[0]


def _step_index(workflow: str, step_name: str) -> int:
    marker = f"- name: {step_name}"
    assert marker in workflow
    return workflow.index(marker)


def _step_block(workflow: str, step_name: str) -> str:
    marker = f"      - name: {step_name}"
    assert marker in workflow
    remainder = workflow.split(marker, 1)[1]
    return remainder.split("\n      - name:", 1)[0]


def _embedded_gosu_report_parser() -> str:
    reachability = _step_block(
        _publish_workflow(),
        "Verify PostgreSQL gosu binary vulnerability reachability",
    )
    python_source = reachability.split(
        "python - \"$govulncheck_report\" <<'PY'\n", 1
    )[1].split("\n          PY", 1)[0]
    python_source = textwrap.dedent(python_source)
    start = python_source.index("report = Path(sys.argv[1])")
    end = python_source.index("\n\nobserved_cves =", start)
    return python_source[start:end]


def _run_embedded_gosu_report_parser(
    report_text: str,
    report_path: Path,
) -> tuple[dict[str, object], str, int]:
    report_path.write_text(report_text, encoding="utf-8")
    stderr = io.StringIO()
    namespace: dict[str, object] = {
        "aliases_by_osv": {},
        "findings": [],
        "json": __import__("json"),
        "Path": Path,
        "sys": SimpleNamespace(argv=["parser", str(report_path)], stderr=stderr),
    }
    try:
        exec(_embedded_gosu_report_parser(), namespace)
    except SystemExit as exc:
        return namespace, stderr.getvalue(), int(exc.code or 0)
    return namespace, stderr.getvalue(), 0


def _embedded_postgres_manifest_comparator() -> str:
    verifier = _step_block(
        _publish_workflow(),
        "Prepare PostgreSQL manifest content verifier",
    )
    python_source = verifier.split(
        'python - "$source_manifest" "$remote_manifest" <<\'PY\'\n', 1
    )[1].split("\n          PY", 1)[0]
    return textwrap.dedent(python_source)


def _postgres_manifest(
    *,
    media_type: str = "application/vnd.docker.distribution.manifest.v2+json",
) -> dict[str, object]:
    return {
        "schemaVersion": 2,
        "mediaType": media_type,
        "config": {
            "mediaType": "application/vnd.oci.image.config.v1+json",
            "digest": "sha256:" + "1" * 64,
            "size": 1234,
        },
        "layers": [
            {
                "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                "digest": "sha256:" + "2" * 64,
                "size": 2345,
            },
            {
                "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                "digest": "sha256:" + "3" * 64,
                "size": 3456,
            },
        ],
    }


def _run_embedded_postgres_manifest_comparator(
    tmp_path: Path,
    source: dict[str, object] | str,
    remote: dict[str, object] | str,
) -> subprocess.CompletedProcess[str]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source_path = tmp_path / "source-manifest.json"
    remote_path = tmp_path / "remote-manifest.json"
    source_path.write_text(
        source if isinstance(source, str) else json.dumps(source),
        encoding="utf-8",
    )
    remote_path.write_text(
        remote if isinstance(remote, str) else json.dumps(remote),
        encoding="utf-8",
    )
    return subprocess.run(
        [
            sys.executable,
            "-c",
            _embedded_postgres_manifest_comparator(),
            str(source_path),
            str(remote_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _embedded_scan_enforcement() -> str:
    enforcement = _step_block(
        _publish_workflow(),
        "Enforce sanitized scan results",
    )
    python_source = enforcement.split(
        'python - "$RUNNER_TEMP" <<\'PY\'\n', 1
    )[1].split("\n          PY", 1)[0]
    return textwrap.dedent(python_source)


def _postgres_reviewed_findings() -> list[dict[str, str]]:
    return [
        {
            "Severity": "CRITICAL" if cve == "CVE-2025-68121" else "HIGH",
            "VulnerabilityID": cve,
            "PkgName": "stdlib",
            "InstalledVersion": "v1.24.6",
            "FixedVersion": "reviewed-fixed-version",
        }
        for cve in POSTGRES_GO_CVES
    ]


def _run_embedded_scan_enforcement(
    root: Path,
    *,
    vulnerabilities: dict[str, list[dict[str, str]]] | None = None,
    secret_counts: dict[str, int] | None = None,
    missing_files: set[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    vulnerabilities = vulnerabilities or {}
    secret_counts = secret_counts or {}
    missing_files = missing_files or set()
    root.mkdir(parents=True, exist_ok=True)

    for image in ("backend", "frontend", "postgres"):
        secret_name = f"{image}-secret.json"
        vulnerability_name = f"{image}-vulnerability.json"
        if secret_name not in missing_files:
            secrets = [
                {"RuleID": f"test-secret-{index}"}
                for index in range(secret_counts.get(image, 0))
            ]
            (root / secret_name).write_text(
                json.dumps({"Results": [{"Secrets": secrets}]}),
                encoding="utf-8",
            )
        if vulnerability_name not in missing_files:
            (root / vulnerability_name).write_text(
                json.dumps(
                    {
                        "Results": [
                            {"Vulnerabilities": vulnerabilities.get(image, [])}
                        ]
                    }
                ),
                encoding="utf-8",
            )

    return subprocess.run(
        [sys.executable, "-c", _embedded_scan_enforcement(), str(root)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_publish_workflow_is_manual_only():
    triggers = _trigger_block(_publish_workflow())

    assert re.search(r"^\s+workflow_dispatch:\s*$", triggers, re.MULTILINE)
    for forbidden in (
        "push:",
        "pull_request:",
        "schedule:",
        "workflow_run:",
        "repository_dispatch:",
    ):
        assert forbidden not in triggers


def test_dispatch_requires_audit_or_publish_operation_defaulting_to_audit():
    triggers = _trigger_block(_publish_workflow())

    assert re.search(r"^\s+operation:\s*$", triggers, re.MULTILINE)
    assert re.search(r"^\s+required:\s+true\s*$", triggers, re.MULTILINE)
    assert re.search(r"^\s+type:\s+choice\s*$", triggers, re.MULTILINE)
    assert re.search(
        r"options:\s*\n\s+- audit\s*\n\s+- publish\s*$",
        triggers,
        re.MULTILINE,
    )
    assert re.search(r"^\s+default:\s+audit\s*$", triggers, re.MULTILINE)


def test_operation_mode_validation_is_fail_closed_after_sha_validation():
    workflow = _publish_workflow()
    validation = _step_block(workflow, "Validate operation mode")

    assert _step_index(workflow, "Validate main branch and full commit SHA") < _step_index(
        workflow, "Validate operation mode"
    )
    assert "${{ inputs.operation }}" in validation
    assert '"audit"|"publish"' in validation
    assert "Unsupported operation" in validation
    assert 'echo "operation=$OPERATION"' in validation


def test_audit_explicitly_skips_every_ghcr_publish_side_effect():
    workflow = _publish_workflow()
    publish_only_steps = (
        "Log in to GHCR after all gates pass",
        "Check immutable tags before publishing",
        "Retag validated images",
        "Push immutable images",
        "Verify remote image digests",
        "Verify GHCR packages are private",
    )

    for step_name in publish_only_steps:
        block = _step_block(workflow, step_name)
        assert "if: ${{ inputs.operation == 'publish' }}" in block


def test_publish_mode_keeps_the_complete_fail_closed_publish_sequence():
    workflow = _publish_workflow()
    steps = (
        "Inspect image contents and Docker history",
        "Enforce sanitized scan results",
        "Log in to GHCR after all gates pass",
        "Check immutable tags before publishing",
        "Retag validated images",
        "Push immutable images",
        "Verify remote image digests",
        "Verify GHCR packages are private",
        "Cleanup publish credentials and temporary images",
    )

    assert [_step_index(workflow, name) for name in steps] == sorted(
        _step_index(workflow, name) for name in steps
    )


def test_audit_success_is_reported_only_after_all_local_security_checks():
    workflow = _publish_workflow()
    audit = _step_block(workflow, "Report audit-only success")

    assert "if: ${{ inputs.operation == 'audit' }}" in audit
    assert "audit_only=ok" in audit
    assert "publish_attempted=false" in audit
    assert _step_index(workflow, "Inspect image contents and Docker history") < _step_index(
        workflow, "Enforce sanitized scan results"
    )
    assert _step_index(workflow, "Enforce sanitized scan results") < _step_index(
        workflow, "Report audit-only success"
    )
    assert _step_index(workflow, "Report audit-only success") < _step_index(
        workflow, "Log in to GHCR after all gates pass"
    )


def test_vulnerability_diagnostics_emit_only_six_sanitized_fields():
    workflow = _publish_workflow()
    enforcement = _step_block(workflow, "Enforce sanitized scan results")

    assert re.search(
        r'print\(\s*"vulnerability "\s*'
        r'f"image=\{image\} "\s*'
        r'f"severity=\{severity\} "\s*'
        r'f"id=\{vulnerability_id\} "\s*'
        r'f"package=\{package_name\} "\s*'
        r'f"installed=\{installed_version\} "\s*'
        r'f"fixed=\{fixed_version\}"\s*\)',
        enforcement,
    )
    for key in (
        'item.get("Severity")',
        'item.get("VulnerabilityID")',
        'item.get("PkgName")',
        'item.get("InstalledVersion")',
        'item.get("FixedVersion")',
    ):
        assert key in enforcement


def test_vulnerability_diagnostics_exclude_verbose_and_sensitive_fields():
    enforcement = _step_block(
        _publish_workflow(), "Enforce sanitized scan results"
    )

    for forbidden in (
        'item.get("Title")',
        'item.get("Description")',
        'item.get("PrimaryURL")',
        'item.get("References")',
        'item.get("PkgPath")',
        'item.get("Layer")',
        "json.dumps(secret_data",
        "print(secret_data",
        "print(vulnerability_data",
    ):
        assert forbidden not in enforcement


def test_vulnerability_diagnostics_are_sorted_and_deduplicated():
    enforcement = _step_block(
        _publish_workflow(), "Enforce sanitized scan results"
    )

    assert "records = set()" in enforcement
    assert "records.add(" in enforcement
    assert "for record in sorted(records):" in enforcement
    assert "fixable_vulnerabilities = len(records)" in enforcement


def test_diagnostic_mode_does_not_allowlist_or_weaken_vulnerability_gate():
    workflow = _publish_workflow()
    enforcement = _step_block(workflow, "Enforce sanitized scan results")

    assert "severity: HIGH,CRITICAL" in workflow
    assert 'item.get("Severity") in {"HIGH", "CRITICAL"}' in enforcement
    assert "if fixable_vulnerabilities:" in enforcement
    assert "failed = True" in enforcement
    assert "raise SystemExit(1)" in enforcement
    for forbidden in ("allowlist", "whitelist", "ignore-cve", "CRITICAL-only"):
        assert forbidden.lower() not in workflow.lower()


def test_secret_diagnostics_remain_counts_only():
    enforcement = _step_block(
        _publish_workflow(), "Enforce sanitized scan results"
    )

    assert 'print(f"{image}_secret_findings={secret_findings}")' in enforcement
    assert "Secret scan failed" in enforcement
    assert "for secret in" not in enforcement
    assert "SecretID" not in enforcement
    assert "Match" not in enforcement


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


def test_postgres_remote_checks_compare_content_not_registry_manifest_digest():
    workflow = _publish_workflow()
    immutable_check = _step_block(workflow, "Check immutable tags before publishing")
    remote_check = _step_block(workflow, "Verify remote image digests")

    assert '"$remote_digest" != "$POSTGRES_AMD64_DIGEST"' not in immutable_check
    assert '"$postgres_remote" != "$POSTGRES_AMD64_DIGEST"' not in remote_check
    assert "POSTGRES_MANIFEST_VERIFIER" in immutable_check
    assert "POSTGRES_MANIFEST_VERIFIER" in remote_check
    assert "postgres_upstream_index_digest=" in workflow
    assert "postgres_linux_amd64_digest=" in workflow
    assert "postgres_source_manifest_digest=" in workflow
    assert "postgres_remote_manifest_digest=" in workflow


def test_postgres_manifest_comparator_accepts_equal_content_with_different_media_type(
    tmp_path: Path,
):
    source = _postgres_manifest()
    remote = _postgres_manifest(
        media_type="application/vnd.oci.image.manifest.v1+json"
    )
    remote["annotations"] = {"org.example.registry": "rewrapped"}

    result = _run_embedded_postgres_manifest_comparator(tmp_path, source, remote)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "postgres_config_digest=sha256:" + "1" * 64 in result.stdout
    assert "postgres_layer_count=2" in result.stdout
    assert "postgres_content_equivalence=verified" in result.stdout


def test_postgres_manifest_comparator_rejects_config_digest_or_size_changes(
    tmp_path: Path,
):
    for field, value in (("digest", "sha256:" + "9" * 64), ("size", 9999)):
        source = _postgres_manifest()
        remote = json.loads(json.dumps(source))
        remote["config"][field] = value

        result = _run_embedded_postgres_manifest_comparator(
            tmp_path / field,
            source,
            remote,
        )

        assert result.returncode == 1, field
        assert result.stdout == ""
        assert result.stderr == "postgres_content_equivalence=config_mismatch\n"


def test_postgres_manifest_comparator_rejects_every_layer_shape_change(
    tmp_path: Path,
):
    source = _postgres_manifest()
    cases: dict[str, dict[str, object]] = {}
    for name in ("digest", "size"):
        changed = json.loads(json.dumps(source))
        changed["layers"][0][name] = (
            "sha256:" + "8" * 64 if name == "digest" else 8888
        )
        cases[f"layer-{name}"] = changed
    reordered = json.loads(json.dumps(source))
    reordered["layers"].reverse()
    cases["layer-order"] = reordered
    missing = json.loads(json.dumps(source))
    missing["layers"].pop()
    cases["layer-missing"] = missing
    added = json.loads(json.dumps(source))
    added["layers"].append(
        {"digest": "sha256:" + "4" * 64, "size": 4567}
    )
    cases["layer-added"] = added

    for name, remote in cases.items():
        result = _run_embedded_postgres_manifest_comparator(
            tmp_path / name,
            source,
            remote,
        )
        assert result.returncode == 1, name
        assert result.stdout == ""
        assert result.stderr == "postgres_content_equivalence=layer_mismatch\n"


def test_postgres_manifest_comparator_rejects_index_and_invalid_json(
    tmp_path: Path,
):
    source = _postgres_manifest()
    index = {
        "schemaVersion": 2,
        "manifests": [
            {
                "digest": "sha256:" + "5" * 64,
                "size": 5678,
                "platform": {"os": "linux", "architecture": "amd64"},
            }
        ],
    }
    for name, remote in (("index", index), ("invalid-json", "{not-json")):
        result = _run_embedded_postgres_manifest_comparator(
            tmp_path / name,
            source,
            remote,
        )
        assert result.returncode == 1, name
        assert result.stdout == ""
        assert result.stderr == "postgres_content_equivalence=invalid_manifest\n"


def test_existing_postgres_tag_is_reused_only_after_content_equivalence():
    workflow = _publish_workflow()
    immutable_check = _step_block(workflow, "Check immutable tags before publishing")

    assert 'echo "POSTGRES_SHOULD_PUSH=false"' in immutable_check
    assert 'echo "postgres_immutable_tag=existing_equivalent"' in immutable_check
    assert 'echo "POSTGRES_SHOULD_PUSH=true"' in immutable_check
    assert "POSTGRES_MANIFEST_VERIFIER" in immutable_check
    assert immutable_check.index("POSTGRES_MANIFEST_VERIFIER") < immutable_check.index(
        'echo "POSTGRES_SHOULD_PUSH=false"'
    )
    assert "docker push" not in immutable_check


def test_postgres_manifest_verifier_keeps_raw_manifests_out_of_logs():
    workflow = _publish_workflow()
    verifier = _step_block(
        workflow,
        "Prepare PostgreSQL manifest content verifier",
    )

    assert '--raw "$source_ref" > "$source_manifest"' in verifier
    assert '--raw "$remote_ref" > "$remote_manifest"' in verifier
    assert '^sha256:[0-9a-f]{64}$' in verifier
    for forbidden in (
        'cat "$source_manifest"',
        'cat "$remote_manifest"',
        "print(document)",
        "print(source)",
        "print(remote)",
    ):
        assert forbidden not in verifier


def test_package_verification_uses_authenticated_user_metadata_and_versions():
    workflow = _publish_workflow()
    package_check = _step_block(workflow, "Verify GHCR packages are private")

    assert 'GH_TOKEN: ${{ secrets.GHCR_PUBLISH_TOKEN }}' in package_check
    assert '"/user/packages/container/$package"' in package_check
    assert '"/user/packages/container/$package/versions?per_page=100"' in package_check
    assert "application/vnd.github+json" in package_check
    assert "X-GitHub-Api-Version: 2022-11-28" in package_check
    for field in (".name", ".package_type", ".owner.login", ".visibility"):
        assert field in package_check
    for forbidden_tag in ("latest", "main", "production"):
        assert forbidden_tag in package_check
    assert "GITHUB_SHA" in package_check
    assert "POSTGRES_TAG" in package_check
    assert "/users/mikkon-ada/packages/container/" not in package_check
    assert "DELETE" not in package_check


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


def test_documentation_explains_audit_default_and_first_failure_boundary():
    documentation = PUBLISH_DOCUMENTATION.read_text(encoding="utf-8")

    for expected in (
        "`audit` is the default",
        "never logs in to GHCR",
        "`publish` must be selected explicitly",
        "29679562418",
        "one backend and 15 PostgreSQL",
        "no GHCR package was created",
        "vulnerability ID, package name, installed version, fixed version, and severity",
        "does not print vulnerability descriptions, references, or secret contents",
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
    assert '.visibility == "private"' in workflow
    assert '"/user/packages/container/$package"' in workflow


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


def test_backend_pins_the_only_python_multipart_definition_to_fixed_version():
    requirements = BACKEND_REQUIREMENTS.read_text(encoding="utf-8")
    multipart_lines = [
        line.strip()
        for line in requirements.splitlines()
        if line.strip().lower().startswith("python-multipart")
    ]

    assert multipart_lines == ["python-multipart==0.0.30"]
    assert "python-multipart==0.0.29" not in requirements


def test_backend_image_installs_the_locked_requirements_without_multipart_override():
    dockerfile = BACKEND_DOCKERFILE.read_text(encoding="utf-8")

    assert "COPY bowei_ai_dashboard/requirements.txt ." in dockerfile
    assert "pip install --no-cache-dir -r requirements.txt" in dockerfile
    assert "python-multipart" not in dockerfile.lower()


def test_publish_workflow_uses_pinned_setup_go_and_exact_govulncheck_versions():
    workflow = _publish_workflow()

    assert "actions/setup-go@924ae3a1cded613372ab5595356fb5720e22ba16" in workflow
    assert "go-version: '1.26.5'" in workflow
    assert re.search(r"^\s+cache:\s+false\s*$", workflow, re.MULTILINE)
    assert "golang.org/x/vuln/cmd/govulncheck@v1.6.0" in workflow


def test_postgres_gosu_is_extracted_from_the_pulled_image_and_verified_exactly():
    workflow = _publish_workflow()
    identity = _step_block(workflow, "Verify PostgreSQL gosu binary identity")

    assert 'docker create --platform linux/amd64 "$POSTGRES_LOCAL"' in identity
    assert 'docker cp "$gosu_container:/usr/local/bin/gosu" "$gosu_binary"' in identity
    assert 'test -f "$gosu_binary"' in identity
    assert 'test -x "$gosu_binary"' in identity
    assert "52c8749d0142edd234e9d6bd5237dff2d81e71f43537e2f4f66f75dd4b243dd0" in identity
    assert '[[ "$gosu_version" == "1.19" ]]' in identity
    assert '[[ "$gosu_go_version" == "go1.24.6" ]]' in identity
    assert '[[ "$gosu_platform" == "linux/amd64" ]]' in identity
    for safe_line in (
        "gosu_version=",
        "gosu_go_version=",
        "gosu_platform=",
        "gosu_sha256=",
        "gosu_identity=verified",
    ):
        assert safe_line in identity
    for forbidden in ("curl ", "wget ", "go install", "docker pull"):
        assert forbidden not in identity


def test_gosu_reachability_scans_the_extracted_binary_and_requires_full_db_coverage():
    workflow = _publish_workflow()
    reachability = _step_block(
        workflow, "Verify PostgreSQL gosu binary vulnerability reachability"
    )

    assert 'govulncheck" -mode binary -json "$gosu_binary"' in reachability
    assert '"$RUNNER_TEMP/postgres-gosu"' in reachability
    assert '"$RUNNER_TEMP/postgres-gosu-govulncheck.json"' in reachability
    assert "gosu_vulndb_coverage=15/15" in reachability
    for cve in POSTGRES_GO_CVES:
        assert cve in reachability


def test_gosu_reachability_uses_first_trace_symbol_deduplicates_and_fails_closed():
    reachability = _step_block(
        _publish_workflow(),
        "Verify PostgreSQL gosu binary vulnerability reachability",
    )

    assert 'trace = finding.get("trace") or []' in reachability
    assert 'symbol = str((trace[0] or {}).get("function") or "").strip()' in reachability
    assert "records = set()" in reachability
    assert "records.add(" in reachability
    assert "for record in sorted(records):" in reachability
    assert "gosu_reachable_vulnerability_count=" in reachability
    assert "gosu_reachable_vulnerability id=" in reachability
    assert "gosu_binary_reachability=clear" in reachability
    assert "raise SystemExit(1)" in reachability


def test_gosu_diagnostics_never_emit_raw_reports_or_weaken_trivy_enforcement():
    workflow = _publish_workflow()
    reachability = _step_block(
        workflow, "Verify PostgreSQL gosu binary vulnerability reachability"
    )

    for forbidden in (
        "print(message",
        "print(data",
        "print(osv",
        "Description",
        "References",
        "actions/upload-artifact",
        "allowlist",
        "vex",
    ):
        assert forbidden.lower() not in reachability.lower()
    assert 'for image in ("backend", "frontend", "postgres"):' in workflow
    assert "if fixable_vulnerabilities:" in workflow
    assert "Fixable HIGH/CRITICAL vulnerabilities found" in workflow


def test_gosu_evidence_runs_before_existing_image_security_gates_and_login():
    workflow = _publish_workflow()
    identity = _step_index(workflow, "Verify PostgreSQL gosu binary identity")
    reachability = _step_index(
        workflow, "Verify PostgreSQL gosu binary vulnerability reachability"
    )
    secret_scan = _step_index(workflow, "Scan backend image for secrets")
    trivy_scan = _step_index(
        workflow, "Scan backend image for fixable vulnerabilities"
    )
    login = _step_index(workflow, "Log in to GHCR after all gates pass")

    assert _step_index(workflow, "Pull immutable PostgreSQL linux/amd64 image") < identity
    assert identity < reachability < secret_scan < trivy_scan < login


def test_gosu_temporary_binary_and_json_are_removed_by_always_cleanup():
    cleanup = _step_block(
        _publish_workflow(), "Cleanup publish credentials and temporary images"
    )

    assert "if: always()" in cleanup
    assert '"$RUNNER_TEMP/postgres-gosu"' in cleanup
    assert '"$RUNNER_TEMP/postgres-gosu-govulncheck.json"' in cleanup


def test_documentation_records_multipart_patch_and_gosu_evidence_boundaries():
    documentation = PUBLISH_DOCUMENTATION.read_text(encoding="utf-8")

    for expected in (
        "python-multipart 0.0.29",
        "python-multipart 0.0.30",
        "CVE-2026-53539",
        "gosu 1.19",
        "go1.24.6",
        "linux/amd64",
        "15/15",
        "govulncheck v1.6.0",
        "binary",
        "Trivy",
        "does not authorize publishing",
        "no VEX",
        "no allowlist",
    ):
        assert expected in documentation


def test_govulncheck_stream_parser_uses_raw_decode_and_remains_fail_closed():
    reachability = _step_block(
        _publish_workflow(),
        "Verify PostgreSQL gosu binary vulnerability reachability",
    )

    assert "json.loads(line)" not in reachability
    assert "text = report.read_text(encoding=\"utf-8\")" in reachability
    assert "decoder = json.JSONDecoder()" in reachability
    assert "decoder.raw_decode(text, position)" in reachability
    assert "message, position = decoder.raw_decode(text, position)" in reachability
    assert "while position < len(text) and text[position].isspace():" in reachability
    assert "position += 1" in reachability
    assert "if not isinstance(message, dict):" in reachability
    assert "message_count += 1" in reachability
    assert "if message_count == 0:" in reachability
    assert "json.JSONDecodeError" in reachability
    assert 'print("gosu_govulncheck_report=invalid", file=sys.stderr)' in reachability
    for forbidden in ("print(text", "print(report", "print(message"):
        assert forbidden not in reachability


def test_govulncheck_stream_parser_accepts_three_multiline_messages(tmp_path: Path):
    sample = """{
  \"config\": {
    \"protocol_version\": \"v1.0.0\"
  }
}
{
  \"osv\": {
    \"id\": \"GO-TEST-0001\",
    \"aliases\": [
      \"CVE-TEST-0001\"
    ]
  }
}
{
  \"finding\": {
    \"osv\": \"GO-TEST-0001\",
    \"trace\": [
      {
        \"function\": \"example.Symbol\"
      }
    ]
  }
}

"""
    namespace, stderr, exit_code = _run_embedded_gosu_report_parser(
        sample,
        tmp_path / "valid-stream.json",
    )

    assert exit_code == 0
    assert stderr == ""
    assert namespace["message_count"] == 3
    assert namespace["aliases_by_osv"] == {
        "GO-TEST-0001": {"CVE-TEST-0001"}
    }
    assert namespace["findings"] == [
        {
            "osv": "GO-TEST-0001",
            "trace": [{"function": "example.Symbol"}],
        }
    ]


def test_govulncheck_stream_parser_rejects_empty_non_object_and_trailing_garbage(
    tmp_path: Path,
):
    samples = {
        "empty": " \n\t",
        "non-object": "[]",
        "trailing-garbage": '{\"config\": {}}\nnot-json',
    }

    for name, sample in samples.items():
        _, stderr, exit_code = _run_embedded_gosu_report_parser(
            sample,
            tmp_path / f"{name}.json",
        )
        assert exit_code == 1
        assert stderr == "gosu_govulncheck_report=invalid\n"


def test_gosu_security_evidence_is_a_strict_prerequisite_for_enforcement():
    workflow = _publish_workflow()
    identity_name = "Verify PostgreSQL gosu binary identity"
    reachability_name = "Verify PostgreSQL gosu binary vulnerability reachability"
    content_name = "Inspect image contents and Docker history"
    enforcement_name = "Enforce sanitized scan results"

    assert _step_index(workflow, identity_name) < _step_index(
        workflow, reachability_name
    ) < _step_index(workflow, content_name) < _step_index(workflow, enforcement_name)
    for step_name in (identity_name, reachability_name, content_name):
        step = _step_block(workflow, step_name)
        assert "continue-on-error" not in step
        assert "\n        if:" not in step
    enforcement = _step_block(workflow, enforcement_name)
    assert "continue-on-error" not in enforcement
    assert "\n        if:" not in enforcement


def test_reviewed_gosu_exception_executes_only_for_exact_15_findings(
    tmp_path: Path,
):
    result = _run_embedded_scan_enforcement(
        tmp_path / "exact",
        vulnerabilities={"postgres": _postgres_reviewed_findings()},
    )

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert result.stdout.count("vulnerability image=postgres ") == 15
    assert "postgres_secret_findings=0" in result.stdout
    assert "postgres_fixable_high_critical=15" in result.stdout
    assert "postgres_reviewed_gosu_findings=15" in result.stdout
    assert "postgres_unreviewed_fixable_high_critical=0" in result.stdout
    assert "postgres_gosu_reviewed_exception=true" in result.stdout
    for cve in POSTGRES_GO_CVES:
        assert f"id={cve} " in result.stdout


def test_reviewed_gosu_exception_fails_for_missing_extra_or_changed_findings(
    tmp_path: Path,
):
    exact = _postgres_reviewed_findings()
    cases = {
        "missing": exact[:-1],
        "extra": exact
        + [
            {
                "Severity": "HIGH",
                "VulnerabilityID": "CVE-2099-00001",
                "PkgName": "stdlib",
                "InstalledVersion": "v1.24.6",
                "FixedVersion": "future-fix",
            }
        ],
        "package-changed": [
            {**exact[0], "PkgName": "not-stdlib"},
            *exact[1:],
        ],
        "version-changed": [
            {**exact[0], "InstalledVersion": "v1.24.7"},
            *exact[1:],
        ],
    }

    for name, findings in cases.items():
        result = _run_embedded_scan_enforcement(
            tmp_path / name,
            vulnerabilities={"postgres": findings},
        )
        assert result.returncode == 1, name
        assert "postgres_gosu_reviewed_exception=false" in result.stdout


def test_backend_frontend_and_secret_findings_keep_zero_tolerance(tmp_path: Path):
    high = {
        "Severity": "HIGH",
        "VulnerabilityID": "CVE-2099-10001",
        "PkgName": "test-package",
        "InstalledVersion": "1.0",
        "FixedVersion": "1.1",
    }
    critical = {**high, "Severity": "CRITICAL", "VulnerabilityID": "CVE-2099-10002"}
    cases = {
        "backend-high": {
            "vulnerabilities": {
                "backend": [high],
                "postgres": _postgres_reviewed_findings(),
            },
            "secret_counts": {},
        },
        "frontend-critical": {
            "vulnerabilities": {
                "frontend": [critical],
                "postgres": _postgres_reviewed_findings(),
            },
            "secret_counts": {},
        },
        "postgres-secret": {
            "vulnerabilities": {"postgres": _postgres_reviewed_findings()},
            "secret_counts": {"postgres": 1},
        },
    }

    for name, inputs in cases.items():
        result = _run_embedded_scan_enforcement(
            tmp_path / name,
            vulnerabilities=inputs["vulnerabilities"],
            secret_counts=inputs["secret_counts"],
        )
        assert result.returncode == 1, name


def test_scan_enforcement_fails_closed_when_any_json_file_is_missing(
    tmp_path: Path,
):
    for image in ("backend", "frontend", "postgres"):
        for scan_type in ("secret", "vulnerability"):
            missing = f"{image}-{scan_type}.json"
            result = _run_embedded_scan_enforcement(
                tmp_path / missing,
                vulnerabilities={"postgres": _postgres_reviewed_findings()},
                missing_files={missing},
            )
            assert result.returncode == 1, missing
            assert f"{image}_scan_result=missing" in result.stderr
            if image == "postgres":
                assert "postgres_gosu_reviewed_exception=false" in result.stdout


def test_reviewed_gosu_exception_is_exact_and_not_a_generic_bypass():
    workflow = _publish_workflow()
    enforcement = _step_block(workflow, "Enforce sanitized scan results")

    for cve in POSTGRES_GO_CVES:
        assert cve in enforcement
    for required in (
        'package_name == "stdlib"',
        'installed_version == "v1.24.6"',
        "postgres_reviewed_gosu_findings=",
        "postgres_unreviewed_fixable_high_critical=",
        "postgres_gosu_reviewed_exception=true",
        "postgres_gosu_reviewed_exception=false",
    ):
        assert required in enforcement
    for forbidden in ("ignorefile", "ignore-file", "vex", "continue-on-error"):
        assert forbidden.lower() not in workflow.lower()
    for forbidden in ('startswith("CVE-")', "fnmatch"):
        assert forbidden.lower() not in enforcement.lower()


def test_documentation_records_the_exact_reviewed_gosu_exception_boundary():
    documentation = PUBLISH_DOCUMENTATION.read_text(encoding="utf-8")

    for required in (
        "29683559066",
        "gosu 1.19",
        "go1.24.6",
        "linux/amd64",
        "52c8749d0142edd234e9d6bd5237dff2d81e71f43537e2f4f66f75dd4b243dd0",
        "15/15",
        "exactly the 15 reviewed CVE records",
        "package `stdlib`",
        "installed version is exactly `v1.24.6`",
        "requires a new human security review",
    ):
        assert required in documentation
