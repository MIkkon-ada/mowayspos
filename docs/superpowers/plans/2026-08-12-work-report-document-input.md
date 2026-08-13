# Work Report Document Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Let users upload a Word, PDF, Excel, or PowerPoint document as a work-report input, edit extracted text, and run the existing permission-safe AI review and submission flow.

**Architecture:** Add a stateless authenticated document-to-text endpoint beneath the updates router. The frontend adds an isolated upload hook and fourth input tab, passing returned text to the existing extraction and submission hooks. Parsing neither stores original files nor changes tasks.

**Tech Stack:** FastAPI, Pydantic, python-docx, pypdf, openpyxl, python-pptx, React 19, TypeScript, node:test, pytest.

---

## File structure

- Create: bowei_ai_dashboard/app/services/work_report_document_text.py — bounded parser for DOCX/PDF/XLSX/PPTX.
- Create: bowei_ai_dashboard/tests/test_work_report_document_text.py — parser format and rejection tests.
- Modify: bowei_ai_dashboard/app/routers/updates.py — authenticated multipart parser route without DB writes.
- Modify: bowei_ai_dashboard/app/domain/source_type.py — document source label.
- Modify: bowei_ai_dashboard/requirements.txt — python-pptx dependency.
- Create: bowei_ai_dashboard/tests/test_updates_document_upload.py — auth, response, no-write API checks.
- Modify: frontend/src/api/updates.ts — typed multipart client.
- Create: frontend/src/features/voice-update/useVoiceDocumentUpload.ts — upload state and safe text replacement.
- Modify: frontend/src/features/voice-update/VoiceUpdateInputPanel.tsx — document mode and presentation.
- Modify: frontend/src/pages/VoiceUpdatePage.tsx — hook integration and busy-state gates.
- Modify: frontend/src/features/voice-update/useVoiceExtraction.ts and useVoiceSubmission.ts — document source label.
- Modify: frontend/src/features/voice-update/voiceUpdateFlow.css — namespaced styles.
- Create: frontend/tests/workReportDocumentInput.test.mjs — frontend contracts.

### Task 1: Build the bounded document-to-text service

**Files:**
- Create: bowei_ai_dashboard/app/services/work_report_document_text.py
- Create: bowei_ai_dashboard/tests/test_work_report_document_text.py
- Modify: bowei_ai_dashboard/requirements.txt

- [ ] **Step 1: Write parser tests first**

~~~python
from io import BytesIO
import pytest
from docx import Document
from openpyxl import Workbook
from pptx import Presentation
from app.services.work_report_document_text import (
    MAX_DOCUMENT_BYTES, WorkReportDocumentTextError,
    extract_work_report_document_text,
)

def make_docx() -> bytes:
    document = Document()
    document.add_paragraph("完成接口联调")
    row = document.add_table(rows=1, cols=2).rows[0].cells
    row[0].text, row[1].text = "风险", "等待供应商文档"
    out = BytesIO(); document.save(out)
    return out.getvalue()

def test_extracts_docx_paragraphs_and_table_cells():
    text = extract_work_report_document_text("weekly.docx", make_docx())
    assert "完成接口联调" in text
    assert "风险\t等待供应商文档" in text

def test_extracts_xlsx_sheet_and_nonempty_cells():
    wb = Workbook(); ws = wb.active; ws.title = "周报"; ws.append(["本次完成", "联调"])
    out = BytesIO(); wb.save(out)
    text = extract_work_report_document_text("weekly.xlsx", out.getvalue())
    assert "[周报]" in text and "本次完成\t联调" in text

def test_extracts_pptx_slide_text_and_table_cells():
    deck = Presentation(); slide = deck.slides.add_slide(deck.slide_layouts[5])
    slide.shapes.add_textbox(0, 0, 3000000, 300000).text_frame.text = "下周计划"
    table = slide.shapes.add_table(1, 2, 0, 400000, 3000000, 300000).table
    table.cell(0, 0).text, table.cell(0, 1).text = "任务", "UAT"
    out = BytesIO(); deck.save(out)
    text = extract_work_report_document_text("weekly.pptx", out.getvalue())
    assert "[第 1 页]" in text and "任务\tUAT" in text

