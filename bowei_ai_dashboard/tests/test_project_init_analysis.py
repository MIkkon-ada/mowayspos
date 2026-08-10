from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models, schemas
from app.database import Base
from app.time_utils import utc_now


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def add_project_graph(db, *, project_id: int = 1, status: str = "dispatched"):
    project = models.Project(id=project_id, name=f"Project {project_id}", status=status)
    owner = models.Person(id=project_id, name=f"Owner {project_id}", is_active=True)
    member = models.ProjectMember(
        project_id=project_id,
        person_id=project_id,
        person_name_snapshot=owner.name,
        role="owner",
    )
    db.add_all([project, owner, member])
    db.flush()
    return project, owner


def add_attachment(db, *, project_id: int, attachment_id: int, size: int = 10, deleted_at=None):
    row = models.ProjectInitAttachment(
        id=attachment_id,
        project_id=project_id,
        storage_key=f"{project_id}/{attachment_id}",
        original_name=f"source-{attachment_id}.txt",
        mime_type="text/plain",
        size_bytes=size,
        uploaded_by="owner",
        deleted_at=deleted_at,
    )
    db.add(row)
    db.flush()
    return row


def test_run_model_has_frozen_snapshot_and_worker_timestamps():
    table = models.ProjectInitAnalysisRun.__table__
    assert {"snapshot_json", "started_at", "finished_at"} <= set(table.c.keys())
    assert table.c.snapshot_json.default.arg == "{}"


def test_create_run_freezes_attachments_and_project_snapshot(monkeypatch):
    from app.routers import project_init_ai

    db = make_session()
    project, _owner = add_project_graph(db)
    db.add(models.Account(username="owner", password_hash="x", person_id=project.id, status="active"))
    db.add(models.Task(project_id=project.id, key_task="Frozen task", owner="Owner 1"))
    add_attachment(db, project_id=project.id, attachment_id=10, size=100)
    db.commit()

    scheduled: list[int] = []
    background = SimpleNamespace(add_task=lambda fn, run_id: scheduled.append(run_id))
    result = project_init_ai.create_project_init_analysis_run(
        project_id=project.id,
        payload=schemas.ProjectInitAnalysisCreate(
            attachment_ids=[10],
            current_draft=[schemas.ProjectWorkProgressTaskDraft(title="Existing draft")],
        ),
        background_tasks=background,
        current_user="owner",
        db=db,
    )

    run = db.get(models.ProjectInitAnalysisRun, result["id"])
    assert run.status == "queued"
    assert json.loads(run.attachment_ids_json) == [10]
    snapshot = json.loads(run.snapshot_json)
    assert snapshot["project"]["status"] == "dispatched"
    assert snapshot["tasks"][0]["key_task"] == "Frozen task"
    assert scheduled == [run.id]
    response = schemas.ProjectInitAnalysisRunResponse.model_validate(result)
    assert response.status == "queued"
    assert json.loads(run.snapshot_json)["current_draft"][0]["title"] == "Existing draft"


@pytest.mark.parametrize("count", [11])
def test_create_run_rejects_more_than_ten_attachments(count):
    from app.services.project_init_analysis import validate_analysis_attachment_selection

    with pytest.raises(HTTPException) as error:
        validate_analysis_attachment_selection(list(range(1, count + 1)), list(range(count)), {})
    assert error.value.status_code == 422


def test_create_run_rejects_cross_project_deleted_and_100_mib_over_limit():
    from app.services.project_init_analysis import validate_analysis_attachment_selection

    db = make_session()
    add_project_graph(db, project_id=1)
    add_project_graph(db, project_id=2)
    add_attachment(db, project_id=1, attachment_id=1, size=100)
    add_attachment(db, project_id=2, attachment_id=2, size=100)
    add_attachment(db, project_id=1, attachment_id=3, size=100, deleted_at=utc_now())
    db.commit()

    rows = {row.id: row for row in db.query(models.ProjectInitAttachment).all()}
    with pytest.raises(HTTPException) as cross_project:
        validate_analysis_attachment_selection([2], [rows[2]], {"project_id": 1})
    assert cross_project.value.status_code == 404
    with pytest.raises(HTTPException) as deleted:
        validate_analysis_attachment_selection([3], [rows[3]], {"project_id": 1})
    assert deleted.value.status_code == 404
    with pytest.raises(HTTPException) as too_large:
        validate_analysis_attachment_selection([1], [SimpleNamespace(id=1, project_id=1, deleted_at=None, size_bytes=100 * 1024 * 1024 + 1)], {"project_id": 1})
    assert too_large.value.status_code == 413


