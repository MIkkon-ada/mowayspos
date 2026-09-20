import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('people management uses a table and moves person actions into a drawer', () => {
  const table = read('src/features/settings/PeopleManagementTable.tsx')
  const drawer = read('src/features/settings/PersonDetailDrawer.tsx')
  for (const label of ['人员 / 账号', '部门 · 岗位', '系统角色', '企业微信', '账号状态']) assert.match(table, new RegExp(label))
  assert.match(table, /搜索姓名或账号/)
  assert.match(table, /onSelectPerson/)
  assert.match(drawer, /企业微信身份/)
  assert.match(drawer, /同步来源/)
  assert.match(drawer, /系统权限/)
  assert.match(drawer, /账号与安全/)
  assert.match(drawer, /重置密码/)
  assert.match(drawer, /停用账号|启用账号/)
  assert.doesNotMatch(drawer, /placeholder="部门"/)
  assert.doesNotMatch(drawer, /placeholder="岗位"/)
})

test('settings section owns refreshes and delegates display to table and drawer', () => {
  const section = read('src/features/settings/AccountPeopleMgmtSection.tsx')
  assert.match(section, /PeopleManagementTable/)
  assert.match(section, /PersonDetailDrawer/)
  assert.match(section, /selectedPersonId/)
  assert.match(section, /loadAll\(\)/)
  assert.match(section, /createAccountManagementPerson/)
  assert.match(section, /updateAccountManagementPerson/)
  assert.doesNotMatch(section, /grid-cols-1 md:grid-cols-2 xl:grid-cols-3/)
  assert.doesNotMatch(section, /恢复企业微信值/)
  assert.doesNotMatch(section, /placeholder="部门（可选）"/)
  assert.doesNotMatch(section, /placeholder="岗位（可选）"/)
})
