import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')
const exists = (file) => fs.existsSync(path.join(root, file))

const PAGE = 'src/pages/VoiceUpdatePage.tsx'
const MY_TASKS = 'src/pages/MyTasksPage.tsx'
const TYPES = 'src/features/voice-update/voiceUpdateResultTypes.ts'
const BINDING = 'src/features/voice-update/useVoiceTaskBinding.ts'
const STEPPER = 'src/features/voice-update/VoiceUpdateFlowStepper.tsx'
const BINDING_BAR = 'src/features/voice-update/VoiceUpdateTaskBindingBar.tsx'
const INPUT = 'src/features/voice-update/VoiceUpdateInputPanel.tsx'
const RESULT = 'src/features/voice-update/VoiceUpdateResultCard.tsx'
const REPORTS = 'src/features/voice-update/VoiceUpdateTaskReportsSection.tsx'
const SUBMIT = 'src/features/voice-update/VoiceUpdateSubmitPanel.tsx'
const HISTORY = 'src/features/voice-update/VoiceUpdateHistoryDrawer.tsx'
const HISTORY_PANEL = 'src/features/voice-update/VoiceUpdateHistoryPanel.tsx'
const TASK_DRAWER = 'src/features/voice-update/VoiceUpdateTaskContextDrawer.tsx'
const EXTRACTION = 'src/features/voice-update/useVoiceExtraction.ts'
const SUBMISSION = 'src/features/voice-update/useVoiceSubmission.ts'
const DRAFT = 'src/features/voice-update/useVoiceDraft.ts'
const CSS = 'src/features/voice-update/voiceUpdateFlow.css'
const ROUTES = 'src/app/routes.tsx'

async function loadFlowModel() {
  const source = read(TYPES)
  const js = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
}

