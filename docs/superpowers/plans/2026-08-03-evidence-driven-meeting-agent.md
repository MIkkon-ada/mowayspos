# Evidence-Driven Meeting Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace prompt-only ordinary meeting analysis with an evidence-backed Agent workflow that preserves original/corrected transcripts, validates every candidate deterministically, and writes only human-reviewed meeting versions.

**Architecture:** Keep `Meeting` as the latest compatible projection, but add immutable transcript, analysis-run, candidate, and enriched revision records.  `meeting_analysis_agent.py` extracts untrusted candidates and `meeting_validation.py` independently validates evidence, people, dates, classifications, and forbidden inference.  The frontend creates analysis runs, reviews candidates with evidence, then explicitly saves selected final values as a new meeting revision; no endpoint writes project tasks from this flow.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, Python standard-library `datetime`/`zoneinfo`, React, TypeScript, Vite, Node test runner, pytest.

---

## Locked file structure

- Create `bowei_ai_dashboard/app/services/meeting_analysis_agent.py`: prompt contract, context snapshot construction, model-output normalization.
- Create `bowei_ai_dashboard/app/services/meeting_validation.py`: pure evidence, metadata, member, category, task-reference, and temporal validators.
- Create `bowei_ai_dashboard/app/services/meeting_workbench.py`: transaction-safe source/revision/run/candidate creation, review application, and immutable revision projection.
- Modify `bowei_ai_dashboard/app/models.py`: transcript source/revision, analysis run/candidate, and enriched meeting-revision models.
- Modify `bowei_ai_dashboard/app/schemas.py`: analysis-run, candidate-review, transcript-revision, and save-version request/response schemas.
- Modify `bowei_ai_dashboard/app/routers/meetings.py`: replace `/analyze` with run APIs and append revisions for status transitions.
- Create `bowei_ai_dashboard/migrations/versions/a1b2c3d4e5f_add_meeting_analysis_audit.py`: additive schema migration and safe backfill of existing meeting text into immutable sources.
- Create `bowei_ai_dashboard/scripts/backfill_meeting_transcript_sources.py`: explicit, logged application-admin backfill command.
- Modify `frontend/src/api/meetings.ts` and `frontend/src/types.ts`: typed run/candidate/evidence/version APIs.
- Create `frontend/src/features/meeting/MeetingAnalysisReviewWorkspace.tsx`: evidence-first candidate review and save-preview UI.
- Modify `frontend/src/features/meeting/NewMeetingModal.tsx`: metadata input, analysis-run creation, and review-workspace integration; remove the `confirmed_items_json -> risk_items_json` remap.
- Modify `frontend/src/pages/MeetingPage.tsx`: display the selected version's run/source/revision provenance and all five separate item groups.
- Create focused pytest and Node tests listed in the tasks below; retain legacy meeting-revision tests as regression coverage.

### Task 1: Specify and test the immutable transcript and Agent-audit schema

**Files:**
- Modify: `bowei_ai_dashboard/app/models.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_analysis_models.py`

- [ ] **Step 1: Write failing ORM tests for source/revision/run/candidate relationships and revision provenance.**

```python
def test_meeting_analysis_records_source_revision_run_and_candidate():
    source = models.MeetingTranscriptSource(meeting_id=1, raw_text="原始转写", source_hash="h1")
    revision = models.MeetingTranscriptRevision(source_id=1, revision_no=1, text="纠错转写", text_hash="h2")
    run = models.MeetingAnalysisRun(project_id=1, source_id=1, transcript_revision_id=1, timezone="Asia/Shanghai")
    candidate = models.MeetingAnalysisCandidate(run_id=1, candidate_type="action_item", validation_status="needs_confirmation")
    assert source.raw_text == "原始转写"
    assert revision.revision_no == 1
    assert candidate.review_status == "pending"
```

- [ ] **Step 2: Run the test and verify it fails because the new models do not exist.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_analysis_models.py -q`

Expected: FAIL with an `AttributeError` for `MeetingTranscriptSource`.

- [ ] **Step 3: Add the additive SQLAlchemy models and enriched revision columns.**

```python
class MeetingTranscriptSource(Base, TimestampMixin):
    __tablename__ = "meeting_transcript_sources"
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=True, index=True)
    raw_text = Column(Text, nullable=False)
    source_hash = Column(String(64), nullable=False, index=True)
    source_type = Column(String(20), nullable=False, default="manual")
    created_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True)

