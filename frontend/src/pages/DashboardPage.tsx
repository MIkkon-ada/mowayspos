import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getOverview, exportWeeklyReport } from '../api/dashboard'
import { ApiError } from '../api/client'
import { toast } from '../utils/toast'
import { useProject } from '../context/ProjectContext'
import {
  canShowProjectApproveAction,
  canShowProjectSubmitAction,
  getProjectPrimaryStatus,
  getProjectStatusBadge,
} from '../domain/projectLifecycleStatus'
import { projectOwnerSubmitPath } from '../domain/projectEntryRoutes'
import type { DashboardOverview, GovernanceAction, GovernanceInitiative, Project } from '../types'
import { fmtMonth, fmtPlanTime } from '../utils/time'
import { Skel, SkeletonStatCard } from '../components/Skeleton'
import { MobileDashboardContent, type RoleQueueType } from '../features/dashboard/MobileDashboardContent'
import { GovernanceDashboardContent, type ProjectHealthRow } from '../features/dashboard/GovernanceDashboardContent'
import { aggregateGovernanceOverviews, emptyGovernance } from '../features/dashboard/governanceDashboard'

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
    governance: aggregateGovernanceOverviews(overviews),
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
    if (projects.length === 1) return 'project'
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
    const nextScopeId = nextScopeMode === 'project' ? (urlProjectId ?? projects[0]?.id ?? null) : null
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
  const mobileRoleQueueType: RoleQueueType = ['pending_decisions', 'pending_review', 'pending_coordinator', 'in_progress'].includes(qType)
    ? qType as RoleQueueType
    : 'pending_decisions'
  const mobileScopeOptions = [
    ...(canViewGlobalDashboard ? [{ value: 'global', label: '全部项目' }] : []),
    ...(!canViewGlobalDashboard && canViewMyDashboard ? [{ value: 'my', label: '我的项目' }] : []),
    ...projects.map((project) => ({ value: String(project.id), label: project.name })),
  ]
  const mobileCompletionRows = projects.slice(0, 6).map((project) => {
    const card = completionMap.get(project.name)
    return { id: project.id, name: project.name, done: card?.done ?? 0, total: card?.total ?? 0, rate: card?.rate ?? 0 }
  })
  const governance = data?.governance ?? emptyGovernance()
  const scopedProjects = scopeMode === 'project' && scopeId
    ? projects.filter((project) => project.id === scopeId)
    : projects
  const projectHealthRows: ProjectHealthRow[] = scopedProjects.slice(0, 4).map((project) => {
    const card = completionMap.get(project.name)
    const relatedInitiative = governance.initiatives.find((initiative) => initiative.project_id === project.id)
    return {
      id: project.id,
      name: project.name,
      nextMilestone: relatedInitiative?.next_milestone || '未设置',
      health: card?.rate === 0 && (card?.total ?? 0) > 0 ? 'unstarted' : card?.rate === 100 ? 'healthy' : 'watch',
    }
  })

  function openGovernanceAction(action: GovernanceAction) {
    if (!action.route || (scopeMode === 'project' && action.project_id !== scopeId)) return
    navigate(action.route)
  }

  function openGovernanceInitiative(initiative: GovernanceInitiative) {
    if (!initiative.project_id) return
    navigate(`/work/tasks?projectId=${initiative.project_id}`)
  }

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

  function openFillModal(project?: Project | null) {
    const target = project ?? dashboardProject
    if (target) navigate(projectOwnerSubmitPath(target.id))
  }

  const now = new Date()
  const monthStr = `${now.getFullYear()}年${now.getMonth() + 1}月`

  const dashboardProject = scopeMode === 'project' && scopeId ? (projects.find((p) => p.id === scopeId) ?? currentProject) : currentProject
  const dashboardProjectRoles = dashboardProject?.user_roles ?? currentProjectRoles
  const isFillableForOwner = canShowProjectSubmitAction(dashboardProject) && dashboardProjectRoles.includes('owner')
  const isPendingReviewForOwner = canShowProjectApproveAction(dashboardProject) && dashboardProjectRoles.includes('owner')
  const exportTitle = scopeMode === 'my'
    ? '请选择单个项目后导出周报；多项目周报将在后续聚合导出中支持。'
    : undefined
  const exportLabel = exportLoading ? '生成中…' : (scopeMode === 'my' ? '导出我的项目周报' : '导出周报')
  const mobileProjectNotice = isFillableForOwner
    ? { title: `项目「${currentProject?.name ?? ''}」待补全立项信息`, detail: '请填写项目背景、目标、预期交付物等内容，填完后可直接发布或提交企业教练审核。', tone: 'warning' as const, actionLabel: '去填写' }
    : isPendingReviewForOwner
      ? { title: '立项信息已提交，等待企业教练审核', detail: '企业教练审核通过后项目将正式启动，届时会通知全体成员。', tone: 'review' as const }
      : undefined

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="min-[800px]:hidden flex min-h-0 flex-1 flex-col">
        {dataReady ? (
          <MobileDashboardContent
            scopeOptions={mobileScopeOptions}
            selectedScope={scopeMode === 'project' ? String(scopeId ?? '') : scopeMode}
            selectedMonth={selectedMonth}
            monthOptions={monthOptions}
            onScopeChange={handleScopeChange}
            onMonthChange={setSelectedMonth}
            total={total}
            notStarted={notStarted}
            inProgress={inProgress}
            completed={completed}
            delayed={delayed}
            paused={paused}
            achievements={achievements}
            pendingDecisions={pendingDecisions}
            canViewDecisions={canViewDecisions}
            recentTasks={(data?.recent?.tasks as Array<Record<string, unknown>>) ?? []}
            delayedTasks={delayedTasks}
            roleQueue={{ type: mobileRoleQueueType, count: qCount, items: qItems }}
            completionRows={mobileCompletionRows}
            onOpenTasks={(status) => {
              const pid = scopeId ?? currentProjectId
              if (pid) navigate(status ? `/project/${pid}/tasks?status=${encodeURIComponent(status)}` : `/project/${pid}/tasks`)
            }}
            onOpenAchievements={() => {
              const pid = scopeId ?? currentProjectId
              if (pid) navigate(`/project/${pid}/achievements`)
            }}
            onOpenRoleQueue={(type) => {
              const pid = scopeId ?? currentProjectId
              const route = { pending_decisions: 'decisions', pending_review: 'confirm', pending_coordinator: 'coordinate', in_progress: 'confirm' }[type]
              if (pid) navigate(`/project/${pid}/${route}`)
            }}
            onOpenNotifications={() => navigate('/home/notifications')}
            projectNotice={mobileProjectNotice}
            onOpenProjectNotice={isFillableForOwner ? () => openFillModal() : undefined}
            formatPlanTime={fmtPlanTime}
            projectNameFromRecord={projectNameFromRecord}
          />
        ) : (
          <main className="flex min-h-0 flex-1 items-center justify-center bg-slate-100 p-4">
            <div className="w-full rounded-2xl border border-[#E9EFF6] bg-white p-5 text-center shadow-sm">
              <p className="text-sm font-semibold text-slate-700">{shouldBlockDashboardLoading ? '普通成员请从我的任务查看个人工作' : initialLoading ? '驾驶舱加载中…' : loadError ?? '暂无可查看的项目驾驶舱数据。'}</p>
              {errorWithNoData ? <p className="mt-2 text-xs text-slate-500">{loadError}</p> : null}
            </div>
          </main>
        )}
      </div>
      {/* Top Bar */}
      <header className="hidden min-[800px]:flex min-h-16 flex-wrap items-center px-4 py-3 lg:px-6 gap-4 flex-shrink-0 bg-white border-b" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex-1 min-w-0">
          <h1 className="text-base font-bold text-slate-800">首页驾驶舱</h1>
          {!canViewGlobalDashboard && (
            <p className="text-xs text-slate-500">实时掌握我参与项目的进度、风险、成果与待决策事项</p>
          )}
        </div>

        {/* 专项筛选 —— 这里是仪表盘自己的筛选，与 URL 项目无关 */}
        <div className="flex flex-wrap items-center gap-2">
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

        <div className="flex flex-wrap items-center gap-2">
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
      <main className="hidden min-[800px]:block flex-1 overflow-y-auto p-4 lg:p-6 space-y-5" style={{ background: '#F1F5F9' }}>
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
        <GovernanceDashboardContent
          governance={governance}
          projectHealthRows={projectHealthRows}
          onOpenAction={openGovernanceAction}
          onOpenProject={(projectId) => handleScopeChange(String(projectId))}
          onOpenInitiative={openGovernanceInitiative}
        />
        </>}
      </main>

    </div>
  )
}
