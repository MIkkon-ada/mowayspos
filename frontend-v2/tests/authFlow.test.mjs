import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')
const readRepo = (file) => fs.readFileSync(path.resolve(root, '..', file), 'utf8')

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

test('V2 local backend launcher allows the V2 frontend origin', () => {
  const launcher = fs.readFileSync(path.resolve(root, '..', 'bowei_ai_dashboard/run_local_backend_safe.py'), 'utf8')
  assert.match(launcher, /127\.0\.0\.1:6005/)
  assert.match(launcher, /localhost:6005/)
})

test('blocked frontend origins explain the backend allowlist problem', async () => {
  const { normalizeLoginError } = await loadAuthFlow()
  assert.equal(
    normalizeLoginError({ status: 403, body: { detail: 'origin_not_allowed' } }),
    '前端来源未加入后端白名单，请重启 V2 开发环境',
  )
})

test('V2 startup delegates to the readiness-aware orchestrator', () => {
  const launcher = readRepo('start-frontend-v2-dev.bat')
  assert.match(launcher, /start-v2-dev\.ps1/)
  assert.doesNotMatch(launcher, /timeout \/t 6/)

  const orchestrator = readRepo('start-v2-dev.ps1')
  assert.match(orchestrator, /6005/)
  assert.match(orchestrator, /8011/)
  assert.match(orchestrator, /api\/health/)
  assert.match(orchestrator, /v2-dev-processes\.json/)
  assert.match(orchestrator, /backend\.err\.log/)
  assert.match(orchestrator, /frontend\.err\.log/)
  assert.match(orchestrator, /Get-Process -Id \$ProcessId/)
  assert.match(readRepo('.gitignore'), /\.runtime\//)
  const backendLauncher = readRepo('bowei_ai_dashboard/start-backend-v2-dev.bat')
  assert.match(backendLauncher, /import dotenv, uvicorn/)
  assert.match(backendLauncher, /pip install -r requirements\.txt/)
  const frontendLauncher = read('start-frontend-v2-dev.bat')
  assert.match(frontendLauncher, /node_modules\\\.bin\\vite\.cmd/)
})

test('V2 shutdown only stops recorded processes', () => {
  const shutdown = readRepo('stop-v2-dev.ps1')
  assert.match(shutdown, /v2-dev-processes\.json/)
  assert.match(shutdown, /Stop-Process/)
  assert.match(shutdown, /taskkill\.exe/)
  assert.match(shutdown, /\/T/)
  assert.match(shutdown, /Remove-Item/)
  assert.match(readRepo('stop-frontend-v2-dev.bat'), /stop-v2-dev\.ps1/)
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
