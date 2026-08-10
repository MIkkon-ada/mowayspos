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

test('notes column has a bounded share of the task table', () => {
  assert.match(source, /table-fixed/)
  assert.match(source, /w-\[180px\][^\n]*备注 \/ 标准/)
})

test('task header inputs use readable card styling instead of browser default focus chrome', () => {
  assert.match(source, /text-xs font-semibold tracking-wide text-slate-500/)
  assert.match(source, /placeholder="请输入重点工作"[\s\S]{0,320}text-xl font-bold[\s\S]{0,220}focus:outline-none focus:ring-4/)
  assert.match(source, /placeholder="请输入完成准则"[\s\S]{0,320}text-base font-medium[\s\S]{0,220}focus:outline-none focus:ring-4/)
})

test('workbench uses a compact balanced two-column layout', () => {
  assert.match(source, /max-w-\[1560px\]/)
  assert.match(source, /min-h-\[68px\]/)
  assert.match(source, /gap-6 px-6 py-6/)
  assert.match(source, /lg:w-\[280px\] xl:w-\[300px\]/)
})

test('upload entry remains available when AI initialization fails', () => {
  assert.match(aiSource, /const showUploadStage = panelState === 'idle' \|\| panelState === 'uploading' \|\| \(panelState === 'failed' && !run\)/)
  assert.match(aiSource, /\{showUploadStage && \(/)
  assert.match(aiSource, /暂时无法获取 AI 分析状态，请先选择资料文件，上传后再重试。/)
})
