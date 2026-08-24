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

test('meeting API exposes the existing delete endpoint', () => {
  const api = readFileSync(new URL('../src/api/meetings.ts', import.meta.url), 'utf8')
  assert.match(api, /import \{[^}]*apiDelete[^}]*\} from '\.\/client'/)
  assert.match(api, /export function deleteMeeting\(id: number\): Promise<\{ ok: boolean \}>/)
  assert.match(api, /apiDelete<\{ ok: boolean \}>\('\/api\/meetings\/' \+ id\)/)
})

test('meeting list renders a permission-aware confirmed delete action instead of an inert ellipsis', () => {
  assert.match(source, /import \{[^}]*deleteMeeting[^}]*\} from '\.\.\/api\/meetings'/)
  assert.match(source, /const canDeleteMeeting = Boolean\(currentUser\?\.is_tech_admin \|\| \(effectiveProject\?\.user_roles \?\? currentProjectRoles\)\.includes\('owner'\)\)/)
  assert.match(source, /window\.confirm\('确认删除会议纪要「' \+ title \+ '」吗？此操作不可恢复。'\)/)
  assert.match(source, /await deleteMeeting\(meeting\.id\)/)
  assert.match(source, /setMeetings\(\(rows\) => rows\.filter\(\(row\) => row\.id !== meeting\.id\)\)/)
  assert.match(source, /setSelected\(\(row\) => row\?\.id === meeting\.id \? null : row\)/)
  assert.match(source, /会议纪要已删除/)
  assert.match(source, /canDeleteMeeting && !projectArchived && <button/)
  assert.doesNotMatch(source, /<span className="text-lg leading-none text-slate-400">…<\/span>/)
})
