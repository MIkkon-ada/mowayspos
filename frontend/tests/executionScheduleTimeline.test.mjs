import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('monthly plan workspace defaults to the current month and exposes monthly-plan actions', () => {
  const source = read('src/components/task-management/MonthlyPlanWorkspace.tsx')
  assert.match(source, /currentMonthKey/)
  assert.match(source, /monthTabs/)
  assert.match(source, /sortMonthPlans/)
  assert.match(source, /新增月计划/)
  assert.match(source, /已延期.*进行中.*暂缓.*未开始.*已完成/s)
  assert.match(source, /MonthlyPlanDrawer/)
})

test('monthly plan drawer only presents business fields, never audit fields', () => {
  const source = read('src/components/task-management/MonthlyPlanDrawer.tsx')
  assert.match(source, /预期产出/)
  assert.match(source, /执行负责人/)
  assert.match(source, /实际产出/)
  assert.doesNotMatch(source, /created_by|updated_by|创建人|最后修改人/)
})
