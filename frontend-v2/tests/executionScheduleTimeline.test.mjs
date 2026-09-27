import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('key task subtasks replace the legacy monthly-plan presentation', () => {
  const workspace = read('src/components/task-management/KeyTaskSubtasksWorkspace.tsx')
  const drawer = read('src/components/task-management/KeyTaskSubtaskDrawer.tsx')
  assert.match(workspace, /全部子任务/)
  assert.match(workspace, /sortMonthPlans/)
  assert.match(drawer, /预期产出/)
  assert.match(drawer, /负责人/)
  assert.match(drawer, /实际产出/)
  assert.doesNotMatch(drawer, /created_by|updated_by|创建人|最后修改人/)
  assert.equal(fs.existsSync(path.join(root, 'src/components/task-management/MonthlyPlanWorkspace.tsx')), false)
  assert.equal(fs.existsSync(path.join(root, 'src/components/task-management/MonthlyPlanDrawer.tsx')), false)
})
