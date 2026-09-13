# Project Init AI Analysis Resilience Implementation Plan

> Status: Implemented on the delivery baseline; the original task checkboxes are retained as the execution record.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give project-init analysis a 200-second primary-model budget, short fallback budgets, structured-Excel fast paths, strict JSON requests, sanitized diagnostics, and fewer cross-batch model calls.

**Architecture:** Add a fallback timeout to the capability policy and choose a timeout by candidate role in `AIService`. Keep raw model output transient: classify it into a safe code, persist only invocation metadata, and expose that metadata with an analysis run. Before text analysis, non-vision Excel-only uploads attempt the existing deterministic extractor; final AI merging is conditional on title conflicts across batches.

**Tech Stack:** Python, FastAPI, SQLAlchemy/Alembic, Pydantic, pytest, React, TypeScript, Vitest.

---

### Task 1: Add primary and fallback timeout policy support

**Files:**

- Modify: `bowei_ai_dashboard/app/models.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Modify: `bowei_ai_dashboard/app/ai/repository.py`
- Modify: `bowei_ai_dashboard/app/routers/ai_config.py`
- Modify: `bowei_ai_dashboard/app/ai/service.py`
- Create: `bowei_ai_dashboard/migrations/versions/l3m4n5o6p7q_add_ai_fallback_timeout.py`
- Test: `bowei_ai_dashboard/tests/test_ai_service.py`, `bowei_ai_dashboard/tests/test_ai_config_models.py`, `bowei_ai_dashboard/tests/test_ai_config_repository.py`

- [ ] **Step 1: Write the failing service test.**

```python
def test_project_init_uses_long_primary_timeout_and_short_fallback(db, configured_chat_policy, fake_adapters):
    primary, fallback = configured_chat_policy
    AIConfigurationRepository(db, cipher_key=TEST_FERNET_KEY).save_policy(
        Capability.PROJECT_INIT_ANALYSIS,
        primary_model_id=primary.id,
        fallback_model_ids=[fallback.id],
        timeout_seconds=200,
        fallback_timeout_seconds=25,
        max_attempts=2,
        enabled=True,
    )
    fake_adapters.chat_errors[primary.id] = AIUpstreamError("AI_UPSTREAM_TIMEOUT", retryable=True)
    fake_adapters.chat_results[fallback.id] = '{"tasks":[]}'
    AIService(db, adapters=fake_adapters, cipher_key=TEST_FERNET_KEY).invoke_chat(Capability.PROJECT_INIT_ANALYSIS, "prompt")
    assert fake_adapters.chat_timeouts == [200, 25]
```

- [ ] **Step 2: Run it to verify it fails.**

Run: `python -m pytest tests/test_ai_service.py::test_project_init_uses_long_primary_timeout_and_short_fallback -q` from `bowei_ai_dashboard`.

Expected: failure because `fallback_timeout_seconds` is not yet accepted.

- [ ] **Step 3: Implement the policy field, migration, and candidate timeout selection.**

Add a non-null `fallback_timeout_seconds` column with default 25; expose and validate it in policy schemas, repository methods, API payloads, and admin configuration. In the migration, backfill 25 and update only `project.init.analysis.timeout_seconds` to 200. In `AIService._invoke_candidates`, supply `policy.timeout_seconds` to the first candidate and `policy.fallback_timeout_seconds` to all subsequent candidates; preserve the task-plan no-client-timeout exception.

- [ ] **Step 4: Run the focused tests.**

Run: `python -m pytest tests/test_ai_service.py tests/test_ai_config_models.py tests/test_ai_config_repository.py -q` from `bowei_ai_dashboard`.

Expected: exit code 0.

- [ ] **Step 5: Commit this task.**

Run: `git add bowei_ai_dashboard/app/models.py bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/app/ai/repository.py bowei_ai_dashboard/app/routers/ai_config.py bowei_ai_dashboard/app/ai/service.py bowei_ai_dashboard/migrations/versions/l3m4n5o6p7q_add_ai_fallback_timeout.py bowei_ai_dashboard/tests/test_ai_service.py bowei_ai_dashboard/tests/test_ai_config_models.py bowei_ai_dashboard/tests/test_ai_config_repository.py && git commit -m "feat: tune project init AI fallback timeouts"`.

### Task 2: Force JSON and show sanitized model diagnostics

**Files:**

- Modify: `bowei_ai_dashboard/app/ai/adapters.py`
- Modify: `bowei_ai_dashboard/app/ai/service.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_ai_agent.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_analysis.py`
- Modify: `frontend/src/features/settings/OwnerSubmitAiPanel.tsx`
- Test: `bowei_ai_dashboard/tests/test_ai_adapters.py`, `bowei_ai_dashboard/tests/test_project_init_ai_agent.py`, `bowei_ai_dashboard/tests/test_project_init_analysis.py`, `frontend/src/features/settings/OwnerSubmitAiPanel.retry.test.tsx`

- [ ] **Step 1: Write failing validator and UI tests.**

```python
def test_raw_draft_validator_returns_a_sanitized_json_category():
    assert classify_raw_draft_response("not json") == "json_missing_or_multiple"
    assert classify_raw_draft_response('{"tasks": [}') == "json_malformed"
