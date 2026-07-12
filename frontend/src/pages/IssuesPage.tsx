import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { createIssue, closeIssue, resolveIssue, assignIssueHelper, requestIssueCeo, fetchIssues, updateIssueStatus } from '../api/issues'
import { fetchTasks } from '../api/tasks'
import { useProject } from '../context/ProjectContext'
import { toast } from '../utils/toast'
import { fmtDate } from '../utils/time'
import { isProjectArchived } from '../domain/projectLifecycleStatus'
import { getProjectDisplayName } from '../domain/projectDisplay'
import type { IssueItem, Project, TaskItem } from '../types'

const PRIORITY_STYLE: Record<string, string> = {
  '高': 'bg-red-100 text-red-700 border-red-200',
  '中': 'bg-amber-100 text-amber-700 border-amber-200',
  '低': 'bg-slate-100 text-slate-600 border-slate-200',
}

const STATUS_STYLE: Record<string, { badge: string; dot: string }> = {
  '待处理': { badge: 'bg-amber-100 text-amber-700 border-amber-200', dot: '#F59E0B' },
  '处理中': { badge: 'bg-blue-100 text-blue-700 border-blue-200', dot: '#3B82F6' },
  '待决策': { badge: 'bg-purple-100 text-purple-700 border-purple-200', dot: '#7C3AED' },
  '已解决': { badge: 'bg-emerald-100 text-emerald-700 border-emerald-200', dot: '#10B981' },
  '已关闭': { badge: 'bg-slate-200 text-slate-500 border-slate-200', dot: '#94A3B8' },
}

const TYPE_STYLE: Record<string, string> = {
  '问题': 'bg-orange-50 text-orange-700 border-orange-200',
  '风险': 'bg-red-50 text-red-700 border-red-200',
  '待协调': 'bg-blue-50 text-blue-700 border-blue-200',
  '需决策': 'bg-purple-50 text-purple-700 border-purple-200',
}

const KANBAN_COLUMNS = ['待处理', '处理中', '待决策', '已解决', '已关闭'] as const

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
  const count = project.member_counts?.project_ceo ?? 0
  return count > 0 ? `${count} 位企业教练` : '未配置'
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

