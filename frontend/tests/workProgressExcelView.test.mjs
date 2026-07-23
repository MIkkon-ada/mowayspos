import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')
const exists = (file) => fs.existsSync(path.join(root, file))

const MODEL_FILE = 'src/components/task-management/planTableViewModel.ts'
const ZOOM_FILE = 'src/components/task-management/usePlanTableZoom.ts'
const TOOLBAR_FILE = 'src/components/task-management/PlanTableToolbar.tsx'
const STATUS_FILE = 'src/components/task-management/PlanTableStatusBar.tsx'
const CSS_FILE = 'src/components/task-management/planTableExcelV2.css'
const VIEW_FILE = 'src/components/task-management/PlanTableViewV2.tsx'
const PAGE_FILE = 'src/pages/TaskManagementPage.tsx'
const EXPORT_FILE = 'src/utils/exportPlanTableExcel.ts'

async function loadViewModel() {
  assert.ok(exists(MODEL_FILE), `${MODEL_FILE} must exist`)
  const source = read(MODEL_FILE)
  const js = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
}

function requireSources(...files) {
  for (const file of files) assert.ok(exists(file), `${file} must exist`)
  return files.map(read).join('\n')
}

const project = {
  id: 7,
  name: '真实项目',
  description: '项目描述',
  objectives: '完成客户数据治理',
  owners: ['项目经理甲'],
}

const tasks = [
  {
    id: 11,
    project_id: 7,
    key_task: '客户资料核验',
    completion_standard: '字段准确率达到 100%',
    key_achievement: '',
    owner: '重点工作负责人甲',
    plan_time: '2026-07-01 至 2026-07-31',
    status: '进行中',
  },
  {
    id: 12,
    project_id: 7,
    key_task: '交付复盘',
    completion_standard: '形成复盘结论',
    key_achievement: '',
    owner: '重点工作负责人乙',
    plan_time: '2026-08-01 至 2026-08-20',
    status: '未开始',
  },
]

const taskSubMap = {
  11: [
    {
      id: 101,
      task_id: 11,
      title: '完成第一轮字段核对',
      assignee: '张三',
      plan_time: '2026-07-01 至 2026-07-10',
      status: '已完成',
      notes: '协助人：李四\n已完成客户字段核对',
    },
    {
      id: 102,
      task_id: 11,
      title: '完成第二轮抽样检查',
      assignee: '王五',
      plan_time: '2026-07-11 至 2026-07-20',
      status: '进行中',
      notes: '协同人：赵六\n正在核验异常字段',
    },
  ],
  12: [],
}

test('work progress defaults to the Excel table and preserves execution detail', () => {
  const source = read(PAGE_FILE)
  assert.match(source, /useState<'execution' \| 'plan'>\('plan'\)/)
  assert.match(source, />\s*表格视图\s*</)
  assert.match(source, />\s*执行详情\s*</)
  assert.match(source, /viewMode === 'execution'/)
  assert.match(source, /data-testid="work-progress-detail-panel"/)
})

test('the executable view model exposes the exact fourteen business columns', async () => {
  const { PLAN_TABLE_BUSINESS_HEADERS } = await loadViewModel()
  assert.deepEqual(PLAN_TABLE_BUSINESS_HEADERS, [
    '目标',
    '重点工作',
    '评价标准',
    '序号',
    '关键任务',
    '责任人',
    '计划开始时间',
    '计划结束时间',
    '协同人',
    '完成情况',
    '备注',
    '项目经理',
    '重点工作计划开始时间',
    '重点工作计划结束时间',
  ])
})

test('buildPlanRows calculates project and task row spans from visible rows', async () => {
  const { buildPlanRows } = await loadViewModel()
  const rows = buildPlanRows({ project, tasks, taskSubMap, searchText: '' })
  assert.equal(rows.length, 3)
  assert.equal(rows[0].showObjective, true)
  assert.equal(rows[0].objectiveRowSpan, 3)
  assert.equal(rows[1].showObjective, false)
  assert.equal(rows[0].showTaskCells, true)
  assert.equal(rows[0].taskRowSpan, 2)
  assert.equal(rows[1].showTaskCells, false)
  assert.equal(rows[2].showTaskCells, true)
  assert.equal(rows[2].taskRowSpan, 1)
  assert.deepEqual(rows.map((row) => row.sequence), [1, 2, 3])
  assert.equal(rows[2].keyTask, '暂无关键任务')
})

