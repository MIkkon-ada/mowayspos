import assert from 'node:assert/strict'
import fs from 'node:fs'

const api = fs.readFileSync('src/api/meetings.ts', 'utf8')
const review = fs.readFileSync('src/features/meeting/ProjectMeetingReviewWorkspace.tsx', 'utf8')
const page = fs.readFileSync('src/pages/MeetingPage.tsx', 'utf8')

assert.match(api, /type ProjectMeetingProposalLineage/)
assert.match(api, /field_sources/)
assert.match(api, /owner_edit_history/)
assert.match(api, /execution_status: 'pending' \| 'executed' \| 'conflict'/)
assert.match(review, /<details/)
assert.match(review, /会议事实/)
assert.match(review, /项目匹配/)
assert.match(review, /项目基线/)
assert.match(review, /AI 判断/)
assert.match(review, /建议修改/)
assert.match(review, /change\.executionStatus === 'conflict'/)
assert.match(page, /lineage: change\.lineage/)
assert.match(page, /executionStatus: change\.execution_status/)

console.log('project meeting lineage trace structure verified')
