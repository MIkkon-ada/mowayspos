import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'

const root = path.resolve(import.meta.dirname, '..')
const MODEL_FILE = 'src/components/task-management/planTableViewModel.ts'
const COLUMN_LAYOUT_FILE = 'src/components/task-management/usePlanTableColumnLayout.ts'
const VIEW_FILE = 'src/components/task-management/PlanTableViewV2.tsx'
const CSS_FILE = 'src/components/task-management/planTableExcelV2.css'

function read(file) {
  return fs.readFileSync(path.join(root, file), 'utf8')
}

function toDataUrl(source) {
  const js = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  }).outputText
  return `data:text/javascript;base64,${Buffer.from(js).toString('base64')}`
}

async function loadModule(file) {
  let source = read(file)
  if (file.endsWith('planTableViewModel.ts')) {
    const columnsUrl = toDataUrl(read('src/components/task-management/planTableColumns.ts'))
    source = source.replace("from './planTableColumns'", `from '${columnsUrl}'`)
  }
  return import(toDataUrl(source))
}

const project = {
  id: 7,
  name: '示例制造企业经营提升项目',
  objectives: '完成年度经营目标分解',
  owners: ['项目经理'],
}

const tasks = [
  {
    id: 11,
    project_id: 7,
    key_task: '战略目标分解',
    key_achievement: '年度经营目标责任书',
    completion_standard: '管理层确认年度目标',
    owner: '项目经理',
    plan_time: '2026-07-01 至 2026-07-31',
    status: '进行中',
  },
  {
    id: 12,
    project_id: 7,
    key_task: '经营复盘机制',
    key_achievement: '季度经营复盘机制',
    completion_standard: '完成季度复盘会议',
    owner: '运营负责人',
    plan_time: '2026-08-01 至 2026-08-20',
    status: '未开始',
  },
]

const taskSubMap = {
  11: [
    {
      id: 101,
      task_id: 11,
      title: '完成经营目标初稿',
      assignee: '张三',
      plan_time: '2026-07-01 至 2026-07-10',
      status: '进行中',
      completion_criteria: '年度经营目标责任书经管理层确认',
      notes: '协同人：李四',
      has_risk: true,
      latest_confirmed_submission: {
        id: 9,
        submitter: '张三',
        confirmed_at: '2026-08-24T09:00:00',
        summary: '已完成第一轮目标核验',
      },
      latest_next_step: '提交管理层复核',
    },
    {
      id: 102,
      task_id: 11,
      title: '完成目标责任书确认',
      assignee: '王五',
      plan_time: '2026-07-11 至 2026-07-20',
      status: '未开始',
      completion_criteria: '责任人完成签字确认',
      notes: '',
    },
  ],
  12: [],
}

test('shared columns describe the same project work progress fields for web and Excel', async () => {
  const { PLAN_TABLE_COLUMNS, PLAN_TABLE_OPTIONAL_COLUMNS, getPlanTableColumnGroups } = await loadModule('src/components/task-management/planTableColumns.ts')
  assert.deepEqual(PLAN_TABLE_COLUMNS.map((column) => column.key), [
    'workstream',
    'keyTask',
    'acceptance',
    'responsible',
    'planTime',
    'status',
    'risk',
    'latestProgress',
    'nextStep',
  ])
  assert.deepEqual(PLAN_TABLE_COLUMNS.map((column) => column.label), [
    '重点工作',
    '关键任务',
    '验收标准',
    '负责人',
    '计划时间',
    '状态',
    '风险/问题',
    '最新进展',
    '下一步',
  ])
  assert.deepEqual(getPlanTableColumnGroups(PLAN_TABLE_COLUMNS).map((group) => [group.key, group.label, group.columns.length]), [
    ['structure', '工作结构', 2],
    ['planning', '计划与验收', 3],
    ['tracking', '推进跟进', 4],
  ])
  assert.deepEqual(PLAN_TABLE_OPTIONAL_COLUMNS.map((column) => column.key), ['expectedOutcome', 'goal', 'boweiRole'])
})

