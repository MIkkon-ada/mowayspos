# Meeting Progress Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist member-level progress review results against the approved kickoff task baseline, require human confirmation, and write confirmed states back to subtasks.

**Architecture:** Add an immutable approved kickoff snapshot plus a `meeting_progress_reviews` table. A focused backend service parses `姓名：汇报内容`, asks the existing LLM provider for evidence-bound classifications, and exposes analyze/read/review/confirm endpoints. The existing meeting editor triggers analysis after saving; the meeting detail page renders review cards and confirms writes transactionally.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, existing LLM provider wrapper, React/TypeScript, Vitest source-structure tests.

---

### Task 1: Add approved kickoff baseline and review persistence

**Files:**
- Modify: `bowei_ai_dashboard/app/models.py`
- Create: `bowei_ai_dashboard/migrations/versions/e5f6a7b8c9d0_add_meeting_progress_reviews.py`
- Test: `bowei_ai_dashboard/tests/test_meeting_progress_review_model.py`
- Test: `bowei_ai_dashboard/tests/test_migration_bootstrap.py`

- [ ] **Step 1: Write the failing model tests**

```python
def test_progress_review_snapshot_and_review_fields_round_trip(db):
    row = models.MeetingProgressReview(
        project_id=1, meeting_id=2, baseline_run_id=3,
        member_name="张三", baseline_snapshot_json='{"subtask_id": 7}',
        report_text="已完成接口设计", status="completed",
        evidence_quote="张三：已完成接口设计",
        suggested_task_status="已完成", review_status="pending",
    )
    db.add(row)
    db.commit()
    loaded = db.get(models.MeetingProgressReview, row.id)
    assert loaded.evidence_quote == "张三：已完成接口设计"
    assert loaded.review_status == "pending"


def test_kickoff_run_has_approved_snapshot_json():
    assert hasattr(models.KickoffAgentRun, "approved_snapshot_json")
```

- [ ] **Step 2: Run the focused tests and verify the expected failure**

Run from `bowei_ai_dashboard`:

```powershell
python -m pytest tests/test_meeting_progress_review_model.py -q
```

Expected: FAIL because `MeetingProgressReview` and `approved_snapshot_json` do not exist.

- [ ] **Step 3: Implement the model and migration**

Add `approved_snapshot_json = Column(Text, nullable=False, default="{}")` to `KickoffAgentRun`.

Add `MeetingProgressReview` with `id`, `project_id`, `meeting_id`, `baseline_run_id`, nullable `baseline_task_id`, nullable `baseline_subtask_id`, `member_name`, `baseline_snapshot_json`, `report_text`, `status`, `evidence_quote`, `suggested_task_status`, `review_status`, nullable `reviewer_person_id`, nullable `reviewed_at`, `review_comment`, `validation_json`, `analysis_version`, `created_at`, and `updated_at`.

Create revision `e5f6a7b8c9d0_add_meeting_progress_reviews.py` with `down_revision = "d4e5f6a7b8c9"`, adding the column, foreign keys, indexes on `project_id`, `meeting_id`, `baseline_run_id`, and `review_status`, plus a uniqueness constraint on `(meeting_id, analysis_version, member_name, baseline_subtask_id)`.

- [ ] **Step 4: Run model and migration tests**

```powershell
python -m pytest tests/test_meeting_progress_review_model.py tests/test_migration_bootstrap.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the persistence slice**

```powershell
git add bowei_ai_dashboard/app/models.py bowei_ai_dashboard/migrations/versions/e5f6a7b8c9d0_add_meeting_progress_reviews.py bowei_ai_dashboard/tests/test_meeting_progress_review_model.py bowei_ai_dashboard/tests/test_migration_bootstrap.py
git commit -m "feat: persist meeting progress review results"
```

### Task 2: Build baseline, speaker parsing, and evidence normalization service

**Files:**
- Create: `bowei_ai_dashboard/app/services/meeting_progress_review.py`
- Test: `bowei_ai_dashboard/tests/test_meeting_progress_review_service.py`

- [ ] **Step 1: Write failing service tests**

```python
def test_load_approved_baseline_uses_final_snapshot(db):
    run = models.KickoffAgentRun(
        project_id=1, snapshot_json='{"tasks": [{"id": 1}]}',
        approved_snapshot_json='{"tasks": [{"id": 2}]}',
        result_json="{}", status="approved",
    )
    db.add(run)
    db.commit()
    baseline = load_approved_baseline(1, db)
    assert baseline["tasks"][0]["id"] == 2


def test_parse_named_reports_rejects_unknown_names():
    reports = parse_named_reports("张三：完成接口设计\n陌生人：已完成", {"张三"})
    assert reports == [{"member_name": "张三", "report_text": "完成接口设计"}]


def test_normalize_review_requires_verbatim_evidence():
    normalized = normalize_review_candidates(
        [{"member_name": "张三", "status": "completed", "evidence_quote": ""}],
        "张三：本周继续推进", {"张三"},
    )
    assert normalized[0]["status"] == "not_mentioned"
    assert normalized[0]["validation_json"]
