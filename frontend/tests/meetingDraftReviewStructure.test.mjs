import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/pages/MeetingPage.tsx', import.meta.url), 'utf8')

test('meeting drafts show source material beside AI notes', () => {
  assert.ok(source.includes("searchParams.get('meetingId')"))
  assert.ok(source.includes('提交原文'))
  assert.ok(source.includes('AI 提取纪要'))
  assert.ok(source.includes('selected.transcript_text'))
  assert.ok(source.includes('未进入 AI 确认中心'))
})
