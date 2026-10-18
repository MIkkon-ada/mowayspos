import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models, schemas
from app.database import Base
from app.routers import projects


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        models.Project(id=1, name="Initiation", status="dispatched", objectives="目标", start_date="2026-10-01"),
        models.Project(id=2, name="Other", status="dispatched"),
        models.Person(id=1, name="PM", system_role="normal_member", is_active=True),
        models.Person(id=2, name="Coach", system_role="normal_member", is_active=True),
        models.Person(id=3, name="Other PM", system_role="normal_member", is_active=True),
        models.Account(username="pm", password_hash="x", person_id=1, status="active"),
        models.Account(username="coach", password_hash="x", person_id=2, status="active"),
        models.Account(username="pm2", password_hash="x", person_id=3, status="active"),
        models.ProjectMember(project_id=1, person_id=1, role="owner"),
        models.ProjectMember(project_id=1, person_id=2, role="project_ceo"),
        models.ProjectMember(project_id=1, person_id=3, role="owner"),
    ])
    session.commit()
    yield session
    session.close()
    engine.dispose()


def plan(title="Delivery", task_id=None, subtask_id=None):
    return schemas.ProjectProfilePayload(replace_plan=True, work_progress_draft=[{
        "id": task_id, "title": title, "goal": "完整交付", "acceptance_criteria": "验收通过",
        "subtasks": [{"id": subtask_id, "title": "Review", "assignee_id": 1,
                      "plan_start": "2026-10-01", "plan_end": "2026-10-12"}],
    }])


def test_partial_draft_survives_new_session_without_formal_writes(db):
    payload = schemas.ProjectProfilePayload(work_progress_draft=[{"title": "进行中的草稿 ", "subtasks": [{"title": ""}]}])
    projects.save_owner_plan_draft(1, payload, current_user="pm", db=db)
    db.expire_all()
    result = projects.get_owner_plan_draft(1, current_user="pm", db=db)
    assert result["draft"]["work_progress_draft"][0]["title"] == "进行中的草稿 "
    assert db.get(models.Project, 1).status == "dispatched"
    assert db.query(models.Task).count() == db.query(models.SubTask).count() == 0
    assert projects.get_owner_plan_draft(1, current_user="pm2", db=db)["draft"] is None


@pytest.mark.parametrize("status", ["draft", "pending_review", "active", "pending_close", "ended", "archived"])
def test_draft_write_rejects_non_editable_states(db, status):
    db.get(models.Project, 1).status = status
    db.commit()
    with pytest.raises(HTTPException):
        projects.save_owner_plan_draft(1, plan(), current_user="pm", db=db)


def test_coach_cannot_read_or_save_an_owners_private_draft(db):
    for operation in [projects.get_owner_plan_draft, projects.save_owner_plan_draft]:
        with pytest.raises(HTTPException) as error:
            operation(1, **({"payload": plan()} if operation == projects.save_owner_plan_draft else {}), current_user="coach", db=db)
        assert error.value.status_code == 403


def test_return_restores_reviewed_plan_and_comment_then_renames_in_place(db):
    projects.save_owner_plan_draft(1, plan(), current_user="pm", db=db)
    projects.owner_submit_project_profile(1, plan(), current_user="pm", db=db)
    projects.return_project(1, reason="补充任务评价指标", current_user="coach", db=db)
    result = projects.get_owner_plan_draft(1, current_user="pm", db=db)
    assert result["draft"] is None
    assert result["return_reason"] == "补充任务评价指标"
    existing = result["existing_plan"][0]
    assert existing["goal"] == "完整交付"
    assert existing["subtasks"][0]["plan_end"] == "2026-10-12"
    projects.owner_submit_project_profile(1, plan("Renamed", existing["id"], existing["subtasks"][0]["id"]), current_user="pm", db=db)
    assert db.query(models.Task).count() == db.query(models.SubTask).count() == 1
    assert db.query(models.Task).one().key_task == "Renamed"
    projects.approve_project(1, current_user="coach", db=db)
    assert db.get(models.Project, 1).status == "active"


def test_revised_plan_removes_omitted_task_without_leaving_active_duplicates(db):
    original = plan()
    original.work_progress_draft.append(schemas.ProjectWorkProgressTaskDraft(title="Remove me", subtasks=[{"title": "Old", "assignee_id": 1}]))
    projects.owner_submit_project_profile(1, original, current_user="pm", db=db)
    projects.return_project(1, reason="精简", current_user="coach", db=db)
    existing = projects.get_owner_plan_draft(1, current_user="pm", db=db)["existing_plan"][0]
    projects.owner_submit_project_profile(1, plan(task_id=existing["id"], subtask_id=existing["subtasks"][0]["id"]), current_user="pm", db=db)
    assert db.query(models.Task).filter_by(is_deleted=False).count() == 1
    assert db.query(models.SubTask).filter_by(is_deleted=False).count() == 1