export function IssuesPage() {
  const { projects, currentUser } = useProject()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const projectId = parseProjectId(searchParams)
  const currentProject = projects.find((p) => p.id === projectId) ?? null
  const projectArchived = isProjectArchived(currentProject)

  // issues state
  const [issues, setIssues] = useState<IssueItem[]>([])
  const [selected, setSelected] = useState<IssueItem | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')

  // tasks
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [tasksLoading, setTasksLoading] = useState(false)

  // filters
  const [filterType, setFilterType] = useState('全部')
  const [filterPriority, setFilterPriority] = useState('全部')
  const [filterOwner, setFilterOwner] = useState('')
  const [filterHelper, setFilterHelper] = useState('')
  const [keyword, setKeyword] = useState('')

  // project search
  const [projectSearch, setProjectSearch] = useState('')

  // add modal
  const [addOpen, setAddOpen] = useState(false)

  // right panel actions
  const [actionLoading, setActionLoading] = useState(false)
  const [actionErr, setActionErr] = useState('')
  const [resolutionInput, setResolutionInput] = useState('')
  const [handlerReplyInput, setHandlerReplyInput] = useState('')
  const [helperInput, setHelperInput] = useState('')
  const [ceoTarget, setCeoTarget] = useState('')
  const [ceoNote, setCeoNote] = useState('')
  const [showCeoForm, setShowCeoForm] = useState(false)
  const [closeReason, setCloseReason] = useState('')

  const visibleProjects = useMemo(() => {
    const term = projectSearch.trim().toLowerCase()
    if (!term) return projects
    return projects.filter((p) => p.name.toLowerCase().includes(term))
  }, [projects, projectSearch])

  // --- Load issues when projectId is set ---
  useEffect(() => {
    if (!projectId) {
      setIssues([]); setSelected(null); setLoadError(''); return
    }
    let cancelled = false
    setLoading(true); setLoadError('')
    fetchIssues(projectId)
      .then((rows) => {
        if (cancelled) return
        setIssues(rows)
        setSelected((prev) => rows.find((r) => r.id === prev?.id) ?? rows[0] ?? null)
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

  // --- Derived data ---
  const filteredIssues = useMemo(() => {
    const term = keyword.trim().toLowerCase()
    return issues.filter((item) => {
      if (filterType !== '全部' && item.issue_type !== filterType) return false
      if (filterPriority !== '全部' && item.priority !== filterPriority) return false
      if (filterOwner && (item.owner || '') !== filterOwner) return false
      if (filterHelper && (item.helper || '') !== filterHelper) return false
      if (term && !(item.description || '').toLowerCase().includes(term)) return false
      return true
    })
  }, [issues, filterType, filterPriority, filterOwner, filterHelper, keyword])

  const groupedByStatus = useMemo(() => {
    const map: Record<string, IssueItem[]> = {}
    KANBAN_COLUMNS.forEach((col) => { map[col] = [] })
    filteredIssues.forEach((item) => {
      const s = item.status || '待处理'
      if (map[s]) map[s].push(item)
    })
    return map
  }, [filteredIssues])

  const stats = useMemo(() => {
    const pending = issues.filter((i) => i.status === '待处理').length
    const processing = issues.filter((i) => i.status === '处理中').length
    const decision = issues.filter((i) => i.status === '待决策').length
    const closed = issues.filter((i) => i.status === '已关闭').length
    return { total: issues.length, pending, processing, decision, closed }
  }, [issues])

  // --- Reset action state when selection changes ---
  useEffect(() => {
    setActionErr('')
    setResolutionInput(selected?.resolution ?? '')
    setHandlerReplyInput(selected?.handler_reply ?? '')
    setHelperInput(selected?.helper ?? '')
    setCeoTarget('')
    setCeoNote('')
    setShowCeoForm(false)
    setCloseReason('')
  }, [selected?.id])

  // --- Actions ---
  function reload() {
    if (!projectId) return
    fetchIssues(projectId)
      .then((rows) => {
        setIssues(rows)
        setSelected((prev) => rows.find((r) => r.id === prev?.id) ?? rows[0] ?? null)
      })
      .catch(() => {})
  }

  async function doAction(fn: () => Promise<IssueItem>) {
    setActionLoading(true); setActionErr('')
    try {
      const updated = await fn()
      setIssues((prev) => prev.map((i) => i.id === updated.id ? updated : i))
      setSelected(updated)
      setShowCeoForm(false)
    } catch (e: unknown) {
      setActionErr(e instanceof Error ? e.message : '操作失败')
    } finally { setActionLoading(false) }
  }

  function handleResolve() {
    if (!selected) return
    doAction(() => resolveIssue(selected.id, resolutionInput.trim(), handlerReplyInput.trim()))
  }

  function handleClose() {
    if (!selected) return
    doAction(() => closeIssue(selected.id, closeReason.trim(), handlerReplyInput.trim()))
  }

  function handleAssignHelper() {
    if (!selected || !helperInput.trim()) return
    doAction(() => assignIssueHelper(selected.id, helperInput.trim()))
  }

  function handleRequestCeo() {
    if (!selected || !ceoTarget.trim()) return
    doAction(() => requestIssueCeo(selected.id, ceoTarget.trim(), ceoNote.trim()))
  }

  async function handleStartProcessing() {
    if (!selected) return
    setActionLoading(true); setActionErr('')
    try {
      const updated = await updateIssueStatus(selected.id, '处理中')
      setIssues((prev) => prev.map((i) => i.id === updated.id ? updated : i))
      setSelected(updated)
      toast.success('已开始处理')
    } catch (e: unknown) {
      setActionErr(e instanceof Error ? e.message : '操作失败')
    } finally { setActionLoading(false) }
  }

  // ============ PROJECT SELECTION PAGE ============
  if (!projectId) {
    return (
      <div className="flex-1 overflow-y-auto bg-[#f6f8fb]">
        <div className="mx-auto max-w-[1440px] px-6 py-6">
          <div className="mb-6 flex items-start justify-between gap-5">
            <div>
              <p className="text-[11px] font-extrabold uppercase tracking-[0.24em] text-purple-600">ISSUE CENTER</p>
              <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950">项目问题中心</h1>
              <p className="mt-2 text-sm text-slate-500">请先选择一个项目，进入后查看和处理该项目问题。</p>
            </div>
            <div className="w-80 rounded border border-slate-200 bg-white px-4 py-2.5 shadow-sm">
              <label className="text-[11px] font-bold uppercase tracking-wide text-slate-400">搜索项目名称</label>
              <input
                value={projectSearch}
                onChange={(e) => setProjectSearch(e.target.value)}
                placeholder="搜索项目名称"
                className="mt-1.5 w-full border-0 p-0 text-sm font-medium text-slate-800 outline-none placeholder:text-slate-300"
              />
            </div>
          </div>

          <div className="mb-6 grid grid-cols-4 gap-4">
            {[
              ['可查看项目数', projects.length],
              ['待处理问题', '—'],
              ['处理中问题', '—'],
              ['待决策事项', '—'],
            ].map(([label, value]) => (
              <div key={label} className="rounded border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">{label}</p>
                <p className="mt-2 text-2xl font-black tabular-nums text-slate-950">{value}</p>
              </div>
            ))}
          </div>

          <div className="overflow-hidden rounded border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-5 py-3">
              <div>
                <h2 className="text-base font-bold text-slate-900">选择项目问题中心</h2>
                <p className="mt-0.5 text-xs text-slate-500">请先选择一个项目，进入后查看该项目问题看板。</p>
              </div>
              <div className="flex gap-2">
                <button type="button" disabled className="rounded border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-400">筛选</button>
                <button type="button" disabled className="rounded border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-400">排序</button>
              </div>
            </div>
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
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ============ KANBAN BOARD PAGE ============
  const selectedStatus = selected?.status || ''
  const selectedType = selected?.issue_type || ''
  const isTerminal = selectedStatus === '已解决' || selectedStatus === '已关闭'
  const isClosed = selectedStatus === '已关闭'
  const isDecision = selectedType === '需决策'
  const canOwnerWrite = !projectArchived

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
            <button type="button" onClick={reload} className="rounded border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50">刷新</button>
            <button type="button" onClick={() => setAddOpen(true)} disabled={projectArchived} className="rounded bg-purple-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-purple-700 disabled:cursor-not-allowed disabled:opacity-50">新增问题</button>
          </div>
        </div>

        {/* Stats bar */}
        <div className="mt-4 grid grid-cols-5 overflow-hidden rounded-lg border border-slate-200 bg-white">
          {[
            ['问题总数', stats.total],
            ['待处理', stats.pending],
            ['处理中', stats.processing],
            ['待决策', stats.decision],
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
          <input value={filterOwner} onChange={(e) => setFilterOwner(e.target.value)} placeholder="负责人" className="w-24 rounded border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:border-purple-400" />
          <input value={filterHelper} onChange={(e) => setFilterHelper(e.target.value)} placeholder="协助人" className="w-24 rounded border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700 outline-none focus:border-purple-400" />
          <input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="搜索问题摘要" className="min-w-[200px] flex-1 rounded border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 outline-none focus:border-purple-400" />
        </div>
      </header>

      {/* Kanban + Detail Panel */}
      <div className="min-h-0 flex-1 flex gap-4 px-5 py-4 overflow-hidden">
        {/* Kanban area */}
        <div className="flex-1 overflow-x-auto overflow-y-hidden">
          {loading ? (
            <div className="flex items-center justify-center h-full text-sm text-slate-400">加载中...</div>
          ) : loadError ? (
            <div className="flex items-center justify-center h-full text-sm text-red-500">{loadError}</div>
          ) : (
            <div className="flex gap-4 min-h-full h-full">
              {KANBAN_COLUMNS.map((col) => {
                const colIssues = groupedByStatus[col] || []
                const isColPending = col === '待处理'
                const isColClosed = col === '已关闭'
                let colBorderClass = 'border-slate-200'
                if (isColPending) colBorderClass = 'border-amber-200'
                else if (col === '处理中') colBorderClass = 'border-blue-200'
                else if (col === '待决策') colBorderClass = 'border-purple-200'
                else if (col === '已解决') colBorderClass = 'border-emerald-200'

                return (
                  <div key={col} className={`flex min-w-[280px] max-w-[340px] flex-1 flex-col rounded-lg border bg-slate-50/60 ${colBorderClass}`}>
                    <div className="flex items-center justify-between px-3 py-2 border-b border-slate-200 bg-white rounded-t-lg">
                      <span className="text-xs font-bold text-slate-700">{col}</span>
                      <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[11px] font-bold text-slate-600">{colIssues.length}</span>
                    </div>
                    <div className="flex-1 overflow-y-auto p-2 space-y-2">
                      {colIssues.length === 0 ? (
                        <p className="py-8 text-center text-xs text-slate-400">
                          {isColClosed ? '暂无已关闭问题' : `暂无${col}问题`}
                        </p>
                      ) : colIssues.map((item) => {
                        const active = selected?.id === item.id
                        const st = STATUS_STYLE[item.status || ''] || STATUS_STYLE['待处理']
                        const source = issueSourceLabel(item)
                        return (
                          <div
                            key={item.id}
                            onClick={() => setSelected(item)}
                            className={`cursor-pointer rounded border bg-white p-3 shadow-sm transition hover:shadow-md ${active ? 'ring-2 ring-purple-400 border-purple-300' : 'border-slate-200'}`}
                          >
                            <p className="text-sm font-bold text-slate-800 leading-snug line-clamp-2">{item.description || '未命名问题'}</p>
                            <div className="mt-2 flex flex-wrap items-center gap-1.5">
                              <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold border ${TYPE_STYLE[item.issue_type || ''] || 'bg-slate-50 text-slate-600 border-slate-200'}`}>
                                {item.issue_type || '问题'}
                              </span>
                              <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold border ${PRIORITY_STYLE[item.priority || ''] || PRIORITY_STYLE['中']}`}>
                                {item.priority || '中'}
                              </span>
                            </div>
                            <div className="mt-2 text-[11px] text-slate-500 space-y-0.5">
                              <p>负责人：{item.owner || '—'}</p>
                              <p>协助人：{item.helper || '—'}</p>
                              {item.reporter && <p>上报人：{item.reporter}</p>}
                              {item.expected_resolve_time && <p>预计解决：{item.expected_resolve_time}</p>}
                              <p>
                                <span className={`inline-flex px-1.5 py-0.5 rounded-full text-[10px] font-bold ${source === 'AI确认入库' ? 'bg-purple-50 text-purple-600' : 'bg-slate-100 text-slate-500'}`}>
                                  {source}
                                </span>
                              </p>
                              <p>关联重点工作：{taskNameForId(tasks, item.related_task_id as number | null | undefined)}</p>
                              <p className="text-slate-400">关键任务：暂未关联</p>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Right detail panel */}
        {selected && (
          <div className="w-[320px] flex-shrink-0 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm flex flex-col">
            {/* Fixed header */}
            <div className="flex-shrink-0 px-4 pt-4 pb-3 border-b border-slate-200">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-bold text-slate-800">问题详情</h2>
                <button onClick={() => setSelected(null)} className="p-1 rounded hover:bg-slate-100 text-slate-400">
                  <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>
              <p className="text-sm font-bold text-slate-800 leading-snug">{selected.description || '—'}</p>
              <div className="flex items-center gap-2 mt-2">
                <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold ${PRIORITY_STYLE[selected.priority || ''] || PRIORITY_STYLE['中']}`}>{selected.priority || '—'}</span>
                <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold border ${STATUS_STYLE[selectedStatus]?.badge || 'bg-slate-100 text-slate-600 border-slate-200'}`}>
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: STATUS_STYLE[selectedStatus]?.dot || '#94A3B8' }}></span>
                  {selectedStatus || '—'}
                </span>
              </div>
            </div>

            {/* Scrollable body */}
            <div className="flex-1 overflow-y-auto px-4 py-3" style={{ minHeight: 0 }}>
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">问题信息</h3>
              <div className="space-y-2 text-xs">
                <DetailRow label="所属项目" value={currentProject?.name || selected.special_project || '—'} />
                <DetailRow label="来源" value={issueSourceLabel(selected)} />
                <DetailRow label="问题类型" value={selectedType || '—'} />
                <DetailRow label="关联重点工作" value={taskNameForId(tasks, selected.related_task_id as number | null | undefined)} />
                <DetailRow label="关联关键任务" value="暂未关联" />
                <DetailRow label="上报人" value={selected.reporter || '—'} />
                <DetailRow label="负责人" value={selected.owner || '—'} />
                <DetailRow label="协助人" value={selected.helper || '—'} />
                <DetailRow label="需决策人" value={selected.need_decision_by || '—'} />
                <DetailRow label="预计解决时间" value={selected.expected_resolve_time || '—'} />
                <DetailRow label="创建时间" value={fmtDate(selected.created_at) || '—'} />
                <DetailRow label="更新时间" value={fmtDate(selected.updated_at) || '—'} />
              </div>

              {isTerminal && selected.resolution && (
                <div className="mt-4">
                  <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">{isDecision ? '决策结论' : '处理结论'}</p>
                  <p className="text-xs text-slate-600 leading-relaxed p-3 rounded-lg" style={{ background: '#F0FDF4', border: '1px solid #BBF7D0' }}>{selected.resolution}</p>
                </div>
              )}
              {isTerminal && selected.handler_reply && (
                <div className="mt-3">
                  <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">回复给上报人</p>
                  <p className="text-xs text-amber-800 leading-relaxed p-3 rounded-lg" style={{ background: '#FFFBEB', border: '1px solid #FDE68A' }}>{selected.handler_reply}</p>
                </div>
              )}
            </div>

            {/* Action area */}
            {!isClosed && (
              <div className="flex-shrink-0 px-4 py-3 border-t border-slate-200">
                {actionErr && <p className="text-xs text-red-500 mb-2">{actionErr}</p>}

                {!isTerminal && (
                  <>
                    {/* 开始处理 */}
                    {selectedStatus === '待处理' && (
                      <button
                        onClick={handleStartProcessing}
                        disabled={actionLoading || projectArchived}
                        className="w-full py-2 rounded text-xs font-bold text-white mb-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
                      >
                        开始处理
                      </button>
                    )}

                    {/* 处理中/待决策: resolution input */}
                    {selectedStatus !== '待处理' && (
                      <div className="mb-2">
                        <p className="text-xs font-semibold text-slate-500 mb-1">{isDecision ? '决策结论' : '处理结论'}</p>
                        <textarea
                          value={resolutionInput}
                          onChange={(e) => setResolutionInput(e.target.value)}
                          rows={2}
                          placeholder={isDecision ? '请输入最终决策结论' : '请输入处理措施、结果或后续安排'}
                          className="w-full text-xs border border-slate-200 rounded px-2 py-1.5 focus:outline-none focus:border-purple-400 resize-none leading-relaxed"
                        />
                      </div>
                    )}

                    {selectedStatus === '处理中' && selected.reporter && (
                      <div className="mb-2">
                        <p className="text-xs font-semibold text-slate-500 mb-1">回复给上报人 <span className="font-normal text-slate-400">（{selected.reporter}，选填）</span></p>
                        <textarea
                          value={handlerReplyInput}
                          onChange={(e) => setHandlerReplyInput(e.target.value)}
                          rows={2}
                          placeholder="填写后会在上报人的工作台展示"
                          className="w-full text-xs border border-amber-200 rounded px-2 py-1.5 focus:outline-none focus:border-amber-400 resize-none leading-relaxed"
                          style={{ background: '#FFFBEB' }}
                        />
                      </div>
                    )}

                    {/* 指定协助人 */}
                    <div className="mb-2">
                      <p className="text-xs font-semibold text-slate-500 mb-1">协助人</p>
                      <div className="flex gap-1.5">
                        <input
                          value={helperInput}
                          onChange={(e) => setHelperInput(e.target.value)}
                          placeholder="输入协助人姓名"
                          className="flex-1 text-xs border border-slate-200 rounded px-2 py-1.5 focus:outline-none focus:border-purple-400"
                        />
                        <button
                          onClick={handleAssignHelper}
                          disabled={actionLoading || !helperInput.trim() || projectArchived}
                          className="text-xs text-white font-semibold px-2.5 py-1.5 rounded disabled:opacity-50 bg-purple-600"
                        >指定</button>
                      </div>
                    </div>

                    {/* 标记已解决 */}
                    <button
                      onClick={handleResolve}
                      disabled={actionLoading || projectArchived}
                      className="w-full py-2 rounded text-white text-xs font-bold hover:opacity-90 disabled:opacity-50 mb-2"
                      style={{ background: isDecision ? 'linear-gradient(135deg,#7C3AED,#A78BFA)' : 'linear-gradient(135deg,#059669,#34D399)' }}
                    >
                      {isDecision ? '确认决策' : '标记已解决'}
                    </button>

                    {/* 上报Coach */}
                    <div>
                      <button
                        onClick={() => setShowCeoForm(!showCeoForm)}
                        className="text-xs font-medium cursor-pointer text-purple-600"
                      >
                        {showCeoForm ? '▲ 收起' : '▼ 上报Coach'}
                      </button>
                      {showCeoForm && (
                        <div className="mt-2 space-y-1.5">
                          <input
                            value={ceoTarget}
                            onChange={(e) => setCeoTarget(e.target.value)}
                            placeholder="企业教练"
                            className="w-full text-xs border border-slate-200 rounded px-2 py-1.5 focus:outline-none focus:border-purple-400"
                          />
                          <textarea
                            value={ceoNote}
                            onChange={(e) => setCeoNote(e.target.value)}
                            rows={2}
                            placeholder="上报说明（可选）"
                            className="w-full text-xs border border-slate-200 rounded px-2 py-1.5 focus:outline-none focus:border-purple-400 resize-none"
                          />
                          <button
                            onClick={handleRequestCeo}
                            disabled={actionLoading || !ceoTarget.trim() || projectArchived}
                            className="w-full py-1.5 rounded text-white text-xs font-bold hover:opacity-90 disabled:opacity-50 bg-purple-600"
                          >确认上报</button>
                        </div>
                      )}
                    </div>
                  </>
                )}

                {/* 已解决: close section */}
                {selectedStatus === '已解决' && (
                  <>
                    <p className="text-xs font-semibold text-slate-500 mb-1">关闭说明（可选）</p>
                    <textarea
                      value={closeReason}
                      onChange={(e) => setCloseReason(e.target.value)}
                      rows={2}
                      placeholder="关闭原因或备注"
                      className="w-full text-xs border border-slate-200 rounded px-2 py-1.5 focus:outline-none resize-none mb-2 leading-relaxed"
                    />
                    <button
                      onClick={handleClose}
                      disabled={actionLoading}
                      className="w-full py-2 rounded border border-slate-200 text-slate-600 text-xs font-semibold hover:bg-slate-50 disabled:opacity-50"
                    >关闭事项</button>
                  </>
                )}
              </div>
            )}
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
          setSelected(item)
          setAddOpen(false)
          toast.success('问题已创建')
        }}
      />
    )}
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
    issue_type: '问题',
    description: '',
    owner: currentUser?.name || '',
    helper: '',
    priority: '中',
    expected_resolve_time: '',
    related_task_id: null as number | null,
  })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  function setField(k: string, v: unknown) { setForm((prev) => ({ ...prev, [k]: v })) }

  async function handleSubmit() {
    if (!form.description.trim()) { setErr('请填写问题描述'); return }
    if (!form.project_id) { setErr('请选择所属项目'); return }
    if (projectArchived) { setErr('项目已归档，不可新增问题'); return }
    setSaving(true); setErr('')
    try {
      const item = await createIssue({ project_id: form.project_id, issue_type: form.issue_type, description: form.description.trim(), owner: form.owner, helper: form.helper, priority: form.priority, expected_resolve_time: form.expected_resolve_time, related_task_id: form.related_task_id })
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
              <select value={form.related_task_id ?? ''} onChange={(e) => setField('related_task_id', e.target.value ? Number(e.target.value) : null)} className={inputCls}>
                <option value="">暂未关联</option>
                {tasks.map((t) => <option key={t.id} value={t.id}>{t.key_task}</option>)}
              </select>
            )}
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1.5">关联关键任务</label>
            <select disabled className={`${inputCls} bg-slate-50 text-slate-400`}>
              <option>暂未关联</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1.5">问题类型</label>
            <select value={form.issue_type} onChange={(e) => setField('issue_type', e.target.value)} className={inputCls}>
              <option>问题</option><option>风险</option><option>待协调</option><option>需决策</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1.5">问题摘要 / 描述 <span className="text-red-400">*</span></label>
            <textarea value={form.description} onChange={(e) => setField('description', e.target.value)} rows={3}
              placeholder="描述问题、影响范围和期望结果"
              className="w-full text-sm border border-slate-200 rounded px-3 py-2 focus:outline-none focus:border-purple-400 resize-none" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1.5">负责人</label>
              <input value={form.owner} onChange={(e) => setField('owner', e.target.value)} placeholder="姓名" className={inputCls} />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1.5">协助人</label>
              <input value={form.helper} onChange={(e) => setField('helper', e.target.value)} placeholder="姓名" className={inputCls} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1.5">优先级</label>
              <select value={form.priority} onChange={(e) => setField('priority', e.target.value)} className={inputCls}>
                <option>高</option><option>中</option><option>低</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1.5">预计解决时间</label>
              <input type="date" value={form.expected_resolve_time} onChange={(e) => setField('expected_resolve_time', e.target.value)} className={inputCls} />
            </div>
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
