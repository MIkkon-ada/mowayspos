import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')
const exists = (file) => fs.existsSync(path.join(root, file))

const archiveFiles = [
  'src/pages/ProjectArchivePage.tsx',
  'src/features/project-archive/ProjectArchiveView.tsx',
  'src/features/project-archive/ArchiveSectionNav.tsx',
  'src/features/project-archive/ArchiveTimeline.tsx',
  'src/features/project-archive/ArchiveOverview.tsx',
  'src/features/project-archive/ArchiveProgressSnapshot.tsx',
  'src/features/project-archive/ArchiveAssetsSection.tsx',
  'src/features/project-archive/ArchiveMeetingSection.tsx',
  'src/features/project-archive/ArchiveCloseReviewSection.tsx',
  'src/features/project-archive/ArchiveOperationSection.tsx',
  'src/features/project-archive/projectArchiveViewModel.ts',
  'src/features/project-archive/useProjectArchiveData.ts',
  'src/features/project-archive/projectArchive.css',
]

function readArchiveSources() {
  assert.deepEqual(archiveFiles.filter((file) => !exists(file)), [], 'all archive page modules must exist')
  return archiveFiles.map(read).join('\n')
}

async function loadArchiveViewModel() {
  const source = read('src/features/project-archive/projectArchiveViewModel.ts')
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
}

