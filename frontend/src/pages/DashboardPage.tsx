import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getOverview, exportWeeklyReport } from '../api/dashboard'
import { ApiError } from '../api/client'
import { OwnerSubmitModal } from '../features/settings/OwnerSubmitModal'
import { toast } from '../utils/toast'
import { useProject } from '../context/ProjectContext'
import {
  canShowProjectApproveAction,
  canShowProjectSubmitAction,
  getProjectPrimaryStatus,
  getProjectStatusBadge,
} from '../domain/projectLifecycleStatus'
import type { DashboardOverview, Project } from '../types'
import Chart from 'chart.js/auto'
import { fmtMonth, fmtPlanTime } from '../utils/time'
import { Skel, SkeletonStatCard } from '../components/Skeleton'

type DashboardScope = 'global' | 'my' | 'project'

function asNumber(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function mergeRecords(overviews: DashboardOverview[], path: (overview: any) => unknown): Array<Record<string, unknown>> {
  return overviews.flatMap((overview) => {
    const value = path(overview)
    return Array.isArray(value) ? value as Array<Record<string, unknown>> : []
  })
}

function aggregateDashboardOverviews(projects: Project[], overviews: DashboardOverview[]): DashboardOverview {
  const projectCards = mergeRecords(overviews, (overview) => overview.project_cards)
  const roleQueueItems = mergeRecords(overviews, (overview) => overview.role_queue?.items)
  const recentTasks = mergeRecords(overviews, (overview) => overview.recent?.tasks)
  const delayedTasks = mergeRecords(overviews, (overview) => overview.recent?.delayed_tasks)
  const recentIssues = mergeRecords(overviews, (overview) => overview.recent?.issues)
  const recentSubmissions = mergeRecords(overviews, (overview) => overview.recent?.submissions)
  const latestAchievements = mergeRecords(overviews, (overview) => overview.achievement_stats?.recent_achievements)

  const taskStats = {
    total_tasks: overviews.reduce((sum, item) => sum + asNumber(item.task_stats?.total_tasks), 0),
    not_started: overviews.reduce((sum, item) => sum + asNumber(item.task_stats?.not_started), 0),
    in_progress: overviews.reduce((sum, item) => sum + asNumber(item.task_stats?.in_progress), 0),
    completed: overviews.reduce((sum, item) => sum + asNumber(item.task_stats?.completed), 0),
    delayed: overviews.reduce((sum, item) => sum + asNumber(item.task_stats?.delayed), 0),
    paused: overviews.reduce((sum, item) => sum + asNumber(item.task_stats?.paused), 0),
  }

  return {
    project: { id: null, name: '我的项目' },
    access: {
      can_view_decisions: overviews.some((item: any) => Boolean(item.access?.can_view_decisions)),
      can_view_confirmation_center: overviews.some((item: any) => Boolean(item.access?.can_view_confirmation_center)),
    },
    filters: {
      projects: projects.map((project) => project.name),
      owners: [],
      statuses: ['未开始', '推进中', '已完成', '延期', '暂缓'],
    },
    task_stats: taskStats,
    achievement_stats: {
      total_achievements: overviews.reduce((sum, item) => sum + asNumber(item.achievement_stats?.total_achievements), 0),
      recent_achievements: latestAchievements.slice(0, 10),
    },
    issue_stats: {
      total_issues: overviews.reduce((sum, item) => sum + asNumber(item.issue_stats?.total_issues), 0),
      open_issues: overviews.reduce((sum, item) => sum + asNumber(item.issue_stats?.open_issues), 0),
      high_priority_issues: overviews.reduce((sum, item) => sum + asNumber(item.issue_stats?.high_priority_issues), 0),
      waiting_ceo_decision: overviews.reduce((sum, item) => sum + asNumber(item.issue_stats?.waiting_ceo_decision), 0),
    },
    recent: {
      submissions: recentSubmissions.slice(0, 10),
      tasks: recentTasks.slice(0, 10),
      issues: recentIssues.slice(0, 10),
      delayed_tasks: delayedTasks.slice(0, 10),
    } as any,
    project_cards: projectCards,
    role_queue: {
      type: 'in_progress',
      count: roleQueueItems.length,
      items: roleQueueItems.slice(0, 10),
    },
  }
}

export function DashboardPage() {
  const { currentProjectId, projects, currentProject, currentProjectRoles, currentUser } = useProject()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const rawProjectId = searchParams.get('projectId')
  const urlProjectId = rawProjectId && Number.isFinite(Number(rawProjectId)) ? Number(rawProjectId) : null
  const canViewGlobalDashboard = !!(currentUser?.is_tech_admin || currentUser?.is_ceo || currentUser?.can_view_all)
  const managedDashboardProjects = projects.filter((project) =>
    project.user_roles?.some((role) => ['owner', 'coordinator', 'project_ceo'].includes(role)),
  )
  const hasProjectDashboardRole = managedDashboardProjects.length > 0
  const canViewMyDashboard = canViewGlobalDashboard || hasProjectDashboardRole

  function initialDashboardScope(): DashboardScope {
    if (urlProjectId !== null) return 'project'
    if (canViewGlobalDashboard) return 'global'
    if (hasProjectDashboardRole) return 'my'
    return 'my'
  }

  // 独立的仪表盘筛选：global = 全部项目，my = 我的项目汇总，project = 单项目。
  // 项目角色默认进入“我的项目”汇总，不请求真正全局 overview。
  const [scopeMode, setScopeMode] = useState<DashboardScope>(() => initialDashboardScope())
  const [scopeId, setScopeId] = useState<number | null>(() => urlProjectId)

  // 月份筛选：生成最近 6 个月选项
  function buildMonthOptions(): string[] {
    const opts: string[] = []
    const d = new Date()
    for (let i = 0; i < 6; i++) {
      opts.push(`${d.getFullYear()}年${d.getMonth() + 1}月`)
      d.setMonth(d.getMonth() - 1)
    }
    return opts
  }
  const monthOptions = buildMonthOptions()
  const [selectedMonth, setSelectedMonth] = useState<string>('')
  const [exportLoading, setExportLoading] = useState(false)
  const [showNotif, setShowNotif] = useState(false)
  const notifRef = useRef<HTMLDivElement>(null)

  const [data, setData] = useState<DashboardOverview | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const chartRef = useRef<HTMLCanvasElement>(null)
  const chartInstance = useRef<Chart | null>(null)
  const shouldBlockDashboardLoading = !canViewMyDashboard && scopeMode === 'my'

  // ── 顶层渲染状态 ──
  // blocked:       shouldBlockDashboardLoading → 显示阻断提示，不请求数据
  // initialLoading：首次加载尚无可用数据 → 只显示骨架
  // errorWithNoData：无历史数据且加载失败 → 只显示错误
  // dataReady:     已有可用数据 → 展示正式内容（refreshing / refreshError 是其上的覆盖提示，不切换顶层状态）
  const dataReady = data !== null && !shouldBlockDashboardLoading
  const initialLoading = loading && data === null && loadError === null && !shouldBlockDashboardLoading
  const errorWithNoData = loadError !== null && data === null && !shouldBlockDashboardLoading
  // dataReady 上的提示性子状态
  const refreshing = loading && data !== null && !shouldBlockDashboardLoading
  const refreshError = loadError !== null && data !== null && !shouldBlockDashboardLoading

  useEffect(() => {
    const nextScopeMode = initialDashboardScope()
    const nextScopeId = nextScopeMode === 'project' ? urlProjectId : null
    if (nextScopeMode !== scopeMode) {
      setScopeMode(nextScopeMode)
    }
    if (nextScopeId !== scopeId) {
      setScopeId(nextScopeId)
    }
  }, [urlProjectId, canViewGlobalDashboard, hasProjectDashboardRole, managedDashboardProjects.length])

  // 切换筛选时，同步更新驾驶舱 URL，保留在 /home/dashboard 自己的项目范围内。
  function handleScopeChange(val: string) {
    if (val === 'global') {
      if (!canViewGlobalDashboard) return
      setScopeMode('global')
      setScopeId(null)
      navigate('/home/dashboard')
    } else if (val === 'my') {
      setScopeMode('my')
      setScopeId(null)
      navigate('/home/dashboard')
    } else {
      const id = Number(val)
      setScopeMode('project')
      setScopeId(id)
      navigate(`/home/dashboard?projectId=${id}`)
    }
  }

  async function loadMyProjectDashboard(cancelledRef: { cancelled: boolean }) {
    if (managedDashboardProjects.length === 0) {
      setData(null)
      setLoadError('请先选择项目后查看驾驶舱')
      return
    }
    const results = await Promise.allSettled(
      managedDashboardProjects.map((project) => getOverview(project.id, selectedMonth)),
    )
    if (cancelledRef.cancelled) return
    results.forEach((result, index) => {
      if (result.status === 'rejected') {
        console.warn('项目驾驶舱数据加载失败', managedDashboardProjects[index]?.id, result.reason)
      }
    })
    const fulfilled = results
      .filter((result): result is PromiseFulfilledResult<DashboardOverview> => result.status === 'fulfilled')
      .map((result) => result.value)
    if (fulfilled.length === 0) {
      setData(null)
      setLoadError('暂无可查看的项目驾驶舱数据。')
      return
    }
    setData(aggregateDashboardOverviews(managedDashboardProjects, fulfilled))
    setLoadError(null)
  }

  // 拉数据：global 查全局；my 按当前用户可访问项目逐个查并前端聚合；project 查单项目。
  useEffect(() => {
    const cancelledRef = { cancelled: false }
    if (shouldBlockDashboardLoading) {
      setData(null)
      setLoading(false)
      setLoadError('普通成员请从我的任务查看个人工作')
      return () => { cancelledRef.cancelled = true }
    }
    setLoadError(null)
    setLoading(true)
    const load = scopeMode === 'my'
      ? loadMyProjectDashboard(cancelledRef)
      : getOverview(scopeMode === 'global' ? undefined : scopeId, selectedMonth)
        .then((d) => { if (!cancelledRef.cancelled) { setData(d); setLoadError(null) } })
    load
      .catch((err) => {
        if (cancelledRef.cancelled) return
        if (err instanceof ApiError && err.status === 403) {
          setLoadError(scopeMode === 'global' ? '你没有权限查看全局驾驶舱，请选择项目查看。' : '你没有权限查看该项目驾驶舱。')
          return
        }
        setLoadError('数据加载失败，请稍后重试。')
      })
      .finally(() => { if (!cancelledRef.cancelled) setLoading(false) })
    return () => { cancelledRef.cancelled = true }
  }, [scopeMode, scopeId, selectedMonth, shouldBlockDashboardLoading, projects])

  async function handleExport() {
    if (scopeMode === 'my') {
      toast.error('请选择单个项目后导出周报；多项目周报将在后续聚合导出中支持。')
      return
    }
    if (scopeMode === 'global' && !canViewGlobalDashboard) {
      toast.error('你没有权限查看全局驾驶舱，请选择项目查看。')
      return
    }
    setExportLoading(true)
    try {
      await exportWeeklyReport(scopeMode === 'global' ? null : scopeId, selectedMonth)
    } catch {
      toast.error('导出失败，请稍后重试')
    } finally {
      setExportLoading(false)
    }
  }

  const stats = data?.task_stats ?? {}
  const total = stats.total_tasks ?? 0
  const inProgress = stats.in_progress ?? 0
  const completed = stats.completed ?? 0
  const delayed = stats.delayed ?? 0
  const paused = stats.paused ?? 0
  const notStarted = stats.not_started ?? 0
  const achievements = (data?.achievement_stats?.total_achievements as number) ?? 0
  const pendingDecisions = data?.issue_stats?.waiting_ceo_decision ?? 0
  const canViewDecisions = (data as any)?.access?.can_view_decisions ?? false

  function projectNameFromRecord(record: any) {
    if (!record) return ""
    const matched = record.project_id != null ? projects.find((p) => p.id === record.project_id) : null
    return matched?.name ?? record.special_project ?? record.related_special_project ?? record.name ?? ""
  }

  // 专项进度：用 project_cards 里后端算好的 completion_rate
  const completionMap = new Map<string, { rate: number; done: number; total: number }>()
  ;(data?.project_cards as any[] ?? []).forEach((card: any) => {
    const name = projectNameFromRecord(card)
    if (name) completionMap.set(name, {
      rate:  card.completion_rate ?? 0,
      done:  card.completed_count ?? 0,
      total: card.task_count ?? 0,
    })
  })

  // 甜甜圈图
  useEffect(() => {
    if (!chartRef.current) return
    chartInstance.current?.destroy()
    chartInstance.current = new Chart(chartRef.current, {
      type: 'doughnut',
      data: {
        labels: ['未启动', '进行中', '已完成', '延期', '暂缓'],
        datasets: [{
          data: [notStarted, inProgress, completed, delayed, paused],
          backgroundColor: ['#9CA3AF', '#2563EB', '#059669', '#DC2626', '#D97706'],
          borderWidth: 2,
          borderColor: '#fff',
        }],
      },
      options: {
        cutout: '72%',
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (ctx) => ` ${ctx.label}: ${ctx.parsed} 项` } },
        },
        animation: { animateRotate: true, duration: 800 },
      },
    })
    return () => { chartInstance.current?.destroy() }
  }, [notStarted, inProgress, completed, delayed, paused])

  // ── 通知数据 ────────────────────────────────────────────────
  const delayedTasks: any[]   = (data as any)?.recent?.delayed_tasks ?? []
  const queue: any            = (data as any)?.role_queue ?? {}
  const qItems: any[]         = queue.items ?? []
  const qCount: number        = queue.count ?? 0
  const qType: string         = queue.type ?? ''
  const QUEUE_LABEL: Record<string, string> = {
    pending_decisions:   '需决策事项',
    pending_review:      '待审核内容',
    pending_coordinator: '待给出建议',
    in_progress:         '流程推进中',
  }
  const notifTotal = delayedTasks.length + (canViewDecisions ? pendingDecisions : qCount)

  // 点击面板外部关闭
  useEffect(() => {
    if (!showNotif) return
    function handler(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setShowNotif(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showNotif])

  // 负责人填报状态
  const [showFillModal, setShowFillModal] = useState(false)
  const [selectedFillProject, setSelectedFillProject] = useState<Project | null>(null)

  function openFillModal(project?: Project | null) {
    setSelectedFillProject(project ?? null)
    setShowFillModal(true)
  }

  const now = new Date()
  const monthStr = `${now.getFullYear()}年${now.getMonth() + 1}月`

  // 当前选中的专项名
  const scopeLabel = scopeMode === 'global'
    ? '全部项目'
    : scopeMode === 'my'
      ? '我的项目'
      : (projects.find((p) => p.id === scopeId)?.name ?? '单个项目')
  const dashboardProject = scopeMode === 'project' && scopeId ? (projects.find((p) => p.id === scopeId) ?? currentProject) : currentProject
  const dashboardProjectRoles = dashboardProject?.user_roles ?? currentProjectRoles
  const isFillableForOwner = canShowProjectSubmitAction(dashboardProject) && dashboardProjectRoles.includes('owner')
  const isPendingReviewForOwner = canShowProjectApproveAction(dashboardProject) && dashboardProjectRoles.includes('owner')
  const exportTitle = scopeMode === 'my'
    ? '请选择单个项目后导出周报；多项目周报将在后续聚合导出中支持。'
    : undefined
  const exportLabel = exportLoading ? '生成中…' : (scopeMode === 'my' ? '导出我的项目周报' : '导出周报')

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Top Bar */}
      <header className="h-16 flex items-center px-6 gap-4 flex-shrink-0 bg-white border-b" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex-1">
          <h1 className="text-base font-bold text-slate-800">首页驾驶舱</h1>
        </div>

        {/* 专项筛选 —— 这里是仪表盘自己的筛选，与 URL 项目无关 */}
        <div className="flex items-center gap-2">
          <select
            value={scopeMode === 'project' ? String(scopeId ?? '') : scopeMode}
            onChange={(e) => handleScopeChange(e.target.value)}
            className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-600 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-400/30"
          >
            {canViewGlobalDashboard && <option value="global">全部项目</option>}
            {!canViewGlobalDashboard && canViewMyDashboard && <option value="my">我的项目</option>}
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <select
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
            className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-600 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-400/30"
          >
            <option value="">全部月份</option>
            {monthOptions.map((m) => (
              <option key={m} value={m}>{fmtMonth(m)}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          {/* 通知铃铛 */}
          <div ref={notifRef} className="relative">
            <button
              onClick={() => setShowNotif((v) => !v)}
              className="cursor-pointer relative p-2 rounded-lg hover:bg-slate-100 transition-colors"
            >
              <svg style={{ width: 18, height: 18, color: showNotif ? '#2563EB' : '#64748B' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              {notifTotal > 0 && (
                <span className="absolute top-1 right-1 min-w-[16px] h-4 px-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center border-2 border-white leading-none">
                  {notifTotal > 99 ? '99+' : notifTotal}
                </span>
              )}
            </button>

            {/* 通知下拉面板 */}
            {showNotif && (
              <div className="absolute right-0 top-full mt-2 w-80 bg-white rounded-2xl border shadow-xl z-50 overflow-hidden"
                style={{ borderColor: '#E9EFF6', boxShadow: '0 8px 30px rgba(15,23,42,0.12)' }}>
                <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: '#F1F5F9' }}>
                  <span className="text-sm font-bold text-slate-800">待办提醒</span>
                  {notifTotal > 0 && (
                    <span className="text-xs text-slate-400">{notifTotal} 项需关注</span>
                  )}
                </div>

                <div className="max-h-96 overflow-y-auto">
                  {/* 延期/超期任务 */}
                  {delayedTasks.length > 0 && (
                    <div>
                      <div className="px-4 py-2 bg-red-50 flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-500 flex-shrink-0" />
                        <span className="text-xs font-semibold text-red-600">延期 / 超期任务</span>
                        <span className="ml-auto text-xs text-red-400">{delayedTasks.length} 项</span>
                      </div>
                      {delayedTasks.slice(0, 5).map((t: any, i: number) => {
                        const pid = scopeId ?? currentProjectId
                        return (
                          <div key={i}
                            onClick={() => { pid && navigate(`/project/${pid}/tasks`); setShowNotif(false) }}
                            className="flex items-start gap-3 px-4 py-2.5 hover:bg-red-50 cursor-pointer transition-colors border-b last:border-0"
                            style={{ borderColor: '#FEF2F2' }}>
                            <svg style={{ width: 14, height: 14, color: '#DC2626', flexShrink: 0, marginTop: 2 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium text-slate-700 truncate">{t.key_task ?? '任务'}</p>
                              <p className="text-xs text-slate-400 mt-0.5">
                                {t.is_overdue ? <span className="text-red-500 font-semibold">超期 · </span> : null}
                                {t.owner ?? ''}{t.plan_time ? ` · ${fmtPlanTime(t.plan_time)}` : ''}
                              </p>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}

                  {/* 角色队列 */}
                  {qItems.length > 0 && (
                    <div>
                      <div className="px-4 py-2 bg-blue-50 flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-500 flex-shrink-0" />
                        <span className="text-xs font-semibold text-blue-600">{QUEUE_LABEL[qType] ?? '待处理事项'}</span>
                        <span className="ml-auto text-xs text-blue-400">{qCount} 项</span>
                      </div>
                      {qItems.slice(0, 4).map((item: any, i: number) => {
                        const pid = scopeId ?? currentProjectId
                        const route = { pending_decisions: 'decisions', pending_review: 'confirm', pending_coordinator: 'coordinate', in_progress: 'confirm' }[qType] ?? 'confirm'
                        return (
                          <div key={i}
                            onClick={() => { pid && navigate(`/project/${pid}/${route}`); setShowNotif(false) }}
                            className="flex items-start gap-3 px-4 py-2.5 hover:bg-blue-50 cursor-pointer transition-colors border-b last:border-0"
                            style={{ borderColor: '#EFF6FF' }}>
                            <svg style={{ width: 14, height: 14, color: '#2563EB', flexShrink: 0, marginTop: 2 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                            </svg>
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium text-slate-700 truncate">{item.title ?? item.key_task ?? item.description ?? '待处理事项'}</p>
                              <p className="text-xs text-slate-400 mt-0.5">{item.confirm_status ?? item.status ?? ''}{projectNameFromRecord(item) ? ` · ${projectNameFromRecord(item)}` : ''}</p>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}

                  {notifTotal === 0 && (
                    <div className="px-4 py-8 text-center">
                      <svg style={{ width: 32, height: 32, color: '#CBD5E1', margin: '0 auto 8px' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <p className="text-xs text-slate-400">暂无待办提醒</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
          <button
            onClick={handleExport}
            disabled={exportLoading || scopeMode === 'my' || shouldBlockDashboardLoading}
            title={exportTitle}
            className="cursor-pointer flex items-center gap-2 px-4 py-2 rounded-lg text-white text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-60 disabled:cursor-not-allowed"
            style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}
          >
            {exportLoading ? (
              <svg style={{ width: 14, height: 14 }} className="animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            ) : (
              <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            )}
            {exportLabel}
          </button>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto p-6 space-y-5" style={{ background: '#F1F5F9' }}>
        {shouldBlockDashboardLoading && (
          <div className="rounded-2xl border bg-white p-5" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
            <div>
              <h2 className="text-sm font-bold text-slate-800">
                {managedDashboardProjects.length === 0 ? '普通成员请从我的任务查看个人工作' : '请先选择项目后查看驾驶舱'}
              </h2>
              <p className="text-xs text-slate-500 mt-1">
                {managedDashboardProjects.length === 0 ? '当前账号暂无项目管理驾驶舱权限。' : '当前账号没有可访问项目，暂无法展示项目驾驶舱。'}
              </p>
            </div>
            {managedDashboardProjects.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 mt-4">
                {managedDashboardProjects.map((project) => (
                  <button
                    key={project.id}
                    type="button"
                    onClick={() => handleScopeChange(String(project.id))}
                    className="text-left rounded-xl border border-slate-200 px-4 py-3 hover:border-blue-300 hover:bg-blue-50 transition-colors"
                  >
                    <p className="text-sm font-semibold text-slate-800 truncate">{project.name}</p>
                    <p className="text-xs text-slate-400 mt-1">{project.code ? `项目编号：${project.code}` : '点击进入项目驾驶舱'}</p>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 mt-4">当前没有可查看的项目驾驶舱。</p>
            )}
          </div>
        )}

        {/* 待完善立项项目列表（owner 全项目扫描） */}
        {(() => {
          const fillableProjects = projects.filter((p) => {
            const status = getProjectPrimaryStatus(p)
            return (status === 'dispatched' || status === 'returned') && p.user_roles?.includes('owner')
          })
          if (fillableProjects.length === 0) return null
          return (
            <div className="rounded-2xl border px-5 py-4" style={{ background: '#FFFBEB', borderColor: '#FDE68A' }}>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: '#FEF3C7' }}>
                  <svg style={{ width: 14, height: 14, color: '#D97706' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                </div>
                <p className="text-sm font-semibold text-amber-800">待完善立项</p>
                <span className="text-xs text-amber-500">{fillableProjects.length} 个项目</span>
              </div>
              <div className="space-y-2">
                {fillableProjects.map((p) => (
                  <div key={p.id} className="flex items-center justify-between gap-3 rounded-xl bg-white/60 px-3 py-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-800 truncate">{p.name}</p>
                      <p className="text-xs text-amber-600 mt-0.5">请补全项目背景、目标、预期交付物和重点工作，提交企业教练审核。</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => openFillModal(p)}
                      className="cursor-pointer flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold text-white"
                      style={{ background: '#D97706' }}
                    >
                      完善立项信息
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )
        })()}

        {/* 负责人填报横幅 */}
        {isFillableForOwner && (
          <div className="flex items-center gap-4 px-5 py-4 rounded-2xl border"
            style={{ background: '#FFFBEB', borderColor: '#FDE68A' }}>
            <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: '#FEF3C7' }}>
              <svg style={{ width: 18, height: 18, color: '#D97706' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-amber-800">项目「{currentProject?.name}」待补全立项信息</p>
              <p className="text-xs text-amber-600 mt-0.5">请填写项目背景、目标、预期交付物等内容，填完后可直接发布或提交企业教练审核</p>
            </div>
            <button type="button" onClick={() => openFillModal()}
              className="cursor-pointer flex-shrink-0 px-4 py-2 rounded-xl text-sm font-semibold"
              style={{ background: '#D97706', color: '#fff' }}>
              去填写
            </button>
          </div>
        )}

        {isPendingReviewForOwner && (
          <div className="flex items-center gap-4 px-5 py-4 rounded-2xl border"
            style={{ background: '#FDF4FF', borderColor: '#E9D5FF' }}>
            <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: '#F3E8FF' }}>
              <svg style={{ width: 18, height: 18, color: '#7E22CE' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-purple-800">立项信息已提交，等待企业教练审核</p>
              <p className="text-xs text-purple-600 mt-0.5">企业教练审核通过后项目将正式启动，届时会通知全体成员</p>
            </div>
          </div>
        )}

        {initialLoading && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 16 }}>
              {Array.from({ length: 5 }).map((_, i) => <SkeletonStatCard key={i} />)}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} style={{ background: '#fff', border: '1px solid #E9EFF6', borderRadius: 14, padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <Skel width="50%" height={13} />
                  <Skel width="100%" height={8} radius={4} />
                  <Skel width="70%" height={11} />
                  <Skel width="85%" height={8} radius={4} />
                </div>
              ))}
            </div>
          </div>
        )}
        {errorWithNoData && (
          <div className="flex items-center justify-center py-8">
            <div className="text-red-500 text-sm">{loadError}</div>
          </div>
        )}

        {dataReady && <>
        {/* ─── 统计卡片 ─── */}
        {refreshing && (
          <div className="flex items-center justify-center py-2">
            <span className="text-xs text-slate-400 flex items-center gap-1.5">
              <svg className="animate-spin" style={{ width: 12, height: 12 }} fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              更新中...
            </span>
          </div>
        )}
        {refreshError && (
          <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl border" style={{ background: '#FFF7ED', borderColor: '#FED7AA' }}>
            <svg style={{ width: 14, height: 14, flexShrink: 0, color: '#EA580C' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
            <span className="text-sm" style={{ color: '#C2410C' }}>更新失败，当前显示上次成功加载的数据。</span>
            {loadError && <span className="text-xs" style={{ color: '#9A3412' }}>（{loadError}）</span>}
          </div>
        )}
        {(() => {
          const pid = scopeId ?? currentProjectId
          const toTasks = (status?: string) => () => {
            if (!pid) return
            navigate(status ? `/project/${pid}/tasks?status=${encodeURIComponent(status)}` : `/project/${pid}/tasks`)
          }
          const toAchs = () => pid && navigate(`/project/${pid}/achievements`)
          const toDecisions = () => pid && navigate(`/project/${pid}/decisions`)
          return (
            <div className={`grid gap-4 ${canViewDecisions ? 'grid-cols-6' : 'grid-cols-5'}`}>
              <StatCard label="任务总数" value={total} sub={notStarted > 0 ? `未开始 ${notStarted} 项` : '全部已启动'} subColor="#64748B"
                onClick={toTasks()}
                icon={<IconBox bg="#EFF6FF" color="#2563EB"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></IconBox>}
              />
              <StatCard label="进行中" value={inProgress} sub={`占比 ${total ? Math.round(inProgress / total * 100) : 0}%`} accent="#2563EB"
                onClick={toTasks('推进中')}
                icon={<IconBox bg="#DBEAFE" color="#2563EB"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></IconBox>}
              />
              <StatCard label="已完成" value={completed} sub={`完成率 ${total ? Math.round(completed / total * 100) : 0}%`} accent="#059669"
                onClick={toTasks('已完成')}
                icon={<IconBox bg="#D1FAE5" color="#059669"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></IconBox>}
              />
              <StatCard label="延期" value={delayed} sub={total ? `延期率 ${Math.round(delayed / total * 100)}%` : '无任务'} accent="#DC2626"
                onClick={toTasks('延期')}
                icon={<IconBox bg="#FEE2E2" color="#DC2626"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></IconBox>}
              />
              {canViewDecisions && (
                <StatCard label="待决策" value={pendingDecisions} sub={pendingDecisions > 0 ? '需及时处理' : '暂无待决策'} subColor={pendingDecisions > 0 ? '#D97706' : '#94A3B8'} accent="#D97706"
                  onClick={toDecisions}
                  icon={<IconBox bg="#FEF3C7" color="#D97706"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></IconBox>}
                />
              )}
              <StatCard label="成果数量" value={achievements} sub={scopeMode === 'global' ? '全部项目汇总' : scopeLabel} subColor="#7C3AED" accent="#7C3AED"
                onClick={toAchs}
                icon={<IconBox bg="#EDE9FE" color="#7C3AED"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" /></IconBox>}
              />
            </div>
          )
        })()}

        {/* ─── 本月重点 / 延迟任务 / 需决策 ─── */}
        <div className="grid grid-cols-3 gap-4">
          {(() => {
            const pid = scopeId ?? currentProjectId
            const toTasks = (status?: string) => pid
              ? () => navigate(status ? `/project/${pid}/tasks?status=${encodeURIComponent(status)}` : `/project/${pid}/tasks`)
              : undefined
            return null
          })()}
          <PanelCard title="本月重点" onMore={(() => { const pid = scopeId ?? currentProjectId; return pid ? () => navigate(`/project/${pid}/tasks`) : undefined })()}>
            {(data?.recent?.tasks as any[] ?? []).slice(0, 3).map((t: any, i: number) => (
              <div key={i} className="flex items-start gap-3 p-2.5 rounded-lg hover:bg-slate-50 transition-colors cursor-pointer">
                <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-600 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-slate-700 leading-snug">{t.key_task ?? '任务项'}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-slate-400">{t.owner ?? ''}</span>
                    <StatusBadge status={t.status ?? '进行中'} />
                  </div>
                </div>
              </div>
            ))}
            {!(data?.recent?.tasks as any[])?.length && (
              <p className="text-xs text-slate-400 text-center py-4">暂无数据</p>
            )}
          </PanelCard>

          <PanelCard title="延迟任务" badge={delayed} badgeColor="bg-red-100 text-red-600"
            onMore={(() => { const pid = scopeId ?? currentProjectId; return pid ? () => navigate(`/project/${pid}/tasks?status=${encodeURIComponent('延期')}`) : undefined })()}>

            {((data?.recent as any)?.delayed_tasks as any[] ?? []).slice(0, 4).map((t: any, i: number) => (
              <div key={i} className="flex items-start gap-3 p-2.5 rounded-lg cursor-pointer hover:bg-red-50 transition-colors" style={{ background: '#FEF2F250', border: '1px solid #FECACA' }}>
                <div className="w-8 h-8 rounded-lg bg-red-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <svg style={{ width: 14, height: 14, color: '#DC2626' }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-slate-700 truncate">{t.key_task ?? '任务'}</p>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    {t.is_overdue && <span className="text-xs font-semibold text-red-500">超期</span>}
                    <span className="text-xs text-slate-400">{projectNameFromRecord(t)}{projectNameFromRecord(t) && t.owner ? ' · ' : ''}{t.owner ?? ''}</span>
                    {t.plan_time && <span className="text-xs text-slate-300 ml-auto whitespace-nowrap">{fmtPlanTime(t.plan_time)}</span>}
                  </div>
                </div>
              </div>
            ))}
            {!((data?.recent as any)?.delayed_tasks as any[])?.length && (
              <p className="text-xs text-slate-400 text-center py-4">暂无延期任务</p>
            )}
          </PanelCard>

          {(() => {
            const queue = (data as any)?.role_queue
            const qType: string = queue?.type ?? 'pending_decisions'
            const qItems: any[] = queue?.items ?? []
            const qCount: number = queue?.count ?? 0
            const PANEL_META: Record<string, { title: string; empty: string; accent: string; bg: string }> = {
              pending_decisions:  { title: '需决策事项',  empty: '暂无待决策事项',  accent: '#DC2626', bg: '#FEF2F2' },
              pending_review:     { title: '待审核内容',  empty: '暂无待审核内容',  accent: '#2563EB', bg: '#EFF6FF' },
              pending_coordinator:{ title: '待给出建议',  empty: '暂无待处理事项',  accent: '#7C3AED', bg: '#F5F3FF' },
              in_progress:        { title: '流程推进中',  empty: '暂无进行中提交',  accent: '#059669', bg: '#F0FDF4' },
            }
            const meta = PANEL_META[qType] ?? PANEL_META['pending_decisions']
            const pid = scopeId ?? currentProjectId
            const Q_ROUTE: Record<string, string> = {
              pending_decisions:   'decisions',
              pending_review:      'confirm',
              pending_coordinator: 'coordinate',
              in_progress:         'confirm',
            }
            const qRoute = Q_ROUTE[qType] ?? 'confirm'
            const onQueueMore = pid ? () => navigate(`/project/${pid}/${qRoute}`) : undefined
            return (
              <PanelCard title={meta.title} badge={qCount || undefined} badgeColor={`text-white`} badgeStyle={{ background: meta.accent }} onMore={onQueueMore}>
                {qItems.slice(0, 3).map((item: any, i: number) => (
                  <div key={i} className="p-3 rounded-xl border cursor-pointer transition-colors hover:opacity-90"
                    style={{ borderColor: `${meta.accent}40`, background: `${meta.bg}CC` }}>
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-xs font-semibold text-slate-700 leading-snug flex-1 truncate">
                        {item.title ?? item.key_task ?? item.description ?? '提交事项'}
                      </p>
                      <span className="text-xs px-1.5 py-0.5 rounded flex-shrink-0 font-medium"
                        style={{ background: `${meta.accent}20`, color: meta.accent }}>
                        {item.confirm_status ?? item.status ?? '处理中'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1.5 truncate">
                      {item.submitter ?? item.owner ?? ''}{projectNameFromRecord(item) ? ` · ${projectNameFromRecord(item)}` : ''}
                    </p>
                  </div>
                ))}
                {qItems.length === 0 && (
                  <p className="text-xs text-slate-400 text-center py-4">{meta.empty}</p>
                )}
              </PanelCard>
            )
          })()}
        </div>

        {/* ─── 专项进度 + 状态环形图 ─── */}
        <div className="grid grid-cols-5 gap-4">
          <div className="bg-white rounded-2xl border p-5 col-span-3" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-sm font-bold text-slate-800">专项进度总览</h2>
              <span className="text-xs text-slate-400">更新于 {selectedMonth || '全部月份'}</span>
            </div>
            <div className="space-y-4">
              {projects.slice(0, 6).map((p, i) => {
                const gradients = [
                  '#2563EB,#60A5FA', '#059669,#34D399', '#F59E0B,#FCD34D',
                  '#8B5CF6,#C4B5FD', '#0891B2,#67E8F9', '#6366F1,#A5B4FC',
                ]
                const dots = ['#2563EB', '#059669', '#F59E0B', '#8B5CF6', '#0891B2', '#6366F1']
                const card = completionMap.get(p.name)
                const pct = card?.rate ?? 0
                const taskLabel = card ? `${card.done}/${card.total}` : '暂无数据'
                return (
                  <div key={p.id}>
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleScopeChange(String(p.id))}
                          className="w-2 h-2 rounded-full flex-shrink-0 cursor-pointer hover:scale-125 transition-transform"
                          style={{ background: dots[i] }}
                          title={`切换到 ${p.name}`}
                        />
                        <span
                          onClick={() => handleScopeChange(String(p.id))}
                          className="text-sm font-medium text-slate-700 cursor-pointer hover:text-blue-600 transition-colors"
                        >
                          {p.name}
                        </span>
                        {p.user_roles?.includes('owner') && (
                          <svg
                            style={{ width: 14, height: 14, color: '#DC2626', flexShrink: 0 }}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                            aria-label="项目预警"
                          >
                            <title>项目预警</title>
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                          </svg>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-400">{taskLabel}</span>
                        <span className="text-sm font-bold text-slate-700">{pct}%</span>
                      </div>
                    </div>
                    <div className="h-1.5 rounded-full overflow-hidden" style={{ background: '#EEF2F7' }}>
                      <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: `linear-gradient(90deg,${gradients[i]})` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="bg-white rounded-2xl border p-5 col-span-2" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
            <h2 className="text-sm font-bold text-slate-800 mb-4">任务状态分布</h2>
            <div className="flex items-center gap-4">
              <div style={{ width: 140, height: 140, flexShrink: 0 }}>
                <canvas ref={chartRef} />
              </div>
              <div className="flex-1 space-y-2.5">
                {[
                  { label: '未启动', val: notStarted, color: '#6B7280' },
                  { label: '进行中', val: inProgress, color: '#2563EB' },
                  { label: '已完成', val: completed, color: '#059669' },
                  { label: '延期',   val: delayed,   color: '#DC2626' },
                  { label: '暂缓',   val: paused,    color: '#D97706' },
                ].map(({ label, val, color }) => (
                  <div key={label} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} />
                      <span className="text-xs text-slate-600">{label}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-700">{val}</span>
                      <span className="text-xs text-slate-400">{total ? `${Math.round(val / total * 100)}%` : '0%'}</span>
                    </div>
                  </div>
                ))}
                <div className="pt-1 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs text-slate-500 font-medium">合计</span>
                  <span className="text-xs font-bold text-slate-800">{total} 项</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        </>}
      </main>

      {/* 负责人填报弹窗（复用 OwnerSubmitModal） */}
      {showFillModal && (selectedFillProject ?? dashboardProject) && (
        <OwnerSubmitModal
          project={(selectedFillProject ?? dashboardProject) as Project}
          onClose={() => { setShowFillModal(false); setSelectedFillProject(null) }}
          onSuccess={(result) => {
            setShowFillModal(false)
            setSelectedFillProject(null)
            if (!result.submitted_for_review) window.location.reload()
          }}
        />
      )}
    </div>
  )
}

/* ── 子组件 ── */

function StatCard({ label, value, sub, subColor, accent, icon, onClick }: {
  label: string; value: number; sub?: string; subColor?: string; accent?: string; icon: React.ReactNode; onClick?: () => void
}) {
  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-2xl border p-4 transition-all hover:-translate-y-0.5 ${onClick ? 'cursor-pointer hover:shadow-md' : ''}`}
      style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)', borderLeft: accent ? `3px solid ${accent}` : undefined }}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-slate-500 font-medium">{label}</p>
          <p className="text-3xl font-bold mt-1.5 leading-none" style={{ color: accent ?? '#1E293B' }}>{value}</p>
          {sub && <p className="text-xs font-medium mt-2" style={{ color: subColor ?? '#94A3B8' }}>{sub}</p>}
        </div>
        {icon}
      </div>
    </div>
  )
}

function PanelCard({ title, badge, badgeColor, badgeStyle, onMore, children }: {
  title: string; badge?: number; badgeColor?: string; badgeStyle?: React.CSSProperties; onMore?: () => void; children: React.ReactNode
}) {
  return (
    <div className="bg-white rounded-2xl border p-5" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-bold text-slate-800 flex items-center gap-2">
          {title}
          {badge !== undefined && badge > 0 && (
            <span className={`w-5 h-5 rounded-full text-xs font-bold flex items-center justify-center ${badgeColor ?? 'bg-blue-100 text-blue-600'}`}
              style={badgeStyle}>{badge}</span>
          )}
        </h2>
        {onMore && (
          <button onClick={onMore} className="cursor-pointer text-xs text-blue-500 hover:text-blue-700 font-medium">查看更多 →</button>
        )}
      </div>
      <div className="space-y-2.5">{children}</div>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    '进行中': 'bg-blue-100 text-blue-700',
    '推进中': 'bg-blue-100 text-blue-700',
    '已完成': 'bg-emerald-100 text-emerald-700',
    '延期':   'bg-red-100 text-red-700',
    '暂缓':   'bg-amber-100 text-amber-700',
    '未启动': 'bg-slate-100 text-slate-600',
    '待审核': 'bg-purple-100 text-purple-700',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${map[status] ?? 'bg-slate-100 text-slate-600'}`}>
      {status}
    </span>
  )
}

function IconBox({ bg, color, children }: { bg: string; color: string; children: React.ReactNode }) {
  return (
    <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: bg }}>
      <svg style={{ width: 20, height: 20, color }} fill="none" stroke="currentColor" viewBox="0 0 24 24">{children}</svg>
    </div>
  )
}