test('subtask search retains its parent and recomputes row spans', async () => {
  const { buildPlanRows } = await loadViewModel()
  const rows = buildPlanRows({ project, tasks, taskSubMap, searchText: '第二轮' })
  assert.equal(rows.length, 1)
  assert.equal(rows[0].task.id, 11)
  assert.equal(rows[0].subtask.id, 102)
  assert.equal(rows[0].showObjective, true)
  assert.equal(rows[0].objectiveRowSpan, 1)
  assert.equal(rows[0].showTaskCells, true)
  assert.equal(rows[0].taskRowSpan, 1)
})

test('parent task search retains all of its visible key tasks', async () => {
  const { buildPlanRows } = await loadViewModel()
  const rows = buildPlanRows({ project, tasks, taskSubMap, searchText: '字段准确率' })
  assert.equal(rows.length, 2)
  assert.deepEqual(rows.map((row) => row.subtask.id), [101, 102])
  assert.equal(rows[0].taskRowSpan, 2)
})

test('parseAssistingPerson separates only the supported first-line prefixes', async () => {
  const { parseAssistingPerson } = await loadViewModel()
  assert.deepEqual(parseAssistingPerson('协助人：张三\n完成第一轮核验'), {
    assistingPerson: '张三',
    remainingNotes: '完成第一轮核验',
  })
  assert.deepEqual(parseAssistingPerson('协同人：李四\n等待复核'), {
    assistingPerson: '李四',
    remainingNotes: '等待复核',
  })
  assert.deepEqual(parseAssistingPerson('普通进展说明'), {
    assistingPerson: '—',
    remainingNotes: '普通进展说明',
  })
})

test('zoom helpers clamp persisted values to 50 through 160', async () => {
  const { clampPlanTableZoom, normalizeStoredPlanTableZoom, DEFAULT_PLAN_TABLE_ZOOM } = await loadViewModel()
  assert.equal(clampPlanTableZoom(40), 50)
  assert.equal(clampPlanTableZoom(170), 160)
  assert.equal(clampPlanTableZoom(100), 100)
  assert.equal(normalizeStoredPlanTableZoom(null), 100)
  assert.equal(normalizeStoredPlanTableZoom(''), 100)
  assert.equal(normalizeStoredPlanTableZoom('40'), 50)
  assert.equal(normalizeStoredPlanTableZoom('125'), 125)
  assert.equal(DEFAULT_PLAN_TABLE_ZOOM, 100)
})

test('toolbar, status bar and zoom hook share the required controls', () => {
  const source = requireSources(ZOOM_FILE, TOOLBAR_FILE, STATUS_FILE)
  assert.match(source, /moways\.workProgress\.planZoom/)
  assert.match(source, /适合宽度/)
  assert.match(source, /重置视图/)
  assert.match(source, /type="range"/)
  assert.match(source, /ctrlKey \|\| event\.metaKey/)
  assert.match(source, /INPUT|input/i)
  assert.match(source, /SELECT|select/i)
  assert.match(source, /TEXTAREA|textarea/i)
  assert.match(source, /isContentEditable/)
})

test('V2 table uses scroll workspace with overflow containment', () => {
  const viewSource = requireSources(VIEW_FILE, CSS_FILE)
  // V2 uses v2-table-scroll for workspace with overflow containment
  assert.match(viewSource, /v2-table-scroll|overflow:\s*auto/)
  assert.match(viewSource, /overscroll-behavior:\s*contain/)
  // V2 uses position:sticky for frozen headers (top:0)
  assert.match(viewSource, /position:\s*sticky/)
  assert.match(viewSource, /top:\s*0/)
  // No raw overflow-x-auto on the main container
  assert.doesNotMatch(read(VIEW_FILE), /overflow-x-auto/)
})

test('key-task cells open the existing detail flow without inline editing', () => {
  const source = read(VIEW_FILE)
  // V2 renders key-task cells; subtask detail is opened via parent page callback
  // The table component itself does not contain editing logic
  assert.doesNotMatch(source, /contentEditable/)
  assert.doesNotMatch(source, /onDoubleClick/) // no double-click-to-edit
  // No undo/redo/save-cell operations
  assert.doesNotMatch(source, /撤销|重做|保存单元格/)
  // No CRUD mutations inside the table component itself
  assert.doesNotMatch(source, /createTask|updateTask|deleteTask|createSubTask|updateSubTask/)
})

