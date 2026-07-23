import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { createIssue, fetchIssues } from '../api/issues'
import { fetchTasks } from '../api/tasks'
import { fetchSubTasks, fetchSubtasksByProject } from '../api/subtasks'
import { useProject } from '../context/ProjectContext'
import { toast } from '../utils/toast'
import { fmtDate } from '../utils/time'
import { isProjectArchived } from '../domain/projectLifecycleStatus'
import { getProjectDisplayName } from '../domain/projectDisplay'
import type { IssueItem, Project, SubTaskItem, TaskItem } from '../types'

const PRIORITY_STYLE: Record<string, string> = {
  '高': 'bg-red-100 text-red-700 border-red-200',
  '中': 'bg-amber-100 text-amber-700 border-amber-200',
  '低': 'bg-slate-100 text-slate-600 border-slate-200',
}

const STATUS_STYLE: Record<string, { badge: string; dot: string }> = {
  '待处理': { badge: 'bg-amber-100 text-amber-700 border-amber-200', dot: '#F59E0B' },
  '待协调': { badge: 'bg-orange-100 text-orange-700 border-orange-200', dot: '#F97316' },
  '待决策': { badge: 'bg-purple-100 text-purple-700 border-purple-200', dot: '#7C3AED' },
  '待负责人确认': { badge: 'bg-sky-100 text-sky-700 border-sky-200', dot: '#0EA5E9' },
  '已解决': { badge: 'bg-emerald-100 text-emerald-700 border-emerald-200', dot: '#10B981' },
  '已关闭': { badge: 'bg-slate-200 text-slate-500 border-slate-200', dot: '#94A3B8' },
}

const TYPE_STYLE: Record<string, string> = {
  '问题': 'bg-orange-50 text-orange-700 border-orange-200',
  '风险': 'bg-red-50 text-red-700 border-red-200',
  '待协调': 'bg-blue-50 text-blue-700 border-blue-200',
  '需决策': 'bg-purple-50 text-purple-700 border-purple-200',
}

// 问题状态流转顺序（主流程）
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
  const idx = ISSUE_FLOW.findIndex(s => s.key === status)
  return idx >= 0 ? idx : 0
}

function parseProjectId(searchParams: URLSearchParams): number | null {
  const raw = searchParams.get('projectId')
  if (!raw) return null
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : null
}

function projectStatusLabel(project?: Project | null): string {
  const map: Record<string, string> = {
    draft: '草稿', dispatched: '已派发', pending_review: '待审核',
    returned: '已退回', active: '进行中', archived: '已归档',
  }
  if (!project) return '未选择'
  return map[project.status] || project.status || '未填写'
}

function ownerText(project?: Project | null): string {
  if (!project) return '—'
  return project.owners?.filter(Boolean).join('、') || '未配置'
}

function coachText(project?: Project | null): string {
  if (!project) return '—'
  return project.coaches?.length ? project.coaches.join('、') : '未配置'
}

function taskNameForId(tasks: TaskItem[], taskId?: number | null): string {
  if (!taskId) return '暂未关联'
  return tasks.find((t) => t.id === taskId)?.key_task || `重点工作 #${taskId}`
}

function issueSourceLabel(item: IssueItem): string {
  const raw = String(item.source_type || '').toLowerCase()
  if (raw.includes('ai') || raw.includes('确认') || raw.includes('confirm')) return 'AI确认入库'
  return '手动新增'
}

// --- Operation log helpers ---
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

function LOG_ACTION_CN(action: string): string {
  return LOG_ACTION_MAP[action] || action
}

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

function keyTaskLabelForIssue(item: IssueItem, subtaskById: Record<number, SubTaskItem>): string {
  // 优先通过 related_subtask_id 在本地 map 中查找名称
  if (item.related_subtask_id && subtaskById[item.related_subtask_id]) {
    return subtaskById[item.related_subtask_id].title
  }
  const candidate = (
    item.related_subtask_title
    ?? item.related_subtask_name
    ?? item.key_task_title
    ?? item.matched_subtask_title
    ?? item.matched_subtask_name
  )
  if (typeof candidate === 'string' && candidate.trim()) return candidate.trim()
  return '未指定关键任务'
}

