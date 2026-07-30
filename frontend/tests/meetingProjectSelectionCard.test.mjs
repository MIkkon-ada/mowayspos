import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/pages/MeetingPage.tsx', import.meta.url), 'utf8')

test('meeting project selector renders square project information cards', () => {
  assert.match(source, /import \{ getOverview \} from '\.\.\/api\/dashboard'/)
  assert.match(source, /const \[projectProgress, setProjectProgress\] = useState<Record<number, number>>\(\{\}\)/)
  assert.match(source, /getOverview\(\)/)
  assert.match(source, /projectProgress\[p\.id\] \?\? 0/)
  assert.match(source, /p\.owners\?\.\[0\] \?\? p\.coordinator/)
  assert.match(source, /grid grid-cols-1 sm:grid-cols-2/)
  assert.match(source, /aspect-square/)
  assert.match(source, /project-card-period/)
  assert.match(source, /project-card-manager/)
  assert.match(source, /project-card-members/)
  assert.match(source, /project-card-progress/)
  assert.match(source, /role="progressbar"/)
  assert.match(source, /prev\.set\('projectId', String\(p\.id\)\)/)
})
