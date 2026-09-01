# Complex Workbook Vision Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give high-risk project-init Excel workbooks a verified DeepSeek Vision route while retaining deterministic table extraction and safe review fallbacks.

**Architecture:** A bounded renderer turns visible workbook sheets into temporary PNG images. An opted-in DeepSeek Vision adapter submits the images inline and returns the existing evidence-bound draft envelope. The analysis worker only uses vision for high-risk workbooks that were not fully resolved by deterministic rows; failures retain the text-with-review route.

**Tech Stack:** Python 3.14, openpyxl, Pillow, OpenAI Python SDK, FastAPI, SQLAlchemy, pytest, React/Vitest.

---

### Task 1: Deterministic workbook-image renderer

**Files:**
- Create: `bowei_ai_dashboard/app/services/project_init_workbook_renderer.py`
- Test: `bowei_ai_dashboard/tests/test_project_init_workbook_renderer.py`

- [ ] Write failing tests for visible-sheet rendering, hidden-sheet exclusion, merged-cell values, and image-count/pixel limits.
- [ ] Run `& .\.venv\Scripts\python.exe -m pytest tests/test_project_init_workbook_renderer.py -q`; expect import failure.
- [ ] Implement `render_workbook_images(path, output_directory, *, max_images=8)` with `openpyxl` and Pillow. It must render only visible sheets, cap cells, rows, columns and dimensions, and return PNG paths without logging source values.
- [ ] Run the focused renderer test; expect pass.
- [ ] Commit only its service and test files with message `feat: render bounded workbook images`.

### Task 2: Vision model opt-in and image adapter

**Files:**
- Modify: `bowei_ai_dashboard/app/ai/adapters.py`
- Modify: `bowei_ai_dashboard/app/ai/service.py`
- Test: `bowei_ai_dashboard/tests/test_ai_adapters.py`
- Test: `bowei_ai_dashboard/tests/test_ai_service.py`

- [ ] Write failing tests: an opted-in DeepSeek model sends `file_data` as an inline PNG data URL; a non-opted-in model raises `AICapabilityNotConfigured`; API keys and file IDs do not enter logs.
- [ ] Run `& .\.venv\Scripts\python.exe -m pytest tests/test_ai_adapters.py tests/test_ai_service.py -q`; expect missing methods/failures.
- [ ] Add `complete_images` and `invoke_project_init_vision`. Permit only enabled DeepSeek chat models with `vision_workbook_analysis: true`, set the model from `vision_model` or `deepseek-v4-flash-vision-exp`, and send `file` content parts using inline base64 PNG data.
- [ ] Run focused adapter/service tests; expect pass.
- [ ] Commit only adapter, service, and their tests with message `feat: add opted-in DeepSeek workbook vision adapter`.

### Task 3: Evidence-bound vision analysis route

**Files:**
- Create: `bowei_ai_dashboard/app/services/project_init_vision_analysis.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_analysis.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_analysis_routing.py`
- Test: `bowei_ai_dashboard/tests/test_project_init_vision_analysis.py`
- Test: `bowei_ai_dashboard/tests/test_project_init_analysis.py`

- [ ] Write failing tests for: high-risk non-tabular workbooks use `vision_with_review`; image files are removed after success and failure; unavailable vision retains `text_with_review`.
- [ ] Run `& .\.venv\Scripts\python.exe -m pytest tests/test_project_init_vision_analysis.py tests/test_project_init_analysis.py -q`; expect missing route failures.
- [ ] Implement `generate_project_init_vision_draft(images, people, tasks, *, ai_service, context)` using the existing strict `ProjectInitAiResult` validation and local source-evidence catalog. The worker must skip vision when `structured_spreadsheet` was used, clean its temporary directory in `finally`, and retain the current parser+AI fallback on error.
- [ ] Run worker-route tests; expect pass.
- [ ] Commit only the vision service, routing/worker changes, and their tests with message `feat: analyze complex workbooks through vision review route`.

### Task 4: Reviewer-visible result and regression

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitAiPanel.tsx`
- Modify: `frontend/src/features/settings/OwnerSubmitAiPanel.retry.test.tsx`
- Test: backend files listed above

- [ ] Write a failing UI test that expects `复杂 Excel 已通过视觉分析生成候选，请复核后应用。` for `analysis_route.mode === 'vision_with_review'`.
- [ ] Run `npm run test:unit -- OwnerSubmitAiPanel.retry.test.tsx`; expect failure.
- [ ] Extend `analysisReviewNotice` with the visual route message.
- [ ] Run backend verification:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests/test_project_init_ai_agent.py tests/test_project_init_analysis.py tests/test_project_init_attachment_storage.py tests/test_project_init_workbook_profile.py tests/test_project_init_analysis_routing.py tests/test_project_init_workbook_renderer.py tests/test_project_init_vision_analysis.py -q
```

- [ ] Run frontend verification:

```powershell
npm run test:unit -- OwnerSubmitAiPanel.retry.test.tsx
npm run build
```

- [ ] Commit only the panel and its test with message `feat: show workbook vision review route`.
