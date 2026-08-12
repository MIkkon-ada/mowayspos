import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const modal = readFileSync(new URL('../src/features/meeting/PushToTasksModal.tsx', import.meta.url), 'utf8')

test('push modal uses confirmed action items instead of speaker labels', () => {
  assert.match(modal, /taskListJson/)
  assert.match(modal, /推送待办到工作推进/)
  assert.match(modal, /fetchTasks/)
  assert.doesNotMatch(modal, /speakerMap/)
  assert.doesNotMatch(modal, /generateTaskCards/)
})

test('push modal lets every selected action choose its workstream target', () => {
  assert.match(modal, /新建重点工作/)
  assert.match(modal, /\/api\/tasks\/\$\{(?:item|selected)\.targetTaskId\}\/subtasks/)
  assert.match(modal, /无待办事项可推送/)
})
