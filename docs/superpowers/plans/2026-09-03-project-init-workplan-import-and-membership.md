# Project-init Workplan Import and Membership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reliably import explicit Excel work-progress tables, bind active organization people, and add matched non-members only when the owner submits the project plan.

**Architecture:** Analysis snapshots active people and their project-membership state. A deterministic Excel converter runs before chat analysis and emits a non-blocking `will_join_project` signal. The existing owner-submit transaction remains the sole writer of `project_members` and task assignments.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, openpyxl, React, TypeScript, pytest, Vitest.

---

## File map

- `bowei_ai_dashboard/app/services/project_init_analysis.py` — active-person snapshot.
- `bowei_ai_dashboard/app/services/project_init_ai_agent.py` — workbook row conversion and matching state.
- `bowei_ai_dashboard/tests/test_project_init_analysis.py` — snapshot regression.
- `bowei_ai_dashboard/tests/test_project_init_ai_agent.py` — actual workplan-shape regression.
- `frontend/src/features/settings/ownerSubmitDraft.ts` — informational warning filtering.
- `frontend/src/features/settings/OwnerSubmitAiPanel.tsx` — pending-join presentation and deterministic-processor label.
- `frontend/src/features/settings/ownerSubmitDraft.test.ts`, `OwnerSubmitAiPanel.retry.test.tsx` — focused UI checks.

### Task 1: Snapshot active organization people

**Files:**

- Modify: `bowei_ai_dashboard/app/services/project_init_analysis.py:96-153`
- Modify: `bowei_ai_dashboard/tests/test_project_init_analysis.py:70-105`

- [ ] **Step 1: Write the failing snapshot test**

Create active `杨宇帆` without a `ProjectMember` row, create a run, and assert both people occur in the frozen snapshot with distinct membership flags.

```python
def test_create_run_snapshot_marks_active_organization_people(monkeypatch):
    from app.routers import project_init_ai
    db = make_session()
    project, owner = add_project_graph(db)
    db.add_all([
        models.Person(id=99, name="杨宇帆", is_active=True),
        models.Account(username="owner", password_hash="x", person_id=owner.id, status="active"),
    ])
    add_attachment(db, project_id=project.id, attachment_id=10)
    db.commit()
    response = project_init_ai.create_project_init_analysis_run(
        project.id, schemas.ProjectInitAnalysisCreate(attachment_ids=[10], current_draft=[]),
        SimpleNamespace(add_task=lambda *_: None), "owner", db,
    )
    snapshot = json.loads(db.get(models.ProjectInitAnalysisRun, response["id"]).snapshot_json)
    people = {item["name"]: item for item in snapshot["people"]}
    assert people[owner.name]["is_project_member"] is True
    assert people["杨宇帆"]["is_project_member"] is False
```

- [ ] **Step 2: Confirm the current membership-only query fails**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_project_init_analysis.py::test_create_run_snapshot_marks_active_organization_people -q`

Expected: FAIL because the snapshot does not contain `杨宇帆`.

- [ ] **Step 3: Implement only snapshot expansion**

Replace `Person.id.in_(member_ids)` with the active-person query; leave `members` unchanged and add the marker only to serialized candidates.

```python
people = (db.query(models.Person).filter(models.Person.is_active.is_(True))
          .order_by(models.Person.id.asc()).all())

def _snapshot_person(person: models.Person) -> dict[str, Any]:
    value = crud.to_dict(person)
    value["is_project_member"] = person.id in member_ids
    return value

