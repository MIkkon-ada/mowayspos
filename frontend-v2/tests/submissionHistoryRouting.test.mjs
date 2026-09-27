import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('AI confirmation center contains reviewer queues only', () => {
  const source = read('src/pages/ConfirmPage.tsx')
  assert.doesNotMatch(source, /ConfirmViewMode[^\n]*mine/)
  assert.doesNotMatch(source, /fetchMyUpdates/)
  assert.doesNotMatch(source, /我的提交记录/)
  assert.doesNotMatch(source, /viewMode\s*===\s*['"]mine['"]/)
  for (const view of ["'all'", "'coordinator'", "'ceo'"]) assert.match(source, new RegExp(view))
})

test('confirmation route redirects mine deep links and ordinary members to work-report history', () => {
  const source = read('src/app/routes.tsx')
  assert.match(source, /function ConfirmationCenterRoute/)
  assert.match(source, /searchParams\.get\('view'\) === 'mine'/)
  assert.match(source, /\['owner', 'coordinator', 'project_ceo'\]/)
  assert.match(source, /to={`\/work\/submit\?\${params\.toString\(\)}`}/)
  assert.match(source, /path="confirmations" element={<ConfirmationCenterRoute \/>}/)
})

test('work report history deep link opens and selects the requested submission', () => {
  const source = read('src/pages/VoiceUpdatePage.tsx')
  assert.match(source, /searchParams\.get\('history'\) === '1'/)
  assert.match(source, /requestedSubmissionId/)
  assert.match(source, /setHistoryOpen\(true\)/)
  assert.match(source, /historyState\.handleSelectUpdate\(requestedSubmissionId\)/)
})

test('future submitter notifications target work-report history instead of confirmation mine view', () => {
  const source = fs.readFileSync(path.resolve(root, '../bowei_ai_dashboard/app/routers/confirmations.py'), 'utf8')
  assert.doesNotMatch(source, /\/work\/confirmations\?view=mine/)
  assert.match(source, /\/work\/submit\?history=1/)
})
