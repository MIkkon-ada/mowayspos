import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const modal = readFileSync(new URL('../src/features/meeting/NewMeetingModal.tsx', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/api/meetings.ts', import.meta.url), 'utf8')

test('new meeting workspace offers the six agreed meeting types', () => {
  for (const label of ['项目例会', '专题会议', '启动会', '沟通会', '评审会', '复盘会']) {
    assert.match(modal, new RegExp(`label: '${label}'`))
  }
  assert.match(modal, /const MEETING_TYPE_OPTIONS = \[/)
})

test('meeting type options use one compact row on wide screens', () => {
  assert.match(modal, /grid gap-3 md:grid-cols-3 xl:grid-cols-6/)
})

test('new meeting keeps host and participants as separate fields', () => {
  assert.match(modal, /label="主持人"/)
  assert.match(modal, /label="参会人员"/)
  assert.match(modal, /label="抄送"/)
  assert.match(modal, /label="整理人"/)
})

test('standard Word minutes bypass AI rewriting and retain both action tables', () => {
  assert.match(modal, /result\.standard_minutes\?\.is_standard_minutes/)
  assert.match(modal, /source_mode: 'standard_minutes'/)
  assert.match(modal, /agenda_items_json: JSON\.stringify\(minutes\.agenda_items/)
  assert.match(modal, /task_list_json: JSON\.stringify\(minutes\.current_action_items/)
  assert.match(modal, /prior_action_items_json: JSON\.stringify\(minutes\.prior_action_items/)
  assert.match(modal, /不经过 AI 改写/)
  assert.match(modal, /function StandardMinutesReview/)
  assert.match(modal, /function ParsedRows/)
})

test('new meeting accepts additive Word Excel TXT text and audio sources without PDF', () => {
  assert.match(modal, /accept="\.docx,\.xlsx,\.txt"/)
  assert.doesNotMatch(modal, /\.pdf/)
  assert.match(modal, /会议文档/)
  assert.match(modal, /补充原文/)
  assert.match(modal, /音频转写/)
  assert.match(modal, /combineAnalysisSources/)
  assert.match(api, /extractMeetingDocumentText/)
  assert.match(api, /extract-document-text/)
})

test('new meeting preflights Skill inputs and blocks on clarification before generation', () => {
  assert.match(modal, /preflightMeetingSkill/)
  assert.match(modal, /waiting_for_answers/)
  assert.match(modal, /生成已暂停，需先完成以下核对/)
  assert.match(modal, /addMeetingSkillSnapshot/)
  assert.match(modal, /resumeMeetingSkillRun/)
  assert.match(api, /skill-runs\/preflight/)
})

test('review keeps analysis source in the record but does not display it as a sidebar', () => {
  assert.doesNotMatch(modal, /<SectionTitle>分析原文<\/SectionTitle>/)
  assert.match(modal, /transcript_text: analysisText/)
})
