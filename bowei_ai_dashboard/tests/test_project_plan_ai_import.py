from __future__ import annotations

import json
import asyncio
from io import BytesIO

import pytest
from openpyxl import Workbook

from app.ai.contracts import AICapabilityNotConfigured
from app import models, schemas
from tests.test_project_permission_characterization import _seed
from app.services.project_init_file_parser import parse_project_init_file
from app.services import project_plan_ai_import
from app.services.project_plan_ai_import import analyze_project_plan_upload, draft_to_batch_rows
from starlette.datastructures import UploadFile
from app.services.project_init_ai_agent import (
    AgentSubTask,
    AgentTask,
    Evidence,
    ProjectInitAiResult,
    ProjectProfileDraft,
)


def test_csv_and_tsv_are_supported_by_the_shared_source_parser(tmp_path):
    csv_path = tmp_path / "plan.csv"
    csv_path.write_text("主要工作,关键任务\n工作A,任务A\n", encoding="utf-8")
    tsv_path = tmp_path / "plan.tsv"
    tsv_path.write_text("主要工作\t关键任务\n工作A\t任务A\n", encoding="utf-8")

    csv_chunks = parse_project_init_file(csv_path, csv_path.name)
    tsv_chunks = parse_project_init_file(tsv_path, tsv_path.name)

    assert csv_chunks[0].text.startswith("主要工作,关键任务")
    assert tsv_chunks[0].text.startswith("主要工作\t关键任务")


def test_ai_draft_to_batch_rows_preserves_hierarchy_and_evidence():
    evidence = Evidence(
        attachment_id=None,
        file_name="计划.xlsx",
        location="'复制推广'!A2:E3",
        excerpt="工作A",
    )
    draft = ProjectInitAiResult(
        project_profile=ProjectProfileDraft(
            name="项目A",
            objectives="完成目标",
            evidence=[evidence],
        ),
        tasks=[
            AgentTask(
                title="工作A",
                goal="形成成果",
                acceptance_criteria="通过验收",
                process="梳理→试运行",
                evidence=[evidence],
                subtasks=[
                    AgentSubTask(title="任务A1", evidence=[evidence]),
                    AgentSubTask(title="任务A2", evidence=[evidence]),
                    AgentSubTask(title="任务A3", evidence=[evidence]),
                ],
            )
        ],
        provider="project.init.analysis",
        model_name="test-model",
    )

    rows = draft_to_batch_rows(draft)

    assert [row.project_name for row in rows] == ["项目A", "项目A", "项目A"]
    assert [row.workstream for row in rows] == ["工作A", "工作A", "工作A"]
    assert [row.key_task for row in rows] == ["任务A1", "任务A2", "任务A3"]
    assert all(row.key_achievement == "形成成果" for row in rows)
    assert all(row.completion_standard == "通过验收" for row in rows)
    assert all("复制推广" in row.notes for row in rows)


def test_ai_draft_to_batch_rows_rejects_missing_project_or_task():
    draft = ProjectInitAiResult(
        project_profile=ProjectProfileDraft(name=""),
        tasks=[AgentTask(title="工作", subtasks=[AgentSubTask(title="任务")])],
    )

    with pytest.raises(ValueError, match="项目"):
        draft_to_batch_rows(draft)


