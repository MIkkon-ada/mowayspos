import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const modal = readFileSync(new URL('../src/features/meeting/NewMeetingModal.tsx', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/api/meetings.ts', import.meta.url), 'utf8')
const formats = readFileSync(new URL('../src/config/aiDocumentFormats.ts', import.meta.url), 'utf8')

test('new project meeting uses the shared meeting document format contract', () => {
  assert.match(modal, /acceptedDocumentTypes\('meeting'\)/)
  assert.match(formats, /meeting:\s*\['\.docx', '\.txt', '\.xlsx'\]/)
  assert.doesNotMatch(formats, /meeting:[^\r\n]*\.pdf/)
})

test('new project meeting creates and polls an Agent document run', () => {
  assert.match(modal, /createProjectMeetingDocumentRun/)
  assert.match(modal, /pollProjectMeetingDocumentRun/)
  assert.match(modal, /fetchProjectMeetingDocumentRun/)
  assert.match(modal, /status\.error_code/)
})

test('document run API has a status fetch and bounded polling helper', () => {
  assert.match(api, /fetchProjectMeetingDocumentRunStatus/)
  assert.match(api, /pollProjectMeetingDocumentRun/)
  assert.match(api, /document-runs\/\$\{runId\}\/status/)
  assert.match(api, /maxAttempts/)
})
