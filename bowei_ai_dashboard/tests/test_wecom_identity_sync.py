from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.permissions import ROLE_NORMAL
from app.routers.accounts import (
    apply_wecom_identity_record,
    build_wecom_directory_preview,
    provision_wecom_directory_accounts,
    sync_wecom_identity_records,
)
from app.routers.people import reset_wecom_identity_field
from app.routers import accounts as accounts_router
from app.routers import people as people_router
from app.settings import get_settings, load_local_env
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


def test_local_env_loader_sets_missing_values_without_overriding_process_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("WECOM_CORPID=from-file\nWECOM_SECRET=from-file-secret\n", encoding="utf-8")
    monkeypatch.delenv("WECOM_CORPID", raising=False)
    monkeypatch.setenv("WECOM_SECRET", "from-process")

    load_local_env(env_file)

    assert __import__("os").environ["WECOM_CORPID"] == "from-file"
    assert __import__("os").environ["WECOM_SECRET"] == "from-process"


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


def test_visible_department_members_query_each_non_root_department_without_children(monkeypatch):
    calls = []
    departments = [
        {"id": 1, "name": "公司", "parentid": 0},
        {"id": 2, "name": "咨询部", "parentid": 1},
        {"id": 3, "name": "商务部", "parentid": 1},
    ]
    monkeypatch.setattr(wecom, "list_departments", lambda: departments)

    def fake_list_users(department_id, fetch_child):
        calls.append((department_id, fetch_child))
        return (
            [{"userid": "alice", "name": "Alice"}]
            if department_id == 2
            else [{"userid": "alice", "name": "Alice"}, {"userid": "bob", "name": "Bob"}]
        )

    monkeypatch.setattr(wecom, "list_department_users", fake_list_users)

    users, returned_departments = wecom.list_visible_department_users()

    assert calls == [(2, False), (3, False)]
    assert [item["userid"] for item in users] == ["alice", "bob"]
    assert returned_departments == departments


def test_visible_department_details_use_detail_endpoint_for_each_visible_department(monkeypatch):
    calls = []
    monkeypatch.setattr(wecom, "list_departments", lambda: [{"id": 1}, {"id": 8}, {"id": 9}])

    def fake_details(department_id, fetch_child):
        calls.append((department_id, fetch_child))
        return [{"userid": f"user-{department_id}", "department": [department_id]}]

    monkeypatch.setattr(wecom, "list_department_user_details", fake_details)

    users, _ = wecom.list_visible_department_users(details=True)

    assert calls == [(8, False), (9, False)]
    assert [item["userid"] for item in users] == ["user-8", "user-9"]


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


def test_wecom_sync_overwrites_legacy_local_identity_values():
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
    assert person.department == "产品部"
    assert person.position_title == "产品经理"
    assert person.department_source == "wecom"
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
        assert person.department == "产品部"
        assert person.wecom_department == "产品部"
        assert person.position_title == "产品经理"
        assert person.department_source == "wecom"
        assert member.role == "owner"
    finally:
        db.close()


def test_provision_wecom_directory_creates_accounts_and_skips_ambiguous_names():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add_all([
            models.Person(name="王伟", system_role=ROLE_NORMAL),
            models.Person(name="张三"),
            models.Person(name="张三"),
            models.Account(username="lihua", password_hash="existing", status="active"),
        ])
        db.commit()

        result = provision_wecom_directory_accounts(db, [
            {"userid": "lihua", "name": "李华", "department_path": "博维 / 产品部", "position": "产品经理"},
            {"userid": "wangwei", "name": "王伟", "department_path": "博维 / 研发部", "position": "工程师"},
            {"userid": "zhangsan", "name": "张三", "department_path": "博维 / 销售部", "position": "销售"},
        ])

        new_person = db.query(models.Person).filter_by(wecom_userid="lihua").one()
        linked_person = db.query(models.Person).filter_by(wecom_userid="wangwei").one()
        new_account = db.query(models.Account).filter_by(person_id=new_person.id).one()
        linked_account = db.query(models.Account).filter_by(person_id=linked_person.id).one()
        assert (new_person.department, new_person.wecom_department, new_person.position_title) == ("博维 / 产品部", "博维 / 产品部", "产品经理")
        assert (new_account.username, new_account.password_hash, new_account.wecom_userid) == ("lihua-2", "123456", "lihua")
        assert new_account.status == "active"
        assert new_account.must_change_password is False
        assert linked_account.username == "wangwei"
        assert result == {
            "updated": 2,
            "linked_by_name": 1,
            "created_people": 1,
            "created_accounts": 2,
            "conflicts": [{"userid": "zhangsan", "name": "张三", "reason": "ambiguous_name"}],
        }
    finally:
        db.close()