test('archive detail route inherits RequireAuth without the global project_view capability gate', () => {
  const source = read('src/app/routes.tsx')
  assert.match(source, /const ProjectArchivePage = lazy\(/)
  assert.match(source, /path="\/home"[\s\S]{0,160}<RequireAuth>[\s\S]{0,100}<ProjectLayout/)
  assert.match(source, /path="projects"[\s\S]{0,160}<RequireCapability mode="project_view">[\s\S]{0,120}<ProjectManagementPage/)
  assert.match(source, /path="projects\/:projectId\/archive"\s+element=\{<ProjectArchivePage \/>\}/)
  const archiveRoute = source.match(/<Route\s+path="projects\/:projectId\/archive"[\s\S]*?<ProjectArchivePage \/>[\s\S]*?\/>/)?.[0] ?? ''
  assert.doesNotMatch(archiveRoute, /RequireCapability|mode="project_view"/)
})

test('archived projects enter the archive route while ended projects retain the close drawer', () => {
  const ui = read('src/domain/projectCloseUi.ts')
  const projects = read('src/features/settings/ProjectsMgmtSection.tsx')
  assert.match(ui, /status === 'ended'.*type: 'closeArchiveView'.*label: '查看结束档案'/)
  assert.match(ui, /status === 'archived'.*type: 'projectArchive'.*label: '查看项目档案'/)
  // archived → projectArchive navigates via onOpenArchive (both patterns exist in source)
  assert.match(projects, /'projectArchive'/)
  assert.match(projects, /onOpenArchive/)
  assert.match(projects, /查看项目档案.*onOpenArchive|onOpenArchive.*查看项目档案/)
  // ended/closeArchiveView opens close flow drawer
  assert.match(projects, /'closeArchiveView'/)
  assert.match(projects, /openCloseFlow/)
})

test('archive page exposes all eight scroll sections and no subpage switcher', () => {
  const source = readArchiveSources()
  for (const id of [
    'archive-overview',
    'archive-project-info',
    'archive-progress',
    'archive-assets',
    'archive-meetings',
    'archive-close-review',
    'archive-approvals',
    'archive-operations',
  ]) assert.match(source, new RegExp(`id=["']${id}["']`))
  assert.match(source, /IntersectionObserver/)
  assert.match(source, /behavior: 'smooth'/)
})

test('archive overview declares the exact six compact metrics', () => {
  const source = readArchiveSources()
  for (const label of ['计划周期', '实际周期', '里程碑完成率', '关键任务完成率', '成果交付率', '问题关闭率']) {
    assert.match(source, new RegExp(label))
  }
  assert.match(source, /ARCHIVE_METRIC_LABELS/)
})

test('data hook aggregates every existing project archive source without demo fallback data', () => {
  const source = read('src/features/project-archive/useProjectArchiveData.ts')
  for (const call of [
    'getProject(projectId)',
    'getProjectMembers(projectId)',
    'fetchTasks(projectId)',
    'fetchSubtasksByProject(projectId)',
    'fetchAchievements(projectId)',
    'fetchIssues(projectId)',
    'fetchMeetings(projectId)',
    'fetchUpdates(projectId)',
    'getProjectCloseRequests(projectId)',
  ]) assert.match(source, new RegExp(call.replace(/[()]/g, '\\$&')))
  assert.match(source, /Promise\.allSettled/)
})

test('administrator logs are fetched only for tech admins', () => {
  const source = read('src/features/project-archive/useProjectArchiveData.ts')
  assert.match(source, /currentUser\?\.is_tech_admin/)
  assert.match(source, /fetchTargetLogs\('project', projectId\)/)
  assert.match(source, /currentUser\?\.is_tech_admin[\s\S]{0,240}fetchTargetLogs/)
  assert.doesNotMatch(source, /fetchTargetLogs\('project', projectId\)[\s\S]{0,80}currentUser\?\.is_tech_admin/)
})

test('PDF prints and ZIP remains honestly disabled', () => {
  const source = readArchiveSources()
  assert.match(source, /window\.print\(\)/)
  assert.match(source, /导出档案（PDF）/)
  assert.match(source, /导出原始数据（ZIP）/)
  assert.match(source, /title="原始数据 ZIP 导出尚未接入"/)
  assert.match(source, /disabled/)
})

test('archive page keeps global layout ownership in routes', () => {
  const page = read('src/pages/ProjectArchivePage.tsx')
  const routes = read('src/app/routes.tsx')
  assert.doesNotMatch(page, /Sidebar|ProjectLayout/)
  assert.match(routes, /path="\/home"[\s\S]{0,160}<ProjectLayout/)
})

test('archive page contains no reference-image demo identities', () => {
  const source = readArchiveSources()
  for (const fake of ['智慧门店POS系统升级项目', '张三', '李四', 'PRJ-2024-0004']) assert.doesNotMatch(source, new RegExp(fake))
})

test('archive feature exposes no project write operation', () => {
  const source = readArchiveSources()
  for (const action of ['编辑项目', '申请结束', '取消结束', '审核结束', '归档项目', '恢复项目', '删除项目', '修改成员', '修改任务']) {
    assert.doesNotMatch(source, new RegExp(`>\\s*${action}\\s*<`))
  }
})

test('responsive archive layout switches from three to two to one columns at exact breakpoints', () => {
  const css = read('src/features/project-archive/projectArchive.css')
  assert.match(css, /@media \(min-width:\s*1440px\)[\s\S]*?grid-template-columns:\s*160px minmax\(0,\s*1fr\) 260px/)
  assert.match(css, /@media \(max-width:\s*1439px\)[\s\S]*?grid-template-columns:\s*150px minmax\(0,\s*1fr\)/)
  assert.match(css, /@media \(max-width:\s*1439px\)[\s\S]*?\.archive-timeline-column[\s\S]*?display:\s*none/)
  assert.match(css, /@media \(max-width:\s*767px\)[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)/)
})

test('archive layout contains width guards and only approved local horizontal scrollers', () => {
  const css = read('src/features/project-archive/projectArchive.css')
  assert.match(css, /\.project-archive-page\s*\{[^}]*min-width:\s*0[^}]*max-width:\s*100%[^}]*overflow-x:\s*hidden/)
  for (const selector of [
    '.archive-toolbar',
    '.archive-main-grid',
    '.archive-nav-column',
    '.archive-content-column',
    '.archive-timeline-column',
    '.archive-project-header',
    '.archive-metric-grid',
    '.archive-two-column',
    '.archive-members-card',
    '.archive-progress-card',
    '.archive-card',
  ]) {
    const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    assert.match(css, new RegExp(`${escaped}\\s*\\{[^}]*min-width:\\s*0[^}]*max-width:\\s*100%`), `${selector} must constrain its width`)
  }
  const horizontalScrollRules = [...css.matchAll(/([^{}]+)\{[^{}]*overflow-x:\s*auto/g)].map((match) => match[1].trim())
  assert.ok(horizontalScrollRules.length >= 2)
  assert.ok(horizontalScrollRules.every((selector) => selector.includes('.archive-section-nav-scroll') || selector.includes('.archive-table-scroll')))
})

