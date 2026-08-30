"""Standalone, opt-in DeepSeek probes for spreadsheet understanding."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Callable, Literal

from openpyxl import load_workbook
from openpyxl.utils import quote_sheetname
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app import models

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


TEXT_MODELS = ("deepseek-v4-flash", "deepseek-v4-pro")
ProbeStatus = Literal[
    "succeeded",
    "invalid_json",
    "invalid_schema",
    "uncited_output",
    "upstream_error",
    "skipped",
]


@dataclass(frozen=True)
class ProbeResult:
    """A sanitized outcome for one probe model invocation."""

    mode: Literal["a", "b"]
    model_name: str
    status: ProbeStatus
    duration_ms: int
    output: ProbeOutput | None = None
    reason: str = ""


class ProbeRunner:
    """Compare text models against the same workbook evidence."""

    def __init__(self, *, complete_text: Callable[[str, str], str]) -> None:
        self._complete_text = complete_text

    def run_text(self, evidence: WorkbookEvidence) -> list[ProbeResult]:
        return [self._run_text_model(model_name, evidence) for model_name in TEXT_MODELS]

    def _run_text_model(self, model_name: str, evidence: WorkbookEvidence) -> ProbeResult:
        started = time.monotonic()
        try:
            response = self._complete_text(model_name, _text_prompt(evidence))
        except Exception:
            return ProbeResult(
                mode="a",
                model_name=model_name,
                status="upstream_error",
                duration_ms=_elapsed_ms(started),
            )
        try:
            payload = json.loads(response)
        except (TypeError, json.JSONDecodeError):
            return ProbeResult(
                mode="a",
                model_name=model_name,
                status="invalid_json",
                duration_ms=_elapsed_ms(started),
            )
        try:
            output = ProbeOutput.model_validate(payload)
        except ValidationError:
            return ProbeResult(
                mode="a",
                model_name=model_name,
                status="invalid_schema",
                duration_ms=_elapsed_ms(started),
            )
        if not _has_only_known_evidence(output, evidence.locations):
            return ProbeResult(
                mode="a",
                model_name=model_name,
                status="uncited_output",
                duration_ms=_elapsed_ms(started),
            )
        return ProbeResult(
            mode="a",
            model_name=model_name,
            status="succeeded",
            duration_ms=_elapsed_ms(started),
            output=output,
        )


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


def _has_only_known_evidence(output: ProbeOutput, locations: set[str]) -> bool:
    return all(
        location in locations
        for workstream in output.workstreams
        for key_task in workstream.key_tasks
        for location in key_task.evidence
    )


def _text_prompt(evidence: WorkbookEvidence) -> str:
    return """你正在测试对 Excel 工作推进表的结构理解。只返回一个 JSON 对象，不能使用 Markdown。

请提取：专项/重点工作 -> workstreams；关键任务 -> key_tasks。每个关键任务必须包含
title、owner、collaborators、plan_start、plan_end、completion_standard、note、evidence。
“协同成员”“协助人”“参与人”以及类似“协助人：张三、李四”的备注都属于 collaborators；
不要在 note 中重复协助人名单。信息不确定时留空或在 note 说明，不能编造。
每个 key_task 必须用 evidence 引用下面证据中完全一致的单元格位置。

JSON 结构：
{"workstreams":[{"title":"","key_tasks":[{"title":"","owner":"","collaborators":[],"plan_start":"","plan_end":"","completion_standard":"","note":"","evidence":["'工作表'!A1"]}]}]}