# returned snapshot key
"people": [_snapshot_person(person) for person in people],
```

- [ ] **Step 4: Verify and commit**

Run the Step 2 command; expected PASS. Commit: `git add bowei_ai_dashboard/app/services/project_init_analysis.py bowei_ai_dashboard/tests/test_project_init_analysis.py && git commit -m "fix: snapshot active people for project init analysis"`.

### Task 2: Deterministically import multiline workplan rows

**Files:**

- Modify: `bowei_ai_dashboard/app/services/project_init_ai_agent.py:45-81, 151-220, 1091-1191`
- Modify: `bowei_ai_dashboard/tests/test_project_init_ai_agent.py:898-998`

- [ ] **Step 1: Write the failing end-to-end workbook regression**

Create a production-shaped workbook with `目标/重点工作/评价标准/序号/关键任务/责任人/计划开始时间/计划结束时间/协同人`, a multiline target cell, merged “重点工作”, and “吴肖、郭熠彬” in responsibility. Pass active people where 吴肖 is a member and 郭熠彬、温会林、刘万超 are not. The LLM callback must raise if invoked. Assert:

```python
assert result.model_name == "structured-spreadsheet"
assert (first.assignee_name, first.assignee_id) == ("吴肖", 5)
assert first.helper_names == ["郭熠彬", "温会林"]
assert first.helper_ids == [7, 9]
assert (first.plan_start, first.plan_end) == ("2026-07-03", "2026-07-10")
assert {warning.code for warning in first.warnings} == {"will_join_project"}
```

- [ ] **Step 2: Run the one regression**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_project_init_ai_agent.py::test_multiline_merged_workplan_uses_structured_import -q`

Expected: FAIL with `chat analysis must not run`, proving `splitlines()[1]` loses the actual tabular row after the embedded newline.

- [ ] **Step 3: Preserve the serialized row and explicit dates**

Add non-overlapping start/end aliases, then use the first newline only. Explicit valid dates override the legacy one-column date parser.

```python
_WORK_PLAN_HEADER_ALIASES.update({
    "计划开始": {"计划开始时间", "计划开始日期"},
    "计划结束": {"计划结束时间", "计划结束日期"},
})

header_line, separator, values_line = str(text or "").partition("\n")
if not separator or "\t" not in header_line or "\t" not in values_line:
    continue
headers = [item.strip() for item in header_line.split("\t")]
values = [item.strip() for item in values_line.split("\t")]

def _explicit_spreadsheet_date(value: str) -> str:
    match = re.match(r"^(\d{4}-\d{2}-\d{2})(?:T\d{2}:\d{2}:\d{2})?$", str(value or "").strip())
    return match.group(1) if match and _is_calendar_date(match.group(1)) else ""

fallback_start, fallback_end = _spreadsheet_plan_dates(row.get("计划时间", ""))
plan_start = _explicit_spreadsheet_date(row.get("计划开始", "")) or fallback_start
plan_end = _explicit_spreadsheet_date(row.get("计划结束", "")) or fallback_end
```

- [ ] **Step 4: Split responsibility and signal membership additions**

Pass `people` into `_structured_spreadsheet_rows`. Select the first uniquely active responsibility name as assignee, then append remaining responsibility names and “协同人” in order; keep unresolved values for deterministic warnings.

```python
responsible_names = _split_helper_names(row.get("负责人", ""))
matched = [name for name in responsible_names if _match_person(name, people)[0] is not None]
assignee_name = matched[0] if matched else (responsible_names[0] if responsible_names else coordinator)
helper_names = _dedupe_strings([
    *(name for name in responsible_names if name != assignee_name),
    *_split_helper_names(row.get("协同成员", "")),
])
```

Extend `PersonCandidate` and `_person_candidates` with `is_project_member: bool = True`. On a unique active non-member, `_match_person` returns its ID plus `_warning("will_join_project", name)` with message `提交项目方案时将自动加入项目`; it must not be blocking.

