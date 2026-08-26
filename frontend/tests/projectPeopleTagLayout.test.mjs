import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/features/settings/ProjectInitModal.tsx', import.meta.url), 'utf8')
const activeStart = source.indexOf('project-init-workbench')
const activeEnd = source.indexOf('  return createPortal(', activeStart)
const activeLayout = source.slice(activeStart, activeEnd)

test('selected people render as wrapping name tags without generated avatars', () => {
  assert.match(activeLayout, /flex[^"\n]*flex-wrap[^"\n]*gap-/)
  assert.match(activeLayout, /rounded-md border[^\n]*bg-/)
  assert.match(activeLayout, /person\.name/)
  assert.doesNotMatch(activeLayout, /bg-gradient-to-br \$\{getAvatarColor\(person\.name\)\}/)
})
