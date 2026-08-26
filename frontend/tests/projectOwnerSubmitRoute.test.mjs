import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const readSource = (relativePath) => fs.readFileSync(path.resolve(here, '..', relativePath), 'utf8')

const routesSource = readSource('src/app/routes.tsx')
const dashboardSource = readSource('src/pages/DashboardPage.tsx')
const projectsSource = readSource('src/features/settings/ProjectsMgmtSection.tsx')
const detailSource = readSource('src/pages/ProjectDetailPage.tsx')
const workbenchSource = readSource('src/features/settings/OwnerSubmitModal.tsx')
const ownerSubmitPageSource = readSource('src/pages/ProjectOwnerSubmitPage.tsx')
const lifecycleSource = readSource('src/domain/projectLifecycleStatus.ts')

test('owner submit is a guarded project-detail child route rather than an overlay-only feature', () => {
  assert.match(routesSource, /ProjectOwnerSubmitPage/)
  assert.match(routesSource, /path="projects\/:projectId\/owner-submit"/)
  assert.match(routesSource, /path="projects\/:projectId\/owner-submit"[\s\S]{0,260}RequireCapability mode="project_view"/)
  assert.doesNotMatch(workbenchSource, /fixed inset-0/)
  assert.doesNotMatch(workbenchSource, /bg-slate-950\/30/)
})

test('all existing owner-submit entries navigate to the project child page', () => {
  assert.doesNotMatch(dashboardSource, /OwnerSubmitModal/)
  assert.doesNotMatch(projectsSource, /OwnerSubmitModal/)
  for (const source of [dashboardSource, projectsSource, detailSource]) {
    assert.match(source, /projectOwnerSubmitPath/)
  }
  assert.match(detailSource, /projectEditPath/)
  assert.doesNotMatch(dashboardSource, /\?edit=/)
  assert.doesNotMatch(projectsSource, /\?edit=/)
})

test('owner submit page renders the editable workbench only for a dispatched or returned real project owner', () => {
  assert.match(ownerSubmitPageSource, /getProjectMembers/)
  assert.match(ownerSubmitPageSource, /currentUser\?\.person_id/)
  assert.match(ownerSubmitPageSource, /member\.role === 'owner'/)
  assert.match(ownerSubmitPageSource, /canShowProjectSubmitAction\(project\)/)
  assert.match(ownerSubmitPageSource, /项目尚未下发，项目负责人暂不可填写/)
  assert.match(ownerSubmitPageSource, /无权完善该项目方案/)
})

test('owner submit route keeps the centered page-local workbench shell', () => {
  assert.match(ownerSubmitPageSource, /return \(\s*<div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-\[#F1F5F9\] p-4 sm:p-6">\s*<div className="mx-auto flex min-h-0 w-full max-w-\[1400px\] flex-1 flex-col">\s*<OwnerSubmitWorkbench/)
})

test('draft owners have no detail-panel or dashboard submit entry', () => {
  assert.doesNotMatch(projectsSource, /status === 'draft' && roles\.isRealOwner[\s\S]{0,160}onOwnerSubmit/)
  assert.match(projectsSource, /status === 'dispatched' && roles\.isRealOwner[\s\S]{0,160}onOwnerSubmit/)
  assert.match(projectsSource, /status === 'returned' && roles\.isRealOwner[\s\S]{0,160}onOwnerSubmit/)
  assert.match(dashboardSource, /canShowProjectSubmitAction\(dashboardProject\) && dashboardProjectRoles\.includes\('owner'\)/)
  assert.match(lifecycleSource, /return status === 'dispatched' \|\| status === 'returned'/)
})
