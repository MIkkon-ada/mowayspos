import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const testDir = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(testDir, '..')
const sidebarSource = fs.readFileSync(
  path.join(frontendRoot, 'src/components/Sidebar.tsx'),
  'utf8',
)
const archiveCss = fs.readFileSync(
  path.join(frontendRoot, 'src/features/project-archive/projectArchive.css'),
  'utf8',
)

test('sidebar uses 64px compact width and expands to 176px at xl', () => {
  assert.match(
    sidebarSource,
    /<aside className="app-sidebar w-16 xl:w-44 flex-shrink-0 flex flex-col overflow-hidden"/,
  )
  assert.doesNotMatch(sidebarSource, /\bw-56\b/)
  assert.doesNotMatch(sidebarSource, /addEventListener\(['"]resize['"]/)
  assert.doesNotMatch(sidebarSource, /window\.innerWidth/)
})

test('brand header renders a borderless MOWAYS logo on white with a notification bell', () => {
  assert.doesNotMatch(sidebarSource, /SYSTEM_NAME_CN/)
  assert.match(sidebarSource, /platformName\?: string/)
  assert.doesNotMatch(sidebarSource, /\{platformName\s*\}/)
  assert.match(sidebarSource, /const effectiveLogoUrl = logoUrl \|\| '\/moways-logo-transparent\.png'/)
  assert.match(sidebarSource, /background: '#FFFFFF'/)
  assert.match(sidebarSource, /borderBottom: '1px solid #E2E8F0'/)
  assert.match(sidebarSource, /<img src=\{effectiveLogoUrl\} alt="MOWAYS 博维咨询"/)
  assert.match(sidebarSource, /className="hidden xl:block"[\s\S]*?<NotificationBell \/>/)
  assert.match(sidebarSource, /className="flex items-center justify-center xl:justify-between px-3 h-14 flex-shrink-0"/)
  assert.match(sidebarSource, /className="h-8 max-w-8 xl:max-w-\[90px\] object-contain flex-shrink-0"/)
  assert.doesNotMatch(sidebarSource, /linear-gradient\(135deg,var\(--brand-accent/)
})

test('navigation keeps every existing item and permission boundary', () => {
  for (const token of [
    "label: '驾驶舱'",
    "label: '工作推进表'",
    "label: '我的任务'",
    'label: AI_CONFIRM_CENTER_LABEL',
    "label: '工作汇报'",
    "label: '会议纪要'",
    "label: '成果库'",
    "label: '问题中心'",
    "label: '组织管理'",
    "label: '项目管理'",
    "label: '通知中心'",
    "label: '系统设置'",
  ]) {
    assert.ok(sidebarSource.includes(token), `missing navigation contract: ${token}`)
  }

  for (const condition of [
    'showParticipantModules && hasActiveProject',
    'showParticipantModules && isPrivileged',
    "globalUserRoles.includes('project_ceo')",
    "globalUserRoles.includes('owner')",
    'currentUser?.is_tech_admin',
  ]) {
    assert.ok(sidebarSource.includes(condition), `missing permission condition: ${condition}`)
  }
})

test('navigation keeps its click routing and compact readable dimensions', () => {
  assert.match(sidebarSource, /function handleNavigate\(page: AppPage\)/)
  assert.match(sidebarSource, /navigate\('\/home\/dashboard'\)/)
  assert.match(sidebarSource, /onNavigate\(page\)/)
  assert.match(sidebarSource, /onClick=\{\(\) => handleNavigate\(entry\.page\)\}/)
  assert.match(sidebarSource, /title=\{entry\.label\}/)
  assert.match(sidebarSource, /<nav className="flex-1 px-2 py-2 space-y-0\.5 overflow-y-auto">/)
  assert.match(sidebarSource, /className="pt-2"/)
  assert.match(sidebarSource, /gap: 8/)
  assert.match(sidebarSource, /padding: '6px 10px'/)
  assert.match(sidebarSource, /fontSize: 13/)
  assert.match(sidebarSource, /className="justify-center xl:justify-start"/)
  assert.match(sidebarSource, /<span className="hidden xl:block flex-1 min-w-0">\{entry\.label\}<\/span>/)
  assert.match(sidebarSource, /className="hidden xl:inline-flex"/)
  assert.match(sidebarSource, /entry\.badge > 99 \? '99\+' : entry\.badge/)
})

test('account footer stacks compact controls and restores the wide row at xl', () => {
  assert.match(sidebarSource, /className="px-3 py-2\.5 flex flex-col xl:flex-row items-center gap-2 flex-shrink-0"/)
  assert.match(sidebarSource, /className="w-7 h-7 rounded-full/)
  assert.match(sidebarSource, /className="hidden xl:block flex-1 min-w-0"[\s\S]*?\{userName \|\|/)
  assert.match(sidebarSource, /\{userName \|\| '未登录'\}/)
  assert.match(sidebarSource, /\{roleText \|\| '暂无角色'\}/)
  assert.match(sidebarSource, /navigate\('\/change-password'\)/)
  assert.match(sidebarSource, /title="修改密码"/)
  assert.match(sidebarSource, /onClick=\{onLogout\}/)
  assert.match(sidebarSource, /title="退出登录"/)
})

test('archived project mobile rule follows the stable sidebar class below 768px', () => {
  assert.doesNotMatch(archiveCss, /aside\.w-56/)
  assert.match(
    archiveCss,
    /@media \(max-width: 767px\)[\s\S]*?body:has\(\.project-archive-page\) aside\.app-sidebar \{ display: none; \}/,
  )
})
