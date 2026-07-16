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

async function loadPermissions() {
  const source = read('src/domain/permissions.ts')
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

test('project lifecycle page admits participants without granting project management', async () => {
  const { canManageProjects, canViewProjectManagement } = await loadPermissions()
  const normalUser = { is_tech_admin: false, is_ceo: false }
  const companyCeoUser = { is_tech_admin: false, is_ceo: true }
  const superAdminUser = { is_tech_admin: true, is_ceo: false }

  assert.equal(canViewProjectManagement(normalUser, []), false)
  assert.equal(canViewProjectManagement(normalUser, ['member']), true)
  assert.equal(canViewProjectManagement(normalUser, ['coordinator']), true)
  assert.equal(canViewProjectManagement(normalUser, ['owner']), true)
  assert.equal(canViewProjectManagement(normalUser, ['project_ceo']), true)
  assert.equal(canViewProjectManagement(companyCeoUser, []), true)
  assert.equal(canViewProjectManagement(superAdminUser, []), true)

  assert.equal(canManageProjects(normalUser, ['member']), false)
  assert.equal(canManageProjects(normalUser, ['coordinator']), false)
  assert.equal(canManageProjects(normalUser, ['owner']), false)
  assert.equal(canManageProjects(normalUser, ['project_ceo']), true)
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

test('drawer invalidates stale loads and clears all project-bound state before fetching', () => {
  const source = read('src/features/settings/ProjectCloseFlowDrawer.tsx')
  assert.match(source, /useRef/)
  assert.match(source, /loadGenerationRef/)
  assert.match(source, /const generation = \+\+loadGenerationRef\.current/)
  assert.match(source, /const emptyForm = freshEmptyForm\(\)[\s\S]{0,180}setRequest\(null\)[\s\S]{0,120}setForm\(emptyForm\)[\s\S]{0,180}setReviewComment\(''\)/)
  assert.match(source, /generation !== loadGenerationRef\.current/)
  assert.match(source, /loadGenerationRef\.current \+= 1[\s\S]{0,180}onClose\(\)/)
})

test('failed deep-link loads cannot expose an active create form', () => {
  const source = read('src/features/settings/ProjectCloseFlowDrawer.tsx')
  assert.match(source, /const \[loadFailed, setLoadFailed\] = useState\(false\)/)
  assert.match(source, /setLoadFailed\(true\)/)
  assert.match(source, /canCreate && !loadFailed/)
  assert.match(source, /!loading && \(\(canCreate && !loadFailed\) \|\| request\)/)
})

test('mutation success is retained when refresh fails and disables every write action', () => {
  const source = read('src/features/settings/ProjectCloseFlowDrawer.tsx')
  assert.match(source, /mutationCommittedButRefreshFailed/)
  const mutationAwait = source.indexOf('result = await action()')
  const mutationCatch = source.indexOf('} catch (error) {', mutationAwait)
  const mutationReturn = source.indexOf('return', mutationCatch)
  const successToast = source.indexOf('toast.success(success)', mutationReturn)
  const refreshTry = source.indexOf('try {', successToast)
  const refreshAwait = source.indexOf('await onChanged', refreshTry)
  assert.ok(mutationAwait > 0 && mutationAwait < mutationCatch && mutationCatch < mutationReturn)
  assert.ok(mutationReturn < successToast && successToast < refreshTry && refreshTry < refreshAwait)
  assert.match(source, /操作已成功，但项目状态刷新失败，请刷新页面后继续。/)
  assert.match(source, /操作已成功。当前页面状态未刷新，请刷新页面后继续，勿重复提交。/)
  assert.match(source, /const writesDisabled = Boolean\(busyAction\) \|\| mutationCommittedButRefreshFailed/)
  assert.ok((source.match(/disabled=\{writesDisabled\}/g) ?? []).length >= 6)
})

test('dirty state includes unsaved review comments and successful mutation resets its baseline', () => {
  const source = read('src/features/settings/ProjectCloseFlowDrawer.tsx')
  assert.match(source, /initialReviewComment/)
  assert.match(source, /JSON\.stringify\(form\) !== initialForm \|\| reviewComment !== initialReviewComment/)
  assert.match(source, /setReviewComment\(nextReviewComment\)[\s\S]{0,160}setInitialReviewComment\(nextReviewComment\)/)
})
