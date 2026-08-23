# Project Meeting Execution Context Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze confirmed, key-task-scoped work-report cards and execution events into each project meeting run so the meeting Agent can validate Word facts against the project’s real execution context.

**Architecture:** Extend the existing immutable `ProjectMeetingRun.snapshot_json`; no new persistence entity or migration is required. `build_project_meeting_snapshot()` computes a China-local meeting window, attaches `execution_context` to each key task, and records only canonical confirmed task cards and confirmed execution events. The existing frozen read tools expose this context; the existing normalizer remains the boundary that requires Word evidence for any proposed writeback.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite/PostgreSQL-compatible ORM queries, Pydantic, pytest, existing `UpdateSubmission` / `KeyTaskExecutionEvent` models.

---

## File map

- Modify: `bowei_ai_dashboard/app/services/project_meeting_minutes.py`
  - Compute the meeting window and build deterministic, immutable execution facts in the snapshot.
- Modify: `bowei_ai_dashboard/app/services/project_meeting_agent_tools.py`
  - Return the frozen execution context through `get_plan_node_detail` and `get_recent_progress`.
- Modify: `bowei_ai_dashboard/app/services/project_meeting_agent.py`
  - Tell the Agent that execution context is baseline-only, never Word evidence or an independent writeback source.
- Modify: `bowei_ai_dashboard/app/services/cross_project_submission.py`
  - Make task-card canonicalization a reusable validation boundary.
- Modify: `bowei_ai_dashboard/app/routers/updates.py`
  - Require every direct work-report task card to have a canonical same-project key-task assignment before persisting it.
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py`
  - Cover window calculation, report-card/event projection, frozen snapshot behavior, and Word-evidence-only writeback.
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_agent_tools.py`
  - Cover read-tool exposure and frozen-only filtering for execution context.
- Modify: `bowei_ai_dashboard/tests/test_cross_project_submission_batch.py`
  - Cover reusable task-card validation and rejection of an unassigned card.
- Modify: `bowei_ai_dashboard/tests/test_execution_submission_to_work_progress_flow.py`
  - Cover direct submission rejection when any task card is unassigned or cross-project.

No migration, frontend change, review-route change, or writeback-route change is in scope.