def test_foreign_task_id_is_rejected_without_partial_writes(db):
    db.add(models.Task(id=100, project_id=2, key_task="Foreign", is_deleted=False))
    db.commit()
    with pytest.raises(HTTPException) as error:
        projects.owner_submit_project_profile(1, plan(task_id=100), current_user="pm", db=db)
    assert error.value.status_code == 422
    assert db.get(models.Project, 1).status == "dispatched"
    assert db.get(models.Task, 100).key_task == "Foreign"


def test_new_same_named_workstreams_remain_distinct_plan_rows(db):
    payload = plan()
    payload.work_progress_draft.append(schemas.ProjectWorkProgressTaskDraft(title="Delivery", subtasks=[{"title": "Second", "assignee_id": 1}]))
    projects.owner_submit_project_profile(1, payload, current_user="pm", db=db)
    assert db.query(models.Task).filter_by(is_deleted=False).count() == 2


def test_revision_cannot_remove_a_workstream_with_a_linked_issue(db):
    projects.owner_submit_project_profile(1, plan(), current_user="pm", db=db)
    original = db.query(models.Task).one()
    db.add(models.Issue(project_id=1, description="保留来源", related_task_id=original.id))
    db.commit()
    projects.return_project(1, reason="修订", current_user="coach", db=db)
    with pytest.raises(HTTPException) as error:
        projects.owner_submit_project_profile(1, plan("Replacement"), current_user="pm", db=db)
    assert error.value.status_code == 409
    assert db.get(models.Project, 1).status == "returned"
    assert db.query(models.Task).filter_by(is_deleted=False).count() == 1


def test_owner_plan_migration_round_trip_and_data_loss_guard(tmp_path):
    from test_cross_project_submission_batch_migration import _run, _assert_ok
    import sqlalchemy as sa
    database = tmp_path / "owner-plan.db"
    _assert_ok(_run(database, "upgrade", "y6z7a8b9c0d1"))
    engine = sa.create_engine(f"sqlite:///{database.as_posix()}")
    assert "owner_plan_drafts" in {column["name"] for column in sa.inspect(engine).get_columns("projects")}
    assert sa.inspect(engine).get_columns("subtasks")[next(i for i, column in enumerate(sa.inspect(engine).get_columns("subtasks")) if column["name"] == "plan_time")]["type"].length == 80
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO projects (name, owner_plan_drafts) VALUES (:name, :draft)"), {"name": "Draft", "draft": '{"person:1":{"payload":{"work_progress_draft":[]}}}'})
    result = _run(database, "downgrade", "x5y6z7a8b9c0")
    assert result.returncode != 0
    assert "owner plan drafts would be lost" in result.stdout + result.stderr
    with engine.begin() as connection:
        connection.execute(sa.text("UPDATE projects SET owner_plan_drafts = '{}'"))
    _assert_ok(_run(database, "downgrade", "x5y6z7a8b9c0"))
    _assert_ok(_run(database, "upgrade", "y6z7a8b9c0d1"))
    engine.dispose()


def test_http_save_return_resubmit_approve_keeps_the_same_tasks(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.database import get_db
    app = FastAPI()
    app.include_router(projects.router)
    actor = ["pm"]
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[projects.get_current_user_name] = lambda: actor[0]
    with TestClient(app) as client:
        body = plan().model_dump(mode="json")
        assert client.put('/api/projects/1/owner-plan-draft', json=body).status_code == 200
        assert client.post('/api/projects/1/owner-submit', json=body).status_code == 200
        actor[0] = "coach"
        assert client.post('/api/projects/1/return?reason=补充标准', json={}).status_code == 200
        actor[0] = "pm"
        recovered = client.get('/api/projects/1/owner-plan-draft').json()
        assert recovered['return_reason'] == "补充标准"
        edited = {'replace_plan': True, 'work_progress_draft': recovered['existing_plan']}
        edited['work_progress_draft'][0]['title'] = 'Revised delivery'
        assert client.post('/api/projects/1/owner-submit', json=edited).status_code == 200
        actor[0] = "coach"
        assert client.post('/api/projects/1/approve', json={}).status_code == 200
    assert db.get(models.Project, 1).status == 'active'
    assert db.query(models.Task).filter_by(is_deleted=False).count() == 1
    assert db.query(models.SubTask).filter_by(is_deleted=False).count() == 1