def test_worker_success_updates_monotonic_progress_and_keeps_snapshot(monkeypatch, tmp_path):
    from app.services import project_init_analysis as service

    db = make_session()
    project, owner = add_project_graph(db)
    attachment = add_attachment(db, project_id=project.id, attachment_id=1)
    run = models.ProjectInitAnalysisRun(
        project_id=project.id,
        attachment_ids_json="[1]",
        snapshot_json=json.dumps({"project": {"status": "dispatched"}, "tasks": [], "people": []}),
        created_by="owner",
    )
    db.add(run)
    db.commit()
    run_id = run.id
    run_id = run.id
    (tmp_path / "source-1.txt").write_text("Frozen source", encoding="utf-8")
    monkeypatch.setattr(service, "SessionLocal", lambda: db)
    monkeypatch.setattr(service, "parse_project_init_file", lambda path, original_name=None: [{"file_name": "source-1.txt", "location": "lines 1", "text": "Frozen source", "attachment_id": 1}])
    monkeypatch.setattr(service, "generate_project_init_draft", lambda chunks, people, tasks: SimpleNamespace(model_dump=lambda: {"tasks": [{"title": "Draft task"}], "warnings": []}, tasks=[SimpleNamespace()]))
    monkeypatch.setattr(service, "_attachment_path", lambda row: tmp_path / "source-1.txt")

    service.process_analysis_run(run_id)
    db.expire_all()
    stored = db.get(models.ProjectInitAnalysisRun, run_id)
    assert stored.status == "completed"
    assert stored.progress == 100
    assert stored.started_at is not None
    assert stored.finished_at is not None
    assert json.loads(stored.current_draft_json)["tasks"][0]["title"] == "Draft task"
    assert json.loads(stored.result_json)["task_count"] == 1
    assert json.loads(stored.snapshot_json)["project"]["status"] == "dispatched"


def test_worker_all_failure_is_failed_and_does_not_leak_provider_secret(monkeypatch, tmp_path):
    from app.services import project_init_analysis as service

    db = make_session()
    project, _owner = add_project_graph(db)
    add_attachment(db, project_id=project.id, attachment_id=1)
    run = models.ProjectInitAnalysisRun(
        project_id=project.id,
        attachment_ids_json="[1]",
        snapshot_json=json.dumps({"project": {}, "tasks": [], "people": []}),
        created_by="owner",
    )
    db.add(run)
    db.commit()
    run_id = run.id
    (tmp_path / "source-1.txt").write_text("bad", encoding="utf-8")
    monkeypatch.setattr(service, "SessionLocal", lambda: db)
    monkeypatch.setattr(service, "parse_project_init_file", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("secret-api-key prompt body")))
    monkeypatch.setattr(service, "_attachment_path", lambda row: tmp_path / "source-1.txt")

    service.process_analysis_run(run_id)
    db.expire_all()
    stored = db.get(models.ProjectInitAnalysisRun, run_id)
    assert stored.status == "failed"
    assert "secret-api-key" not in stored.error_summary
    assert "prompt body" not in stored.error_summary


def test_worker_partial_attachment_failure_preserves_successful_draft(monkeypatch, tmp_path):
    from app.services import project_init_analysis as service

    db = make_session()
    project, _owner = add_project_graph(db)
    add_attachment(db, project_id=project.id, attachment_id=1)
    add_attachment(db, project_id=project.id, attachment_id=2)
    run = models.ProjectInitAnalysisRun(
        project_id=project.id,
        attachment_ids_json="[1, 2]",
        snapshot_json=json.dumps({
            "project": {},
            "tasks": [],
            "people": [],
            "attachments": [
                {"id": 1, "storage_key": "1/1", "original_name": "ok.txt", "size_bytes": 2},
                {"id": 2, "storage_key": "1/2", "original_name": "bad.txt", "size_bytes": 2},
            ],
        }),
        created_by="owner",
    )
    db.add(run)
    db.commit()
    run_id = run.id
    monkeypatch.setattr(service, "SessionLocal", lambda: db)
    monkeypatch.setattr(service, "_attachment_path", lambda storage_key: tmp_path / str(storage_key).replace("/", "-"))
    (tmp_path / "1-1").write_text("ok", encoding="utf-8")
    (tmp_path / "1-2").write_text("bad", encoding="utf-8")

    def parse(path, original_name):
        if original_name == "bad.txt":
            raise RuntimeError("bad source")
        return [{"file_name": original_name, "location": "lines 1", "text": "ok"}]

    monkeypatch.setattr(service, "parse_project_init_file", parse)
    monkeypatch.setattr(service, "generate_project_init_draft", lambda *args: {"tasks": [{"title": "Kept"}], "warnings": []})
    service.process_analysis_run(run_id)

    db.expire_all()
    stored = db.get(models.ProjectInitAnalysisRun, run_id)
    assert stored.status == "partial_failed"
    assert json.loads(stored.current_draft_json)["tasks"][0]["title"] == "Kept"
    assert stored.progress == 100