证据：
""" + evidence.text


def build_text_completion(
    credential_model: models.AIModel,
    *,
    credential_reader: Callable[[int], str],
    adapter: Callable[[models.AIModel, str, str], str],
) -> Callable[[str, str], str]:
    """Build an in-memory target-model caller without storing credentials."""
    api_key = credential_reader(credential_model.id)

    def complete(target_model_name: str, prompt: str) -> str:
        target_model = models.AIModel(
            id=credential_model.id,
            code=f"{credential_model.code}-spreadsheet-probe",
            display_name=credential_model.display_name,
            provider=credential_model.provider,
            model_name=target_model_name,
            model_type=credential_model.model_type,
            base_url=credential_model.base_url,
            config_json=credential_model.config_json,
            enabled=credential_model.enabled,
        )
        return adapter(target_model, api_key, prompt)

    return complete


def run_visual_probe(
    input_path: Path,
    *,
    evidence: WorkbookEvidence,
    build_images: Callable[[Path, Path], list[Path] | None],
    complete_vision: Callable[[list[Path], str], str],
) -> ProbeResult:
    """Run only a real visual route; never fall back to text evidence alone."""
    with tempfile.TemporaryDirectory(prefix="deepseek-spreadsheet-probe-") as raw_directory:
        images = build_images(Path(input_path), Path(raw_directory))
        if not images:
            return ProbeResult(
                mode="b",
                model_name="deepseek-v4-flash-vision-exp",
                status="skipped",
                duration_ms=0,
                reason="renderer_unavailable",
            )
        started = time.monotonic()
        try:
            response = complete_vision(images, _text_prompt(evidence))
        except Exception:
            return ProbeResult(
                mode="b",
                model_name="deepseek-v4-flash-vision-exp",
                status="upstream_error",
                duration_ms=_elapsed_ms(started),
            )
        return _validated_response("b", "deepseek-v4-flash-vision-exp", response, evidence, started)


def render_workbook_images(input_path: Path, output_directory: Path) -> list[Path] | None:
    """Render an Excel workbook through local office software, or return None."""
    office = shutil.which("soffice") or shutil.which("libreoffice")
    pdftoppm = shutil.which("pdftoppm")
    if not office or not pdftoppm:
        return None
    try:
        conversion = subprocess.run(
            [office, "--headless", "--convert-to", "pdf", "--outdir", str(output_directory), str(input_path)],
            check=False,
            capture_output=True,
            timeout=60,
        )
        if conversion.returncode != 0:
            return None
        pdf_paths = list(output_directory.glob("*.pdf"))
        if len(pdf_paths) != 1:
            return None
        prefix = output_directory / "sheet"
        raster = subprocess.run(
            [pdftoppm, "-png", str(pdf_paths[0]), str(prefix)],
            check=False,
            capture_output=True,
            timeout=60,
        )
        images = sorted(output_directory.glob("sheet-*.png"))
        return images if raster.returncode == 0 and images else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def build_vision_completion(
    credential_model: models.AIModel,
    *,
    credential_reader: Callable[[int], str],
    client_factory: Callable[..., object] | None = None,
) -> Callable[[list[Path], str], str]:
    """Create a DeepSeek image-file caller without returning credentials or IDs."""
    api_key = credential_reader(credential_model.id)
    if client_factory is None:
        from openai import OpenAI

        client_factory = OpenAI

    def complete(images: list[Path], prompt: str) -> str:
        client = client_factory(
            api_key=api_key,
            base_url=credential_model.base_url,
            timeout=60,
            max_retries=0,
        )
        content: list[dict] = [{"type": "text", "text": prompt}]
        for image_path in images:
            with Path(image_path).open("rb") as image:
                uploaded = client.files.create(file=image, purpose="user_data")
            content.append({"type": "image_file", "image_file": {"file_id": uploaded.id}})
        response = client.chat.completions.create(
            model="deepseek-v4-flash-vision-exp",
            messages=[{"role": "user", "content": content}],
        )
        return str(response.choices[0].message.content or "")

    return complete


def _validated_response(
    mode: Literal["a", "b"],
    model_name: str,
    response: object,
    evidence: WorkbookEvidence,
    started: float,
) -> ProbeResult:
    try:
        payload = json.loads(response)
    except (TypeError, json.JSONDecodeError):
        return ProbeResult(mode=mode, model_name=model_name, status="invalid_json", duration_ms=_elapsed_ms(started))
    try:
        output = ProbeOutput.model_validate(payload)
    except ValidationError:
        return ProbeResult(mode=mode, model_name=model_name, status="invalid_schema", duration_ms=_elapsed_ms(started))
    if not _has_only_known_evidence(output, evidence.locations):
        return ProbeResult(mode=mode, model_name=model_name, status="uncited_output", duration_ms=_elapsed_ms(started))
    return ProbeResult(mode=mode, model_name=model_name, status="succeeded", duration_ms=_elapsed_ms(started), output=output)


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
