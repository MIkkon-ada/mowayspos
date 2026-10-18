# Stable-ID My Tasks Aggregation Implementation Plan

> **For agentic workers:** Execute inline in the current authorized task. The repository's `AGENTS.md` prohibits subagents unless the user explicitly authorizes them. Preserve all existing worktree changes and do not commit mixed work.

**Goal:** Make the personal task center return only tasks owned by the authenticated person's stable ID, safely include uniquely attributable legacy rows, and replace per-project name-filtered requests with one authorized server query.

**Architecture:** Add a backend `/api/my-tasks` endpoint that derives the person ID from the authenticated account, obtains the same visible-project scope as project listing, and returns active-project task rows plus an ambiguity count. A unique active-person name may temporarily bridge a row whose `assignee_id` is null; duplicate or unmapped names remain unresolved. Add a read-only audit command that lists null-ID rows and their unique/ambiguous candidate status without writing data. Update the V2 hook and view model to consume the aggregate response and stop filtering by display name.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, React, TypeScript, Vitest, Node contract tests.

---

## File map

- `bowei_ai_dashboard/app/routers/subtasks.py`: expose the authenticated aggregate endpoint beside existing subtask listing routes.
- `bowei_ai_dashboard/app/services/my_tasks.py` (new): resolve the signed-in account identity, authorized active project scope, task query, and legacy assignment diagnostics.
- `bowei_ai_dashboard/scripts/audit_task_assignee_links.py` (new): read-only inventory of unlinked task owners; default output is a count summary, optional CSV includes record identifiers for manual reconciliation.
- `bowei_ai_dashboard/tests/test_my_tasks.py` (new): authorization, stable-ID, legacy fallback, ambiguity, and lifecycle coverage.
- `bowei_ai_dashboard/tests/test_audit_task_assignee_links.py` (new): audit classification and no-write behavior.
- `frontend-v2/src/api/subtasks.ts`: define the aggregate response and `fetchMyTasks` client without a caller-supplied person ID.
- `frontend-v2/src/features/my-tasks/myTasksViewModel.ts`: build rows from server-resolved records without name matching.
- `frontend-v2/src/features/my-tasks/useMyTasks.ts`: replace per-project `Promise.allSettled` calls with one request and retain stale-response protection.
- `frontend-v2/src/pages/MyTasksPage.tsx`: replace per-project partial-failure copy with aggregate error and unresolved-assignment warning states.
- `frontend-v2/tests/myTasksPageStructure.test.mjs`: assert one identity-safe request and no name-based client filtering.
- `frontend-v2/src/features/my-tasks/myTasksViewModel.test.ts` or existing contract test fixtures: cover renamed ID-bound assignments.

## Task 1: Specify the backend identity boundary

**Files:** Create `bowei_ai_dashboard/tests/test_my_tasks.py`.

- [ ] Add a test with two active `Person` rows sharing a name, two accounts with different `person_id` values, and two ID-bound tasks. Calling the service as the first account must return only the first task.
- [ ] Add a test where an ID-bound task's saved display name is stale after a rename; it must still be returned to the account whose `person_id` matches.
- [ ] Add a project-scope test proving an ID-bound task outside the caller's visible project IDs is absent, while an active task in a visible project is present.
- [ ] Add legacy-row tests: a null-ID task maps only when exactly one active person has the assignee name; an ambiguous null-ID row is excluded and increments the ambiguity count.
- [ ] Add lifecycle coverage: `active` and legacy `pending_kickoff` match the V2 personal-task project scope; draft, dispatched, pending review, returned, pending close, ended, and archived projects do not appear.
- [ ] Run `python -m pytest tests/test_my_tasks.py -q`; verify it fails because the service is not implemented.

## Task 2: Implement an identity-safe aggregate service

**Files:** Create `bowei_ai_dashboard/app/services/my_tasks.py`; modify `bowei_ai_dashboard/tests/test_my_tasks.py` only if fixture names need alignment.

- [ ] Resolve the account using `models.Account.username == current_user` and `status == "active"`; require a non-null `account.person_id`. Never accept a person ID from query parameters or request bodies.
- [ ] Resolve visible project IDs with `resolve_visible_project_ids(context, db, allow_legacy=True)`, and constrain projects to statuses `active` and `pending_kickoff`, matching `frontend-v2/src/domain/projectLifecycleStatus.ts:isProjectActive`.
- [ ] Query `SubTask`, `Task`, and `Project` in one joined query, excluding deleted rows and selecting assignments where `SubTask.assignee_id == account.person_id`.
- [ ] For null-ID rows only, enable exact-name fallback when the account's current active `Person.name` resolves to exactly that one person ID. Count same-name ambiguous null-ID rows without returning them.
- [ ] Populate the same display fields used by `/api/subtasks`: `parent_key_task`, `parent_task_id`, `parent_project_id`, and `parent_special_project`; source the project name from the joined `Project` row to avoid per-row project lookups.
- [ ] Return `{ projects, tasks, ambiguous_assignment_count }`, where `projects` contains authorized active-scope projects even when they have no tasks. Return a clear 409 when the authenticated account has no stable person binding.
- [ ] Run `python -m pytest tests/test_my_tasks.py -q`; expect all identity and scope tests to pass.

