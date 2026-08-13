# Cross-Project Submission Regression Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore atomic per-project batch submission for `all` and `project` work-report scopes while preserving single submission for `task` scope.

**Architecture:** Keep the existing scope selector and backend contracts. Make `useVoiceSubmission` select `createUpdate` only for `task`, select `createUpdateBatch` for `all/project`, retain one batch idempotency key across failed retries, and keep the existing history/detail handoff through the first created child submission.

**Tech Stack:** React 19, TypeScript, Node test runner, FastAPI, SQLAlchemy, pytest

---

## File Structure

- Modify `frontend/tests/workReportFlowPage.test.mjs`: enforce the scope-to-endpoint contract and idempotency behavior.
- Modify `frontend/src/features/voice-update/useVoiceSubmission.ts`: restore scope-aware submission routing.
- Verify `frontend/src/api/updates.ts`: existing typed `createUpdateBatch` client remains unchanged.
- Verify `bowei_ai_dashboard/app/routers/updates.py`: existing transactional `/api/updates/batch` route remains unchanged.

### Task 1: Add a failing frontend regression contract

**Files:**
- Modify: `frontend/tests/workReportFlowPage.test.mjs:538-559`
- Test: `frontend/tests/workReportFlowPage.test.mjs`

- [ ] **Step 1: Replace the single-endpoint assertion with the intended scope contract**

```js
test('submission routes task scope to one update and broader scopes to an idempotent batch', () => {
  const submission = read(SUBMISSION)
  const api = read('src/api/updates.ts')
  const page = read(PAGE)
  assert.match(api, /createUpdate/)
  assert.match(api, /createUpdateBatch/)
  assert.match(submission, /if\s*\(reportScope === 'task'\)[\s\S]*?createUpdate\(/)
  assert.match(submission, /else\s*\{[\s\S]*?createUpdateBatch\(/)
  assert.match(submission, /batchRequestId\.current\s*\|\|=/)
  assert.match(submission, /client_request_id:\s*batchRequestId\.current/)
  assert.match(submission, /batchRequestId\.current\s*=\s*null/)
  assert.match(submission, /human_result:/)
  assert.match(submission, /buildVoiceUpdateHumanResult/)
  assert.match(submission, /createDrafts/)
  assert.match(page, /reportScope,/)
})
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
node frontend/tests/workReportFlowPage.test.mjs
```

Expected: FAIL in `submission routes task scope to one update and broader scopes to an idempotent batch` because `handleSubmitFinal` contains no `createUpdateBatch(...)` call or `batchRequestId`.

- [ ] **Step 3: Commit the failing regression test**

```powershell
git add frontend/tests/workReportFlowPage.test.mjs
git commit -m "test: expose cross-project submission regression"
```

### Task 2: Restore scope-aware submission routing

**Files:**
- Modify: `frontend/src/features/voice-update/useVoiceSubmission.ts:52-180`
- Test: `frontend/tests/workReportFlowPage.test.mjs`

- [ ] **Step 1: Add a retry-stable batch request id**

Immediately after `const submitLock = useRef(false)`, add:

```ts
const batchRequestId = useRef<string | null>(null)
```

- [ ] **Step 2: Block broader-scope submission until every task card has concrete ownership**

Immediately after `patchedTaskReports` is created, add:

```ts
if (reportScope !== 'task' && patchedTaskReports.some((report) => (
  report.type !== 'progress' || !report.parent_task_id || !report.matched_subtask_id
))) {
  setError('请先确认所有任务卡的项目、重点工作和关键任务归属')
  submitLock.current = false
  return
}
```

- [ ] **Step 3: Route task and broader scopes to their correct APIs**

Replace the unconditional `createUpdate` call with:

```ts
const sourceType = mode === 'voice' ? '语音更新' : '文字更新'
let submissionId: number | null = null
if (reportScope === 'task') {
  const { submission } = await createUpdate({
    project_id: projectId,
    source_type: sourceType,
    transcript_text: content,
    submitter: submitterName,
    human_result: mergedHumanResult,
  })
  submissionId = submission?.id ?? null
} else {
  batchRequestId.current ||= globalThis.crypto?.randomUUID?.()
    ?? `report-${Date.now()}-${Math.random().toString(36).slice(2)}`
  const batchResult = await createUpdateBatch({
    client_request_id: batchRequestId.current,
    source_type: sourceType,
    title: '工作汇报',
    transcript_text: content,
    human_result: mergedHumanResult,
  })
  submissionId = batchResult.submissions[0]?.id ?? null
  batchRequestId.current = null
}
```

Use `submissionId` for `createDrafts({ source_submission_id })` and `setSubmittedSubmissionId(submissionId)`.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run:

```powershell
node frontend/tests/workReportFlowPage.test.mjs
```

Expected: all work-report subtests pass.

- [ ] **Step 5: Build the frontend**

Run:

```powershell
npm --prefix frontend run build
```

Expected: TypeScript and Vite build exit with code 0.

- [ ] **Step 6: Run backend batch regression tests**

Run from `bowei_ai_dashboard`:

```powershell
python -m pytest tests/test_cross_project_submission_batch.py -q
```

Expected: `7 passed`.

- [ ] **Step 7: Commit the implementation**

```powershell
git add frontend/src/features/voice-update/useVoiceSubmission.ts
git commit -m "fix: restore cross-project report batching"
```

### Task 3: Final verification

**Files:**
- Verify only; no expected modifications.

- [ ] **Step 1: Confirm the intended diff and clean formatting**

Run:

```powershell
git diff HEAD~2 --check
git status --short
```

Expected: no whitespace errors and no unintended files.

- [ ] **Step 2: Re-run both focused suites from a clean process**

Run:

```powershell
node frontend/tests/workReportFlowPage.test.mjs
Push-Location bowei_ai_dashboard
python -m pytest tests/test_cross_project_submission_batch.py -q
Pop-Location
```

Expected: all frontend work-report tests pass and backend reports `7 passed`.