def test_rejects_empty_unsupported_and_oversized_files():
    with pytest.raises(WorkReportDocumentTextError, match="为空"):
        extract_work_report_document_text("weekly.docx", b"")
    with pytest.raises(WorkReportDocumentTextError, match="仅支持"):
        extract_work_report_document_text("weekly.doc", b"legacy")
    with pytest.raises(WorkReportDocumentTextError, match="20 MB"):
        extract_work_report_document_text("weekly.pdf", b"x" * (MAX_DOCUMENT_BYTES + 1))
~~~

- [ ] **Step 2: Verify the test fails before implementation**

Run: python -m pytest bowei_ai_dashboard/tests/test_work_report_document_text.py -q

Expected: collection fails because the parser module does not exist.

- [ ] **Step 3: Add the dependency and minimal parser contract**

Add this exact line after python-docx==1.2.0:

~~~text
python-pptx==1.0.2
~~~

Implement:

~~~python
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
MAX_EXTRACTED_CHARS = 5_000
ALLOWED_SUFFIXES = {".docx", ".pdf", ".xlsx", ".pptx"}

class WorkReportDocumentTextError(ValueError):
    pass

def extract_work_report_document_text(filename: str, content: bytes) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise WorkReportDocumentTextError("仅支持 Word、PDF、Excel、PPT 文档")
    if not content:
        raise WorkReportDocumentTextError("文档内容为空")
    if len(content) > MAX_DOCUMENT_BYTES:
        raise WorkReportDocumentTextError("文档不能超过 20 MB")
    # Dispatch, normalize whitespace, reject empty and over-5000-character text.
~~~

Use Document(BytesIO(content)), PdfReader(BytesIO(content)), load_workbook(BytesIO(content), read_only=True, data_only=True), and Presentation(BytesIO(content)). Include DOCX table cells, Excel sheet headings and nonempty cell rows, and PowerPoint shape/table text. Convert invalid or encrypted parser errors to WorkReportDocumentTextError with the message 文档无法解析，请确认文件未损坏且未加密. Do not write to disk, evaluate formulas, execute macros, or read external links.

- [ ] **Step 4: Verify focused parser tests pass**

Run: python -m pytest bowei_ai_dashboard/tests/test_work_report_document_text.py -q

Expected: all tests pass.

- [ ] **Step 5: Commit the parser unit**

~~~bash
git add bowei_ai_dashboard/requirements.txt bowei_ai_dashboard/app/services/work_report_document_text.py bowei_ai_dashboard/tests/test_work_report_document_text.py
git commit -m "feat: extract work report document text"
~~~

### Task 2: Add the stateless upload endpoint and canonical source type

**Files:**
- Modify: bowei_ai_dashboard/app/routers/updates.py
- Modify: bowei_ai_dashboard/app/domain/source_type.py
- Create: bowei_ai_dashboard/tests/test_updates_document_upload.py

- [ ] **Step 1: Add failing endpoint tests**

