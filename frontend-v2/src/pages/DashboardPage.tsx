import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getOverview, exportWeeklyReport } from '../api/dashboard'
import { ApiError } from '../api/client'
import { toast } from '../utils/toast'
import { useProject } from '../context/ProjectContext'
import {
  getProjectStatusBadge,
  isProjectArchived,
} from '../domain/projectLifecycleStatus'
import type { DashboardOverview, Project } from '../types'
import { Skel } from '../components/Skeleton'
import { ChevronDownIcon } from '../components/icons/ChevronDownIcon'
import { GovernanceDashboardContent, type ProjectOverviewRow } from '../features/dashboard/GovernanceDashboardContent'
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
  const { projects, currentUser, reloadProjects } = useProject()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  useEffect(() => {
    void reloadProjects()
  }, [reloadProjects])

  const rawProjectId = searchParams.get('projectId')
  const urlProjectId = rawProjectId && Number.isFinite(Number(rawProjectId)) ? Number(rawProjectId) : null
  const requestedScope = searchParams.get('scope')
  const canViewGlobalDashboard = !!(currentUser?.is_tech_admin || currentUser?.is_ceo || currentUser?.can_view_all)
  const managedDashboardProjects = projects.filter((project) =>
    !isProjectArchived(project) && project.user_roles?.some((role) => ['owner', 'coordinator', 'project_ceo'].includes(role)),
  )
  const hasProjectDashboardRole = managedDashboardProjects.length > 0
  const canViewMyDashboard = canViewGlobalDashboard || hasProjectDashboardRole

  function initialDashboardScope(): DashboardScope {
    if (urlProjectId !== null) return 'project'
    if (requestedScope === 'global' && canViewGlobalDashboard) return 'global'
    if (requestedScope === 'my' && canViewMyDashboard) return 'my'
    if (canViewGlobalDashboard) return 'global'
    if (projects.length === 1) return 'project'
    if (hasProjectDashboardRole) return 'my'
    return 'my'
  }

  // 独立的仪表盘筛选：global = 全部项目，my = 我的项目汇总，project = 单项目。
  // 项目角色默认进入“我的项目”汇总，不请求真正全局 overview。
  const [scopeMode, setScopeMode] = useState<DashboardScope>(() => initialDashboardScope())
  const [scopeId, setScopeId] = useState<number | null>(() => urlProjectId)

  const [exportLoading, setExportLoading] = useState(false)

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
  }, [urlProjectId, requestedScope, canViewGlobalDashboard, hasProjectDashboardRole, managedDashboardProjects.length])

  // 切换筛选时，同步更新驾驶舱 URL，保留在 /home/dashboard 自己的项目范围内。
  function handleScopeChange(val: string) {
    if (val === 'global' && !canViewGlobalDashboard) return
    if (val !== (scopeMode === 'project' ? String(scopeId ?? '') : scopeMode)) setData(null)
    if (val === 'global') {
      setScopeMode('global')
      setScopeId(null)
      navigate('/home/dashboard?scope=global')
    } else if (val === 'my') {
      setScopeMode('my')
      setScopeId(null)
      navigate('/home/dashboard?scope=my')
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
      managedDashboardProjects.map((project) => getOverview(project.id)),
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
      : getOverview(scopeMode === 'global' ? undefined : scopeId)
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
  }, [scopeMode, scopeId, shouldBlockDashboardLoading, projects])

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
      await exportWeeklyReport(scopeMode === 'global' ? null : scopeId)
    } catch {
      toast.error('导出失败，请稍后重试')
    } finally {
      setExportLoading(false)
    }
  }


  function projectNameFromRecord(record: any) {
    if (!record) return ""
    const matched = record.project_id != null ? projects.find((p) => p.id === record.project_id) : null
    return matched?.name ?? record.special_project ?? record.related_special_project ?? record.name ?? ""
  }

  // 项目概况使用重点工作统计；管理关注点来自问题中心的当前状态。
  const projectCards = (data?.project_cards as any[] ?? [])
  const projectCardById = new Map<number, Record<string, any>>()
  projectCards.forEach((card: any) => {
    const projectId = Number(card.project_id)
    if (Number.isFinite(projectId)) projectCardById.set(projectId, card)
  })

  const governance = data?.governance ?? emptyGovernance()
  const scopedProjects = scopeMode === 'project' && scopeId
    ? projects.filter((project) => project.id === scopeId)
    : scopeMode === 'my'
      ? managedDashboardProjects
      : projectCards.length > 0
        ? projects.filter((project) => projectCardById.has(project.id))
        : projects.filter((project) => !isProjectArchived(project))
  const projectRows: ProjectOverviewRow[] = scopedProjects.map((project) => {
    const card = projectCardById.get(project.id) ?? projectCards.find((item: any) => projectNameFromRecord(item) === project.name)
    const signals = governance.project_signals?.[String(project.id)]
    const status = getProjectStatusBadge(project)
    return {
      id: project.id,
      name: project.name,
      statusLabel: status.label,
      statusClassName: status.className,
      completedWorkstreams: asNumber(card?.completed_count ?? card?.task_stats?.completed),
      totalWorkstreams: asNumber(card?.task_count ?? card?.task_stats?.total_tasks),
      openIssues: asNumber(card?.open_issue_count),
      latestUpdate: String(card?.latest_update ?? ''),
      pendingDecisions: signals?.pending_decisions ?? 0,
      pendingCoordination: signals?.pending_coordination ?? 0,
    }
  }).sort((left, right) =>
    right.pendingDecisions - left.pendingDecisions
    || right.pendingCoordination - left.pendingCoordination
    || right.openIssues - left.openIssues
    || left.name.localeCompare(right.name, 'zh-CN'),
  )

  function openIssueCenter(projectId?: number, status?: '待决策' | '待协调') {
    const targetProjectId = projectId ?? (scopeMode === 'project' ? scopeId : null)
    const params = new URLSearchParams()
    if (targetProjectId) params.set('projectId', String(targetProjectId))
    if (targetProjectId && status) params.set('status', status)
    navigate(`/work/issues${params.size ? `?${params.toString()}` : ''}`)
  }

  const exportTitle = scopeMode === 'my'
    ? '请选择单个项目后导出周报；多项目周报将在后续聚合导出中支持。'
    : undefined
  const exportLabel = exportLoading ? '生成中…' : (scopeMode === 'my' ? '导出我的项目周报' : '导出周报')

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Top Bar */}
      <header className="flex min-h-16 flex-shrink-0 flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 lg:gap-4 lg:px-6">
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-bold text-slate-900">
            {scopeMode === 'global' ? '全局项目工作台' : scopeMode === 'my' ? '我负责的项目' : '项目工作台'}
          </h1>
          <p className="text-xs text-slate-500">管理层项目概况与问题提醒</p>
        </div>

        {/* 专项筛选 —— 这里是仪表盘自己的筛选，与 URL 项目无关 */}
        <div className="relative flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <label className="sr-only" htmlFor="dashboard-scope">项目范围</label>
          <select
            id="dashboard-scope"
            value={scopeMode === 'project' ? String(scopeId ?? '') : scopeMode}
            onChange={(e) => handleScopeChange(e.target.value)}
            className="max-w-full flex-1 cursor-pointer appearance-none rounded-lg border border-slate-200 bg-white py-2 pl-3 pr-9 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-500 sm:flex-none"
          >
            {canViewGlobalDashboard && <option value="global">全部项目</option>}
            {hasProjectDashboardRole && <option value="my">我负责的项目</option>}
            {projects.filter((project) => !isProjectArchived(project)).map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-500"><ChevronDownIcon /></span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
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
      <main className="min-h-0 flex-1 space-y-5 overflow-y-auto bg-slate-50 p-4 pb-12 lg:p-6">
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

        {initialLoading && (
          <div className="mx-auto max-w-[1440px] space-y-5" aria-label="正在加载管理层概览">
            <div className="space-y-5 rounded-2xl border border-slate-200 bg-white p-6">
              <Skel width="24%" height={18} />
              <Skel width="58%" height={12} />
              <div className="grid gap-4 pt-3 sm:grid-cols-3">
                {Array.from({ length: 3 }).map((_, index) => <Skel key={index} width="100%" height={42} radius={8} />)}
              </div>
            </div>
            <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6">
              <Skel width="22%" height={18} />
              {Array.from({ length: 4 }).map((_, index) => <Skel key={index} width="100%" height={40} radius={8} />)}
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
          key={`${scopeMode}:${scopeId ?? 'all'}`}
          governance={governance}
          projectRows={projectRows}
          onOpenProject={(projectId) => navigate(`/home/projects/${projectId}`)}
          onOpenIssueCenter={openIssueCenter}
        />
        </>}
      </main>

    </div>
  )
}
