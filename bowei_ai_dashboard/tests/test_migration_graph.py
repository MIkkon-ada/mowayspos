from pathlib import Path
import subprocess
import sys


def test_repository_has_a_single_alembic_head():
    backend_root = Path(__file__).parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=backend_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    heads = [line for line in result.stdout.splitlines() if "(head)" in line]
    assert len(heads) == 1, result.stdout
