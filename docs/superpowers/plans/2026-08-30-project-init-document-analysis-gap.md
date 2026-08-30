# Project-Initialization Document Analysis Gap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retain project-init source files durably, profile spreadsheet layout risk, and make the analysis route/review requirement explicit before draft generation.

**Architecture:** A shared storage resolver removes the inconsistent container-only root. A pure routing module profiles workbooks and chooses text, file, or text-with-review based on actual model capability. Snapshot creation freezes that decision and the worker preserves safe route metadata for the reviewer.

**Tech Stack:** Python, openpyxl, Pydantic, SQLAlchemy, FastAPI, React, pytest.

---

### Task 1: Centralize durable attachment storage

**Files:**
- Create: `bowei_ai_dashboard/app/services/project_init_attachment_storage.py`
- Modify: `bowei_ai_dashboard/app/routers/project_init_ai.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_analysis.py`
- Modify: `bowei_ai_dashboard/app/routers/projects.py`
- Test: `bowei_ai_dashboard/tests/test_project_init_attachment_storage.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_attachment_root_defaults_inside_backend_when_environment_is_absent(monkeypatch):
    monkeypatch.delenv("PROJECT_INIT_ATTACHMENT_ROOT", raising=False)
    assert project_init_attachment_root() == BACKEND_ROOT / "data" / "project-init-attachments"


def test_attachment_path_rejects_key_escaping_root(tmp_path):
    monkeypatch.setenv("PROJECT_INIT_ATTACHMENT_ROOT", str(tmp_path))
    with pytest.raises(ValueError):
        project_init_attachment_path("../outside")
```

- [ ] **Step 2: Verify RED**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_project_init_attachment_storage.py -v`

Expected: FAIL because the shared storage module does not exist.

- [ ] **Step 3: Implement one resolver used by every caller**

```python
def project_init_attachment_root() -> Path:
    configured = os.getenv("PROJECT_INIT_ATTACHMENT_ROOT", "").strip()
    root = Path(configured).expanduser() if configured else BACKEND_ROOT / "data" / "project-init-attachments"
    return root.resolve()


def project_init_attachment_path(storage_key: str) -> Path:
    root = project_init_attachment_root()
    path = (root / storage_key).resolve()
    if path == root or root not in path.parents:
        raise ValueError("invalid attachment storage path")
    return path
```

Replace the router, worker, and project cleanup local roots with these helpers.
Each caller keeps its current HTTP or worker error behavior.

- [ ] **Step 4: Verify GREEN and commit**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_project_init_attachment_storage.py tests/test_project_init_attachments.py tests/test_project_init_analysis.py -v`

Expected: PASS.

Run: `git add bowei_ai_dashboard/app/services/project_init_attachment_storage.py bowei_ai_dashboard/app/routers/project_init_ai.py bowei_ai_dashboard/app/services/project_init_analysis.py bowei_ai_dashboard/app/routers/projects.py bowei_ai_dashboard/tests/test_project_init_attachment_storage.py; git commit -m "fix: retain project init attachments locally"`

### Task 2: Profile workbook complexity and choose a truthful route

**Files:**
- Create: `bowei_ai_dashboard/app/services/project_init_document_routing.py`
- Modify: `bowei_ai_dashboard/app/ai/contracts.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Test: `bowei_ai_dashboard/tests/test_project_init_document_routing.py`

- [ ] **Step 1: Write the failing profile and route tests**

```python
def test_profile_marks_merged_multi_sheet_workbook_as_high_layout_risk(tmp_path):
    path = write_workbook(tmp_path, merged_ranges=6, nonempty_sheets=2)
    profile = profile_attachment(path, "plan.xlsx")
    assert profile.layout_risk == "high"
    assert "merged_ranges" in profile.reasons


def test_high_risk_spreadsheet_requires_review_without_xlsx_document_model():
    profile = SpreadsheetProfile(layout_risk="high", reasons=["merged_ranges"])
    route = select_analysis_route(profile, document_models=[])
    assert route.kind == "text_with_review"
    assert route.review_required is True
```

- [ ] **Step 2: Verify RED**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_project_init_document_routing.py -v`

Expected: FAIL because the routing module does not exist.

- [ ] **Step 3: Implement bounded profile and contracts**

```python
class AnalysisRoute(BaseModel):
    kind: Literal["text_structured", "file_understanding", "text_with_review"]
    review_required: bool = False
    fallback_reason: str = ""


def select_analysis_route(profile, document_models):
    if profile.layout_risk != "high":
        return AnalysisRoute(kind="text_structured")
    if any(".xlsx" in item.supported_input_extensions for item in document_models):
        return AnalysisRoute(kind="file_understanding")
    return AnalysisRoute(kind="text_with_review", review_required=True, fallback_reason="xlsx_file_model_unavailable")
```

Inspect only validated `.xlsx` metadata: worksheet visibility, non-empty cells,
merged ranges, formulas, and stable header shape. Reuse parser limits and do
not retain cell values. Add `ModelType.DOCUMENT` and validate document-model
`supported_input_extensions`; do not declare DeepSeek text models eligible.

