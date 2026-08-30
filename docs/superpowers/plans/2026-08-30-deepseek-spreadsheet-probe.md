# DeepSeek Spreadsheet Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in CLI diagnostic that tests an Excel workbook through DeepSeek structured-text (A) and visual-layout (B) routes without changing production imports or exposing credentials.

**Architecture:** A small service module owns cited evidence, strict output validation, prompt construction, and safe result statuses. A thin CLI obtains an already configured encrypted DeepSeek credential internally, invokes A in Flash→Pro order, and independently attempts B only when a genuine office renderer and vision path are available.

**Tech Stack:** Python, Pydantic, openpyxl, OpenAI SDK, pytest, SQLAlchemy.

---

### Task 1: Create cited workbook evidence and safe models

**Files:**
- Create: `bowei_ai_dashboard/app/services/deepseek_spreadsheet_probe.py`
- Create: `bowei_ai_dashboard/tests/test_deepseek_spreadsheet_probe.py`

- [ ] **Step 1: Write the failing test**

```python
def test_build_workbook_evidence_preserves_cells_and_merged_range(tmp_path):
    path = tmp_path / "推进表.xlsx"
    book = Workbook(); sheet = book.active; sheet.title = "工作推进表"
    sheet.merge_cells("A1:B1"); sheet["A1"] = "知识资产AI化"
    sheet["A2"] = "关键任务"; sheet["B2"] = "协助人：张三、李四"; book.save(path)

    evidence = build_workbook_evidence(path, "推进表.xlsx", max_sheets=3, max_cells=100)

    assert evidence.locations == {"'工作推进表'!A1:B1", "'工作推进表'!A2", "'工作推进表'!B2"}
    assert evidence.merged_ranges == {"'工作推进表'!A1:B1": "知识资产AI化"}
```

- [ ] **Step 2: Verify RED**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_deepseek_spreadsheet_probe.py::test_build_workbook_evidence_preserves_cells_and_merged_range -v`

Expected: FAIL because `deepseek_spreadsheet_probe` does not exist.

- [ ] **Step 3: Add minimal evidence implementation**

```python
@dataclass(frozen=True)
class WorkbookEvidence:
    text: str
    locations: set[str]
    merged_ranges: dict[str, str]
    input_sha256: str


def build_workbook_evidence(path: Path, original_name: str, *, max_sheets: int, max_cells: int) -> WorkbookEvidence:
    chunks = parse_project_init_file(path, original_name)
    # Load a workbook after parser validation; emit visible non-empty A1 cells and merged anchors.
```

Use `quote_sheetname`, visible sheets only, physical non-empty cells bounded by
`max_cells`, and a `finally` block that closes the workbook. Keep exact
locations in the evidence and compute SHA-256 from input bytes. Add Pydantic
models `ProbeKeyTask`, `ProbeWorkstream`, and `ProbeOutput` with
`extra="forbid"`, required non-empty `workstreams` / `key_tasks`, and
per-key-task `evidence`.

- [ ] **Step 4: Verify GREEN**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_deepseek_spreadsheet_probe.py::test_build_workbook_evidence_preserves_cells_and_merged_range -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add bowei_ai_dashboard/app/services/deepseek_spreadsheet_probe.py bowei_ai_dashboard/tests/test_deepseek_spreadsheet_probe.py; git commit -m "feat: add cited spreadsheet probe evidence"`

### Task 2: Add Probe A Flash→Pro comparison and validation

**Files:**
- Modify: `bowei_ai_dashboard/app/services/deepseek_spreadsheet_probe.py`
- Modify: `bowei_ai_dashboard/tests/test_deepseek_spreadsheet_probe.py`

- [ ] **Step 1: Write failing model-comparison tests**

```python
def test_probe_a_calls_flash_then_pro_and_requires_cited_output():
    calls = []
    runner = ProbeRunner(complete_text=lambda model, prompt: calls.append(model) or JSON_WITH_A1_EVIDENCE)
    evidence = WorkbookEvidence("'表'!A1=专项", {"'表'!A1"}, {}, "hash")

    results = runner.run_text(evidence)

    assert calls == ["deepseek-v4-flash", "deepseek-v4-pro"]
    assert [item.status for item in results] == ["succeeded", "succeeded"]


def test_probe_a_rejects_unknown_evidence_location():
    runner = ProbeRunner(complete_text=lambda _model, _prompt: JSON_WITH_Z9_EVIDENCE)
    result = runner.run_text(WorkbookEvidence("x", {"'表'!A1"}, {}, "hash"))[0]
    assert result.status == "uncited_output"
    assert result.output is None
```

