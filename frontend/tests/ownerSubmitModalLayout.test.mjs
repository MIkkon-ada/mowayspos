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

test('notes column receives a wide share without truncating its editor', () => {
  assert.match(source, /table-fixed/)
  assert.match(source, /w-\[24%\][^\n]*验收标准 \/ 备注/)
  assert.match(source, /placeholder="填写验收标准或说明"/)
  assert.doesNotMatch(source, /max-w-\[180px\]/)
  assert.doesNotMatch(source, /max-w-\[180px\][^\n]*truncate/)
})

test('expanded task header inputs use compact workbench styling', () => {
  assert.match(source, /text-xs font-semibold tracking-wide text-slate-500/)
  assert.match(source, /placeholder="请输入重点工作"[\s\S]{0,360}h-10[\s\S]{0,160}font-semibold[\s\S]{0,220}focus:ring-2/)
  assert.match(source, /placeholder="请输入完成准则"[\s\S]{0,360}h-10[\s\S]{0,220}focus:ring-2/)
})

test('workbench uses a single-column project summary and full-width plan', () => {
  assert.match(source, /max-w-\[1560px\]/)
  assert.match(source, /填写项目方案 — \{project\.name\}/)
  assert.match(source, /完善项目计划内容，确认后提交企业教练审核/)
  assert.match(source, /owner-submit-project-summary/)
  assert.match(source, /owner-submit-plan-section/)
  assert.doesNotMatch(source, /lg:flex-row/)
  assert.doesNotMatch(source, /owner-submit-left-pane/)
  assert.doesNotMatch(source, /disabled[\s\S]{0,120}value=\{project\.name\}/)
})

test('task expansion state defaults to the first task and collapsed cards are read-only summaries', () => {
  assert.match(source, /expandedTaskIndexes, setExpandedTaskIndexes[\s\S]{0,100}new Set\(\[0\]\)/)
  assert.match(source, /const isExpanded = expandedTaskIndexes\.has\(taskIndex\)/)
  assert.match(source, /isExpanded \? \([\s\S]*?placeholder="请输入重点工作"[\s\S]*?\) : \([\s\S]*?未命名重点工作[\s\S]*?未填写目标成果/)
  assert.match(source, /task\.subtasks\.length\} 个关键任务/)
  assert.match(source, /onClick=\{\(\) => expandTask\(taskIndex\)\}/)
  assert.match(source, /aria-label=\{`重点工作 \$\{taskIndex \+ 1\} 更多操作`\}/)
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
  assert.match(source, /findIndex\(\(task\) =>[\s\S]*!existingTaskIdentities\.has\(taskStableIdentity\(task\)\)/)
  assert.match(source, /firstNewTaskIndex >= 0[\s\S]*next\.add\(firstNewTaskIndex\)/)
})

test('upload entry remains available when AI initialization fails', () => {
  assert.match(aiSource, /const showUploadStage = panelState === 'idle' \|\| panelState === 'uploading' \|\| \(panelState === 'failed' && !run\)/)
  assert.match(aiSource, /\{showUploadStage && \(/)
  assert.match(aiSource, /暂时无法获取 AI 分析状态，请先选择资料文件，上传后再重试。/)
})
