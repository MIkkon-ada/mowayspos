import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const source = fs.readFileSync(path.resolve(here, '../src/features/settings/AIConfigurationSection.tsx'), 'utf8')

test('technical administrators can order and save AI model fallback policies', () => {
  assert.match(source, /listAICapabilityPolicies/)
  assert.match(source, /saveAICapabilityPolicy/)
  assert.match(source, /AI 能力策略/)
  assert.match(source, /moveModel/)
  assert.match(source, /保存顺序/)
  assert.match(source, /fallback_model_ids: ids\.slice\(1\)/)
})
