"""Parse project-init source files into text chunks with source locations."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import xlrd
from docx import Document
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from pypdf import PdfReader


class ProjectInitFileParseError(Exception):
    """Raised when a supported project-init file cannot be parsed."""


class UnsupportedProjectInitFile(Exception):
    """Raised when a project-init file has an unsupported extension."""


@dataclass(frozen=True)
class SourceChunk:
    file_name: str
    location: str
    text: str

    @property
    def source_label(self) -> str:
        return f"{self.file_name} · {self.location}"


PdfReaderFactory = Callable[[Path], Any]


def parse_project_init_file(
    path: Path,
    original_name: str,
    *,
    pdf_reader_factory: PdfReaderFactory | None = None,
) -> list[SourceChunk]:
    """Parse a supported file and normalize parser failures for callers."""
    path = Path(path)
    extension = Path(original_name).suffix.lower()
    if extension not in {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt"}:
        raise UnsupportedProjectInitFile(f"不支持的项目初始化文件：{original_name}")

    try:
        if extension == ".pdf":
            chunks = _parse_pdf(
                path,
                original_name,
                pdf_reader_factory or PdfReader,
            )
        elif extension == ".doc":
            chunks = _parse_doc(path, original_name)
        elif extension == ".docx":
            chunks = _parse_docx(path, original_name)
        elif extension == ".xls":
            chunks = _parse_xls(path, original_name)
        elif extension == ".xlsx":
            chunks = _parse_xlsx(path, original_name)
        else:
            chunks = _parse_txt(path, original_name)
        return [chunk for chunk in chunks if chunk.text.strip()]
    except (ProjectInitFileParseError, UnsupportedProjectInitFile):
        raise
    except Exception as exc:
        raise ProjectInitFileParseError(
            f"无法解析项目初始化文件：{original_name}"
        ) from exc


def _parse_pdf(
    path: Path,
    original_name: str,
    reader_factory: PdfReaderFactory,
) -> list[SourceChunk]:
    reader = reader_factory(path)
    return [
        SourceChunk(original_name, f"第 {page_number} 页", page.extract_text() or "")
        for page_number, page in enumerate(reader.pages, start=1)
    ]


def _parse_doc(path: Path, original_name: str) -> list[SourceChunk]:
    result = subprocess.run(
        ["antiword", "-w", "0", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise ProjectInitFileParseError(
            f"无法解析项目初始化文件：{original_name}"
        )
    return _chunk_lines(result.stdout, original_name)


def _parse_docx(path: Path, original_name: str) -> list[SourceChunk]:
    document = Document(path)
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    return _chunk_numbered_text(paragraphs, 20, "段", original_name)


def _parse_xls(path: Path, original_name: str) -> list[SourceChunk]:
    workbook = xlrd.open_workbook(str(path))
    try:
        chunks = []
        for sheet in workbook.sheets():
            rows = [
                [
                    sheet.cell_value(row_index, column_index)
                    for column_index in range(sheet.ncols)
                ]
                for row_index in range(sheet.nrows)
            ]
            chunk = _worksheet_chunk(sheet.name, rows, original_name)
            if chunk is not None:
                chunks.append(chunk)
        return chunks
    finally:
        release_resources = getattr(workbook, "release_resources", None)
        if callable(release_resources):
            release_resources()


def _parse_xlsx(path: Path, original_name: str) -> list[SourceChunk]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        chunks = []
        for sheet in workbook.worksheets:
            rows = [[cell.value for cell in row] for row in sheet.iter_rows()]
            chunk = _worksheet_chunk(sheet.title, rows, original_name)
            if chunk is not None:
                chunks.append(chunk)
        return chunks
    finally:
        workbook.close()


def _parse_txt(path: Path, original_name: str) -> list[SourceChunk]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("gb18030")
    return _chunk_lines(text, original_name)


def _chunk_lines(text: str, original_name: str) -> list[SourceChunk]:
    return _chunk_numbered_text(text.splitlines(), 80, "行", original_name)


def _chunk_numbered_text(
    values: Sequence[str],
    chunk_size: int,
    unit: str,
    original_name: str,
) -> list[SourceChunk]:
    chunks = []
    for start_index in range(0, len(values), chunk_size):
        end_index = min(start_index + chunk_size, len(values))
        chunks.append(
            SourceChunk(
                original_name,
                f"第 {start_index + 1}-{end_index} {unit}",
                "\n".join(values[start_index:end_index]),
            )
        )
    return chunks


def _worksheet_chunk(
    sheet_name: str,
    rows: Sequence[Sequence[Any]],
    original_name: str,
) -> SourceChunk | None:
    populated = [
        (row_index, column_index)
        for row_index, row in enumerate(rows)
        for column_index, value in enumerate(row)
        if _is_non_empty_cell(value)
    ]
    if not populated:
        return None

    min_row = min(row for row, _column in populated)
    max_row = max(row for row, _column in populated)
    min_column = min(column for _row, column in populated)
    max_column = max(column for _row, column in populated)
    rendered_rows = [
        "\t".join(
            _render_cell(rows[row_index][column_index])
            for column_index in range(min_column, max_column + 1)
        )
        for row_index in range(min_row, max_row + 1)
    ]
    location = (
        f"{sheet_name}!{get_column_letter(min_column + 1)}{min_row + 1}:"
        f"{get_column_letter(max_column + 1)}{max_row + 1}"
    )
    return SourceChunk(original_name, location, "\n".join(rendered_rows))


def _is_non_empty_cell(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _render_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return str(value)