### Task 1: Establish the execution-context snapshot contract with failing service tests

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py`

- [ ] **Step 1: Add test helpers for canonical confirmed report cards and events**

  Add imports:

  ```python
  from datetime import datetime, timezone

  from app.domain import submission_status as SS
  from app.services.key_task_execution import record_execution_event
  ```

  Add a helper that writes a `models.UpdateSubmission` with `confirm_status=SS.S_CONFIRMED`, a non-null `confirmed_at`, project ID `1`, and this canonical card in `human_result_json`:

  ```python
  {
      "task_reports": [{
          "parent_task_id": 10,
          "matched_subtask_id": 20,
          "matched_subtask_title": "Weekly delivery",
          "match_status": "matched",
          "content": "Acceptance checklist reviewed",
          "actual_output": "Signed checklist",
          "next_step": "Prepare release",
      }]
  }
  ```

  Use `datetime(2026, 8, 1, 2, tzinfo=None)` for a report confirmed after the Asia/Shanghai 2026-07-27 meeting cutoff (which is 2026-07-27 16:00 UTC), and create an event with `status_before="in_progress"`, `status_after="completed"`, `occurred_at=datetime(2026, 8, 2, 3)`, `authority="confirmed"`.

- [ ] **Step 2: Write failing tests for a non-first-meeting window**

  Create a published `Meeting(project_id=1, meeting_date="2026-07-27", publish_status="published")`. Assert that the snapshot has:

  ```python
  assert snapshot["execution_window"] == {
      "start": "2026-07-28T00:00:00+08:00",
      "end": snapshot["execution_window"]["end"],
      "basis": "last_published_meeting_date",
      "last_published_meeting_id": meeting.id,
  }
  context = snapshot["workstreams"][0]["key_tasks"][0]["execution_context"]
  assert context["confirmed_reports"][0]["source_submission_id"] == submission.id
  assert context["confirmed_reports"][0]["card_index"] == 0
  assert context["confirmed_reports"][0]["source_type"] == "confirmed_report"
  assert context["confirmed_events"][0]["status_before"] == "in_progress"
  assert context["confirmed_events"][0]["status_after"] == "completed"
  assert context["confirmed_events"][0]["source_type"] == "confirmed_event"
  ```

  Add an otherwise valid report confirmed at `datetime(2026, 7, 27, 15, 59)` and an event at that same time; assert neither appears. This proves the lower bound is the next local calendar day, not merely the old meeting record’s date text.

  Add a meeting with `review_status="approved"` but `publish_status="draft"`; assert it remains visible in legacy history if existing behavior requires it, but it does not become `last_published_meeting_id` or move the execution window boundary. This proves the window uses only published meeting records.

- [ ] **Step 3: Write failing tests for first meeting and invalid historical cards**

  Assert that, with no published meetings and `Project(start_date="2026-07-01")`, `execution_window["basis"] == "project_start_date"` and a confirmed report after the start date is included.

  Set `project.start_date = ""` with no published meeting and assert `execution_window is None`, all `confirmed_reports` / `confirmed_events` are empty, and `diagnostics` includes `{"code": "missing_execution_window_start"}`. This proves the service does not invent a first-meeting range.

  Add a confirmed parent submission with a card missing `matched_subtask_id`. Assert it is not included and that the snapshot has an explicit diagnostic:

  ```python
  assert snapshot["diagnostics"] == [{
      "code": "invalid_confirmed_report_card",
      "source_submission_id": invalid.id,
      "card_index": 0,
      "reason": "missing or invalid key-task assignment",
  }]
  ```

- [ ] **Step 4: Run the focused service tests to verify they fail**

  Run:

  ```powershell
  cd bowei_ai_dashboard
  .\.venv\Scripts\python.exe -m pytest tests/test_project_meeting_minutes_service.py -q
  ```

  Expected: the new assertions fail because `execution_window`, `execution_context`, and `diagnostics` do not exist yet.

### Task 2: Build the immutable execution-context snapshot

**Files:**
- Modify: `bowei_ai_dashboard/app/services/project_meeting_minutes.py`
- Test: `bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py`

- [ ] **Step 1: Add deterministic window and projection helpers**

  Import `timedelta`, `time`, `timezone`, and `ZoneInfo`; use the existing `utc_now()` helper. Add these private helpers above `build_project_meeting_snapshot()`:

  ```python
  _SHANGHAI = ZoneInfo("Asia/Shanghai")

  def _meeting_window(project: models.Project, published: list[models.Meeting]) -> dict[str, Any]:
      last = max(published, key=lambda row: (_meeting_date(row), row.id), default=None)
      boundary = _meeting_date(last) if last else _parse_date(project.start_date)
      if boundary is None:
          return {"start_utc": None, "public": None, "diagnostic": "missing_execution_window_start"}
      local_start = datetime.combine(boundary + timedelta(days=1), time.min, tzinfo=_SHANGHAI)
      return {
          "start_utc": local_start.astimezone(timezone.utc).replace(tzinfo=None),
          "public": {
              "start": local_start.isoformat(),
              "end": utc_now().replace(tzinfo=timezone.utc).astimezone(_SHANGHAI).isoformat(),
              "basis": "last_published_meeting_date" if last else "project_start_date",
              "last_published_meeting_id": last.id if last else None,
          },
          "diagnostic": None,
      }
  ```

  Implement `_parse_date()` with `date.fromisoformat`; return `None` for malformed legacy dates. Implement `_meeting_date()` as a wrapper over a meeting’s `meeting_date`.

- [ ] **Step 2: Add canonical read-only task-card projection**

  Add `_confirmed_report_cards(...) -> tuple[dict[int, list[dict]], list[dict]]`. Query only rows that satisfy:

  ```python
  models.UpdateSubmission.project_id == project_id
  models.UpdateSubmission.confirm_status.in_(SS.CONFIRMED_AND_STORED)
  models.UpdateSubmission.confirmed_at >= window_start_utc
  models.UpdateSubmission.confirmed_at <= window_end_utc
  ```

  Parse `human_result_json` first, falling back to `ai_result_json`. For every `task_reports` item, accept it only when all are true:

  ```python
  card["match_status"] == "matched"
  int(card["parent_task_id"]) == task.id
  int(card["matched_subtask_id"]) == subtask.id
  subtask.task_id == task.id
  task.project_id == project_id
  ```

  Project accepted cards to immutable plain dictionaries. Do not expose the raw complete submission JSON:

  ```python
  {
      "source_type": "confirmed_report",
      "source_submission_id": submission.id,
      "card_index": index,
      "key_task_id": subtask.id,
      "submitter": submission.submitter or "",
      "submitter_id": submission.submitter_id,
      "submitted_at": _json_value(submission.created_at),
      "confirmed_at": _json_value(submission.confirmed_at),
      "content": str(card.get("content") or card.get("summary") or ""),
      "actual_output": str(card.get("actual_output") or ""),
      "next_step": str(card.get("next_step") or ""),
  }
  ```

  For a malformed card, append exactly one diagnostic with the submission ID and card index; do not infer a key task from text.

- [ ] **Step 3: Add confirmed execution-event projection**

  Query `KeyTaskExecutionEvent` joined to `SubTask` and `Task`, restricted to project, task ownership, `authority == "confirmed"`, and `occurred_at` inside the same window. Return deterministic event dictionaries ordered by `occurred_at.asc(), id.asc()` with:

  ```python
  {
      "source_type": "confirmed_event",
      "event_id": event.id,
      "key_task_id": event.key_task_id,
      "execution_schedule_id": event.execution_plan_id,
      "event_type": event.event_type,
      "event_source_type": event.source_type,
      "event_source_id": event.source_id,
      "actor": {"person_id": event.actor_person_id, "name": event.actor_name_snapshot or ""},
      "occurred_at": _json_value(event.occurred_at),
      "confirmed_at": _json_value(event.confirmed_at),
      "effective_at": _json_value(event.effective_at),
      "status_before": event.status_before,
      "status_after": event.status_after,
      "progress_summary": event.progress_summary or "",
      "next_step": event.next_step or "",
      "affects_current_progress": bool(event.affects_current_progress),
      "display_payload": _json_object(event.display_payload_json),
  }
  ```

- [ ] **Step 4: Attach facts without changing existing snapshot keys**

  Keep `execution_schedules`, `recent_progress`, `history`, and `previous_meetings` byte-for-byte compatible. Add top-level `execution_window` and `diagnostics`; add this to every key task:

  ```python
  "execution_context": {
      "current_task_baseline": {
          "id": subtask.id,
          "title": subtask.title or "",
          "assignee": subtask.assignee or "",
          "assignee_id": subtask.assignee_id,
          "status": subtask.status or "",
          "plan_time": subtask.plan_time or "",
          "completion_criteria": subtask.completion_criteria or "",
          "notes": subtask.notes or "",
      },
      "current_execution_schedules": [_schedule_snapshot(item) for item in schedules],
      "confirmed_reports": report_cards_by_subtask.get(subtask.id, []),
      "confirmed_events": events_by_subtask.get(subtask.id, []),
  }
  ```

  Keep all values JSON serializable through `_json_value()`.

  When `_meeting_window()` has no start, set top-level `execution_window` to `None`, attach `{"code": "missing_execution_window_start"}` to `diagnostics`, and deliberately return empty report/event collections. Do not run unbounded report or event queries.

- [ ] **Step 5: Run the focused service tests to verify they pass**

  Run:

  ```powershell
  cd bowei_ai_dashboard
  .\.venv\Scripts\python.exe -m pytest tests/test_project_meeting_minutes_service.py -q
  ```

  Expected: PASS, including all legacy snapshot tests.

### Task 3: Expose only frozen, key-task-scoped execution context to the Agent

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_agent_tools.py`
- Modify: `bowei_ai_dashboard/app/services/project_meeting_agent_tools.py`

