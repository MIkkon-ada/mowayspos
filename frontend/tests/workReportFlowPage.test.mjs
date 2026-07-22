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
  assert.equal(getVoiceFlowStep('input', false), 1)
  assert.equal(getVoiceFlowStep('input', true), 2)
  assert.equal(getVoiceFlowStep('extracting', true), 3)
  assert.equal(getVoiceFlowStep('extracted', true), 4)
  assert.equal(getVoiceFlowStep('submitting', true), 5)
  assert.equal(getVoiceFlowStep('submitted', true), 5)
})

test('stepper renders the exact five non-clickable workflow labels', () => {
  assert.ok(exists(STEPPER))
  const source = read(STEPPER)
  for (const label of ['汇报范围', '输入内容', 'AI 提取', '人工检查', '提交确认', '完成']) assert.match(source, new RegExp(label))
  assert.match(source, /phase === 'submitted'\s*\?\s*'完成'\s*:\s*'提交确认'/)
  assert.doesNotMatch(source, /下一步|上一步|onClick/)
})

test('project and key task selectors are required only in task scope', () => {
  assert.ok(exists(BINDING_BAR))
  const source = read(BINDING_BAR)
  assert.match(source, /scope !== 'all'/)
  assert.match(source, /scope === 'task'/)
  assert.match(source, /关键任务\s*<span[^>]*>\*<\/span>/)
})

