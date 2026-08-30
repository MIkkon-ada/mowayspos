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


def test_analysis_run_response_labels_legacy_snapshot_without_model_strategy():
    from app.routers import project_init_ai

    run = models.ProjectInitAnalysisRun(
        project_id=1,
        attachment_ids_json="[]",
        current_draft_json="{}",
        result_json="{}",
        file_results_json="[]",
        snapshot_json=json.dumps({"attachments": []}),
    )

    response = project_init_ai._analysis_run_response(run)

    assert response["result_metadata"]["model_strategy_status"] == "historical_unavailable"


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
    monkeypatch.setattr(service, "AIService", lambda _db: object())
    monkeypatch.setattr(service, "parse_project_init_file", lambda path, original_name=None: [{"file_name": "source-1.txt", "location": "lines 1", "text": "Frozen source", "attachment_id": 1}])
    monkeypatch.setattr(service, "generate_project_init_draft", lambda chunks, people, tasks, **_kwargs: SimpleNamespace(model_dump=lambda: {"tasks": [{"title": "Draft task"}], "warnings": []}, tasks=[SimpleNamespace()]))
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


def test_worker_records_complex_workbook_review_requirement(monkeypatch, tmp_path):
    from app.services import project_init_analysis as service

    db = make_session()
    project, _owner = add_project_graph(db)
    attachment = add_attachment(db, project_id=project.id, attachment_id=1)
    attachment.original_name = "complex.xlsx"
    run = models.ProjectInitAnalysisRun(
        project_id=project.id,
        attachment_ids_json="[1]",
        snapshot_json=json.dumps({
            "project": {},
            "tasks": [],
            "people": [],
            "attachments": [
                {"id": 1, "storage_key": "1/1", "original_name": "complex.xlsx", "size_bytes": 10},
            ],
        }),
        created_by="owner",
    )
    db.add(run)
    db.commit()
    run_id = run.id
    source_path = tmp_path / "complex.xlsx"
    source_path.write_bytes(b"placeholder")
    monkeypatch.setattr(service, "SessionLocal", lambda: db)
    monkeypatch.setattr(service, "_attachment_path", lambda _key: source_path)
    monkeypatch.setattr(service, "parse_project_init_file", lambda *_args: [{"file_name": "complex.xlsx", "location": "Sheet1!A1", "text": "task"}])
    monkeypatch.setattr(service, "profile_project_init_workbook", lambda *_args: {
        "risk_level": "high",
        "signals": ["hidden_sheets", "merged_cells"],
        "summary": {"worksheet_count": 2},
    })
    monkeypatch.setattr(service, "AIService", lambda _db: object())
    monkeypatch.setattr(service, "generate_project_init_draft", lambda *_args, **_kwargs: {"tasks": [{"title": "Draft"}], "warnings": []})

    service.process_analysis_run(run_id)

    db.expire_all()
    stored = db.get(models.ProjectInitAnalysisRun, run_id)
    result = json.loads(stored.result_json)
    file_result = json.loads(stored.file_results_json)[0]
    assert result["analysis_route"] == {
        "mode": "text_with_review",
        "review_required": True,
        "reason_codes": ["complex_workbook_layout"],
    }
    assert file_result["workbook_profile"] == {
        "risk_level": "high",
        "signals": ["hidden_sheets", "merged_cells"],
        "summary": {"worksheet_count": 2},
    }


