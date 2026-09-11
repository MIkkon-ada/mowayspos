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

test('picker menus flip upward and stay inside the viewport when the bottom area is short', () => {
  assert.match(source, /function getPickerMenuPosition\(/)
  assert.match(source, /spaceBelow/)
  assert.match(source, /spaceAbove/)
  assert.match(source, /bottom: menuPosition\.bottom/)
  assert.match(source, /maxHeight: menuPosition\.maxHeight/)
  assert.match(source, /min-h-0 flex-1[^\"]*overflow-y-auto/)
})

test('picker triggers use stable SVG chevrons instead of a font glyph', () => {
  assert.equal((source.match(/className=\{`owner-submit-picker-chevron shrink-0 h-4 w-4/g) ?? []).length, 2)
  assert.doesNotMatch(source, />⌄</)
})

test('approved B layout shows project overview beside one selected workstream editor', () => {
  assert.match(source, /function renderApprovedLayout\(\)/)
  assert.match(source, /aria-label="重点工作列表"/)
  assert.match(source, /draftTasks\[selectedTaskIndex\] \?\? draftTasks\[0\]/)
  assert.match(source, /owner-submit-b-split/)
  assert.match(source, /验收标准 \/ 关键成果/)
  assert.match(source, /推进流程/)
})

test('approved layout has one add action and no legacy expansion UI', () => {
  assert.equal((source.match(/onClick=\{addTaskDraft\}/g) ?? []).length, 1)
  assert.doesNotMatch(source, /owner-submit-continue-add/)
  assert.doesNotMatch(source, /expandedTaskIndexes/)
  assert.doesNotMatch(source, /collapseTask\(/)
  assert.doesNotMatch(source, /expandTask\(/)
})

test('AI merge preserves selection by stable identity and selects a genuinely new task as fallback', () => {
  assert.match(source, /function taskStableIdentity\(/)
  assert.match(source, /existingTaskIdentities/)
  assert.match(source, /firstNewTaskIndex/)
  assert.match(source, /setSelectedTaskIndex\(nextSelectedIndex >= 0 \? nextSelectedIndex : \(firstNewTaskIndex >= 0 \? firstNewTaskIndex : 0\)\)/)
})

test('upload entry remains available when AI initialization fails', () => {
  assert.match(aiSource, /const showUploadStage = panelState === 'idle' \|\| panelState === 'uploading' \|\| \(panelState === 'failed' && !run\)/)
  assert.match(aiSource, /\{showUploadStage && \(/)
  assert.match(aiSource, /选择资料文件/)
  assert.match(aiSource, /开始分析/)
})
