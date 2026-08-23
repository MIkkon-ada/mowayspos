import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const accountsApi = fs.readFileSync(path.join(root, 'src/api/accounts.ts'), 'utf8')
const peopleApi = fs.readFileSync(path.join(root, 'src/api/people.ts'), 'utf8')
const section = fs.readFileSync(path.join(root, 'src/features/settings/AccountPeopleMgmtSection.tsx'), 'utf8')

test('people management exposes confirmed WeCom identity sync', () => {
  assert.match(accountsApi, /fetchWecomDirectory/)
  assert.match(accountsApi, /syncWecomDirectory/)
  assert.match(peopleApi, /resetIdentityField/)
  assert.match(section, /WecomIdentitySyncModal/)
  assert.match(section, /本地覆盖/)
  assert.match(section, /恢复企业微信值/)
})
