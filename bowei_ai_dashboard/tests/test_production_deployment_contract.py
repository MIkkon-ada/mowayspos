from __future__ import annotations

import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPOSITORY_ROOT / "docker-compose.prod.yml"
DEPLOYMENT_DOC_PATH = REPOSITORY_ROOT / "docs/tencent-cvm-first-deploy.md"
P1B2A_WORKFLOW_PATH = REPOSITORY_ROOT / ".github/workflows/cloud-p1b2a-gate.yml"

RELEASE_SHA = "4182c9746e498aebbbd9371fe7488d7dd71ae02f"
POSTGRES_SOURCE_DIGEST = "7a396fd264a2067788b6551122b50f162bf6136312c7fc9d74381cb92c648382"
BACKEND_REMOTE_DIGEST = "7fa06bd6579c98b21cfbf949f773daede9df508edd177823ed70c77630e65aa5"
FRONTEND_REMOTE_DIGEST = "49b46fd61da49e047ee3427cd762ce101eb752241018b7ddf36cce446e87a76a"
POSTGRES_REMOTE_DIGEST = "428f48e250303765f62fdfcf2df623cb4f5bb27fafda6b26e9cb17e53bf8019b"
BACKEND_REPOSITORY = "ghcr.io/mikkon-ada/mowayspos-backend"
FRONTEND_REPOSITORY = "ghcr.io/mikkon-ada/mowayspos-frontend"
POSTGRES_IMAGE = (
    "ghcr.io/mikkon-ada/mowayspos-postgres:"
    f"linux-amd64-sha256-{POSTGRES_SOURCE_DIGEST}"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _service_block(compose: str, service: str, next_service: str | None) -> str:
    end = rf"^  {next_service}:" if next_service else r"^networks:"
    match = re.search(
        rf"^  {service}:\n(?P<body>.*?)(?={end})",
        compose,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match, f"missing Compose service: {service}"
    return match.group("body")


def _bash_blocks(markdown: str) -> str:
    return "\n".join(re.findall(r"```bash\n(.*?)```", markdown, flags=re.DOTALL))


def _squash_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\\", " ")).strip()


def test_compose_parameterizes_backend_repository_and_requires_tag():
    compose = _read(COMPOSE_PATH)
    assert (
        "image: ${MOWAYS_BACKEND_REPOSITORY:-mowayspos-backend}:"
        "${MOWAYS_IMAGE_TAG:?MOWAYS_IMAGE_TAG is required}"
    ) in compose


def test_compose_parameterizes_frontend_repository_and_requires_tag():
    compose = _read(COMPOSE_PATH)
    assert (
        "image: ${MOWAYS_FRONTEND_REPOSITORY:-mowayspos-frontend}:"
        "${MOWAYS_IMAGE_TAG:?MOWAYS_IMAGE_TAG is required}"
    ) in compose


def test_compose_parameterizes_postgres_image_with_existing_default():
    compose = _read(COMPOSE_PATH)
    assert "image: ${MOWAYS_POSTGRES_IMAGE:-postgres:16-alpine}" in compose


def test_compose_keeps_local_and_ci_image_defaults():
    compose = _read(COMPOSE_PATH)
    assert "${MOWAYS_BACKEND_REPOSITORY:-mowayspos-backend}" in compose
    assert "${MOWAYS_FRONTEND_REPOSITORY:-mowayspos-frontend}" in compose
    assert "${MOWAYS_POSTGRES_IMAGE:-postgres:16-alpine}" in compose
    assert "ghcr.io/mikkon-ada" not in compose


def test_compose_keeps_backend_and_frontend_build_definitions():
    compose = _read(COMPOSE_PATH)
    backend = _service_block(compose, "backend", "frontend")
    frontend = _service_block(compose, "frontend", None)
    assert "build:" in backend and "dockerfile: Dockerfile.backend" in backend
    assert "build:" in frontend and "dockerfile: Dockerfile.frontend" in frontend


def test_compose_exposes_only_frontend_on_loopback():
    compose = _read(COMPOSE_PATH)
    assert compose.count("ports:") == 1
    assert '"127.0.0.1:18100:80"' in compose
    for forbidden in ('"0.0.0.0:', '"80:80"', '"443:443"'):
        assert forbidden not in compose


def test_backend_has_no_host_port_and_exposes_8008_internally():
    compose = _read(COMPOSE_PATH)
    backend = _service_block(compose, "backend", "frontend")
    assert "ports:" not in backend
    assert 'expose:\n      - "8008"' in backend
    assert "8008:8008" not in compose


def test_postgres_has_no_host_port_and_exposes_5432_internally():
    compose = _read(COMPOSE_PATH)
    postgres = _service_block(compose, "postgres", "backend")
    assert "ports:" not in postgres
    assert 'expose:\n      - "5432"' in postgres
    assert "5432:5432" not in compose


def test_compose_keeps_the_isolated_application_network():
    compose = _read(COMPOSE_PATH)
    assert compose.count("- mowayspos_app") == 3
    assert "mowayspos_app:\n    name: mowayspos_app\n    driver: bridge" in compose


def test_deployment_doc_pins_the_validated_release_and_images():
    doc = _read(DEPLOYMENT_DOC_PATH)
    for expected in (
        f"RELEASE_SHA={RELEASE_SHA}",
        f"MOWAYS_BACKEND_REPOSITORY={BACKEND_REPOSITORY}",
        f"MOWAYS_FRONTEND_REPOSITORY={FRONTEND_REPOSITORY}",
        f"MOWAYS_POSTGRES_IMAGE={POSTGRES_IMAGE}",
        f"MOWAYS_IMAGE_TAG={RELEASE_SHA}",
    ):
        assert expected in doc


def test_deployment_doc_lists_all_required_runtime_variables():
    doc = _read(DEPLOYMENT_DOC_PATH)
    for name in (
        "POSTGRES_DB",
        "POSTGRES_USER",
        "DB_PASSWORD",
        "MOWAYS_ENV_FILE",
        "MOWAYS_DATA_ROOT",
        "SESSION_COOKIE_NAME",
    ):
        assert re.search(rf"^{name}=", doc, flags=re.MULTILINE)


def test_deployment_doc_uses_stdin_only_for_the_ghcr_token():
    doc = _read(DEPLOYMENT_DOC_PATH)
    assert "read -s GHCR_READ_TOKEN" in doc
    assert (
        'printf \'%s\' "$GHCR_READ_TOKEN" | '
        "docker login ghcr.io -u MIkkon-ada --password-stdin"
    ) in doc
    assert "unset GHCR_READ_TOKEN" in doc
    assert "GHCR_READ_TOKEN=" not in doc


def test_deployment_doc_uses_explicit_env_file_for_every_compose_command():
    doc = _read(DEPLOYMENT_DOC_PATH)
    commands = [line.strip() for line in doc.splitlines() if line.strip().startswith("docker compose")]
    assert commands
    direct_commands = [command for command in commands if command != "docker compose"]
    assert all(
        "--env-file /opt/mowayspos/production.env -f docker-compose.prod.yml" in command
        for command in direct_commands
    )
    assert "dc=(" in doc
    assert "docker compose\n  --env-file /opt/mowayspos/production.env\n  -f docker-compose.prod.yml" in doc


def test_deployment_doc_pulls_before_starting_without_building():
    doc = _read(DEPLOYMENT_DOC_PATH)
    pull = "docker compose --env-file /opt/mowayspos/production.env -f docker-compose.prod.yml pull"
    up = '"${dc[@]}" up -d --no-build backend frontend'
    assert pull in doc and up in doc
    assert doc.index(pull) < doc.index(up)
    assert "up -d --build" not in doc
    assert "docker compose build" not in doc


def test_deployment_doc_does_not_use_mutable_image_tags():
    doc = _read(DEPLOYMENT_DOC_PATH)
    for forbidden in (":latest", ":main", ":production", "MOWAYS_IMAGE_TAG=main"):
        assert forbidden not in doc


def test_deployment_doc_verifies_all_three_pulled_images():
    doc = _read(DEPLOYMENT_DOC_PATH)
    assert "docker image inspect" in doc
    assert doc.count("require_repo_digest \\") == 3
    assert BACKEND_REPOSITORY in doc
    assert FRONTEND_REPOSITORY in doc
    assert POSTGRES_IMAGE in doc
    assert f"sha256:{POSTGRES_SOURCE_DIGEST}" in doc


def test_deployment_doc_checks_exact_backend_remote_digest():
    doc = _read(DEPLOYMENT_DOC_PATH)
    assert f"sha256:{BACKEND_REMOTE_DIGEST}" in doc


def test_deployment_doc_checks_exact_frontend_remote_digest():
    doc = _read(DEPLOYMENT_DOC_PATH)
    assert f"sha256:{FRONTEND_REMOTE_DIGEST}" in doc


def test_deployment_doc_checks_postgres_ghcr_remote_digest():
    doc = _read(DEPLOYMENT_DOC_PATH)
    assert f"sha256:{POSTGRES_REMOTE_DIGEST}" in doc


def test_postgres_source_digest_is_not_treated_as_the_ghcr_repo_digest():
    doc = _read(DEPLOYMENT_DOC_PATH)
    assert f"grep -F '@sha256:{POSTGRES_SOURCE_DIGEST}'" not in doc
    assert f"expected_digest=sha256:{POSTGRES_SOURCE_DIGEST}" not in doc
    assert "source manifest" in doc
    assert "GHCR remote manifest" in doc


def test_all_three_images_use_the_exact_repo_digest_comparison():
    doc = _read(DEPLOYMENT_DOC_PATH)
    assert "require_repo_digest()" in doc
    assert "$2 == expected { found = 1 }" in doc
    assert "END { exit(found ? 0 : 1) }" in doc
    assert doc.count("require_repo_digest \\") == 3
    assert 'test -n "$(docker image inspect' not in doc


def test_deployment_directory_is_owned_by_the_current_docker_user():
    doc = _read(DEPLOYMENT_DOC_PATH)
    assert '-o "$(id -un)"' in doc
    assert '-g "$(id -gn)"' in doc
    assert "/opt/mowayspos" in doc
    assert "0777" not in doc


def test_deployment_doc_prepares_postgres_and_environment_directories():
    doc = _read(DEPLOYMENT_DOC_PATH)
    assert "/data/mowayspos/postgres" in doc
    assert "/data/mowayspos/env" in doc
    assert doc.index("/data/mowayspos/postgres") < doc.index("docker compose")


def test_deployment_doc_initializes_llm_config_as_a_private_regular_file():
    doc = _read(DEPLOYMENT_DOC_PATH)
    assert "install -m 0600 /dev/null \\\n  /data/mowayspos/env/llm_configs.json" in doc
    assert "printf '{}\\n' > \\\n  /data/mowayspos/env/llm_configs.json" in doc
    assert "test -f /data/mowayspos/env/llm_configs.json" in doc
    assert "test ! -d /data/mowayspos/env/llm_configs.json" in doc


def test_deployment_doc_creates_production_env_with_private_permissions():
    doc = _read(DEPLOYMENT_DOC_PATH)
    assert "install -m 0600 /dev/null \\\n  /opt/mowayspos/production.env" in doc


def test_production_env_template_does_not_duplicate_database_url():
    doc = _read(DEPLOYMENT_DOC_PATH)
    assert not re.search(r"^DATABASE_URL=", doc, flags=re.MULTILINE)
    assert re.search(
        r"Compose inserts DB_PASSWORD into the\s+backend DATABASE_URL",
        doc,
    )


def test_deployment_doc_limits_runtime_to_loopback_and_health_checks():
    doc = _read(DEPLOYMENT_DOC_PATH)
    assert "http://127.0.0.1:18100/" in doc
    assert "http://127.0.0.1:18100/api/health" in doc
    assert "status=ok" in doc
    assert "database=ok" in doc
    assert "env=production" in doc


def test_deployment_doc_stops_before_host_infrastructure_changes():
    doc = _read(DEPLOYMENT_DOC_PATH)
    for expected in (
        "Do not modify host Nginx",
        "Do not modify DNS",
        "Do not run Certbot",
        "KAP",
        "WeKnora",
        "OnlyOffice",
    ):
        assert expected in doc


def test_deployment_doc_forbids_unsafe_or_out_of_scope_docker_commands():
    doc = _read(DEPLOYMENT_DOC_PATH)
    for forbidden in (
        "docker run",
        "docker system prune",
        "docker volume prune",
        "docker network prune",
        "docker compose build",
    ):
        assert forbidden not in doc


def test_p1b2a_workflow_keeps_local_build_and_runtime_gate_behavior():
    workflow = _read(P1B2A_WORKFLOW_PATH)
    for expected in (
        "build --no-cache backend",
        "build --no-cache frontend",
        "alembic upgrade head",
        "http://127.0.0.1:18100/api/health",
        "Cleanup isolated runtime",
    ):
        assert expected in workflow
    for unexpected in (
        "MOWAYS_BACKEND_REPOSITORY:",
        "MOWAYS_FRONTEND_REPOSITORY:",
        "MOWAYS_POSTGRES_IMAGE:",
        "docker login ghcr.io",
    ):
        assert unexpected not in workflow


def test_migration_gate_starts_only_postgres_before_application_services():
    doc = _read(DEPLOYMENT_DOC_PATH)
    postgres_up = '"${dc[@]}" up -d --no-build postgres'
    migration = "alembic upgrade head"
    app_up = '"${dc[@]}" up -d --no-build backend frontend'
    assert postgres_up in doc
    assert app_up in doc
    assert doc.index(postgres_up) < doc.index(migration) < doc.index(app_up)


def test_migration_gate_waits_for_postgres_health_and_stops_on_failure():
    doc = _read(DEPLOYMENT_DOC_PATH)
    for expected in (
        "for attempt in $(seq 1 60)",
        "mowayspos-postgres",
        '[[ "$status" == "healthy" ]]',
        '[[ "$status" == "exited" || "$status" == "dead" ]]',
        "docker logs --tail 100 mowayspos-postgres",
        '[[ "$attempt" == "60" ]]',
        "sleep 2",
    ):
        assert expected in doc


def test_migration_gate_reads_and_validates_one_alembic_head():
    doc = _read(DEPLOYMENT_DOC_PATH)
    assert "alembic heads" in doc
    assert "test -n \"$expected\"" in doc
    assert "head_count" in doc
    assert 'test "$head_count" = "1"' in doc
    assert "^[A-Za-z0-9_]+$" in doc


def test_migration_run_is_ephemeral_offline_and_dependency_free():
    commands = _squash_whitespace(_bash_blocks(_read(DEPLOYMENT_DOC_PATH)))
    assert '"${dc[@]}" run --rm --no-deps --pull never backend alembic upgrade head' in commands


def test_compose_run_does_not_invent_a_no_build_option():
    bash = _bash_blocks(_read(DEPLOYMENT_DOC_PATH))
    assert not re.search(r"\brun\s+(?:\\\s*)?--no-build\b", bash)


def test_actual_revision_comes_from_postgres_container_environment():
    doc = _read(DEPLOYMENT_DOC_PATH)
    commands = _squash_whitespace(_bash_blocks(doc))
    assert '"${dc[@]}" exec -T postgres sh -ec' in commands
    assert '-U "$POSTGRES_USER"' in doc
    assert '-d "$POSTGRES_DB"' in doc
    assert "select version_num from alembic_version" in doc


def test_expected_and_actual_alembic_revisions_must_match_exactly():
    doc = _read(DEPLOYMENT_DOC_PATH)
    assert 'test -n "$actual"' in doc
    assert 'test "$actual" = "$expected"' in doc
    assert 'echo "alembic_revision=$actual"' in doc


def test_migration_gate_checks_every_required_core_table():
    doc = _read(DEPLOYMENT_DOC_PATH)
    for table in (
        "accounts",
        "auth_sessions",
        "people",
        "projects",
        "project_close_requests",
    ):
        assert f"\\$\\${table}\\$\\$" in doc
    assert "to_regclass(\\$\\$public.\\$\\$ || name) IS NULL" in doc
    assert 'test "$missing" = "0"' in doc
    assert 'echo "required_database_tables=verified"' in doc


def test_migration_failure_is_fail_closed_before_application_start():
    doc = _read(DEPLOYMENT_DOC_PATH)
    gate = doc[doc.index("## 4. Initialize PostgreSQL schema") :]
    assert "set -euo pipefail" in gate
    assert "Do not start backend or frontend if any migration gate command fails." in gate
    assert gate.index("alembic upgrade head") < gate.index(
        '"${dc[@]}" up -d --no-build backend frontend'
    )


def test_migration_guidance_is_idempotent_and_preserves_data_on_failure():
    doc = _squash_whitespace(_read(DEPLOYMENT_DOC_PATH))
    for expected in (
        "first deployment and later releases",
        "already at head",
        "preserve the PostgreSQL data and logs",
        "Do not use `create_all`",
        "Do not delete the database",
        "Do not run `alembic downgrade`",
        "Do not empty the PostgreSQL data directory",
    ):
        assert expected.casefold() in doc.casefold()


def test_migration_bash_does_not_delete_or_downgrade_database_state():
    bash = _bash_blocks(_read(DEPLOYMENT_DOC_PATH))
    for forbidden in (
        "create_all",
        "alembic downgrade",
        "rm -rf",
        "docker volume rm",
        "DROP DATABASE",
        "drop database",
    ):
        assert forbidden not in bash
