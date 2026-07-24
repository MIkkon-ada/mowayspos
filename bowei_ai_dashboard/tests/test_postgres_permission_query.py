from pathlib import Path


def test_permission_lookup_uses_boolean_coalesce_defaults():
    source = (Path(__file__).resolve().parents[1] / "app" / "permissions.py").read_text(encoding="utf-8")

    assert "COALESCE(a.is_tech_admin, FALSE)" in source
    assert "COALESCE(p.is_admin, FALSE)" in source
