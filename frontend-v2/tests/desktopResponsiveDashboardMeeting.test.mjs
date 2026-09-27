import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const dashboard = readFileSync(new URL('../src/pages/DashboardPage.tsx', import.meta.url), 'utf8')
const meeting = readFileSync(new URL('../src/pages/MeetingPage.tsx', import.meta.url), 'utf8')

test('dashboard uses wrapping desktop header and responsive content padding', () => {
  assert.match(dashboard, /<header className="hidden min-\[800px\]:flex min-h-16 flex-wrap items-center px-4 py-3 lg:px-6 gap-4 flex-shrink-0 bg-white border-b"/)
  assert.match(dashboard, /<div className="flex-1 min-w-0">/)
  assert.match(dashboard, /<div className="flex flex-wrap items-center gap-2">/)
  assert.match(dashboard, /<main className="hidden min-\[800px\]:block flex-1 overflow-y-auto p-4 lg:p-6 space-y-5"/)
})

test('dashboard mounts the responsive executive governance layout instead of legacy chart grids', () => {
  assert.match(dashboard, /<GovernanceDashboardContent/)
  assert.match(dashboard, /projectHealthRows=/)
  assert.match(dashboard, /onOpenAction=/)
  assert.match(dashboard, /onOpenInitiative=/)
  assert.doesNotMatch(dashboard, /chart\.js\/auto/)
  assert.doesNotMatch(dashboard, /<canvas ref=\{chartRef\}/)
})

test('meeting uses wrapping desktop header and responsive content padding', () => {
  assert.match(meeting, /<header className="min-h-16 flex flex-wrap items-center px-4 py-3 lg:px-6 gap-4 flex-shrink-0 bg-white border-b"/)
  assert.match(meeting, /<div className="flex-1 min-w-0">/)
  assert.match(meeting, /<div className="flex flex-wrap items-center gap-2">/)
  assert.match(meeting, /flex-1 overflow-y-auto[^\n]*p-4 lg:p-6/)
})

test('selected meeting detail uses responsive five-track layout', () => {
  assert.match(meeting, /grid-cols-2[^"\n]*lg:grid-cols-3[^"\n]*xl:grid-cols-5/)
  assert.match(meeting, /className="bg-white rounded-2xl border p-5 col-span-2 lg:col-span-3 xl:col-span-2 overflow-y-auto"/)
  assert.match(meeting, /className="col-span-2 lg:col-span-3 xl:col-span-3 flex flex-col gap-4"/)
})

test('responsive pages do not use JavaScript resize listeners', () => {
  for (const source of [dashboard, meeting]) {
    assert.doesNotMatch(source, /addEventListener\(\s*['"]resize['"]|window\.innerWidth|matchMedia\(/)
  }
})