```

```tsx
it('shows sanitized attempt failures without raw model content', () => {
  render(<ModelUsageSummary run={runWithFailedAttempts} />)
  expect(screen.getByText(/返回格式无效/)).toBeTruthy()
  expect(screen.queryByText(/secret source text/)).toBeNull()
})
```

- [ ] **Step 2: Run the new tests and verify they fail.**

Run: `python -m pytest tests/test_project_init_ai_agent.py -k raw_draft_validator -q` from `bowei_ai_dashboard`, then `npm run test:unit -- OwnerSubmitAiPanel.retry.test.tsx` from `frontend`.

Expected: failures for missing classifier and diagnostics UI.

- [ ] **Step 3: Implement JSON mode and safe classification.**

Add optional `response_format` to the chat adapter protocol and provider request. Add `force_json_object=False` to `AIService.invoke_chat`; project-init extraction, repair, and final-merge calls set it to true. Extract `classify_raw_draft_response(raw) -> str | None` that returns only `json_missing_or_multiple`, `json_malformed`, or `schema_invalid`; it must never return the model text. Have the validation callback return this code, and make `AIService` log it as a retryable invocation error.

- [ ] **Step 4: Expose attempt summaries.**

Build `result_metadata["model_attempts"]` from existing `AIInvocationLog` rows, including model identity, status, duration, error code, and fallback flag. Update `ModelUsageSummary` to display localized failure labels for timeout and JSON/schema codes. Do not add raw responses to models, metadata, or UI.

- [ ] **Step 5: Run focused tests.**

Run: `python -m pytest tests/test_ai_adapters.py tests/test_project_init_ai_agent.py tests/test_project_init_analysis.py -q` from `bowei_ai_dashboard`, then `npm run test:unit -- OwnerSubmitAiPanel.retry.test.tsx` from `frontend`.

Expected: exit code 0.

- [ ] **Step 6: Commit this task.**

Run: `git add bowei_ai_dashboard/app/ai/adapters.py bowei_ai_dashboard/app/ai/service.py bowei_ai_dashboard/app/services/project_init_ai_agent.py bowei_ai_dashboard/app/services/project_init_analysis.py bowei_ai_dashboard/tests/test_ai_adapters.py bowei_ai_dashboard/tests/test_project_init_ai_agent.py bowei_ai_dashboard/tests/test_project_init_analysis.py frontend/src/features/settings/OwnerSubmitAiPanel.tsx frontend/src/features/settings/OwnerSubmitAiPanel.retry.test.tsx && git commit -m "feat: diagnose project init AI response failures"`.

### Task 3: Use deterministic extraction before the text model for ordinary Excel

**Files:**

- Modify: `bowei_ai_dashboard/app/services/project_init_ai_agent.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_analysis.py`
- Test: `bowei_ai_dashboard/tests/test_project_init_ai_agent.py`, `bowei_ai_dashboard/tests/test_project_init_analysis.py`

- [ ] **Step 1: Write a failing worker test.**

```python
def test_worker_uses_structured_excel_draft_before_contacting_a_chat_model(monkeypatch, tmp_path):
    # Build one regular work-plan workbook and make the AI route raise if called.
    service.process_analysis_run(run_id)
    stored = db.get(models.ProjectInitAnalysisRun, run_id)
    assert stored.model_name == "structured-spreadsheet-fallback"
    assert stored.status == "completed"
