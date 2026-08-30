from __future__ import annotations

from openpyxl import Workbook

from app.services.deepseek_spreadsheet_probe import (
    ProbeRunner,
    WorkbookEvidence,
    build_workbook_evidence,
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
