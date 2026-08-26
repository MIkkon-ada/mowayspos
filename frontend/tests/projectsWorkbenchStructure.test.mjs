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
for (const label of [
  'project-todo-summary flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between',
  'project-todo-action-row',
  '待补充：',
  '已完成 ',
  '尚有 ${missingCount} 项信息待完善',
  'check.label.trim()',
  '.filter((check) => check.label)',
  'flex-1',
]) {
  assert.ok(source.includes(label), `expected ProjectTodoSection hierarchy to contain ${label}`)
}
console.log('projects management workbench structure contract passed')
