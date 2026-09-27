import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const page = readFileSync(new URL('../src/pages/DashboardPage.tsx', import.meta.url), 'utf8')
const content = readFileSync(new URL('../src/features/dashboard/GovernanceDashboardContent.tsx', import.meta.url), 'utf8')

test('dashboard uses the same management overview on narrow and wide screens', () => {
  assert.match(page, /<GovernanceDashboardContent/)
  assert.doesNotMatch(page, /<MobileDashboardContent/)
  assert.match(content, /grid-cols-2 sm:grid-cols-3/)
  assert.match(content, /xl:grid-cols-/)
})

test('project issue counts open the existing issue center', () => {
  assert.match(content, /onOpenIssueCenter\(project\.id, '待决策'\)/)
  assert.match(content, /onOpenIssueCenter\(project\.id, '待协调'\)/)
  assert.match(page, /navigate\(`\/work\/issues/)
})

test('dashboard does not duplicate the issue center or notification panel', () => {
  assert.doesNotMatch(page, /setShowNotif/)
  assert.doesNotMatch(content, /问题列表/)
})

test('dashboard does not render project-init notices', () => {
  assert.doesNotMatch(page, /projectNotice=\{/)
  assert.doesNotMatch(page, /actionLabel: '去填写'/)
})
