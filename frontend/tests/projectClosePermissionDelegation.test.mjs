import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/domain/projectCloseUi.ts', import.meta.url), 'utf8')

test('project close UI delegates permission decisions to the shared project policy', () => {
  assert.match(source, /import\s*\{\s*canProjectAction\s*\}\s*from\s*['"]\.\/permissions['"]/)
  assert.doesNotMatch(source, /type CloseProjectAction\s*=/)
  assert.doesNotMatch(source, /function canProjectAction\s*\(/)
})
