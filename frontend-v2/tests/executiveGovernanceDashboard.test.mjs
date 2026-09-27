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
  assert.match(types, /project_signals:\s*Record<string/)
})

test('governance view model module exists for deterministic scope aggregation', () => {
  assert.equal(existsSync(helperUrl), true)
})

test('governance presentation module exists separately from dashboard routing', () => {
  assert.equal(existsSync(componentUrl), true)
  const component = readFileSync(componentUrl, 'utf8')
  assert.match(component, /管理层关注/)
  assert.match(component, /待决策问题/)
  assert.match(component, /待协调问题/)
  assert.match(component, /项目概况/)
  assert.match(component, /进入问题中心/)
  assert.match(component, /onOpenIssueCenter\(project\.id, '待决策'\)/)
  assert.doesNotMatch(component, /重点 Initiative/)
})

test('dashboard preserves scope control and mounts one responsive governance content', () => {
  assert.match(page, /<select[\s\S]*handleScopeChange/)
  assert.match(page, /<ChevronDownIcon/)
  assert.match(page, /<GovernanceDashboardContent/)
  assert.match(page, /onOpenIssueCenter=\{openIssueCenter\}/)
  assert.match(page, /onOpenProject=/)
  assert.doesNotMatch(page, /<MobileDashboardContent/)
})
