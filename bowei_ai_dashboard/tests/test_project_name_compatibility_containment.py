from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def test_project_name_resolution_has_an_explicit_compatibility_owner():
    compatibility_source = APP_ROOT / "compatibility" / "project_names.py"

    assert compatibility_source.exists(), "historical project-name resolution must live in app.compatibility"
    assert "_NAME_KEYS" in compatibility_source.read_text(encoding="utf-8")
