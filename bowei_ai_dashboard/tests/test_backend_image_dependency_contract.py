from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS_PATH = REPOSITORY_ROOT / "bowei_ai_dashboard" / "requirements.txt"
DOCKERFILE_PATH = REPOSITORY_ROOT / "Dockerfile.backend"

EXPECTED_DIRECT_DEPENDENCIES = {
    "alembic",
    "anthropic",
    "bcrypt",
    "cryptography",
    "dashscope",
    "fastapi",
    "openai",
    "openpyxl",
    "psycopg[binary]",
    "pydantic",
    "pypdf",
    "python-docx",
    "python-multipart",
    "python-pptx",
    "sqlalchemy",
    "uvicorn[standard]",
    "xlrd",
}


def _requirement_names() -> set[str]:
    lines = REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()
    return {
        line.split("==", 1)[0].lower()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_backend_requirements_are_exactly_pinned_for_clean_image_builds():
    lines = [
        line.strip()
        for line in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert all(line.count("==") == 1 for line in lines)
    assert _requirement_names() == EXPECTED_DIRECT_DEPENDENCIES


def test_backend_dockerfile_installs_the_tracked_runtime_contract():
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")

    assert "COPY bowei_ai_dashboard/requirements.txt ." in dockerfile
    assert "pip install --no-cache-dir -r requirements.txt" in dockerfile
    assert dockerfile.index("antiword") < dockerfile.index("pip install")
    assert dockerfile.index("rm -rf /var/lib/apt/lists/*") < dockerfile.index("pip install")
    assert 'CMD ["uvicorn", "app.main:app"' in dockerfile


def test_backend_dockerfile_runs_as_an_unprivileged_runtime_user():
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")

    assert "groupadd --system --gid 10001 app" in dockerfile
    assert "useradd --system --uid 10001 --gid 10001" in dockerfile
    assert "mkdir -p /app/data" in dockerfile
    assert "chown -R app:app /app/data" in dockerfile
    assert "llm_configs.json" not in dockerfile
    assert "chown -R app:app /app\n" not in dockerfile
    assert "USER app:app" in dockerfile
    assert dockerfile.index("chown -R app:app /app/data") < dockerfile.index("USER app:app")
    assert dockerfile.index("USER app:app") < dockerfile.index('CMD ["uvicorn"')


def test_binary_psycopg_image_does_not_install_a_build_toolchain():
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")

    assert "gcc" not in dockerfile
    assert "libpq-dev" not in dockerfile