def test_progress_never_moves_backwards():
    from app.services import project_init_analysis as service

    db = make_session()
    project, _owner = add_project_graph(db)
    run = models.ProjectInitAnalysisRun(project_id=project.id, created_by="owner", progress=70)
    db.add(run)
    db.commit()
    service._set_progress(db, run, stage="parsing", progress=20)
    assert run.progress == 70
    service._set_progress(db, run, stage="matching", progress=80)
    assert run.progress == 80


def test_retry_creates_new_frozen_run_and_completed_run_conflicts():
    from app.routers import project_init_ai

    db = make_session()
    project, _owner = add_project_graph(db)
    db.add(models.Account(username="owner", password_hash="x", person_id=project.id, status="active"))
    attachment = add_attachment(db, project_id=project.id, attachment_id=1)
    db.commit()
    old = models.ProjectInitAnalysisRun(
        project_id=project.id,
        attachment_ids_json="[1]",
        snapshot_json=json.dumps({"current_draft": [], "attachments": [{"id": 1, "storage_key": attachment.storage_key, "original_name": attachment.original_name, "size_bytes": 1}]}),
        status="failed",
        stage="failed",
        created_by="owner",
    )
    db.add(old)
    db.commit()
    old_id = old.id
    scheduled = SimpleNamespace(tasks=[], add_task=lambda fn, run_id: scheduled.tasks.append(run_id))
    retry = project_init_ai.retry_project_init_analysis_run(project.id, old_id, scheduled, current_user="owner", db=db)
    assert retry["id"] != old_id
    assert scheduled.tasks == [retry["id"]]
    assert db.get(models.ProjectInitAnalysisRun, old_id).status == "failed"

    completed = models.ProjectInitAnalysisRun(project_id=project.id, attachment_ids_json="[1]", status="completed", created_by="owner")
    db.add(completed)
    db.commit()
    with pytest.raises(HTTPException) as error:
        project_init_ai.retry_project_init_analysis_run(project.id, completed.id, scheduled, current_user="owner", db=db)
    assert error.value.status_code == 409


def test_stale_processing_is_marked_failed_and_retry_only_allows_failed(monkeypatch):
    from app.services import project_init_analysis as service

    db = make_session()
    project, _owner = add_project_graph(db)
    run = models.ProjectInitAnalysisRun(project_id=project.id, created_by="owner", status="processing", stage="parsing", progress=30)
    db.add(run)
    db.commit()
    run_id = run.id
    run.started_at = utc_now() - timedelta(minutes=31)
    db.commit()

    assert service.recover_stale_run(run) is True
    assert run.status == "failed"
    assert "stale" in run.error_summary.lower()


def test_apply_is_explicitly_rejected_without_business_mutation():
    from app.routers import project_init_ai

    db = make_session()
    project, _owner = add_project_graph(db)
    db.add(models.Account(username="owner", password_hash="x", person_id=project.id, status="active"))
    db.commit()
    task = models.Task(project_id=project.id, key_task="Original", owner="Owner 1")
    db.add(task)
    db.flush()
    run = models.ProjectInitAnalysisRun(project_id=project.id, created_by="owner", status="completed", result_json='{"tasks": [{"title": "AI"}]}')
    db.add(run)
    db.commit()
    run_id = run.id

    with pytest.raises(HTTPException) as error:
        project_init_ai.apply_project_init_analysis_run(project.id, run.id, current_user="owner", db=db)
    assert error.value.status_code == 409
    db.expire_all()
    task_id = task.id
    assert db.get(models.Task, task_id).key_task == "Original"
    assert db.get(models.ProjectInitAnalysisRun, run_id).applied_at is None
