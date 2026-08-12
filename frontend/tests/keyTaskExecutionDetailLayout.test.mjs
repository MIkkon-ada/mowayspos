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

test('key task detail is a monthly-plan workbench while retaining task context and process records', () => {
  const detail = read('src/components/task-management/KeyTaskExecutionDetailView.tsx')
  const page = read('src/pages/TaskManagementPage.tsx')
  assert.match(detail, /返回工作推进表/)
  assert.match(detail, /直接负责人/)
  assert.match(detail, /MonthlyPlanWorkspace/)
  assert.match(detail, /关键任务概览/)
  assert.match(detail, /工作汇报记录/)
  assert.doesNotMatch(detail, /ExecutionScheduleTimeline/)
  assert.match(page, /projectMembers=\{projectMembersByProject/)
})

test('opening a key task switches from every entry point into execution detail', () => {
  const page = read('src/pages/TaskManagementPage.tsx')
  const focusSubTask = page.match(/function focusSubTask\([\s\S]*?function focusProject/)

  assert.ok(focusSubTask)
  assert.match(focusSubTask[0], /setViewMode\('execution'\)/)
})

test('work progress table opens a key task through the shared execution-workbench entry', () => {
  const page = read('src/pages/TaskManagementPage.tsx')
  const planTable = read('src/components/task-management/PlanTableViewV2.tsx')

  assert.match(page, /<PlanTableViewV2[\s\S]*?onOpenSubTask=\{openSubDetail\}/)
  assert.match(planTable, /onOpenSubTask\?: \(subtask: SubTaskItem\) => void/)
  assert.match(planTable, /onOpenSubTask\?\.\(row\.subtask\)/)
  assert.doesNotMatch(planTable, /setEditingSubTask\(row\.subtask\)/)
})

test('monthly workbench owns base-task editing and the table no longer carries a legacy detail modal', () => {
  const detail = read('src/components/task-management/KeyTaskExecutionDetailView.tsx')
  const page = read('src/pages/TaskManagementPage.tsx')
  const planTable = read('src/components/task-management/PlanTableViewV2.tsx')

  assert.match(detail, /onEditSubTask/)
  assert.match(detail, /编辑关键任务/)
  assert.match(detail, /KeyTaskEditDrawer/)
  for (const label of ['任务名称', '责任人', '协同人', '计划时间', '整体状态', '完成标准']) {
    assert.match(detail, new RegExp(label))
  }
  assert.match(page, /onEditSubTask=\{handleWorkbenchSubTaskSave\}/)
  assert.doesNotMatch(planTable, /function SubTaskEditModal/)
  assert.doesNotMatch(planTable, /editingSubTaskDetail/)
  assert.equal(fs.existsSync(path.join(root, 'src/components/task-management/PlanTableView.tsx')), false)
})