```

- [ ] **Step 2: Run the service tests and verify failure**

```powershell
python -m pytest tests/test_meeting_progress_review_service.py -q
```

Expected: FAIL because the service functions do not exist.

- [ ] **Step 3: Implement the service**

Implement these public functions: `load_approved_baseline(project_id, db)`, `parse_named_reports(transcript, member_names)`, `build_progress_prompt(baseline, reports)`, `normalize_review_candidates(candidates, transcript, member_names)`, and `next_analysis_version(meeting_id, db)`.

Use the latest approved `KickoffAgentRun` ordered by ID, parse only lines matching `姓名：内容` or `姓名:内容`, accept only exact project member names, and emit an explicit validation error for unknown speakers or missing evidence. The prompt must forbid inferred completion and require `status`, `evidence_quote`, `baseline_subtask_id`, `suggested_task_status`, and `reason` for every candidate.

- [ ] **Step 4: Run service tests**

```powershell
python -m pytest tests/test_meeting_progress_review_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the service slice**

```powershell
git add bowei_ai_dashboard/app/services/meeting_progress_review.py bowei_ai_dashboard/tests/test_meeting_progress_review_service.py
git commit -m "feat: normalize evidence-bound meeting progress reviews"
```

### Task 3: Capture the final approved kickoff snapshot

**Files:**
- Modify: `bowei_ai_dashboard/app/services/kickoff_writeback.py`
- Test: `bowei_ai_dashboard/tests/test_kickoff_writeback.py`

- [ ] **Step 1: Add a failing regression test**

```python
def test_confirm_kickoff_start_persists_post_approval_snapshot(db):
    project, run, created_subtask = make_pending_kickoff_fixture(db)
    confirm_kickoff_start(run.id, "coach", db)
    db.refresh(run)
    snapshot = json.loads(run.approved_snapshot_json)
    assert any(item["id"] == created_subtask.id for task in snapshot["tasks"] for item in task["subtasks"])
```

- [ ] **Step 2: Run the regression test and verify failure**

```powershell
python -m pytest tests/test_kickoff_writeback.py::test_confirm_kickoff_start_persists_post_approval_snapshot -q
```

Expected: FAIL because the approved snapshot remains empty.

- [ ] **Step 3: Implement final snapshot capture**

After `_apply_approved_proposal` finishes and before committing the transaction, call `build_kickoff_snapshot(project.id, db)`, serialize it into `run.approved_snapshot_json`, set `run.meeting_id` after flushing the published kickoff meeting, and keep the original `snapshot_json` unchanged for audit.

- [ ] **Step 4: Run kickoff tests**

```powershell
python -m pytest tests/test_kickoff_writeback.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the kickoff baseline slice**

```powershell
git add bowei_ai_dashboard/app/services/kickoff_writeback.py bowei_ai_dashboard/tests/test_kickoff_writeback.py
git commit -m "feat: persist approved kickoff task baseline"
```

### Task 4: Add analyze, read, review, and confirm APIs

**Files:**
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Modify: `bowei_ai_dashboard/app/routers/meetings.py`
- Modify: `bowei_ai_dashboard/app/services/meeting_progress_review.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_progress_review_api.py`

- [ ] **Step 1: Write failing endpoint tests**

Cover missing baseline, successful confirmation, and atomic failure:

```python
def test_analyze_requires_approved_baseline(db, meeting_row):
    with pytest.raises(HTTPException) as exc:
        analyze_progress_review(meeting_row.id, current_user="owner", db=db)
    assert exc.value.status_code == 409


def test_confirm_review_updates_subtask_and_marks_accepted(db, review, payload):
    result = confirm_progress_review(review.id, payload, current_user="owner", db=db)
    assert result["review_status"] == "accepted"
    assert db.get(models.SubTask, review.baseline_subtask_id).status == "已完成"


def test_confirm_failure_does_not_mark_review_accepted(db, review, payload):
    review.baseline_subtask_id = 999999
    with pytest.raises(HTTPException):
        confirm_progress_review(review.id, payload, current_user="owner", db=db)
    assert db.get(models.MeetingProgressReview, review.id).review_status == "pending"
```

- [ ] **Step 2: Run API tests and verify failure**

```powershell
python -m pytest tests/test_meeting_progress_review_api.py -q
```

Expected: FAIL because the schemas and endpoints do not exist.

- [ ] **Step 3: Implement schemas and endpoints**

Add Pydantic payloads for review edits and confirmation. Add these routes below the existing meeting routes: `POST /api/meetings/{row_id}/progress-review/analyze`, `GET /api/meetings/{row_id}/progress-review`, `PATCH /api/meetings/{row_id}/progress-review/{review_id}`, and `POST /api/meetings/{row_id}/progress-review/{review_id}/confirm`.

The analyze route must verify the meeting belongs to the requested project, require an approved baseline, preserve accepted historical rows, and replace only pending rows for the new `analysis_version`. The confirm route must require owner/coordinator task-write permission, revalidate project ownership of the subtask, update only the allowed task status/notes fields, append the existing operation log, and commit the review and task update in one transaction.

- [ ] **Step 4: Run API tests and existing meeting tests**

```powershell
python -m pytest tests/test_meeting_progress_review_api.py tests/test_meeting_draft_review.py tests/test_meeting_revision_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the API slice**