- [ ] **Step 1: Write failing read-tool tests**

  Extend the fixture’s key task with an `execution_context` containing one report and one event. Assert `get_plan_node_detail` for that key task returns:

  ```python
  assert detail["execution_context"] == snapshot["workstreams"][0]["key_tasks"][0]["execution_context"]
  ```

  Assert `get_recent_progress` returns the frozen window and only the matched key task’s values:

  ```python
  assert tools.execute("get_recent_progress", {"project_id": 7, "key_task_id": 20}) == {
      "window": snapshot["execution_window"],
      "items": [snapshot["recent_progress"][0]],
      "confirmed_reports": snapshot["workstreams"][0]["key_tasks"][0]["execution_context"]["confirmed_reports"],
      "confirmed_events": snapshot["workstreams"][0]["key_tasks"][0]["execution_context"]["confirmed_events"],
  }
  ```

  Mutate the original fixture after creating `ProjectMeetingAgentTools`; assert returned execution context retains its pre-mutation values.

- [ ] **Step 2: Run the tool tests to verify they fail**

  Run:

  ```powershell
  cd bowei_ai_dashboard
  .\.venv\Scripts\python.exe -m pytest tests/test_project_meeting_agent_tools.py -q
  ```

  Expected: FAIL because the tool currently omits `execution_context`, window, report cards, and events.

