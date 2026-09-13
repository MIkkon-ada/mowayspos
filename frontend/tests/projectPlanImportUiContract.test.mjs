import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/features/settings/ProjectsMgmtSection.tsx', import.meta.url), 'utf8')
const dialog = readFileSync(new URL('../src/features/settings/ProjectPlanAiImportDialog.tsx', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/api/projectPlanAiImport.ts', import.meta.url), 'utf8')
const converter = readFileSync(new URL('../src/features/settings/projectPlanAiImportDraft.ts', import.meta.url), 'utf8')

test('project management uses the AI work plan import review flow', () => {
  assert.match(source, /ProjectPlanAiImportDialog/)
  assert.match(source, /AI 批量导入弹窗/)
  assert.match(dialog, /previewAiProjectPlan/)
  assert.match(dialog, /draftToBatchImportRows/)
  assert.match(dialog, /applyAiProjectPlan/)
  assert.match(dialog, /确认并修正导入内容/)
  assert.match(dialog, /fallback_mode/)
  assert.match(dialog, /targetProjectId/)
  assert.match(api, /\/api\/projects\/ai-plan-import\/preview/)
  assert.match(api, /\/api\/projects\/ai-plan-import\/apply/)
  assert.match(converter, /evidenceNotes/)
  assert.match(converter, /AI 未识别到项目名称/)
})
