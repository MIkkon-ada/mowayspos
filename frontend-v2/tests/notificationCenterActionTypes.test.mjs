import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const source = fs.readFileSync(path.join(root, 'src/pages/NotificationCenterPage.tsx'), 'utf8')

test('project initiation notifications are treated as actionable', () => {
  assert.match(source, /'project_owner_notify'/)
  assert.match(source, /'project_returned'/)
})