def test_worker_uses_vision_for_high_risk_non_tabular_workbook_and_cleans_images(monkeypatch, tmp_path):
    from app.services import project_init_analysis as service

    db = make_session()
    project, _owner = add_project_graph(db)
    attachment = add_attachment(db, project_id=project.id, attachment_id=1)
    attachment.original_name = "复杂表.xlsx"
    run = models.ProjectInitAnalysisRun(
        project_id=project.id,
        attachment_ids_json="[1]",
        snapshot_json=json.dumps({
            "project": {}, "tasks": [], "people": [],
            "attachments": [{"id": 1, "storage_key": "1/1", "original_name": "复杂表.xlsx", "size_bytes": 10}],
        }),
        created_by="owner",
    )
    db.add(run)
    db.commit()
    run_id = run.id
    source_path = tmp_path / "复杂表.xlsx"
    source_path.write_bytes(b"placeholder")
    rendered_directories = []

    def render(_path, output_directory):
        rendered_directories.append(output_directory)
        output_directory.mkdir(parents=True, exist_ok=True)
        image = output_directory / "sheet.png"
        image.write_bytes(b"png")
        return [image]

    monkeypatch.setattr(service, "SessionLocal", lambda: db)
    monkeypatch.setattr(service, "_attachment_path", lambda _key: source_path)
    monkeypatch.setattr(service, "parse_project_init_file", lambda *_args: [{"file_name": "复杂表.xlsx", "location": "'推进表'!A1:J30", "text": "复杂布局"}])
    monkeypatch.setattr(service, "profile_project_init_workbook", lambda *_args: {"risk_level": "high", "signals": ["merged_cells"], "summary": {}})
    monkeypatch.setattr(service, "render_workbook_images", render)
    monkeypatch.setattr(service, "AIService", lambda _db: object())
    monkeypatch.setattr(service, "generate_project_init_vision_draft", lambda *_args, **_kwargs: {"tasks": [{"title": "视觉任务"}], "warnings": []})
    monkeypatch.setattr(service, "generate_project_init_draft", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("text route should not run")))

    service.process_analysis_run(run_id)

    db.expire_all()
    stored = db.get(models.ProjectInitAnalysisRun, run_id)
    assert json.loads(stored.result_json)["analysis_route"]["mode"] == "vision_with_review"
    assert json.loads(stored.current_draft_json)["tasks"][0]["title"] == "视觉任务"
    assert rendered_directories and not rendered_directories[0].exists()


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
    monkeypatch.setattr(service, "AIService", lambda _db: object())
    monkeypatch.setattr(service, "parse_project_init_file", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("secret-api-key prompt body")))
    monkeypatch.setattr(service, "_attachment_path", lambda row: tmp_path / "source-1.txt")

    service.process_analysis_run(run_id)
    db.expire_all()
    stored = db.get(models.ProjectInitAnalysisRun, run_id)
    assert stored.status == "failed"
    assert "secret-api-key" not in stored.error_summary
    assert "prompt body" not in stored.error_summary


def test_worker_records_invalid_draft_schema_without_leaking_details(monkeypatch, tmp_path):
    from app.services import project_init_analysis as service
    from app.services.project_init_ai_agent import ProjectInitAiInvalidDraft

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
    (tmp_path / "source-1.txt").write_text("source", encoding="utf-8")
    monkeypatch.setattr(service, "SessionLocal", lambda: db)
    monkeypatch.setattr(service, "AIService", lambda _db: object())
    monkeypatch.setattr(
        service,
        "parse_project_init_file",
        lambda *args, **kwargs: [{"file_name": "source-1.txt", "location": "lines 1", "text": "source"}],
    )
    monkeypatch.setattr(service, "_attachment_path", lambda row: tmp_path / "source-1.txt")
    monkeypatch.setattr(
        service,
        "generate_project_init_draft",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ProjectInitAiInvalidDraft(
                "invalid model response",
                validation_errors=[
                    {"path": "tasks[0].evidence[0].attachment_id", "type": "int_type"}
                ],
            )
        ),
    )

    service.process_analysis_run(run_id)
    db.expire_all()
    stored = db.get(models.ProjectInitAnalysisRun, run_id)
    result = json.loads(stored.result_json)

    assert result["failure_category"] == "invalid_draft_schema"
    assert result["validation_errors"] == [
        {"path": "tasks[0].evidence[0].attachment_id", "type": "int_type"}
    ]
    assert stored.error_summary == "AI analysis failed; please retry later"
    assert "invalid model response" not in stored.result_json


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
    monkeypatch.setattr(service, "AIService", lambda _db: object())
    monkeypatch.setattr(service, "generate_project_init_draft", lambda *args, **_kwargs: {"tasks": [{"title": "Kept"}], "warnings": []})
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
    run = models.ProjectInitAnalysisRun(project_id=project.id, created_by="owner", status="processing", progress=70)
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
    run.updated_at = utc_now() - timedelta(minutes=31)
    db.commit()

    assert service.recover_stale_run(run) is True
    assert run.status == "failed"
    assert "stale" in run.error_summary.lower()


