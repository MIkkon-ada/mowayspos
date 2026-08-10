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
  assert.doesNotMatch(source, /applyInitAnalysisRun/)
  assert.equal((source.match(/ownerSubmitProfile\(/g) ?? []).length, 1)
})

test('AI merge confirmation updates local form state and retains submit validation flow', () => {
  assert.match(source, /const current = currentAiDraft\(draftTasksRef\.current\)/)
  assert.match(source, /buildAiMergePreview\(current, savedAiDraftRef\.current, savedAiDecisionsRef\.current/)
  assert.match(source, /draftTasksRef\.current/)
  assert.doesNotMatch(source, /applyMergedDraftToForm\(aiPreview\.draft\)/)
  assert.match(source, /setDraftTasks\(nextTasks\.length > 0 \? nextTasks : \[cloneEmptyTask\(\)\]\)/)
  assert.match(source, /if \(workProgressDraft\.length === 0\)/)
  assert.match(source, /if \(subtaskCount === 0\)/)
  assert.match(source, /!subtask\.assignee_id/)
  assert.match(source, /setFillLoading\(true\)/)
})
