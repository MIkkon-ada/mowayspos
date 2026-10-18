import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

test('project creation surfaces preserve one retry identity per actor and payload', () => {
  const projectAdmin = read('src/pages/ProjectAdminPage.tsx')
  const settings = read('src/features/settings/ProjectsMgmtSection.tsx')

  for (const source of [projectAdmin, settings]) {
    assert.match(source, /projectCreateRequestIdsRef = useRef\(new Map<string, string>\(\)\)/)
    assert.match(source, /actor: currentUser\?\.person_id \?\? currentUser\?\.account_id \?\? currentUser\?\.username/)
    assert.match(source, /projectCreateRequestIdsRef\.current\.get\(fingerprint\)/)
    assert.match(source, /createProject\(payload, requestId\)/)
    assert.match(source, /projectCreateRequestIdsRef\.current\.clear\(\)/)
  }
})