test('archive page removes visible English design kickers', () => {
  const css = read('src/features/project-archive/projectArchive.css')
  const componentSource = archiveFiles.filter((file) => file.endsWith('.tsx')).map(read).join('\n')
  assert.match(css, /\.archive-section-eyebrow,\s*\.archive-card-kicker\s*\{[^}]*display:\s*none/)
  const englishLabelTags = [...componentSource.matchAll(/<(?:span|p)[^>]*>\s*[A-Z][A-Z &]+\s*<\/(?:span|p)>/g)].map((match) => match[0])
  assert.ok(englishLabelTags.every((tag) => /className="[^"]*(?:archive-section-eyebrow|archive-card-kicker)/.test(tag)))
})

test('archive overview keeps the first four members and uses the compact goal empty state', () => {
  const source = read('src/features/project-archive/ArchiveOverview.tsx')
  assert.match(source, /members\.slice\(0,\s*4\)/)
  assert.match(source, /members\.length\s*>\s*4/)
  assert.match(source, /empty="项目目标未记录"/)
  assert.doesNotMatch(source, /members\.slice\(0,\s*6\)/)
})

test('archive objective status helper distinguishes missing, partial and complete results', async () => {
  const { getArchiveObjectiveStatus } = await loadArchiveViewModel()
  assert.equal(getArchiveObjectiveStatus(null), '未记录')
  assert.equal(getArchiveObjectiveStatus(''), '未记录')
  assert.equal(getArchiveObjectiveStatus('   '), '未记录')
  assert.equal(getArchiveObjectiveStatus('部分完成，后续继续推进'), '部分完成')
  assert.equal(getArchiveObjectiveStatus('核心目标已完成'), '已完成')
})

test('archive operation helper maps real backend action keys', async () => {
  const { getArchiveOperationTitle } = await loadArchiveViewModel()
  const expected = {
    archive_project: '项目归档',
    project_close_request_create: '提交结束申请',
    project_close_request_update: '更新结束材料',
    project_close_request_cancel: '取消结束申请',
    project_close_request_approve: '批准项目结束',
    project_close_request_reject: '退回结束申请',
    create_project: '创建项目',
    dispatch_project: '项目下发',
    kickoff_project: '项目启动',
    update_project: '更新项目资料',
  }
  for (const [action, title] of Object.entries(expected)) assert.equal(getArchiveOperationTitle(action), title)
  assert.equal(getArchiveOperationTitle('future_action'), 'future_action')
})

test('one archive_project log produces one localized archive timeline event', async () => {
  const { buildArchiveTimeline } = await loadArchiveViewModel()
  const timeline = buildArchiveTimeline({
    project: { id: 4, name: '归档项目', status: 'archived' },
    updates: [],
    meetings: [],
    closeRequests: [],
    logs: [{ id: 9, action: 'archive_project', operator: '管理员', created_at: '2026-07-16T08:00:00Z' }],
  })
  const archiveEvents = timeline.filter((event) => event.title.includes('归档'))
  assert.equal(archiveEvents.length, 1)
  assert.equal(archiveEvents[0].title, '项目归档')
  assert.equal(timeline.some((event) => event.title.includes('archive_project')), false)
})
