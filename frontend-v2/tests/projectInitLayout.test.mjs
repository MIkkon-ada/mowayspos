import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(new URL('../src/features/settings/ProjectInitModal.tsx', import.meta.url), 'utf8')
const activeStart = source.indexOf('project-init-workbench')
const activeEnd = source.indexOf('\n  return createPortal(', activeStart + 1)
const activeLayout = source.slice(activeStart, activeEnd)

test('project initiation uses a centered information canvas and team sidebar', () => {
  assert.match(activeLayout, /project-init-workbench/)
  assert.match(activeLayout, /initiation-form-body/)
  assert.match(activeLayout, /max-w-\[1180px\]/)
  assert.match(activeLayout, /justify-center/)
  assert.match(activeLayout, /initiation-team/)
  assert.match(activeLayout, /aria-label="立项流程"/)
  assert.match(activeLayout, /基本信息/)
  assert.match(activeLayout, /项目目标与验收要求/)
  assert.match(activeLayout, /团队配置/)
  assert.match(activeLayout, /保存项目草稿/)
  assert.match(activeLayout, /保存后进入草稿/)
  assert.doesNotMatch(activeLayout, /rounded-3xl bg-white shadow-/)
})

test('project initiation keeps business fields and explains the next handoff', () => {
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