def test_apply_only_records_audit_without_business_mutation():
    from app.routers import project_init_ai

    db = make_session()
    project, _owner = add_project_graph(db)
    db.add(models.Account(username="owner", password_hash="x", person_id=project.id, status="active"))
    project.status = "pending_review"
    db.commit()
    task = models.Task(project_id=project.id, key_task="Original", owner="Owner 1")
    db.add(task)
    db.flush()
    run = models.ProjectInitAnalysisRun(project_id=project.id, created_by="owner", status="completed", result_json='{"tasks": [{"title": "AI"}]}')
    db.add(run)
    db.commit()
    run_id = run.id

    response = project_init_ai.apply_project_init_analysis_run(project.id, run.id, current_user="owner", db=db)
    assert response["applied_at"] is not None
    response_again = project_init_ai.apply_project_init_analysis_run(project.id, run.id, current_user="owner", db=db)
    assert response_again["applied_at"] == response["applied_at"]
    fetched = project_init_ai.get_project_init_analysis_run(project.id, run.id, current_user="owner", db=db)
    latest = project_init_ai.latest_project_init_analysis_run(project.id, current_user="owner", db=db)
    assert fetched["applied_at"] == response["applied_at"]
    assert latest["applied_at"] == response["applied_at"]
    db.expire_all()
    task_id = task.id
    assert db.get(models.Task, task_id).key_task == "Original"
    assert db.get(models.ProjectInitAnalysisRun, run_id).applied_at is not None


def test_apply_after_owner_submit_pending_review_records_audit_without_business_mutation():
    from app.routers import project_init_ai, projects

    db = make_session()
    project, owner = add_project_graph(db)
    db.add(models.Account(username="owner", password_hash="x", person_id=owner.id, status="active"))
    db.commit()

    submit_payload = schemas.ProjectProfilePayload(
        background="Submitted background",
        work_progress_draft=[
            schemas.ProjectWorkProgressTaskDraft(
                title="Submitted task",
                subtasks=[
                    schemas.ProjectWorkProgressSubTaskDraft(
                        title="Submitted subtask",
                        assignee_id=owner.id,
                    )
                ],
            )
        ],
    )
    submitted = projects.owner_submit_project_profile(
        project.id,
        submit_payload,
        current_user="owner",
        db=db,
    )
    assert submitted["submitted_for_review"] is True
    assert db.get(models.Project, project.id).status == "pending_review"

    task_rows_before = [
        (row.id, row.key_task, row.completion_standard, row.owner, row.edit_count)
        for row in db.query(models.Task).filter(models.Task.project_id == project.id).all()
    ]
    subtask_rows_before = [
        (row.id, row.task_id, row.title, row.assignee_id)
        for row in db.query(models.SubTask)
        .join(models.Task, models.SubTask.task_id == models.Task.id)
        .filter(models.Task.project_id == project.id)
        .all()
    ]
    run = models.ProjectInitAnalysisRun(
        project_id=project.id,
        created_by="owner",
        status="completed",
        result_json='{"tasks": [{"title": "AI suggestion"}]}',
    )
    db.add(run)
    db.commit()

    response = project_init_ai.apply_project_init_analysis_run(
        project.id,
        run.id,
        current_user="owner",
        db=db,
    )

    assert response["applied_at"] is not None
    assert db.get(models.Project, project.id).status == "pending_review"
    assert [
        (row.id, row.key_task, row.completion_standard, row.owner, row.edit_count)
        for row in db.query(models.Task).filter(models.Task.project_id == project.id).all()
    ] == task_rows_before
    assert [
        (row.id, row.task_id, row.title, row.assignee_id)
        for row in db.query(models.SubTask)
        .join(models.Task, models.SubTask.task_id == models.Task.id)
        .filter(models.Task.project_id == project.id)
        .all()
    ] == subtask_rows_before

    latest = project_init_ai.latest_project_init_analysis_run(
        project.id,
        current_user="owner",
        db=db,
    )
    fetched = project_init_ai.get_project_init_analysis_run(
        project.id,
        run.id,
        current_user="owner",
        db=db,
    )
    assert latest["id"] == run.id
    assert fetched["applied_at"] == response["applied_at"]


@pytest.mark.parametrize("lifecycle", ["dispatched", "returned"])
@pytest.mark.parametrize("actor", ["owner", "project-ceo"])
def test_apply_completed_run_requires_pending_review_after_submit(lifecycle, actor):
    from app.routers import project_init_ai

    db = make_session()
    project, owner = add_project_graph(db)
    manager = models.Person(id=20, name="Project CEO", is_active=True)
    db.add_all(
        [
            manager,
            models.ProjectMember(project_id=project.id, person_id=manager.id, role="project_ceo"),
            models.Account(username="owner", password_hash="x", person_id=owner.id, status="active"),
            models.Account(username="project-ceo", password_hash="x", person_id=manager.id, status="active"),
        ]
    )
    project.status = lifecycle
    run = models.ProjectInitAnalysisRun(project_id=project.id, created_by="owner", status="completed")
    db.add(run)
    db.commit()

    with pytest.raises(HTTPException) as error:
        project_init_ai.apply_project_init_analysis_run(
            project.id,
            run.id,
            current_user=actor,
            db=db,
        )
    assert error.value.status_code == 409
    assert db.get(models.ProjectInitAnalysisRun, run.id).applied_at is None

    latest = project_init_ai.latest_project_init_analysis_run(
        project.id,
        current_user=actor,
        db=db,
    )
    fetched = project_init_ai.get_project_init_analysis_run(
        project.id,
        run.id,
        current_user=actor,
        db=db,
    )
    assert latest["id"] == run.id
    assert fetched["id"] == run.id


