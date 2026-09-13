from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1] / "app"

PROJECT_NAME_CALLERS = (
    APP_ROOT / "crud.py",
    APP_ROOT / "permissions.py",
    APP_ROOT / "routers" / "achievement_submissions.py",
    APP_ROOT / "routers" / "achievements.py",
    APP_ROOT / "routers" / "confirmations.py",
    APP_ROOT / "routers" / "dashboard.py",
    APP_ROOT / "routers" / "issues.py",
    APP_ROOT / "routers" / "meetings.py",
    APP_ROOT / "routers" / "subtasks.py",
    APP_ROOT / "routers" / "tasks.py",
    APP_ROOT / "routers" / "updates.py",
    APP_ROOT / "services" / "confirmation_review_workflow.py",
    APP_ROOT / "services" / "meeting_change_set_review_workflow.py",
)


def test_project_name_resolution_has_an_explicit_compatibility_owner():
    compatibility_source = APP_ROOT / "compatibility" / "project_names.py"

    assert compatibility_source.exists(), "historical project-name resolution must live in app.compatibility"
    assert "_NAME_KEYS" in compatibility_source.read_text(encoding="utf-8")


def test_project_name_callers_import_only_the_compatibility_owner():
    for caller in PROJECT_NAME_CALLERS:
        source = caller.read_text(encoding="utf-8")

        assert "services.project_resolution" not in source, caller
        assert "compatibility.project_names" in source, caller


def test_legacy_service_module_is_only_a_deprecated_facade():
    service_module = APP_ROOT / "services" / "project_resolution.py"

    assert not service_module.exists(), "project-name compatibility must not retain a service-layer facade"
