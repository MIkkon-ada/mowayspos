import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const page = readFileSync(new URL('../src/pages/MeetingPage.tsx', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/api/meetings.ts', import.meta.url), 'utf8')

test('meeting page exposes immutable revision history beside the current minutes', () => {
  assert.ok(api.includes('fetchMeetingRevisions'))
  assert.ok(page.includes('fetchMeetingRevisions'))
  assert.ok(page.includes('version_no'))
  assert.ok(page.includes('is_legacy_snapshot'))
  assert.ok(page.includes('selectedRevision'))
})

test('meeting history keeps the original transcript visible for source tracing', () => {
  assert.ok(page.includes('selectedRevision.transcript_text'))
  assert.ok(page.includes('selected.transcript_text'))
  assert.ok(page.includes('只读'))
})