```

- [ ] **Step 2: Run it to verify it fails.**

Run: `python -m pytest tests/test_project_init_analysis.py::test_worker_uses_structured_excel_draft_before_contacting_a_chat_model -q` from `bowei_ai_dashboard`.

Expected: failure because semantic Excel currently calls the text-model route.

- [ ] **Step 3: Implement the Excel fast path.**

Extract a public `generate_structured_spreadsheet_draft(chunks, people, existing_tasks)` from the existing deterministic fallback. In the worker, call it after parsing only when every chunk comes from `.xls` or `.xlsx` worksheet ranges and `vision_sources` is empty. Use the result when it contains tasks; otherwise retain the existing vision and text-model path.

- [ ] **Step 4: Add and run the complex-Excel preservation test.**

Test that a high-risk workbook profile with `vision_sources` never invokes the deterministic fast path. Run: `python -m pytest tests/test_project_init_ai_agent.py tests/test_project_init_analysis.py -q` from `bowei_ai_dashboard`.

Expected: exit code 0.

- [ ] **Step 5: Commit this task.**

Run: `git add bowei_ai_dashboard/app/services/project_init_ai_agent.py bowei_ai_dashboard/app/services/project_init_analysis.py bowei_ai_dashboard/tests/test_project_init_ai_agent.py bowei_ai_dashboard/tests/test_project_init_analysis.py && git commit -m "perf: bypass AI for structured project init workbooks"`.

### Task 4: Skip final model merge when batches do not conflict

**Files:**

- Modify: `bowei_ai_dashboard/app/services/project_init_ai_agent.py`
- Test: `bowei_ai_dashboard/tests/test_project_init_ai_agent.py`

- [ ] **Step 1: Write failing no-conflict and conflict tests.**

```python
def test_multiple_batches_without_similar_titles_skip_final_llm_merge():
    calls = []
    first = chunk("first" + "x" * (MAX_BATCH_CHARS - 5), location="lines 1-2")
    second = chunk("second" + "y" * (MAX_BATCH_CHARS - 6), location="lines 1-2")
    def llm(prompt, _provider):
        calls.append(prompt)
        title = "调研" if "first" in prompt else "培训"
        return json.dumps({"tasks": [raw_task(title=title)]}, ensure_ascii=False)
    generate_project_init_draft([first, second], [], [], llm_call=llm)
    assert len(calls) == 2

def test_multiple_batches_with_similar_titles_use_final_llm_merge():
    calls = []
    first = chunk("first" + "x" * (MAX_BATCH_CHARS - 5), location="lines 1-2")
    second = chunk("second" + "y" * (MAX_BATCH_CHARS - 6), location="lines 1-2")
    def llm(prompt, _provider):
        calls.append(prompt)
        title = "需求调研" if "first" in prompt else "调研需求"
        return json.dumps({"tasks": [raw_task(title=title)]}, ensure_ascii=False)
    generate_project_init_draft([first, second], [], [], llm_call=llm)
    assert len(calls) == 3
```

- [ ] **Step 2: Run them to verify the no-conflict test fails.**

Run: `python -m pytest tests/test_project_init_ai_agent.py -k "multiple_batches and final_llm_merge" -q` from `bowei_ai_dashboard`.

Expected: no-conflict observes three calls because final merge is unconditional.

- [ ] **Step 3: Implement deterministic conflict detection.**

Add `has_cross_batch_task_conflict(batch_tasks)`. Normalize titles by trimming, case-folding, and removing punctuation/whitespace; compare only tasks from separate batches, treating exact equality or `SequenceMatcher` similarity of at least 0.88 as a conflict. Call the final merge model only when this helper returns true; keep local task/evidence merging unchanged.

- [ ] **Step 4: Run the agent suite.**

Run: `python -m pytest tests/test_project_init_ai_agent.py -q` from `bowei_ai_dashboard`.

Expected: exit code 0.

- [ ] **Step 5: Commit this task.**

Run: `git add bowei_ai_dashboard/app/services/project_init_ai_agent.py bowei_ai_dashboard/tests/test_project_init_ai_agent.py && git commit -m "perf: skip unnecessary project init AI merges"`.

### Task 5: Verify the completed change

**Files:**

- Verify: backend AI service, adapter, configuration, project-init agent, and analysis tests
- Verify: `frontend/src/features/settings/OwnerSubmitAiPanel.retry.test.tsx`

- [ ] **Step 1: Run the full affected backend suite.**

Run: `python -m pytest tests/test_ai_service.py tests/test_ai_adapters.py tests/test_ai_config_models.py tests/test_ai_config_repository.py tests/test_project_init_ai_agent.py tests/test_project_init_analysis.py -q` from `bowei_ai_dashboard`.

Expected: exit code 0 with no failures.

- [ ] **Step 2: Run frontend verification.**

Run: `npm run test:unit -- OwnerSubmitAiPanel.retry.test.tsx && npm run build` from `frontend`.

Expected: Vitest and TypeScript/Vite both exit 0.

- [ ] **Step 3: Inspect repository state.**

Run: `git diff --check HEAD~4..HEAD && git status --short` from the repository root.

Expected: no whitespace errors; leave the pre-existing owner-submit label edits and untracked runtime files untouched.
