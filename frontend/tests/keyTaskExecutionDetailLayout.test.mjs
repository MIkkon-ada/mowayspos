import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('task-management keeps the shared key-task execution workspace behind its temporary entry switch', () => {
  const detail = read('src/components/task-management/KeyTaskExecutionDetailView.tsx')
  const page = read('src/pages/TaskManagementPage.tsx')
  assert.match(detail, /KeyTaskExecutionWorkspace/)
  assert.match(detail, /keyTaskId=\{subTask\.id\}/)
  assert.match(page, /SHOW_EXECUTION_DETAIL = true/)
  assert.match(page, /viewMode === 'execution' && selectedSubTask/)
  assert.match(page, /KeyTaskExecutionDetailView/)
})

test('execution progress keeps the existing table entry but has no fake aggregate percentage', () => {
  const overview = read('src/components/task-management/ExecutionProgressView.tsx')
  assert.match(overview, /onOpenSubTask/)
  assert.match(overview, /completion_standard/)
  assert.doesNotMatch(overview, /整体进度/)
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
