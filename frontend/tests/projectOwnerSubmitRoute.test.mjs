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
