import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/pages/AchievementsPage.tsx', import.meta.url), 'utf8')

test('achievement library overview matches the full project table information architecture', () => {
  for (const label of ['项目成果库', '搜索项目名称', '登记成果', '查看成果']) assert.match(source, new RegExp(label))
  for (const label of ['项目', '已入库成果', '本月新增成果', '最近更新']) assert.match(source, new RegExp(label))
  for (const label of ['项目名称', '状态', '项目负责人', '企业教练', '成果数量', '最近更新', '操作']) assert.match(source, new RegExp(label))
  assert.match(source, /fetchAchievements\(project\.id\)/)
  assert.match(source, /查看成果/)
})

test('achievement library never renders the Bowei Consulting suffix', () => {
  assert.doesNotMatch(source, /博维咨询/)
})