class MeetingTranscriptRevision(Base, TimestampMixin):
    __tablename__ = "meeting_transcript_revisions"
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("meeting_transcript_sources.id"), nullable=False, index=True)
    revision_no = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    text_hash = Column(String(64), nullable=False)
    created_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True)
    __table_args__ = (UniqueConstraint("source_id", "revision_no", name="uq_meeting_transcript_revision"),)
```

Add `MeetingAnalysisRun` with immutable JSON fields `member_snapshot_json`, `plan_snapshot_json`, `agent_input_json`, `raw_response_json`, `normalized_output_json`, `validation_output_json`, provider/model/policy/prompt identifiers, `reference_at`, and `timezone`.  Add `MeetingAnalysisCandidate` with `agent_proposal_json`, `evidence_json`, `validation_json`, `validation_status`, `review_status`, `final_value_json`, reviewer fields, and `review_comment`.  Add nullable `transcript_source_id`, `transcript_revision_id`, `analysis_run_id`, `parent_revision_id`, `revision_kind`, `agent_output_json`, `validation_output_json`, `human_output_json`, and `human_diff_json` to `MeetingRevision`.

- [ ] **Step 4: Add Pydantic response/request types that expose no untyped JSON strings to the new UI.**

```python
class EvidenceRef(BaseModel):
    source_id: int
    transcript_revision_id: int | None = None
    char_start: int
    char_end: int
    quote: str
    source_hash: str
    segment_id: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None

class CandidateReviewPayload(BaseModel):
    review_status: Literal["accepted", "needs_confirmation", "ignored"]
    final_value: dict[str, Any] = Field(default_factory=dict)
    review_comment: str = ""
```

- [ ] **Step 5: Run the model tests and existing revision-model tests.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_analysis_models.py tests/test_meeting_revision_model.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the schema contract.**

```bash
git add bowei_ai_dashboard/app/models.py bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/tests/test_meeting_analysis_models.py
git commit -m "feat: add meeting analysis audit models"
```

### Task 2: Implement deterministic context, evidence, and temporal validation

**Files:**
- Create: `bowei_ai_dashboard/app/services/meeting_validation.py`
- Modify: `bowei_ai_dashboard/app/services/meeting_traceability.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_validation.py`

- [ ] **Step 1: Write failing pure-function tests for the exact validation policy.**

```python
def test_next_week_is_an_iso_week_range():
    value = resolve_temporal_expression("下周", date(2026, 8, 3), ZoneInfo("Asia/Shanghai"))
    assert value == {"expression": "下周", "start": "2026-08-10", "end": "2026-08-16", "status": "passed"}

def test_ambiguous_month_day_is_not_given_an_invented_year():
    value = resolve_temporal_expression("8月3日前", date(2026, 8, 3), ZoneInfo("Asia/Shanghai"))
    assert value["status"] == "needs_confirmation"
    assert value["start"] is None

def test_project_member_without_owner_evidence_needs_confirmation():
    candidate = {"owner_person_id": 23, "owner_name": "刘万超", "evidence": []}
    assert validate_action_owner(candidate, {23: "刘万超"}) == ["owner is not supported by transcript evidence"]
```

- [ ] **Step 2: Run the tests and verify they fail.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_validation.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.meeting_validation'`.

- [ ] **Step 3: Implement a pure validator with four statuses and source-span verification.**

```python
VALIDATION_STATES = {"passed", "warning", "needs_confirmation", "blocked"}

def validate_evidence(ref: dict[str, Any], transcript: str, expected_hash: str) -> list[dict[str, str]]:
    start, end = ref.get("char_start"), ref.get("char_end")
    if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
        return [{"code": "invalid_span", "status": "blocked"}]
    if ref.get("source_hash") != expected_hash or transcript[start:end] != ref.get("quote"):
        return [{"code": "evidence_mismatch", "status": "blocked"}]
    return []
```

Implement `resolve_temporal_expression()` using `datetime`, `timedelta`, and `ZoneInfo`.  Resolve only explicit calendar-safe expressions; retain `expression`, `reference_date`, and timezone in all results.  Return `needs_confirmation` for vague/ambiguous expressions.  Require exact member ID/name plus source evidence for an accepted action owner.  Block an acceptance criterion, decision, risk impact, probability, or mitigation that does not have evidence or a clearly labelled non-meeting snapshot source.  Remove the current `normalize_action_items` behavior that writes `待确认` as a fabricated acceptance criterion.

