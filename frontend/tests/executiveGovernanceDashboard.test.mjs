import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

const types = readFileSync(new URL('../src/types.ts', import.meta.url), 'utf8')
const page = readFileSync(new URL('../src/pages/DashboardPage.tsx', import.meta.url), 'utf8')
const helperUrl = new URL('../src/features/dashboard/governanceDashboard.ts', import.meta.url)
const componentUrl = new URL('../src/features/dashboard/GovernanceDashboardContent.tsx', import.meta.url)

test('dashboard overview declares the compact governance contract', () => {
  assert.match(types, /export type GovernanceActionKind/)
  assert.match(types, /export type GovernanceDashboardOverview/)
  assert.match(types, /governance\?:\s*GovernanceDashboardOverview/)
  assert.match(types, /key_task_id:\s*number/)
  assert.match(types, /workstream_title:\s*string/)
})

test('governance view model module exists for deterministic scope aggregation', () => {
  assert.equal(existsSync(helperUrl), true)
})

test('governance presentation module exists separately from dashboard routing', () => {
  assert.equal(existsSync(componentUrl), true)
  const component = readFileSync(componentUrl, 'utf8')
  assert.match(component, /当前需要关注/)
  assert.match(component, /需要处理/)
  assert.match(component, /项目健康/)
  assert.match(component, /重点 Initiative/)
  assert.match(component, /collaborators\.slice\(0, 3\)/)
  assert.match(component, /evidence_confirmed/)
  assert.match(component, /healthLabel/)
})

test('desktop dashboard preserves real controls and mounts governance content', () => {
  assert.match(page, /<select[\s\S]*handleScopeChange/)
  assert.match(page, /<select[\s\S]*setSelectedMonth/)
  assert.match(page, /<GovernanceDashboardContent/)
  assert.match(page, /onOpenAction=/)
  assert.match(page, /onOpenInitiative=/)
  assert.match(page, /<MobileDashboardContent/)
})