def _work_plan_xlsx(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "复制推广"
    sheet.append(["第三阶段五项工作的简要方案"])
    sheet.append(["主要工作", "目标", "验收标准与关键成果", "关键任务", "推进流程"])
    sheet.append(["工作A", "形成成果", "通过验收", "1.任务A1\n2.任务A2", "梳理→试运行"])
    path = tmp_path / "plan.xlsx"
    workbook.save(path)
    return path


def _fake_draft() -> ProjectInitAiResult:
    evidence = Evidence(file_name="plan.xlsx", location="'复制推广'!A3:E3", excerpt="工作A")
    return ProjectInitAiResult(
        project_profile=ProjectProfileDraft(name="AI项目", objectives="形成成果", evidence=[evidence]),
        tasks=[
            AgentTask(
                title="工作A",
                goal="形成成果",
                acceptance_criteria="通过验收",
                process="梳理→试运行",
                evidence=[evidence],
                subtasks=[AgentSubTask(title="任务A1", evidence=[evidence])],
            )
        ],
        provider="project.init.analysis",
        model_name="test-model",
    )


def test_ai_preview_is_review_only_and_uses_existing_ai_pipeline(tmp_path, monkeypatch):
    db = _seed()
    source = _work_plan_xlsx(tmp_path)
    captured = {}

    def fake_generate(chunks, people, existing_tasks, *, ai_service, invocation_context):
        captured["chunks"] = list(chunks)
        captured["context"] = invocation_context
        return _fake_draft()

    monkeypatch.setattr(project_plan_ai_import, "generate_project_init_draft", fake_generate)
    monkeypatch.setattr(project_plan_ai_import, "AIService", lambda _db: object())

    preview = analyze_project_plan_upload(
        db,
        source.read_bytes(),
        source.name,
        actor="admin",
    )

    assert preview.result.project_profile.name == "AI项目"
    assert preview.fallback_mode == "ai"
    assert preview.source_files == ("plan.xlsx",)
    assert captured["context"].resource_type == "project_plan_import"
    assert db.query(models.Project).count() == 1
    db.close()


def test_ai_preview_uses_deterministic_fallback_when_ai_is_unavailable(tmp_path, monkeypatch):
    db = _seed()
    source = _work_plan_xlsx(tmp_path)

    def unavailable(*_args, **_kwargs):
        raise AICapabilityNotConfigured("not configured")

    monkeypatch.setattr(project_plan_ai_import, "generate_project_init_draft", unavailable)
    monkeypatch.setattr(
        project_plan_ai_import,
        "generate_structured_project_init_draft",
        lambda *_args, **_kwargs: _fake_draft(),
    )
    monkeypatch.setattr(project_plan_ai_import, "AIService", lambda _db: object())

    preview = analyze_project_plan_upload(db, source.read_bytes(), source.name, actor="admin")

    assert preview.fallback_mode == "deterministic"
    assert preview.result.tasks[0].title == "工作A"
    db.close()


def test_preview_route_is_review_only(monkeypatch):
    from app.routers import project_plan_ai_import as router

    db = _seed()
    monkeypatch.setattr(router, "authorize_global_project_action", lambda *_args: None)
    monkeypatch.setattr(
        router,
        "analyze_project_plan_upload",
        lambda *_args, **_kwargs: project_plan_ai_import.ProjectPlanAiImportDraft(
            result=_fake_draft(),
            fallback_mode="ai",
            source_files=("plan.xlsx",),
        ),
    )

    response = asyncio.run(
        router.preview_ai_work_plan(
            file=UploadFile(filename="plan.xlsx", file=BytesIO(b"xlsx")),
            project_name="",
            target_project_id=None,
            current_user="admin",
            db=db,
        )
    )

    assert response["fallback_mode"] == "ai"
    assert response["source_files"] == ["plan.xlsx"]
    assert db.query(models.Project).count() == 1
    db.close()


def test_apply_route_delegates_only_after_confirmation(monkeypatch):
    from app.routers import project_plan_ai_import as router

    db = _seed()
    captured = {}
    monkeypatch.setattr(router, "authorize_global_project_action", lambda *_args: None)
    monkeypatch.setattr(
        router,
        "import_project_plan_rows",
        lambda _db, rows, actor: captured.update(rows=rows, actor=actor) or {"ok": True},
    )

    payload = schemas.ProjectBatchImportPayload(
        rows=[schemas.BatchImportRow(project_name="项目A", workstream="工作A", key_task="任务A")]
    )
    response = router.apply_ai_work_plan(payload=payload, current_user="admin", db=db)

    assert response == {"ok": True}
    assert captured["actor"] == "admin"
    assert captured["rows"][0].key_task == "任务A"
    db.close()
