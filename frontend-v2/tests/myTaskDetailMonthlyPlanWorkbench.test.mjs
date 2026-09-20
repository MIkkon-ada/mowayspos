import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('personal key-task detail uses the shared execution workspace API', () => {
  const detail = read('src/pages/MyTaskDetailPage.tsx')
  assert.match(detail, /KeyTaskExecutionWorkspace/)
  assert.match(detail, /keyTaskId=\{taskId\}/)
  assert.doesNotMatch(detail, /KeyTaskSubtasksWorkspace/)
  assert.doesNotMatch(detail, /getProgress\(/)
})
