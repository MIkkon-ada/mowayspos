# 企业微信公司身份同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a preview-and-confirm WeCom directory sync that maintains department and position identity data with independent local overrides.

**Architecture:** Extend the existing Person model with a stable WeCom identity, raw WeCom values, effective values, and per-field source flags. Add detailed directory retrieval and explicit sync/reset endpoints under the existing accounts/people routers. Keep system roles, project roles, local account authentication, and project history completely independent.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, urllib-based WeCom client, React/TypeScript, Node test runner, pytest.

---

### Task 1: Add failing backend model and migration tests

**Files:**
- Create: `bowei_ai_dashboard/tests/test_wecom_identity_sync.py`
- Create: `bowei_ai_dashboard/migrations/versions/f6a7b8c9d0e1_add_wecom_identity_fields.py`
- Modify: `bowei_ai_dashboard/app/models.py`

- [ ] **Step 1: Write tests for field defaults and isolation**

Add tests that instantiate a `Person` and assert new identity fields default to empty strings and `wecom` sources; add a migration contract assertion that the revision adds the new `people` columns and indexes without changing `project_members`.

- [ ] **Step 2: Run the tests and confirm the expected failure**

Run `pytest -q bowei_ai_dashboard/tests/test_wecom_identity_sync.py`. Expected failure: `Person` does not yet expose the new fields and the migration file does not exist.

- [ ] **Step 3: Implement the model and migration**

Add `position_title`, `wecom_userid`, `wecom_department`, `wecom_position_title`, `department_source`, and `position_source` to `Person`. Add a batch-safe Alembic migration with an index on `people.wecom_userid`; preserve existing `department` and `role` values.

- [ ] **Step 4: Run the tests and verify they pass**

Run the same pytest command and confirm all tests pass.

### Task 2: Add detailed WeCom directory retrieval

**Files:**
- Modify: `bowei_ai_dashboard/app/services/wecom.py`
- Modify: `bowei_ai_dashboard/tests/test_wecom_identity_sync.py`

- [ ] **Step 1: Write failing service tests**

Test that the detailed member endpoint uses `/user/list` and preserves `userid`, `name`, `department`, and `position`; test department parsing preserves IDs and names returned by the department endpoint.

- [ ] **Step 2: Run the service tests and confirm failure**

Run `pytest -q bowei_ai_dashboard/tests/test_wecom_identity_sync.py -k directory`. Expected failure: the detailed retrieval helpers are missing.

- [ ] **Step 3: Implement minimal service helpers**

Add `list_department_user_details()` using the existing token and HTTP helpers, add `list_departments()`, and add a pure helper that builds a readable department path from department metadata. Keep `list_department_users()` unchanged for existing account-binding behavior.

- [ ] **Step 4: Run the service tests and verify they pass**

Run the targeted pytest command and confirm all directory tests pass.

### Task 3: Add preview and confirmed sync APIs

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/accounts.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Modify: `bowei_ai_dashboard/tests/test_wecom_identity_sync.py`

- [ ] **Step 1: Write failing API behavior tests**

Cover: exact `wecom_userid` matches an existing person; name-only matches are marked `needs_confirmation`; preview reports local overrides without changing data; confirmed sync updates raw values and only updates effective values when that field source is `wecom`; system role and project member rows remain unchanged.

- [ ] **Step 2: Run the tests and confirm failure**

Run `pytest -q bowei_ai_dashboard/tests/test_wecom_identity_sync.py -k sync`. Expected failure: the new endpoints and sync helpers are missing.

- [ ] **Step 3: Implement preview and confirmation**

Add schemas for preview selection and sync confirmation. Add a shared helper in `accounts.py` that normalizes directory records, matches by `Person.wecom_userid` first, falls back to name suggestions, and returns action/status metadata. The confirmation endpoint must run under `_require_admin`, write only selected records, preserve local effective values when the corresponding source is `local`, update `Person.wecom_userid`, and mirror the ID into any linked `Account` only when that account has no conflicting WeCom ID. Reject conflicting IDs atomically.

