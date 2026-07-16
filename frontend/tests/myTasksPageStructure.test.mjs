import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')
const exists = (file) => fs.existsSync(path.join(root, file))
const MODEL = 'src/features/my-tasks/myTasksViewModel.ts'

async function loadModel() {
  assert.ok(exists(MODEL), `${MODEL} must exist`)
  const source = read(MODEL)
  const js = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
}

const projects = [
  { id: 1, name: '数字化升级项目', status: 'active', lifecycle_status: 'active' },
  { id: 2, name: 'POS 系统升级项目', status: 'active', lifecycle_status: 'active' },
  { id: 3, name: '已结束项目', status: 'ended', lifecycle_status: 'ended' },
]

function task(id, projectId, status, overrides = {}) {
  return {
    id,
    task_id: 100 + projectId,
    title: `关键任务 ${id}`,
    assignee: '张三',
    plan_time: '2026-07-01 至 2026-07-31',
    status,
    completion_criteria: `完成标准 ${id}`,
    notes: `当前进展 ${id}`,
    parent_key_task: `重点工作 ${projectId}`,
    parent_task_id: 100 + projectId,
    parent_project_id: projectId,
    parent_special_project: projects.find((item) => item.id === projectId)?.name ?? '',
    ...overrides,
  }
}

test('member routes preserve projects and add the personal task center', () => {
  const routes = read('src/app/routes.tsx')
  assert.match(routes, /const MyTasksPage = lazy\(/)
  assert.match(routes, /path="\/member"[\s\S]*?<Route index element=\{<Navigate to="\/member\/tasks" replace \/>\}/)
  assert.match(routes, /path="tasks" element=\{<MyTasksPage \/>\}/)
  assert.match(routes, /path="projects" element=\{<MemberProjectsPage \/>\}/)
  assert.match(routes, /path="projects\/:projectId" element=\{<MemberProjectTasksPage \/>\}/)
})
test('home and legacy mytasks routes enter the new center', () => {
  const routes = read('src/app/routes.tsx')
  assert.match(routes, /isPrivileged \? '\/home\/dashboard' : '\/member\/tasks'/)
  assert.match(routes, /path="mytasks" element=\{<LegacyProjectRedirect to="\/member\/tasks" includeProjectId \/>\}/)
})

test('status normalization covers current and historical values', async () => {
  const { normalizeMyTaskStatus } = await loadModel()
  assert.equal(normalizeMyTaskStatus('not_started'), '未开始')
  assert.equal(normalizeMyTaskStatus('待开始'), '未开始')
  assert.equal(normalizeMyTaskStatus('in_progress'), '进行中')
  assert.equal(normalizeMyTaskStatus('已延期'), '延期')
  assert.equal(normalizeMyTaskStatus('completed'), '已完成')
  assert.equal(normalizeMyTaskStatus('paused'), '暂缓')
})

test('plan time parser supports ranges, single values, ongoing and empty input', async () => {
  const { parseMyTaskPlanTime } = await loadModel()
  assert.deepEqual(parseMyTaskPlanTime('2026-07-01 至 2026-07-31'), {
    start: '2026-07-01', end: '2026-07-31', display: '2026-07-01 ～ 2026-07-31', endTimestamp: Date.parse('2026-07-31T00:00:00'),
  })
  assert.equal(parseMyTaskPlanTime('2026-08-01 ~ 2026-08-20').end, '2026-08-20')
  assert.equal(parseMyTaskPlanTime('2026年7月1日 至 2026年7月31日').end, '2026-07-31')
  assert.equal(parseMyTaskPlanTime('持续').display, '持续')
  assert.equal(parseMyTaskPlanTime('').display, '')
})

test('progress text removes only the first assisting-person line', async () => {
  const { getMyTaskProgressText } = await loadModel()
  assert.equal(getMyTaskProgressText('协助人：李四\n已完成第一轮核验'), '已完成第一轮核验')
  assert.equal(getMyTaskProgressText('协同人: 王五\n等待客户确认'), '等待客户确认')
  assert.equal(getMyTaskProgressText('普通进展内容'), '普通进展内容')
  assert.equal(getMyTaskProgressText(''), '暂无进展记录')
})

test('row mapping keeps only the current assignee and deduplicates by subtask id', async () => {
  const { buildMyTaskRows } = await loadModel()
  const rows = buildMyTaskRows([
    task(1, 1, '进行中'),
    task(1, 1, '进行中'),
    task(2, 1, '未开始', { assignee: '李四' }),
    task(3, 2, '已完成'),
  ], projects, '张三')
  assert.deepEqual(rows.map((row) => row.id), [1, 3])
  assert.equal(rows[0].projectName, '数字化升级项目')
  assert.equal(rows[0].workstreamName, '重点工作 1')
})

test('allSettled merge preserves successful projects and reports failures', async () => {
  const { mergeMyTaskProjectResults } = await loadModel()
  const activeProjects = projects.slice(0, 2)
  const merged = mergeMyTaskProjectResults(activeProjects, [
    { status: 'fulfilled', value: [task(1, 1, '进行中')] },
    { status: 'rejected', reason: new Error('forbidden') },
  ], '张三')
  assert.deepEqual(merged.rows.map((row) => row.id), [1])
  assert.deepEqual(merged.successProjectIds, [1])
  assert.deepEqual(merged.failedProjectIds, [2])
})

test('default sorting follows urgency and then planned end date', async () => {
  const { buildMyTaskRows, sortMyTaskRows } = await loadModel()
  const rows = buildMyTaskRows([
    task(1, 1, '已完成'),
    task(2, 1, '未开始'),
    task(3, 1, '进行中', { plan_time: '2026-08-01 至 2026-08-20' }),
    task(4, 1, '延期'),
    task(5, 1, '暂缓'),
    task(6, 1, '进行中', { plan_time: '2026-08-01 至 2026-08-10' }),
  ], projects, '张三')
  assert.deepEqual(sortMyTaskRows(rows).map((row) => row.id), [4, 6, 3, 2, 5, 1])
})

test('status counts use the complete loaded result', async () => {
  const { buildMyTaskRows, countMyTaskStatuses } = await loadModel()
  const rows = buildMyTaskRows([
    task(1, 1, '未开始'), task(2, 1, '进行中'), task(3, 1, '延期'),
    task(4, 2, '已完成'), task(5, 2, '暂缓'),
  ], projects, '张三')
  assert.deepEqual(countMyTaskStatuses(rows), {
    全部: 5, 未开始: 1, 进行中: 1, 延期: 1, 已完成: 1, 暂缓: 1,
  })
})

test('filters apply status, project and normalized search before sorting', async () => {
  const { buildMyTaskRows, filterMyTaskRows } = await loadModel()
  const rows = buildMyTaskRows([
    task(1, 1, '进行中', { title: '客户字段核验', completion_criteria: '完成 100%', notes: '等待 API 权限' }),
    task(2, 2, '进行中', { title: '门店培训', parent_key_task: '组织赋能' }),
    task(3, 1, '已完成'),
  ], projects, '张三')
  assert.deepEqual(filterMyTaskRows(rows, { status: '进行中', projectId: 1, search: ' api ' }).map((row) => row.id), [1])
  assert.deepEqual(filterMyTaskRows(rows, { status: '全部', projectId: null, search: 'POS 系统' }).map((row) => row.id), [2])
  assert.deepEqual(filterMyTaskRows(rows, { status: '全部', projectId: null, search: '组织赋能' }).map((row) => row.id), [2])
  assert.deepEqual(filterMyTaskRows(rows, { status: '全部', projectId: null, search: '完成 100%' }).map((row) => row.id), [1])
})

test('project options contain only projects represented by loaded tasks', async () => {
  const { buildMyTaskRows, getMyTaskProjectOptions } = await loadModel()
  const rows = buildMyTaskRows([task(1, 2, '进行中')], projects, '张三')
  assert.deepEqual(getMyTaskProjectOptions(rows), [{ id: 2, name: 'POS 系统升级项目' }])
})

test('client pagination returns legal pages and supports 10, 20 and 50 rows', async () => {
  const { paginateMyTaskRows } = await loadModel()
  const rows = Array.from({ length: 28 }, (_, index) => ({ id: index + 1 }))
  assert.deepEqual(paginateMyTaskRows(rows, 1, 10).items.map((row) => row.id), [1,2,3,4,5,6,7,8,9,10])
  assert.equal(paginateMyTaskRows(rows, 4, 10).page, 3)
  assert.equal(paginateMyTaskRows(rows, 1, 20).items.length, 20)
  assert.equal(paginateMyTaskRows(rows, 1, 50).items.length, 28)
})

test('data hook queries each active project with the fixed current user name', () => {
  const hook = read('src/features/my-tasks/useMyTasks.ts')
  assert.match(hook, /projects\.filter\(isProjectActive\)/)
  assert.match(hook, /Promise\.allSettled/)
  assert.match(hook, /fetchSubtasksByAssignee\(currentUser\.name, project\.id\)/)
  assert.doesNotMatch(hook, /fetchSubtasksByAssignee\([^,]+,\s*null\)/)
})

test('details load only inside the drawer and expose no write operation', () => {
  const hook = read('src/features/my-tasks/useMyTasks.ts')
  const page = read('src/pages/MyTasksPage.tsx')
  const drawer = read('src/features/my-tasks/MyTaskDetailDrawer.tsx')
  assert.doesNotMatch(hook, /fetchSubtaskDetail/)
  assert.doesNotMatch(page, /fetchSubtaskDetail/)
  assert.match(drawer, /fetchSubtaskDetail\(row\.id\)/)
  assert.doesNotMatch(drawer, /patchSubTaskStatus|updateSubTask|deleteSubTask|createUpdate/)
  assert.doesNotMatch(drawer, />\s*(?:编辑|删除|修改状态)\s*</)
})

test('table keeps the exact personal-task columns and no unsupported metrics', () => {
  const table = read('src/features/my-tasks/MyTasksTable.tsx')
  for (const column of ['#', '关键任务', '所属项目 / 重点工作', '计划时间', '状态', '当前进展', '操作']) {
    assert.match(table, new RegExp(column.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
  assert.doesNotMatch(table, /成果数量|问题数量|协助任务/)
  assert.doesNotMatch(table, /patchSubTaskStatus|updateSubTask/)
})

test('page has no calendar shortcut and member projects use localized roles', () => {
  const page = read('src/pages/MyTasksPage.tsx')
  const projectsPage = read('src/pages/MemberProjectsPage.tsx')
  assert.doesNotMatch(page, /查看日程/)
  assert.match(projectsPage, /getProjectRoleLabel\(role\)/)
})

test('responsive CSS constrains body overflow and drawer widths', () => {
  const css = read('src/features/my-tasks/myTasks.css')
  assert.match(css, /\.my-tasks-page\s*\{[^}]*overflow-x:\s*hidden/s)
  assert.match(css, /\.my-task-table-scroll\s*\{[^}]*overflow-x:\s*auto/s)
  assert.match(css, /\.my-task-drawer\s*\{[^}]*width:\s*420px/s)
  assert.match(css, /@media \(max-width:\s*1279px\)[\s\S]*?\.my-task-drawer\s*\{[^}]*width:\s*380px/s)
  assert.match(css, /@media \(max-width:\s*899px\)[\s\S]*?\.my-task-drawer\s*\{[^}]*width:\s*100%/s)
})

test('each task row exposes a dedicated detail action beside the overflow menu', () => {
  const table = read('src/features/my-tasks/MyTasksTable.tsx')
  assert.match(table, /className="my-task-row-actions"/)
  assert.match(table, /className="my-task-detail-button"[\s\S]*?>\s*查看详情\s*<\/button>/)
  assert.match(table, /my-task-detail-button[\s\S]*?event\.stopPropagation\(\)[\s\S]*?onOpenDetail\(row\)/)
  assert.match(table, /className="my-task-actions"[\s\S]*?查看工作推进[\s\S]*?提交工作汇报/)
  const menu = table.match(/<div className="my-task-actions-menu">([\s\S]*?)<\/div>/)?.[1] ?? ''
  assert.doesNotMatch(menu, /查看详情/)
})

test('drawer renders complete plan dates and clamps the accessible task title to two lines', () => {
  const drawer = read('src/features/my-tasks/MyTaskDetailDrawer.tsx')
  const css = read('src/features/my-tasks/myTasks.css')
  assert.match(drawer, /className="my-task-detail-plan"/)
  assert.match(drawer, /<span>\{row\.planStart\}<\/span>\s*<span>～<\/span>\s*<span>\{row\.planEnd\}<\/span>/)
  assert.match(drawer, /id="my-task-detail-title"[\s\S]*?title=\{row\.title\}/)
  assert.match(css, /\.my-task-detail-plan\s*\{[^}]*white-space:\s*normal[^}]*overflow-wrap:\s*anywhere/s)
  assert.doesNotMatch(css, /\.my-task-detail-plan\s*\{[^}]*text-overflow:\s*ellipsis/s)
  assert.doesNotMatch(css, /\.my-task-detail-plan\s*\{[^}]*white-space:\s*nowrap/s)
  assert.match(css, /\.my-task-drawer-header h2\s*\{[^}]*-webkit-line-clamp:\s*2/s)
})

test('bottom support area contains three compact panels with the exact help copy', () => {
  const page = read('src/pages/MyTasksPage.tsx')
  const panel = read('src/features/my-tasks/MyTasksHelpPanel.tsx')
  const css = read('src/features/my-tasks/myTasks.css')
  assert.match(page, /<MyTasksHelpPanel\s*\/>/)
  assert.match(panel, />使用说明</)
  for (const copy of [
    '仅展示本人作为责任人的关键任务',
    '协助任务将在后续结构化版本中支持',
    '点击“查看详情”查看任务完整信息',
    '工作汇报请使用“工作汇报”入口',
  ]) assert.match(panel, new RegExp(copy))
  assert.match(css, /\.my-task-bottom-grid\s*\{[^}]*grid-template-columns:\s*1fr 1fr 1fr/s)
  assert.match(css, /@media \(max-width:\s*1279px\)[\s\S]*?\.my-task-bottom-grid\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/s)
  assert.match(css, /@media \(max-width:\s*899px\)[\s\S]*?\.my-task-bottom-grid\s*\{[^}]*grid-template-columns:\s*1fr/s)
})

test('personal task center uses Chinese feature labels only', () => {
  const page = read('src/pages/MyTasksPage.tsx')
  assert.doesNotMatch(page, /PERSONAL WORKSPACE|QUICK ACTIONS/)
  assert.match(page, />个人工作</)
  assert.match(page, />快捷入口</)
})

test('legacy inline write workflow stays removed from the page and feature modules', () => {
  const featureFiles = fs.readdirSync(path.join(root, 'src/features/my-tasks'))
    .filter((name) => /\.(?:ts|tsx)$/.test(name))
    .map((name) => read(`src/features/my-tasks/${name}`))
  const source = [read('src/pages/MyTasksPage.tsx'), ...featureFiles].join('\n')
  assert.doesNotMatch(source, /createUpdate|patchSubTaskStatus|isPendingConfirmation|fetchMyUpdates|TaskUpdateModal/)
  assert.doesNotMatch(source, /<form\b|<textarea\b|更新进展|提交完成|上报问题/)
})
