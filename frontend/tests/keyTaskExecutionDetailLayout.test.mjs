import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('execution timeline combines key-task reports, achievements, issues, and meeting filter', () => {
  const file = path.join(root, 'src/components/task-management/KeyTaskExecutionTimeline.tsx')
  assert.equal(fs.existsSync(file), true)
  const timeline = fs.readFileSync(file, 'utf8')
  for (const label of ['执行过程', '全部', '工作汇报', '成果', '问题', '会议纪要']) {
    assert.match(timeline, new RegExp(label))
  }
  assert.match(timeline, /related_achievements/)
  assert.match(timeline, /related_issues/)
  assert.match(timeline, /work_reports/)
})

test('execution view retains key-task navigation and detail integration', () => {
  const overview = read('src/components/task-management/ExecutionProgressView.tsx')
  const detail = read('src/components/task-management/KeyTaskExecutionDetailView.tsx')
  const page = read('src/pages/TaskManagementPage.tsx')

  assert.match(overview, /onOpenSubTask/)
  assert.match(overview, /completion_standard/)
  assert.match(detail, /KeyTaskExecutionTimeline/)
  assert.match(page, /ExecutionProgressView/)
  assert.match(page, /KeyTaskExecutionDetailView/)
})

test('execution project overview splits base information and evaluation criteria into equal halves', () => {
  const overview = read('src/components/task-management/ExecutionProgressView.tsx')

  assert.match(overview, /grid-cols-1.*lg:grid-cols-2/)
  assert.match(overview, /expected_outcomes/)
  assert.doesNotMatch(overview, /整体进度/)
})

test('key task detail presents the approved subtask execution page semantics', () => {
  const detail = read('src/components/task-management/KeyTaskExecutionDetailView.tsx')
  const page = read('src/pages/TaskManagementPage.tsx')
  assert.match(detail, /返回工作推进表/)
  for (const label of ['负责人', '协作人', '开始时间', '状态']) {
    assert.match(detail, new RegExp(label))
  }
  assert.match(detail, /KeyTaskSubtasksWorkspace/)
  assert.match(detail, /KeyTaskExecutionTimeline/)
  assert.doesNotMatch(detail, /MonthlyPlanWorkspace|工作汇报记录|过程记录/)
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

test('key task execution page owns base-task editing and the table no longer carries a legacy detail modal', () => {
  const detail = read('src/components/task-management/KeyTaskExecutionDetailView.tsx')
  const page = read('src/pages/TaskManagementPage.tsx')
  const planTable = read('src/components/task-management/PlanTableViewV2.tsx')

  assert.match(detail, /onEditSubTask/)
  assert.match(detail, /编辑关键任务/)
  assert.match(detail, /KeyTaskEditDrawer/)
  for (const label of ['任务名称', '负责人', '协作人', '开始时间', '状态', '完成标准']) {
    assert.match(detail, new RegExp(label))
  }
  assert.match(page, /onEditSubTask=\{handleWorkbenchSubTaskSave\}/)
  assert.doesNotMatch(planTable, /function SubTaskEditModal/)
  assert.doesNotMatch(planTable, /editingSubTaskDetail/)
  assert.equal(fs.existsSync(path.join(root, 'src/components/task-management/PlanTableView.tsx')), false)
})
