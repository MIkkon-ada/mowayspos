import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

const CONFIRM = 'src/pages/ConfirmPage.tsx'
const PAGE = 'src/pages/VoiceUpdatePage.tsx'
const HISTORY = 'src/features/voice-update/VoiceUpdateHistoryDrawer.tsx'
const DETAIL = 'src/features/voice-update/VoiceUpdateDetailDrawer.tsx'
const SUBMIT = 'src/features/voice-update/VoiceUpdateSubmitPanel.tsx'
const HISTORY_HOOK = 'src/features/voice-update/useVoiceHistory.ts'
const ROUTE_CONFIG = 'src/domain/routeConfig.ts'
const PERMISSIONS = 'src/domain/permissions.ts'

async function loadHistoryFilterModel() {
  const source = read(HISTORY)
  const start = source.indexOf('export type HistoryFilter')
  const end = source.indexOf('export function VoiceUpdateHistoryDrawer')
  assert.ok(start >= 0 && end > start, 'history filter helpers must be exported before the drawer')
  const helperSource = source.slice(start, end)
  const ssStub = `
    const SS = {
      S_NEW: '待确认', S_PENDING_OWNER: '待负责人审核', S_RETURNED: '已打回提交人',
      S_WITHDRAWN: '已撤回', S_PERMANENTLY_REJECTED: '不入库', S_WAITING_COORDINATOR: '已转交统筹人',
      S_COORDINATOR_GIVEN: '统筹人已反馈', S_WAITING_CEO: '待CEO决策', S_CEO_DECIDED: 'CEO已批示',
      S_CONFIRMED: '已入库', S_NEEDS_REVISION: '需修改',
      normalize: (status) => status || '待确认',
      DISPLAY_LABEL: {}, STATUS_BADGE_CLASS: {},
      RETURNED_TO_SUBMITTER: new Set(['已打回提交人']),
      CONFIRMED_AND_STORED: new Set(['已入库']),
    }
  `
  const js = ts.transpileModule(`${ssStub}\n${helperSource}`, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
}

test('AI confirmation center contains reviewer views only', () => {
  const source = read(CONFIRM)
  assert.doesNotMatch(source, /ConfirmViewMode[^\n]*mine/)
  assert.doesNotMatch(source, /fetchMyUpdates/)
  assert.doesNotMatch(source, /我的提交记录/)
  assert.doesNotMatch(source, /viewMode\s*===\s*['"]mine['"]/)
  // Tab labels shown in empty states (not explicit tab definitions)
  for (const label of ['待确认事项', '暂无待统筹事项', '暂无待决策事项']) assert.match(source, new RegExp(label))
  // View mode enum only has reviewer modes — no 'mine'
  assert.match(source, /viewMode === 'ceo'/)
  assert.match(source, /viewMode === 'coordinator'/)
  assert.match(source, /viewMode === 'all'/)
  for (const handler of ['handleConfirm', 'handleDecision', 'handleTaskCardDecision', 'handleCoordinatorFeedback', 'handleCoachSubmissionDecide']) {
    assert.match(source, new RegExp(`\\b${handler}\\b`))
  }
})

test('work report owns cross-project current-user history and the history submission label', () => {
  const page = read(PAGE)
  const hook = read(HISTORY_HOOK)
  assert.match(page, />历史提交<\/button>/)
  assert.match(hook, /fetchMyUpdates\(\)/)
  assert.doesNotMatch(hook, /slice\(0,\s*20\)/)
})

test('history submission filter has the exact four labels and required status groups', async () => {
  const source = read(HISTORY)
  for (const label of ['全部', '审核中', '已退回', '已确认']) assert.match(source, new RegExp(label))
  assert.doesNotMatch(source, /['"]草稿['"]\s*\|\s*['"]已提交['"]/)

  const { matchesHistoryFilter } = await loadHistoryFilterModel()
  const group = (confirm_status) => ({ aggregateStatus: confirm_status, items: [{ confirm_status }], key: 'test', batchId: null })
  for (const status of ['待确认', '待负责人审核', '已转交统筹人', '统筹人已反馈', '待CEO决策', 'CEO已批示', '需修改']) {
    assert.equal(matchesHistoryFilter(group(status), '审核中'), true, `${status} must be under review`)
  }
  assert.equal(matchesHistoryFilter(group('已打回提交人'), '已退回'), true)
  assert.equal(matchesHistoryFilter(group('已入库'), '已确认'), true)
  for (const status of ['已撤回', '不入库']) {
    assert.equal(matchesHistoryFilter(group(status), '全部'), true)
    assert.equal(matchesHistoryFilter(group(status), '审核中'), false)
    assert.equal(matchesHistoryFilter(group(status), '已退回'), false)
    assert.equal(matchesHistoryFilter(group(status), '已确认'), false)
  }
})

test('history rows show project time source and normalized review state', () => {
  const source = read(HISTORY)
  assert.match(source, /project/)
  assert.match(source, /project_name/)
  assert.match(source, /created_at/)
  assert.match(source, /source_type/)
  assert.match(source, /normalizeHistoryStatus\(item\.confirm_status\)/)
})

test('returned history detail reuses the existing resubmitSubmission API client', () => {
  const source = `${read(PAGE)}\n${read(DETAIL)}`
  assert.match(source, /resubmitSubmission/)
  assert.match(source, /补充并重新提交/)
})

test('submission success opens history and no longer navigates submitters to confirmations', () => {
  const source = `${read(SUBMIT)}\n${read(PAGE)}`
  assert.match(source, /查看提交记录/)
  assert.doesNotMatch(source, /前往 AI 确认中心/)
  assert.doesNotMatch(source, /navigate\(`\/work\/confirmations/)
  assert.match(source, /setHistoryOpen\(true\)/)
})

test('confirmation navigation is visible to every reviewer role and hidden from ordinary members', () => {
  const routeConfig = read(ROUTE_CONFIG)
  const permissions = read(PERMISSIONS)
  assert.match(routeConfig, /canViewConfirmCenter/)
  assert.match(routeConfig, /visible:\s*canViewConfirmCenter/)
  for (const role of ['owner', 'coordinator', 'project_ceo']) assert.match(permissions, new RegExp(`['"]${role}['"]`))
  assert.match(permissions, /isSuperAdmin/)
})

