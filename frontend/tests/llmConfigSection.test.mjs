import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const source = fs.readFileSync(path.join(root, 'src/features/settings/LLMConfigSection.tsx'), 'utf8')
const api = fs.readFileSync(path.join(root, 'src/api/llmConfig.ts'), 'utf8')

test('LLM settings exposes a persisted default provider without rendering keys', () => {
  assert.match(source, /默认 LLM/)
  assert.match(source, /defaultProvider/)
  assert.match(api, /getLLMDefaultProvider/)
  assert.match(api, /saveLLMDefaultProvider/)
  assert.doesNotMatch(source, /value=\{cfg\.api_key\}/)
})
