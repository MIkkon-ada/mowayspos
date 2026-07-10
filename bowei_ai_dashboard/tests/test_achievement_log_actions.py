from __future__ import annotations

import ast
import re
from pathlib import Path


ACTION_CODE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def _achievement_log_actions() -> list[tuple[str, int, ast.AST]]:
    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "app" / "routers" / "achievements.py",
        root / "app" / "routers" / "achievement_submissions.py",
    ]
    actions: list[tuple[str, int, ast.AST]] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute) or node.func.attr != "log":
                continue
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "crud":
                continue
            action = node.args[2] if len(node.args) > 2 else None
            for keyword in node.keywords:
                if keyword.arg == "action":
                    action = keyword.value
                    break
            assert action is not None, f"crud.log at {path.name}:{node.lineno} is missing action"
            actions.append((path.name, node.lineno, action))
    return actions


def test_achievement_log_actions_are_static_english_codes():
    for filename, line, action in _achievement_log_actions():
        location = f"{filename}:{line}"
        assert isinstance(action, ast.Constant) and isinstance(action.value, str), (
            f"crud.log action at {location} must be a static string literal"
        )
        value = action.value
        assert not CHINESE_RE.search(value), f"crud.log action at {location} contains Chinese: {value!r}"
        assert " " not in value, f"crud.log action at {location} contains spaces: {value!r}"
        assert ACTION_CODE_RE.fullmatch(value), (
            f"crud.log action at {location} must match {ACTION_CODE_RE.pattern}: {value!r}"
        )