async function loadHistoryStatusModel() {
  const source = read(HISTORY)
  const start = source.indexOf('const HISTORY_SYMBOLIC_STATUS')
  const end = source.indexOf('export function VoiceUpdateHistoryDrawer')
  assert.ok(start >= 0 && end > start, 'history status helper must be defined before the drawer component')
  const helperSource = source.slice(start, end)
  const ssStub = `
    const SS = {
      S_NEW: '待确认', S_PENDING_OWNER: '待负责人审核', S_RETURNED: '已打回提交人',
      S_WITHDRAWN: '已撤回', S_PERMANENTLY_REJECTED: '不入库', S_WAITING_COORDINATOR: '已转交统筹人',
      S_COORDINATOR_GIVEN: '统筹人已反馈', S_WAITING_CEO: '待CEO决策', S_CEO_DECIDED: 'CEO已批示',
      S_CONFIRMED: '已入库', S_NEEDS_REVISION: '需修改',
      normalize: (status) => status || '待确认',
      DISPLAY_LABEL: {
        '待确认': '待确认', '待负责人审核': '待审核', '已打回提交人': '已退回', '已撤回': '已撤回',
        '不入库': '不入库', '已转交统筹人': '已转交统筹', '统筹人已反馈': '统筹已反馈',
        '待CEO决策': '待企业教练决策', 'CEO已批示': '企业教练已批示', '已入库': '已入库', '需修改': '需修改',
      },
      STATUS_BADGE_CLASS: { '待负责人审核': 'pending', '已入库': 'confirmed', '已打回提交人': 'returned' },
      RETURNED_TO_SUBMITTER: new Set(['已打回提交人']),
    }
  `
  const js = ts.transpileModule(`${ssStub}\n${helperSource}`, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
}

const selectedTask = {
  id: 108,
  title: '门店基础资料标准化',
  status: '进行中',
  parent_task_id: 17,
  parent_key_task: '数据质量与资料治理',
  parent_project_id: 41,
}

test('work report route remains available at /work/submit', () => {
  assert.match(read(ROUTES), /path="submit"[\s\S]*?<VoiceUpdatePage\s*\/>/)
})

test('flow step model follows the five real page phases', async () => {
  const { getVoiceFlowStep } = await loadFlowModel()
  assert.equal(getVoiceFlowStep('input', null, null), 1)
  assert.equal(getVoiceFlowStep('input', 41, 108), 2)
  assert.equal(getVoiceFlowStep('extracting', 41, 108), 3)
  assert.equal(getVoiceFlowStep('extracted', 41, 108), 4)
  assert.equal(getVoiceFlowStep('submitting', 41, 108), 4)
  assert.equal(getVoiceFlowStep('submitted', 41, 108), 5)
})

test('stepper renders the exact five non-clickable workflow labels', () => {
  assert.ok(exists(STEPPER))
  const source = read(STEPPER)
  for (const label of ['选择任务', '输入内容', 'AI 提取', '人工检查', '提交确认']) assert.match(source, new RegExp(label))
  assert.doesNotMatch(source, /下一步|上一步|onClick/)
})

test('project and key task selectors are both required', () => {
  assert.ok(exists(BINDING_BAR))
  const source = read(BINDING_BAR)
  assert.match(source, /所属项目\s*<span[^>]*>\*<\/span>/)
  assert.match(source, /关键任务\s*<span[^>]*>\*<\/span>/)
})

test('binding hook scopes every voice context request to projectId', () => {
  assert.ok(exists(BINDING))
  const source = read(BINDING)
  assert.match(source, /fetchVoiceContext\(selectedProjectId\)/)
  assert.doesNotMatch(source, /fetchVoiceContext\(\s*\)/)
})

test('page removes the old unscoped global task gate', () => {
  const source = read(PAGE)
  assert.doesNotMatch(source, /fetchVoiceContext\(\s*\)/)
  assert.doesNotMatch(source, /hasSubtasks/)
})

test('URL task preselection accepts only an option from the selected project', async () => {
  const { resolveVoiceTaskPreselection } = await loadFlowModel()
  assert.equal(resolveVoiceTaskPreselection(108, [selectedTask]), 108)
  assert.equal(resolveVoiceTaskPreselection(999, [selectedTask]), null)
  assert.equal(resolveVoiceTaskPreselection(null, [selectedTask]), null)
})

test('page parses projectId and subtaskId from the work-report URL', () => {
  const source = read(PAGE)
  assert.match(source, /searchParams\.get\('projectId'\)/)
  assert.match(source, /searchParams\.get\('subtaskId'\)/)
})

test('MyTasks work-report navigation carries projectId and subtaskId', () => {
  const source = read(MY_TASKS)
  assert.match(source, /\/work\/submit\?projectId=\$\{row\.projectId\}&subtaskId=\$\{row\.id\}/)
})

test('project changes clear the selected key task and stale extraction state', () => {
  const source = `${read(PAGE)}\n${read(BINDING)}`
  assert.match(source, /setSelectedSubtaskId\(null\)/)
  assert.match(source, /resetExtractionState\(\)/)
})

test('task changes also clear stale extraction state', () => {
  const source = `${read(PAGE)}\n${read(BINDING)}`
  assert.match(source, /handleTaskChange|selectTask/)
  assert.match(source, /resetExtractionState\(\)/)
})

test('selected AI context contains exactly one key task', async () => {
  const { buildSelectedVoiceContext } = await loadFlowModel()
  assert.deepEqual(buildSelectedVoiceContext(selectedTask), [selectedTask])
  assert.deepEqual(buildSelectedVoiceContext(null), [])
})

test('AI extraction sends only the selected key task', () => {
  const source = read(EXTRACTION)
  assert.match(source, /user_subtasks:\s*\[selectedTaskContext\]/)
  assert.match(source, /setVoiceSubtasksContext\(\[selectedTaskContext\]\)/)
  assert.doesNotMatch(source, /slice\(0,\s*60\)/)
})

test('progress reports default to the selected key-task ownership', async () => {
  const { bindProgressReportsToTask } = await loadFlowModel()
  const reports = [
    { type: 'progress', matched_subtask_id: 999, matched_subtask_title: '旧任务', completed: '完成' },
    { type: 'new_task', title: '建议任务' },
  ]
  const bound = bindProgressReportsToTask(reports, selectedTask)
  assert.equal(bound[0].matched_subtask_id, 108)
  assert.equal(bound[0].matched_subtask_title, '门店基础资料标准化')
  assert.equal(bound[0].parent_task_id, 17)
  assert.equal(bound[0].parent_key_task, '数据质量与资料治理')
  assert.deepEqual(bound[1], reports[1])
})

test('extraction validation requires project task content active lifecycle and idle media', async () => {
  const { canExtractVoiceUpdate } = await loadFlowModel()
  const valid = { projectId: 41, selectedTaskContext: selectedTask, text: '完成核验', projectActive: true, recording: false, transcribing: false, uploading: false, phase: 'input' }
  assert.equal(canExtractVoiceUpdate(valid), true)
  assert.equal(canExtractVoiceUpdate({ ...valid, projectId: null }), false)
  assert.equal(canExtractVoiceUpdate({ ...valid, selectedTaskContext: null }), false)
  assert.equal(canExtractVoiceUpdate({ ...valid, text: ' ' }), false)
  assert.equal(canExtractVoiceUpdate({ ...valid, projectActive: false }), false)
  assert.equal(canExtractVoiceUpdate({ ...valid, recording: true }), false)
  assert.equal(canExtractVoiceUpdate({ ...valid, phase: 'submitting' }), false)
})

test('missing selected task produces the exact extraction guidance', () => {
  assert.match(read(EXTRACTION), /请先选择本次汇报对应的关键任务。/)
})

test('submission requires a selected key task and preserves explicit ownership edits', () => {
  const source = read(SUBMISSION)
  assert.match(source, /selectedSubtaskId/)
  assert.match(source, /请先选择本次汇报对应的关键任务。/)
  assert.match(source, /e\?\.modified/)
})

test('main result preview exposes five editable fields from taskReports', () => {
  const source = `${read(RESULT)}\n${read(REPORTS)}`
  for (const label of ['本次完成', '下一步计划', '问题与风险', '取得的成果', '任务状态建议']) assert.match(source, new RegExp(label))
  assert.match(source, /setTaskReports/)
  assert.match(source, /<textarea/)
  assert.match(source, /<select/)
})

test('status suggestion offers the five allowed review values without direct status writes', () => {
  const source = `${read(REPORTS)}\n${read(PAGE)}`
  for (const status of ['未开始', '进行中', '延期', '已完成', '暂缓']) assert.match(source, new RegExp(status))
  assert.doesNotMatch(source, /patchSubTaskStatus/)
})

test('input modes are text voice upload in that order and use no emoji', () => {
  const source = read(INPUT)
  const textIndex = source.indexOf("key: 'text'")
  const voiceIndex = source.indexOf("key: 'voice'")
  const uploadIndex = source.indexOf("key: 'upload'")
  assert.ok(textIndex > -1 && textIndex < voiceIndex && voiceIndex < uploadIndex)
  assert.doesNotMatch(source, /🎙️|📻|📝/)
})

test('input panel owns model selection and the AI extraction action', () => {
  const source = read(INPUT)
  assert.match(source, /提取模型/)
  assert.match(source, /'AI 提取'/)
  assert.match(source, /正在提取…/)
  assert.match(source, /推荐/)
  assert.match(source, /onClick=\{onExtract\}/)
})

test('raw report textarea matches the 225px target height with a 5000 character count', () => {
  const source = `${read(INPUT)}\n${read(CSS)}`
  assert.match(source, /maxLength=\{5000\}/)
  assert.match(source, /\{text\.length\}\/5000/)
  assert.match(source, /height:\s*225px/)
  assert.match(source, /min-height:\s*225px/)
})

test('input guidance is compressed to the exact two useful hints', () => {
  const source = read(INPUT)
  assert.match(source, /建议包含：本次完成、下一步计划、问题、成果/)
  assert.match(source, /内容越完整，AI 提取结果越准确/)
  assert.doesNotMatch(source, /本周完成了什么？|形成了什么成果？|当前有什么问题？|下周做什么/)
})

test('fixed footer submits to AI confirmation center and removes the old label', () => {
  const source = `${read(SUBMIT)}\n${read(PAGE)}\n${read(SUBMISSION)}`
  assert.match(source, /提交至 AI 确认中心/)
  assert.doesNotMatch(source, /提交给负责人/)
  assert.match(source, /已提交至 AI 确认中心/)
  assert.match(source, /查看提交记录/)
  assert.doesNotMatch(source, /前往 AI 确认中心/)
  assert.doesNotMatch(source, /\/work\/confirmations\?projectId=/)
})

test('draft payload extends the legacy format with binding and input mode', () => {
  const source = `${read(PAGE)}\n${read(DRAFT)}\n${read(BINDING)}`
  for (const field of ['text', 'provider', 'mode', 'projectId', 'subtaskId']) assert.match(source, new RegExp(field))
  assert.match(source, /try\s*\{[\s\S]*JSON\.parse[\s\S]*catch/)
})

test('clear content keeps project task and provider bindings', () => {
  const source = `${read(PAGE)}\n${read(SUBMIT)}`
  assert.match(source, /resetExtractionState\(\{\s*clearText:\s*true\s*\}\)/)
  assert.doesNotMatch(source, /onClear[\s\S]{0,200}setSelectedProjectId\(null\)/)
  assert.doesNotMatch(source, /onClear[\s\S]{0,200}setSelectedSubtaskId\(null\)/)
})

test('history is a right drawer rather than a persistent main-page panel', () => {
  const source = read(PAGE)
  assert.ok(exists(HISTORY))
  assert.match(source, /<VoiceUpdateHistoryDrawer/)
  assert.doesNotMatch(source, /<VoiceUpdateHistoryPanel/)
  assert.equal(exists(HISTORY_PANEL), true)
})

test('history drawer has search and exact four status filters', () => {
  const source = read(HISTORY)
  assert.match(source, /搜索历史提交/)
  for (const label of ['全部', '审核中', '已退回', '已确认']) assert.match(source, new RegExp(label))
})

test('history uses current-user records across projects and selection opens the existing detail drawer', () => {
  const page = read(PAGE)
  const historyHook = read('src/features/voice-update/useVoiceHistory.ts')
  assert.match(historyHook, /fetchMyUpdates\(\)/)
  assert.doesNotMatch(historyHook, /slice\(0,\s*20\)/)
  assert.match(page, /handleSelectUpdate/)
  assert.match(page, /<VoiceUpdateDetailDrawer/)
})

test('task context drawer is read-only and loads details only on explicit open', () => {
  assert.ok(exists(TASK_DRAWER))
  const source = `${read(BINDING)}\n${read(TASK_DRAWER)}`
  assert.match(source, /fetchSubtaskDetail\(selectedSubtaskId\)/)
  for (const label of ['关键任务名称', '所属项目', '所属重点工作', '责任人', '计划时间', '当前状态', '完成标准', '当前进展', '关联成果', '关联问题']) assert.match(source, new RegExp(label))
  assert.doesNotMatch(source, /patchSubTaskStatus|updateSubTask|deleteSubTask|createUpdate/)
})

test('extraction and submission failures retain user-owned page state', () => {
  const extraction = read(EXTRACTION)
  const submission = read(SUBMISSION)
  assert.match(extraction, /AI 提取失败，请重新尝试。/)
  assert.doesNotMatch(extraction, /catch[\s\S]{0,240}setText\(''\)/)
  assert.match(submission, /catch[\s\S]*setPhase\('extracted'\)/)
  assert.doesNotMatch(submission, /catch[\s\S]{0,240}setTaskReports\(\[\]\)/)
})

test('page state locks binding and input controls while extracting or submitting', () => {
  const source = `${read(PAGE)}\n${read(BINDING_BAR)}\n${read(INPUT)}`
  assert.match(source, /phase === 'extracting'\s*\|\|\s*phase === 'submitting'/)
  assert.match(source, /disabled=\{controlsLocked\}/)
})

test('flow CSS owns internal scrolling responsive columns and body overflow safety', () => {
  const source = read(CSS)
  assert.match(source, /\.voice-update-page\s*\{[^}]*display:\s*flex[^}]*flex-direction:\s*column[^}]*min-height:\s*0[^}]*overflow:\s*hidden/s)
  assert.match(source, /grid-template-columns:\s*minmax\(0,\s*32fr\)\s+minmax\(0,\s*68fr\)/)
  assert.match(source, /@media \(max-width:\s*899px\)[\s\S]*grid-template-columns:\s*1fr/s)
  assert.match(source, /overflow-x:\s*hidden/)
})