- [ ] **Step 4: Verify GREEN and commit**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_project_init_document_routing.py tests/test_ai_service.py -v`

Expected: PASS.

Run: `git add bowei_ai_dashboard/app/services/project_init_document_routing.py bowei_ai_dashboard/app/ai/contracts.py bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/tests/test_project_init_document_routing.py; git commit -m "feat: classify project init document routes"`

### Task 3: Freeze route metadata and protect the review flow

**Files:**
- Modify: `bowei_ai_dashboard/app/services/project_init_analysis.py`
- Modify: `bowei_ai_dashboard/app/routers/project_init_ai.py`
- Modify: `bowei_ai_dashboard/tests/test_project_init_analysis.py`

- [ ] **Step 1: Write failing snapshot and worker tests**

```python
def test_snapshot_records_high_risk_text_fallback_without_source_cells(db, project, attachment, monkeypatch):
    monkeypatch.setattr(service, "profile_attachment", lambda *_args: high_risk_profile())
    snapshot = build_project_init_snapshot(db, project, [attachment], [])
    assert snapshot["attachments"][0]["analysis_route"] == "text_with_review"
    assert snapshot["attachments"][0]["review_required"] is True
    assert "cell_values" not in snapshot["attachments"][0]


def test_worker_marks_layout_review_required(monkeypatch, db, run):
    monkeypatch.setattr(service, "generate_project_init_draft", lambda *args, **kwargs: {"tasks": [], "warnings": []})
    service.process_analysis_run(run.id)
    assert json.loads(db.get(models.ProjectInitAnalysisRun, run.id).result_json)["review_required"] is True
```

- [ ] **Step 2: Verify RED**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_project_init_analysis.py -k "layout_risk or review_required" -v`

Expected: FAIL because snapshot route metadata is absent.

- [ ] **Step 3: Implement frozen route metadata**

At snapshot creation profile every source from its durable path. A missing
source becomes `layout_risk="unknown"`, `analysis_route="text_with_review"`,
and `fallback_reason="attachment_unavailable"`. Store only counts, reasons,
risk, route, and review flag. The worker keeps the current parser + text AI
flow for text routes and appends exactly:

```text
文件版式较复杂，当前按文本提取；请重点核对层级、协助人和完成标准。
```

For a frozen `file_understanding` route with no configured adapter, fail with
safe category `document_model_unavailable`; never route it to chat under a
file-understanding label.

- [ ] **Step 4: Verify GREEN and commit**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_project_init_analysis.py tests/test_project_init_attachments.py -v`

Expected: PASS.

Run: `git add bowei_ai_dashboard/app/services/project_init_analysis.py bowei_ai_dashboard/app/routers/project_init_ai.py bowei_ai_dashboard/tests/test_project_init_analysis.py; git commit -m "feat: expose project init analysis route risk"`

### Task 4: Present the review signal and run regressions

**Files:**
- Modify: `frontend/src/features/settings/ProjectsMgmtSection.tsx`
- Modify: `frontend/src/features/settings/projectReviewDraftRows.ts`
- Modify: `frontend/src/features/settings/projectReviewDraftRows.test.ts`
- Modify: `bowei_ai_dashboard/tests/test_project_init_ai_frontend.py`

- [ ] **Step 1: Write the failing notice test**

```typescript
test('shows layout review notice for text fallback', () => {
  expect(buildAnalysisRouteNotice({ analysis_route: 'text_with_review', review_required: true }))
    .toBe('文件版式较复杂，已按文本提取，请重点核对层级、协助人和完成标准。');
});
```

- [ ] **Step 2: Verify RED**

Run: `cd frontend; npm run test:unit -- projectReviewDraftRows.test.ts`

Expected: FAIL because `buildAnalysisRouteNotice` is absent.

- [ ] **Step 3: Implement the smallest read-only notice**

Add `buildAnalysisRouteNotice` to the existing review-row helper and render it
only when `review_required` is true. Do not alter submit, approval, members,
or task writeback.

- [ ] **Step 4: Verify GREEN and commit**

Run: `cd frontend; npm run test:unit -- projectReviewDraftRows.test.ts; npm run build; cd ../bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_project_init_ai_frontend.py tests/test_project_init_attachment_storage.py tests/test_project_init_document_routing.py tests/test_project_init_analysis.py tests/test_project_init_file_parser.py tests/test_ai_service.py -v`

Expected: PASS.

Run: `git add frontend/src/features/settings/ProjectsMgmtSection.tsx frontend/src/features/settings/projectReviewDraftRows.ts frontend/src/features/settings/projectReviewDraftRows.test.ts bowei_ai_dashboard/tests/test_project_init_ai_frontend.py; git commit -m "feat: show document analysis review risk"`

- [ ] **Step 5: Inspect final safety**

Run: `git diff --check; git status --short`

Expected: no raw attachment, key, temporary spreadsheet, or generated probe result is staged.
