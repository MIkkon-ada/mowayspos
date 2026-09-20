import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

const layout = readFileSync(new URL('../src/layouts/ProjectLayout.tsx', import.meta.url), 'utf8')
const mobileUrl = new URL('../src/components/MobileAppNavigation.tsx', import.meta.url)
const navigationModelUrl = new URL('../src/domain/navigationModel.ts', import.meta.url)

test('project layout switches from desktop sidebar to mobile navigation at 800px', () => {
  assert.match(layout, /<div className="hidden min-\[800px\]:flex">[\s\S]*?<Sidebar/)
  assert.match(layout, /<MobileAppNavigation/)
  assert.match(layout, /min-\[800px\]:hidden/)
})

test('mobile navigation has four primaries and a more drawer', () => {
  assert.equal(existsSync(mobileUrl), true)
  const source = readFileSync(mobileUrl, 'utf8')
  for (const label of ['首页', '任务', '确认', '更多']) assert.match(source, new RegExp(label))
  assert.match(source, /aria-label="更多功能"/)
  assert.doesNotMatch(source, /window\.innerWidth|matchMedia\(|addEventListener\(\s*['"]resize['"]/)
})

test('desktop and mobile use the same permission-aware navigation entries', () => {
  assert.equal(existsSync(navigationModelUrl), true)
  const source = readFileSync(navigationModelUrl, 'utf8')
  assert.match(source, /export function getNavigationEntries/)
  assert.match(source, /showParticipantModules/)
  assert.match(source, /canViewMeetings/)
  assert.match(source, /currentUser\?\.is_tech_admin/)
})