## Task 3: Expose and exercise the API contract

**Files:** Modify `bowei_ai_dashboard/app/routers/subtasks.py`; modify `bowei_ai_dashboard/tests/test_my_tasks.py`.

- [ ] Add `GET /api/my-tasks` that requires the existing session identity and delegates to `list_my_tasks`; do not accept `person_id`, `assignee`, or `project_id` as filters.
- [ ] Add a route-level test proving a forged `person_id` query parameter cannot change the returned identity scope.
- [ ] Add tests for unauthenticated requests and accounts lacking `person_id`, asserting 401 and 409 respectively.
- [ ] Run `python -m pytest tests/test_my_tasks.py -q` and `python -m pytest tests/test_subtask_log_actions.py tests/test_work_progress_latest_submission.py -q`.

## Task 4: Add a read-only legacy-link audit

**Files:** Create `bowei_ai_dashboard/app/services/my_tasks.py` audit helpers if the service can share them cleanly; create `bowei_ai_dashboard/scripts/audit_task_assignee_links.py`; create `bowei_ai_dashboard/tests/test_audit_task_assignee_links.py`.

- [ ] Classify every non-deleted null-`assignee_id` subtask as `unique_candidate`, `ambiguous`, or `unmatched` by active exact-name matches; retain task, workstream, and project IDs for manual review.
- [ ] Default CLI output prints aggregate counts only. `--csv PATH` explicitly writes a CSV containing project ID/name, workstream ID/title, key-task ID/title, saved assignee name, classification, and candidate person IDs.
- [ ] Keep the script read-only: no ORM assignments, commits, updates, or automatic backfill.
- [ ] Test classification, ambiguous candidate preservation, CSV escaping, and no database writes by comparing row values before and after audit.
- [ ] Run `python -m pytest tests/test_audit_task_assignee_links.py -q`.

## Task 5: Consume the aggregate response in V2

**Files:** Modify `frontend-v2/src/api/subtasks.ts`, `frontend-v2/src/features/my-tasks/myTasksViewModel.ts`, `frontend-v2/src/features/my-tasks/useMyTasks.ts`, and `frontend-v2/src/pages/MyTasksPage.tsx`.

- [ ] Add typed `{ projects, tasks, ambiguous_assignment_count }` and `fetchMyTasks()` calling `GET /api/my-tasks` with no identity query parameters.
- [ ] Remove the `assignee` filter from `buildMyTaskRows`; ID ownership is already enforced by the server, and display names must not decide task ownership.
- [ ] Replace the per-project `Promise.allSettled` request loop with one `fetchMyTasks` call. Keep cancellation/stale-response protection, refresh behavior, and timestamp update.
- [ ] Remove per-project success/failure states. Represent a request failure as a single actionable error, and show a separate warning when `ambiguous_assignment_count > 0` so unresolved legacy rows are not silently presented as a complete personal list.
- [ ] Update empty-state text to say tasks are associated with the signed-in person rather than the account name.
- [ ] Add test coverage for a renamed assignee with an ID, one aggregate request, failure state, and ambiguity warning. Update source-contract assertions to reject name-based filtering and per-project loops.
- [ ] Run `cd frontend-v2 && npm run test:unit && npm run test:contracts`.

## Task 6: Verify compatibility and record evidence

**Files:** Update `docs/系统完整优化路径清单-2026-10-08.md`.

- [ ] Run `cd bowei_ai_dashboard && python -m pytest tests/test_my_tasks.py tests/test_audit_task_assignee_links.py tests/test_project_permission_characterization.py -q`.
- [ ] Run `cd frontend-v2 && npm run test:all && npm run test:bundle`.
- [ ] Run `git diff --check` and inspect the final diff for unauthorized person IDs, unsafe automatic backfills, duplicate requests, or regressions in empty/error states.
- [ ] Record exact outcomes, list the audit command, and keep E01/E02 unchecked until a real database audit is run and any ambiguous records are assigned through an authorized process.

## Self-review

- E01 stable ownership, same-name separation, rename behavior, and explicit manual review are covered by Tasks 1–4.
- E02 per-project request reduction and failure-state consistency are covered by Tasks 3 and 5; global timeout and cancellation policy remain a separate E02 follow-up and are not implied complete here.
- Authorization uses the server's account binding and existing visible-project resolver; no frontend-supplied identity controls scope.
- No schema migration or automatic data rewrite is included because `assignee_id` already exists and its production completeness has not been measured.
- Deployment, production data audit, and role-based UAT remain outside this local implementation plan and must be reported as unverified.