def test_apply_pending_review_denies_ordinary_member_with_403():
    from app.routers import project_init_ai

    db = make_session()
    project, owner = add_project_graph(db)
    member = models.Person(id=20, name="Ordinary Member", is_active=True)
    db.add_all(
        [
            member,
            models.ProjectMember(project_id=project.id, person_id=member.id, role="member"),
            models.Account(username="owner", password_hash="x", person_id=owner.id, status="active"),
            models.Account(username="member", password_hash="x", person_id=member.id, status="active"),
        ]
    )
    project.status = "pending_review"
    run = models.ProjectInitAnalysisRun(project_id=project.id, created_by="owner", status="completed")
    db.add(run)
    db.commit()

    with pytest.raises(HTTPException) as error:
        project_init_ai.apply_project_init_analysis_run(
            project.id,
            run.id,
            current_user="member",
            db=db,
        )
    assert error.value.status_code == 403


@pytest.mark.parametrize("run_status", ["completed", "partial_failed"])
def test_apply_pending_review_accepts_terminal_runs_idempotently(run_status):
    from app.routers import project_init_ai

    db = make_session()
    project, owner = add_project_graph(db)
    db.add(models.Account(username="owner", password_hash="x", person_id=owner.id, status="active"))
    project.status = "pending_review"
    run = models.ProjectInitAnalysisRun(project_id=project.id, created_by="owner", status=run_status)
    db.add(run)
    db.commit()

    response = project_init_ai.apply_project_init_analysis_run(
        project.id,
        run.id,
        current_user="owner",
        db=db,
    )
    repeated = project_init_ai.apply_project_init_analysis_run(
        project.id,
        run.id,
        current_user="owner",
        db=db,
    )
    assert response["applied_at"] is not None
    assert repeated["applied_at"] == response["applied_at"]
    assert db.get(models.Project, project.id).status == "pending_review"


@pytest.mark.parametrize("status", ["queued", "processing", "failed"])
def test_apply_pending_review_rejects_non_terminal_runs(status):
    from app.routers import project_init_ai

    db = make_session()
    project, owner = add_project_graph(db)
    db.add(models.Account(username="owner", password_hash="x", person_id=owner.id, status="active"))
    project.status = "pending_review"
    run = models.ProjectInitAnalysisRun(project_id=project.id, created_by="owner", status=status)
    db.add(run)
    db.commit()

    with pytest.raises(HTTPException) as error:
        project_init_ai.apply_project_init_analysis_run(
            project.id,
            run.id,
            current_user="owner",
            db=db,
        )
    assert error.value.status_code == 409
    assert error.value.detail == f"analysis run status {status} cannot be applied"


def test_atomic_worker_claim_and_stale_lease_cannot_be_revived(tmp_path):
    from app.services import project_init_analysis as service

    database_url = f"sqlite:///{tmp_path / 'analysis-race.db'}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    first, second = sessions(), sessions()
    project = models.Project(id=1, name="Race", status="dispatched")
    first.add(project)
    first.add(models.ProjectInitAnalysisRun(project_id=1, created_by="owner", status="queued"))
    first.commit()
    run_id = first.query(models.ProjectInitAnalysisRun).one().id

    assert service._claim_run(first, run_id) is True
    assert service._claim_run(second, run_id) is False

    stale = utc_now() - timedelta(minutes=31)
    second.query(models.ProjectInitAnalysisRun).filter_by(id=run_id).update(
        {models.ProjectInitAnalysisRun.updated_at: stale}, synchronize_session=False
    )
    second.commit()
    assert service.recover_stale_runs(second, 1) == 1
    assert service._update_processing(first, run_id, stage="matching", progress=80) is False
    assert first.get(models.ProjectInitAnalysisRun, run_id).status == "failed"
    first.close()
    second.close()


