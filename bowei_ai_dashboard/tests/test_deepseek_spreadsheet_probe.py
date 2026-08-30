from __future__ import annotations

from openpyxl import Workbook

from app.services.deepseek_spreadsheet_probe import build_workbook_evidence


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
