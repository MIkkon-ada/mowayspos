# 项目初始化导入规范化 Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:executing-plans task-by-task. Steps use checkbox syntax.

**Goal:** Make Excel drafts preserve start-only dates, use row-level evidence, avoid duplicated parent text, and safely create/bind imported people at owner submission.

**Architecture:** The parser emits contextual source chunks per populated Excel row. The AI-agent normalizes dates and duplicate parent text after model output. The owner-submit API resolves raw names before validation, creates only clearly personal names, and uses the existing project-member save path.

**Tech Stack:** Python/FastAPI, SQLAlchemy, Pydantic, pytest, React/TypeScript, Vitest.

---

### Task 1: Row-level Excel evidence

**Files:**

- Modify: bowei_ai_dashboard/app/services/project_init_file_parser.py:705-758
- Modify: bowei_ai_dashboard/tests/test_project_init_file_parser.py

- [ ] **Step 1: Write the failing test**

```python
def test_xlsx_parser_emits_each_data_row_with_header_context(tmp_path):
    path = _write_xlsx(tmp_path, [["专项", "关键任务"], ["知识资产AI化", "修订标签"], ["平台预研", "技术选型"]])
    chunks = list(parse_project_init_file(path, "推进表.xlsx"))
    assert [(chunk.location, chunk.text) for chunk in chunks] == [
        ("'Sheet'!A2:B2", "专项\t关键任务\n知识资产AI化\t修订标签"),
        ("'Sheet'!A3:B3", "专项\t关键任务\n平台预研\t技术选型"),
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: pytest bowei_ai_dashboard/tests/test_project_init_file_parser.py::test_xlsx_parser_emits_each_data_row_with_header_context -q

Expected: FAIL because the parser currently emits one A1:B3 chunk for the entire worksheet.

- [ ] **Step 3: Write minimal implementation**

Replace the single _worksheet_chunk output for XLS/XLSX with a row iterator that uses the first non-empty row as headings, skips blank rows, emits each subsequent populated row as SourceChunk(original_name, "'Sheet'!A2:B2", header_and_row_text), and retains the existing one-chunk fallback for sheets with no data rows.

- [ ] **Step 4: Run test to verify it passes**

Run: pytest bowei_ai_dashboard/tests/test_project_init_file_parser.py -q

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bowei_ai_dashboard/app/services/project_init_file_parser.py bowei_ai_dashboard/tests/test_project_init_file_parser.py
git commit -m "feat: emit row-level project-init Excel evidence"
```

### Task 2: Normalize start-only dates and duplicate parent descriptions

**Files:**

- Modify: bowei_ai_dashboard/app/services/project_init_ai_agent.py:503-545, 640-683
- Modify: bowei_ai_dashboard/tests/test_project_init_ai_agent.py

- [ ] **Step 1: Write the failing tests**

```python
def test_generated_draft_moves_start_only_month_from_end_to_full_start_date():
    result = generate_project_init_draft([chunk("专项\t关键任务\t计划时间\n知识资产\t修订标签\t2026-06")], people(), [], llm_call=lambda *_: ai_payload(plan_start="", plan_end="2026-06"))
    assert result.tasks[0].plan_start == "2026-06-01"
    assert result.tasks[0].plan_end == ""

def test_generated_draft_removes_parent_description_that_repeats_first_subtask():
    result = generate_project_init_draft([chunk("专项\t关键任务\n知识资产\t修订标签")], people(), [], llm_call=lambda *_: ai_payload(description="修订标签", subtask_title="修订标签"))
    assert result.tasks[0].description == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: pytest bowei_ai_dashboard/tests/test_project_init_ai_agent.py -k "start_only_month or repeats_first_subtask" -q

Expected: FAIL because plan_end remains 2026-06 and the duplicate description survives.

- [ ] **Step 3: Write minimal implementation**

Add a post-model normalization helper called from task reconciliation: when plan_start is empty and plan_end is a single ISO month or ISO date, move it to plan_start; normalize YYYY-MM to YYYY-MM-01; leave an explicitly supplied end date intact when a start date is present. Clear a parent description only when its normalized text equals the first subtask title. Update the extraction prompt to map 专项 to task title, 关键任务 to subtasks, and 关键成果/完成标准 to parent description.

- [ ] **Step 4: Run test to verify it passes**

Run: pytest bowei_ai_dashboard/tests/test_project_init_ai_agent.py -q

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bowei_ai_dashboard/app/services/project_init_ai_agent.py bowei_ai_dashboard/tests/test_project_init_ai_agent.py
git commit -m "fix: normalize project-init start-only dates"
```

