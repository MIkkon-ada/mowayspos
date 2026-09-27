import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('document client posts one multipart file to the work-report endpoint', () => {
  const api = read('src/api/updates.ts')
  assert.match(api, /extractWorkReportDocumentText/)
  assert.match(api, /extract-document-text/)
  assert.match(api, /fd\.append\(['"]file['"], file\)/)
})

test('document hook replaces text only after successful parsing and exposes removal state', () => {
  const hook = read('src/features/voice-update/useVoiceDocumentUpload.ts')
  assert.match(hook, /setText\(result\.text\)/)
  assert.match(hook, /function removeDocument\(\)/)
  assert.match(hook, /documentFileName/)
})

test('work-report input exposes document as fourth source and accepts approved formats', () => {
  const input = read('src/features/voice-update/VoiceUpdateInputPanel.tsx')
  const formats = read('src/config/aiDocumentFormats.ts')
  assert.match(input, /VoiceInputMode/)
  assert.match(input, /document/)
  assert.match(input, /上传文档/)
  assert.match(input, /acceptedDocumentTypes\('workReport'\)/)
  assert.match(formats, /workReport:\s*\['\.docx', '\.pdf', '\.xlsx', '\.pptx'\]/)
  assert.match(input, /拖入文档，或点击选择/)
  assert.match(input, /文档解析内容/)
})

test('document origin uses the document label for extraction and submission', () => {
  assert.match(read('src/features/voice-update/useVoiceExtraction.ts'), /文档解析/)
  assert.match(read('src/features/voice-update/useVoiceSubmission.ts'), /文档解析/)
})

test('page wires document upload state into the shared editor', () => {
  const page = read('src/pages/VoiceUpdatePage.tsx')
  assert.match(page, /useVoiceDocumentUpload/)
  assert.match(page, /onDocumentFile/)
  assert.match(page, /documentUploading/)
})

test('starting a new report clears parsed document text and document metadata together', () => {
  const page = read('src/pages/VoiceUpdatePage.tsx')
  assert.match(
    page,
    /onResetExtractionState=\{\(options\) => \{\s*resetExtractionState\(options\);\s*removeDocument\(\)\s*\}\}/,
  )
})

test('restarting from history clears stale document metadata before restoring report text', () => {
  const page = read('src/pages/VoiceUpdatePage.tsx')
  assert.match(
    page,
    /onRestartFromSubmission=\{\(detailItem\) => \{\s*resetExtractionState\(\)\s*removeDocument\(\)/,
  )
})
