import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('execution schedule timeline exposes status filters and an accessible create action', () => {
  const source = read('src/components/task-management/ExecutionScheduleTimeline.tsx')
  assert.match(source, /全部.*待开始.*进行中.*已逾期.*已完成/s)
  assert.match(source, /新建执行安排/)
  assert.match(source, /aria-label/)
  assert.match(source, /周计划.*月计划/s)
})
