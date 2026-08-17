# Separate Meeting Publish and Writeback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make meeting publication and project-plan writeback two explicit owner actions, so publishing a meeting can never silently alter a subplan.

**Architecture:** Extend the existing review endpoint’s action enum with `publish` and `apply_changes`. `publish` records an owner event and changes only the meeting’s publication/review state. `apply_changes` is allowed only after publication and executes selected pending proposals through the existing validation/writeback helper. The review workspace changes from one ambiguous approval callback to separate publish and apply callbacks.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, React 19, TypeScript, pytest, Vitest.

---

### Task 1: Define and lock the separated review actions

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_review_writeback.py`
- Modify: `bowei_ai_dashboard/app/schemas.py:519-531`
- Modify: `bowei_ai_dashboard/app/routers/meetings.py:1070-1110`

- [ ] **Step 1: Write failing backend tests**

Add tests that prove:

```python
# publish changes only meeting state and creates no ExecutionSchedule rows
response = client.post(f"/api/meetings/{meeting_id}/review", json={"action": "publish"})
assert response.status_code == 200
assert response.json()["publish_status"] == "published"
assert db.query(models.ExecutionSchedule).count() == 0

# apply_changes is rejected before publication
response = client.post(f"/api/meetings/{meeting_id}/review", json={"action": "apply_changes", "proposal_ids": [proposal_id]})
assert response.status_code == 409
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_project_meeting_review_writeback.py -k "publish_without_writeback or apply_changes_requires_published" -q`

Expected: FAIL because the schema only accepts `approve` and `return`.

- [ ] **Step 3: Implement separated actions**

Change `ProjectMeetingReviewPayload.action` to `Literal["publish", "apply_changes", "return"]`; require at least one proposal ID for `apply_changes`. In the route:

```python
if payload.action == "publish":
    meeting.review_status = "approved"
    meeting.publish_status = "published"
    meeting.review_version = (meeting.review_version or 0) + 1
    event_action = "published"
elif payload.action == "apply_changes":
    if meeting.publish_status != "published":
        raise HTTPException(409, "publish meeting before applying schedule changes")
    _execute_project_meeting_schedule_changes(meeting, payload.proposal_ids, current_user, db)
    event_action = "changes_applied"
else:
    # existing return behavior
```

Do not change `_execute_project_meeting_schedule_changes`; it continues to validate selected proposals, evidence, snapshots, and live schedule state.

- [ ] **Step 4: Run targeted backend tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_project_meeting_review_writeback.py -k "publish_without_writeback or apply_changes_requires_published" -q`

Expected: PASS.

### Task 2: Make the owner interface express the two actions

**Files:**
- Modify: `frontend/src/api/meetings.ts:434-439`
- Modify: `frontend/src/pages/MeetingPage.tsx:312-334`
- Modify: `frontend/src/features/meeting/ProjectMeetingReviewWorkspace.tsx:46-178`
- Modify: `frontend/src/features/meeting/ProjectMeetingReviewWorkspace.test.ts`

- [ ] **Step 1: Write a failing UI contract test**

Assert the workspace includes `发布会议纪要`, `回填已选`, `onPublish`, and `onApplyChanges`, and no longer contains `项目负责人批准`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm.cmd run test:unit -- src/features/meeting/ProjectMeetingReviewWorkspace.test.ts`

Expected: FAIL because the current UI exposes only the ambiguous approve action.

- [ ] **Step 3: Change the client API and page callbacks**

Extend `reviewProjectMeeting` to accept the three actions. `onPublish` calls `{ action: "publish" }`, retains the review workspace, and shows a “published without writeback” message. `onApplyChanges` calls `{ action: "apply_changes", proposal_ids }`, then refetches the review package so proposal execution status updates visibly.

- [ ] **Step 4: Change workspace action rendering**

Use `meetingDraft.publish_status === "published"` to render:

```tsx
// before publication, always available
<button>发布会议纪要</button>
// after publication and only with suggestions
<button disabled={!selectedScheduleChangeIds.size}>回填已选 {selectedScheduleChangeIds.size} 项变更</button>
```

Show the return form only before publication. Keep the explanatory copy: publication never writes the project plan; writeback is a separate confirmed action.

- [ ] **Step 5: Run full frontend verification**

Run: `npm.cmd run test:unit; npm.cmd run build`

Expected: all unit tests pass and the production build succeeds.

### Task 3: Verify owner outcomes in the local app

**Files:**
- Modify: none

- [ ] **Step 1: Inspect a meeting with zero proposals**

Expected: only `发布会议纪要` and `退回修改` are presented; no plan-writeback language appears.

- [ ] **Step 2: Inspect a published meeting with pending proposals**

Expected: selected pending proposals can be applied using the distinct `回填已选 X 项变更` action; the event and proposal execution statuses update after success.

