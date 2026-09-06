import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const config = read('../src/config/aiDocumentFormats.ts')
const meeting = read('../src/features/meeting/NewMeetingModal.tsx')
const workReport = read('../src/features/voice-update/VoiceUpdateInputPanel.tsx')
const taskPlan = read('../src/components/key-task-workspace/ExecutionPlanCreateDrawer.tsx')
const projectInit = read('../src/features/settings/OwnerSubmitAiPanel.tsx')

test('defines each AI upload format in one frontend capability module', () => {
  assert.match(config, /meeting:\s*\['\.docx', '\.txt', '\.xlsx'\]/)
  assert.match(config, /workReport:\s*\['\.docx', '\.pdf', '\.xlsx', '\.pptx'\]/)
  assert.match(config, /taskPlan:\s*\['\.docx', '\.xlsx', '\.txt'\]/)
  assert.match(config, /projectInit:\s*\['\.pdf', '\.doc', '\.docx', '\.xls', '\.xlsx', '\.txt'\]/)
})

test('all AI upload controls consume the shared format definitions', () => {
  for (const source of [meeting, workReport, taskPlan, projectInit]) {
    assert.match(source, /aiDocumentFormats/)
  }
  assert.match(meeting, /会议纪要支持 Word、TXT、Excel/)
})
