import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

async function loadAuthFlow() {
  const source = read('src/domain/authFlow.ts')
  const js = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
}

const member = {
  is_tech_admin: false,
  is_ceo: false,
  can_view_all: false,
  must_change_password: false,
}

test('ordinary members enter the personal task center after login', async () => {
  const { getPostLoginDestination } = await loadAuthFlow()
  assert.equal(getPostLoginDestination(member, [{ id: 4 }], null), '/member/tasks')
  assert.equal(getPostLoginDestination(member, [{ id: 4 }, { id: 5 }], 5), '/member/tasks')
})
test('project owners enter project management after login', async () => {
  const { getPostLoginDestination } = await loadAuthFlow()
  assert.equal(getPostLoginDestination(member, [{ id: 4, user_roles: ['owner'] }], null), '/home/projects')
  assert.equal(getPostLoginDestination({ ...member, owned_projects: ['Draft project'] }, [], null), '/home/projects')
})

test('external auth returns to the shared home route resolver', () => {
  assert.match(read('src/layouts/AppLayout.tsx'), /window\.location\.replace\('\/home'\)/)
  const backendAuth = fs.readFileSync(path.resolve(root, '..', 'bowei_ai_dashboard/app/routers/wecom_auth.py'), 'utf8')
  assert.match(backendAuth, /RedirectResponse\(_frontend_url\(["']\/home["']\)\)/)
})
test('mytasks sidebar navigation always enters the personal task center', async () => {
  const { getProjectScopedNavigationDestination } = await loadAuthFlow()
  assert.equal(getProjectScopedNavigationDestination('mytasks', null, []), '/member/tasks')
  assert.equal(getProjectScopedNavigationDestination('mytasks', 4, [{ id: 4 }]), '/member/tasks')
})

test('privileged users enter the dashboard and the removed forced-password flag does not redirect', async () => {
  const { getPostLoginDestination } = await loadAuthFlow()
  assert.equal(getPostLoginDestination({ ...member, is_tech_admin: true }, [{ id: 4 }], null), '/home/dashboard')
  assert.equal(getPostLoginDestination({ ...member, must_change_password: true }, [], null), '/home/dashboard')
})
