import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'
import ts from 'typescript'
import { fileURLToPath } from 'node:url'

const source = readFileSync(new URL('../src/pages/ProjectDetailPage.tsx', import.meta.url), 'utf8')
const panelSource = readFileSync(new URL('../src/features/settings/ProjectsMgmtSection.tsx', import.meta.url), 'utf8')

assert.match(
  source,
  /import \{[^}]*dispatchProject[^}]*\} from '\.\.\/api\/projects'/,
  'project detail page must import the existing dispatch API',
)
assert.match(source, /createProjectDetailDispatcher<Project>/, 'page must create the tested dispatch action')
assert.match(source, /dispatch: dispatchProject/, 'dispatch flow must use the existing project dispatch API')
assert.match(source, /refresh: getProject/, 'dispatch flow must refresh project state')
assert.match(source, /const dispatchAttempt = dispatchFromDetail\(project\.id\)/, 'page handler must start the guarded action')
assert.match(source, /const refreshedProject = await dispatchAttempt/, 'page handler must await the guarded action')
assert.match(source, /if \(refreshedProject\) setProject\(refreshedProject\)/, 'refreshed project must replace stale page state')
assert.match(source, /toast\.success/, 'successful dispatch must provide visible feedback')
assert.match(source, /toast\.error/, 'failed dispatch must provide visible feedback')
assert.match(source, /dispatching=\{dispatching\}/, 'detail panel must receive the in-flight state')
assert.match(source, /onDispatch=\{\(\) => void handleDispatch\(\)\}/, 'detail panel must invoke the real dispatch handler')
assert.match(panelSource, /dispatching\?: boolean/, 'detail panel must accept an optional in-flight state')
assert.match(panelSource, /disabled=\{dispatching && btn\.onClick === onDispatch\}/, 'dispatch button must be disabled while dispatching')
assert.equal(
  (panelSource.match(/disabled=\{dispatching && btn\.onClick === onDispatch\}/g) ?? []).length,
  2,
  'wide and narrow detail layouts must both disable dispatch while busy',
)
assert.doesNotMatch(
  source,
  /onDispatch=\{async \(\) => \{\s*\/\/[^\n]*dispatch logic\s*\}\}/,
  'dispatch button must not use an empty callback',
)

console.log('project detail dispatch contract passed')

const flowUrl = new URL('../src/domain/projectDetailDispatch.ts', import.meta.url)

test('dispatch success is preserved when the follow-up refresh fails', async () => {
  assert.equal(existsSync(fileURLToPath(flowUrl)), true, 'project detail dispatch flow module must exist')
  const flowSource = readFileSync(flowUrl, 'utf8')
  const flowJs = ts.transpileModule(flowSource, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  }).outputText
  const { runProjectDetailDispatch } = await import(`data:text/javascript;base64,${Buffer.from(flowJs).toString('base64')}`)
  const events = []

  const refreshed = await runProjectDetailDispatch(2, {
    dispatch: async () => ({ ok: true, dispatched_to: 1 }),
    refresh: async () => { throw new Error('refresh unavailable') },
    onSuccess: (count) => events.push(`success:${count}`),
    onDispatchError: (message) => events.push(`dispatch-error:${message}`),
    onRefreshError: () => events.push('refresh-error'),
  })

  assert.equal(refreshed, null)
  assert.deepEqual(events, ['success:1', 'refresh-error'])
})

test('dispatch failure does not attempt a refresh', async () => {
  const flowSource = readFileSync(flowUrl, 'utf8')
  const flowJs = ts.transpileModule(flowSource, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  }).outputText
  const { runProjectDetailDispatch } = await import(`data:text/javascript;base64,${Buffer.from(flowJs).toString('base64')}#failure`)
  let refreshCalls = 0
  const errors = []

  const refreshed = await runProjectDetailDispatch(2, {
    dispatch: async () => { throw new Error('permission denied') },
    refresh: async () => { refreshCalls += 1; return {} },
    onSuccess: () => {},
    onDispatchError: (message) => errors.push(message),
    onRefreshError: () => {},
  })

  assert.equal(refreshed, null)
  assert.equal(refreshCalls, 0)
  assert.deepEqual(errors, ['permission denied'])
})

test('project detail dispatcher rejects a concurrent second attempt', async () => {
  const flowSource = readFileSync(flowUrl, 'utf8')
  const flowJs = ts.transpileModule(flowSource, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  }).outputText
  const { createProjectDetailDispatcher } = await import(`data:text/javascript;base64,${Buffer.from(flowJs).toString('base64')}#concurrent`)
  let dispatchCalls = 0
  let finishDispatch
  const dispatcher = createProjectDetailDispatcher({
    dispatch: async () => {
      dispatchCalls += 1
      await new Promise((resolve) => { finishDispatch = resolve })
      return { ok: true, dispatched_to: 1 }
    },
    refresh: async () => ({ id: 2, status: 'dispatched' }),
    onSuccess: () => {},
    onDispatchError: () => {},
    onRefreshError: () => {},
  })

  const firstAttempt = dispatcher(2)
  const secondAttempt = dispatcher(2)

  assert.notEqual(firstAttempt, null)
  assert.equal(secondAttempt, null)
  assert.equal(dispatchCalls, 1)
  finishDispatch()
  assert.deepEqual(await firstAttempt, { id: 2, status: 'dispatched' })
})
