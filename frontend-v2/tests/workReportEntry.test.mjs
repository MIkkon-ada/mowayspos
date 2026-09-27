import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

test('subtask grouping month is optional', () => {
  const api = read('src/api/monthlyPlans.ts')
  assert.match(api, /plan_month:\s*string\s*\|\s*null/)
})

test('work report entry keeps project and key task ownership', () => {
  const target = new URL('../src/domain/workReportEntry.ts', import.meta.url)
  assert.equal(existsSync(target), true, 'workReportEntry.ts should centralize the existing report deep link')
  const entry = read('src/domain/workReportEntry.ts')
  assert.match(entry, /projectId/)
  assert.match(entry, /subtaskId/)
  assert.match(entry, /entryIntent/)
  assert.doesNotMatch(entry, /monthlyPlanId|planId/)
})

test('work report page interprets entry intent without changing the submission flow', () => {
  const page = read('src/pages/VoiceUpdatePage.tsx')
  const panel = read('src/features/voice-update/VoiceUpdateInputPanel.tsx')

  assert.match(page, /searchParams\.get\('entryIntent'\)/)
  assert.match(page, /<VoiceUpdateInputPanel[\s\S]*?entryIntent=\{entryIntent\}/)
  assert.match(panel, /entryIntent:\s*WorkReportEntryIntent/)
  assert.match(panel, /记录问题/)
  assert.match(panel, /添加成果/)
  assert.match(panel, /提交工作汇报/)
  assert.doesNotMatch(page, /monthlyPlanId|planId/)
})
