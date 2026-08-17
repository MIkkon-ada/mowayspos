import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const page = readFileSync(new URL('../src/pages/MeetingPage.tsx', import.meta.url), 'utf8')
const editor = readFileSync(new URL('../src/features/meeting/NewMeetingModal.tsx', import.meta.url), 'utf8')

test('meeting creation replaces the meeting content with a page-level workbench', () => {
  assert.match(page, /if \(meetingEditor\) return \(/)
  assert.match(page, /<NewMeetingModal[\s\S]{0,80}projectId=\{effectiveProjectId\}/)
  assert.doesNotMatch(page, /showNewModal && effectiveProjectId && !pending_kickoff && <NewMeetingModal/)
  assert.doesNotMatch(page, /editingItem && effectiveProjectId && <NewMeetingModal/)
})

test('meeting workbench uses the app content area instead of a viewport overlay', () => {
  assert.match(editor, /meeting-workbench-shell flex min-h-0 flex-1 flex-col overflow-hidden/)
  assert.match(editor, /meeting-workbench-main min-h-0 flex-1 overflow-x-hidden overflow-y-auto/)
  assert.doesNotMatch(editor, /fixed inset-0/)
  assert.doesNotMatch(editor, /z-50/)
})