### Task 3: Resolve and create safe imported people at owner submission

**Files:**

- Modify: bowei_ai_dashboard/app/routers/projects.py:104-160, 2428-2462
- Modify: bowei_ai_dashboard/tests/test_project_init_work_progress_draft.py

- [ ] **Step 1: Write the failing tests**

```python
def test_owner_submit_creates_unlisted_person_and_adds_them_to_project():
    payload = _payload(assignee="杨宇帆", assignee_id=None, helper="袁金玉")
    owner_submit_project_profile(1, payload, current_user="owner", db=db)
    people = {row.name: row for row in db.query(models.Person).all()}
    assert people["杨宇帆"].system_role == "normal_member"
    assert db.query(models.ProjectMember).filter_by(project_id=1, person_id=people["杨宇帆"].id, role="member").one()
    assert db.query(models.SubTask).one().assignee_id == people["杨宇帆"].id

@pytest.mark.parametrize("raw_name", ["各项目经理", "咨询部", "mowasyadmin"])
def test_owner_submit_does_not_create_roles_departments_or_account_aliases(raw_name):
    with pytest.raises(HTTPException, match="请选择关键任务负责人"):
        owner_submit_project_profile(1, _payload(assignee=raw_name, assignee_id=None), current_user="owner", db=db)
    assert db.query(models.Person).filter_by(name=raw_name).count() == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: pytest bowei_ai_dashboard/tests/test_project_init_work_progress_draft.py -k "creates_unlisted or does_not_create" -q

Expected: FAIL because unselected raw names are rejected before they are resolved.

- [ ] **Step 3: Write minimal implementation**

Add a transaction-scoped resolver before _validate_work_progress_draft. Normalize names, reuse active people by normalized name, add existing people to the current project as member when needed, create a new active Person(name=..., system_role="normal_member") without an Account only for 2–8-character Chinese personal names, then assign IDs to task owners, subtask assignees, and comma/Chinese-list helpers. Reject role, department, generic-group, and Latin account-alias text with the existing missing-assignee validation; never grant owner/coach/admin project roles. Reuse _save_work_progress_draft and roll back all created rows if submission fails.

- [ ] **Step 4: Run test to verify it passes**

Run: pytest bowei_ai_dashboard/tests/test_project_init_work_progress_draft.py -q

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bowei_ai_dashboard/app/routers/projects.py bowei_ai_dashboard/tests/test_project_init_work_progress_draft.py
git commit -m "feat: create safe imported project members"
```

### Task 4: Let the owner-submit UI defer raw names to the server

**Files:**

- Modify: frontend/src/features/settings/OwnerSubmitModal.tsx:765-790
- Modify: bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py

- [ ] **Step 1: Write the failing frontend contract test**

```python
def test_owner_submit_ui_allows_raw_assignee_name_for_server_resolution():
    source = _frontend_source("features/settings/OwnerSubmitModal.tsx")
    assert "!subtask.assignee_id && !subtask.assignee.trim()" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: pytest bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py -q

Expected: FAIL because the UI currently rejects every missing assignee ID, even when it has a raw imported name.

- [ ] **Step 3: Write minimal implementation**

Change only the pre-submit guard to reject a subtask when both assignee_id and trimmed assignee are absent. Keep the server as the source of truth; it either binds/creates a safe person or returns the existing validation error. Update the error text to explain that named imported people will be resolved automatically at submission.

- [ ] **Step 4: Run test to verify it passes**

Run: pytest bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py -q; npm --prefix frontend run test -- --run OwnerSubmitModal

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/settings/OwnerSubmitModal.tsx bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py
git commit -m "fix: defer imported people resolution to submission"
```