- [ ] **Step 2: Verify RED**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_deepseek_spreadsheet_probe.py -k "probe_a" -v`

Expected: FAIL because `ProbeRunner` is absent.

- [ ] **Step 3: Implement the smallest text runner**

```python
TEXT_MODELS = ("deepseek-v4-flash", "deepseek-v4-pro")


class ProbeRunner:
    def __init__(self, *, complete_text: Callable[[str, str], str]) -> None:
        self._complete_text = complete_text

    def run_text(self, evidence: WorkbookEvidence) -> list[ProbeResult]:
        return [self._run_text_model(name, evidence) for name in TEXT_MODELS]
```

`_run_text_model` must request one JSON object mapping 专项/重点工作 to
workstream and 关键任务 to key task. It explicitly maps 协同成员、协助人、参与人
and `协助人：...` prose to `collaborators`, and asks the model to remove the
duplicate roster from `note`. It parses JSON, validates `ProbeOutput`, verifies
every cited location, and returns only `succeeded`, `invalid_json`,
`invalid_schema`, `uncited_output`, or `upstream_error`. Never preserve an
exception message or unvalidated response.

- [ ] **Step 4: Verify GREEN**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_deepseek_spreadsheet_probe.py -k "probe_a" -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add bowei_ai_dashboard/app/services/deepseek_spreadsheet_probe.py bowei_ai_dashboard/tests/test_deepseek_spreadsheet_probe.py; git commit -m "feat: compare DeepSeek spreadsheet text probes"`

### Task 3: Add secure command-line execution for A

**Files:**
- Create: `bowei_ai_dashboard/scripts/probe_deepseek_spreadsheet.py`
- Modify: `bowei_ai_dashboard/app/services/deepseek_spreadsheet_probe.py`
- Modify: `bowei_ai_dashboard/tests/test_deepseek_spreadsheet_probe.py`

- [ ] **Step 1: Write a failing credential-boundary test**

```python
def test_build_text_completion_targets_in_memory_model_without_returning_secret():
    captured = {}
    completion = build_text_completion(
        credential_model=deepseek_model(),
        credential_reader=lambda model_id: captured.setdefault("id", model_id) or "secret",
        adapter=lambda model, key, prompt: captured.update(model=model.model_name, key=key) or "{}",
    )

    assert completion("deepseek-v4-flash", "prompt") == "{}"
    assert captured["model"] == "deepseek-v4-flash"
    assert "secret" not in repr(completion)
```

- [ ] **Step 2: Verify RED**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_deepseek_spreadsheet_probe.py::test_build_text_completion_targets_in_memory_model_without_returning_secret -v`

Expected: FAIL because `build_text_completion` is absent.

- [ ] **Step 3: Implement safe completion and CLI**

```python
def build_text_completion(credential_model, *, credential_reader, adapter):
    api_key = credential_reader(credential_model.id)
    def complete(target_model_name: str, prompt: str) -> str:
        return adapter(replace(credential_model, model_name=target_model_name), api_key, prompt)
    return complete
```

The CLI uses `argparse`, requires `--input`, accepts `--mode a|b|all`,
`--output-dir`, and `--dry-run`, and calls `load_local_env()` before importing
the database session. It selects an enabled DeepSeek chat model with an
encrypted credential, calls `AIService(db)._credential` internally, and wraps
`DefaultAIAdapters().complete_chat`. Do not call `AIService.invoke_chat` (it
adds a production capability audit log), do not expose API keys in args/output,
and never persist a model override. Write a sanitized `summary.json` only
after input validation. Dry run reports target models and makes no request.

- [ ] **Step 4: Verify GREEN**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_deepseek_spreadsheet_probe.py::test_build_text_completion_targets_in_memory_model_without_returning_secret -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add bowei_ai_dashboard/app/services/deepseek_spreadsheet_probe.py bowei_ai_dashboard/scripts/probe_deepseek_spreadsheet.py bowei_ai_dashboard/tests/test_deepseek_spreadsheet_probe.py; git commit -m "feat: add secure DeepSeek spreadsheet probe CLI"`