- [ ] **Step 3: Implement minimal frozen-tool changes**

  In `_get_plan_node_detail`, add `"execution_context": deepcopy(key_task.get("execution_context", {}))` to key-task and schedule responses. Do not add raw `notes` or unrelated fields to `_node_summary()`.

  Replace `_get_recent_progress()` return construction with deterministic, snapshot-only aggregation:

  ```python
  contexts = [
      key_task.get("execution_context", {})
      for workstream in self._snapshot.get("workstreams", [])
      for key_task in workstream.get("key_tasks", [])
      if isinstance(key_task, dict)
      and (key_task_id is None or key_task.get("id") == key_task_id)
  ]
  return {
      "window": self._snapshot.get("execution_window"),
      "items": items,
      "confirmed_reports": [item for context in contexts for item in context.get("confirmed_reports", [])],
      "confirmed_events": [item for context in contexts for item in context.get("confirmed_events", [])],
  }
  ```

  Preserve existing project-ID boundary checks and deepcopy isolation.

- [ ] **Step 4: Run tool tests to verify they pass**

  Run the command from Step 2. Expected: PASS.

### Task 4: Preserve the Word-evidence boundary in the Agent prompt and validator

**Files:**
- Modify: `bowei_ai_dashboard/app/services/project_meeting_agent.py`
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_agent.py`
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py`

- [ ] **Step 1: Write failing prompt and normalization tests**

  Add a prompt-contract test asserting the generated Agent system prompt includes all of:

  ```text
  confirmed_report
  confirmed_event
  project_baseline
  does not replace Word evidence
  ```

  Add a normalization test whose only claimed support for a proposed schedule update is a `confirmed_event`. Give it no matching Word evidence span and assert:

  ```python
  assert proposal["validation"]["state"] == "needs_confirmation"
  assert "evidence" in " ".join(proposal["validation"]["errors"])
  ```

- [ ] **Step 2: Run the targeted tests to verify they fail**

  Run:

  ```powershell
  cd bowei_ai_dashboard
  .\.venv\Scripts\python.exe -m pytest tests/test_project_meeting_agent.py tests/test_project_meeting_minutes_service.py -q
  ```

  Expected: prompt assertion fails; if the validator test passes already, retain it as a regression test and document that the existing evidence validator already enforces the required boundary.

- [ ] **Step 3: Add the minimal Agent prompt instruction**

  Add this explicit rule to the project meeting Agent prompt, adjacent to tool/evidence instructions:

  ```text
  Execution context returned by tools is frozen project baseline. Treat confirmed_report and confirmed_event as context for matching, consistency checks, risk flags, and questions for the owner. They never replace field-level Word evidence and must never be the sole source of a proposed writeback value.
  ```

  Do not add a new model call, new Agent, or new tool.

- [ ] **Step 4: Run the targeted tests to verify they pass**

  Run the command from Step 2. Expected: PASS.

