# Backend Project Name Compatibility Containment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` in the current session task-by-task. Do not delegate to subagents for this repository.

**Goal:** Move project-name fallback parsing into `app.compatibility` while preserving ID-first resolution and every existing public field.

**Architecture:** `compatibility/project_names.py` owns the current resolver implementation. Production callers import that adapter directly; database models and schemas retain historical fields as contract definitions, not identity sources. A temporary service re-export is removed only after all production imports migrate.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, pytest.

---

## File structure

- Create: `bowei_ai_dashboard/app/compatibility/project_names.py`
- Create: `bowei_ai_dashboard/tests/test_project_name_compatibility_containment.py`
- Modify then delete: `bowei_ai_dashboard/app/services/project_resolution.py`
- Modify: every production file returned by `rg -l "services.project_resolution" bowei_ai_dashboard/app -g "*.py"`
- Modify: `bowei_ai_dashboard/app/routers/tasks.py`, `issues.py`, `achievements.py`, `meetings.py`

### Task 1: Fix resolver behavior and boundary with failing tests

- [ ] **Step 1: Add direct compatibility behavior tests.**

Create `tests/test_project_name_compatibility_containment.py` using a fresh SQLite `Base.metadata.create_all` fixture with Project 1 named `Current` and Project 2 named `Historical`. Import `resolve_project_context` from `app.compatibility.project_names`. Assert an input of `project_id=1, special_project='Historical'` returns ID 1 and source `project_id`; assert name-only `special_project='Historical'` returns ID 2; assert invalid `project_id=99, special_project='Current'` returns invalid and does not fall back; assert two distinct name hints return `is_conflict is True` and `needs_manual_review is True`.

- [ ] **Step 2: Add a source boundary test.**

Read source with `Path.read_text`. Assert `compatibility/project_names.py` exists and contains `_NAME_KEYS`; assert `services/project_resolution.py` has no `_NAME_KEYS`, `_project_by_name`, or `json.loads`; assert the four target Routers import `compatibility.project_names` and do not define `_NAME_KEYS`.

- [ ] **Step 3: Run red tests.**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_name_compatibility_containment.py -q
```

Expected: FAIL because the compatibility module does not exist and Router imports still point to the service module.

- [ ] **Step 4: Commit the failing contract.**

```powershell
git add bowei_ai_dashboard/tests/test_project_name_compatibility_containment.py
git diff --cached --check
git commit -m "test: define project name compatibility containment"
```

### Task 2: Move resolver ownership without behavior changes

- [ ] **Step 1: Move the complete implementation.**

Copy the complete current implementation of `_NAME_KEYS`, coercion helpers, `resolve_project_context` and `resolve_project_id` into `app/compatibility/project_names.py`. Preserve function signatures, ordering, return keys and warning text byte-for-byte where practical. Do not add a new lookup policy.

- [ ] **Step 2: Replace the service implementation with a temporary re-export.**

```python
from ..compatibility.project_names import resolve_project_context, resolve_project_id

__all__ = ["resolve_project_context", "resolve_project_id"]
```

- [ ] **Step 3: Run focused compatibility tests.**

```powershell
python -m pytest tests/test_project_name_compatibility_containment.py -q
```

Expected: PASS; ID-first, name-only, invalid-ID and conflict behavior are unchanged.

- [ ] **Step 4: Commit the ownership move.**

```powershell
git add bowei_ai_dashboard/app/compatibility/project_names.py bowei_ai_dashboard/app/services/project_resolution.py bowei_ai_dashboard/tests/test_project_name_compatibility_containment.py
git diff --cached --check
git commit -m "refactor: isolate project name compatibility"
```

### Task 3: Migrate production imports and remove the service facade

- [ ] **Step 1: Replace every resolver import.**

For each file returned by the prescribed `rg` command, replace only `from ...services.project_resolution import ...` with the equivalent `...compatibility.project_names` import. In the four target Routers, do not change resolver arguments, endpoint signatures, SQL filters, serialisation or permission code.

- [ ] **Step 2: Prove no production import remains.**

```powershell
rg -n "services\.project_resolution" app -g "*.py"
```

Expected: no output. Delete `app/services/project_resolution.py`, then run the source-boundary test again.

- [ ] **Step 3: Run focused resource regressions.**

```powershell
python -m pytest tests/test_project_name_compatibility_containment.py tests/test_key_task_execution_workspace.py tests/test_meeting_change_set_review_workflow.py tests/test_achievement_attachments.py -q
```

Expected: all selected tests PASS.

- [ ] **Step 4: Commit caller migration.**

```powershell
git add bowei_ai_dashboard/app bowei_ai_dashboard/tests/test_project_name_compatibility_containment.py
git diff --cached --check
git commit -m "refactor: route project name fallback through compatibility"
```

### Task 4: Full delivery verification

- [ ] **Step 1: Run the complete local release gate.**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests -q
Set-Location ..\frontend
npm run test:all
npm run test:bundle
Set-Location ..
git diff --check
git status --short
```

- [ ] **Step 2: Record actual totals and commit verification evidence.**

```powershell
git add docs/superpowers/plans/2026-09-13-backend-project-name-compatibility-containment.md
git diff --cached --check
git commit -m "docs: verify project name compatibility containment"
```
