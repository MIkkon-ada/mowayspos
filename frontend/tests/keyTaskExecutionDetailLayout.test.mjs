import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('execution view retains key-task navigation and detail integration', () => {
  const overview = read('src/components/task-management/ExecutionProgressView.tsx')
  const detail = read('src/components/task-management/KeyTaskExecutionDetailView.tsx')
  const page = read('src/pages/TaskManagementPage.tsx')

  assert.match(overview, /onOpenSubTask/)
  assert.match(overview, /completion_standard/)
  assert.match(detail, /工作汇报记录/)
  assert.match(page, /ExecutionProgressView/)
  assert.match(page, /KeyTaskExecutionDetailView/)
})

test('execution project overview splits base information and evaluation criteria into equal halves', () => {
  const overview = read('src/components/task-management/ExecutionProgressView.tsx')

  assert.match(overview, /grid-cols-1.*lg:grid-cols-2/)
  assert.match(overview, /expected_outcomes/)
  assert.doesNotMatch(overview, /整体进度/)
})
