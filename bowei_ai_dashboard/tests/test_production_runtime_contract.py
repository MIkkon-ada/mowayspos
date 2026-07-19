from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")


def test_compose_isolates_services_and_publishes_only_loopback_frontend():
    compose = _read("docker-compose.prod.yml")

    for expected in (
        "name: mowayspos",
        "container_name: mowayspos-postgres",
        "container_name: mowayspos-backend",
        "container_name: mowayspos-frontend",
        "mowayspos_app:",
        "127.0.0.1:18100:80",
        "${MOWAYS_DATA_ROOT:-/data/mowayspos}/postgres:/var/lib/postgresql/data",
        "${MOWAYS_DATA_ROOT:-/data/mowayspos}/env/llm_configs.json:/app/llm_configs.json",
        "postgresql+psycopg://",
    ):
        assert expected in compose

    for forbidden in (
        '"80:80"',
        "127.0.0.1:5432:5432",
        "127.0.0.1:8008:8008",
        "bowei-postgres",
        "bowei-backend",
        "bowei-frontend",
        "bowei_postgres_data",
    ):
        assert forbidden not in compose

    assert compose.count("restart: unless-stopped") == 3
    assert compose.count("driver: json-file") == 3
    assert compose.count("healthcheck:") == 3
    assert compose.count("ports:") == 1


def test_compose_forces_production_security_values_after_env_file():
    compose = _read("docker-compose.prod.yml")

    for expected in (
        "APP_ENV: production",
        "FRONTEND_ORIGIN: https://pos.moways.com.cn",
        "CORS_ALLOWED_ORIGINS: https://pos.moways.com.cn",
        "SESSION_COOKIE_SECURE: \"true\"",
        "ALLOW_FILE_SECRET_FALLBACK: \"false\"",
        "ALLOW_LEGACY_PASSWORD_LOGIN: \"false\"",
        "BOWEI_DEV_MODE: \"false\"",
        "ALLOW_DEV_SCHEMA_CREATE_ALL: \"false\"",
        "ALLOW_PROTECTED_DATABASE_MIGRATION: \"false\"",
    ):
        assert expected in compose


def test_production_environment_example_is_secret_free_and_complete():
    example = _read(".env.production.example")

    for expected in (
        "MOWAYS_IMAGE_TAG=replace_with_git_commit_sha",
        "MOWAYS_DATA_ROOT=/data/mowayspos",
        "MOWAYS_ENV_FILE=/data/mowayspos/env/production.env",
        "DATABASE_URL=postgresql+psycopg://mowayspos:replace_with_same_password@postgres:5432/mowayspos",
        "SESSION_COOKIE_NAME=moways_session",
        "ANTHROPIC_API_KEY=",
        "DASHSCOPE_API_KEY=",
        "DEEPSEEK_API_KEY=",
        "ZHIPUAI_API_KEY=",
    ):
        assert expected in example

    assert "ALLOW_FILE_SECRET_FALLBACK=false" in example
    assert "ALLOW_DEV_SCHEMA_CREATE_ALL=false" in example
    assert "ALLOW_PROTECTED_DATABASE_MIGRATION=false" in example


def test_inner_nginx_has_api_websocket_upload_and_forwarded_proto_contract():
    nginx = _read("nginx.conf")

    for expected in (
        "client_max_body_size 210m;",
        "map $http_upgrade $connection_upgrade",
        "map $http_x_forwarded_proto $proxy_x_forwarded_proto",
        "location = /api/transcribe/stream",
        "proxy_set_header Upgrade $http_upgrade;",
        "proxy_set_header Connection $connection_upgrade;",
        "proxy_read_timeout 3600s;",
        "proxy_send_timeout 3600s;",
        "location /api/",
        "proxy_connect_timeout 30s;",
        "proxy_read_timeout 300s;",
        "proxy_send_timeout 300s;",
        "proxy_set_header X-Forwarded-Proto $proxy_x_forwarded_proto;",
        "try_files $uri $uri/ /index.html;",
    ):
        assert expected in nginx


def test_frontend_dockerfile_uses_tracked_lockfile_with_npm_ci():
    dockerfile = _read("Dockerfile.frontend")

    assert "COPY frontend/package.json frontend/package-lock.json ./" in dockerfile
    assert "RUN npm ci" in dockerfile
    assert "npm install" not in dockerfile


def test_github_actions_gate_runs_the_complete_isolated_runtime_contract():
    workflow = _read(".github/workflows/cloud-p1b2a-gate.yml")

    assert "MOWAYS_DATA_ROOT: ${{ runner.temp }}" not in workflow
    assert "MOWAYS_ENV_FILE: ${{ runner.temp }}" not in workflow
    assert 'runtime_root="$RUNNER_TEMP/moways-p1b2a-runtime"' in workflow
    assert 'echo "MOWAYS_DATA_ROOT=$runtime_root" >> "$GITHUB_ENV"' in workflow
    assert 'echo "MOWAYS_ENV_FILE=$env_file" >> "$GITHUB_ENV"' in workflow

    for expected in (
        "workflow_dispatch:",
        "cloud-p1b2a-cvm-production-runtime-config",
        "contents: read",
        "runs-on: ubuntu-latest",
        "python-version: '3.12'",
        "node-version: '20'",
        "python -m pip install pytest==9.0.3",
        "npm ci",
        "python -m compileall bowei_ai_dashboard/app",
        "docker compose",
        "build --no-cache backend",
        "build --no-cache frontend",
        "nginx -t",
        "alembic upgrade head",
        "http://127.0.0.1:18100/api/health",
        "LLM configuration survives backend recreation",
        "Session cookie and production LLM key contracts",
        "git diff --check",
        "Cleanup isolated runtime",
    ):
        assert expected in workflow

    for forbidden in (
        "docker login",
        "docker push",
        "docker system prune",
        "docker volume prune",
        "docker network prune",
        "registry-mirrors",
        "TENCENT",
        "SSH_KEY",
    ):
        assert forbidden not in workflow
