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

    body = root.find(f".//{_WORD_NS}body")
    if body is None:
        raise MeetingDocumentTextError("Word 文档缺少正文")
    text = "\n".join(_extract_word_blocks(body)).strip()
    if not text:
        raise MeetingDocumentTextError("文档中没有可分析的文字")
    return text


def _paragraph_text(paragraph: ElementTree.Element) -> str:
    parts: list[str] = []

    def append(value: str) -> None:
        if value == "\f" and parts and parts[-1] == "\f":
            return
        parts.append(value)

    for node in paragraph.iter():
        if node.tag == f"{_WORD_NS}t":
            append(node.text or "")
        elif node.tag == f"{_WORD_NS}tab":
            append("\t")
        elif node.tag == f"{_WORD_NS}br":
            break_type = node.attrib.get(f"{_WORD_NS}type", "")
            append("\f" if break_type == "page" else "\n")
        elif node.tag == f"{_WORD_NS}lastRenderedPageBreak":
            append("\f")
    return "".join(parts).strip()


def _table_rows(table: ElementTree.Element) -> list[str]:
    rows: list[str] = []
    for row in table.findall(f"{_WORD_NS}tr"):
        cells: list[str] = []
        for cell in row.findall(f"{_WORD_NS}tc"):
            cell_text = " / ".join(part for part in _extract_word_blocks(cell) if part)
            cells.append(cell_text.replace("\n", " / "))
        line = "\t".join(cells).rstrip()
        if line.strip():
            rows.append(line)
    return rows


def _extract_word_blocks(container: ElementTree.Element) -> list[str]:
    blocks: list[str] = []
    for child in container:
        if child.tag == f"{_WORD_NS}p":
            paragraph = _paragraph_text(child)
            if paragraph:
                blocks.append(paragraph)
        elif child.tag == f"{_WORD_NS}tbl":
            blocks.extend(_table_rows(child))
        else:
            # Walk content wrappers such as content controls while ignoring
            # formatting/property trees that cannot contain body content.
            if child.tag.endswith("Pr") or child.tag in {
                f"{_WORD_NS}sectPr",
                f"{_WORD_NS}tblGrid",
                f"{_WORD_NS}trPr",
                f"{_WORD_NS}tcPr",
            }:
                continue
            blocks.extend(_extract_word_blocks(child))
    return blocks


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


def meeting_source_locator(filename: str, document_text: str, char_start: int, char_end: int) -> str:
    """Convert a verified extracted-text span into a human-readable source location."""
    if char_start < 0 or char_end <= char_start or char_end > len(document_text):
        return ""
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".docx":
        page_start = document_text.rfind("\f", 0, char_start) + 1
        page_number = document_text.count("\f", 0, char_start) + 1
        paragraph_number = document_text.count("\n", page_start, char_start) + 1
        return f"第{page_number}页·第{paragraph_number}段"
    line_number = document_text.count("\n", 0, char_start) + 1
    if suffix == ".xlsx":
        return f"第{line_number}行"
    return f"第{line_number}段"
