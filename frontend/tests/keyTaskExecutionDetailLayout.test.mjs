import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('task-management keeps the shared key-task execution workspace after removing the overview mode', () => {
  const detail = read('src/components/task-management/KeyTaskExecutionDetailView.tsx')
  const page = read('src/pages/TaskManagementPage.tsx')
  assert.match(detail, /KeyTaskExecutionWorkspace/)
  assert.match(detail, /keyTaskId=\{subTask\.id\}/)
  assert.match(page, /selectedSubTask \? \(/)
  assert.doesNotMatch(page, /SHOW_EXECUTION_DETAIL|viewMode === ['"]execution['"]|ExecutionProgressView/)
  assert.match(page, /KeyTaskExecutionDetailView/)
})

test('legacy detail composition is no longer the source for execution facts', () => {
  const detail = read('src/components/task-management/KeyTaskExecutionDetailView.tsx')
  assert.doesNotMatch(detail, /KeyTaskSubtasksWorkspace/)
  assert.doesNotMatch(detail, /KeyTaskExecutionTimeline/)
  assert.doesNotMatch(detail, /notes.*match|collaboratorOf/)
})

test('plan table still opens the key-task detail flow from the progress table', () => {
  const page = read('src/pages/TaskManagementPage.tsx')
  const table = read('src/components/task-management/PlanTableViewV2.tsx')
  assert.match(page, /<PlanTableViewV2[\s\S]*?onOpenSubTask=\{openSubDetail\}/)
  assert.match(table, /onOpenSubTask\?\.\(row\.subtask\)/)
})
