import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const confirmPage = readFileSync(new URL('../src/pages/ConfirmPage.tsx', import.meta.url), 'utf8')
const confirmationApi = readFileSync(new URL('../src/api/confirmations.ts', import.meta.url), 'utf8')
const sidebar = readFileSync(new URL('../src/components/Sidebar.tsx', import.meta.url), 'utf8')

test('confirmation scope changes abort the active pending-list request', () => {
  assert.match(confirmPage, /function loadPendingItems\(/)
  assert.match(confirmPage, /getPending\(projectId, tab, \{ \.\.\.options, signal: controller\.signal \}\)/)
  assert.equal((confirmPage.match(/\bgetPending\(/g) ?? []).length, 1)
  assert.match(confirmPage, /pendingLoadController\.current\?\.abort\(\)/)
})

test('successful confirmation actions refresh the sidebar todo badge immediately', () => {
  assert.match(confirmationApi, /CONFIRMATION_COUNTS_INVALIDATED_EVENT/)
  assert.match(confirmationApi, /function postConfirmationAction/)
  assert.ok((confirmationApi.match(/return postConfirmationAction/g) ?? []).length >= 10)
  assert.match(sidebar, /addEventListener\(CONFIRMATION_COUNTS_INVALIDATED_EVENT, poll\)/)
  assert.match(sidebar, /removeEventListener\(CONFIRMATION_COUNTS_INVALIDATED_EVENT, poll\)/)
})

test('confirmation badges are cleared and refetched when the signed-in identity changes', () => {
  assert.match(sidebar, /setConfirmBadge\(0\)/)
  assert.match(sidebar, /currentUser\?\.account_id/)
  assert.match(sidebar, /currentUser\?\.person_id/)
  assert.match(sidebar, /if \(cancelled\) return[\s\S]*setConfirmBadge/)
})
