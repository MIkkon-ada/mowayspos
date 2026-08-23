# Meeting Type Category Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the user-selected standard meeting category for workflow and filtering, while preserving the Word-extracted meeting name only in immutable analysis evidence.

**Architecture:** `requested_meeting_type` already exists in each run’s frozen snapshot. At review-draft creation, a whitelisted requested category (`regular`, `special`, `kickoff`, `communication`, `review`, `retrospective`) becomes `Meeting.meeting_type`; otherwise the existing Agent-derived value remains the legacy fallback. The review UI reads the frozen category for its badge and leaves raw Word wording inside evidence.

**Tech Stack:** FastAPI, SQLAlchemy, React 19, TypeScript, Vitest, pytest.

---

### Task 1: Persist the standard category without rewriting AI evidence

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_agent_processing.py`
- Modify: `bowei_ai_dashboard/app/services/project_meeting_agent_processing.py`

- [ ] **Step 1: Write the failing backend test**

Add a test where the frozen snapshot contains `requested_meeting_type: "special"` and the Agent’s immutable result contains `meeting_info.meeting_type: "Word 原文专题名称"`. After processing, assert:

```python
assert db.query(models.Meeting).one().meeting_type == "special"
assert json.loads(db.get(models.ProjectMeetingRun, run.id).result_json)["meeting_draft"]["meeting_type"] == "Word 原文专题名称"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_project_meeting_agent_processing.py -k standard_meeting_category -q`

Expected: FAIL because review-draft creation currently writes the Agent-derived Word wording to `Meeting.meeting_type`.

- [ ] **Step 3: Add a whitelisted category resolver**

In `project_meeting_agent_processing.py`, define the six accepted category codes and resolve the persisted meeting type from `json.loads(run.snapshot_json).get("requested_meeting_type")`. Use the requested code only when it is whitelisted; otherwise retain `draft.get("meeting_type")` as the legacy fallback. Do not mutate `normalized`, `result_json`, or field-level evidence.

- [ ] **Step 4: Run the targeted backend test**

Run: `..\.venv\Scripts\python.exe -m pytest tests/test_project_meeting_agent_processing.py -k standard_meeting_category -q`

Expected: PASS.

### Task 2: Display the standard category instead of a raw Word label

**Files:**
- Modify: `frontend/src/pages/MeetingPage.tsx:218-250`
- Modify: `frontend/src/features/meeting/ProjectMeetingReviewWorkspace.tsx:1-170`
- Modify: `frontend/src/features/meeting/ProjectMeetingReviewWorkspace.test.ts`

- [ ] **Step 1: Write the failing UI contract assertions**

Add assertions that the review workspace imports `typeLabel`, renders `typeLabel(editableDraft.meeting_type)`, and does not keep `meeting_type` in `fieldLabels`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm.cmd run test:unit -- src/features/meeting/ProjectMeetingReviewWorkspace.test.ts`

Expected: FAIL because the workspace does not yet render the standard category badge.

- [ ] **Step 3: Render the frozen standard category**

In `MeetingPage.tsx`, derive `requestedMeetingType` from `projectMeetingReview.snapshot.requested_meeting_type`; pass it to `meetingDraft.meeting_type` when present, otherwise preserve the current meeting value. In the workspace, remove `meeting_type` from the editable field list and render a styled header badge using `typeLabel` and `TYPE_STYLE`.

- [ ] **Step 4: Run frontend verification**

Run: `npm.cmd run test:unit; npm.cmd run build`

Expected: all tests pass and the production build succeeds.

### Task 3: Verify review and list semantics

**Files:**
- Modify: none

- [ ] **Step 1: Inspect a newly created review draft**

Expected: the header shows `项目例会` / `专题会议` etc. based on the creation selection; no raw Word naming appears as the category field.

- [ ] **Step 2: Inspect evidence disclosure**

Expected: the Word-specific meeting wording remains available through `查看原文依据` and the immutable result remains unchanged.