def test_retry_unique_link_deduplicates_across_sessions_and_uses_frozen_snapshot(tmp_path, monkeypatch):
    from app.routers import project_init_ai

    database_url = f"sqlite:///{tmp_path / 'retry-race.db'}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    seed = sessions()
    project = models.Project(id=1, name="Retry", status="dispatched")
    snapshot = {
        "project": {"id": 1, "status": "dispatched"},
        "attachments": [{"id": 99, "storage_key": "1/frozen", "original_name": "frozen.txt", "size_bytes": 1}],
        "current_draft": [],
    }
    old = models.ProjectInitAnalysisRun(
        project_id=1,
        attachment_ids_json="[99]",
        snapshot_json=json.dumps(snapshot),
        status="failed",
        created_by="owner",
    )
    seed.add_all([project, old])
    seed.commit()
    old_id = old.id
    seed.close()
    monkeypatch.setattr(project_init_ai, "_authorize_edit", lambda *args: None)
    monkeypatch.setattr(project_init_ai, "get_user_context_from_db", lambda *args: {"person_id": None})
    first, second = sessions(), sessions()
    first_old = first.get(models.ProjectInitAnalysisRun, old_id)
    second_old = second.get(models.ProjectInitAnalysisRun, old_id)
    background_one = SimpleNamespace(tasks=[], add_task=lambda fn, run_id: background_one.tasks.append(run_id))
    background_two = SimpleNamespace(tasks=[], add_task=lambda fn, run_id: background_two.tasks.append(run_id))
    result_one = project_init_ai._create_retry_from_frozen_snapshot(1, first_old, "owner", first, background_one)
    result_two = project_init_ai._create_retry_from_frozen_snapshot(1, second_old, "owner", second, background_two)
    assert result_one["id"] == result_two["id"]
    retry = first.get(models.ProjectInitAnalysisRun, result_one["id"])
    assert json.loads(retry.snapshot_json) == snapshot
    assert background_one.tasks == [retry.id]
    assert background_two.tasks == []
    first.close()
    second.close()


def test_project_manager_can_create_retry_apply_and_ordinary_member_is_denied():
    from app.routers import project_init_ai

    db = make_session()
    project, _owner = add_project_graph(db)
    manager = models.Person(id=20, name="Project CEO", is_active=True)
    member = models.Person(id=21, name="Ordinary Member", is_active=True)
    db.add_all([
        manager,
        member,
        models.ProjectMember(project_id=project.id, person_id=manager.id, role="project_ceo"),
        models.ProjectMember(project_id=project.id, person_id=member.id, role="member"),
        models.Account(username="project-ceo", password_hash="x", person_id=manager.id, status="active"),
        models.Account(username="member", password_hash="x", person_id=member.id, status="active"),
    ])
    attachment = add_attachment(db, project_id=project.id, attachment_id=77)
    old = models.ProjectInitAnalysisRun(
        project_id=project.id,
        attachment_ids_json="[77]",
        snapshot_json=json.dumps({
            "project": {"id": project.id, "status": "dispatched"},
            "attachments": [{"id": 77, "storage_key": attachment.storage_key, "original_name": attachment.original_name, "size_bytes": 1}],
            "current_draft": [],
        }),
        status="failed",
        created_by="project-ceo",
    )
    completed = models.ProjectInitAnalysisRun(project_id=project.id, status="completed", created_by="project-ceo")
    db.add_all([old, completed])
    db.commit()

    background = SimpleNamespace(tasks=[], add_task=lambda fn, run_id: background.tasks.append(run_id))
    created = project_init_ai.create_project_init_analysis_run(
        project_id=project.id,
        payload=schemas.ProjectInitAnalysisCreate(attachment_ids=[77], current_draft=[]),
        background_tasks=background,
        current_user="project-ceo",
        db=db,
    )
    assert created["status"] == "queued"
    retry = project_init_ai.retry_project_init_analysis_run(
        project.id,
        old.id,
        background,
        current_user="project-ceo",
        db=db,
    )
    assert retry["status"] == "queued"
    project.status = "pending_review"
    db.commit()
    applied = project_init_ai.apply_project_init_analysis_run(
        project.id,
        completed.id,
        current_user="project-ceo",
        db=db,
    )
    assert applied["applied_at"] is not None
    project.status = "dispatched"
    db.commit()
    project_init_ai.delete_init_attachment(project.id, attachment.id, current_user="project-ceo", db=db)
    assert db.get(models.ProjectInitAttachment, attachment.id).deleted_at is not None

    with pytest.raises(HTTPException) as denied:
        project_init_ai.create_project_init_analysis_run(
            project_id=project.id,
            payload=schemas.ProjectInitAnalysisCreate(attachment_ids=[77], current_draft=[]),
            background_tasks=background,
            current_user="member",
            db=db,
        )
    assert denied.value.status_code == 403
