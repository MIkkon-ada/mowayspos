import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

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

test('archive detail route is lazy, nested under ProjectLayout and protected by project_view', () => {
  const source = read('src/app/routes.tsx')
  assert.match(source, /const ProjectArchivePage = lazy\(/)
  assert.match(source, /path="projects\/:projectId\/archive"[\s\S]{0,240}<RequireCapability mode="project_view">[\s\S]{0,160}<ProjectArchivePage/)
})

test('archived projects enter the archive route while ended projects retain the close drawer', () => {
  const ui = read('src/domain/projectCloseUi.ts')
  const projects = read('src/features/settings/ProjectsMgmtSection.tsx')
  assert.match(ui, /status === 'ended'.*type: 'closeArchiveView'.*label: '查看结束档案'/)
  assert.match(ui, /status === 'archived'.*type: 'projectArchive'.*label: '查看项目档案'/)
  assert.match(projects, /mainAction\.type === 'projectArchive'[\s\S]{0,160}navigate\(`\/home\/projects\/\$\{project\.id\}\/archive`\)/)
  assert.match(projects, /mainAction\.type === 'closeArchiveView'[\s\S]{0,120}openCloseFlow\(project\)/)
  assert.match(projects, /status === 'archived'[\s\S]{0,160}onOpenArchive[\s\S]{0,160}>查看项目档案</)
  assert.doesNotMatch(projects, /status === 'archived'[\s\S]{0,160}onOpenCloseFlow/)
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
