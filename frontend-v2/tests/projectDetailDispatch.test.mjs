import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const panelSource = readFileSync(new URL('../src/features/settings/ProjectsMgmtSection.tsx', import.meta.url), 'utf8')

test('project management exposes an explicit dispatch gate', () => {
  assert.match(panelSource, /dispatchProject/)
  assert.match(panelSource, /async function handleDispatch/)
  assert.match(panelSource, /下发给负责人/)
  assert.match(panelSource, /isProjectDispatchReady/)
  assert.doesNotMatch(panelSource, /notifyProjectOwner/)
})

console.log('project lifecycle detail contract passed')
