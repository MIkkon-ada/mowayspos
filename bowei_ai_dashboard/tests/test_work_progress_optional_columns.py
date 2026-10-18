from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import Base
from app.routers import projects, subtasks
from tests.test_execution_submission_to_work_progress_flow import _seed_execution_team
from tests.test_migration_bootstrap import _output, _run_alembic


PRE_WORK_PROGRESS_REVISION = "l3m4n5o6p7q"


def _db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add_all([
        models.Project(id=1, name="项目一", status="active", is_active=True),
        models.Task(id=1, project_id=1, key_task="重点工作"),
        models.SubTask(id=1, task_id=1, title="关键任务", assignee="张三", expected_outcome="初稿", goal="达成共识", bowei_role="负责分析"),
    ])
    db.commit()
    return db


def test_project_columns_are_shared_and_key_task_fields_survive_older_editors(monkeypatch):
    db = _db()
    monkeypatch.setattr(projects, "authorize_project_action", lambda *args, **kwargs: None)
    monkeypatch.setattr(subtasks, "get_user_context_from_db", lambda *args, **kwargs: {})
    monkeypatch.setattr(subtasks, "_check_subtask_struct_write", lambda *args, **kwargs: None)
    monkeypatch.setattr(subtasks, "_validate_key_task_people", lambda *args, **kwargs: None)
    monkeypatch.setattr(subtasks, "require_project_business_writable", lambda *args, **kwargs: None)
    monkeypatch.setattr(subtasks, "_sync_parent_task_status", lambda *args, **kwargs: None)

    projects.update_work_progress_columns(1, schemas.WorkProgressColumnsPayload(optional_columns=["expectedOutcome", "goal", "boweiRole"]), current_user="张三", db=db)
    assert projects.get_work_progress_columns(1, current_user="李四", db=db)["optional_columns"] == ["expectedOutcome", "goal", "boweiRole"]

    result = subtasks.update_subtask(1, schemas.SubTaskPayload(title="关键任务已修改", assignee="张三"), current_user="张三", db=db)
    assert (result["expected_outcome"], result["goal"], result["bowei_role"]) == ("初稿", "达成共识", "负责分析")

    result = subtasks.update_subtask(1, schemas.SubTaskPayload(title="关键任务已修改", assignee="张三", bowei_role="负责培训"), current_user="张三", db=db)
    assert (result["expected_outcome"], result["goal"], result["bowei_role"]) == ("初稿", "达成共识", "负责培训")
    db.close()


def test_downgrade_refuses_to_drop_configured_progress_fields(tmp_path: Path):
    database = tmp_path / "work-progress-values.db"
    result = _run_alembic(database, "upgrade", "head")
    assert result.returncode == 0, _output(result)

    engine = create_engine(f"sqlite:///{database.resolve().as_posix()}")
    db = Session(engine)
    team = _seed_execution_team(db)
    team["project"].work_progress_optional_columns = ["expectedOutcome", "goal"]
    team["subtask"].expected_outcome = "完成联调"
    team["subtask"].goal = "形成验收结论"
    team["subtask"].bowei_role = "负责协调"
    project_id = team["project"].id
    subtask_id = team["subtask"].id
    db.commit()
    db.close()

    result = _run_alembic(database, "downgrade", PRE_WORK_PROGRESS_REVISION)

    assert result.returncode != 0
    assert "work progress data would be lost" in _output(result)
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == "m4n5o6p7q8r9"
        assert connection.execute(sa.text("SELECT work_progress_optional_columns FROM projects WHERE id = 1")).scalar_one() == '["expectedOutcome", "goal"]'
        assert connection.execute(sa.text("SELECT expected_outcome, goal, bowei_role FROM subtasks WHERE id = 1")).one() == ("完成联调", "形成验收结论", "负责协调")

    # This database is intentionally stopped at an older revision, so use its
    # physical schema instead of querying it through the current ORM model.
    with engine.begin() as connection:
        connection.execute(
            sa.text("UPDATE projects SET work_progress_optional_columns = '[]' WHERE id = :id"),
            {"id": project_id},
        )
    result = _run_alembic(database, "downgrade", PRE_WORK_PROGRESS_REVISION)
    assert result.returncode != 0
    assert "work progress data would be lost" in _output(result)

    with engine.begin() as connection:
        connection.execute(
            sa.text("UPDATE subtasks SET expected_outcome = '', goal = '', bowei_role = '' WHERE id = :id"),
            {"id": subtask_id},
        )
        connection.execute(
            sa.text("UPDATE projects SET work_progress_optional_columns = :columns WHERE id = :id"),
            {"id": project_id, "columns": '["expectedOutcome"]'},
        )
    result = _run_alembic(database, "downgrade", PRE_WORK_PROGRESS_REVISION)
    assert result.returncode != 0
    assert "work progress data would be lost" in _output(result)

    with engine.begin() as connection:
        connection.execute(
            sa.text("UPDATE projects SET work_progress_optional_columns = '[]' WHERE id = :id"),
            {"id": project_id},
        )
    result = _run_alembic(database, "downgrade", PRE_WORK_PROGRESS_REVISION)
    assert result.returncode == 0, _output(result)
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == PRE_WORK_PROGRESS_REVISION

    result = _run_alembic(database, "upgrade", "head")
    assert result.returncode == 0, _output(result)
    assert "expected_outcome" in {column["name"] for column in sa.inspect(engine).get_columns("subtasks")}
    engine.dispose()
