import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('shared key task workspace owns both detail entry points', () => {
  const workspace = read('src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx')
  const personal = read('src/pages/MyTaskDetailPage.tsx')
  const management = read('src/components/task-management/KeyTaskExecutionDetailView.tsx')
  const page = read('src/pages/TaskManagementPage.tsx')

  assert.match(workspace, /CurrentProgressCard/)
  assert.match(workspace, /ExecutionPlanTable/)
  assert.match(workspace, /ExecutionTimeline/)
  assert.match(personal, /KeyTaskExecutionWorkspace/)
  assert.match(management, /KeyTaskExecutionWorkspace/)
  assert.match(page, /viewMode === 'execution' && selectedSubTask/)
})

test('key task header keeps owner, collaborators, and plan time on one aligned metadata rail', () => {
  const header = read('src/components/key-task-workspace/KeyTaskHeader.tsx')

  assert.match(header, /function MetaItem/)
  assert.match(header, /aria-label="关键任务元信息"/)
  assert.match(header, /grid items-center gap-3/)
  assert.match(header, /min-h-8/)
  for (const label of ['负责人', '协同人', '计划时间']) {
    assert.match(header, new RegExp(`label=\{?['\"]?${label}`))
  }
})

test('workspace keeps its history scrollable inside the fixed application shell', () => {
  const workspace = read('src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx')

  assert.match(workspace, /<main className="min-h-0 flex-1 overflow-y-auto bg-slate-50">/)
  assert.doesNotMatch(workspace, /<main className="min-h-full bg-slate-50">/)
})

test('execution plan table has approved columns, row click, and no operation column', () => {
  const table = read('src/components/key-task-workspace/ExecutionPlanTable.tsx')
  for (const label of ['任务计划', '状态', '计划事项', '负责人', '协助人', '计划时间', '最新进展']) {
    assert.match(table, new RegExp(label))
  }
  assert.match(table, /onOpen/)
  assert.doesNotMatch(table, />操作</)
  assert.doesNotMatch(table, /%/)
})

test('workspace renders execution state before historical state', () => {
  const workspace = read('src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx')
  const currentIndex = workspace.indexOf('<CurrentProgressCard')
  const planIndex = workspace.indexOf('<ExecutionPlanTable')
  const achievementIndex = workspace.indexOf('<AchievementList')
  const issueIndex = workspace.indexOf('<IssueList')
  const timelineIndex = workspace.indexOf('<ExecutionTimeline')

  assert.ok(currentIndex > -1)
  assert.ok(planIndex > currentIndex)
  assert.ok(achievementIndex > planIndex)
  assert.ok(issueIndex > achievementIndex)
  assert.ok(timelineIndex > issueIndex)
})

test('workspace UI has no key-task fake percentage or subtask execution-plan label', () => {
  const files = [
    'src/pages/MyTaskDetailPage.tsx',
    'src/components/task-management/KeyTaskExecutionDetailView.tsx',
    'src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx',
    'src/components/key-task-workspace/ExecutionPlanTable.tsx',
    'src/components/key-task-workspace/ExecutionPlanDetailDrawer.tsx',
  ]
  const source = files.map(read).join('\n')

  assert.doesNotMatch(source, /整体完成率|预计完成度/)
  assert.doesNotMatch(source, /进行中['\"]?\s*[:=]>?\s*(75|50)/)
  assert.doesNotMatch(source, /子任务/)
})

test('current progress and timeline use authoritative workspace DTOs', () => {
  const api = read('src/api/keyTaskWorkspace.ts')
  const current = read('src/components/key-task-workspace/CurrentProgressCard.tsx')
  const timeline = read('src/components/key-task-workspace/ExecutionTimeline.tsx')

  assert.match(api, /effective_at/)
  assert.match(api, /affects_current_progress/)
  assert.match(current, /当前进展/)
  assert.match(current, /下一步/)
  for (const label of ['推进记录', '全部', '工作提交', '会议纪要', '成果', '问题', '计划变更']) {
    assert.match(timeline, new RegExp(label))
  }
  assert.doesNotMatch(timeline, /related_achievements|work_reports/)
})

test('execution plan drawer reuses DetailDrawer and keeps actions outside table', () => {
  const drawer = read('src/components/key-task-workspace/ExecutionPlanDetailDrawer.tsx')

  assert.match(drawer, /<DetailDrawer/)
  for (const label of ['当前进展', '下一步', '关联成果', '关联问题', '推进记录']) {
    assert.match(drawer, new RegExp(label))
  }
  assert.match(drawer, /编辑计划/)
  assert.match(drawer, /提交更新/)
  assert.match(drawer, /标记完成/)
})