- [ ] **Step 4: Add category tests ensuring no cross-category projection.**

```python
def test_completed_progress_is_not_a_risk_or_decision():
    package = validate_candidates([{ "type": "progress", "content": "版本已完成更新", "evidence": [VALID_REF] }], CONTEXT)
    assert package[0]["candidate_type"] == "progress"
    assert package[0]["validation_status"] == "passed"
```

- [ ] **Step 5: Run validator and legacy traceability tests.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_validation.py tests/test_meeting_date_traceability.py tests/test_meeting_extraction_traceability.py -q`

Expected: PASS.

- [ ] **Step 6: Commit deterministic validation.**

```bash
git add bowei_ai_dashboard/app/services/meeting_validation.py bowei_ai_dashboard/app/services/meeting_traceability.py bowei_ai_dashboard/tests/test_meeting_validation.py
git commit -m "feat: validate meeting candidates against evidence"
```

### Task 3: Build a review-only ordinary-meeting Agent package

**Files:**
- Create: `bowei_ai_dashboard/app/services/meeting_analysis_agent.py`
- Create: `bowei_ai_dashboard/app/services/meeting_workbench.py`
- Modify: `bowei_ai_dashboard/app/routers/meetings.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_analysis_agent.py`

- [ ] **Step 1: Write failing tests that prove a run freezes member/task context and does not invent task writes.**

```python
def test_run_keeps_snapshot_and_returns_only_review_candidates(monkeypatch, db):
    monkeypatch.setattr(meetings, "_do_analyze", lambda *_: {
        "candidates": [{"type": "action_item", "action": "完成联调", "evidence": [EVIDENCE]}]
    })
    response = create_analysis_run(project_id=1, transcript_text="刘万超下周三前完成联调", current_user="owner", db=db)
    assert response["status"] == "review"
    assert response["member_snapshot"]["members"][0]["name"] == "刘万超"
    assert db.query(models.Task).count() == 0
```

- [ ] **Step 2: Run the test and verify it fails before adding the run endpoint.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_analysis_agent.py -q`

Expected: FAIL because `create_analysis_run` is absent.

- [ ] **Step 3: Implement context snapshots, an untrusted JSON extraction contract, and persistence.**

```python
def build_meeting_context(project_id: int, db: Session, reference_at: datetime) -> dict[str, Any]:
    return {
        "members": [{"person_id": row.person_id, "name": row.person_name_snapshot, "role": row.role} for row in members],
        "tasks": [{"id": task.id, "title": task.key_task, "owner": task.owner, "plan_time": task.plan_time,
                   "completion_standard": task.completion_standard} for task in tasks],
        "reference_at": reference_at.isoformat(),
        "timezone": "Asia/Shanghai",
    }
```

Require the model to return only `metadata_candidates`, `action_items`, `decisions`, `decision_requests`, `risks`, and `progress_items`, each with evidence spans.  Record provider/model/policy/prompt identifiers, the exact input hash, raw parsed response, normalized package, and validation package in `MeetingAnalysisRun`.  Persist one candidate row per metadata/candidate item with validation state; never call task, subtask, or issue write APIs.

Implement the only state-changing workflow functions in `meeting_workbench.py`: `create_analysis_run(project_id, transcript_text, metadata, actor_person_id, db)`, `apply_candidate_review(run, candidate, payload, reviewer_person_id, db)`, `save_run_as_draft(run, actor, actor_person_id, db)`, and `backfill_meeting_transcript_sources(db)`.

`save_run_as_draft` builds meeting content solely from candidates marked `accepted` or `needs_confirmation`, rejects `blocked` items, computes `human_diff`, creates or links a `Meeting`, and appends exactly one `MeetingRevision`.  It must not import task, subtask, issue, achievement, or notification write services.

- [ ] **Step 4: Replace the unsafe `/analyze` flow with explicit run endpoints.**

```text
POST /api/meetings/analysis-runs
GET  /api/meetings/analysis-runs/{run_id}
PATCH /api/meetings/analysis-runs/{run_id}/candidates/{candidate_id}/review
POST /api/meetings/analysis-runs/{run_id}/save-draft
POST /api/meetings/{meeting_id}/transcript-revisions
```

`save-draft` must reject any included candidate whose validation status is `blocked`, construct the complete human-selected output server-side, call `append_meeting_revision`, and write `crud.log` events for run creation, candidate review, source/revision view, and version save.  Change `patch_meeting_status` to append a revision before commit.

