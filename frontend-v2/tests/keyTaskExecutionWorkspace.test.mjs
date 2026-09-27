import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('shared key task workspace remains available from work progress and personal tasks', () => {
  const workspace = read('src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx')
  const personal = read('src/pages/MyTaskDetailPage.tsx')
  const management = read('src/components/task-management/KeyTaskExecutionDetailView.tsx')
  const page = read('src/pages/TaskManagementPage.tsx')

  assert.match(workspace, /CurrentProgressCard/)
  assert.match(workspace, /ExecutionPlanTable/)
  assert.match(workspace, /ExecutionTimeline/)
  assert.match(personal, /KeyTaskExecutionWorkspace/)
  assert.match(management, /KeyTaskExecutionWorkspace/)
  assert.match(page, /selectedSubTask \? \(/)
  assert.doesNotMatch(page, /SHOW_EXECUTION_DETAIL|viewMode === ['"]execution['"]|ExecutionProgressView/)
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

test('key task header uses a white rounded reference card without changing its content rail', () => {
  const header = read('src/components/key-task-workspace/KeyTaskHeader.tsx')

  assert.match(header, /rounded-xl/)
  assert.match(header, /border-slate-200/)
  assert.match(header, /bg-white/)
  assert.doesNotMatch(header, /border-blue-200 bg-blue-50/)
})

test('key task header does not present a placeholder more-actions menu', () => {
  const header = read('src/components/key-task-workspace/KeyTaskHeader.tsx')

  assert.doesNotMatch(header, />更多操作</)
  assert.doesNotMatch(header, /尚无有效任务计划；不会自动完成。/)
})

test('workspace keeps its history scrollable inside the fixed application shell', () => {
  const workspace = read('src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx')

  assert.match(workspace, /<main className="flex-1 min-h-0 overflow-y-auto bg-slate-50">/)
  assert.doesNotMatch(workspace, /<main className="min-h-full bg-slate-50">/)
})

test('workspace owns a flex-safe vertical scroll container', () => {
  const workspace = read('src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx')
  assert.match(workspace, /<main className="flex-1 min-h-0 overflow-y-auto bg-slate-50">/)
})

test('execution plan table has the compact approved columns and row action', () => {
  const table = read('src/components/key-task-workspace/ExecutionPlanTable.tsx')
  for (const label of ['任务计划', '状态', '计划事项', '负责人', '协助人', '时间']) {
    assert.match(table, new RegExp(label))
  }
  assert.match(table, /onOpen/)
  assert.doesNotMatch(table, />操作</)
  assert.doesNotMatch(table, /最新进展/)
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

test('key-task workspace lets authorized users mark and clear a recorded risk', () => {
  const api = read('src/api/keyTaskWorkspace.ts')
  const workspace = read('src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx')
  const header = read('src/components/key-task-workspace/KeyTaskHeader.tsx')

  assert.match(api, /apiPatch/)
  assert.match(api, /setKeyTaskRisk/)
  assert.match(api, /risk_note/)
  assert.match(api, /can_manage_risk/)
  assert.match(workspace, /setKeyTaskRisk/)
  assert.match(workspace, /onChangeRisk/)
  assert.match(header, /有风险/)
  assert.match(header, /标记风险|解除风险/)
  assert.match(header, /can_manage_risk/)
})

test('key-task header aligns its metadata in three desktop columns', () => {
  const header = read('src/components/key-task-workspace/KeyTaskHeader.tsx')

  assert.match(header, /grid[^"']*xl:grid-cols-3/)
  for (const label of ['负责人', '协同人', '计划时间']) {
    assert.match(header, new RegExp(`MetaItem label="${label}"`))
  }
})

test('execution plan drawer reuses DetailDrawer and keeps actions outside table', () => {
  const drawer = read('src/components/key-task-workspace/ExecutionPlanDetailDrawer.tsx')

  assert.match(drawer, /<DetailDrawer/)
  for (const label of ['预期成果', '完成定义', '当前进展', '推进记录']) {
    assert.match(drawer, new RegExp(label))
  }
  assert.match(drawer, /编辑计划/)
  assert.match(drawer, /提交更新/)
  assert.match(drawer, /标记完成/)
})

test('workspace uses the approved reference card hierarchy and empty states', () => {
  const workspace = read('src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx')
  const header = read('src/components/key-task-workspace/KeyTaskHeader.tsx')
  const plan = read('src/components/key-task-workspace/ExecutionPlanTable.tsx')
  const current = read('src/components/key-task-workspace/CurrentProgressCard.tsx')
  const achievements = read('src/components/key-task-workspace/AchievementList.tsx')
  const issues = read('src/components/key-task-workspace/IssueList.tsx')
  const timeline = read('src/components/key-task-workspace/ExecutionTimeline.tsx')
  const context = read('src/components/key-task-workspace/KeyTaskContextCard.tsx')

  assert.match(workspace, /md:grid-cols-2/)
  assert.match(header, /bg-white/)
  assert.match(plan, /添加计划/)
  assert.match(current, /暂无已确认的有效推进事实/)
  assert.match(achievements, /暂无关联成果/)
  assert.match(issues, /暂无关联问题或风险/)
  assert.match(timeline, /暂无已确认的推进记录/)
  assert.match(context, /所属关系/)
})

test('empty execution plan state exposes an add-plan button only to plan managers', () => {
  const plan = read('src/components/key-task-workspace/ExecutionPlanTable.tsx')

  assert.match(plan, /添加计划/)
  assert.match(plan, /onAdd/)
  assert.match(plan, /canManage/)
  assert.match(plan, /<button[^>]*onClick=\{onAdd\}[^>]*>添加计划<\/button>/)
})

test('workspace wires task-plan creation to the current key task permissions and refresh', () => {
  const workspace = read('src/components/key-task-workspace/KeyTaskExecutionWorkspace.tsx')

  assert.match(workspace, /ExecutionPlanCreateDrawer/)
  assert.match(workspace, /getProjectMembers/)
  assert.match(workspace, /can_manage_execution_plans/)
  assert.match(workspace, /onAdd=\{\(\) => setCreatingPlan\(true\)\}/)
  assert.match(workspace, /onCreated=\{refresh\}/)
})
