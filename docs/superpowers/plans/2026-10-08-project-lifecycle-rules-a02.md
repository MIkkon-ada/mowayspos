# Project Lifecycle Rules A02 Implementation Plan

> **For agentic workers:** Execute inline in this session with `executing-plans`. Do not use subagents; the repository AGENTS.md prohibits them without direct user consent.

**Goal:** Make project lifecycle transitions enforce their documented preconditions and publish one evidence-based reference for status transitions, project permissions, business-write boundaries, and project fields.

**Architecture:** The backend lifecycle module, project/workflow permission decision functions, route guards, and behavior tests are authoritative. Dedicated transition endpoints own lifecycle changes; generic project metadata updates may keep an unchanged legacy status field but may not change lifecycle. Canonical documentation records compatibility and exceptional admin routes separately from the normal flow, while older acceptance documents are marked historical rather than silently rewritten.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Markdown.

---

### Task 1: Guard lifecycle approval, return, and metadata patch transitions

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_project_lifecycle_simplification.py`
- Modify: `bowei_ai_dashboard/tests/test_project_permission_characterization.py`
- Modify: `bowei_ai_dashboard/app/routers/projects.py`

- [x] Add tests proving approval and return reject draft, dispatched, returned, active, and archived projects without state, audit-log, or notification writes.
- [x] Run the new tests and observe the existing implementation wrongly accepts all non-archived/non-frozen cases.
- [x] Add the `pending_review` precondition to approval and return while retaining the existing archived error.
- [x] Add tests proving generic PATCH cannot change draft to dispatched, pending_review, returned, or active through either `status` or `lifecycle_status`.
- [x] Run those tests and observe the existing PATCH changes lifecycle directly.
- [x] Reject lifecycle changes through generic PATCH while keeping unchanged legacy fields accepted.
- [x] Verify lifecycle, permission characterization, full-role flow, and close-frozen tests: `python -m pytest tests/test_project_lifecycle_simplification.py tests/test_project_permission_characterization.py tests/test_full_role_lifecycle_audit.py tests/test_project_close_lifecycle_guards.py -q --tb=short`.

### Task 2: Publish the canonical lifecycle, permissions, and field reference

**Files:**
- Create: `docs/PROJECT_LIFECYCLE_AND_PERMISSIONS.md`
- Modify: `docs/PROJECT_FLOW_BOUNDARY.md`
- Inspect: `bowei_ai_dashboard/app/domain/project_lifecycle.py`
- Inspect: `bowei_ai_dashboard/app/domain/project_permissions.py`
- Inspect: `bowei_ai_dashboard/app/domain/workflow_permissions.py`
- Inspect: `bowei_ai_dashboard/app/routers/projects.py`
- Inspect: `bowei_ai_dashboard/app/services/project_close.py`

- [x] Record normal state transitions separately from the exceptional technical kickoff and batch-import paths.
- [x] Build the actor/action/state matrix from route guards plus `decide_project_action()` and `decide_workflow_action()`; identify when actor authorization and lifecycle preconditions are separate checks.
- [x] Document report, key-task, meeting, close-review, archive, and generic-write lifecycle boundaries from their actual guards.
- [x] Document the `projects` model fields and optional legacy profile columns, including canonical `status`, optional mirrored `lifecycle_status`, and derived compatibility `is_active` semantics.
- [x] Replace stale `pending_kickoff` gate language in `PROJECT_FLOW_BOUNDARY.md` and link its detailed permissions and lifecycle matrix to the new reference.

### Task 3: Mark conflicting lifecycle runbooks as historical

**Files:**
- Modify: `docs/full-flow-manual-acceptance-checklist.md`
- Modify: `docs/full-flow-manual-acceptance-runbook.md`
- Modify: `docs/N4_P0_BASELINE_MAIN_FLOW_STAGE_MAP.md`
- Modify: `docs/N4_P0_L_MAIN_FLOW_CODE_GAP_AUDIT.md`
- Inspect: `docs/MOWAYS_WAVE_GAP_ANALYSIS.md`

- [x] Add concise top-of-file notices to superseded lifecycle assertions, linking to the canonical reference and preserving the historic test record.
- [x] Correct any document still presented as current that claims normal approval enters `pending_kickoff`, that `pending_kickoff` is a new gate, or that legacy rows have been runtime-verified when no such evidence exists.
- [x] Retain material unrelated to project lifecycle and avoid broad rewriting of historical narrative.

### Task 4: Verify implementation and documentation

**Files:**
- Verify: `docs/PROJECT_LIFECYCLE_AND_PERMISSIONS.md`
- Verify: all files changed in Tasks 1–3.

- [x] Run `python -m pytest tests/test_project_lifecycle_simplification.py tests/test_project_permission_characterization.py tests/test_full_role_lifecycle_audit.py tests/test_project_close_lifecycle_guards.py -q --tb=short` from `bowei_ai_dashboard` (124 passed).
- [x] Run `git diff --check` from the repository root.
- [x] Compare every transition and matrix row with its route guard and permission decision before reporting A02 progress.
- [x] Leave any rule lacking code or acceptance evidence explicitly unresolved; do not infer deployed database contents from model or migration files.
