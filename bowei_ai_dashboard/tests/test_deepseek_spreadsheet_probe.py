from __future__ import annotations

from types import SimpleNamespace

from openpyxl import Workbook
import pytest

from app import models
from app.services.deepseek_spreadsheet_probe import (
    ProbeRunner,
    WorkbookEvidence,
    build_text_completion,
    build_vision_completion,
    build_workbook_evidence,
    run_visual_probe,
)


def test_build_workbook_evidence_preserves_cells_and_merged_range(tmp_path):
    path = tmp_path / "推进表.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "工作推进表"
    sheet.merge_cells("A1:B1")
    sheet["A1"] = "知识资产AI化"
    sheet["A2"] = "关键任务"
    sheet["B2"] = "协助人：张三、李四"
    book.save(path)

    evidence = build_workbook_evidence(path, "推进表.xlsx", max_sheets=3, max_cells=100)

    assert evidence.locations == {"'工作推进表'!A1:B1", "'工作推进表'!A2", "'工作推进表'!B2"}
    assert evidence.merged_ranges == {"'工作推进表'!A1:B1": "知识资产AI化"}
    assert "'工作推进表'!B2=协助人：张三、李四" in evidence.text


def test_probe_a_calls_flash_then_pro_and_requires_cited_output():
    calls: list[tuple[str, str]] = []
    response = (
        '{"workstreams":[{"title":"专项","key_tasks":[{"title":"任务",'
        '"collaborators":["张三"],"evidence":["\'表\'!A1"]}]}]}'
    )
    runner = ProbeRunner(
        complete_text=lambda model, prompt: calls.append((model, prompt)) or response
    )

    results = runner.run_text(WorkbookEvidence("'表'!A1=专项", {"'表'!A1"}, {}, "hash"))

    assert [model for model, _prompt in calls] == ["deepseek-v4-flash", "deepseek-v4-pro"]
    assert [item.status for item in results] == ["succeeded", "succeeded"]
    assert "协助人：" in calls[0][1]


def test_probe_a_rejects_unknown_evidence_location():
    response = (
        '{"workstreams":[{"title":"专项","key_tasks":[{"title":"任务",'
        '"evidence":["\'表\'!Z9"]}]}]}'
    )
    runner = ProbeRunner(complete_text=lambda _model, _prompt: response)

    result = runner.run_text(WorkbookEvidence("x", {"'表'!A1"}, {}, "hash"))[0]

    assert result.status == "uncited_output"
    assert result.output is None


def test_build_text_completion_targets_in_memory_model_without_returning_secret():
    captured: dict[str, object] = {}
    credential_model = models.AIModel(
        id=7,
        code="configured-deepseek",
        display_name="Configured DeepSeek",
        provider="deepseek",
        model_name="deepseek-v4-pro",
        model_type="chat",
        base_url="https://api.deepseek.com",
        config_json="{}",
        enabled=True,
    )
    completion = build_text_completion(
        credential_model,
        credential_reader=lambda model_id: captured.setdefault("model_id", model_id) or "secret",
        adapter=lambda model, key, _prompt: captured.update(model=model.model_name, key=key) or "{}",
    )

    assert completion("deepseek-v4-flash", "prompt") == "{}"
    assert captured["model_id"] == 7
    assert captured["model"] == "deepseek-v4-flash"
    assert "secret" not in repr(completion)


def test_probe_b_skips_instead_of_falling_back_to_text_without_renderer(tmp_path):
    result = run_visual_probe(
        tmp_path / "plan.xlsx",
        evidence=WorkbookEvidence("x", {"'表'!A1"}, {}, "hash"),
        build_images=lambda _path, _directory: None,
        complete_vision=lambda _images, _prompt: pytest.fail("vision must not run"),
    )

    assert (result.status, result.reason) == ("skipped", "renderer_unavailable")


def test_probe_b_passes_rendered_images_to_vision_and_validates_citations(tmp_path):
    captured: dict[str, object] = {}
    response = (
        '{"workstreams":[{"title":"专项","key_tasks":[{"title":"任务",'
        '"evidence":["\'表\'!A1"]}]}]}'
    )
    result = run_visual_probe(
        tmp_path / "plan.xlsx",
        evidence=WorkbookEvidence("'表'!A1=专项", {"'表'!A1"}, {}, "hash"),
        build_images=lambda _path, directory: [directory / "sheet-1.png"],
        complete_vision=lambda images, prompt: captured.update(images=images, prompt=prompt) or response,
    )

    assert result.status == "succeeded"
    assert result.model_name == "deepseek-v4-flash-vision-exp"
    assert len(captured["images"]) == 1


def test_build_vision_completion_uploads_png_as_user_data(tmp_path):
    captured: dict[str, object] = {}
    image = tmp_path / "sheet.png"
    image.write_bytes(b"png")

    class FakeFiles:
        def create(self, **kwargs):
            captured["upload"] = kwargs
            return SimpleNamespace(id="file-1")

    class FakeCompletions:
        def create(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

    client = SimpleNamespace(
        files=FakeFiles(),
        chat=SimpleNamespace(completions=FakeCompletions()),
    )
    model = models.AIModel(
        id=7, code="deepseek", display_name="DeepSeek", provider="deepseek",
        model_name="deepseek-v4-pro", model_type="chat", base_url="https://api.deepseek.com",
        config_json="{}", enabled=True,
    )
    completion = build_vision_completion(
        model,
        credential_reader=lambda _model_id: "secret",
        client_factory=lambda **kwargs: captured.update(client=kwargs) or client,
    )

    assert completion([image], "prompt") == "{}"
    assert captured["upload"]["purpose"] == "user_data"
    assert captured["request"]["model"] == "deepseek-v4-flash-vision-exp"