### Task 5: Verify the combined flow

- [ ] **Step 1: Run focused backend regression suite**

Run: pytest bowei_ai_dashboard/tests/test_project_init_file_parser.py bowei_ai_dashboard/tests/test_project_init_ai_agent.py bowei_ai_dashboard/tests/test_project_init_work_progress_draft.py bowei_ai_dashboard/tests/test_project_init_work_progress_frontend.py -q

Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run: npm --prefix frontend run build

Expected: exit code 0.

- [ ] **Step 3: Review scope before final commit**

Run: git diff --check; git status --short; git log --oneline -4

Expected: no whitespace errors; only feature files and pre-existing user changes remain visible.

### Task 6: Complete subtask start-only normalization and parent-description fallback

**Files:**

- Modify: `bowei_ai_dashboard/app/services/project_init_ai_agent.py:519-583`
- Modify: `bowei_ai_dashboard/tests/test_project_init_ai_agent.py`

- [x] **Step 1: Write failing regression tests**

```python
def test_reconciles_subtask_end_only_month_as_full_start_date():
    payload = raw_task()
    payload["subtasks"][0].update({"plan_start": "", "plan_end": "2026-06"})
    result = generate_project_init_draft([chunk("计划时间\\n2026-06")], people(), [], llm_call=fake_llm({"tasks": [payload]}))
    assert (result.tasks[0].subtasks[0].plan_start, result.tasks[0].subtasks[0].plan_end) == ("2026-06-01", "")

def test_reconciles_empty_parent_description_from_first_subtask_completion_standard():
    payload = raw_task()
    payload["description"] = ""
    payload["subtasks"][0]["evaluation_standard"] = "交付首版并完成验收"
    result = generate_project_init_draft([chunk("关键成果\\n交付首版")], people(), [], llm_call=fake_llm({"tasks": [payload]}))
    assert result.tasks[0].description == "交付首版并完成验收"
```

- [x] **Step 2: Run the tests to verify RED**

Run: `& .\\.venv\\Scripts\\python.exe -m pytest -q tests/test_project_init_ai_agent.py -k "subtask_end_only or empty_parent_description"`

Expected: FAIL because only the task-level date fields are normalized and an empty parent description is kept empty.

- [x] **Step 3: Implement the deterministic reconciliation**

Create or reuse one date-normalization helper for task and subtask payloads. It moves a valid end-only `YYYY-MM` to `plan_start` as `YYYY-MM-01` and clears `plan_end`; it must not overwrite a nonempty start. During task reconciliation, after duplicate-title suppression, populate an otherwise empty parent description from the first nonempty subtask `evaluation_standard`. Do not invent text or alter nonempty descriptions.

- [x] **Step 4: Run the focused suite to verify GREEN**

Run: `& .\\.venv\\Scripts\\python.exe -m pytest -q tests/test_project_init_ai_agent.py tests/test_project_init_work_progress_draft.py`

Expected: PASS.

- [x] **Step 5: Commit; restart the local backend before browser verification**

```powershell
git add bowei_ai_dashboard/app/services/project_init_ai_agent.py bowei_ai_dashboard/tests/test_project_init_ai_agent.py docs/superpowers/plans/2026-08-30-project-init-import-normalization.md
git commit -m "fix: normalize imported subtask dates"
```

The implementing agent commits this task; the coordinating agent restarts the local backend so the already-correct row-level Excel parser and this reconciliation code are both active before a fresh browser analysis run.
