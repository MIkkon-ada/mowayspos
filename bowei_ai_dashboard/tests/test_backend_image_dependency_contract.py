from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS_PATH = REPOSITORY_ROOT / "bowei_ai_dashboard" / "requirements.txt"
DOCKERFILE_PATH = REPOSITORY_ROOT / "Dockerfile.backend"

EXPECTED_DIRECT_DEPENDENCIES = {
    "alembic",
    "anthropic",
    "bcrypt",
    "dashscope",
    "fastapi",
    "openai",
    "psycopg[binary]",
    "pydantic",
    "python-docx",
    "python-multipart",
    "sqlalchemy",
    "uvicorn[standard]",
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
    assert "RUN pip install --no-cache-dir -r requirements.txt" in dockerfile
    assert 'CMD ["uvicorn", "app.main:app"' in dockerfile


def test_binary_psycopg_image_does_not_install_a_build_toolchain():
    dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")

    assert "gcc" not in dockerfile
    assert "libpq-dev" not in dockerfile
