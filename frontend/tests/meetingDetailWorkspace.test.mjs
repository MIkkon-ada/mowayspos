import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const page = readFileSync(new URL('../src/pages/MeetingPage.tsx', import.meta.url), 'utf8')
const detail = readFileSync(new URL('../src/features/meeting/MeetingDetailWorkspace.tsx', import.meta.url), 'utf8')
const modal = readFileSync(new URL('../src/features/meeting/NewMeetingModal.tsx', import.meta.url), 'utf8')

test('meeting detail opens in a dedicated workspace with template tabs', () => {
  assert.match(page, /MeetingDetailWorkspace/)
  assert.match(page, /if \(selected\) return \(/)
  assert.match(page, /navigate\(`\/work\/meetings\/detail\/\$\{m\.id\}\?projectId=\$\{effectiveProjectId\}`\)/)
  assert.match(page, /useNavigate/)
  assert.match(detail, /会议列表/)
  assert.match(detail, /会议纪要/)
  assert.match(detail, /本周待办/)
  assert.match(detail, /上周追踪/)
  assert.match(detail, /相关资料/)
  assert.match(detail, /暂无上周追踪数据/)
  assert.match(detail, /暂无相关资料/)
})

test('meeting detail follows the reusable minutes template', () => {
  assert.match(detail, /一、会议议程/)
  assert.match(detail, /二、会议小结与决议/)
  assert.match(detail, /整理人：/)
  assert.match(detail, /会议安排事项/)
  assert.match(detail, /本周进展\/说明/)
  assert.doesNotMatch(detail, /会议内容摘要/)
  assert.doesNotMatch(detail, /行动清单/)
})

test('standard minutes detail keeps the source agenda and both tracker table shapes', () => {
  const source = readFileSync(new URL('../src/features/meeting/MeetingDetailWorkspace.tsx', import.meta.url), 'utf8')

  assert.match(source, /agenda_items_json/)
  assert.match(source, /prior_action_items_json/)
  assert.match(source, /会议安排事项/)
  assert.match(source, /本周进展\/说明/)
  assert.match(source, /meeting\.copied_to/)
})

test('meeting type options use the agreed vocabulary', () => {
  for (const label of ['项目例会', '专题会议', '启动会', '沟通会', '评审会', '复盘会']) {
    assert.match(modal, new RegExp(label))
  }
})
