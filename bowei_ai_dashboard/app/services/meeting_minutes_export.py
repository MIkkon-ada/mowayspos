"""Generate a formal, readable DOCX record from a saved meeting draft."""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from .. import models


def _json_list(value: str | None) -> list[Any]:
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("content") or value.get("title") or value.get("task") or "").strip()
    return str(value or "").strip()


def _pick(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return "—"


def _action_rows(value: str | None) -> list[tuple[str, str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str, str]] = []
    for index, item in enumerate(_json_list(value), start=1):
        row = item if isinstance(item, dict) else {"task": _text(item)}
        code = _pick(row, "编号", "code", "id")
        rows.append((
            code if code != "—" else f"本周-{index:02d}",
            _pick(row, "会议安排事项", "事项", "task", "title", "content"),
            _pick(row, "负责人", "owner", "member"),
            _pick(row, "追踪人", "tracker"),
            _pick(row, "完成时限", "完成时间", "due_date", "dueDate", "deadline"),
            _pick(row, "来源/备注", "来源", "备注", "source", "note"),
        ))
    return rows


def _set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    tc_pr.append(shading)


def _set_cell_text(cell, text: str, *, bold: bool = False, color: str | None = None) -> None:
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run(text or "—")
    run.bold = bold
    run.font.size = Pt(9.5)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def _add_heading(document: Document, text: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(13)
    paragraph.paragraph_format.space_after = Pt(5)
    run = paragraph.add_run(text)
    run.bold = True
    run.font.size = Pt(12)


def _decision_sections(value: str | None, fallback: str | None) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    for index, item in enumerate(_json_list(value), start=1):
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("heading") or item.get("topic") or f"会议事项 {index}").strip()
            raw_bullets = item.get("bullets") or item.get("points") or item.get("items") or item.get("content")
            bullets = [str(part).strip() for part in raw_bullets] if isinstance(raw_bullets, list) else [_text(raw_bullets)]
        else:
            title, bullets = _text(item), []
        bullets = [bullet for bullet in bullets if bullet]
        if title or bullets:
            sections.append((title, bullets))
    if not sections and (fallback or "").strip():
        sections.append(("会议小结", [(fallback or "").strip()]))
    return sections


def _add_fact_list(document: Document, values: list[Any]) -> None:
    for item in values:
        text = _text(item)
        if text:
            paragraph = document.add_paragraph(style="List Bullet")
            paragraph.paragraph_format.space_after = Pt(3)
            paragraph.add_run(text).font.size = Pt(10.5)


def _configure_document(document: Document) -> None:
    section = document.sections[0]
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2.4)
    section.right_margin = Cm(2.4)
    normal = document.styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(10.5)


def _add_metadata_table(document: Document, meeting: models.Meeting) -> None:
    table = document.add_table(rows=0, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    for label, value in (
        ("所属项目", meeting.related_special_project or "—"),
        ("会议时间", meeting.meeting_date or "—"),
        ("会议地点", meeting.location or "—"),
        ("会议类型", meeting.meeting_type or "—"),
        ("会议主持人", meeting.host or "—"),
        ("与会者", meeting.participants or "—"),
    ):
        cells = table.add_row().cells
        _set_cell_text(cells[0], label, bold=True, color="1F4E79")
        _set_cell_text(cells[1], value)
        _set_cell_shading(cells[0], "EAF2F8")


def _add_action_table(document: Document, rows: list[tuple[str, str, str, str, str, str]]) -> None:
    table = document.add_table(rows=1, cols=6)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    headers = ["编号", "会议安排事项", "负责人", "追踪人", "完成时限", "来源/备注"]
    for cell, label in zip(table.rows[0].cells, headers):
        _set_cell_text(cell, label, bold=True, color="FFFFFF")
        _set_cell_shading(cell, "1F4E79")
    for values in rows or [("—", "暂无明确待办事项", "—", "—", "—", "—")]:
        for cell, value in zip(table.add_row().cells, values):
            _set_cell_text(cell, value)


def build_meeting_minutes_docx(meeting: models.Meeting, *, source_name: str = "") -> bytes:
    """Produce the published minutes; source_name is retained for API compatibility."""
    document = Document()
    _configure_document(document)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(3)
    run = title.add_run(meeting.title or "项目会议纪要")
    run.bold = True
    run.font.size = Pt(18)
    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(2)
    subtitle.add_run(f"（{meeting.meeting_date or '日期待补充'}）").font.size = Pt(10.5)
    confidentiality = document.add_paragraph()
    confidentiality.alignment = WD_ALIGN_PARAGRAPH.CENTER
    confidentiality.paragraph_format.space_after = Pt(12)
    confidentiality.add_run("内部留档 · 不对外发送").font.size = Pt(9)

    _add_metadata_table(document, meeting)
    _add_heading(document, "一、会议议程")
    agenda_items = _json_list(meeting.agenda_items_json)
    if agenda_items:
        for index, item in enumerate(agenda_items, start=1):
            text = _text(item)
            if text:
                document.add_paragraph(f"{index}. {text}")
    else:
        document.add_paragraph("暂无明确会议议程")

    _add_heading(document, "二、会议小结与决议")
    sections = _decision_sections(meeting.decision_items_json, meeting.summary)
    for index, (section_title, bullets) in enumerate(sections, start=1):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(5)
        heading = paragraph.add_run(f"（{'一二三四五六七八九十'[index - 1] if index <= 10 else index}）{section_title}")
        heading.bold = True
        heading.font.size = Pt(10.5)
        _add_fact_list(document, bullets)
    if not sections:
        document.add_paragraph("暂无会议小结与决议")

    _add_heading(document, "三、待办事项跟踪")
    _add_action_table(document, _action_rows(meeting.task_list_json))
    risks = _json_list(meeting.risk_items_json)
    if risks:
        _add_heading(document, "四、风险与待确认")
        _add_fact_list(document, risks)

    footer = document.add_table(rows=1, cols=4)
    footer.alignment = WD_TABLE_ALIGNMENT.CENTER
    footer.style = "Table Grid"
    for cell, value, bold in zip(footer.rows[0].cells, ("整理人", meeting.organizer or "—", "抄送", meeting.copied_to or "—"), (True, False, True, False)):
        _set_cell_text(cell, value, bold=bold, color="1F4E79" if bold else None)
        if bold:
            _set_cell_shading(cell, "EAF2F8")

    output = BytesIO()
    document.save(output)
    return output.getvalue()