~~~python
def test_document_text_endpoint_requires_login(client):
    response = client.post(
        "/api/updates/extract-document-text",
        files={"file": ("weekly.docx", b"not-a-document",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 401

def test_document_text_endpoint_returns_text_without_creating_submission(auth_client, monkeypatch, db):
    monkeypatch.setattr(
        "app.routers.updates.extract_work_report_document_text",
        lambda filename, content: "完成接口联调",
    )
    before = db.query(models.UpdateSubmission).count()
    response = auth_client.post(
        "/api/updates/extract-document-text",
        files={"file": ("weekly.docx", b"document",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200
    assert response.json() == {
        "filename": "weekly.docx", "text": "完成接口联调",
        "char_count": 6, "source_type": "document",
    }
    assert db.query(models.UpdateSubmission).count() == before
~~~

- [ ] **Step 2: Verify the tests fail**

Run: python -m pytest bowei_ai_dashboard/tests/test_updates_document_upload.py -q

Expected: endpoint returns 404.

- [ ] **Step 3: Implement the route without persistence**

In source_type.py add DOCUMENT = "document", display label 文档解析, aliases 文档解析/document/file, add it to _ALIASES_BY_KEY, and add:

~~~python
def is_document(value: str | None) -> bool:
    return normalize(value) == DOCUMENT
~~~

In updates.py import File, UploadFile, the parser and its error. Add this route before the existing /extract route:

~~~python
@router.post("/extract-document-text")
async def extract_document_text(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    require_login(current_user, db)
    filename = (file.filename or "").strip()
    content = await file.read()
    try:
        text = extract_work_report_document_text(filename, content)
    except WorkReportDocumentTextError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "filename": filename, "text": text, "char_count": len(text),
        "source_type": ST.DOCUMENT,
    }
~~~

The route does not receive project ID, call an LLM, or create ORM rows. Existing /extract remains the authorization authority for work/task candidates.

- [ ] **Step 4: Verify endpoint behavior**

Run: python -m pytest bowei_ai_dashboard/tests/test_updates_document_upload.py -q

Expected: authentication and no-write assertions pass.

- [ ] **Step 5: Commit the API unit**

~~~bash
git add bowei_ai_dashboard/app/routers/updates.py bowei_ai_dashboard/app/domain/source_type.py bowei_ai_dashboard/tests/test_updates_document_upload.py
git commit -m "feat: add work report document upload endpoint"
~~~

### Task 3: Create the typed frontend client and document hook

**Files:**
- Modify: frontend/src/api/updates.ts
- Create: frontend/src/features/voice-update/useVoiceDocumentUpload.ts
- Create: frontend/tests/workReportDocumentInput.test.mjs

- [ ] **Step 1: Add failing frontend contracts**

~~~javascript
test("document client posts one multipart file to the work-report endpoint", () => {
  const api = read("src/api/updates.ts")
  assert.match(api, /extractWorkReportDocumentText/)
  assert.match(api, /extract-document-text/)
  assert.match(api, /fd\.append\('file', file\)/)
})

test("document hook replaces text only after successful parsing and exposes removal state", () => {
  const hook = read("src/features/voice-update/useVoiceDocumentUpload.ts")
  assert.match(hook, /setText\(result\.text\)/)
  assert.match(hook, /function removeDocument\(\)/)
  assert.match(hook, /documentFileName/)
})
~~~

- [ ] **Step 2: Verify the contracts fail**

Run: node --test frontend/tests/workReportDocumentInput.test.mjs

Expected: API function and hook are missing.

- [ ] **Step 3: Implement typed upload and isolated state**

Add to updates.ts:

~~~ts
export type WorkReportDocumentTextResult = {
  filename: string
  text: string
  char_count: number
  source_type: "document"
}

export function extractWorkReportDocumentText(file: File): Promise<WorkReportDocumentTextResult> {
  const fd = new FormData()
  fd.append("file", file)
  return apiUpload<WorkReportDocumentTextResult>("/api/updates/extract-document-text", fd)
}
~~~

Import apiUpload. The hook exposes documentUploading, documentFileName, documentCharCount, documentInputRef, handleDocumentFile, and removeDocument. Reject files above 20 * 1024 * 1024 before requesting. Clear errors before upload, set status while pending, call setText(result.text) only after success, and preserve prior editable text on every failure. removeDocument clears only document metadata, never the editable text.

- [ ] **Step 4: Verify focused frontend tests pass**

Run: node --test frontend/tests/workReportDocumentInput.test.mjs

Expected: all contracts pass.

- [ ] **Step 5: Commit client and hook**

~~~bash
git add frontend/src/api/updates.ts frontend/src/features/voice-update/useVoiceDocumentUpload.ts frontend/tests/workReportDocumentInput.test.mjs
git commit -m "feat: add document input upload hook"
~~~

### Task 4: Add the fourth mode to the existing report UI

**Files:**
- Modify: frontend/src/features/voice-update/VoiceUpdateInputPanel.tsx
- Modify: frontend/src/pages/VoiceUpdatePage.tsx
- Modify: frontend/src/features/voice-update/useVoiceExtraction.ts
- Modify: frontend/src/features/voice-update/useVoiceSubmission.ts
- Modify: frontend/src/features/voice-update/voiceUpdateFlow.css
- Modify: frontend/tests/workReportDocumentInput.test.mjs

- [ ] **Step 1: Extend frontend contracts before UI work**

~~~javascript
test("work-report input exposes document as fourth source and accepts approved formats", () => {
  const input = read("src/features/voice-update/VoiceUpdateInputPanel.tsx")
  assert.match(input, /VoiceInputMode/)
  assert.match(input, /document/)
  assert.match(input, /上传文档/)
  assert.match(input, /\.docx,\.pdf,\.xlsx,\.pptx/)
  assert.match(input, /拖入文档，或点击选择/)
  assert.match(input, /文档解析内容/)
})

test("document origin uses the document label for extraction and submission", () => {
  assert.match(read("src/features/voice-update/useVoiceExtraction.ts"), /文档解析/)
  assert.match(read("src/features/voice-update/useVoiceSubmission.ts"), /文档解析/)
})

test("page wires document upload state into the shared editor", () => {
  const page = read("src/pages/VoiceUpdatePage.tsx")
  assert.match(page, /useVoiceDocumentUpload/)
  assert.match(page, /onDocumentFile/)
  assert.match(page, /documentUploading/)
})
~~~

- [ ] **Step 2: Verify new assertions fail**

Run: node --test frontend/tests/workReportDocumentInput.test.mjs

Expected: mode, panel, and source assertions fail.

- [ ] **Step 3: Implement approved UI and workflow integration**

Extend VoiceInputMode and MODE_OPTIONS:

~~~ts
{ key: "document", label: "上传文档", path: "M6 2h9l3 3v15H6zM15 2v4h4M9 11h6M9 15h6" }
~~~

Add document props to VoiceUpdateInputPanel. Its document branch includes a hidden file input accepting:

~~~text
.docx,.pdf,.xlsx,.pptx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.openxmlformats-officedocument.presentationml.presentation
~~~

Render a keyboard-operable drop zone and select button with the copy 拖入文档，或点击选择 and 支持 Word、PDF、Excel、PPT · 单个文件不超过 20 MB. After parsing, show filename, 已完成解析 · 已提取 N 字, an accessible remove button, and the editable textarea headed 文档解析内容 with helper 可编辑，AI 将据此提取.

In VoiceUpdatePage call useVoiceDocumentUpload with setText and setExtractionError. Merge documentUploading into controlsLocked, recording eligibility, and the existing uploading gate passed to canExtractVoiceUpdate. On report-range changes or starting a new report, call removeDocument. Switching tabs alone must not erase editable text.

In both existing hooks use this source mapping:

~~~ts
source_type: mode === "voice"
  ? "语音更新"
  : mode === "document"
    ? "文档解析"
    : "文字更新",
~~~

Add only component-scoped CSS selectors: .voice-update-document-dropzone, .is-dragging, .voice-update-document-file, .voice-update-document-status, and .voice-update-document-remove. Reuse existing radius, colors, focus ring and responsive rules.

- [ ] **Step 4: Verify frontend behavior and build**

Run: node --test frontend/tests/workReportDocumentInput.test.mjs frontend/tests/workReportFlowPage.test.mjs && npm --prefix frontend run build

Expected: node:test files pass and the production build has no TypeScript errors.

- [ ] **Step 5: Commit UI integration**

~~~bash
git add frontend/src/features/voice-update/VoiceUpdateInputPanel.tsx frontend/src/pages/VoiceUpdatePage.tsx frontend/src/features/voice-update/useVoiceExtraction.ts frontend/src/features/voice-update/useVoiceSubmission.ts frontend/src/features/voice-update/voiceUpdateFlow.css frontend/tests/workReportDocumentInput.test.mjs
git commit -m "feat: add document input to work reports"
~~~

### Task 5: Perform complete verification

**Files:**
- Modify: docs/superpowers/specs/2026-08-12-work-report-document-input-design.md only if implementation discovers and corrects a real difference from approved behavior.

- [ ] **Step 1: Run the complete automated check set**

~~~bash
python -m pytest bowei_ai_dashboard/tests/test_work_report_document_text.py bowei_ai_dashboard/tests/test_updates_document_upload.py -q
node --test frontend/tests/workReportDocumentInput.test.mjs frontend/tests/workReportFlowPage.test.mjs
npm --prefix frontend run build
~~~

Expected: every command exits 0.

- [ ] **Step 2: Manually exercise the acceptance path**

1. In 我的全部工作, upload one DOCX, PDF, XLSX, and PPTX; each produces editable text.
2. Upload DOC, an empty file, and a file over 20 MiB; each reports a readable error and preserves old text.
3. Click AI 提取; suggestions only use the authenticated user candidate pool and uncertain matches remain reviewable.
4. Submit after review; history labels the report 文档解析 and no task changes before the AI confirmation workflow.
5. Remove the document row or switch input source; metadata clears and editable text stays.

- [ ] **Step 3: Inspect final state**

Run: git diff --check HEAD~4..HEAD && git status --short

Expected: no whitespace errors; remaining unrelated changes are pre-existing user work.

- [ ] **Step 4: Commit design alignment only when needed**

~~~bash
git add docs/superpowers/specs/2026-08-12-work-report-document-input-design.md
git commit -m "docs: align work report document input design"
~~~

Do not run this commit if implementation did not change the approved design.
