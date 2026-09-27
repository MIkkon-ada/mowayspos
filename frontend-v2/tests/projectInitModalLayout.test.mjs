import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const source = fs.readFileSync(path.resolve(here, '../src/features/settings/ProjectInitModal.tsx'), 'utf8')

test('project init exposes an end-date pending control below the date input', () => {
  assert.match(source, /const \[endDatePending, setEndDatePending\] = useState\(false\)/)
  assert.match(source, /<label className="block">结束日期<\/label>/)
  assert.match(source, /disabled=\{endDatePending\}/)
  assert.match(source, /aria-pressed=\{endDatePending\}[\s\S]{0,700}暂不填写/)
  assert.match(source, /setForm\(\(prev\) => \(\{ \.\.\.prev, end_date: '' \}\)\)/)
})

test('project init marks both coach and owner as required team roles', () => {
  assert.match(source, /const REQUIRED_TEAM_ROLES: TeamRole\[\] = \['project_ceo', 'owner'\]/)
  assert.match(source, /REQUIRED_TEAM_ROLES\.includes\(role\)/)
})