test('binding hook supports global and project-scoped voice context requests', () => {
  assert.ok(exists(BINDING))
  const source = read(BINDING)
  assert.match(source, /fetchVoiceContext\(scope === 'all' \? undefined : selectedProjectId\)/)
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

test('AI extraction sends the active scope candidate pool', () => {
  const source = read(EXTRACTION)
  assert.match(source, /user_subtasks:\s*voiceCandidates/)
  assert.match(source, /setVoiceSubtasksContext\(voiceCandidates\)/)
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

test('empty candidate scope produces explicit extraction guidance', () => {
  assert.match(read(EXTRACTION), /当前范围内暂无可汇报工作，请调整汇报范围。/)
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

test('raw report textarea uses the expanded compact-layout height with a 5000 character count', () => {
  const source = `${read(INPUT)}\n${read(CSS)}`
  assert.match(source, /maxLength=\{5000\}/)
  assert.match(source, /\{text\.length\}\/5000/)
  assert.match(source, /height:\s*240px/)
  assert.match(source, /min-height:\s*240px/)
})

test('input guidance is compressed to the exact two useful hints', () => {
  const source = read(INPUT)
  assert.match(source, /建议包含：本次完成、下一步计划、问题、成果/)
  assert.match(source, /内容越完整，AI 提取结果越准确/)
  assert.doesNotMatch(source, /本周完成了什么？|形成了什么成果？|当前有什么问题？|下周做什么/)
})

test('successful submission opens personal history instead of AI confirmation center', () => {
  const source = `${read(SUBMIT)}\n${read(PAGE)}\n${read(SUBMISSION)}`
  assert.match(source, /提交至 AI 确认中心/)
  assert.match(source, /已提交至 AI 确认中心/)
  assert.match(source, /查看提交记录/)
  assert.match(source, /setHistoryOpen\(true\)/)
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
  assert.match(source, /搜索历史提交内容/)
  for (const label of ['全部', '审核中', '已退回', '已确认']) assert.match(source, new RegExp(label))
  assert.doesNotMatch(source, /'草稿'\s*\|\s*'已提交'/)
})

test('history loads all personal submissions and selection opens the existing detail drawer', () => {
  const page = read(PAGE)
  const historyHook = read('src/features/voice-update/useVoiceHistory.ts')
  assert.match(historyHook, /fetchMyUpdates\(\)/)
  assert.doesNotMatch(historyHook, /fetchUpdates\(projectId\)/)
  assert.doesNotMatch(historyHook, /if \(!projectId\)[\s\S]*setHistory\(\[\]\)[\s\S]*return/)
  assert.match(page, /handleSelectUpdate/)
  assert.match(page, /<VoiceUpdateDetailDrawer/)
})

test('history groups cross-project children by batch while keeping legacy rows separate', () => {
  const source = read(HISTORY)
  assert.match(source, /export function groupHistorySubmissions/)
  assert.match(source, /item\.batch_id\s*\?\?\s*`legacy-\$\{item\.id\}`/)
  assert.match(source, /跨项目汇报/)
  assert.match(source, /个项目/)
  assert.match(source, /onSelectUpdate\(item\.id\)/)
})

test('returned batch child restarts only its own project and evidence', () => {
  const page = read(PAGE)
  const detail = read('src/features/voice-update/VoiceUpdateDetailDrawer.tsx')
  assert.match(detail, /onRestartFromSubmission\(detailItem\)/)
  assert.match(page, /setReportScope\('project'\)/)
  assert.match(page, /setSelectedProjectId\(detailItem\.project_id\)/)
  assert.match(page, /task_reports/)
})

test('batch aggregate status prioritizes returned, then all confirmed, otherwise reviewing', () => {
  const source = read(HISTORY)
  assert.match(source, /some\(\(status\)\s*=>\s*SS\.RETURNED_TO_SUBMITTER\.has\(status\)\)/)
  assert.match(source, /every\(\(status\)\s*=>\s*SS\.CONFIRMED_AND_STORED\.has\(status\)\)/)
  assert.match(source, /审核中/)
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
  assert.match(source, /grid-template-columns:\s*minmax\(0,\s*40fr\)\s+minmax\(0,\s*60fr\)/)
  assert.match(source, /@media \(max-width:\s*899px\)[\s\S]*grid-template-columns:\s*1fr/s)
  assert.match(source, /overflow-x:\s*hidden/)
})

test('target visual replica uses one compact header and keeps existing controls', () => {
  const source = read(CSS)
  assert.match(source, /\.voice-update-header\s*\{[^}]*grid-template-columns:\s*auto minmax\(0,\s*1fr\) auto/s)
  assert.match(source, /\.voice-update-header\s*\{[^}]*min-height:\s*72px/s)
  assert.match(source, /\.voice-update-binding\s*\{[^}]*border:\s*0|\.voice-update-binding\s*\{[^}]*min-width:\s*0/s)
  assert.match(source, /\.voice-update-workspace\s*\{[^}]*gap:\s*0/s)
  assert.match(source, /\.voice-update-mode-tabs button\s*\{[^}]*height:\s*40px/s)
  assert.match(source, /\.voice-update-history-drawer\s*\{[^}]*width:\s*292px/s)
})

test('input and result panels expose plain headings and the re-extract action', () => {
  const input = read(INPUT)
  const result = read(RESULT)
  assert.match(input, /<h2>输入内容<\/h2>/)
  assert.doesNotMatch(input, /voice-update-panel-step/)
  assert.doesNotMatch(result, /voice-update-panel-step/)
  assert.match(result, /AI 提取结果/)
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
  assert.match(source, /name=\{`voice-update-status-\$\{index\}`\}/)
  for (const status of ['未开始', '进行中', '延期', '已完成', '暂缓']) assert.match(source, new RegExp(status))
  assert.doesNotMatch(source, /status_update\s*\|\|\s*['"]进行中['"]/)
})

test('footer owns one compact action row with the target confirmation note', () => {
  const submit = read(SUBMIT)
  const css = read(CSS)
  assert.match(submit, /voice-update-footer-bar/)
  assert.match(submit, /voice-update-footer-note/)
  assert.match(submit, /提交后将进入 AI 确认中心/)
  assert.match(css, /\.voice-update-footer-bar\s*\{[^}]*height:\s*56px/s)
  assert.match(css, /\.voice-update-footer-note\s*\{[^}]*flex:\s*1 1 auto/s)
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
  assert.match(hook, /scope !== 'all' && !selectedProjectId/)
  assert.match(hook, /taskError[\s\S]{0,120}null/)
  assert.match(page, /enabled:\s*reportScope === 'all' \|\| selectedProjectIsActive/)
  assert.match(bar, /非执行项目不可提交汇报/)
  assert.match(bar, /disabled=\{controlsLocked\s*\|\|\s*!selectedProjectIsActive/)
})

test('active project and all-work contexts share one scope-aware request', () => {
  const source = read(BINDING)
  assert.equal((source.match(/fetchVoiceContext\(scope === 'all' \? undefined : selectedProjectId\)/g) ?? []).length, 1)
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

test('cross-project report defaults to all work and preserves optional scopes', () => {
  const page = read(PAGE)
  const bar = read(BINDING_BAR)
  assert.match(page, /useState<VoiceReportScope>\('all'\)/)
  for (const label of ['我的全部工作', '指定项目', '指定关键任务']) assert.match(bar, new RegExp(label))
  assert.match(bar, /scope !== 'all'\s*&&\s*selectedTaskContext/)
  assert.doesNotMatch(bar, /selectedTaskContext\?\.plan_time\s*\|\|\s*['"]—['"]/)
})

test('all-work scope loads unscoped voice context and allows extraction without project selection', () => {
  const page = read(PAGE)
  const binding = read(BINDING)
  const extraction = read(EXTRACTION)
  assert.match(binding, /fetchVoiceContext\(scope === 'all' \? undefined : selectedProjectId\)/)
  assert.match(page, /projectActive:\s*reportScope === 'all' \|\| selectedProjectIsActive/)
  assert.doesNotMatch(extraction, /请先选择所属项目，.*AI 提取/)
  assert.doesNotMatch(extraction, /请先选择本次汇报对应的关键任务/)
})

test('extraction sends the complete selected candidate pool to the Agent', () => {
  const source = read(EXTRACTION)
  assert.match(source, /user_subtasks:\s*voiceCandidates/)
  assert.match(source, /setVoiceSubtasksContext\(voiceCandidates\)/)
  assert.match(source, /report_scope:\s*reportScope/)
})

test('single-task deep links remain supported as task scope preselection', () => {
  const page = read(PAGE)
  assert.match(page, /requestedProjectId/)
  assert.match(page, /requestedSubtaskId/)
  assert.match(page, /setReportScope\('task'\)/)
})

test('draft cards display all match states evidence and candidate selection', () => {
  const source = read(REPORTS)
  for (const value of ['matched', 'needs_confirmation', 'unmatched']) assert.match(source, new RegExp(value))
  for (const label of ['AI 已识别', '原文证据', '已匹配归属', '需要确认归属', '无法匹配']) assert.match(source, new RegExp(label))
  assert.match(source, /match_candidates/)
  assert.match(source, /onChange=.*matched_subtask_id/s)
})

test('multiple Agent drafts use a task-card switcher and render only the active full form', () => {
  const source = read(REPORTS)
  assert.match(source, /useState\(0\)/)
  assert.match(source, /voice-update-task-switcher/)
  assert.match(source, /taskReports\.length > 1/)
  assert.match(source, /activeItem\s*&&\s*renderReport\(activeItem\.report, activeItem\.index/)
  assert.doesNotMatch(source, /其他 AI 识别项|其他进展/)
  assert.doesNotMatch(source, /otherItems\.map/)
})

test('unmatched ownership uses explicit project workstream and key-task selection', () => {
  const source = read(REPORTS)
  for (const label of ['选择项目', '选择重点工作', '选择关键任务']) assert.match(source, new RegExp(label))
  assert.match(source, /progress\.match_status === 'unmatched'/)
  assert.match(source, /voice-update-unmatched-ownership/)
})

test('editor uses one cohesive SaaS workspace with a compact visible footer', () => {
  const page = read(PAGE)
  const css = read(CSS)
  assert.match(page, /voice-update-editor-shell[\s\S]*voice-update-workspace[\s\S]*<\/main>\s*<VoiceUpdateSubmitPanel/)
  assert.match(css, /\.voice-update-editor-shell\s*\{[^}]*overflow:\s*hidden[^}]*border:[^}]*border-radius:\s*10px/s)
  assert.match(css, /\.voice-update-footer\s*\{[^}]*margin:\s*0[^}]*border-top:/s)
  assert.match(css, /\.voice-update-main-scroll\s*\{[^}]*padding:\s*0/s)
  assert.match(css, /\.voice-update-footer-bar\s*\{[^}]*height:\s*56px/s)
})

test('unconfirmed Agent ownership blocks formal submission without changing createUpdate', async () => {
  const { hasUnconfirmedOwnership } = await loadFlowModel()
  assert.equal(hasUnconfirmedOwnership([{ type: 'progress', match_status: 'matched', matched_subtask_id: 1 }]), false)
  assert.equal(hasUnconfirmedOwnership([{ type: 'progress', match_status: 'needs_confirmation', matched_subtask_id: null }]), true)
  assert.equal(hasUnconfirmedOwnership([{ type: 'progress', match_status: 'unmatched', matched_subtask_id: null }]), true)
  assert.match(read(SUBMIT), /hasUnconfirmedOwnership/)
  assert.match(read(SUBMIT), /请先确认所有任务卡归属/)
  assert.equal((read(SUBMISSION).match(/createUpdate\(/g) ?? []).length, 1)
})

test('resolved cross-project scopes use one atomic batch request while task scope keeps createUpdate', () => {
  const submission = read(SUBMISSION)
  const api = read('src/api/updates.ts')
  const page = read(PAGE)
  assert.match(api, /createUpdateBatch/)
  assert.match(api, /\/api\/updates\/batch/)
  assert.match(submission, /reportScope === 'task'/)
  assert.match(submission, /createUpdateBatch/)
  assert.match(submission, /createUpdate\(/)
  assert.match(submission, /client_request_id/)
  assert.match(page, /reportScope,/)
  assert.doesNotMatch(page, /姝ｅ紡鎻愪氦灏嗗湪涓嬩竴闃舵寮€鏀?/) // 正式提交将在下一阶段开放
})

test('all and project scope can submit only after every Agent card has concrete ownership', () => {
  const panel = read(SUBMIT)
  assert.match(panel, /reportScope/)
  assert.match(panel, /hasUnconfirmedAgentOwnership/)
  assert.match(panel, /reportScope === 'task'/)
  assert.match(panel, /taskReports\.length > 0/)
})

test('all-work submission is not blocked by the absence of one selected project', () => {
  const source = read(PAGE)
  assert.match(source, /reportScope === 'all'\s*\?\s*null\s*:\s*!selectedProject/)
})

test('compact work report layout keeps the functional scope selector in the header and removes the stepper', () => {
  const page = read(PAGE)
  assert.doesNotMatch(page, /VoiceUpdateFlowStepper/)
  assert.match(page, /VoiceUpdateTaskBindingBar[\s\S]*?scope=\{reportScope\}[\s\S]*?onScopeChange=\{handleScopeChange\}/)
  assert.match(page, /VoiceUpdateTaskBindingBar[\s\S]*?voice-update-history-button/)
})

test('compact work report layout keeps the two-column workspace and bottom actions', () => {
  const page = read(PAGE)
  const css = read(CSS)
  const submit = read(SUBMIT)
  assert.match(css, /\.voice-update-workspace\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*40fr\)\s+minmax\(0,\s*60fr\)/s)
  assert.match(page, /VoiceUpdateInputPanel[\s\S]*VoiceUpdateResultPanel[\s\S]*VoiceUpdateSubmitPanel/)
  assert.match(submit, /onSaveDraft/)
  assert.match(submit, /onSubmitFinal/)
})

test('compact work report panels use plain titles without numbered step badges', () => {
  const source = `${read(INPUT)}\n${read(RESULT)}\n${read(REPORTS)}`
  assert.doesNotMatch(source, /voice-update-panel-step/)
  assert.match(source, /<h2>输入内容<\/h2>/)
  assert.match(source, /AI 提取结果/)
})

test('compact work report modules use natural height without large filler gaps', () => {
  const css = read(CSS)
  assert.match(css, /\.voice-update-workspace\s*\{[^}]*align-items:\s*start/s)
  assert.match(css, /\.voice-update-workspace\s*\{[^}]*gap:\s*0/s)
  assert.doesNotMatch(css, /\.voice-update-workspace\s*\{[^}]*min-height:\s*650px/s)
  assert.match(css, /\.voice-update-textarea\s*\{[^}]*height:\s*240px[^}]*min-height:\s*240px/s)
})
