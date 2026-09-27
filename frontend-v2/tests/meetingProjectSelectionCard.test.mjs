import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/pages/MeetingPage.tsx', import.meta.url), 'utf8')

test('meeting project selector loads real project meetings for each project', () => {
  assert.match(source, /fetchMeetings/)
  assert.match(source, /const \[projectMeetings, setProjectMeetings\] = useState<Record<number, MeetingItem\[\]>>\(\{\}\)/)
  assert.match(source, /Promise\.all\(projects\.map/)
  assert.match(source, /const projectIds = projects\.map\(\(project\) => project\.id\)\.join\(','\)/)
  assert.match(source, /project\.code \?\? ''/)
  assert.match(source, /prev\.set\('projectId', String\(p\.id\)\)/)
})

test('meeting project selector is a reference-aligned project directory', () => {
  assert.match(source, /project-selector-table/)
  assert.match(source, /grid-cols-\[minmax\(300px,2\.1fr\)_150px_190px_minmax\(220px,1\.4fr\)_150px\]/)
  assert.match(source, /项目名称/)
  assert.match(source, /项目经理/)
  assert.match(source, /最近会议/)
  assert.match(source, /查看会议纪要/)
  assert.doesNotMatch(source, /meetingCount/)
  assert.doesNotMatch(source, /project-card-members/)
  assert.doesNotMatch(source, /project-card-period/)
})
