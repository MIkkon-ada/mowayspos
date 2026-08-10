import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(here, '../src/features/settings/OwnerSubmitModal.tsx')
const source = fs.readFileSync(sourcePath, 'utf8')

test('assignee picker renders outside the table overflow container', () => {
  assert.match(source, /from ['"]react-dom['"]/) 
  assert.match(source, /createPortal\(/)
  assert.match(source, /document\.body/)
})
