import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(here, '../src/features/settings/OwnerSubmitModal.tsx')
const source = fs.readFileSync(sourcePath, 'utf8')
const aiSourcePath = path.resolve(here, '../src/features/settings/OwnerSubmitAiPanel.tsx')
const aiSource = fs.readFileSync(aiSourcePath, 'utf8')
const workbenchShellClassName = source.split(/\r?\n/).find((line) => line.includes('owner-submit-workbench-shell')) ?? ''
const workbenchMainClassName = source.split(/\r?\n/).find((line) => line.includes('owner-submit-workbench-main')) ?? ''

test('assignee picker renders outside the table overflow container', () => {
  assert.match(source, /from ['"]react-dom['"]/)
  assert.match(source, /createPortal\(/)
  assert.match(source, /document\.body/)
})

test('helper picker keeps multi-select behavior while using the assignee picker pattern', () => {
  assert.match(source, /function HelperPicker\(/)
  assert.match(source, /请选择协助人/)
  assert.match(source, /helperIds\.includes\(/)
  assert.match(source, /onChange=\{\(personId\) => toggleSubTaskHelper\(/)
})

test('picker scrolling does not close the option list', () => {
  assert.match(source, /menuRef/)
  assert.match(source, /menuRef\.current\?\.contains\(event\.target as Node\)/)
})

test('picker menus flip upward and stay inside the viewport when the bottom area is short', () => {
  assert.match(source, /function getPickerMenuPosition\(/)
  assert.match(source, /spaceBelow/)
  assert.match(source, /spaceAbove/)
  assert.match(source, /bottom: menuPosition\.bottom/)
  assert.match(source, /maxHeight: menuPosition\.maxHeight/)
  assert.match(source, /min-h-0 flex-1[^"]*overflow-y-auto/)
})

test('picker triggers use a stable SVG chevron instead of a font glyph', () => {
  assert.equal((source.match(/<svg[^>]+className=\{`shrink-0 h-4 w-4/g) ?? []).length, 2)
  assert.doesNotMatch(source, /rotate-180[^>]*>⌄</)
})

test('notes column receives a wide share without truncating its editor', () => {
  assert.match(source, /table-fixed/)
  assert.match(source, /w-\[24%\][^\n]*备注 \/ 标准/)
  assert.match(source, /placeholder="填写验收标准或说明"/)
  assert.doesNotMatch(source, /max-w-\[180px\]/)
  assert.doesNotMatch(source, /max-w-\[180px\][^\n]*truncate/)
})

test('expanded task header inputs use compact workbench styling', () => {
  assert.match(source, /owner-submit-task-group-header[^\n]*py-3/)
  assert.equal((source.match(/<label className="sr-only">/g) ?? []).length, 2)
  assert.match(source, /placeholder="[^\"]+"[\s\S]{0,360}sm:max-w-\[360px\][\s\S]{0,160}sm:flex-none/)
  assert.match(source, /placeholder="请输入重点工作"[\s\S]{0,360}h-8[\s\S]{0,160}font-bold[\s\S]{0,220}focus:ring-0/)
  assert.match(source, /placeholder="请输入完成准则"[\s\S]{0,360}h-6[\s\S]{0,220}focus:ring-0/)
})

test('workbench uses the final responsive project core sidebar and plan pane', () => {
  assert.match(workbenchShellClassName, /min-h-0/)
  assert.match(workbenchShellClassName, /flex-1/)
  assert.match(source, /填写项目方案 — \{project\.name\}/)
  assert.match(source, /完善项目计划内容，确认后提交企业教练审核/)
  assert.match(source, /owner-submit-project-summary/)
  assert.match(source, /owner-submit-plan-section/)
  assert.match(source, /owner-submit-workbench-columns[^\n]*lg:flex-row/)
  assert.match(source, /owner-submit-left-pane[^\n]*lg:w-\[280px\][^\n]*xl:w-\[300px\]/)
  assert.match(source, /owner-submit-right-pane[^\n]*flex-1 min-w-0/)
  assert.doesNotMatch(source, /disabled[\s\S]{0,120}value=\{project\.name\}/)
})

test('workbench is page-local while retaining a scrollable main boundary', () => {
  assert.doesNotMatch(source, /fixed inset-0/)
  assert.doesNotMatch(workbenchShellClassName, /max-h-\[calc\(100vh-48px\)\]/)
  assert.doesNotMatch(workbenchShellClassName, /h-\[94vh\]/)
  assert.match(workbenchMainClassName, /min-h-0/)
  assert.match(workbenchMainClassName, /flex-1/)
  assert.match(workbenchMainClassName, /overflow-x-hidden/)
  assert.match(workbenchMainClassName, /overflow-y-auto/)
})

test('workbench fills the right-side page area without modal card framing', () => {
  assert.match(workbenchShellClassName, /owner-submit-workbench-shell flex min-h-0 w-full flex-1 flex-col overflow-hidden bg-\[#f7f9fc\]/)
  assert.doesNotMatch(workbenchShellClassName, /mx-auto/)
  assert.doesNotMatch(workbenchShellClassName, /w-\[96vw\]/)
  assert.doesNotMatch(workbenchShellClassName, /max-w-\[1560px\]/)
  assert.doesNotMatch(workbenchShellClassName, /rounded-xl/)
  assert.doesNotMatch(workbenchShellClassName, /shadow-\[/)
})

test('project core card shows management-maintained base information as read-only', () => {
  assert.match(source, /owner-submit-project-summary[^\n]*owner-submit-core-card[^\n]*py-4/)
  assert.match(source, /mb-1\.5[^>]*>项目核心信息/)
  assert.match(source, /基础信息由管理层维护/)
  assert.match(source, /\{project\.name\}/)
  assert.match(source, /composeProjectPeriod\(project\.start_date, project\.end_date\)/)
  assert.match(source, /\{project\.objectives[^}]*\}/)
  assert.match(source, /项目说明/)
  assert.match(source, /\{project\.description[^}]*\}/)
  assert.match(source, /className="grid grid-cols-1 gap-3"/)
  assert.match(source, /项目名称<\/span>[\s\S]{0,180}mt-2 truncate text-xl font-bold/)
  assert.match(source, /项目周期 \/ 时间段<\/span>[\s\S]{0,260}rounded-lg border border-slate-200 bg-slate-50/)
  assert.match(source, /项目完成准则 \/ 验收标准<\/span>[\s\S]{0,320}>内容<\/span>/)
  assert.match(source, /owner-submit-objectives-content[\s\S]{0,220}rounded-lg border border-slate-200 bg-slate-50/)
  assert.match(source, /project\.objectives\?\.trim\(\) \? \([\s\S]{0,180}\) : \([\s\S]{0,180}未填写/)
  assert.doesNotMatch(source, /md:grid-cols-\[minmax\(160px,0\.8fr\)_minmax\(260px,1fr\)_minmax\(360px,2fr\)\]/)
  assert.match(source, /<details className="app-disclosure group mt-1">/)
  assert.doesNotMatch(source, /setFillForm/)
  assert.doesNotMatch(source, /setProjectPeriod/)
  assert.doesNotMatch(source, /ownerSubmitProfile\(project\.id, \{[\s\S]{0,240}(?:objectives|start_date|end_date)/)
})

test('screenshot reference keeps the project summary display-first and task cards scanable', () => {
  assert.match(source, /owner-submit-project-summary-display/)
  assert.match(source, /owner-submit-project-period-display/)
  assert.match(source, /owner-submit-task-status/)
  assert.match(source, /owner-submit-task-meta/)
  assert.match(source, /composeTaskPeriod\(task\.plan_start, task\.plan_end\)/)
  assert.match(source, /task\.subtasks\.map\(\(subtask\) => composeTaskPeriod\(subtask\.plan_start, subtask\.plan_end\)\)\.find\(Boolean\)/)
})

test('screenshot reference adds presentation-only task table affordances without removing editors', () => {
  assert.match(source, /owner-submit-subtask-drag-handle/)
  assert.match(source, /owner-submit-subtask-date-icon/)
  assert.match(source, /owner-submit-subtask-delete-icon/)
  assert.match(source, /<AssigneePicker people=\{people\}/)
  assert.match(source, /<HelperPicker people=\{people\}/)
  assert.match(source, /owner-submit-subtask-table table-fixed min-w-\[980px\]/)
})

test('top add action stays primary while the list tail uses a weak full-width continue action', () => {
  assert.match(source, /className="owner-submit-primary-add[^"]*"[\s\S]{0,80}>\s*\+ 新增重点工作/)
  assert.match(source, /className="owner-submit-continue-add[^"]*w-full[^"]*h-10[^"]*border-dashed[^"]*"[\s\S]{0,80}>\s*＋ 继续新增重点工作/)
  assert.doesNotMatch(source, /owner-submit-continue-add[^\n]*shadow/)
  assert.equal((source.match(/onClick=\{addTaskDraft\}/g) ?? []).length, 2)
})

test('task expansion state defaults to the first task and collapsed cards are read-only summaries', () => {
  assert.match(source, /expandedTaskIndexes, setExpandedTaskIndexes[\s\S]{0,100}new Set\(\[0\]\)/)
  assert.match(source, /const isExpanded = expandedTaskIndexes\.has\(taskIndex\)/)
  assert.match(source, /isExpanded \? \([\s\S]*?placeholder="请输入重点工作"[\s\S]*?\) : \([\s\S]*?未命名重点工作[\s\S]*?未填写目标成果/)
  assert.match(source, /task\.subtasks\.length\} 个关键任务/)
  assert.match(source, /onClick=\{\(\) => expandTask\(taskIndex\)\}/)
  assert.match(source, /aria-label=\{`重点工作 \$\{taskIndex \+ 1\} 更多操作`\}/)
  assert.match(source, /\) : \([\s\S]*?role="button"[\s\S]*?\)\}/)
  assert.doesNotMatch(source, /max-w-\[180px\]/)
})

test('adding and deleting tasks preserves expansion indexes without drift', () => {
  assert.match(source, /function addTaskDraft\(\)[\s\S]*setExpandedTaskIndexes\(\(current\) => new Set\(current\)\.add\(nextIndex\)\)/)
  assert.match(source, /function removeTaskDraft\(index: number\)[\s\S]*expandedIndex < index[\s\S]*expandedIndex > index[\s\S]*expandedIndex - 1/)
})

test('AI merge identifies one genuinely new task by stable id or task_id', () => {
  assert.match(source, /function taskStableIdentity\(task: Pick<LocalTaskDraft, 'id' \| 'task_id'>\)/)
  assert.match(source, /task\.task_id/)
  assert.match(source, /task\.id/)
  assert.match(source, /existingTaskIdentities/)
  assert.match(source, /findIndex\(\(task\) => \{[\s\S]*const identity = taskStableIdentity\(task\)[\s\S]*!existingTaskIdentities\.has\(identity\)/)
  assert.match(source, /firstNewTaskIndex >= 0[\s\S]*next\.add\(firstNewTaskIndex\)/)
})

test('upload entry remains available when AI initialization fails', () => {
  assert.match(aiSource, /const showUploadStage = panelState === 'idle' \|\| panelState === 'uploading' \|\| \(panelState === 'failed' && !run\)/)
  assert.match(aiSource, /\{showUploadStage && \(/)
  assert.match(aiSource, /暂时无法获取 AI 分析状态，请先选择资料文件，上传后再重试。/)
})