- [ ] **Step 5: Run route, permission, and no-task-write regression tests.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_analysis_agent.py tests/test_meeting_draft_review.py tests/test_meeting_revision_api.py -q`

Expected: PASS.

- [ ] **Step 6: Commit Agent orchestration.**

```bash
git add bowei_ai_dashboard/app/services/meeting_analysis_agent.py bowei_ai_dashboard/app/services/meeting_workbench.py bowei_ai_dashboard/app/routers/meetings.py bowei_ai_dashboard/tests/test_meeting_analysis_agent.py
git commit -m "feat: add review-only meeting analysis runs"
```

### Task 4: Migrate and safely backfill existing meeting history

**Files:**
- Create: `bowei_ai_dashboard/migrations/versions/a1b2c3d4e5f_add_meeting_analysis_audit.py`
- Create: `bowei_ai_dashboard/scripts/backfill_meeting_transcript_sources.py`
- Modify: `bowei_ai_dashboard/app/services/meeting_revisions.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_analysis_migration.py`

- [ ] **Step 1: Write an additive migration test for legacy source backfill and V0/V1 continuity.**

```python
def test_legacy_meeting_backfill_keeps_original_text_and_version_numbers(db):
    meeting = models.Meeting(id=1, transcript_text="历史原文", summary="历史纪要")
    db.add(meeting)
    db.commit()
    backfill_meeting_transcript_sources(db)
    source = db.query(models.MeetingTranscriptSource).filter_by(meeting_id=1).one()
    legacy = db.query(models.MeetingRevision).filter_by(meeting_id=1, version_no=0).one()
    assert source.raw_text == "历史原文"
    assert legacy.is_legacy_snapshot
```

- [ ] **Step 2: Run it and verify it fails before the migration/backfill helper exists.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_analysis_migration.py -q`

Expected: FAIL with an import or missing-table error.

- [ ] **Step 3: Create an additive Alembic migration and idempotent application preflight.**

The migration must create only new tables/columns/indexes; it must not modify `meetings.transcript_text` or renumber a user version.  Implement `scripts/backfill_meeting_transcript_sources.py` to open the configured database, call `backfill_meeting_transcript_sources(db)`, commit, and print the number of sources created.  Use that command after migration to create one source for every existing non-empty transcript and link existing revisions to that source.  Do not invent a transcript revision for historical text.  Before applying against the local SQLite database, run `alembic current`, inspect `sqlite_master`, back up the exact file, and stop if the recorded revision and physical schema disagree.

- [ ] **Step 4: Extend revision projection to retain source/run provenance and status transitions.**

```python
revision = append_meeting_revision(
    db, meeting, human_values, saved_by=current_user,
    transcript_source_id=source.id, transcript_revision_id=revision_id,
    analysis_run_id=run.id, revision_kind="draft_save",
    human_output=human_values, human_diff=diff,
)
```

Retain existing `is_legacy_snapshot=True, version_no=0` behavior for pre-versioning rows and continue numbering current user saves at V1, V2, and so on.

- [ ] **Step 5: Run migration/revision tests and SQL schema checks.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_analysis_migration.py tests/test_meeting_revision_service.py tests/test_meeting_revision_model.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the migration and projection work.**

```bash
git add bowei_ai_dashboard/migrations/versions/a1b2c3d4e5f_add_meeting_analysis_audit.py bowei_ai_dashboard/scripts/backfill_meeting_transcript_sources.py bowei_ai_dashboard/app/services/meeting_revisions.py bowei_ai_dashboard/app/services/meeting_workbench.py bowei_ai_dashboard/tests/test_meeting_analysis_migration.py
git commit -m "feat: preserve meeting analysis provenance in revisions"
```

### Task 5: Replace the opaque draft form with the evidence review workbench

**Files:**
- Create: `frontend/src/features/meeting/MeetingAnalysisReviewWorkspace.tsx`
- Modify: `frontend/src/features/meeting/NewMeetingModal.tsx`
- Modify: `frontend/src/api/meetings.ts`
- Modify: `frontend/src/types.ts`
- Create: `frontend/tests/meetingEvidenceReviewWorkspace.test.mjs`

- [ ] **Step 1: Write a frontend structure test for the non-negotiable review controls.**

```javascript
test('meeting review shows proposal, evidence, validation, and explicit review actions', () => {
  const source = read('src/features/meeting/MeetingAnalysisReviewWorkspace.tsx')
  assert.match(source, /Agent 提议/)
  assert.match(source, /原文证据/)
  assert.match(source, /校验状态/)
  assert.match(source, /修改后接受/)
  assert.match(source, /标记待确认/)
  assert.match(source, /忽略/)
  assert.doesNotMatch(source, /推送为任务/)
})
```

