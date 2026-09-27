import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/features/settings/ProjectInitModal.tsx', import.meta.url), 'utf8')
const pickerSource = source.slice(source.indexOf('export function ProjectPeoplePickerPopover'))

test('people picker shows names without generated avatar blocks', () => {
  assert.match(pickerSource, /grid-cols-1/)
  assert.match(pickerSource, /sm:grid-cols-2/)
  assert.match(pickerSource, /lg:grid-cols-3/)
  assert.match(pickerSource, /person\.name/)
  assert.match(pickerSource, /whitespace-nowrap|break-words/)
  assert.doesNotMatch(pickerSource, /getAvatarColor\(person\.name\)/)
  assert.doesNotMatch(pickerSource, /bg-gradient-to-br \$\{getAvatarColor/)
})