### Task 5: Enforce canonical key-task assignment for newly saved work-report cards

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_cross_project_submission_batch.py`
- Modify: `bowei_ai_dashboard/tests/test_execution_submission_to_work_progress_flow.py`
- Modify: `bowei_ai_dashboard/app/services/cross_project_submission.py`
- Modify: `bowei_ai_dashboard/app/routers/updates.py`

- [ ] **Step 1: Write failing tests for task-card validation**

  In the batch-service tests, verify a card without `matched_subtask_id`, a card whose subtask belongs to another parent task, and a card whose task belongs to a different project each raise HTTP 422. Assert no `UpdateSubmissionBatch` or child `UpdateSubmission` row is committed.

  In direct-update route tests, submit `human_result={"task_reports": [{"parent_task_id": 10}]}` and assert `create_update()` raises `HTTPException` with `status_code == 422` and detail `"任务卡 1 尚未完成归属"`. Submit a card assigned to a different project and assert the same 422 behavior; submit one valid same-project card and assert a pending row is created containing canonical `project_id`, `parent_task_id`, `matched_subtask_id`, `matched_subtask_title`, and `match_status="matched"`.

- [ ] **Step 2: Run the focused validation tests to verify they fail**

  Run:

  ```powershell
  cd bowei_ai_dashboard
  .\.venv\Scripts\python.exe -m pytest tests/test_cross_project_submission_batch.py tests/test_execution_submission_to_work_progress_flow.py -q
  ```

  Expected: direct-update tests fail because `/api/updates` currently accepts a result without canonical task cards.

- [ ] **Step 3: Extract one reusable canonicalization helper**

  In `cross_project_submission.py`, replace private single-use card processing with an exported helper:

  ```python
  def canonicalize_task_report_cards(
      cards: object, *, db: Session, required_project_id: int | None = None,
  ) -> list[dict]:
      if not isinstance(cards, list) or not cards:
          raise HTTPException(422, "至少需要一张已确认归属的任务卡")
      canonical: list[dict] = []
      for index, raw in enumerate(cards):
          if not isinstance(raw, dict):
              raise HTTPException(422, f"任务卡 {index + 1} 格式无效")
          project_id, parent, subtask = _card_project(raw, index, db)
          if required_project_id is not None and project_id != required_project_id:
              raise HTTPException(422, f"任务卡 {index + 1} 不属于当前项目")
          card = dict(raw)
          card.update({
              "project_id": project_id,
              "parent_task_id": parent.id,
              "parent_key_task": parent.key_task,
              "matched_subtask_id": subtask.id,
              "matched_subtask_title": subtask.title,
              "match_status": "matched",
          })
          canonical.append(card)
      return canonical
  ```

  Continue applying project access/archived checks in `create_submission_batch()` after canonicalization, preserving its project-grouping behavior.

- [ ] **Step 4: Require canonical cards in the direct route**

  Import `canonicalize_task_report_cards` into `updates.py`. After resolving `project_id` and before the duplicate check, canonicalize `human_result["task_reports"]` with `required_project_id=project_id`, then write the returned list back into both `human_result` and the stored AI/human result representation. Direct `/api/updates` now accepts exactly one project, while `/api/updates/batch` remains the supported multi-project entry point.

  Preserve existing permission, archive, notification, duplicate, and confirmation workflow behavior.

- [ ] **Step 5: Run the focused validation tests to verify they pass**

  Run the command from Step 2. Expected: PASS.

### Task 6: Run cross-layer regression tests and inspect the resulting snapshot

**Files:**
- Test: `bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py`
- Test: `bowei_ai_dashboard/tests/test_project_meeting_agent_tools.py`
- Test: `bowei_ai_dashboard/tests/test_project_meeting_agent.py`
- Test: `bowei_ai_dashboard/tests/test_cross_project_submission_batch.py`
- Test: `bowei_ai_dashboard/tests/test_execution_submission_to_work_progress_flow.py`

- [ ] **Step 1: Run the complete targeted regression suite**

  Run:

  ```powershell
  cd bowei_ai_dashboard
  .\.venv\Scripts\python.exe -m pytest \
    tests/test_project_meeting_minutes_service.py \
    tests/test_project_meeting_agent_tools.py \
    tests/test_project_meeting_agent.py \
    tests/test_cross_project_submission_batch.py \
    tests/test_execution_submission_to_work_progress_flow.py -q
  ```

  Expected: PASS.

- [ ] **Step 2: Perform one isolated snapshot inspection test**

  In a test fixture, mutate the live `UpdateSubmission`, `KeyTaskExecutionEvent`, and `ExecutionSchedule` after calling `build_project_meeting_snapshot()`. Construct `ProjectMeetingAgentTools(snapshot)` and assert the returned `execution_context` still contains the original values. This proves retries and review cannot read through to current database values.

- [ ] **Step 3: Run static integrity checks**

  Run:

  ```powershell
  git diff --check
  cd bowei_ai_dashboard
  .\.venv\Scripts\python.exe -m pytest tests/test_project_meeting_minutes_service.py tests/test_project_meeting_agent_tools.py -q
  ```

  Expected: no whitespace errors and all selected tests pass.

- [ ] **Step 4: Review scope before handoff**

  Confirm the diff contains only the file-map paths, has no Alembic migration, no frontend route change, no review/writeback behavior change, and no modification of historical project data. Do not create a Git commit unless the user explicitly asks for one.

## Requirement-to-task coverage

- Frozen execution facts, current subplans, report cards, events: Tasks 1–3.
- Last published meeting’s actual date / first-meeting project start / Shanghai boundary: Tasks 1–2.
- Confirmed-only and key-task-only report-card invariant: Tasks 2 and 5.
- Read-only Agent access and no prompt overloading: Task 3.
- Word evidence remains mandatory for writeback: Task 4.
- Immutable snapshot retry/review behavior and regression verification: Task 6.