test('plan rows expose project-control summaries without a WBS number column', async () => {
  const { buildPlanRows } = await loadModule('src/components/task-management/planTableViewModel.ts')
  const { getPlanRowCellValue } = await loadModule('src/components/task-management/planTableColumns.ts')
  const rows = buildPlanRows({ project, tasks, taskSubMap })

  assert.equal(rows[0].workstream, '战略目标分解')
  assert.equal(rows[0].deliverable, '年度经营目标责任书')
  assert.equal(rows[0].acceptance, '年度经营目标责任书经管理层确认')
  assert.equal(rows[0].latestProgress, '已完成第一轮目标核验')
  assert.equal(getPlanRowCellValue(rows[0], 'latestProgress'), '2026-08-24 · 张三\n已完成第一轮目标核验')
  assert.equal(rows[0].nextStep, '提交管理层复核')
  assert.equal(rows[0].risk, '有风险')
  assert.equal(rows[2].workstream, '经营复盘机制')
})

test('work progress quick filters scope delayed, risky, and issue-linked key tasks', async () => {
  const { buildPlanRows } = await loadModule(MODEL_FILE)
  const map = {
    ...taskSubMap,
    11: [
      { ...taskSubMap[11][0], has_risk: true },
      { ...taskSubMap[11][1], status: '延期', is_overdue: true },
    ],
  }

  assert.deepEqual(buildPlanRows({ project, tasks, taskSubMap: map, quickFilter: 'risk' }).map((row) => row.subtask?.id), [101])
  assert.deepEqual(buildPlanRows({ project, tasks, taskSubMap: map, quickFilter: 'overdue' }).map((row) => row.subtask?.id), [102])
  assert.deepEqual(buildPlanRows({ project, tasks, taskSubMap: map, quickFilter: 'issues', issueTaskIds: new Set([12]), issueSubtaskIds: new Set([101]) }).map((row) => row.subtask?.id), [101, undefined])
})

test('work progress overview counts key task status and only real open issues', async () => {
  const { buildPlanRows, summarizeWorkProgress } = await loadModule(MODEL_FILE)
  const rows = buildPlanRows({ project, tasks, taskSubMap: {
    ...taskSubMap,
    11: [
      { ...taskSubMap[11][0], has_risk: true },
      { ...taskSubMap[11][1], status: '延期', is_overdue: true },
    ],
  } })
  const summary = summarizeWorkProgress(rows, [
    { id: 1, project_id: 7, status: '待处理' },
    { id: 2, project_id: 7, status: '待负责人确认' },
    { id: 3, project_id: 7, status: '已解决' },
    { id: 4, project_id: 7, status: '已关闭' },
  ])

  assert.deepEqual(summary, { total: 2, completed: 0, delayed: 1, risky: 1, dateToConfirm: 2, openIssues: 2 })
})

test('unknown plan dates are marked and filtered separately from overdue work', async () => {
  const { buildPlanRows, summarizeWorkProgress } = await loadModule(MODEL_FILE)
  const subtasks = {
    11: [
      { ...taskSubMap[11][0], status: '进行中', due_kind: 'unknown', due_date: null, due_label: '7.3—7.10', is_overdue: false },
      { ...taskSubMap[11][1], status: '进行中', due_kind: 'fuzzy', due_date: null, due_label: '7月中旬', is_overdue: false },
    ],
    12: [{ id: 103, task_id: 12, title: '已完成事项', status: '已完成', due_kind: 'unknown', due_date: null }],
  }
  const rows = buildPlanRows({ project, tasks, taskSubMap: subtasks })
  const summary = summarizeWorkProgress(rows, [])

  assert.deepEqual(rows[0].statusMarkers.map((marker) => marker.kind), ['risk', 'date_unknown'])
  assert.deepEqual(buildPlanRows({ project, tasks, taskSubMap: subtasks, quickFilter: 'date_unknown' }).map((row) => row.subtask?.id), [101, 102])
  assert.deepEqual(summary, { total: 3, completed: 1, delayed: 0, risky: 1, dateToConfirm: 2, openIssues: 0 })
})

