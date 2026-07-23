import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { fetchIssueById, closeIssue, resolveIssue, assignIssueHelper, requestIssueCeo, submitIssueOpinion, ownerConfirmOpinion } from '../api/issues'
import { fetchTargetLogs, type OperationLogItem } from '../api/logs'
import { fetchTasks } from '../api/tasks'
import { fetchSubtasksByProject } from '../api/subtasks'
import type { IssueItem, TaskItem, SubTaskItem } from '../types'
import { useProject } from '../context/ProjectContext'
import { toast } from '../utils/toast'
import { fmtDate, fmtFull } from '../utils/time'

// ============================================================
// Constants (mirrored from IssuesPage in case of future divergence)
// ============================================================
const PRIORITY_STYLE: Record<string, string> = {
  '高': 'bg-red-50 text-red-700 border-red-200',
  '中': 'bg-orange-50 text-orange-700 border-orange-200',
  '低': 'bg-slate-50 text-slate-600 border-slate-200',
}
const STATUS_STYLE: Record<string, { badge: string; dot: string; label: string }> = {
  '待处理': { badge: 'bg-amber-50 text-amber-700 border-amber-200', dot: '#F59E0B', label: '待处理' },
  '待协调': { badge: 'bg-orange-50 text-orange-700 border-orange-200', dot: '#F97316', label: '待协调' },
  '待决策': { badge: 'bg-purple-50 text-purple-700 border-purple-200', dot: '#7C3AED', label: '待决策' },
  '待负责人确认': { badge: 'bg-sky-50 text-sky-700 border-sky-200', dot: '#0EA5E9', label: '待负责人确认' },
  '已解决': { badge: 'bg-emerald-50 text-emerald-700 border-emerald-200', dot: '#10B981', label: '已解决' },
  '已关闭': { badge: 'bg-slate-50 text-slate-500 border-slate-200', dot: '#94A3B8', label: '已关闭' },
}

const ISSUE_FLOW = [
  { key: '待处理', label: '待处理' },
  { key: '待协调', label: '待协调' },
  { key: '待决策', label: '待决策' },
  { key: '待负责人确认', label: '待负责人确认' },
  { key: '已解决', label: '已解决' },
] as const

const FLOW_DOT_COLORS: Record<string, string> = {
  '待处理': '#F59E0B',
  '待协调': '#F97316',
  '待决策': '#7C3AED',
  '待负责人确认': '#0EA5E9',
  '已解决': '#10B981',
}

function getIssueFlowIndex(status: string): number {
  return ISSUE_FLOW.findIndex(s => s.key === status)
}

const LOG_ACTION_MAP: Record<string, string> = {
  issue_create: '创建问题',
  issue_update_status: '更新状态',
  issue_submit_opinion: '提交意见',
  issue_owner_accept_opinion: '负责人确认意见',
  issue_owner_reject_opinion: '负责人退回',
  issue_assign_helper: '指定协助人',
  issue_request_ceo: '请求CEO决策',
  issue_resolve: '标记已解决',
  issue_close: '关闭问题',
  issue_update: '更新问题信息',
}
function LOG_ACTION_CN(action: string): string { return LOG_ACTION_MAP[action] || action }
function LOG_ACTION_COLOR(action: string): string {
  if (action.includes('create')) return '#10B981'
  if (action.includes('close')) return '#EF4444'
  if (action.includes('resolve')) return '#10B981'
  if (action.includes('update_status')) return '#7C3AED'
  if (action.includes('submit_opinion')) return '#F59E0B'
  if (action.includes('owner_accept')) return '#0EA5E9'
  if (action.includes('owner_reject')) return '#EF4444'
  if (action.includes('assign')) return '#8B5CF6'
  if (action.includes('request_ceo')) return '#EC4899'
  return '#94A3B8'
}

function taskNameForId(tasks: TaskItem[], id: number | null | undefined): string {
  if (id == null) return '—'
  const t = tasks.find(x => x.id === id)
  return t ? (t.key_task || `#${id}`) : `#${id}`
}

function keyTaskLabelForIssue(item: IssueItem, subtaskById: Record<number, SubTaskItem>): string {
  if (item.related_subtask_id && subtaskById[item.related_subtask_id]) {
    return subtaskById[item.related_subtask_id].title || '#'
  }
  if (item.related_task_id && subtaskById[item.related_task_id]) {
    return `上级 #${item.related_task_id}`
  }
  return '—'
}

// ============================================================
// Component
// ============================================================

