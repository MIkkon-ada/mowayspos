from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app import schemas
from app.database import Base
from app.main import app
from app.routers import key_tasks
from app.routers.subtasks import list_subtasks_batch
from app.services.key_task_execution import record_execution_event


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_subtask_risk_fields_are_persisted():
    assert {"risk_note", "risk_marked_by", "risk_marked_at"}.issubset(
        models.SubTask.__table__.c.keys()
    )

    db = _db()
    row = models.SubTask(task_id=1, title="关键任务", assignee="负责人")
    row.risk_note = "外部依赖尚未确认"
    row.risk_marked_by = "负责人"
    row.risk_marked_at = datetime(2026, 8, 24, 9, 0)
    db.add(row)
    db.commit()
    row_id = row.id
    db.expunge_all()
    row = db.get(models.SubTask, row_id)

    assert row.risk_note == "外部依赖尚未确认"
    assert row.risk_marked_by == "负责人"
    assert row.risk_marked_at == datetime(2026, 8, 24, 9, 0)


def _seed_batch_access(db):
    db.add_all([
        models.Project(id=1, name="测试项目", status="active", is_active=True),
        models.Person(id=1, name="负责人", is_active=True),
        models.Account(username="owner", password_hash="x", person_id=1, status="active"),
        models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="负责人", role="owner"),
        models.Task(id=10, project_id=1, key_task="重点工作", owner="负责人"),
        models.SubTask(
            id=20, task_id=10, title="关键任务甲", assignee="负责人", status="进行中",
            due_kind="exact", due_date=date.today() - timedelta(days=1),
            risk_note="等待外部接口",
        ),
        models.SubTask(
            id=21, task_id=10, title="关键任务乙", assignee="负责人", status="进行中",
            due_kind="fuzzy", due_label="月底前",
        ),
    ])
    db.commit()


def _submission(subtask_id, submitter, confirmed_at, title):
    return models.UpdateSubmission(
        project_id=1,
        related_task_id=10,
        related_subtask_id=subtask_id,
        submitter=submitter,
        title=title,
        transcript_text=title,
        confirm_status="已确认" if confirmed_at else "待确认",
        confirmed_at=confirmed_at,
    )


def test_batch_subtasks_projects_latest_confirmed_submission_and_status_facts():
    db = _db()
    _seed_batch_access(db)
    older = _submission(20, "甲", datetime(2026, 8, 1), "旧进展")
    newest = _submission(20, "乙", datetime(2026, 8, 2), "新进展")
    draft = _submission(20, "丙", None, "草稿")
    other_task = _submission(21, "丁", datetime(2026, 8, 3), "其他任务进展")
    db.add_all([older, newest, draft, other_task])
    db.commit()

    payload = list_subtasks_batch(task_ids="10", current_user="owner", db=db)
    first, second = payload["10"]

    assert first["latest_confirmed_submission"] == {
        "id": newest.id,
        "submitter": "乙",
        "confirmed_at": "2026-08-02T00:00:00",
        "summary": "新进展",
    }
    assert first["is_overdue"] is True
    assert first["has_risk"] is True
    assert second["latest_confirmed_submission"] == {
        "id": other_task.id,
        "submitter": "丁",
        "confirmed_at": "2026-08-03T00:00:00",
        "summary": "其他任务进展",
    }
    assert second["is_overdue"] is False
    assert second["has_risk"] is False


def test_batch_subtasks_exposes_unconfirmed_submission_state_without_progress_content():
    db = _db()
    _seed_batch_access(db)
    db.add_all([
        models.Project(id=2, name="其他项目", status="active", is_active=True),
        models.Task(id=11, special_project="测试项目", key_task="历史重点工作", owner="负责人"),
        models.SubTask(id=22, task_id=11, title="历史关键任务", assignee="负责人", status="进行中"),
    ])
    pending = models.UpdateSubmission(
        project_id=1,
        submitter="丙",
        title="待确认汇报",
        transcript_text="尚未确认的正式进展内容",
        human_result_json='{"task_reports":[{"matched_subtask_id":20,"completed":["尚未确认的正式进展内容"]},{"matched_subtask_id":22,"completed":["其他待确认内容"]}]}',
        confirm_status="待负责人审核",
        created_at=datetime(2026, 10, 18, 9, 30),
    )
    unrelated = models.UpdateSubmission(
        project_id=2,
        related_subtask_id=20,
        submitter="其他项目成员",
        title="其他项目的错误关联",
        transcript_text="不得显示到当前项目",
        confirm_status="待确认",
    )
    db.add_all([pending, unrelated])
    db.commit()

    batches = list_subtasks_batch(task_ids="10,11", current_user="owner", db=db)
    payload = batches["10"]
    first, second = payload

    assert first["unconfirmed_submission_count"] == 1
    assert first["has_any_submission"] is True
    assert first["latest_unconfirmed_submission"] == {
        "id": pending.id,
        "confirm_status": "待负责人审核",
        "submitter": "丙",
        "created_at": "2026-10-18T09:30:00",
    }
    assert "尚未确认的正式进展内容" not in str(first["latest_unconfirmed_submission"])
    assert second["unconfirmed_submission_count"] == 0
    assert second["has_any_submission"] is False
    assert second["latest_unconfirmed_submission"] is None
    legacy = batches["11"][0]
    assert legacy["unconfirmed_submission_count"] == 1
    assert legacy["latest_unconfirmed_submission"]["id"] == pending.id


def test_batch_subtasks_exposes_reviewed_meeting_progress_as_current_progress():
    db = _db()
    _seed_batch_access(db)
    moment = datetime(2026, 10, 8, 10, 0)
    record_execution_event(
        db, project_id=1, key_task_id=20, event_type="meeting_confirmation",
        source_type="meeting_work_progress", source_id=55,
        dedupe_key="meeting_work_progress:55:confirmed", actor_name="负责人",
        occurred_at=moment, confirmed_at=moment, effective_at=moment,
        affects_current_progress=True, progress_summary="第一批已经完成",
        next_step="继续第二批整理",
    )
    db.commit()

    first = list_subtasks_batch(task_ids="10", current_user="owner", db=db)["10"][0]

    assert first["latest_confirmed_progress"] == {
        "summary": "第一批已经完成", "next_step": "继续第二批整理",
        "source_label": "会议纪要", "confirmed_at": "2026-10-08T10:00:00", "actor": "负责人",
        "action_items": [],
    }


def test_assignee_can_set_and_clear_key_task_risk():
    assert hasattr(key_tasks, "set_key_task_risk")

    db = _db()
    _seed_batch_access(db)
    saved = key_tasks.set_key_task_risk(
        20,
        schemas.KeyTaskRiskRequest(risk_note="等待客户接口"),
        current_user="owner",
        db=db,
    )
    assert saved["key_task"]["risk_note"] == "等待客户接口"
    assert db.get(models.SubTask, 20).risk_marked_by == "owner"

    cleared = key_tasks.set_key_task_risk(
        20,
        schemas.KeyTaskRiskRequest(risk_note=""),
        current_user="owner",
        db=db,
    )
    assert cleared["key_task"]["risk_note"] == ""
    assert db.get(models.SubTask, 20).risk_marked_at is None


def test_batch_subtask_route_precedes_dynamic_subtask_route():
    routes = [route.path for route in app.routes]

    assert routes.index("/api/tasks/subtasks/batch") < routes.index(
        "/api/tasks/{task_id}/subtasks"
    )
