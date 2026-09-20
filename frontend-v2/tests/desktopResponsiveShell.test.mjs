import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const testDir = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(testDir, '..')
const projectLayoutSource = fs.readFileSync(
  path.join(frontendRoot, 'src/layouts/ProjectLayout.tsx'),
  'utf8',
)
const sidebarSource = fs.readFileSync(
  path.join(frontendRoot, 'src/components/Sidebar.tsx'),
  'utf8',
)

test('project content column can shrink in both axes without overflowing the shell', () => {
  assert.match(
    projectLayoutSource,
    /<div className="flex-1 min-w-0 min-h-0 flex flex-col overflow-hidden">/,
  )
})

test('sidebar changes width at the xl breakpoint without resize listeners', () => {
  assert.match(
    sidebarSource,
    /<aside className="app-sidebar w-16 xl:w-44 flex-shrink-0 flex flex-col overflow-hidden"/,
  )
  assert.doesNotMatch(sidebarSource, /addEventListener\(['"]resize['"]/)
  assert.doesNotMatch(sidebarSource, /window\.innerWidth/)
})

test('brand row centers compact content and expands logo and notifications at xl', () => {
  assert.match(sidebarSource, /justify-center xl:justify-between/)
  assert.match(sidebarSource, /className="h-8 max-w-8 xl:max-w-\[90px\] object-contain flex-shrink-0"/)
  assert.doesNotMatch(sidebarSource, /maxWidth\s*:/)
  assert.match(sidebarSource, /className="hidden xl:block"[\s\S]*?<NotificationBell \/>/)
})

test('navigation keeps icon access while labels and badges appear only at xl', () => {
  assert.match(sidebarSource, /title=\{entry\.label\}/)
  assert.match(
    sidebarSource,
    /className="hidden xl:block flex-1 min-w-0"[\s\S]*?\{entry\.label\}/,
  )
  assert.match(
    sidebarSource,
    /className="hidden xl:inline-flex"[\s\S]*?entry\.badge > 99/,
  )
})

test('account footer stacks compact controls and hides only user details', () => {
  assert.match(
    sidebarSource,
    /className="px-3 py-2\.5 flex flex-col xl:flex-row items-center gap-2 flex-shrink-0"/,
  )
  assert.match(
    sidebarSource,
    /className="hidden xl:block flex-1 min-w-0"[\s\S]*?\{userName \|\|/,
  )
  assert.match(sidebarSource, /navigate\('\/change-password'\)/)
  assert.match(sidebarSource, /onClick=\{onLogout\}/)
  assert.match(
    sidebarSource,
    /const userIdentityLabel = `\$\{userName \|\| '未登录'\} · \$\{roleText \|\| '暂无角色'\}`/,
  )
  assert.match(
    sidebarSource,
    /className="w-7 h-7 rounded-full[\s\S]*?title=\{userIdentityLabel\}[\s\S]*?aria-label=\{userIdentityLabel\}/,
  )
})
