import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const routesSource = fs.readFileSync(path.join(root, 'src/app/routes.tsx'), 'utf8')

test('setup routing fails closed when the status endpoint does not return a boolean result', () => {
  assert.match(routesSource, /type SetupState = 'loading' \| 'needed' \| 'done' \| 'error'/)
  assert.match(routesSource, /if \(!response\.ok\)/)
  assert.match(routesSource, /typeof data\.initialized !== 'boolean'/)
  assert.match(routesSource, /setSetupState\('error'\)/)
})

test('setup routing shows an explicit check failure instead of the initialization form', () => {
  assert.match(routesSource, /setupState === 'error'/)
  assert.match(routesSource, /初始化状态检查失败/)
})
