"""Standalone, opt-in DeepSeek probes for spreadsheet understanding."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import quote_sheetname
from pydantic import BaseModel, ConfigDict, Field

from .project_init_file_parser import parse_project_init_file


@dataclass(frozen=True)
class WorkbookEvidence:
    """Bounded workbook evidence that keeps exact worksheet locations."""

    text: str
    locations: set[str]
    merged_ranges: dict[str, str]
    input_sha256: str


class ProbeKeyTask(BaseModel):
    """One model-extracted key task accepted by the probe."""

    model_config = ConfigDict(extra="forbid")

    title: str
    owner: str = ""
    collaborators: list[str] = Field(default_factory=list)
    plan_start: str = ""
    plan_end: str = ""
    completion_standard: str = ""
    note: str = ""
    evidence: list[str] = Field(min_length=1)


class ProbeWorkstream(BaseModel):
    """One model-extracted workstream accepted by the probe."""

    model_config = ConfigDict(extra="forbid")

    title: str
    key_tasks: list[ProbeKeyTask] = Field(min_length=1)


class ProbeOutput(BaseModel):
    """Strict JSON envelope required from every provider route."""

    model_config = ConfigDict(extra="forbid")

    workstreams: list[ProbeWorkstream] = Field(min_length=1)


def build_workbook_evidence(
    path: Path,
    original_name: str,
    *,
    max_sheets: int,
    max_cells: int,
) -> WorkbookEvidence:
    """Return visible, non-empty cells and merge ranges after parser validation."""
    if max_sheets < 1 or max_cells < 1:
        raise ValueError("max_sheets and max_cells must be positive")

    input_path = Path(path)
    parsed_chunks = parse_project_init_file(input_path, original_name)
    workbook = load_workbook(input_path, read_only=False, data_only=True)
    try:
        lines = [
            f"[解析文本] {chunk.location}\n{chunk.text}"
            for chunk in parsed_chunks
            if chunk.text.strip()
        ]
        locations: set[str] = set()
        merged_ranges: dict[str, str] = {}
        emitted_cells = 0
        inspected_sheets = 0

        for sheet in workbook.worksheets:
            if sheet.sheet_state != "visible":
                continue
            inspected_sheets += 1
            if inspected_sheets > max_sheets:
                break
            merged_anchors = {
                (merged.min_row, merged.min_col): str(merged)
                for merged in sheet.merged_cells.ranges
            }
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.value is None or str(cell.value).strip() == "":
                        continue
                    emitted_cells += 1
                    if emitted_cells > max_cells:
                        raise ValueError("workbook evidence exceeds max_cells")
                    cell_range = merged_anchors.get((cell.row, cell.column), cell.coordinate)
                    location = f"{quote_sheetname(sheet.title)}!{cell_range}"
                    rendered_value = str(cell.value).strip()
                    locations.add(location)
                    lines.append(f"{location}={rendered_value}")
                    if cell_range != cell.coordinate:
                        merged_ranges[location] = rendered_value

        return WorkbookEvidence(
            text="\n".join(lines),
            locations=locations,
            merged_ranges=merged_ranges,
            input_sha256=sha256(input_path.read_bytes()).hexdigest(),
        )
    finally:
        workbook.close()
