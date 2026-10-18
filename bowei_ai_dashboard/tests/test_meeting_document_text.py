from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

import pytest

from app.services.meeting_document_text import MeetingDocumentTextError, extract_meeting_document_text


def _docx_with_paragraphs(*paragraphs: str) -> bytes:
    body = "".join(
        f'<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>' for paragraph in paragraphs
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{body}</w:body></w:document>'
    )
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    return output.getvalue()


def _docx_with_body(body: str) -> bytes:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{body}</w:body></w:document>'
    )
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    return output.getvalue()


def test_extracts_utf8_text_document():
    assert extract_meeting_document_text("minutes.txt", "会议结论：下周交付。".encode()) == "会议结论：下周交付。"


def test_extracts_word_paragraphs_in_order():
    content = _docx_with_paragraphs("一、会议议程", "确认交付安排")

    assert extract_meeting_document_text("minutes.docx", content) == "一、会议议程\n确认交付安排"


def test_extracts_word_table_rows_without_losing_cell_relationships():
    content = _docx_with_body(
        '<w:p><w:r><w:t>会议决定</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>第一页结束</w:t><w:br w:type="page"/><w:lastRenderedPageBreak/><w:t>第二页开始</w:t></w:r></w:p>'
        '<w:tbl>'
        '<w:tr><w:tc><w:p><w:r><w:t>事项</w:t></w:r></w:p></w:tc>'
        '<w:tc><w:p><w:r><w:t>负责人</w:t></w:r></w:p></w:tc></w:tr>'
        '<w:tr><w:tc><w:p><w:r><w:t>截止日期</w:t></w:r></w:p></w:tc>'
        '<w:tc><w:p><w:r><w:t>10月18日</w:t></w:r></w:p></w:tc></w:tr>'
        '</w:tbl>'
    )

    assert extract_meeting_document_text("minutes.docx", content) == (
        "会议决定\n第一页结束\f第二页开始\n事项\t负责人\n截止日期\t10月18日"
    )


def test_extracts_excel_cells_for_skill_reference_material():
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Project A</t></is></c></row>'
        '<row r="2"><c r="A2" t="inlineStr"><is><t>received</t></is></c></row></sheetData></worksheet>'
    )
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    assert extract_meeting_document_text("ledger.xlsx", output.getvalue()) == "Project A\nreceived"


def test_rejects_pdf_documents():
    with pytest.raises(MeetingDocumentTextError, match="Word、TXT、Excel"):
        extract_meeting_document_text("minutes.pdf", b"%PDF")
