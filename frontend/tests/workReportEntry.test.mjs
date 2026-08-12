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
