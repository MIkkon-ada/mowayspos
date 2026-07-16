import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { pathToFileURL } from 'node:url'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

async function loadPureUi() {
  const source = read('src/domain/projectCloseUi.ts')
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
}

test('lifecycle declares pending_close and ended without string escape hatch', () => {
  const source = read('src/domain/projectLifecycleStatus.ts')
  assert.match(source, /\| 'pending_close'/); assert.match(source, /\| 'ended'/)
  assert.doesNotMatch(source, /\| string/)
  assert.match(source, /label: '结束审核中'/); assert.match(source, /label: '已结束'/)
  assert.match(source, /isProjectPendingClose/); assert.match(source, /isProjectEnded/); assert.match(source, /isProjectBusinessFrozen/)
})

test('role action mapping is executable and exact', async () => {
  const { getProjectCloseMainAction, canCreateProjectCloseRequest, canReviewProjectCloseRequest } = await loadPureUi()
  const member = { isSuperAdmin: false, isCompanyCeo: false, isRealProjectCeo: false, isRealOwner: false }
  const owner = { ...member, isRealOwner: true }
  const coach = { ...member, isRealProjectCeo: true }
  const admin = { ...member, isSuperAdmin: true }
  assert.equal(getProjectCloseMainAction('active', owner).label, '进入工作推进表')
  assert.equal(canCreateProjectCloseRequest('active', owner), true)
  assert.equal(canCreateProjectCloseRequest('active', member), false)
  assert.equal(getProjectCloseMainAction('pending_close', coach).label, '审核结束申请')
  assert.equal(getProjectCloseMainAction('pending_close', member).label, '查看结束申请')
  assert.equal(canReviewProjectCloseRequest('pending_close', admin), true)
  assert.equal(getProjectCloseMainAction('ended', admin).label, '查看结束档案')
  assert.equal(getProjectCloseMainAction('archived', member).label, '查看归档档案')
})

test('project page exposes new tabs, deep link and safe close entries', () => {
  const source = read('src/features/settings/ProjectsMgmtSection.tsx')
  assert.match(source, /key: 'pending_close', label: '结束审核中', queueLabel: '待企业教练审核'/)
  assert.match(source, /key: 'ended', label: '已结束', queueLabel: '待归档'/)
  assert.match(source, /申请项目结束/)
  assert.match(source, /roles\.isRealOwner \|\| roles\.isSuperAdmin/)
  assert.match(source, /projectId/); assert.match(source, /closeRequestId/)
  assert.match(source, /setCloseFlowProjectId\(projectId\)/)
  assert.doesNotMatch(source, /label: '恢复'/)
  assert.doesNotMatch(source, /handleUnarchive/)
  assert.doesNotMatch(source, /status === 'active'[\s\S]{0,160}label: '归档'/)
})

test('all seven close request APIs match backend methods and paths', () => {
  const source = read('src/api/projects.ts')
  for (const name of ['createProjectCloseRequest', 'getProjectCloseRequests', 'getProjectCloseRequest', 'updateProjectCloseRequest', 'cancelProjectCloseRequest', 'approveProjectCloseRequest', 'rejectProjectCloseRequest']) assert.match(source, new RegExp(`function ${name}\\(`))
  assert.match(source, /apiPost<ProjectCloseRequest>\(`\/api\/projects\/\$\{projectId\}\/close-requests`, payload\)/)
  assert.match(source, /apiGet<ProjectCloseRequest\[]>\(`\/api\/projects\/\$\{projectId\}\/close-requests\$\{query\}`\)/)
  assert.match(source, /apiPatch<ProjectCloseRequest>/)
  for (const suffix of ['cancel', 'approve', 'reject']) assert.match(source, new RegExp(`close-requests/\\$\\{requestId\\}/${suffix}`))
})

test('drawer covers blockers, warnings, permissions, validation and archive', () => {
  const source = read('src/features/settings/ProjectCloseFlowDrawer.tsx')
  assert.match(source, /ApiError/); assert.match(source, /PROJECT_CLOSE_BLOCKED/); assert.match(source, /detail/)
  assert.match(source, /title="暂不能结束"/); assert.match(source, /title="结束前提醒"/)
  assert.match(source, /保存修改/); assert.match(source, /取消申请/); assert.match(source, /批准结束/); assert.match(source, /退回修改/)
  assert.match(source, /status === 'ended' && roles\.isSuperAdmin/); assert.match(source, />归档项目</)
  assert.match(source, /Object\.values\(item\)/); assert.match(source, /window\.confirm\('结束材料尚未保存/)
  assert.doesNotMatch(source, /window\.prompt/)
})

test('change scope remains frontend-only and does not alter routing', () => {
  assert.equal(fs.existsSync(path.join(root, 'src/features/settings/ProjectCloseFlowDrawer.tsx')), true)
  const page = read('src/features/settings/ProjectsMgmtSection.tsx')
  assert.match(page, /getProjects\(true\)/); assert.match(page, /reloadProjects\(\)/)
  assert.match(page, /ProjectCloseFlowDrawer/)
})
