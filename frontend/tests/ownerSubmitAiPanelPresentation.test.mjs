import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(new URL('../src/features/settings/OwnerSubmitAiPanel.tsx', import.meta.url), 'utf8')

test('AI preview keeps technical details and raw evidence secondary to draft review', () => {
  assert.match(source, /className="owner-submit-ai-panel[^\"]*pb-/)
  assert.match(source, /文件分析完成/)
  assert.match(source, /已生成 \{draft\.tasks\.length\} 项候选重点工作/)
  assert.match(source, /\{draft\.tasks\.length\} 项待确认/)
  assert.match(source, /owner-submit-ai-technical-details/)
  assert.match(source, /owner-submit-ai-evidence/)
  assert.match(source, /owner-submit-ai-task-card/)
  assert.match(source, /应用到推进表/)
})