test('plan export uses the web model, fourteen headers, merges and frozen panes', () => {
  const source = requireSources(EXPORT_FILE)
  assert.match(source, /PLAN_TABLE_BUSINESS_HEADERS/)
  assert.match(source, /buildPlanRows/)
  assert.match(source, /mergeCells/)
  assert.match(source, /xSplit:\s*3/)
  assert.match(source, /ySplit:\s*2/)
  assert.match(source, /工作推进表_/)
  assert.match(source, /row\.keyTask/)
})

test('plan mode loads subtasks before search projection and disables incomplete export', () => {
  const page = read(PAGE_FILE)
  // Plan base tasks loaded before filtering/search
  assert.match(page, /planBaseTasks/)
  assert.match(page, /missingTasks = planBaseTasks\.filter/)
  // Search text passed to plan table
  assert.match(page, /searchText=\{search\}/)
  // Export disabled until all subtasks are loaded
  assert.match(page, /exportDisabled=\{!planTableReady\}/)
  // Loading indicator shown while fetching subtasks (in TaskManagementPage)
  assert.match(page, /关键任务加载中[.]{1,3}/)
  // Subtask detail opened via callback from parent page
  assert.match(page, /openSubDetail|onOpenSubTask/)
})

test('archived plan rendering remains read-only and other global layouts stay out of scope', () => {
  const source = read(VIEW_FILE)
  // V2 has no inline CRUD action buttons for add/edit/delete/archive/restore
  // Note: "编辑" may appear in readonly hint text — that is acceptable
  assert.doesNotMatch(source, /新增[^本]|删除|归档|恢复/)
  assert.equal(exists('src/components/Sidebar.tsx'), true)
  assert.equal(exists('src/layouts/ProjectLayout.tsx'), true)
})

test('V2 layout uses banner + scroll + canvas hierarchy with proper z-ordering', () => {
  const view = read(VIEW_FILE)
  const css = read(CSS_FILE)
  // V2 layout: v2-plan-view > v2-project-banner + v2-table-scroll > v2-table-canvas > v2-grid
  assert.match(view, /v2-plan-view/)
  assert.match(view, /v2-project-banner/)
  assert.match(view, /v2-table-scroll/)
  assert.match(view, /v2-table-canvas/)
  assert.match(view, /v2-grid/)
  const bannerIdx = view.indexOf('v2-project-banner')
  const scrollIdx = view.indexOf('v2-table-scroll')
  const canvasIdx = view.indexOf('v2-table-canvas')
  assert.ok(bannerIdx > -1 && scrollIdx > -1 && canvasIdx > -1, 'all three layers present')
  assert.ok(bannerIdx < scrollIdx, 'banner must precede scroll area')
  assert.ok(scrollIdx < canvasIdx, 'canvas must be inside scroll area')
  assert.doesNotMatch(view, /plan-table-title-cell/)
  assert.doesNotMatch(css, /\.plan-table-title-cell/)
  assert.match(css, /position:\s*sticky/)
})

test('page resolves an archived project detail without falling back to another project', () => {
  const page = read(PAGE_FILE)

  assert.match(page, /import\s*{[^}]*\bgetProject\b[^}]*}\s*from\s*'\.\.\/api\/projects'/s)
  assert.match(page, /resolvedProjectDetail,\s*setResolvedProjectDetail/)
  assert.match(page, /getProject\(effectiveTaskProjectId\)/)
  assert.match(page, /resolvedTaskProjects/)
  assert.match(page, /availableTaskProjects\s*=\s*useMemo\([\s\S]*resolvedTaskProjects/)
  assert.match(page, /resolvedProjectDetail\?\.id\s*===\s*effectiveTaskProjectId/)
  assert.match(page, /focusedProject\s*=\s*projectFromContext\s*\?\?\s*resolvedProjectForContext\s*\?\?\s*null/)
  assert.doesNotMatch(page, /focusedProject\s*=.*projects\[0\]/)
  assert.match(page, /projectForTask\(resolvedTaskProjects,/)
  assert.match(page, /isProjectArchived\(focusedProject\)/)
})

test('archived project details suppress task and subtask write controls', () => {
  const page = read(PAGE_FILE)

  assert.match(page, /subCanEdit\s*=\s*selectedSubTask\s*&&\s*!isProjectArchived\(selectedSubProject\)/)
  assert.match(page, /!selectedTaskArchived\s*&&\s*\(\s*<div className="border-t px-4 py-3 flex gap-2/s)
})
