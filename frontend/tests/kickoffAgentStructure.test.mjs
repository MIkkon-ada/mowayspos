import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(path, 'utf8')

test('meeting page routes pending kickoff projects to the kickoff workspace', () => {
  assert.match(read('src/pages/MeetingPage.tsx'), /pending_kickoff/)
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
  assert.match(workspace, /确认启动项目/)
})
