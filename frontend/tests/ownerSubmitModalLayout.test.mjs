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
const activeSource = source.split(/\r?\n\s*\/\*/)[0]
const workbenchShellClassName = activeSource.split(/\r?\n/).find((line) => line.includes('owner-submit-workbench-shell')) ?? ''
const workbenchMainClassName = activeSource.split(/\r?\n/).find((line) => line.includes('owner-submit-workbench-main')) ?? ''

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
  assert.match(source, /min-h-0 flex-1[^\"]*overflow-y-auto/)
})

test('picker triggers use a stable SVG chevron instead of a font glyph', () => {
  assert.equal((activeSource.match(/owner-submit-picker-chevron shrink-0 h-4 w-4/g) ?? []).length, 2)
  assert.doesNotMatch(activeSource, /rotate-180[^>]*>⌄</)
})

test('notes column receives a wide share without truncating its editor', () => {
  assert.match(activeSource, /owner-submit-b-split[\s\S]*?table-fixed min-w-\[680px\]/)
  assert.match(activeSource, /w-\[23%\][^\n]*评价指标/)
  assert.match(activeSource, /placeholder="填写评价指标"/)
  assert.doesNotMatch(activeSource, /max-w-\[180px\]/)
  assert.doesNotMatch(activeSource, /max-w-\[180px\][^\n]*truncate/)
})

test('selected task title keeps display-first editing semantics', () => {
  assert.match(activeSource, /editingTitleIndex === selectedTaskIndex/)
  assert.match(activeSource, /placeholder="请输入重点工作名称"/)
  assert.match(activeSource, /owner-submit-title-display/)
  assert.match(activeSource, /未命名重点工作/)
  assert.match(activeSource, /owner-submit-goal-result/)
  assert.match(activeSource, /placeholder="请输入目标成果"/)
})

test('workbench uses the final responsive project core sidebar and plan pane', () => {
  assert.match(workbenchShellClassName, /min-h-0/)
  assert.match(workbenchShellClassName, /flex-1/)
  assert.match(activeSource, /填写项目方案 — \{project\.name\}/)
  assert.match(activeSource, /完善项目计划内容，确认后提交企业教练审核/)
  assert.match(activeSource, /owner-submit-project-summary/)
  assert.match(activeSource, /owner-submit-plan-section/)
  assert.match(activeSource, /owner-submit-workbench-columns[^\n]*lg:flex-row/)
  assert.match(activeSource, /owner-submit-left-pane[^\n]*lg:w-\[360px\]/)
  assert.match(activeSource, /owner-submit-right-pane[^\n]*min-w-0 flex-1/)
  assert.doesNotMatch(activeSource, /disabled[\s\S]{0,120}value=\{project\.name\}/)
})