export function IssueDetailPage() {
  const navigate = useNavigate()
  const { issueId } = useParams<{ issueId: string }>()
  const [searchParams] = useSearchParams()
  const projectIdParam = searchParams.get('projectId')
  const parsedId = issueId ? parseInt(issueId, 10) : NaN
  const { projects, currentUser } = useProject()

  const [issue, setIssue] = useState<IssueItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [actionLoading, setActionLoading] = useState('')

  // Logs
  const [issueLogs, setIssueLogs] = useState<OperationLogItem[]>([])
  const [logsLoading, setLogsLoading] = useState(false)

  // Tasks / subtasks for lookup
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [subtasks, setSubtasks] = useState<SubTaskItem[]>([])

  // Load issue + logs
  const loadIssue = useCallback(async () => {
    if (isNaN(parsedId)) return
    setLoading(true)
    setLoadError('')
    try {
      const data = await fetchIssueById(parsedId)
      setIssue(data)
    } catch (err) {
      setLoadError('问题不存在或无权限访问')
    } finally {
      setLoading(false)
    }
  }, [parsedId])

  useEffect(() => { loadIssue() }, [loadIssue])

  // Load logs
  useEffect(() => {
    if (!issue) { setIssueLogs([]); return }
    let cancelled = false
    setLogsLoading(true)
    fetchTargetLogs('issue', issue.id)
      .then((logs) => { if (!cancelled) setIssueLogs(logs) })
      .catch(() => { if (!cancelled) setIssueLogs([]) })
      .finally(() => { if (!cancelled) setLogsLoading(false) })
    return () => { cancelled = true }
  }, [issue?.id])

  // Load tasks for the project
  const projectId = useMemo(() => {
    if (issue?.project_id != null) return issue.project_id
    if (projectIdParam) { const n = Number(projectIdParam); if (Number.isFinite(n)) return n }
    return null
  }, [issue?.project_id, projectIdParam])

  useEffect(() => {
    if (projectId == null) return
    fetchTasks(projectId).then(setTasks).catch(() => setTasks([]))
    fetchSubtasksByProject(projectId).then(setSubtasks).catch(() => setSubtasks([]))
  }, [projectId])

  const subtaskById = useMemo(() => {
    const map: Record<number, SubTaskItem> = {}
    subtasks.forEach(s => { map[s.id] = s })
    return map
  }, [subtasks])

  const currentProject = useMemo(() => {
    return projects.find(p => p.id === projectId)
  }, [projects, projectId])

  const projectName = useMemo(() => {
    return currentProject?.name || `项目 #${projectId}`
  }, [currentProject, projectId])

  const canManageIssues = useMemo(() => {
    if (currentUser?.is_tech_admin) return true
    if (!currentProject) return false
    const roles: string[] = currentProject.user_roles ?? []
    return roles.includes('owner')
  }, [currentUser, currentProject])

  // ── Actions ──
  const doClose = async () => {
    if (!issue) return
    const reason = prompt('关闭原因：')
    const handlerReply = prompt('给上报人的回复（可选）：')
    if (reason == null) return
    setActionLoading('close')
    try {
      await closeIssue(issue.id, reason || undefined, handlerReply || undefined)
      toast.success('已关闭问题')
      loadIssue()
    } catch (e: unknown) {
      toast.error(`关闭失败: ${e instanceof Error ? e.message : '未知错误'}`)
    } finally { setActionLoading('') }
  }
  const doResolve = async () => {
    if (!issue) return
    const resolution = prompt('解决方案：')
    const handlerReply = prompt('给上报人的回复（可选）：')
    if (resolution == null) return
    setActionLoading('resolve')
    try {
      await resolveIssue(issue.id, resolution || undefined, handlerReply || undefined)
      toast.success('已标记为已解决')
      loadIssue()
    } catch (e: unknown) {
      toast.error(`解决失败: ${e instanceof Error ? e.message : '未知错误'}`)
    } finally { setActionLoading('') }
  }
  const doAssignHelper = async () => {
    if (!issue) return
    const helper = prompt('请输入协助人姓名：')
    if (!helper) return
    setActionLoading('assign')
    try {
      await assignIssueHelper(issue.id, helper)
      toast.success(`已指定协助人: ${helper}`)
      loadIssue()
    } catch (e: unknown) {
      toast.error(`指定失败: ${e instanceof Error ? e.message : '未知错误'}`)
    } finally { setActionLoading('') }
  }
  const doRequestCeo = async () => {
    if (!issue) return
    const decisionBy = prompt('需要由谁决策？')
    if (!decisionBy) return
    const note = prompt('备注信息（可选）：') || ''
    setActionLoading('ceo')
    try {
      await requestIssueCeo(issue.id, decisionBy, note)
      toast.success('已上报请求决策')
      loadIssue()
    } catch (e: unknown) {
      toast.error(`上报失败: ${e instanceof Error ? e.message : '未知错误'}`)
    } finally { setActionLoading('') }
  }
  const doSubmitOpinion = async () => {
    if (!issue) return
    const opinion = prompt('请输入统筹/教练处理意见：')
    if (!opinion) return
    setActionLoading('opinion')
    try {
      await submitIssueOpinion(issue.id, opinion)
      toast.success('意见已提交')
      loadIssue()
    } catch (e: unknown) {
      toast.error(`提交失败: ${e instanceof Error ? e.message : '未知错误'}`)
    } finally { setActionLoading('') }
  }
  const doOwnerConfirm = async (accepted: boolean) => {
    if (!issue) return
    const note = accepted ? (prompt('确认备注（可选，回车跳过）：') || '') : (prompt('退回原因：') || '')
    if (!accepted && !note) return
    setActionLoading(accepted ? 'accept' : 'reject')
    try {
      await ownerConfirmOpinion(issue.id, accepted, note)
      toast.success(accepted ? '已确认，问题已解决' : '已退回')
      loadIssue()
    } catch (e: unknown) {
      toast.error(`操作失败: ${e instanceof Error ? e.message : '未知错误'}`)
    } finally { setActionLoading('') }
  }

  // Derived
  const st = issue ? (STATUS_STYLE[issue.status || ''] || STATUS_STYLE['待处理']) : STATUS_STYLE['待处理']
  const terminal = issue?.status === '已解决' || issue?.status === '已关闭'
  const isClosed = issue?.status === '已关闭'
  const isPendingOwner = issue?.status === '待负责人确认'
  const isPendingDecision = issue?.status === '待决策'
  const flowIndex = getIssueFlowIndex(issue?.status || '待处理')

  // Back handler
  const handleBack = () => {
    const fromList = searchParams.get('from')
    if (fromList) {
      navigate(fromList)
    } else {
      navigate(-1 as unknown as string, { replace: true })
    }
  }

  if (isNaN(parsedId) || loadError) {
    return (
      <div className="min-h-full flex flex-col items-center justify-center p-8">
        <div className="text-center">
          <p className="text-lg font-bold text-slate-700 mb-2">{loadError || '无效的问题ID'}</p>
          <button onClick={() => navigate(-1 as unknown as string, { replace: true })} className="text-sm text-purple-600 underline">返回上一页</button>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="min-h-full flex items-center justify-center">
        <p className="text-sm text-slate-400">加载中...</p>
      </div>
    )
  }

  if (!issue) {
    return (
      <div className="min-h-full flex flex-col items-center justify-center p-8">
        <p className="text-lg font-bold text-slate-700 mb-2">问题不存在</p>
        <button onClick={handleBack} className="text-sm text-purple-600 underline">返回列表</button>
      </div>
    )
  }

  return (
    <div className="min-h-full flex flex-col bg-slate-50">
      {/* ── Top bar ── */}
      <header className="flex items-center gap-3 px-5 py-3 bg-white border-b border-slate-200 shrink-0">
        <button
          onClick={handleBack}
          className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 font-medium transition-colors"
          title="返回问题列表"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          返回列表
        </button>
        <span className="text-slate-300">|</span>
        <span className="text-xs text-slate-500 font-mono">#{issue.id}</span>
        <span className="text-xs text-slate-400">{projectName}</span>
      </header>

      {/* ── Body ── */}
      <div className="flex-1 overflow-auto">
        <div className="max-w-4xl mx-auto p-6 space-y-6">

          {/* ── Issue Header ── */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <h1 className="text-xl font-bold text-slate-900 leading-snug">{issue.description || '未命名问题'}</h1>
                <div className="flex flex-wrap items-center gap-2 mt-3">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold border ${PRIORITY_STYLE[issue.priority || ''] || PRIORITY_STYLE['中']}`}>
                    {issue.priority || '中'}
                  </span>
                  <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold border ${st.badge}`}>
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: st.dot }}></span>
                    {issue.status || '待处理'}
                  </span>
                  {issue.issue_type && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
                      {issue.issue_type}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* ── Status Flow Progress ── */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">处理进度</h3>
            {isClosed ? (
              <p className="text-sm text-slate-400">该问题已关闭</p>
            ) : (
              <div className="flex items-center justify-between">
                {ISSUE_FLOW.map((step, idx) => {
                  const isDone = idx < flowIndex
                  const isActive = idx === flowIndex
                  const isFuture = idx > flowIndex
                  return (
                    <div key={step.key} className="flex flex-col items-center flex-1 relative">
                      {/* connector line before this step */}
                      {idx > 0 && (
                        <div className="absolute top-[14px] right-1/2 left-0 h-[3px] -translate-y-1/2">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{ background: idx <= flowIndex ? FLOW_DOT_COLORS[step.key] : '#E2E8F0' }}
                          />
                        </div>
                      )}
                      {/* dot */}
                      <span
                        className="relative z-10 inline-flex items-center justify-center rounded-full font-bold text-xs shrink-0 transition-all"
                        style={{
                          width: isActive ? 36 : 28,
                          height: isActive ? 36 : 28,
                          background: isActive ? FLOW_DOT_COLORS[step.key] : isDone ? FLOW_DOT_COLORS[step.key] : '#F1F5F9',
                          color: isActive ? '#fff' : isDone ? '#fff' : '#94A3B8',
                          border: isActive ? `3px solid ${FLOW_DOT_COLORS[step.key]}55` : isDone ? 'none' : '2px solid #E2E8F0',
                          boxShadow: isActive ? `0 0 0 4px ${FLOW_DOT_COLORS[step.key]}22` : 'none',
                        }}
                      >
                        {isDone ? '✓' : isActive ? idx + 1 : idx + 1}
                      </span>
                      <span
                        className="mt-2 text-xs font-semibold"
                        style={{ color: isActive ? FLOW_DOT_COLORS[step.key] : isDone ? '#64748B' : '#CBD5E1' }}
                      >
                        {step.label}
                      </span>
                      {/* Date under step */}
                      {idx <= flowIndex && (
                        <span className="text-[10px] text-slate-400 mt-0.5">
                          {idx === flowIndex
                            ? (issue.updated_at ? fmtDate(issue.updated_at) : '—')
                            : '···'}
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* ── Issue Info Grid + Timeline side by side (desktop) ── */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            {/* Left: Issue details */}
            <div className="lg:col-span-3 space-y-6">
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">基本信息</h3>
                <dl className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <dt className="text-xs text-slate-400 mb-0.5">负责人</dt>
                    <dd className="font-semibold text-slate-800">{issue.owner || '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400 mb-0.5">协助人</dt>
                    <dd className="font-semibold text-slate-800">{issue.helper || '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400 mb-0.5">上报人</dt>
                    <dd className="font-semibold text-slate-800">{issue.reporter || '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400 mb-0.5">预计解决</dt>
                    <dd className="font-semibold text-slate-800">{issue.expected_resolve_time || '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400 mb-0.5">关联重点工作</dt>
                    <dd className="text-slate-700">{taskNameForId(tasks, issue.related_task_id)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400 mb-0.5">关联关键任务</dt>
                    <dd className="text-slate-700">{keyTaskLabelForIssue(issue, subtaskById)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400 mb-0.5">创建时间</dt>
                    <dd className="text-slate-700">{fmtFull(issue.created_at)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-400 mb-0.5">更新时间</dt>
                    <dd className="text-slate-700">{fmtFull(issue.updated_at)}</dd>
                  </div>
                  {issue.need_decision_by && (
                    <div className="col-span-2">
                      <dt className="text-xs text-slate-400 mb-0.5">需决策人</dt>
                      <dd className="font-bold text-purple-700">{issue.need_decision_by}</dd>
                    </div>
                  )}
                </dl>
              </div>

              {/* Resolution / handler_reply */}
              {(issue.resolution || issue.handler_reply) && (
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                  <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">处理结论</h3>
                  {issue.resolution && (
                    <div className="mb-3 p-4 rounded-lg" style={{ background: '#F0FDF4', border: '1px solid #BBF7D0' }}>
                      <p className="text-xs text-slate-500 mb-1">{isPendingDecision ? '决策结论' : '处理结论'}</p>
                      <p className="text-sm text-slate-700">{issue.resolution}</p>
                    </div>
                  )}
                  {issue.handler_reply && (
                    <div className="p-4 rounded-lg" style={{ background: '#FFFBEB', border: '1px solid #FDE68A' }}>
                      <p className="text-xs text-slate-500 mb-1">回复给上报人</p>
                      <p className="text-sm text-amber-800">{issue.handler_reply}</p>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Right: Action buttons */}
            <div className="lg:col-span-2 space-y-4">
              {/* Action area */}
              {!terminal && (
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
                  <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">操作</h3>
                  {!canManageIssues ? (
                    <p className="text-xs text-slate-400 text-center py-3">仅负责人和企业教练可执行处理动作</p>
                  ) : (
                  <div className="space-y-2">
                    {/* Assign helper */}
                    <button
                      onClick={doAssignHelper}
                      disabled={!!actionLoading}
                      className="w-full text-left px-3 py-2.5 rounded-lg border border-slate-200 text-sm font-semibold text-indigo-600 hover:bg-indigo-50 transition-colors disabled:opacity-50"
                    >
                      👥 指定协助人
                    </button>

                    {/* Submit opinion (for 待处理 / 待协调) */}
                    {!isPendingOwner && !isPendingDecision && (
                      <button
                        onClick={doSubmitOpinion}
                        disabled={!!actionLoading}
                        className="w-full text-left px-3 py-2.5 rounded-lg border border-slate-200 text-sm font-semibold text-purple-600 hover:bg-purple-50 transition-colors disabled:opacity-50"
                      >
                        💬 提交处理意见
                      </button>
                    )}

                    {/* Request CEO decision */}
                    <button
                      onClick={doRequestCeo}
                      disabled={!!actionLoading}
                      className="w-full text-left px-3 py-2.5 rounded-lg border border-slate-200 text-sm font-semibold text-pink-600 hover:bg-pink-50 transition-colors disabled:opacity-50"
                    >
                      ⚡ 请求CEO决策
                    </button>

                    {/* Owner confirm */}
                    {isPendingOwner && (
                      <>
                        <button
                          onClick={() => doOwnerConfirm(true)}
                          disabled={!!actionLoading}
                          className="w-full text-left px-3 py-2.5 rounded-lg border border-emerald-200 bg-emerald-50 text-sm font-semibold text-emerald-700 hover:bg-emerald-100 transition-colors disabled:opacity-50"
                        >
                          ✅ 确认并标记已解决
                        </button>
                        <button
                          onClick={() => doOwnerConfirm(false)}
                          disabled={!!actionLoading}
                          className="w-full text-left px-3 py-2.5 rounded-lg border border-red-200 bg-red-50 text-sm font-semibold text-red-700 hover:bg-red-100 transition-colors disabled:opacity-50"
                        >
                          ↩️ 退回重新处理
                        </button>
                      </>
                    )}

                    {/* Resolve */}
                    {!isPendingOwner && (
                      <button
                        onClick={doResolve}
                        disabled={!!actionLoading}
                        className="w-full text-left px-3 py-2.5 rounded-lg border border-emerald-200 bg-emerald-50 text-sm font-semibold text-emerald-700 hover:bg-emerald-100 transition-colors disabled:opacity-50"
                      >
                        ✓ 标记为已解决
                      </button>
                    )}

                    {/* Close */}
                    <button
                      onClick={doClose}
                      disabled={!!actionLoading}
                      className="w-full text-left px-3 py-2.5 rounded-lg border border-red-200 text-sm font-semibold text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
                    >
                      ✕ 关闭问题
                    </button>
                  </div>
                  )}
                  {actionLoading && (
                    <p className="mt-3 text-center text-xs text-slate-400">操作中...</p>
                  )}
                </div>
              )}

              {/* Operation log timeline */}
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">
                  操作记录
                  {logsLoading && <span className="ml-1 font-normal normal-case tracking-normal text-slate-400 animate-pulse">加载中...</span>}
                </h3>
                {issueLogs.length === 0 && !logsLoading ? (
                  <p className="text-xs text-slate-400 py-2">暂无操作记录</p>
                ) : (
                  <div className="relative pl-6 space-y-4">
                    {issueLogs.map((log, idx) => (
                      <div key={log.id ?? idx} className="relative pb-1">
                        {/* timeline dot */}
                        <span
                          className="absolute left-[-16px] top-1.5 w-2.5 h-2.5 rounded-full border-2 bg-white"
                          style={{ borderColor: LOG_ACTION_COLOR(log.action || '') }}
                        />
                        {/* connector line */}
                        {idx < issueLogs.length - 1 && (
                          <span className="absolute left-[-12px] top-4 w-[2px] h-[calc(100%-4px)]" style={{ background: '#E2E8F0' }} />
                        )}
                        <div className="text-xs">
                          <p className="font-bold text-slate-700">
                            {LOG_ACTION_CN(log.action || '')}
                            <span className="ml-1.5 font-normal text-slate-400">{fmtFull(log.created_at) || '—'}</span>
                          </p>
                          <p className="text-slate-500 mt-0.5">
                            <span className="font-semibold text-slate-600">{log.operator || '系统'}</span>
                            {log.note && (
                              <span className="ml-1 text-slate-500">· {log.note}</span>
                            )}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Bottom padding */}
          <div className="h-8" />
        </div>
      </div>
    </div>
  )
}

export default IssueDetailPage