- [ ] **Step 2: Run the test and verify it fails before the workspace exists.**

Run: `cd frontend; node --test tests/meetingEvidenceReviewWorkspace.test.mjs`

Expected: FAIL with `ENOENT` for the new component.

- [ ] **Step 3: Add typed run/candidate APIs and an evidence-first review component.**

```ts
export type MeetingEvidence = {
  quote: string; char_start: number; char_end: number; source_hash: string
  segment_id?: string; start_ms?: number; end_ms?: number
}
export type MeetingCandidate = {
  id: number; candidate_type: 'action_item' | 'decision' | 'decision_request' | 'risk' | 'progress' | 'metadata'
  agent_proposal: Record<string, unknown>; evidence: MeetingEvidence[]
  validation_status: 'passed' | 'warning' | 'needs_confirmation' | 'blocked'
  validation_messages: string[]; review_status: 'pending' | 'accepted' | 'needs_confirmation' | 'ignored'
  final_value: Record<string, unknown>
}
```

Render the transcript beside the selected candidate and highlight the exact character range.  Show original relative dates and normalized values together.  Disable acceptance for `blocked`; allow `needs_confirmation` to be saved only as an explicitly unresolved item.  Keep title/type/host/participants empty unless they were entered by the user or have a transcript/system source badge.  Remove `PushToTasksModal` from this save path and remove the `confirmed_items_json`/`risk_items_json` aliasing.

- [ ] **Step 4: Add a save-preview dialog before the version write.**

The dialog must list the metadata provenance, accepted/edited/unresolved/ignored candidates, original transcript revision, analysis-run identifier, and the full difference from the previous version.  Its only save action calls `/save-draft`; it contains no task creation/update action.

- [ ] **Step 5: Run frontend tests and production build.**

Run: `cd frontend; node --test tests/meetingEvidenceReviewWorkspace.test.mjs tests/meetingDraftReviewStructure.test.mjs tests/meetingRevisionHistory.test.mjs; npm run build`

Expected: all Node tests PASS and Vite build exits 0.

- [ ] **Step 6: Commit the review workbench.**

```bash
git add frontend/src/features/meeting/MeetingAnalysisReviewWorkspace.tsx frontend/src/features/meeting/NewMeetingModal.tsx frontend/src/api/meetings.ts frontend/src/types.ts frontend/tests/meetingEvidenceReviewWorkspace.test.mjs
git commit -m "feat: add evidence-first meeting draft review"
```

### Task 6: Present full provenance and immutable history on the meeting page

**Files:**
- Modify: `frontend/src/pages/MeetingPage.tsx`
- Modify: `frontend/src/api/meetings.ts`
- Create: `frontend/tests/meetingAnalysisHistory.test.mjs`
- Create: `bowei_ai_dashboard/tests/test_meeting_analysis_history_api.py`

- [ ] **Step 1: Write failing API/UI tests for per-version provenance and five distinct sections.**

```python
def test_revision_detail_returns_run_source_and_human_diff(client):
    payload = client.get('/api/meetings/1/revisions/2').json()
    assert payload['analysis_run']['id'] == 7
    assert payload['transcript_source']['source_hash']
    assert payload['human_diff']['summary']
```

```javascript
test('history keeps decisions, decision requests, risks, and progress separate', () => {
  const source = read('src/pages/MeetingPage.tsx')
  for (const label of ['行动项', '已决策', '待决策', '风险/阻塞', '进展']) assert.match(source, new RegExp(label))
  assert.match(source, /原始转写/)
  assert.match(source, /转写修订版/)
  assert.match(source, /分析运行/)
})
```

