import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const issuesSource = readFileSync(new URL('../src/pages/IssuesPage.tsx', import.meta.url), 'utf8')
const tasksSource = readFileSync(new URL('../src/pages/TaskManagementPage.tsx', import.meta.url), 'utf8')

const classTokens = (tag) => tag.match(/className="([^"]+)"/)?.[1].split(/\s+/) ?? []

test('every Issues page header wraps and uses responsive horizontal padding', () => {
  const headers = issuesSource.match(/<header className="[^"]+"/g) ?? []
  assert.equal(headers.length, 4)

  for (const header of headers) {
    const tokens = classTokens(header)
    for (const required of ['min-h-16', 'flex-wrap', 'px-4', 'py-3', 'lg:px-6']) {
      assert.ok(tokens.includes(required), `header is missing ${required}: ${header}`)
    }
    assert.ok(!tokens.includes('h-16'), `header still has fixed height: ${header}`)
  }
})

test('Issues page summary, filters, and main spacing adapt without page-level horizontal scrolling', () => {
  assert.match(issuesSource, /grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6/)
  assert.match(issuesSource, /mb-6 flex flex-wrap items-center gap-4/)
  assert.match(issuesSource, /mx-auto max-w-\[1440px\] px-4 py-6 lg:px-6/)
  assert.match(issuesSource, /min-h-0 flex-1 flex gap-4 px-4 py-4 lg:px-5 overflow-hidden/)
  assert.match(issuesSource, /flex-1 overflow-hidden bg-\[#f6f8fb\] flex flex-col/)
})

test('every Issues page wide table scrolls locally and keeps a readable minimum width', () => {
  const tables = issuesSource.match(/<table className="[^"]+"/g) ?? []
  assert.equal(tables.length, 4)
  for (const table of tables) {
    assert.ok(classTokens(table).includes('min-w-[920px]'), `table lacks minimum width: ${table}`)
  }

  const localTableWrappers = issuesSource.match(/<div className="[^"]*overflow-x-auto[^"]*">\s*<table/g) ?? []
  assert.equal(localTableWrappers.length, 4)
})

test('Task Management top header wraps while retaining local horizontal overflow', () => {
  const header = tasksSource.match(/<header className="[^"]+"/)?.[0]
  assert.ok(header)
  const tokens = classTokens(header)
  for (const required of ['min-h-14', 'flex-wrap', 'px-4', 'py-2', 'lg:px-6', 'overflow-x-auto']) {
    assert.ok(tokens.includes(required), `task header is missing ${required}: ${header}`)
  }
  assert.ok(!tokens.includes('h-14'))
  assert.match(tasksSource, /className="flex-1 min-w-0 min-h-0 flex overflow-hidden"/)
})

test('Task Management detail pane overlays below lg and returns to the split layout above lg', () => {
  const aside = tasksSource.match(/data-testid="work-progress-detail-panel"\s+className="([^"]+)"/)?.[1]
  assert.ok(aside)
  const tokens = aside.split(/\s+/)
  for (const required of [
    'fixed', 'inset-y-0', 'right-0', 'z-40', 'w-[min(380px,calc(100vw-64px))]', 'shadow-2xl',
    'lg:static', 'lg:z-auto', 'lg:w-[340px]', 'lg:shadow-none', 'xl:w-[380px]',
  ]) {
    assert.ok(tokens.includes(required), `detail pane is missing ${required}`)
  }
  assert.ok(!tokens.includes('w-[380px]'))
})
