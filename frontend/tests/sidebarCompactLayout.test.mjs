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

test('sidebar uses the fixed 176px shell width without the legacy width class', () => {
  assert.match(
    sidebarSource,
    /<aside className="w-44 flex-shrink-0 flex flex-col overflow-hidden"/,
  )
  assert.doesNotMatch(sidebarSource, /\bw-56\b/)
})

test('brand header renders only the existing logo or fallback and notification bell', () => {
  assert.doesNotMatch(sidebarSource, /SYSTEM_NAME_CN/)
  assert.match(sidebarSource, /platformName\?: string/)
  assert.doesNotMatch(sidebarSource, /\{platformName\s*\}/)
  assert.match(sidebarSource, /<img src=\{logoUrl\} alt="logo"/)
  assert.match(sidebarSource, /linear-gradient\(135deg,var\(--brand-accent/)
  assert.match(sidebarSource, /<NotificationBell \/>/)
  assert.match(sidebarSource, /className="flex items-center justify-between px-3 h-14 flex-shrink-0"/)
  assert.match(sidebarSource, /height: 32, maxWidth: 90, objectFit: 'contain'/)
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
    'isPrivileged && hasActiveProject',
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
  assert.match(sidebarSource, /<nav className="flex-1 px-2 py-3 space-y-0\.5 overflow-y-auto">/)
  assert.match(sidebarSource, /className="pt-3"/)
  assert.match(sidebarSource, /gap: 8/)
  assert.match(sidebarSource, /padding: '8px 10px'/)
  assert.match(sidebarSource, /fontSize: 13/)
  assert.match(sidebarSource, /<span style=\{\{ flex: 1, minWidth: 0 \}\}>\{entry\.label\}<\/span>/)
  assert.match(sidebarSource, /entry\.badge > 99 \? '99\+' : entry\.badge/)
})

test('account footer retains identity password and logout controls in compact dimensions', () => {
  assert.match(sidebarSource, /className="px-3 py-2\.5 flex items-center gap-2 flex-shrink-0"/)
  assert.match(sidebarSource, /className="w-7 h-7 rounded-full/)
  assert.match(sidebarSource, /\{userName \|\| '未登录'\}/)
  assert.match(sidebarSource, /\{roleText \|\| '暂无角色'\}/)
  assert.match(sidebarSource, /navigate\('\/change-password'\)/)
  assert.match(sidebarSource, /title="修改密码"/)
  assert.match(sidebarSource, /onClick=\{onLogout\}/)
  assert.match(sidebarSource, /title="退出登录"/)
})

test('archived project mobile rule follows the compact sidebar class below 768px', () => {
  assert.doesNotMatch(archiveCss, /aside\.w-56/)
  assert.match(
    archiveCss,
    /@media \(max-width: 767px\)[\s\S]*?body:has\(\.project-archive-page\) aside\.w-44 \{ display: none; \}/,
  )
})
