import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/features/settings/ProjectInitModal.tsx', import.meta.url), 'utf8')
const activeStart = source.indexOf('project-init-workbench')
const activeEnd = source.indexOf('\n  return createPortal(', activeStart + 1)
const activeLayout = source.slice(activeStart, activeEnd)

test('project initiation uses the new three-column workbench layout', () => {
  assert.match(activeLayout, /project-init-workbench/)
  assert.match(activeLayout, /xl:pl-44/)
  assert.match(activeLayout, /max-w-none/)
  assert.match(activeLayout, /justify-end/)
  assert.match(activeLayout, /基本信息/)
  assert.match(activeLayout, /战略背景与目标/)
  assert.match(activeLayout, /团队配置/)
  assert.match(activeLayout, /确认立项/)
  assert.doesNotMatch(activeLayout, /rounded-3xl bg-white shadow-/)
})

test('project initiation keeps business fields without explanatory copy', () => {
  assert.match(activeLayout, /项目类型/)
  assert.match(activeLayout, /项目名称/)
  assert.match(activeLayout, /开始日期/)
  assert.match(activeLayout, /结束日期/)
  assert.match(activeLayout, /项目背景/)
  assert.match(activeLayout, /项目目标/)
  assert.match(activeLayout, /预期交付物/)
  assert.match(activeLayout, /roleOrder\.map\(\(role\)/)
  assert.match(activeLayout, /ROLE_LABELS\[role\]/)
  assert.doesNotMatch(activeLayout, /填写完整后创建项目，立项人会自动记录为当前登录用户/)
})
