import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

const page = readFileSync(new URL('../src/pages/DashboardPage.tsx', import.meta.url), 'utf8')
const mobileUrl = new URL('../src/features/dashboard/MobileDashboardContent.tsx', import.meta.url)

test('dashboard mounts a mobile-only view below the 800px desktop breakpoint', () => {
  assert.match(page, /MobileDashboardContent/)
  assert.match(page, /min-\[800px\]:hidden/)
  assert.match(page, /hidden min-\[800px\]:flex/)
})

test('mobile dashboard component exists as a separate presentation unit', () => {
  assert.equal(existsSync(mobileUrl), true)
})

test('mobile dashboard keeps an entry to the existing notification center', () => {
  const mobile = readFileSync(mobileUrl, 'utf8')
  assert.match(mobile, /onOpenNotifications/)
  assert.match(mobile, /通知中心/)
  assert.match(page, /onOpenNotifications=\{\(\) => navigate\('\/home\/notifications'\)\}/)
})

test('mobile dashboard preserves owner project notices from the desktop dashboard', () => {
  const mobile = readFileSync(mobileUrl, 'utf8')
  assert.match(mobile, /projectNotice/)
  assert.match(mobile, /actionLabel/)
  assert.match(page, /actionLabel: '去填写'/)
  assert.match(page, /projectNotice=\{mobileProjectNotice\}/)
})
