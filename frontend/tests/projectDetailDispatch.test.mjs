import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/pages/ProjectDetailPage.tsx', import.meta.url), 'utf8')
const panelSource = readFileSync(new URL('../src/features/settings/ProjectsMgmtSection.tsx', import.meta.url), 'utf8')

test('project detail no longer exposes a dispatch gate', () => {
  assert.doesNotMatch(source, /dispatchProject|createProjectDetailDispatcher|onDispatch|dispatching/)
  assert.doesNotMatch(panelSource, /下发给负责人|handleDispatch|dispatchProject|onDispatch|dispatching\?/)
  assert.match(panelSource, /notifyProjectOwner/)
  assert.match(panelSource, /status === 'draft' && roles\.isRealOwner/)
})

console.log('project lifecycle detail contract passed')
