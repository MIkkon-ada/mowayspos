from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.routers.accounts import (
    apply_wecom_identity_record,
    build_wecom_directory_preview,
    sync_wecom_identity_records,
)
from app.routers.people import reset_wecom_identity_field
from app.settings import get_settings
from app.services import wecom


def test_person_company_identity_fields_have_safe_defaults():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        person = models.Person(name="Alice")
        db.add(person)
        db.flush()

        assert person.position_title == ""
        assert person.wecom_userid == ""
        assert person.wecom_department == ""
        assert person.wecom_position_title == ""
        assert person.department_source == "wecom"
        assert person.position_source == "wecom"
        assert "wecom_userid" in {column["name"] for column in inspect(db.bind).get_columns("people")}
    finally:
        db.close()


def test_directory_sync_does_not_require_login_redirect_uri(monkeypatch):
    monkeypatch.setenv("WECOM_CORPID", "corp-id")
    monkeypatch.setenv("WECOM_SECRET", "secret")
    monkeypatch.delenv("WECOM_AGENT_ID", raising=False)
    monkeypatch.delenv("WECOM_REDIRECT_URI", raising=False)

    settings = get_settings()

    assert settings.wecom_directory_enabled is True
    assert settings.wecom_enabled is False


def test_wecom_detailed_directory_uses_member_detail_endpoint(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=10.0):
        calls.append((url, params))
        return {
            "errcode": 0,
            "userlist": [
                {
                    "userid": "alice",
                    "name": "Alice",
                    "department": [1, 7],
                    "position": "产品经理",
                }
            ],
        }

    monkeypatch.setattr(wecom, "_http_get_json", fake_get)
    monkeypatch.setattr(wecom, "get_access_token", lambda: "token")

    users = wecom.list_department_user_details()

    assert users == [
        {
            "userid": "alice",
            "name": "Alice",
            "department": [1, 7],
            "position": "产品经理",
        }
    ]
    assert calls[0][0].endswith("/user/list")
    assert calls[0][1] == {"access_token": "token", "department_id": 1, "fetch_child": 1}


def test_wecom_department_paths_are_built_from_parent_tree(monkeypatch):
    def fake_get(url, params=None, timeout=10.0):
        assert url.endswith("/department/list")
        return {
            "errcode": 0,
            "department": [
                {"id": 1, "name": "博维", "parentid": 0},
                {"id": 7, "name": "产品部", "parentid": 1},
                {"id": 9, "name": "平台组", "parentid": 7},
            ],
        }

    monkeypatch.setattr(wecom, "_http_get_json", fake_get)
    monkeypatch.setattr(wecom, "get_access_token", lambda: "token")

    departments = wecom.build_department_paths(wecom.list_departments())

    assert departments[9]["path"] == "博维 / 产品部 / 平台组"


def test_wecom_sync_preserves_local_overrides_per_field():
    person = models.Person(
        name="Alice",
        department="战略部",
        position_title="产品负责人",
        department_source="local",
        position_source="wecom",
    )

    apply_wecom_identity_record(
        person,
        {
            "userid": "alice",
            "name": "Alice",
            "department_path": "产品部",
            "position": "产品经理",
        },
    )

    assert person.wecom_userid == "alice"
    assert person.wecom_department == "产品部"
    assert person.wecom_position_title == "产品经理"
    assert person.department == "战略部"
    assert person.position_title == "产品经理"
    assert person.department_source == "local"
    assert person.position_source == "wecom"


def test_design_and_migration_keep_project_roles_out_of_sync_scope():
    migration = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "f6a7b8c9d0e1_add_wecom_identity_fields.py"
    source = migration.read_text(encoding="utf-8")

    assert "people" in source
    assert "wecom_userid" in source
    assert "project_members" not in source


def test_wecom_directory_preview_prefers_userid_and_marks_name_matches_for_review():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add_all([
            models.Person(name="Alice", wecom_userid="alice"),
            models.Person(name="Bob"),
        ])
        db.commit()

        preview = build_wecom_directory_preview(
            [
                {"userid": "alice", "name": "Alice", "department": [7], "position": "产品经理"},
                {"userid": "bob", "name": "Bob", "department": [8], "position": "研发工程师"},
                {"userid": "carol", "name": "Carol", "department": [9], "position": "设计师"},
            ],
            {
                7: {"path": "产品部"},
                8: {"path": "研发部"},
                9: {"path": "设计部"},
            },
            db,
        )

        assert [item["match_type"] for item in preview] == ["exact", "name_suggestion", "new"]
        assert preview[0]["matched_person_id"] is not None
        assert preview[1]["needs_confirmation"] is True
        assert preview[2]["needs_confirmation"] is True
    finally:
        db.close()


def test_confirmed_sync_updates_identity_without_touching_project_roles():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        person = models.Person(
            name="Alice",
            wecom_userid="alice",
            department="战略部",
            department_source="local",
            position_source="wecom",
        )
        project = models.Project(name="Project", status="active", is_active=True)
        db.add_all([person, project])
        db.flush()
        member = models.ProjectMember(
            project_id=project.id,
            person_id=person.id,
            person_name_snapshot=person.name,
            role="owner",
        )
        db.add(member)
        db.commit()

        result = sync_wecom_identity_records(
            db,
            [
                {
                    "userid": "alice",
                    "name": "Alice",
                    "department_path": "产品部",
                    "position": "产品经理",
                }
            ],
            [{"wecom_userid": "alice", "person_id": person.id, "create_person": False}],
        )

        assert result[0]["person_id"] == person.id
        db.refresh(person)
        db.refresh(member)
        assert person.department == "战略部"
        assert person.wecom_department == "产品部"
        assert person.position_title == "产品经理"
        assert member.role == "owner"
    finally:
        db.close()


def test_reset_identity_field_restores_latest_wecom_value_independently():
    person = models.Person(
        name="Alice",
        department="战略部",
        wecom_department="产品部",
        department_source="local",
        position_title="产品经理",
        wecom_position_title="高级产品经理",
        position_source="local",
    )

    reset_wecom_identity_field(person, "department")

    assert person.department == "产品部"
    assert person.department_source == "wecom"
    assert person.position_title == "产品经理"
    assert person.position_source == "local"
