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
  const { PLAN_TABLE_COLUMNS } = await loadModule('src/components/task-management/planTableColumns.ts')
  assert.deepEqual(PLAN_TABLE_COLUMNS.map((column) => column.key), [
    'wbsCode',
    'workstream',
    'keyTask',
    'deliverable',
    'acceptance',
    'responsible',
    'planTime',
    'status',
    'risk',
    'latestProgress',
    'nextStep',
  ])
  assert.deepEqual(PLAN_TABLE_COLUMNS.map((column) => column.label), [
    'WBS编号',
    '重点工作',
    '关键任务',
    '交付成果',
    '验收标准',
    '负责人',
    '计划时间',
    '状态',
    '风险/问题',
    '最新进展',
    '下一步',
  ])
})

test('plan rows expose stable WBS codes and project-control summaries', async () => {
  const { buildPlanRows } = await loadModule('src/components/task-management/planTableViewModel.ts')
  const { getPlanRowCellValue } = await loadModule('src/components/task-management/planTableColumns.ts')
  const rows = buildPlanRows({ project, tasks, taskSubMap })

  assert.deepEqual(rows.map((row) => row.wbsCode), ['1.1', '1.2', '2'])
  assert.equal(rows[0].workstream, '战略目标分解')
  assert.equal(rows[0].deliverable, '年度经营目标责任书')
  assert.equal(rows[0].acceptance, '年度经营目标责任书经管理层确认')
  assert.equal(rows[0].latestProgress, '已完成第一轮目标核验')
  assert.equal(getPlanRowCellValue(rows[0], 'latestProgress'), '2026-08-24 · 张三\n已完成第一轮目标核验')
  assert.equal(rows[0].nextStep, '提交管理层复核')
  assert.equal(rows[0].risk, '有风险')
  assert.equal(rows[2].wbsCode, '2')
  assert.equal(rows[2].workstream, '经营复盘机制')
})

test('page and export use the project work progress naming and shared schema', () => {
  const page = read('src/pages/TaskManagementPage.tsx')
  const view = read('src/components/task-management/PlanTableViewV2.tsx')
  const exportSource = read('src/utils/exportPlanTableExcel.ts')

  assert.match(page, /项目工作推进表/)
  assert.match(view, /PLAN_TABLE_COLUMNS/)
  assert.match(exportSource, /PLAN_TABLE_COLUMNS/)
  assert.match(exportSource, /getPlanRowCellValue/)
})

test('column layout clamps resized widths and restores canonical widths', async () => {
  const {
    clampPlanTableColumnWidth,
    normalizeStoredPlanTableWidths,
    getDefaultPlanTableWidths,
  } = await loadModule(MODEL_FILE)

  assert.equal(clampPlanTableColumnWidth('wbsCode', 20), 64)
  assert.equal(clampPlanTableColumnWidth('keyTask', 720), 520)
  assert.equal(clampPlanTableColumnWidth('keyTask', 340), 340)
  assert.equal(normalizeStoredPlanTableWidths('{"wbsCode":88,"keyTask":360}').wbsCode, 88)
  assert.deepEqual(normalizeStoredPlanTableWidths('{"unknown":999}'), getDefaultPlanTableWidths())
})

test('column layout hook persists personal widths without changing export columns', () => {
  const source = read(COLUMN_LAYOUT_FILE)
  assert.match(source, /moways\.workProgress\.planColumnWidths/)
  assert.match(source, /PLAN_TABLE_COLUMNS/)
  assert.match(source, /pointermove/)
  assert.match(source, /pointerup/)
  assert.match(source, /clampPlanTableColumnWidth/)
})

test('smart grid exposes zoom and drag-resize controls', () => {
  const viewSource = read(VIEW_FILE)
  const cssSource = read(CSS_FILE)
  assert.match(viewSource, /usePlanTableZoom/)
  assert.match(viewSource, /usePlanTableColumnLayout/)
  assert.match(viewSource, /调整列宽/)
  assert.match(viewSource, /onPointerDown/)
  assert.match(viewSource, /style=\{\{ width:/)
  assert.match(viewSource, /PlanTableToolbar/)
  assert.match(viewSource, /v2-table-scroll/)
  assert.match(cssSource, /resize-handle/)
  assert.doesNotMatch(cssSource, /\.v2-sheet-frame\s*\{[^}]*overflow:\s*hidden/s)
  assert.match(cssSource, /position:\s*sticky/)
})

test('worksheet view exposes spreadsheet selection and row coordinates', () => {
  const viewSource = read(VIEW_FILE)
  const cssSource = read(CSS_FILE)
  assert.match(viewSource, /selectedCellKey/)
  assert.match(viewSource, /v2-cell--active/)
  assert.match(viewSource, /v2-row-number/)
  assert.match(viewSource, /aria-label=\{`\$\{column\.label\}，第\$\{rowIndex \+ 1\}行`\}/)
  assert.match(viewSource, /v2-task-cell/)
  assert.doesNotMatch(viewSource, /v2-task-card/)
  assert.match(viewSource, /onDoubleClick=\{column\.key === 'keyTask' \? \(\) => canClick && openKeyTask\(row\) : undefined\}/)
  assert.doesNotMatch(viewSource, /onClick=\{canClick \? \(\) => openKeyTask\(row\) : undefined\}/)
  assert.match(cssSource, /v2-cell--active/)
  assert.match(cssSource, /v2-row-number/)
  assert.match(cssSource, /v2-freeze-divider/)
  assert.match(cssSource, /overflow-x:\s*auto/)
  assert.match(cssSource, /\.v2-grid td\s*\{[^}]*overflow:\s*hidden/s)
})