- [ ] **Step 5: Verify only the regression pair and commit**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_project_init_ai_agent.py::test_multiline_merged_workplan_uses_structured_import tests/test_project_init_ai_agent.py::test_merged_alias_header_workbook_is_extracted_end_to_end_without_ai -q`

Expected: PASS. Commit: `git add bowei_ai_dashboard/app/services/project_init_ai_agent.py bowei_ai_dashboard/tests/test_project_init_ai_agent.py && git commit -m "fix: deterministically import multiline workplans"`.

### Task 3: Render pending project joins as information

**Files:**

- Modify: `frontend/src/features/settings/ownerSubmitDraft.ts:35-43, 368-381`
- Modify: `frontend/src/features/settings/OwnerSubmitAiPanel.tsx:137-153, 612-615`
- Modify: `frontend/src/features/settings/ownerSubmitDraft.test.ts`
- Modify: `frontend/src/features/settings/OwnerSubmitAiPanel.retry.test.tsx`

- [ ] **Step 1: Write focused failing front-end checks**

In `ownerSubmitDraft.test.ts`, give a valid subtask a `will_join_project` warning; its ID must stay in the draft and the information signal must stay out of preview warnings. In the panel test, mock a completed analysis result with the same warning after upload; assert `提交时自动加入项目` appears without `未自动绑定`.

```ts
const pendingJoin = { code: 'will_join_project', message: '提交项目方案时将自动加入项目', person_name: '郭熠彬' }
const preview = buildAiMergePreview([], { tasks: [aiTask({ subtasks: [{ ...aiTask().subtasks[0], warnings: [pendingJoin] }] })] }, [], { knownMemberIds: [7, 8, 9] })
expect((preview.draft[0].subtasks[0] as any).assignee_id).toBe(8)
expect(preview.warnings.join(' ')).not.toContain('will_join_project')
```

- [ ] **Step 2: Confirm the current UI fails the information-message expectation**

Run: `cd frontend; npm run test:unit -- src/features/settings/ownerSubmitDraft.test.ts src/features/settings/OwnerSubmitAiPanel.retry.test.tsx`

Expected: FAIL before classification is changed.

- [ ] **Step 3: Partition informational and blocking warning rendering**

Filter `will_join_project` from `collectWarnings`; keep ID validation unchanged. In `OwnerSubmitAiPanel`, render pending joins in blue without `role="alert"` or `（未自动绑定）`, and retain the existing yellow alert for all other warnings.

```ts
const INFORMATIONAL_PERSON_WARNINGS = new Set(['will_join_project'])
const isInformationalWarning = (warning: { code?: unknown }) =>
  INFORMATIONAL_PERSON_WARNINGS.has(String(warning.code ?? ''))
const pendingJoinWarnings = item.warnings.filter(isInformationalWarning)
const blockingWarnings = item.warnings.filter((warning) => !isInformationalWarning(warning))
```

`ModelUsageSummary` must also render `result_metadata.model_name` when `attempted_models` is empty. This is the truthful “实际模型” label for `local-rule / structured-spreadsheet`; a chat model remains preferred whenever an attempted-model record exists.

- [ ] **Step 4: Verify the minimal UI and existing submit transaction, then commit**

Re-run the Step 2 command; expected PASS. Then run: `cd ..\bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_project_init_work_progress_draft.py::test_owner_submit_adds_selected_people_to_project_and_snapshots_names -q`

Expected: PASS—the existing transaction already creates missing `project_members` for valid selected IDs. Commit: `git add frontend/src/features/settings/ownerSubmitDraft.ts frontend/src/features/settings/ownerSubmitDraft.test.ts frontend/src/features/settings/OwnerSubmitAiPanel.tsx frontend/src/features/settings/OwnerSubmitAiPanel.retry.test.tsx && git commit -m "feat: show pending project member additions"`.

### Task 4: Minimal acceptance on local services

**Files:** No code changes.

- [ ] **Step 1: Re-analyze only `工作推进表2.xlsx` as 吴肖**

At `http://127.0.0.1:6004`, open `test1` and create a new analysis run; historical runs are immutable.

- [ ] **Step 2: Check before submission**

Confirm `structured-spreadsheet` rather than DeepSeek; correct Sheet1 evidence; 吴肖 as responsible with 郭熠彬 as collaborator; recognized organization people saying `提交时自动加入项目`; and role labels (`项目经理`, `全员`) still unresolved without IDs.

- [ ] **Step 3: Apply and submit once, then stop**

Confirm matched former non-members become project `member` rows and saved task names/IDs equal the preview. Do not run repository-wide pytest, full Vitest, or unrelated browser checks: the targeted commands above plus this one flow are the complete requested acceptance set.
