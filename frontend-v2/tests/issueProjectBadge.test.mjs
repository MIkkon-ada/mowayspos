import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/pages/IssuesPage.tsx', import.meta.url), 'utf8')

test('issue center homepage highlights every project name in its project table', () => {
  assert.match(source, /issue-home-project-name/)
  assert.match(source, /border-l-4 border-violet-500/)
})
