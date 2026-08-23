import fs from 'node:fs'
import path from 'node:path'
import assert from 'node:assert/strict'

const sourcePaths = [
  'src/features/settings/ProjectsMgmtSection.tsx',
  'src/features/settings/ProjectOverviewStats.tsx',
  'src/features/settings/ProjectTodoSection.tsx',
]
const source = sourcePaths.map((file) => fs.readFileSync(path.resolve(process.cwd(), file), 'utf8')).join('\n')

for (const label of [
  '项目管理',
  '管理项目从立项、启动到执行与归档',
  '待我处理',
  '全部项目',
  '卡片视图',
  '列表视图',
  'viewMode',
  '待完善',
  '待审批',
  '进行中',
  '已归档',
]) {
  assert.ok(source.includes(label), `expected ProjectsMgmtSection to contain ${label}`)
}

assert.ok(!source.includes('完善材料'), 'obsolete materials wording must be removed')
assert.ok(source.includes('完善项目计划'), 'project-plan wording must be present')
console.log('projects management workbench structure contract passed')
