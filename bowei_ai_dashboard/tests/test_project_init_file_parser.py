from __future__ import annotations

import subprocess
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest
from docx import Document
from openpyxl import Workbook

from app.services import project_init_file_parser as parser
from app.services.project_init_file_parser import (
    ProjectInitFileParseError,
    SourceChunk,
    UnsupportedProjectInitFile,
    parse_project_init_file,
)


def test_source_chunk_exposes_source_label_and_is_frozen():
    chunk = SourceChunk("需求.txt", "第 1-2 行", "第一行\n第二行")

    assert chunk.source_label == "需求.txt · 第 1-2 行"
    with pytest.raises(FrozenInstanceError):
        chunk.text = "changed"


def test_txt_utf8_bom_preserves_text_and_eighty_line_ranges(tmp_path):
    lines = [f"第 {index} 行" for index in range(1, 82)]
    path = tmp_path / "upload.txt"
    path.write_bytes("\n".join(lines).encode("utf-8-sig"))

    chunks = parse_project_init_file(path, "原始说明.txt")

    assert chunks == [
        SourceChunk("原始说明.txt", "第 1-80 行", "\n".join(lines[:80])),
        SourceChunk("原始说明.txt", "第 81-81 行", lines[80]),
    ]


def test_txt_falls_back_to_gb18030(tmp_path):
    path = tmp_path / "legacy.txt"
    path.write_bytes("项目背景\n实施范围".encode("gb18030"))

    assert parse_project_init_file(path, "旧版说明.txt") == [
        SourceChunk("旧版说明.txt", "第 1-2 行", "项目背景\n实施范围")
    ]


def test_docx_preserves_ordered_paragraph_text_and_twenty_paragraph_ranges(tmp_path):
    path = tmp_path / "plan.docx"
    document = Document()
    paragraphs = [f"段落 {index}" for index in range(1, 22)]
    for text in paragraphs:
        document.add_paragraph(text)
    document.save(path)

    assert parse_project_init_file(path, "实施方案.docx") == [
        SourceChunk("实施方案.docx", "第 1-20 段", "\n".join(paragraphs[:20])),
        SourceChunk("实施方案.docx", "第 21-21 段", paragraphs[20]),
    ]


def test_xlsx_uses_actual_non_empty_range_and_skips_empty_worksheets(tmp_path):
    path = tmp_path / "plan.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "实施计划"
    sheet["B2"] = "负责人"
    sheet["C3"] = "张三"
    workbook.create_sheet("空表")
    workbook.save(path)

    assert parse_project_init_file(path, "计划.xlsx") == [
        SourceChunk("计划.xlsx", "实施计划!B2:C3", "负责人\t\n\t张三")
    ]


def test_xls_uses_sheet_name_and_actual_non_empty_range(tmp_path, monkeypatch):
    path = tmp_path / "legacy.xls"
    path.write_bytes(b"xls-placeholder")

    class FakeSheet:
        name = "旧版计划"
        nrows = 4
        ncols = 4

        def cell_value(self, row, column):
            values = {(1, 1): "事项", (2, 2): 3.0}
            return values.get((row, column), "")

    class FakeBook:
        def sheets(self):
            return [FakeSheet()]

        def release_resources(self):
            pass

    monkeypatch.setattr(parser.xlrd, "open_workbook", lambda filename: FakeBook())

    assert parse_project_init_file(path, "历史计划.xls") == [
        SourceChunk("历史计划.xls", "旧版计划!B2:C3", "事项\t\n\t3")
    ]


def test_pdf_uses_injected_reader_and_preserves_non_empty_page_numbers(tmp_path):
    path = tmp_path / "scan.pdf"
    path.write_bytes(b"not-a-real-pdf")
    received_paths = []

    class FakePage:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

    class FakeReader:
        pages = [FakePage("第一页内容"), FakePage("  \n"), FakePage("第三页内容")]

    def reader_factory(received_path):
        received_paths.append(received_path)
        return FakeReader()

    assert parse_project_init_file(
        path,
        "调研报告.pdf",
        pdf_reader_factory=reader_factory,
    ) == [
        SourceChunk("调研报告.pdf", "第 1 页", "第一页内容"),
        SourceChunk("调研报告.pdf", "第 3 页", "第三页内容"),
    ]
    assert received_paths == [path]


def test_doc_invokes_antiword_without_shell_and_with_bounded_timeout(tmp_path, monkeypatch):
    path = tmp_path / "legacy.doc"
    path.write_bytes(b"legacy-doc")
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="第一行\n第二行", stderr="")

    monkeypatch.setattr(parser.subprocess, "run", fake_run)

    assert parse_project_init_file(path, "旧版文档.doc") == [
        SourceChunk("旧版文档.doc", "第 1-2 行", "第一行\n第二行")
    ]
    assert calls == [
        (
            ["antiword", "-w", "0", str(path)],
            {
                "capture_output": True,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "timeout": 30,
                "check": False,
            },
        )
    ]


@pytest.mark.parametrize(
    "failure",
    [
        SimpleNamespace(returncode=2, stdout="", stderr="bad document"),
        FileNotFoundError("antiword missing"),
        subprocess.TimeoutExpired(["antiword"], 30),
    ],
)
def test_doc_normalizes_antiword_failures(tmp_path, monkeypatch, failure):
    path = tmp_path / "broken.doc"
    path.write_bytes(b"broken")

    def fake_run(*_args, **_kwargs):
        if isinstance(failure, BaseException):
            raise failure
        return failure

    monkeypatch.setattr(parser.subprocess, "run", fake_run)

    with pytest.raises(ProjectInitFileParseError, match="原始损坏文档\\.doc"):
        parse_project_init_file(path, "原始损坏文档.doc")


def test_corrupt_third_party_file_error_is_normalized_with_original_filename(tmp_path):
    path = tmp_path / "randomized-storage-name.docx"
    path.write_bytes(b"not-a-zip")

    with pytest.raises(ProjectInitFileParseError, match="客户方案\\.docx"):
        parse_project_init_file(path, "客户方案.docx")


def test_unsupported_extension_raises_domain_error(tmp_path):
    path = tmp_path / "archive.csv"
    path.write_text("a,b", encoding="utf-8")

    with pytest.raises(UnsupportedProjectInitFile, match="archive\\.csv"):
        parse_project_init_file(path, "archive.csv")