def test_provision_wecom_directory_skips_duplicate_account_userid_bindings():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        first = models.Person(name="Alice", department="原部门")
        second = models.Person(name="Bob", department="原部门")
        db.add_all([first, second])
        db.flush()
        db.add_all([
            models.Account(username="alice", password_hash="password", person_id=first.id, wecom_userid="shared"),
            models.Account(username="bob", password_hash="password", person_id=second.id, wecom_userid="shared"),
        ])
        db.commit()

        result = provision_wecom_directory_accounts(db, [
            {"userid": "shared", "name": "企微成员", "department_path": "博维 / 产品部", "position": "产品经理"},
        ])

        db.refresh(first)
        db.refresh(second)
        assert result == {
            "updated": 0,
            "linked_by_name": 0,
            "created_people": 0,
            "created_accounts": 0,
            "conflicts": [{"userid": "shared", "name": "企微成员", "reason": "duplicate_account_userid"}],
        }
        assert first.department == second.department == "原部门"
    finally:
        db.close()


def test_provision_wecom_directory_endpoint_reads_children_and_returns_stats(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        monkeypatch.setattr(accounts_router, "_require_admin", lambda current_user, session: None)
        monkeypatch.setattr(accounts_router, "get_settings", lambda: SimpleNamespace(wecom_directory_enabled=True))
        monkeypatch.setattr(
            accounts_router.wecom,
            "list_department_user_details",
            lambda **kwargs: [{"userid": "alice", "name": "Alice", "department": [7], "position": "产品经理"}],
        )
        monkeypatch.setattr(
            accounts_router.wecom,
            "list_departments",
            lambda: [{"id": 1, "name": "博维", "parentid": 0}, {"id": 7, "name": "产品部", "parentid": 1}],
        )

        response = accounts_router.provision_wecom_directory_accounts_endpoint(current_user="admin", db=db)

        assert response["created_people"] == 1
        assert response["created_accounts"] == 1
        assert db.query(models.Person).filter_by(wecom_userid="alice").one().department == "博维 / 产品部"
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


def test_narrow_account_management_update_preserves_wecom_identity_and_assignments(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        person = models.Person(
            name="Alice",
            role="负责人",
            department="产品部",
            position_title="产品经理",
            system_role="normal_member",
            permission="审批",
            contact="alice@example.com",
            is_active=False,
        )
        project = models.Project(
            name="Project A",
            coordinator="Alice",
            owners="Alice",
            status="active",
            is_active=True,
        )
        db.add_all([person, project])
        db.flush()
        db.add(models.ProjectMember(
            project_id=project.id,
            person_id=person.id,
            person_name_snapshot="Alice",
            role="owner",
        ))
        db.commit()
        monkeypatch.setattr(people_router, "_require_admin", lambda current_user, session: None)

        people_router.update_person(
            person.id,
            schemas.PersonPayload(name="Alice Chen", system_role="company_ceo"),
            current_user="admin",
            db=db,
        )

        db.refresh(person)
        db.refresh(project)
        member = db.query(models.ProjectMember).filter_by(person_id=person.id).one()
        assert person.department == "产品部"
        assert person.position_title == "产品经理"
        assert person.role == "负责人"
        assert person.permission == "审批"
        assert person.contact == "alice@example.com"
        assert person.is_active is False
        assert project.coordinator == "Alice Chen"
        assert project.owners == "Alice Chen"
        assert member.person_name_snapshot == "Alice Chen"
    finally:
        db.close()