test('mobile task cards reuse the plan table search and filters without duplicating parent tasks', async () => {
  const { buildMobileTaskList } = await loadModule(MODEL_FILE)
  const result = buildMobileTaskList({ project, tasks, taskSubMap, searchText: '张三' })

  assert.deepEqual(result.tasks.map((task) => task.id), [11])
  assert.deepEqual(result.subTasksByTaskId[11].map((subtask) => subtask.id), [101])
  const riskFiltered = buildMobileTaskList({ project, tasks, taskSubMap, quickFilter: 'risk' })
  assert.deepEqual(riskFiltered.subTasksByTaskId[11].map((subtask) => subtask.id), [101])
})

test('page and export use the project work progress naming and shared schema', () => {
  const page = read('src/pages/TaskManagementPage.tsx')
  const view = read('src/components/task-management/PlanTableViewV2.tsx')
  const exportSource = read('src/utils/exportPlanTableExcel.ts')

  assert.match(page, /项目工作推进表/)
  assert.match(view, /buildPlanRows/)
  assert.match(exportSource, /PLAN_TABLE_COLUMNS/)
  assert.match(exportSource, /getPlanRowCellValue/)
})

test('project selector writes its selection to the URL and retains other route filters', () => {
  const page = read('src/pages/TaskManagementPage.tsx')
  assert.ok(/const \[searchParams, setSearchParams\] = useSearchParams\(\)/.test(page), 'page must be able to update the route query')
  assert.ok(/parseWorkProgressProjectId\(searchParams\)/.test(page), 'project data scope must derive from the route')
  assert.ok(/setSearchParams\(updateWorkProgressProjectQuery\(searchParams, name\)\)/.test(page), 'project selection must navigate to the selected scope')
})

test('work progress project query parses a selected project and preserves other filters on change', async () => {
  const { parseWorkProgressProjectId, updateWorkProgressProjectQuery } = await loadModule('src/components/task-management/workProgressProjectQuery.ts')
  const original = new URLSearchParams('projectId=2&status=延期')

  assert.equal(parseWorkProgressProjectId(original), 2)
  const selected = updateWorkProgressProjectQuery(original, '3')
  assert.equal(parseWorkProgressProjectId(selected), 3)
  assert.equal(selected.get('status'), '延期')

  const cleared = updateWorkProgressProjectQuery(selected, '')
  assert.equal(parseWorkProgressProjectId(cleared), null)
  assert.equal(cleared.get('status'), '延期')
  assert.equal(parseWorkProgressProjectId(new URLSearchParams('projectId=abc')), null)
})

test('column layout clamps resized widths and restores canonical widths', async () => {
  const {
    clampPlanTableColumnWidth,
    normalizeStoredPlanTableWidths,
  } = await loadModule(MODEL_FILE)

  assert.equal(clampPlanTableColumnWidth('keyTask', 720), 520)
  assert.equal(clampPlanTableColumnWidth('keyTask', 340), 340)
  assert.equal(normalizeStoredPlanTableWidths('{"keyTask":360}').keyTask, 360)
  assert.deepEqual(normalizeStoredPlanTableWidths('{"wbsCode":88,"unknown":999}'), {})
})

test('column layout hook persists personal widths without changing export columns', () => {
  const source = read(COLUMN_LAYOUT_FILE)
  assert.match(source, /moways\.workProgress\.planColumnWidths/)
  assert.match(source, /PLAN_TABLE_COLUMNS/)
  assert.match(source, /pointermove/)
  assert.match(source, /pointerup/)
  assert.match(source, /clampPlanTableColumnWidth/)
})
