from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET_DIRS = [ROOT / "app", ROOT / "scripts"]
QUESTION_MARK_RUN = re.compile(r"\?{3,}")


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for base in TARGET_DIRS:
        if base.exists():
            files.extend(
                path
                for path in base.rglob("*.py")
                if "__pycache__" not in path.parts
                and "node_modules" not in path.parts
                and "dist" not in path.parts
                and "build" not in path.parts
                and "venv" not in path.parts
                and ".venv" not in path.parts
            )
    return files


def test_no_corrupted_question_marks_in_backend_python_sources() -> None:
    matches: list[str] = []
    for path in _iter_python_files():
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for match in QUESTION_MARK_RUN.finditer(line):
                snippet = line[max(0, match.start() - 30) : min(len(line), match.end() + 30)]
                matches.append(f"{path}:{line_no}: {snippet}")

    assert not matches, "Found corrupted question-mark runs:\n" + "\n".join(matches)