```powershell
git add bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/app/routers/meetings.py bowei_ai_dashboard/app/services/meeting_progress_review.py bowei_ai_dashboard/tests/test_meeting_progress_review_api.py
git commit -m "feat: add meeting progress review APIs"
```

### Task 5: Add the review API client and meeting detail UI

**Files:**
- Modify: `frontend/src/api/meetings.ts`
- Create: `frontend/src/features/meeting/MeetingProgressReviewSection.tsx`
- Modify: `frontend/src/pages/MeetingPage.tsx`
- Modify: `frontend/src/features/meeting/NewMeetingModal.tsx`
- Create: `frontend/tests/meetingProgressReviewStructure.test.mjs`

- [ ] **Step 1: Write the failing frontend structure test**

```js
import fs from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('meeting progress review UI', () => {
  it('exposes analysis, evidence, confirmation, and ignore actions', () => {
    const source = fs.readFileSync('src/features/meeting/MeetingProgressReviewSection.tsx', 'utf8')
    expect(source).toContain('确认并写回')
    expect(source).toContain('忽略')
    expect(source).toContain('evidence_quote')
  })
})
```

- [ ] **Step 2: Run the frontend test and verify failure**

Run from `frontend`:

```powershell
npm run test:unit -- tests/meetingProgressReviewStructure.test.mjs
```

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement API types and review component**

Add `MeetingProgressReviewItem`, `analyzeProgressReview`, `fetchProgressReviews`, `patchProgressReview`, and `confirmProgressReview` to `frontend/src/api/meetings.ts`.

Implement `MeetingProgressReviewSection` to fetch rows for the selected meeting, show member/task/report/status/evidence, allow status and comment edits, and disable confirmation for accepted or ignored rows. Confirmation must refresh the row and never optimistically change the subtask state before the API succeeds.

- [ ] **Step 4: Trigger analysis after saving and mount the review section**

In `NewMeetingModal.handleSave`, call `analyzeProgressReview(item.id)` after the meeting save succeeds. Treat analysis errors as non-fatal to the meeting save and pass the error back to the page for a retry message.

In `MeetingPage`, mount `MeetingProgressReviewSection` under the selected meeting for normal progress meetings, reload it when `selected.id` changes, and show explicit empty states for “no approved kickoff baseline”, “no named reports”, “analysis pending”, and “analysis failed”.

- [ ] **Step 5: Run frontend tests and build**

```powershell
npm run test:unit -- tests/meetingProgressReviewStructure.test.mjs tests/meetingDraftReviewStructure.test.mjs tests/kickoffAgentStructure.test.mjs
npm run build
```

Expected: PASS with a successful TypeScript/Vite build.

- [ ] **Step 6: Commit the frontend slice**

```powershell
git add frontend/src/api/meetings.ts frontend/src/features/meeting/MeetingProgressReviewSection.tsx frontend/src/pages/MeetingPage.tsx frontend/src/features/meeting/NewMeetingModal.tsx frontend/tests/meetingProgressReviewStructure.test.mjs
git commit -m "feat: add member progress review UI"
```

### Task 6: Full verification and migration safety check

**Files:**
- Test: `bowei_ai_dashboard/tests/test_meeting_progress_review_model.py`
- Test: `bowei_ai_dashboard/tests/test_meeting_progress_review_service.py`
- Test: `bowei_ai_dashboard/tests/test_meeting_progress_review_api.py`
- Test: `frontend/tests/meetingProgressReviewStructure.test.mjs`

- [ ] **Step 1: Run backend migration and focused suite**

From `bowei_ai_dashboard`:

```powershell
python -m alembic heads
python -m pytest tests/test_meeting_progress_review_model.py tests/test_meeting_progress_review_service.py tests/test_meeting_progress_review_api.py tests/test_kickoff_writeback.py tests/test_meeting_revision_api.py -q
```

Expected: one Alembic head and zero test failures.

- [ ] **Step 2: Run the complete backend suite**

```powershell
python -m pytest -q
```

Expected: exit code 0 with no failures.

- [ ] **Step 3: Run the complete frontend unit suite and production build**

From `frontend`:

```powershell
npm run test:unit
npm run build
```

Expected: all unit tests pass and the build exits with code 0.

- [ ] **Step 4: Review the diff and migration scope**

```powershell
git diff --check
git status --short
```

Confirm that only the planned files are staged and unrelated existing worktree changes remain untouched.
