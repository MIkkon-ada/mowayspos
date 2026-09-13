# Project Role Compatibility Containment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` in the current session task-by-task. Do not delegate to subagents for this repository.

**Goal:** Confine legacy project-role read fallback to `app.compatibility` without changing read contracts or granting legacy write access.

**Architecture:** Keep `project_access.py` strict by default and add a neutral resolved-role entry point. `compatibility/project_roles.py` owns the only legacy fallback composition and exposes semantic view/list helpers consumed by the projects Router.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, pytest.

---

## File structure

- Modify: `bowei_ai_dashboard/app/services/project_access.py`
- Modify: `bowei_ai_dashboard/app/compatibility/project_roles.py`
- Modify: `bowei_ai_dashboard/app/routers/projects.py`
- Modify: `bowei_ai_dashboard/tests/test_project_access_service.py`
- Create: `bowei_ai_dashboard/tests/test_project_role_compatibility_containment.py`

### Task 1: Fix the containment contract with failing tests

- [x] **Step 1: Add a source-boundary test and direct compatibility behavior tests.**

Create `tests/test_project_role_compatibility_containment.py`. Reuse the in-memory `Base.metadata.create_all` pattern. Assert `project_access.py` does not contain `allow_legacy`, `projects.py` does not contain `allow_legacy`, and `project_roles.py` exports `authorize_project_view` plus `resolve_visible_project_ids`. Seed a legacy-only owner and assert the compatibility view helper returns `role_source == "legacy_fields"`, while the strict `authorize_project_action(..., A_OWNER_SUBMIT, ...)` still raises `PROJECT_ACTION_DENIED`.

- [x] **Step 2: Run the new test and verify red.**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_role_compatibility_containment.py -q
```

Expected: missing compatibility view helper and current source-boundary assertion failures.

- [x] **Step 3: Commit the failing contract.**

```powershell
git add bowei_ai_dashboard/tests/test_project_role_compatibility_containment.py
git diff --cached --check
git commit -m "test: define project role compatibility containment"
```

### Task 2: Create strict-core and compatibility-facade APIs

- [x] **Step 1: Refactor the strict service around a neutral role resolution.**

In `project_access.py`, make `authorize_project_action` resolve only current member rows. Add `authorize_project_action_with_resolution(current_user, project, action, db, *, resolution, requester_person_id=None, denial_detail=None)` that builds the same `ProjectAccessContext`, policy subject, resource, and denial behavior from the supplied resolution. Replace `resolve_visible_project_ids(..., allow_legacy)` with `resolve_member_project_ids(context, db)` that reads only `ProjectMember.project_id`.

- [x] **Step 2: Add compatibility-owned read helpers.**

In `compatibility/project_roles.py`, add `authorize_project_view(current_user, project, db, *, denial_detail=None)` and `resolve_visible_project_ids(context, db)`. The first resolves roles with `allow_legacy=True`, imports the strict neutral entry point inside the function to avoid an import cycle, and invokes it with `A_VIEW`. The second unions strict member IDs with project IDs found from the authenticated context's existing `visible_projects` names. No Router or normal service receives an `allow_legacy` flag.

- [x] **Step 3: Run service and compatibility tests.**

```powershell
python -m pytest tests/test_project_access_service.py tests/test_project_role_compatibility.py tests/test_project_role_compatibility_containment.py -q
```

Expected: all strict/legacy separation cases pass.

- [x] **Step 4: Commit the API containment.**

```powershell
git add bowei_ai_dashboard/app/services/project_access.py bowei_ai_dashboard/app/compatibility/project_roles.py bowei_ai_dashboard/tests/test_project_access_service.py bowei_ai_dashboard/tests/test_project_role_compatibility_containment.py
git diff --cached --check
git commit -m "refactor: contain project role compatibility"
```

### Task 3: Delegate Router read paths to compatibility

- [x] **Step 1: Replace the project list and four legacy view call sites.**

In `routers/projects.py`, import the compatibility module as a module alias. The list endpoint calls `project_role_compatibility.resolve_visible_project_ids(context, db)`. `list_members`, `list_member_change_requests`, `get_project`, and the project-permissions read endpoint call `project_role_compatibility.authorize_project_view(...)` with their existing denial text. Do not change any write endpoint or response serialization.

- [x] **Step 2: Run Router regressions.**

```powershell
python -m pytest tests/test_project_role_compatibility_containment.py tests/test_project_draft_visibility.py tests/test_people_projects_legacy_compatibility.py tests/test_project_access_service.py -q
```

Expected: legacy read compatibility remains available and strict write authorization remains denied.

- [x] **Step 3: Commit Router delegation.**

```powershell
git add bowei_ai_dashboard/app/routers/projects.py bowei_ai_dashboard/tests/test_project_role_compatibility_containment.py
git diff --cached --check
git commit -m "refactor: delegate project legacy reads to compatibility"
```

### Task 4: Delivery verification and evidence

- [x] **Step 1: Run focused and complete checks.**

```powershell
Set-Location bowei_ai_dashboard
python -m pytest tests/test_project_access_service.py tests/test_project_role_compatibility.py tests/test_project_role_compatibility_containment.py tests/test_project_draft_visibility.py tests/test_people_projects_legacy_compatibility.py -q
python -m pytest tests -q
Set-Location ..\frontend
npm run test:all
npm run test:bundle
Set-Location ..
git diff --check
git status --short
```

- [x] **Step 2: Record exact totals in this plan and commit.**

```powershell
git add docs/superpowers/plans/2026-09-13-project-role-compatibility-containment.md
git diff --cached --check
git commit -m "docs: record project role compatibility verification"
```

## Verification record (2026-09-13)

- Initial containment contract: failed as intended because `authorize_project_view` did not yet exist.
- Strict service, compatibility and containment tests: `16 passed` in `1.91 s`.
- Router compatibility regressions: `11 passed` in `3.78 s`; the characterization update for the compatibility view boundary then passed with the containment test (`3 passed` in `1.47 s`).
- Full backend suite after the characterization update: `1953 passed, 12 skipped` in `387.45 s`.
- Frontend suite: 27 Vitest files / 89 tests passed; 507 contract tests passed. `npm run test:bundle` completed in `6.00 s`; the bundle analyzer confirmed initial JS `302987` B, initial CSS `97388` B, largest route `95588` B, and dynamically isolated ExcelJS `940194` B.
- Local Docker Desktop remains unavailable, so PostgreSQL empty-database migration and Compose smoke execution remain CI-owned evidence. This change does not alter that fail-closed CI gate.