- [ ] **Step 2: Run the tests and verify they fail before detail payload/UI support exists.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_analysis_history_api.py -q; cd ..\frontend; node --test tests/meetingAnalysisHistory.test.mjs`

Expected: backend and frontend tests FAIL on absent fields/labels.

- [ ] **Step 3: Add a revision-detail endpoint and provenance panel.**

Return sanitized source/revision/run provenance only to users who can already view the meeting draft.  Add links/buttons to inspect immutable original text, the selected correction revision, run metadata, candidate validation, and human diff.  Record the source/revision view in `crud.log` without logging raw transcript text into the audit log.

- [ ] **Step 4: Render distinct category sections and preserve missing values visibly.**

Do not collapse decision requests into decisions or risks.  Display null acceptance criteria/impact/mitigation as `未在原文确认`, not a generated sentence.  Show a relative date as `下周三（已换算：2026-08-12）`; show unresolved dates as `8月3日前（待确认）`.

- [ ] **Step 5: Run complete meeting-focused verification.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_analysis_history_api.py tests/test_meeting_analysis_agent.py tests/test_meeting_validation.py tests/test_meeting_revision_api.py -q; cd ..\frontend; node --test tests/meetingAnalysisHistory.test.mjs tests/meetingEvidenceReviewWorkspace.test.mjs tests/meetingRevisionHistory.test.mjs; npm run build`

Expected: all tests PASS and build exits 0.

- [ ] **Step 6: Commit history/provenance UI.**

```bash
git add frontend/src/pages/MeetingPage.tsx frontend/src/api/meetings.ts frontend/tests/meetingAnalysisHistory.test.mjs bowei_ai_dashboard/tests/test_meeting_analysis_history_api.py
git commit -m "feat: expose auditable meeting analysis history"
```

### Task 7: Verify permissions, migration safety, and the original failure regression

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_meeting_draft_review.py`
- Modify: `bowei_ai_dashboard/tests/test_meeting_revision_api.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_agent_regressions.py`
- Modify: `frontend/tests/meetingDraftReviewStructure.test.mjs`

- [ ] **Step 1: Add regression cases for the user-reported failed submission.**

```python
def test_unknown_person_is_blocked_not_written_as_a_project_host(run):
    assert candidate_for("张总")['validation_status'] == 'blocked'

def test_completed_update_is_progress_not_risk():
    assert candidate_for("平台版本更新已完成")['candidate_type'] == 'progress'

def test_unmade_question_is_not_a_decision():
    assert candidate_for("时间待定")['candidate_type'] != 'decision'

def test_draft_save_never_creates_or_updates_project_tasks(db):
    save_run_as_draft(...)
    assert db.query(models.Task).count() == original_task_count
```

- [ ] **Step 2: Run the new regressions and verify each fails before final corrections.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_agent_regressions.py -q`

Expected: FAIL until all category, person, and write-boundary defects are fixed.

- [ ] **Step 3: Make only the smallest corrections necessary for every regression to pass.**

Keep the existing access rules: creator, project owner, and CEO can view a draft; ordinary project members cannot.  Ensure analysis-run/source endpoints use the same project checks, and verify a status change creates a revision.  Do not broaden task/issue/achievement write permissions.

- [ ] **Step 4: Run migration preflight before changing any shared database.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m alembic current; .\.venv\Scripts\python.exe -c "from app.database import engine; from sqlalchemy import inspect; print(sorted(inspect(engine).get_table_names()))"`

Expected: record the Alembic revision and table list.  If they disagree with the expected migration chain, do not run `upgrade`; take a timestamped backup and resolve the drift explicitly first.

- [ ] **Step 5: Run all scoped tests, then the backend suite and frontend suite.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_agent_regressions.py tests/test_meeting_analysis_models.py tests/test_meeting_validation.py tests/test_meeting_analysis_agent.py tests/test_meeting_analysis_history_api.py tests/test_meeting_revision_service.py tests/test_meeting_revision_api.py -q; .\.venv\Scripts\python.exe -m pytest tests -q; cd ..\frontend; node --test tests/*.test.mjs; npm run build`

Expected: scoped tests PASS; record and investigate any full-suite failure before claiming completion.

- [ ] **Step 6: Commit verified regression coverage.**

```bash
git add bowei_ai_dashboard/tests frontend/tests
git commit -m "test: cover evidence-driven meeting agent regressions"
```

## Plan self-review

- Spec coverage: Tasks 1 and 4 preserve originals/revisions/immutable versions; Task 2 implements dates, evidence, categories, and no-invention validation; Task 3 adds the review-only Agent and no-task-write boundary; Tasks 5 and 6 deliver transparent review/history UI; Task 7 verifies permissions, migration safety, and every reported failure.
- Consistency: all runtime names use `MeetingAnalysisRun`, `MeetingAnalysisCandidate`, `MeetingTranscriptSource`, and `MeetingTranscriptRevision`; the only formal write endpoint is `save-draft`.
- No hidden writes: neither the Agent service nor the review UI imports task, subtask, issue, or achievement write operations.
