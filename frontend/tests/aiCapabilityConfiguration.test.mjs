import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const sectionPath = path.join(root, 'src/features/settings/AIConfigurationSection.tsx')
const drawerPath = path.join(root, 'src/features/settings/AIModelDrawer.tsx')
const apiPath = path.join(root, 'src/api/aiConfig.ts')
const providersPath = path.join(root, 'src/features/settings/aiModelProviders.ts')

test('AI model settings manages the model registry without business bindings or secrets', () => {
  const source = fs.readFileSync(sectionPath, 'utf8')
  const drawer = fs.readFileSync(drawerPath, 'utf8')
  const api = fs.readFileSync(apiPath, 'utf8')
  const providers = fs.readFileSync(providersPath, 'utf8')

  assert.match(source, /模型管理/)
  assert.match(source, /添加模型/)
  assert.match(drawer, /credential_configured/)
  assert.match(api, /\/api\/ai-config\/models/)
  assert.doesNotMatch(source, /能力策略|listAICapabilityPolicies|saveAICapabilityPolicy|defaultPolicy/)
  assert.doesNotMatch(source + drawer, /value=\{[^}]*api_key|credential\.api_key/)
  assert.match(providers, /deepseek-v4-flash、deepseek-v4-pro/)
  assert.match(drawer, /setMessage\(result\.message\)/)
  assert.doesNotMatch(drawer, /模型名称、Base URL 和 API Key/)
  assert.match(drawer, /const \{ code: _code, source: _source, \.\.\.updatePayload \} = payload\(\)/)
  assert.match(drawer, /updateAIModel\(persistedModelId, updatePayload\)/)
})
