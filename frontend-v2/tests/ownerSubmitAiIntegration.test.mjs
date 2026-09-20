import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const source = fs.readFileSync(path.resolve(here, '../src/features/settings/OwnerSubmitModal.tsx'), 'utf8')

test('OwnerSubmitModal routes AI results through a local preview before the submit API', () => {
  assert.match(source, /OwnerSubmitAiPanel/)
  assert.match(source, /buildAiMergePreview/)
  assert.match(source, /data-testid="owner-submit-ai-preview"/)
  assert.match(source, /confirmAiPreview/)
  assert.match(source, /applyInitAnalysisRun/)
  assert.match(source, /submittedResultRef\.current = result[\s\S]*await applyInitAnalysisRun\(project\.id, auditRunId\)/)
  assert.match(source, /setAiError\(message\)[\s\S]*toast\.error\(message\)/)
  assert.equal((source.match(/ownerSubmitProfile\(/g) ?? []).length, 1)
})

test('AI merge confirmation updates local form state and retains submit validation flow', () => {
  assert.match(source, /const current = currentAiDraft\(draftTasksRef\.current\)/)
  assert.match(source, /buildAiMergePreview\(current, savedAiDraftRef\.current, savedAiDecisionsRef\.current/)
  assert.match(source, /draftTasksRef\.current/)
  assert.doesNotMatch(source, /applyMergedDraftToForm\(aiPreview\.draft\)/)
  assert.match(source, /const normalizedTasks = nextTasks\.length > 0 \? nextTasks : \[cloneEmptyTask\(\)\]/)
  assert.match(source, /setDraftTasks\(normalizedTasks\)/)
  assert.match(source, /if \(workProgressDraft\.length === 0\)/)
  assert.match(source, /if \(subtaskCount === 0\)/)
  assert.match(source, /!subtask\.assignee_id/)
  assert.match(source, /setFillLoading\(true\)/)
})

test('successful business submit records the AI apply audit afterward and exposes recovery', () => {
  assert.match(source, /function handleAiDraft\(draft: ProjectInitAiDraft, decisions: ProjectInitAiDecision\[\], runId: number\)/)
  assert.match(source, /pendingAiRunIdRef\.current = runId/)
  assert.match(source, /savedAiRunIdRef\.current = pendingAiRunIdRef\.current/)
  assert.match(source, /submittedResultRef\.current = result[\s\S]*await applyInitAnalysisRun\(project\.id, auditRunId\)/)
  assert.match(source, /setAiAuditPendingRunId\(auditRunId\)/)
  assert.match(source, /retryAiApplyAudit/)
  assert.match(source, /function cancelAiPreview\(\)[\s\S]*pendingAiRunIdRef\.current = null/)
})
