import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(path, 'utf8')

test('active projects can open kickoff as an execution event', () => {
  const page = read('src/pages/MeetingPage.tsx')
  assert.match(page, /isProjectExecutionAvailable/)
  assert.match(page, /showKickoffWorkspace/)
  assert.match(page, /记录启动会/)
  assert.match(read('src/features/meeting/KickoffAgentWorkspace.tsx'), /提交企业教练审核/)
  assert.doesNotMatch(read('src/features/meeting/KickoffAgentWorkspace.tsx'), /<option value="kickoff">/)
})

test('kickoff workspace supports the complete PM and coach review flow', () => {
  const api = read('src/api/meetings.ts')
  const workspace = read('src/features/meeting/KickoffAgentWorkspace.tsx')

  assert.match(api, /submitKickoffRun/)
  assert.match(api, /reviewKickoffProposal/)
  assert.match(api, /confirmKickoffStart/)
  assert.doesNotMatch(read('src/features/meeting/NewMeetingModal.tsx'), /setMeetingMode\('kickoff'\)/)
  assert.match(workspace, /审核提案/)
  assert.match(workspace, /确认启动会并写回执行基线/)
})
