from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.compatibility.project_names import resolve_project_context
from app.database import Base


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


@pytest.fixture()
def project_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            models.Project(id=1, name="Current", status="active", is_active=True),
            models.Project(id=2, name="Historical", status="active", is_active=True),
        ]
    )
    db.commit()
    try:
        yield db
    finally:
        db.close()


def test_project_id_is_authoritative_over_historical_name(project_db):
    context = resolve_project_context(project_db, project_id=1, special_project="Historical")

    assert context["project_id"] == 1
    assert context["project_name"] == "Current"
    assert context["source"] == "project_id"
    assert context["matched_by"] == ["project_id"]


def test_name_only_resolution_still_supports_historical_payloads(project_db):
    context = resolve_project_context(project_db, special_project="Historical")

    assert context["project_id"] == 2
    assert context["project_name"] == "Historical"
    assert context["source"] == "special_project"
    assert context["is_valid"] is True


def test_invalid_project_id_does_not_fall_back_to_name(project_db):
    context = resolve_project_context(project_db, project_id=99, special_project="Current")

    assert context["project_id"] is None
    assert context["project_name"] is None
    assert context["source"] is None
    assert context["is_valid"] is False
    assert context["needs_manual_review"] is True


def test_distinct_name_hints_require_manual_review(project_db):
    context = resolve_project_context(
        project_db,
        special_project="Current",
        related_special_project="Historical",
    )

    assert context["is_conflict"] is True
    assert context["needs_manual_review"] is True
    assert context["project_id"] == 1


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