- [ ] **Step 4: Run the API tests and verify they pass**

Run the targeted pytest command and confirm all sync tests pass.

### Task 4: Add per-field local override and restore APIs

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/people.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Modify: `bowei_ai_dashboard/tests/test_wecom_identity_sync.py`

- [ ] **Step 1: Write failing override tests**

Test that an administrator changing only department sets `department_source=local` while leaving position source unchanged; test reset restores the latest WeCom value and switches the source back to `wecom`; test invalid field names return 422 and non-admins return 403.

- [ ] **Step 2: Run the tests and confirm failure**

Run `pytest -q bowei_ai_dashboard/tests/test_wecom_identity_sync.py -k override`. Expected failure: the identity override endpoint is missing.

- [ ] **Step 3: Implement the override/reset endpoint**

Add `POST /api/people/{row_id}/identity-reset` with a validated field enum. Update the existing person edit path so department and position edits mark only the changed field as `local`; retain the existing `system_role` and project assignment behavior.

- [ ] **Step 4: Run the override tests and verify they pass**

Run the targeted pytest command and confirm override tests pass.

### Task 5: Add frontend API types and management UI

**Files:**
- Modify: `frontend/src/api/accounts.ts`
- Modify: `frontend/src/api/people.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/features/settings/AccountPeopleMgmtSection.tsx`
- Create: `frontend/tests/wecomIdentitySync.test.mjs`

- [ ] **Step 1: Write the failing frontend structure tests**

Assert the people management section exposes a WeCom directory sync entry, preview/confirm labels, local override indicators, and restore-WeCom actions; assert the API modules expose preview, confirm, and reset functions.

- [ ] **Step 2: Run the frontend test and confirm failure**

Run `node --test frontend/tests/wecomIdentitySync.test.mjs`. Expected failure: the new API functions and UI strings are absent.

- [ ] **Step 3: Implement API types and UI**

Add typed API functions and render a compact sync panel in the existing people management page. The panel loads preview data, allows selecting exact-ID matches and reviewed name matches, confirms synchronization, and refreshes people/accounts. Each identity field shows its source and latest WeCom value; editing the field uses the existing person update flow and exposes a reset action when the source is `local`.

- [ ] **Step 4: Run the frontend test and verify it passes**

Run `node --test frontend/tests/wecomIdentitySync.test.mjs` and confirm it passes.

### Task 6: Integrate migration and run focused regression checks

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_alembic_database_safety.py` only if the repository's migration contract requires explicit registration.
- Modify: `frontend/src/types.ts` only if the UI types need final alignment.

- [ ] **Step 1: Run migration and role regression tests**

Run `pytest -q bowei_ai_dashboard/tests/test_wecom_identity_sync.py bowei_ai_dashboard/tests/test_role_boundary.py bowei_ai_dashboard/tests/test_company_ceo_owner_confirmation_permission.py`.

- [ ] **Step 2: Run frontend targeted tests and type/build checks**

Run `node --test frontend/tests/wecomIdentitySync.test.mjs frontend/tests/authFlow.test.mjs frontend/tests/confirmPage* 2>$null` where supported, then run the repository's frontend test/build command from `frontend/package.json`.

- [ ] **Step 3: Inspect the diff for scope safety**

Run `git diff --stat` and `git diff -- bowei_ai_dashboard/app/models.py bowei_ai_dashboard/app/services/wecom.py bowei_ai_dashboard/app/routers/accounts.py bowei_ai_dashboard/app/routers/people.py frontend/src/features/settings/AccountPeopleMgmtSection.tsx`. Confirm no system-role or project-role authorization branch changed.

- [ ] **Step 4: Run the complete relevant test suites**

Run the backend focused suite and frontend suite again after the final diff is stable. Record exit codes and failure counts before claiming completion.
