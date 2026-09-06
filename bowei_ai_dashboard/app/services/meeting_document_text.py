"""Extract plain text from the document formats accepted by meeting minutes."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree


MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_DOCX_XML_BYTES = 20 * 1024 * 1024
_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


class MeetingDocumentTextError(ValueError):
    """Raised when an uploaded source cannot be used for meeting analysis."""


def extract_meeting_document_text(filename: str, content: bytes) -> str:
    """Return text from one Word/TXT source without storing the uploaded file."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".docx", ".txt", ".xlsx"}:
        raise MeetingDocumentTextError("仅支持 Word、TXT、Excel 文档（.docx、.txt、.xlsx），暂不支持 PDF")
    if not content:
        raise MeetingDocumentTextError("文档内容为空")
    if len(content) > MAX_DOCUMENT_BYTES:
        raise MeetingDocumentTextError("文档不能超过 10 MB")

    if suffix == ".txt":
        try:
            return content.decode("utf-8-sig").strip()
        except UnicodeDecodeError as exc:
            raise MeetingDocumentTextError("TXT 文档必须使用 UTF-8 编码") from exc

    if suffix == ".xlsx":
        return _extract_xlsx_text(content)

    try:
        with ZipFile(BytesIO(content)) as archive:
            try:
                info = archive.getinfo("word/document.xml")
            except KeyError as exc:
                raise MeetingDocumentTextError("不是有效的 Word 文档") from exc
            if info.file_size > MAX_DOCX_XML_BYTES:
                raise MeetingDocumentTextError("Word 文档内容过大")
            document_xml = archive.read(info)
    except BadZipFile as exc:
        raise MeetingDocumentTextError("不是有效的 Word 文档") from exc

    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError as exc:
        raise MeetingDocumentTextError("Word 文档内容无法解析") from exc

    paragraphs: list[str] = []
    for paragraph in root.iter(f"{_WORD_NS}p"):
        line = "".join(node.text or "" for node in paragraph.iter(f"{_WORD_NS}t")).strip()
        if line:
            paragraphs.append(line)
    text = "\n".join(paragraphs).strip()
    if not text:
        raise MeetingDocumentTextError("文档中没有可分析的文字")
    return text


def _extract_xlsx_text(content: bytes) -> str:
    """Extract readable reference cells from an Excel workbook."""
    try:
        with ZipFile(BytesIO(content)) as archive:
            sheet_names = sorted(
                name for name in archive.namelist()
                if name.startswith("xl/worksheets/") and name.endswith(".xml")
            )
            if not sheet_names:
                raise MeetingDocumentTextError("Invalid Excel workbook")
            for name in sheet_names:
                if archive.getinfo(name).file_size > MAX_DOCX_XML_BYTES:
                    raise MeetingDocumentTextError("Excel worksheet is too large")

            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
                shared_strings = [
                    "".join(node.text or "" for node in item.iter(f"{_SHEET_NS}t"))
                    for item in shared_root.iter(f"{_SHEET_NS}si")
                ]

            lines: list[str] = []
            for name in sheet_names:
                root = ElementTree.fromstring(archive.read(name))
                for row in root.iter(f"{_SHEET_NS}row"):
                    values: list[str] = []
                    for cell in row.iter(f"{_SHEET_NS}c"):
                        cell_type = cell.attrib.get("t", "")
                        if cell_type == "inlineStr":
                            value = "".join(node.text or "" for node in cell.iter(f"{_SHEET_NS}t"))
                        else:
                            value_node = cell.find(f"{_SHEET_NS}v")
                            value = value_node.text if value_node is not None and value_node.text else ""
                            if cell_type == "s" and value.isdigit() and int(value) < len(shared_strings):
                                value = shared_strings[int(value)]
                        if value.strip():
                            values.append(value.strip())
                    if values:
                        lines.append("\t".join(values))
    except (BadZipFile, ElementTree.ParseError) as exc:
        raise MeetingDocumentTextError("Excel workbook cannot be parsed") from exc

    text = "\n".join(lines).strip()
    if not text:
        raise MeetingDocumentTextError("Excel workbook has no readable cells")
    return text
