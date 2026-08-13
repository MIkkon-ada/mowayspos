import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

test('settings uses model management after retiring the legacy LLM provider screen', () => {
  assert.equal(fs.existsSync(path.join(root, 'src/features/settings/LLMConfigSection.tsx')), false)
  assert.equal(fs.existsSync(path.join(root, 'src/api/llmConfig.ts')), false)

  const settings = fs.readFileSync(path.join(root, 'src/pages/SettingsPage.tsx'), 'utf8')
  assert.match(settings, /AIConfigurationSection/)
  assert.doesNotMatch(settings, /LLMConfigSection/)
})
