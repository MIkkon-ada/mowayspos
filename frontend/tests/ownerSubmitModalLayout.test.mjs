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

test('helper picker keeps multi-select behavior while using the assignee picker pattern', () => {
  assert.match(source, /function HelperPicker\(/)
  assert.match(source, /请选择协助人/)
  assert.match(source, /helperIds\.includes\(/)
  assert.match(source, /onChange=\{\(personId\) => toggleSubTaskHelper\(/)
})

test('picker scrolling does not close the option list', () => {
  assert.match(source, /menuRef/)
  assert.match(source, /menuRef\.current\?\.contains\(event\.target as Node\)/)
})

test('notes column has a bounded share of the task table', () => {
  assert.match(source, /table-fixed/)
  assert.match(source, /w-\[180px\][^\n]*备注 \/ 标准/)
})
