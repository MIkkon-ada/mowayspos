import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/pages/MeetingPage.tsx', import.meta.url), 'utf8')

test('project meeting list uses a compact project strip and a unified workspace panel', () => {
  assert.match(source, /meeting-list-workspace/)
  assert.match(source, /meeting-project-strip/)
  assert.match(source, /会议记录/)
  assert.match(source, /还没有会议纪要/)
  assert.match(source, /创建第一条会议纪要/)
  assert.match(source, /setShowNewModal\(true\)/)
  assert.doesNotMatch(source, /10 条\/页/)
})