### Task 4: Add independent Probe B visual gating

**Files:**
- Modify: `bowei_ai_dashboard/app/services/deepseek_spreadsheet_probe.py`
- Modify: `bowei_ai_dashboard/scripts/probe_deepseek_spreadsheet.py`
- Modify: `bowei_ai_dashboard/tests/test_deepseek_spreadsheet_probe.py`

- [ ] **Step 1: Write the failing visual skip test**

```python
def test_probe_b_skips_instead_of_falling_back_to_text_without_renderer(tmp_path):
    result = run_visual_probe(
        tmp_path / "plan.xlsx",
        build_images=lambda _path: None,
        complete_vision=lambda _images, _prompt: pytest.fail("vision must not run"),
    )
    assert (result.status, result.reason) == ("skipped", "renderer_unavailable")
```

- [ ] **Step 2: Verify RED**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_deepseek_spreadsheet_probe.py::test_probe_b_skips_instead_of_falling_back_to_text_without_renderer -v`

Expected: FAIL because `run_visual_probe` is absent.

- [ ] **Step 3: Implement visual-only behavior**

```python
def run_visual_probe(input_path: Path, *, build_images, complete_vision) -> ProbeResult:
    images = build_images(input_path)
    if not images:
        return ProbeResult(mode="b", model_name="deepseek-v4-flash-vision-exp", status="skipped", duration_ms=0, reason="renderer_unavailable")
    return _parse_visual_response(complete_vision(images, build_visual_prompt()), images)
```

Use `shutil.which("soffice")` / `shutil.which("libreoffice")` plus a local
PDF-to-PNG converter to create images in a temporary directory. If either is
unavailable, skip; do not fake a layout image with openpyxl. Upload only PNGs
using `client.files.create(..., purpose="user_data")`; send the documented
file-ID content to `deepseek-v4-flash-vision-exp`; close handles and delete the
temporary directory in `finally`; never put file IDs in a result. Reuse the
same JSON schema and evidence location validation as A.

- [ ] **Step 4: Verify GREEN**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_deepseek_spreadsheet_probe.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add bowei_ai_dashboard/app/services/deepseek_spreadsheet_probe.py bowei_ai_dashboard/scripts/probe_deepseek_spreadsheet.py bowei_ai_dashboard/tests/test_deepseek_spreadsheet_probe.py; git commit -m "feat: add gated DeepSeek visual spreadsheet probe"`

### Task 5: Run A then B against the selected workbook

**Files:**
- Verify: `bowei_ai_dashboard/app/services/deepseek_spreadsheet_probe.py`
- Verify: `bowei_ai_dashboard/scripts/probe_deepseek_spreadsheet.py`

- [ ] **Step 1: Run focused verification**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_deepseek_spreadsheet_probe.py tests/test_project_init_file_parser.py tests/test_ai_adapters.py -v; .\.venv\Scripts\python.exe -m py_compile app/services/deepseek_spreadsheet_probe.py scripts/probe_deepseek_spreadsheet.py`

Expected: all tests pass; compiler is silent.

- [ ] **Step 2: Dry-run A then B**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe scripts/probe_deepseek_spreadsheet.py --input <user-selected-xlsx> --mode all --dry-run --output-dir tmp/deepseek-probe-dry-run`

Expected: reports Flash→Pro targets, B prerequisites, and no external request.

- [ ] **Step 3: Execute the authorized external test once**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe scripts/probe_deepseek_spreadsheet.py --input <user-selected-xlsx> --mode all --output-dir tmp/deepseek-probe-<timestamp>`

Expected: A reports separate Flash and Pro statuses; B reports a validated result, safe upstream error, or `renderer_unavailable`; formal import state and configuration are unchanged.

- [ ] **Step 4: Inspect safety and commit**

Run: `git diff --check; git status --short; git add bowei_ai_dashboard/app/services/deepseek_spreadsheet_probe.py bowei_ai_dashboard/scripts/probe_deepseek_spreadsheet.py bowei_ai_dashboard/tests/test_deepseek_spreadsheet_probe.py; git commit -m "test: verify DeepSeek spreadsheet probes"`

Expected: no secret or generated `tmp/` artifact is staged, and only probe code/tests are committed.
