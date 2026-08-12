import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const sectionPath = path.join(root, 'src/features/settings/AIConfigurationSection.tsx')
const apiPath = path.join(root, 'src/api/aiConfig.ts')

test('AI capability settings manages models and policies without rendering secrets', () => {
  const source = fs.readFileSync(sectionPath, 'utf8')
  const api = fs.readFileSync(apiPath, 'utf8')

  assert.match(source, /AI能力配置/)
  assert.match(source, /能力策略/)
  assert.match(source, /credential_configured/)
  assert.match(api, /\/api\/ai-config\/models/)
  assert.match(api, /\/api\/ai-config\/policies/)
  assert.doesNotMatch(source, /value=\{[^}]*api_key/)
  assert.doesNotMatch(source, /credential\.api_key/)
})
