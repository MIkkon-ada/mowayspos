import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const accountsApi = fs.readFileSync(path.join(root, 'src/api/accounts.ts'), 'utf8')
const peopleApi = fs.readFileSync(path.join(root, 'src/api/people.ts'), 'utf8')
const section = fs.readFileSync(path.join(root, 'src/features/settings/AccountPeopleMgmtSection.tsx'), 'utf8')
const modal = fs.readFileSync(path.join(root, 'src/features/settings/WecomIdentitySyncModal.tsx'), 'utf8')

test('confirmed WeCom identity sync remains preview-first and has no local override path', () => {
  assert.match(accountsApi, /fetchWecomDirectory/)
  assert.match(accountsApi, /syncWecomDirectory/)
  assert.match(peopleApi, /createAccountManagementPerson/)
  assert.match(peopleApi, /updateAccountManagementPerson/)
  assert.match(section, /WecomIdentitySyncModal/)
  assert.match(modal, /确认同步/)
  assert.match(modal, /企业微信同步后将覆盖系统中的部门和岗位/)
  assert.doesNotMatch(modal, /本地覆盖/)
})

test('WeCom modal exposes full-directory account provisioning', () => {
  assert.match(accountsApi, /provisionWecomDirectoryAccounts/)
  assert.match(accountsApi, /wecom-directory\/provision-all/)
  assert.match(modal, /同步全员并创建账号/)
  assert.match(modal, /初始密码为 123456/)
  assert.match(modal, /created_accounts/)
  assert.match(modal, /conflicts/)
})
