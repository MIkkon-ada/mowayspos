import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8')

test('project meeting review workspace exposes the meeting review contract', () => {
  const relativePath = 'src/features/meeting/ProjectMeetingReviewWorkspace.tsx'
  const componentPath = path.join(root, relativePath)
  assert.equal(fs.existsSync(componentPath), true, 'project meeting review workspace must exist')

  const source = read(relativePath)
  assert.match(source, /export (type|interface) ProjectMeetingReviewWorkspaceProps/)
  assert.match(source, /projectContext/)
  assert.match(source, /projectName|projectCode/)
  assert.match(source, /meetingDraft/)
  assert.match(source, /项目会议纪要审核工作台/)
  assert.match(source, /负责人审核/)
})

test('workspace renders evidence and selectable execution-schedule changes', () => {
  const source = read('src/features/meeting/ProjectMeetingReviewWorkspace.tsx')
  assert.match(source, /ScheduleChange|scheduleChanges/)
  assert.match(source, /执行安排变更建议/)
  assert.match(source, /查看原文依据/)
  assert.match(source, /meetingInfoEvidence/)
  assert.match(source, /summaryEvidence/)
  assert.match(source, /openQuestions/)
  assert.match(source, /needsConfirmation/)
  assert.match(source, /parentSubtaskId/)
  assert.match(source, /useState<Set<number>>/)
  assert.match(source, /selectedScheduleChangeIds\.has\(/)
  assert.match(source, /type="checkbox"/)
  assert.match(source, /onApplyChanges/)
})

test('workspace requires a return reason and separates publishing from writeback', () => {
  const source = read('src/features/meeting/ProjectMeetingReviewWorkspace.tsx')
  assert.match(source, /发布会议纪要/)
  assert.match(source, /回填已选/)
  assert.doesNotMatch(source, /项目负责人批准/)
  assert.match(source, /退回原因/)
  assert.match(source, /onReturn/)
  assert.match(source, /returnReason\.trim\(\)/)
  assert.match(source, /下载会议纪要/)
  assert.match(source, /onDownload/)
  assert.match(source, /value=\{returnReason\}/)
})

test('Agent run API exposes polling, audit and proposal-parent fields', () => {
  const source = read('src/api/meetings.ts')
  assert.match(source, /fetchProjectMeetingDocumentRunStatus/)
  assert.match(source, /pollProjectMeetingDocumentRun/)
  for (const field of ['stage', 'step_count', 'error_code', 'tool_trace', 'audit', 'open_questions', 'parent_subtask_id']) {
    assert.match(source, new RegExp(field))
  }
})

test('review page persists owner edits before the owner approves selected proposals', () => {
  const source = read('src/pages/MeetingPage.tsx')
  assert.match(source, /updateMeeting/)
  assert.match(source, /onSaveDraft/)
  assert.match(source, /proposal_ids: proposalIds/)
  assert.match(source, /needs_confirmation|needsConfirmation/)
})

test('document-only meeting review has no realtime audio controls', () => {
  const source = read('src/features/meeting/NewMeetingModal.tsx')
  assert.doesNotMatch(source, /MediaRecorder|getUserMedia|实时语音|开始录音|停止录音|实时转写/)
})

console.log('project meeting minutes workflow contract OK')