test('workbench is page-local while retaining a scrollable main boundary', () => {
  assert.doesNotMatch(activeSource, /fixed inset-0/)
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
  assert.match(activeSource, /owner-submit-project-summary[^\n]*owner-submit-core-card[^\n]*py-4/)
  assert.match(activeSource, />项目概览<\/h3>/)
  assert.doesNotMatch(activeSource, /基础信息由管理层维护/)
  assert.match(activeSource, /grid-cols-\[130px_minmax\(0,1fr\)\]/)
  assert.match(activeSource, /项目编号/)
  assert.match(activeSource, /项目名称/)
  assert.match(activeSource, /项目状态/)
  assert.match(activeSource, /项目周期/)
  assert.match(activeSource, /项目目标/)
  assert.match(activeSource, /项目背景/)
  assert.match(activeSource, /补充说明/)
  assert.match(activeSource, /项目说明/)
  assert.match(activeSource, /项目角色/)
  assert.doesNotMatch(activeSource, /setFillForm/)
  assert.doesNotMatch(activeSource, /setProjectPeriod/)
  assert.doesNotMatch(activeSource, /ownerSubmitProfile\(project\.id, \{[\s\S]{0,240}(?:objectives|start_date|end_date)/)
})

test('project summary and selected task preserve scanable display-first information', () => {
  assert.match(activeSource, /owner-submit-project-summary-display/)
  assert.match(activeSource, /owner-submit-project-info-row/)
  assert.match(activeSource, /owner-submit-b-split/)
  assert.match(activeSource, /composeTaskPeriod\(task\.plan_start, task\.plan_end\)/)
  assert.match(activeSource, /task\.subtasks\.map\(\(subtask\) => composeTaskPeriod\(subtask\.plan_start, subtask\.plan_end\)\)\.find\(Boolean\)/)
})

test('screenshot reference adds presentation-only task table affordances without removing editors', () => {
  assert.match(activeSource, /owner-submit-subtask-drag-handle/)
  assert.match(activeSource, /owner-submit-subtask-delete-icon/)
  assert.match(activeSource, /<AssigneePicker people=\{people\}/)
  assert.match(activeSource, /<HelperPicker people=\{people\}/)
  assert.match(activeSource, /计划时间：\{taskPeriod\}/)
  assert.match(activeSource, /owner-submit-subtask-table table-fixed min-w-\[680px\]/)
})

test('top add action is the only visible workstream creation entry', () => {
  assert.match(activeSource, /className="owner-submit-primary-add[^"]*"[\s\S]{0,80}>\s*\+ 新增重点工作/)
  assert.doesNotMatch(activeSource, /owner-submit-continue-add/)
  assert.equal((activeSource.match(/onClick=\{addTaskDraft\}/g) ?? []).length, 1)
})

test('task selection defaults to the first workstream and keeps all workstreams navigable', () => {
  assert.match(activeSource, /selectedTaskIndex, setSelectedTaskIndex[\s\S]{0,100}useState\(0\)/)
  assert.match(activeSource, /draftTasks\.map\(\(item, index\) => <button/)
  assert.match(activeSource, /aria-current=\{index === selectedTaskIndex/)
  assert.match(activeSource, /setSelectedTaskIndex\(index\)/)
  assert.match(activeSource, /未命名重点工作/)
  assert.doesNotMatch(activeSource, /expandedTaskIndexes/)
})

test('adding and deleting tasks preserves the selected workstream without index drift', () => {
  assert.match(activeSource, /function addTaskDraft\(\)[\s\S]*setSelectedTaskIndex\(nextIndex\)/)
  assert.match(activeSource, /function removeTaskDraft\(index: number\)[\s\S]*setSelectedTaskIndex\(\(current\) => current > index \? current - 1 : Math\.min\(current, prev\.length - 2\)\)/)
})

test('AI merge identifies one genuinely new task by stable id or task_id', () => {
  assert.match(activeSource, /function taskStableIdentity\(task: Pick<LocalTaskDraft, 'id' \| 'task_id'>\)/)
  assert.match(activeSource, /task\.task_id/)
  assert.match(activeSource, /task\.id/)
  assert.match(activeSource, /existingTaskIdentities/)
  assert.match(activeSource, /findIndex\(\(task\) => \{[\s\S]*const identity = taskStableIdentity\(task\)[\s\S]*!existingTaskIdentities\.has\(identity\)/)
  assert.match(activeSource, /setSelectedTaskIndex\(nextSelectedIndex >= 0 \? nextSelectedIndex : \(firstNewTaskIndex >= 0 \? firstNewTaskIndex : 0\)\)/)
})

test('upload entry remains available when AI initialization fails', () => {
  assert.match(aiSource, /const showUploadStage = panelState === 'idle' \|\| panelState === 'uploading' \|\| \(panelState === 'failed' && !run\)/)
  assert.match(aiSource, /\{showUploadStage && \(/)
  assert.match(aiSource, /选择资料文件/)
  assert.match(aiSource, /开始分析/)
})