export function IssuesPage() {
  const { projects, currentUser } = useProject()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const projectId = parseProjectId(searchParams)
  const currentProject = projects.find((p) => p.id === projectId) ?? null
  const projectArchived = isProjectArchived(currentProject)

  // issues state
  const [issues, setIssues] = useState<IssueItem[]>([])
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')

  // tasks
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [tasksLoading, setTasksLoading] = useState(false)

  // subtasks
  const [allSubtasks, setAllSubtasks] = useState<SubTaskItem[]>([])

  // filters
  const [filterType, setFilterType] = useState('全部')
  const [filterPriority, setFilterPriority] = useState('全部')
  const [filterStatus, setFilterStatus] = useState('全部')
  const [filterOwner, setFilterOwner] = useState('')
  const [filterHelper, setFilterHelper] = useState('')
  const [keyword, setKeyword] = useState('')

  // project search
  const [projectSearch, setProjectSearch] = useState('')

  // overview pagination
  const [overviewPage, setOverviewPage] = useState(1)

  // add modal
  const [addOpen, setAddOpen] = useState(false)

  // reload issues
  const reloadIssues = () => {
    if (!projectId) return
    setLoading(true)
    fetchIssues(projectId)
      .then(setIssues)
      .catch((err: unknown) => toast.error(err instanceof Error ? err.message : '刷新失败'))
      .finally(() => setLoading(false))
  }

  const visibleProjects = useMemo(() => {
    const term = projectSearch.trim().toLowerCase()
    if (!term) return projects
    return projects.filter((p) => p.name.toLowerCase().includes(term))
  }, [projects, projectSearch])

  const overviewPageSize = 8
  const overviewPageCount = Math.max(1, Math.ceil(visibleProjects.length / overviewPageSize))
  const pagedProjects = visibleProjects.slice((overviewPage - 1) * overviewPageSize, overviewPage * overviewPageSize)

  useEffect(() => {
    setOverviewPage(1)
  }, [projectSearch])

  // --- Load issues when projectId is set ---
  useEffect(() => {
    if (!projectId) {
      setIssues([]); setLoadError(''); return
    }
    let cancelled = false
    setLoading(true); setLoadError('')
    fetchIssues(projectId)
      .then((rows) => {
        if (cancelled) return
        setIssues(rows)
      })
      .catch((err: unknown) => {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : '加载问题失败')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [projectId])

  // --- Load tasks when projectId is set ---
  useEffect(() => {
    if (!projectId) { setTasks([]); return }
    let cancelled = false
    setTasksLoading(true)
    fetchTasks(projectId)
      .then((rows) => { if (!cancelled) setTasks(rows.filter((t) => !t.is_deleted)) })
      .catch(() => { if (!cancelled) setTasks([]) })
      .finally(() => { if (!cancelled) setTasksLoading(false) })
    return () => { cancelled = true }
  }, [projectId])

  // --- Load all subtasks for the project ---
  useEffect(() => {
    if (!projectId) { setAllSubtasks([]); return }
    let cancelled = false
    fetchSubtasksByProject(projectId)
      .then((rows) => { if (!cancelled) setAllSubtasks(rows.filter((row) => !row.is_deleted)) })
      .catch(() => { if (!cancelled) setAllSubtasks([]) })
    return () => { cancelled = true }
  }, [projectId])

  const subtaskById = useMemo(() => {
    const map: Record<number, SubTaskItem> = {}
    for (const st of allSubtasks) map[st.id] = st
    return map
  }, [allSubtasks])

  // N4-P2-M: 判断当前用户是否为项目负责人/管理员（决定是否显示处理动作）
  const canManageIssues = useMemo(() => {
    if (currentUser?.is_tech_admin) return true
    if (!currentProject) return false
    const roles: string[] = currentProject.user_roles ?? []
    return roles.includes('owner')
  }, [currentUser, currentProject])

  // N4-P2-N: 判断用户在任何项目中是否有管理角色（用于项目选择页视图区分）
  const hasAnyManagementRole = useMemo(() => {
    if (currentUser?.is_tech_admin || currentUser?.is_ceo) return true
    return projects.some((p) => {
      const roles: string[] = p.user_roles ?? []
      return roles.some((role) =>
        ['owner', 'coordinator', 'project_ceo'].includes(role)
      )
    })
  }, [currentUser, projects])

  // N4-P2-N: 判断当前用户能否查看当前项目的全部问题
  const canViewAllProjectIssues = useMemo(() => {
    if (currentUser?.is_tech_admin || currentUser?.is_ceo) return true
    if (!currentProject) return false
    const roles: string[] = currentProject.user_roles ?? []
    return roles.some((role) =>
      ['owner', 'coordinator', 'project_ceo'].includes(role)
    )
  }, [currentUser, currentProject])

  // N4-P2-N: 普通成员问题视图标记
  const isMemberIssueView = Boolean(currentProject) && !canViewAllProjectIssues

  // N4-P2-N: 普通成员状态筛选
  const [memberStatusFilter, setMemberStatusFilter] = useState('全部')

  // --- Derived data ---
  const filteredIssues = useMemo(() => {
    const term = keyword.trim().toLowerCase()
    return issues.filter((item) => {
      if (filterType !== '全部' && item.issue_type !== filterType) return false
      if (filterPriority !== '全部' && item.priority !== filterPriority) return false
      if (filterStatus !== '全部' && item.status !== filterStatus) return false
      if (filterOwner && (item.owner || '') !== filterOwner) return false
      if (filterHelper && (item.helper || '') !== filterHelper) return false
      if (term && !(item.description || '').toLowerCase().includes(term)) return false
      return true
    })
  }, [issues, filterType, filterPriority, filterStatus, filterOwner, filterHelper, keyword])

  // N4-P2-N: 普通成员问题过滤（仅状态和关键词）
  const memberFilteredIssues = useMemo(() => {
    const term = keyword.trim().toLowerCase()
    return issues.filter((item) => {
      if (memberStatusFilter !== '全部' && item.status !== memberStatusFilter) return false
      if (term && !(item.description || '').toLowerCase().includes(term)) return false
      return true
    })
  }, [issues, memberStatusFilter, keyword])

  // N4-P2-N: 判断当前用户与问题的关系
  function getMyRelationship(item: IssueItem): string {
    if (!currentUser) return '—'
    const uname = currentUser.username || ''
    const pname = currentUser.name || ''
    const parts: string[] = []
    if ((item.reporter || '') === uname) parts.push('我上报的')
    if ((item.owner || '') === uname || (pname && (item.owner || '') === pname)) parts.push('我负责的')
    if ((item.helper || '') === uname || (pname && (item.helper || '') === pname)) parts.push('我协助的')
    return parts.length > 0 ? parts.join('、') : '—'
  }

  const stats = useMemo(() => {
    const pending = issues.filter((i) => i.status === '待处理').length
    const pendingOwnerConfirm = issues.filter((i) => i.status === '待负责人确认').length
    const coordinating = issues.filter((i) => i.status === '待协调').length
    const decision = issues.filter((i) => i.status === '待决策').length
    const closed = issues.filter((i) => i.status === '已关闭').length
    return { total: issues.length, pending, pendingOwnerConfirm, coordinating, decision, closed }
  }, [issues])

  // N4-P2-N: 角色标签映射
  function roleLabel(role: string): string {
    const map: Record<string, string> = {
      owner: '负责人', coordinator: '统筹人', project_ceo: '企业教练', member: '成员',
    }
    return map[role] || role
  }

  // ============ PROJECT SELECTION PAGE ============
  if (!projectId) {
    // N4-P2-N: 普通成员无任何管理角色时，显示简化项目选择页
    if (!hasAnyManagementRole) {
      return (
        <div className="flex-1 overflow-y-auto bg-[#f6f8fb]">
          <div className="mx-auto max-w-[1440px] px-6 py-6">
            <div className="mb-6">
              <p className="text-[11px] font-extrabold uppercase tracking-[0.24em] text-purple-600">ISSUE CENTER</p>
              <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950">与我相关的问题</h1>
              <p className="mt-2 text-sm text-slate-500">选择项目，查看你上报、负责或协助处理的问题。</p>
            </div>

            <div className="mb-6 max-w-xs">
              <div className="rounded border border-slate-200 bg-white px-4 py-2.5 shadow-sm">
                <label className="text-[11px] font-bold uppercase tracking-wide text-slate-400">搜索项目名称</label>
                <input
                  value={projectSearch}
                  onChange={(e) => setProjectSearch(e.target.value)}
                  placeholder="搜索项目名称"
                  className="mt-1.5 w-full border-0 p-0 text-sm font-medium text-slate-800 outline-none placeholder:text-slate-300"
                />
              </div>
            </div>

            <div className="overflow-hidden rounded border border-slate-200 bg-white shadow-sm">
              <div className="border-b border-slate-200 bg-slate-50 px-5 py-3">
                <h2 className="text-base font-bold text-slate-900">可查看项目</h2>
                <p className="mt-0.5 text-xs text-slate-500">选择项目，查看与你相关的问题。</p>
              </div>
              <div className="overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-5 py-2.5">项目名称</th>
                      <th className="px-4 py-2.5">状态</th>
                      <th className="px-4 py-2.5">我的角色</th>
                      <th className="px-4 py-2.5 text-center">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {visibleProjects.length === 0 ? (
                      <tr><td colSpan={4} className="px-5 py-12 text-center text-sm text-slate-400">暂无可查看项目</td></tr>
                    ) : visibleProjects.map((project) => {
                      const myRoles: string[] = project.user_roles ?? []
                      const roleText = myRoles.length > 0
                        ? myRoles.map((r) => roleLabel(r)).join('、')
                        : '成员'
                      return (
                        <tr key={project.id} className="transition-colors hover:bg-purple-50/50">
                          <td className="px-5 py-2.5">
                            <p className="font-bold text-slate-950">{project.name}</p>
                            <p className="mt-0.5 text-xs text-slate-400">项目编号：{project.code || `#${project.id}`}</p>
                          </td>
                          <td className="px-4 py-2.5"><span className="rounded border border-sky-100 bg-sky-50 px-2 py-0.5 text-xs font-bold text-sky-700">{projectStatusLabel(project)}</span></td>
                          <td className="px-4 py-2.5 text-sm text-slate-600">{roleText}</td>
                          <td className="px-4 py-2.5 text-center">
                            <button
                              type="button"
                              onClick={() => navigate(`/work/issues?projectId=${project.id}`)}
                              className="rounded bg-purple-600 px-3 py-1.5 text-xs font-bold text-white transition hover:bg-purple-700"
                            >
                              查看问题
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50/50 px-5 py-2.5">
                <span className="text-xs text-slate-400">共 {visibleProjects.length} 个项目可查看</span>
              </div>
            </div>
          </div>
        </div>
      )
    }

    // 管理角色：原项目选择页
    return (
      <div className="flex-1 overflow-y-auto bg-[#f6f8fb]">
        <div className="mx-auto max-w-[1440px] px-6 py-6">
          <div className="mb-6 flex items-center gap-4">
            {[
              ['可查看项目数', projects.length, 'bg-indigo-50 text-indigo-600'],
              ['待处理问题', '—', 'bg-amber-50 text-amber-600'],
              ['待协调问题', '—', 'bg-orange-50 text-orange-600'],
              ['待决策事项', '—', 'bg-emerald-50 text-emerald-600'],
            ].map(([label, value, iconColorClass]) => (
              <div key={label} className="flex flex-1 items-center gap-3 rounded border border-slate-200 bg-white p-4 shadow-sm">
                <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${iconColorClass}`}>
                  {label === '可查看项目数' && (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
                  )}
                  {label === '待处理问题' && (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                  )}
                  {label === '待协调问题' && (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>
                  )}
                  {label === '待决策事项' && (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
                  )}
                </div>
                <div>
                  <p className="text-xs text-slate-500">{label}</p>
                  <p className="mt-0.5 text-2xl font-black tabular-nums text-slate-950">{value}</p>
                </div>
              </div>
            ))}

            <div className="flex items-center gap-2">
              <div className="relative">
                <input
                  value={projectSearch}
                  onChange={(e) => setProjectSearch(e.target.value)}
                  placeholder="搜索项目名称"
                  className="w-52 rounded border border-slate-300 bg-white pl-3 pr-8 py-1.5 text-xs outline-none focus:border-purple-500"
                />
                <svg className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              </div>
              <button type="button" className="inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>
                筛选
              </button>
              <button type="button" className="inline-flex items-center gap-1 rounded bg-purple-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-purple-700">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                新增
              </button>
            </div>
          </div>

          <div className="overflow-hidden rounded border border-slate-200 bg-white shadow-sm">
            <div className="overflow-auto">
              <table className="w-full min-w-[920px] text-left text-sm">
                <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-5 py-2.5">项目名称</th>
                    <th className="px-4 py-2.5">状态</th>
                    <th className="px-4 py-2.5">项目负责人</th>
                    <th className="px-4 py-2.5">Coach / 企业教练</th>
                    <th className="px-4 py-2.5">待处理</th>
                    <th className="px-4 py-2.5">待决策</th>
                    <th className="px-4 py-2.5">最后更新</th>
                    <th className="px-4 py-2.5 text-center">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {visibleProjects.length === 0 ? (
                    <tr><td colSpan={8} className="px-5 py-12 text-center text-sm text-slate-400">暂无可查看项目</td></tr>
                  ) : visibleProjects.map((project) => (
                    <tr key={project.id} className="transition-colors hover:bg-purple-50/50">
                      <td className="px-5 py-2.5">
                        <p className="font-bold text-slate-950">{project.name}</p>
                        <p className="mt-0.5 text-xs text-slate-400">项目编号：{project.code || `#${project.id}`}</p>
                      </td>
                      <td className="px-4 py-2.5"><span className="rounded border border-sky-100 bg-sky-50 px-2 py-0.5 text-xs font-bold text-sky-700">{projectStatusLabel(project)}</span></td>
                      <td className="px-4 py-2.5 text-sm text-slate-600">{ownerText(project)}</td>
                      <td className="px-4 py-2.5 text-sm text-slate-600">{coachText(project)}</td>
                      <td className="px-4 py-2.5 text-sm text-slate-400">—</td>
                      <td className="px-4 py-2.5 text-sm text-slate-400">—</td>
                      <td className="px-4 py-2.5 text-sm text-slate-400">—</td>
                      <td className="px-4 py-2.5 text-center">
                        <button
                          type="button"
                          onClick={() => navigate(`/work/issues?projectId=${project.id}`)}
                          className="rounded bg-purple-600 px-3 py-1.5 text-xs font-bold text-white transition hover:bg-purple-700"
                        >
                          进入问题中心
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50/50 px-5 py-2.5">
              <span className="text-xs text-slate-400">共 {visibleProjects.length} 个项目</span>
              <div className="flex items-center gap-2">
                <button className="rounded border border-slate-300 bg-white p-1 disabled:opacity-40" disabled>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
                </button>
                <span className="rounded border border-purple-600 bg-purple-50 px-2.5 py-0.5 text-xs font-bold text-purple-700">1</span>
                <button className="rounded border border-slate-300 bg-white p-1 disabled:opacity-40" disabled>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
                </button>
                <span className="text-xs text-slate-400">10条/页</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ============ ISSUE LIST PAGE ============

  // N4-P2-N: 普通成员项目详情视图
  if (isMemberIssueView) {
    return (
      <>
      <div className="flex-1 overflow-hidden bg-[#f6f8fb] flex flex-col">
        {/* Header */}
        <header className="flex-shrink-0 rounded-xl border border-slate-200 bg-white mx-5 mt-5 px-4 py-4 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-extrabold uppercase tracking-[0.24em] text-purple-600">ISSUE CENTER</p>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="mt-1 text-3xl font-black tracking-tight text-slate-950">与我相关的问题</h1>
                <span className="mt-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-black text-emerald-700">{projectStatusLabel(currentProject)}</span>
              </div>
              <p className="mt-2 text-xs text-slate-500">查看你在 {currentProject?.name || '当前项目'} 中上报、负责或协助处理的问题。</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" onClick={() => navigate('/work/issues')} className="rounded border border-purple-200 bg-white px-3 py-2 text-xs font-bold text-purple-700 hover:bg-purple-50">切换项目</button>
              <button type="button" onClick={reloadIssues} className="rounded border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50">刷新</button>
              <button type="button" onClick={() => setAddOpen(true)} disabled={projectArchived} className="rounded bg-purple-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-purple-700 disabled:cursor-not-allowed disabled:opacity-50">新增问题</button>
            </div>
          </div>

          {/* Filter bar */}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <select value={memberStatusFilter} onChange={(e) => setMemberStatusFilter(e.target.value)} className="rounded border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700">
              <option value="全部">全部状态</option>
              <option value="待处理">待处理</option>
              <option value="待协调">待协调</option>
              <option value="待决策">待决策</option>
              <option value="待负责人确认">待负责人确认</option>
              <option value="已解决">已解决</option>
              <option value="已关闭">已关闭</option>
            </select>
            <input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="搜索问题摘要" className="min-w-[200px] flex-1 rounded border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 outline-none focus:border-purple-400" />
          </div>
        </header>

        {/* Table + Detail Panel */}
        <div className="min-h-0 flex-1 flex gap-4 px-5 py-4 overflow-hidden">
          {/* Table area */}
          <div className="flex-1 overflow-auto">
            {loading ? (
              <div className="flex items-center justify-center h-full text-sm text-slate-400">加载中...</div>
            ) : loadError ? (
              <div className="flex items-center justify-center h-full text-sm text-red-500">{loadError}</div>
            ) : memberFilteredIssues.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <p className="text-sm font-semibold text-slate-500">当前项目暂无与你相关的问题</p>
                <p className="mt-1 text-xs text-slate-400">你上报的问题，或被指定负责、协助的问题，会显示在这里。</p>
              </div>
            ) : (
              <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-2.5">问题摘要</th>
                      <th className="px-3 py-2.5">关联重点工作 / 关键任务</th>
                      <th className="px-3 py-2.5">当前状态</th>
                      <th className="px-3 py-2.5">我的关系</th>
                      <th className="px-3 py-2.5">负责人 / 协助人</th>
                      <th className="px-3 py-2.5">更新时间</th>
                      <th className="px-3 py-2.5 text-center">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {memberFilteredIssues.map((item) => {
                      const st = STATUS_STYLE[item.status || ''] || STATUS_STYLE['待处理']
                      return (
                        <tr
                          key={item.id}
                          onClick={() => navigate(`/work/issues/${item.id}?projectId=${projectId}`)}
                          className="cursor-pointer transition-colors hover:bg-purple-50/30"
                        >
                          <td className="px-4 py-2.5 max-w-[200px]">
                            <p className="font-bold text-slate-800 text-xs leading-snug line-clamp-2">{item.description || '未命名问题'}</p>
                            {/* Status progress bar for member view */}
                            {item.status !== '已关闭' && (
                              <div className="mt-1.5 flex items-center gap-0.5">
                                {(() => {
                                  const flowIndex = getIssueFlowIndex(item.status || '待处理')
                                  return ISSUE_FLOW.map((step, idx) => {
                                    const isDone = idx < flowIndex
                                    const isActive = idx === flowIndex
                                    return (
                                      <div key={step.key} className="flex items-center gap-0.5">
                                        <span
                                          className="inline-block rounded-full"
                                          style={{
                                            width: isActive ? 6 : 4,
                                            height: isActive ? 6 : 4,
                                            background: isDone || isActive ? FLOW_DOT_COLORS[step.key] : '#E2E8F0',
                                            ...(isActive ? { boxShadow: `0 0 0 1.5px ${FLOW_DOT_COLORS[step.key]}33`, border: `1px solid ${FLOW_DOT_COLORS[step.key]}` } : {}),
                                          }}
                                        />
                                        {idx < ISSUE_FLOW.length - 1 && (
                                          <span className="inline-block h-[1.5px] w-3 rounded-full" style={{ background: idx < flowIndex ? FLOW_DOT_COLORS[ISSUE_FLOW[idx + 1].key] : '#E2E8F0' }} />
                                        )}
                                      </div>
                                    )
                                  })
                                })()}
                              </div>
                            )}
                          </td>
                          <td className="px-3 py-2.5 text-xs text-slate-600">
                            <p>{taskNameForId(tasks, item.related_task_id as number | null | undefined)}</p>
                            <p className="text-slate-400">{keyTaskLabelForIssue(item, subtaskById)}</p>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${st.badge}`}>
                              <span className="w-1.5 h-1.5 rounded-full" style={{ background: st.dot }}></span>
                              {item.status || '待处理'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-xs text-slate-600">{getMyRelationship(item)}</td>
                          <td className="px-3 py-2.5 text-xs text-slate-600">
                            <p>{item.owner || '—'}</p>
                            <p className="text-slate-400">{item.helper || '—'}</p>
                          </td>
                          <td className="px-3 py-2.5 text-xs text-slate-400">{fmtDate(item.updated_at) || '—'}</td>
                          <td className="px-3 py-2.5 text-center">
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); navigate(`/work/issues/${item.id}?projectId=${projectId}`) }}
                              className="rounded border border-purple-200 bg-white px-2.5 py-1 text-[11px] font-bold text-purple-600 hover:bg-purple-50"
                            >
                              查看详情
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Add Issue Modal */}

      {/* Add Issue Modal */}
      {addOpen && (
        <AddIssueModal
          projects={projects}
          currentProjectId={projectId}
          currentUser={currentUser}
          tasks={tasks}
          tasksLoading={tasksLoading}
          projectArchived={projectArchived}
          onClose={() => setAddOpen(false)}
          onCreated={(item) => {
            setIssues((prev) => [item, ...prev])
            navigate(`/work/issues/${item.id}?projectId=${projectId}`)
            setAddOpen(false)
            toast.success('问题已创建')
          }}
        />
      )}
      </>
    )
  }

  return (
    <>
    <div className="flex-1 overflow-hidden bg-[#f6f8fb] flex flex-col">
      {/* Header */}
      <header className="flex-shrink-0 rounded-xl border border-slate-200 bg-white mx-5 mt-5 px-4 py-4 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-extrabold uppercase tracking-[0.24em] text-purple-600">ISSUE CENTER</p>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="mt-1 text-3xl font-black tracking-tight text-slate-950">{currentProject?.name || '项目'} 项目问题中心</h1>
              <span className="mt-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-black text-emerald-700">{projectStatusLabel(currentProject)}</span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-slate-500">
              <span>项目负责人：{ownerText(currentProject)}</span>
              <span>Coach / 企业教练：{coachText(currentProject)}</span>
              <span>项目编号：{currentProject?.code || `#${projectId}`}</span>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => navigate('/work/issues')} className="rounded border border-purple-200 bg-white px-3 py-2 text-xs font-bold text-purple-700 hover:bg-purple-50">切换项目</button>
            <button type="button" onClick={reloadIssues} className="rounded border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50">刷新</button>
            <button type="button" onClick={() => setAddOpen(true)} disabled={projectArchived} className="rounded bg-purple-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-purple-700 disabled:cursor-not-allowed disabled:opacity-50">新增问题</button>
          </div>
        </div>

        {/* Stats bar */}
        <div className="mt-4 grid grid-cols-6 overflow-hidden rounded-lg border border-slate-200 bg-white">
          {[
            ['问题总数', stats.total],
            ['待处理', stats.pending],
            ['待协调', stats.coordinating],
            ['待决策', stats.decision],
            ['待负责人确认', stats.pendingOwnerConfirm],
            ['已关闭', stats.closed],
          ].map(([label, value]) => (
            <div key={label} className="border-r border-slate-200 px-4 py-3 last:border-r-0">
              <p className="text-[11px] font-black uppercase tracking-wide text-slate-400">{label}</p>
              <p className="mt-1 text-2xl font-black tabular-nums text-slate-950">{value}</p>
            </div>
          ))}
        </div>

        {/* Filter bar */}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="rounded border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700">
            <option value="全部">全部类型</option>
            <option value="问题">问题</option>
            <option value="风险">风险</option>
            <option value="待协调">待协调</option>
            <option value="需决策">需决策</option>
          </select>
          <select value={filterPriority} onChange={(e) => setFilterPriority(e.target.value)} className="rounded border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700">
            <option value="全部">全部优先级</option>
            <option value="高">高</option>
            <option value="中">中</option>
            <option value="低">低</option>
          </select>
          <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="rounded border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700">
            <option value="全部">全部状态</option>
            <option value="待处理">待处理</option>
            <option value="待协调">待协调</option>
            <option value="待决策">待决策</option>
            <option value="待负责人确认">待负责人确认</option>
            <option value="已解决">已解决</option>
            <option value="已关闭">已关闭</option>
          </select>
          <input value={filterOwner} onChange={(e) => setFilterOwner(e.target.value)} placeholder="负责人" className="w-24 rounded border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:border-purple-400" />
          <input value={filterHelper} onChange={(e) => setFilterHelper(e.target.value)} placeholder="协助人" className="w-24 rounded border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:border-purple-400" />
          <input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="搜索问题摘要" className="min-w-[200px] flex-1 rounded border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 outline-none focus:border-purple-400" />
        </div>
      </header>

      {/* Issue List + Detail Panel */}
      <div className="min-h-0 flex-1 flex gap-4 px-5 py-4 overflow-hidden">
        {/* Issue list table */}
        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex items-center justify-center h-full text-sm text-slate-400">加载中...</div>
          ) : loadError ? (
            <div className="flex items-center justify-center h-full text-sm text-red-500">{loadError}</div>
          ) : filteredIssues.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <p className="text-sm font-semibold text-slate-500">无匹配结果</p>
              <p className="mt-1 text-xs text-slate-400">尝试调整筛选条件，或点击「新增问题」创建第一个问题。</p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-2.5 whitespace-nowrap">问题摘要 · 处理进度</th>
                    <th className="px-3 py-2.5 whitespace-nowrap">当前状态</th>
                    <th className="px-3 py-2.5 whitespace-nowrap">优先级</th>
                    <th className="px-3 py-2.5 whitespace-nowrap">负责人</th>
                    <th className="px-3 py-2.5 whitespace-nowrap">协助人</th>
                    <th className="px-3 py-2.5 whitespace-nowrap">关联任务</th>
                    <th className="px-3 py-2.5 whitespace-nowrap">更新时间</th>
                    <th className="px-3 py-2.5 text-center whitespace-nowrap">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredIssues.map((item) => {
                    const st = STATUS_STYLE[item.status || ''] || STATUS_STYLE['待处理']
                    const flowIndex = getIssueFlowIndex(item.status || '待处理')
                    const isClosedItem = item.status === '已关闭'
                    return (
                      <tr
                        key={item.id}
                        onClick={() => navigate(`/work/issues/${item.id}?projectId=${projectId}`)}
                        className="cursor-pointer transition-colors hover:bg-purple-50/30"
                      >
                        {/* 问题摘要 + 进度条 */}
                        <td className="px-4 py-2.5 max-w-[340px]">
                          <p className="font-bold text-slate-800 text-xs leading-snug line-clamp-2">{item.description || '未命名问题'}</p>
                          {/* 状态进度条 */}
                          {isClosedItem ? (
                            <p className="mt-1.5 text-[11px] font-medium text-slate-400">该问题已关闭</p>
                          ) : (
                            <div className="mt-2 flex items-center gap-0.5">
                              {ISSUE_FLOW.map((step, idx) => {
                                const isDone = idx < flowIndex
                                const isActive = idx === flowIndex
                                const isFuture = idx > flowIndex
                                return (
                                  <div key={step.key} className="flex items-center gap-0.5">
                                    {/* dot */}
                                    <span
                                      className={`inline-block rounded-full ${isActive ? 'w-2 h-2 ring-2 ring-offset-1' : 'w-1.5 h-1.5'}`}
                                      style={{
                                        background: isDone || isActive ? FLOW_DOT_COLORS[step.key] : '#E2E8F0',
                                        ...(isActive ? {
                                          width: 8, height: 8,
                                          boxShadow: `0 0 0 2px ${FLOW_DOT_COLORS[step.key]}33`,
                                          border: `1.5px solid ${FLOW_DOT_COLORS[step.key]}`,
                                          borderRadius: '50%',
                                        } : {}),
                                      }}
                                      title={step.label}
                                    />
                                    {/* connector line (except last) */}
                                    {idx < ISSUE_FLOW.length - 1 && (
                                      <span
                                        className="inline-block h-[2px] w-5 rounded-full"
                                        style={{ background: idx < flowIndex ? FLOW_DOT_COLORS[ISSUE_FLOW[idx + 1].key] : '#E2E8F0' }}
                                      />
                                    )}
                                  </div>
                                )
                              })}
                              <span className="ml-2 text-[10px] text-slate-400 font-medium">
                                {isClosedItem ? '' : `${flowIndex + 1}/${ISSUE_FLOW.length}`}
                              </span>
                            </div>
                          )}
                          {/* 额外信息 */}
                          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold border ${TYPE_STYLE[item.issue_type || ''] || 'bg-slate-50 text-slate-600 border-slate-200'}`}>
                              {item.issue_type || '问题'}
                            </span>
                            {issueSourceLabel(item) === 'AI确认入库' && (
                              <span className="inline-flex px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-purple-50 text-purple-600">
                                AI确认入库
                              </span>
                            )}
                          </div>
                        </td>
                        {/* 当前状态 */}
                        <td className="px-3 py-2.5">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold border ${st.badge}`}>
                            <span className="w-1.5 h-1.5 rounded-full" style={{ background: st.dot }}></span>
                            {item.status || '待处理'}
                          </span>
                        </td>
                        {/* 优先级 */}
                        <td className="px-3 py-2.5">
                          <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold border ${PRIORITY_STYLE[item.priority || ''] || PRIORITY_STYLE['中']}`}>
                            {item.priority || '中'}
                          </span>
                        </td>
                        {/* 负责人 */}
                        <td className="px-3 py-2.5 text-xs text-slate-600">{item.owner || '—'}</td>
                        {/* 协助人 */}
                        <td className="px-3 py-2.5 text-xs text-slate-600">{item.helper || '—'}</td>
                        {/* 关联任务 */}
                        <td className="px-3 py-2.5 text-xs text-slate-500 max-w-[160px]">
                          <p className="truncate">{taskNameForId(tasks, item.related_task_id as number | null | undefined)}</p>
                        </td>
                        {/* 更新时间 */}
                        <td className="px-3 py-2.5 text-xs text-slate-400 whitespace-nowrap">{fmtDate(item.updated_at) || '—'}</td>
                        {/* 操作 */}
                        <td className="px-3 py-2.5 text-center">
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); navigate(`/work/issues/${item.id}?projectId=${projectId}`) }}
                            className="rounded border border-purple-200 bg-white px-2.5 py-1 text-[11px] font-bold text-purple-600 hover:bg-purple-50 whitespace-nowrap"
                          >
                            查看详情
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>





    {/* Add Issue Modal */}
    {addOpen && (
      <AddIssueModal
        projects={projects}
        currentProjectId={projectId}
        currentUser={currentUser}
        tasks={tasks}
        tasksLoading={tasksLoading}
        projectArchived={projectArchived}
        onClose={() => setAddOpen(false)}
        onCreated={(item) => {
          setIssues((prev) => [item, ...prev])
          setAddOpen(false)
          toast.success('问题已创建')
          navigate(`/work/issues/${item.id}?projectId=${projectId}`)
        }}
      />
    )}
    </div>
    </>
  )
}

// ─── Detail Row ──────────────────────────────────────────
function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2 py-1 border-b border-slate-50">
      <span className="w-20 flex-shrink-0 text-slate-400 font-semibold">{label}</span>
      <span className="text-slate-800">{value || '—'}</span>
    </div>
  )
}

// ─── AddIssueModal ────────────────────────────────────────
type AddModalProps = {
  projects: Project[]
  currentProjectId: number | null
  currentUser: { name?: string } | null
  tasks: TaskItem[]
  tasksLoading: boolean
  projectArchived: boolean
  onClose: () => void
  onCreated: (item: IssueItem) => void
}

function AddIssueModal({ projects, currentProjectId, currentUser, tasks, tasksLoading, projectArchived, onClose, onCreated }: AddModalProps) {
  const [form, setForm] = useState({
    project_id: currentProjectId ?? (projects[0]?.id ?? null) as number | null,
    description: '',
    expected_resolve_time: '',
    related_task_id: null as number | null,
    related_subtask_id: null as number | null,
  })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')
  const [subtasks, setSubtasks] = useState<SubTaskItem[]>([])
  const [subtasksLoading, setSubtasksLoading] = useState(false)

  function setField(k: string, v: unknown) { setForm((prev) => ({ ...prev, [k]: v })) }

  useEffect(() => {
    if (!form.related_task_id) { setSubtasks([]); return }
    let cancelled = false
    setSubtasksLoading(true)
    fetchSubTasks(form.related_task_id)
      .then((rows) => { if (!cancelled) setSubtasks(rows.filter((row) => !row.is_deleted)) })
      .catch(() => { if (!cancelled) setSubtasks([]) })
      .finally(() => { if (!cancelled) setSubtasksLoading(false) })
    return () => { cancelled = true }
  }, [form.related_task_id])

  async function handleSubmit() {
    if (!form.description.trim()) { setErr('请填写问题描述'); return }
    if (!form.project_id) { setErr('请选择所属项目'); return }
    if (projectArchived) { setErr('项目已归档，不可新增问题'); return }
    setSaving(true); setErr('')
    try {
      const item = await createIssue({ project_id: form.project_id, description: form.description.trim(), expected_resolve_time: form.expected_resolve_time, related_task_id: form.related_task_id, related_subtask_id: form.related_subtask_id, issue_type: '问题', priority: '中', status: '待处理', source_type: '人工录入' })
      onCreated(item)
    } catch (e) {
      setErr(e instanceof Error ? e.message : '创建失败，请重试')
    } finally { setSaving(false) }
  }

  const inputCls = 'w-full text-sm border border-slate-200 rounded px-3 py-2 focus:outline-none focus:border-purple-400 bg-white'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 p-4">
      <div className="w-full max-w-xl rounded-xl bg-white shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="text-base font-bold text-slate-800">新增问题</h2>
          <button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-100">
            <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <div className="p-5 space-y-4">
          <p className="text-xs text-slate-500 leading-relaxed p-3 rounded-lg bg-purple-50 border border-purple-100">
            请描述你在项目推进中遇到的问题。问题等级、处理路径和协助人由项目负责人后续判断和分派。
          </p>
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1.5">所属项目 <span className="text-red-400">*</span></label>
            <select value={form.project_id ?? ''} onChange={(e) => setField('project_id', Number(e.target.value) || null)} className={inputCls}>
              <option value="">请选择</option>
              {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1.5">关联重点工作</label>
            {tasks.length === 0 ? (
              <p className="text-xs text-slate-400 mt-1">暂无重点工作</p>
            ) : (
              <select value={form.related_task_id ?? ''} onChange={(e) => { setField('related_task_id', e.target.value ? Number(e.target.value) : null); setField('related_subtask_id', null) }} className={inputCls}>
                <option value="">暂未关联</option>
                {tasks.map((t) => <option key={t.id} value={t.id}>{t.key_task}</option>)}
              </select>
            )}
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1.5">关联关键任务</label>
            <select value={form.related_subtask_id ?? ''} onChange={(e) => setField('related_subtask_id', e.target.value ? Number(e.target.value) : null)} disabled={!form.related_task_id || subtasksLoading} className={`${inputCls}${!form.related_task_id ? ' bg-slate-50 text-slate-400' : ''}`}>
              <option value="">{!form.related_task_id ? '请先选择重点工作' : subtasksLoading ? '加载中...' : subtasks.length === 0 ? '暂无关键任务' : '未指定关键任务'}</option>
              {subtasks.map((st) => <option key={st.id} value={st.id}>{st.title}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1.5">问题描述 <span className="text-red-400">*</span></label>
            <textarea value={form.description} onChange={(e) => setField('description', e.target.value)} rows={3}
              placeholder="请说明遇到的问题、影响范围、当前卡点。"
              className="w-full text-sm border border-slate-200 rounded px-3 py-2 focus:outline-none focus:border-purple-400 resize-none" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1.5">期望解决时间</label>
            <input type="date" value={form.expected_resolve_time} onChange={(e) => setField('expected_resolve_time', e.target.value)} className={inputCls} />
          </div>
          {err && <p className="text-xs text-red-500">{err}</p>}
          {projectArchived && <p className="text-xs text-amber-600">项目已归档，不可新增问题</p>}
        </div>
        <div className="flex justify-end gap-3 border-t border-slate-200 px-5 py-4">
          <button onClick={onClose} className="rounded border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600">取消</button>
          <button onClick={handleSubmit} disabled={saving || projectArchived}
            className="rounded px-5 py-2 text-sm font-bold text-white disabled:opacity-50 bg-purple-600 hover:bg-purple-700">
            {saving ? '创建中...' : '保存问题'}
          </button>
        </div>
      </div>
    </div>
  )
}