test('target visual replica locks the measured desktop vertical rhythm and controls', () => {
  const source = read(CSS)
  assert.match(source, /\.voice-update-header\s*\{[^}]*height:\s*86px/s)
  assert.match(source, /\.voice-update-stepper\s*\{[^}]*height:\s*83px/s)
  assert.match(source, /\.voice-update-binding\s*\{[^}]*height:\s*94px/s)
  assert.match(source, /\.voice-update-workspace\s*\{[^}]*gap:\s*12px/s)
  assert.match(source, /\.voice-update-mode-tabs button\s*\{[^}]*height:\s*44px/s)
  assert.match(source, /\.voice-update-history-drawer\s*\{[^}]*width:\s*292px/s)
})

test('input and result panels expose the target numbered headings and re-extract action', () => {
  const input = read(INPUT)
  const result = read(RESULT)
  assert.match(input, /voice-update-panel-step[^>]*>2</)
  assert.match(input, /<h2>输入内容<\/h2>/)
  assert.match(input, /支持文本、录音、音频文件三种方式/)
  assert.match(result, /voice-update-panel-step[^>]*>3</)
  assert.match(result, /AI 提取结果（预览）/)
  assert.match(result, /重新提取/)
})

test('AI result keeps all five structured fields mounted before extraction', () => {
  const result = read(RESULT)
  const reports = read(REPORTS)
  assert.match(result, /<VoiceUpdateTaskReportsSection/)
  assert.doesNotMatch(result, /\{result\s*&&\s*\([\s\S]*?<VoiceUpdateTaskReportsSection/)
  for (const label of ['本次完成', '下一步计划', '问题与风险', '取得的成果', '任务状态建议']) {
    assert.match(reports, new RegExp(label))
  }
  assert.match(reports, /voice-update-structured-empty/)
  assert.doesNotMatch(result, /voice-update-result-empty[^>]*><strong>\{emptyMessage\}/)
})

test('task status suggestion uses the five target radio options', () => {
  const source = read(REPORTS)
  assert.match(source, /type="radio"/)
  assert.match(source, /primary\s*\?\s*'voice-update-status'/)
  for (const status of ['未开始', '进行中', '延期', '已完成', '暂缓']) assert.match(source, new RegExp(status))
})

test('footer owns a fixed action bar and the target confirmation note', () => {
  const submit = read(SUBMIT)
  const css = read(CSS)
  assert.match(submit, /voice-update-footer-bar/)
  assert.match(submit, /voice-update-footer-note/)
  assert.match(submit, /提交后将进入 AI 确认中心/)
  assert.match(css, /\.voice-update-footer-bar\s*\{[^}]*height:\s*77px/s)
  assert.match(css, /\.voice-update-footer-note\s*\{[^}]*height:\s*39px/s)
})

test('scope leaves Sidebar ConfirmPage and backend untouched by page imports', () => {
  const source = read(PAGE)
  assert.doesNotMatch(source, /Sidebar|ConfirmPage|patchSubTaskStatus/)
})

test('URL project detail resolves an archived project outside the context list without fallback', () => {
  const source = read(PAGE)
  assert.match(source, /import\s*\{\s*getProject\s*\}\s*from\s*'\.\.\/api\/projects'/)
  assert.match(source, /getProject\(requestedProjectId\)/)
  assert.match(source, /resolvedProjectDetail/)
  assert.match(source, /pageProjects/)
  assert.doesNotMatch(source, /requestedProjectId[\s\S]{0,240}projects\[0\]/)
})

test('page project collection deduplicates the resolved project and drives all project display state', () => {
  const source = read(PAGE)
  assert.match(source, /new Map[\s\S]{0,260}resolvedProjectDetail/)
  assert.match(source, /pageProjects\.filter\(isProjectActive\)/)
  assert.match(source, /pageProjects\.find\(\(project\) => project\.id === selectedProjectId\)/)
  assert.match(source, /projects:\s*pageProjects/)
})

test('non-active project disables task context loading and shows a lifecycle-specific task option', () => {
  const hook = read(BINDING)
  const page = read(PAGE)
  const bar = read(BINDING_BAR)
  assert.match(hook, /enabled:\s*boolean/)
  assert.match(hook, /if\s*\(!selectedProjectId\s*\|\|\s*!enabled\)/)
  assert.match(hook, /taskError[\s\S]{0,120}null/)
  assert.match(page, /enabled:\s*selectedProjectIsActive/)
  assert.match(bar, /非执行项目不可提交汇报/)
  assert.match(bar, /disabled=\{controlsLocked\s*\|\|\s*!selectedProjectIsActive/)
})

test('active project context remains project-scoped and is requested only from the enabled branch', () => {
  const source = read(BINDING)
  assert.equal((source.match(/fetchVoiceContext\(selectedProjectId\)/g) ?? []).length, 1)
  assert.match(source, /if\s*\(!selectedProjectId\s*\|\|\s*!enabled\)[\s\S]*return[\s\S]*fetchVoiceContext\(selectedProjectId\)/)
})

test('history symbolic statuses map to canonical labels and unknown symbolic values fail safely', async () => {
  const { normalizeHistoryStatus } = await loadHistoryStatusModel()
  assert.deepEqual(normalizeHistoryStatus('S_PENDING_OWNER'), { status: '待负责人审核', label: '待审核', badgeClass: 'pending' })
  assert.deepEqual(normalizeHistoryStatus('S_CONFIRMED'), { status: '已入库', label: '已入库', badgeClass: 'confirmed' })
  assert.deepEqual(normalizeHistoryStatus('S_RETURNED'), { status: '已打回提交人', label: '已退回', badgeClass: 'returned' })
  assert.equal(normalizeHistoryStatus('S_FUTURE_UNKNOWN').label, '状态未识别')
})

test('history UI uses normalized display state and never renders symbolic status as its fallback', () => {
  const source = read(HISTORY)
  assert.match(source, /normalizeHistoryStatus\(item\.confirm_status\)/)
  assert.doesNotMatch(source, /DISPLAY_LABEL\[status\]\s*\?\?\s*item\.confirm_status/)
  assert.doesNotMatch(source, />\{item\.confirm_status\}<\/em>/)
})
