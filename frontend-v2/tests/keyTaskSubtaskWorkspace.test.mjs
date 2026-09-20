import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

const file = (path) => new URL(`../${path}`, import.meta.url)
const read = (path) => readFileSync(file(path), 'utf8')

test('key task workspace presents optional month-grouped subtasks', () => {
  const path = 'src/components/task-management/KeyTaskSubtasksWorkspace.tsx'
  assert.equal(existsSync(file(path)), true)
  const workspace = read(path)
  assert.match(workspace, />子任务</)
  assert.match(workspace, /全部子任务/)
  assert.match(workspace, /新增子任务/)
  assert.match(workspace, /未分月/)
  assert.match(workspace, /plan_month === selectedGroup/)
})

test('subtask detail keeps owner and collaborators compact until editing', () => {
  const path = 'src/components/task-management/KeyTaskSubtaskDrawer.tsx'
  assert.equal(existsSync(file(path)), true)
  const drawer = read(path)
  assert.match(drawer, /子任务详情/)
  assert.match(drawer, /负责人[\s\S]*协作人/)
  assert.match(drawer, /grid-cols-2/)
  assert.match(drawer, /CollaboratorMultiSelect/)
  assert.doesNotMatch(drawer, /<select multiple/)
})

test('subtask form allows no month grouping', () => {
  const drawer = read('src/components/task-management/KeyTaskSubtaskDrawer.tsx')
  assert.match(drawer, /不按月份/)
  assert.match(drawer, /plan_month[\s\S]*null/)
})

test('subtask selectors deduplicate repeated project members', () => {
  const drawer = read('src/components/task-management/KeyTaskSubtaskDrawer.tsx')
  assert.match(drawer, /selectableMembers/)
  assert.match(drawer, /findIndex\(\(candidate\) => candidate\.person_id === member\.person_id\)/)
  assert.doesNotMatch(drawer, /\{members\.map\(\(member\)/)
})

test('collaborator field uses a compact checkbox dropdown while preserving collaborator ids', () => {
  const drawer = read('src/components/task-management/KeyTaskSubtaskDrawer.tsx')
  assert.match(drawer, /请选择协作人/)
  assert.match(drawer, /selectedNames\.slice\(0, 2\)/)
  assert.match(drawer, /absolute left-0 right-0 top-full/)
  assert.match(drawer, /type="checkbox"/)
  assert.match(drawer, /document\.addEventListener\('mousedown'/)
  assert.match(drawer, /collaborator_ids.*filter\(\(id\) => id !== assigneeId\)/s)
  assert.match(drawer, /patch\('collaborator_ids'/)
})
