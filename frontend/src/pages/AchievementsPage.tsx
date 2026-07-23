import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { createAchievement, fetchAchievements, updateAchievement } from '../api/achievements'
import { fetchTasks } from '../api/tasks'
import { fetchSubTasks, fetchSubtasksByProject } from '../api/subtasks'
import { useProject } from '../context/ProjectContext'
import { getAchievementAddressAction } from '../domain/achievementFlow'
import { isProjectArchived } from '../domain/projectLifecycleStatus'
import type { AchievementItem, Project, SubTaskItem, TaskItem } from '../types'

const ACHIEVEMENT_TYPES = ['方案', '模板', 'SOP', 'Prompt', 'Agent', '文档'] as const
const SOURCE_OPTIONS = ['全部', 'AI确认入库', '手动登记'] as const
const DATE_OPTIONS = ['全部', '本周', '本月'] as const

type RegistrationForm = {
  project_id: number | null
  related_task_id: number | null
  related_subtask_id: number | null
  name: string
  achievement_type: string
  version: string
  reuse_tag: string
  file_link: string
  scenario: string
  description: string
}

function parseProjectId(searchParams: URLSearchParams): number | null {
  const raw = searchParams.get('projectId')
  if (!raw) return null
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : null
}

function formatDate(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 10)
  return date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

function isThisMonth(value?: string | null): boolean {
  if (!value) return false
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return false
  const now = new Date()
  return date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth()
}

function isThisWeek(value?: string | null): boolean {
  if (!value) return false
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return false
  const now = new Date()
  const start = new Date(now)
  const day = start.getDay() || 7
  start.setDate(start.getDate() - day + 1)
  start.setHours(0, 0, 0, 0)
  const end = new Date(start)
  end.setDate(start.getDate() + 7)
  return date >= start && date < end
}

function sourceLabel(item: AchievementItem): 'AI确认入库' | '手动登记' | '来源未标明' {
  if (item.source_submission_id) return 'AI确认入库'
  const raw = String(item.source_type || '').toLowerCase()
  if (['ai', 'ai_extract', 'confirmation', 'confirmed', 'voice', 'meeting'].some((key) => raw.includes(key))) {
    return 'AI确认入库'
  }
  if (['manual', 'text', 'input', 'typed'].some((key) => raw.includes(key)) || !raw) return '手动登记'
  if (String(item.source_type || '').includes('人工') || String(item.source_type || '').includes('手动')) return '手动登记'
  return '来源未标明'
}

function typeBadgeClass(type?: string): string {
  switch (type) {
    case '方案': return 'border-blue-100 bg-blue-50 text-blue-700'
    case '模板': return 'border-amber-100 bg-amber-50 text-amber-700'
    case 'SOP': return 'border-emerald-100 bg-emerald-50 text-emerald-700'
    case 'Prompt': return 'border-indigo-100 bg-indigo-50 text-indigo-700'
    case 'Agent': return 'border-purple-100 bg-purple-50 text-purple-700'
    case '文档': return 'border-cyan-100 bg-cyan-50 text-cyan-700'
    default: return 'border-slate-100 bg-slate-50 text-slate-600'
  }
}

function projectStatusLabel(project?: Project | null): string {
  if (!project) return '未选择'
  const map: Record<string, string> = {
    draft: '草稿',
    dispatched: '已派发',
    pending_review: '待审核',
    returned: '已退回',
    active: '进行中',
    archived: '已归档',
  }
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

function taskName(tasks: TaskItem[], taskId?: number | null): string {
  if (!taskId) return '未关联重点工作'
  return tasks.find((task) => task.id === taskId)?.key_task || `重点工作 #${taskId}`
}

function keyTaskLabelForAchievement(item: AchievementItem, subtaskById: Record<number, SubTaskItem>): string {
  // 优先通过 related_subtask_id 在本地 map 中查找名称
  if (item.related_subtask_id && subtaskById[item.related_subtask_id]) {
    return subtaskById[item.related_subtask_id].title
  }
  // 兼容旧字段（后端可能返回的字符串字段）
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

function emptyForm(projectId: number | null): RegistrationForm {
  return {
    project_id: projectId,
    related_task_id: null,
    related_subtask_id: null,
    name: '',
    achievement_type: '方案',
    version: 'V0.1',
    reuse_tag: '',
    file_link: '',
    scenario: '',
    description: '',
  }
}

export function AchievementsPage() {
  const { projects, currentUser } = useProject()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const projectId = parseProjectId(searchParams)
  const currentProject = projects.find((project) => project.id === projectId) ?? null
  const projectArchived = isProjectArchived(currentProject)

  const [items, setItems] = useState<AchievementItem[]>([])
  const [selected, setSelected] = useState<AchievementItem | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [projectSearch, setProjectSearch] = useState('')
  const [projectAchievementSummary, setProjectAchievementSummary] = useState<Record<number, { count: number; month: number; lastUpdated: string | null }>>({})
  const [overviewLoading, setOverviewLoading] = useState(false)
  const [overviewPage, setOverviewPage] = useState(1)
  const [filterType, setFilterType] = useState('全部')
  const [filterTaskId, setFilterTaskId] = useState('')
  const [filterSource, setFilterSource] = useState<(typeof SOURCE_OPTIONS)[number]>('全部')
  const [filterDate, setFilterDate] = useState<(typeof DATE_OPTIONS)[number]>('全部')
  const [keyword, setKeyword] = useState('')
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [tasksLoading, setTasksLoading] = useState(false)
  const [subtasks, setSubtasks] = useState<SubTaskItem[]>([])
  const [subtasksLoading, setSubtasksLoading] = useState(false)
  const [allSubtasks, setAllSubtasks] = useState<SubTaskItem[]>([])
  const [registerOpen, setRegisterOpen] = useState(false)
  const [registerForm, setRegisterForm] = useState<RegistrationForm>(() => emptyForm(projectId))
  const [registerError, setRegisterError] = useState('')
  const [registerSaving, setRegisterSaving] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [editError, setEditError] = useState('')
  const [editSaving, setEditSaving] = useState(false)
  const [editDraft, setEditDraft] = useState({ name: '', version: '', file_link: '', scenario: '', reuse_tag: '' })

  const visibleProjects = useMemo(() => {
    const term = projectSearch.trim().toLowerCase()
    if (!term) return projects
    return projects.filter((project) => project.name.toLowerCase().includes(term))
  }, [projects, projectSearch])
  const overviewPageSize = 8
  const overviewPageCount = Math.max(1, Math.ceil(visibleProjects.length / overviewPageSize))
  const pagedProjects = visibleProjects.slice((overviewPage - 1) * overviewPageSize, overviewPage * overviewPageSize)
  const overviewStats = useMemo(() => {
    const summaries = Object.values(projectAchievementSummary)
    const latest = projects
      .map((project) => ({ project, value: projectAchievementSummary[project.id]?.lastUpdated }))
      .filter((entry): entry is { project: Project; value: string } => Boolean(entry.value))
      .sort((a, b) => new Date(b.value).getTime() - new Date(a.value).getTime())[0]
    return {
      total: summaries.reduce((sum, item) => sum + item.count, 0),
      month: summaries.reduce((sum, item) => sum + item.month, 0),
      latestProject: latest?.project.name || '—',
    }
  }, [projectAchievementSummary, projects])

  const filteredItems = useMemo(() => {
    const term = keyword.trim().toLowerCase()
    return items.filter((item) => {
      if (filterType !== '全部' && item.achievement_type !== filterType) return false
      if (filterTaskId && String(item.related_task_id || '') !== filterTaskId) return false
      if (filterSource !== '全部' && sourceLabel(item) !== filterSource) return false
      if (filterDate === '本周' && !isThisWeek(item.confirmed_at || item.updated_at || item.created_at)) return false
      if (filterDate === '本月' && !isThisMonth(item.confirmed_at || item.updated_at || item.created_at)) return false
      if (term && !(item.name || '').toLowerCase().includes(term)) return false
      return true
    })
  }, [items, filterType, filterTaskId, filterSource, filterDate, keyword])

  const stats = useMemo(() => {
    const manual = items.filter((item) => sourceLabel(item) === '手动登记').length
    const ai = items.filter((item) => sourceLabel(item) === 'AI确认入库').length
    const taskCount = new Set(items.map((item) => item.related_task_id).filter(Boolean)).size
    return {
      total: items.length,
      month: items.filter((item) => isThisMonth(item.confirmed_at || item.updated_at || item.created_at)).length,
      ai,
      manual,
      taskCount,
    }
  }, [items])

  const selectedTaskName = selected ? taskName(tasks, selected.related_task_id) : '—'

  useEffect(() => {
    if (!projectId) {
      setItems([])
      setSelected(null)
      setTasks([])
      setLoadError('')
      return
    }
    let cancelled = false
    setLoading(true)
    setLoadError('')
    fetchAchievements(projectId)
      .then((rows) => {
        if (cancelled) return
        setItems(rows)
        setSelected((prev) => {
          if (!prev) return rows[0] ?? null
          return rows.find((item) => item.id === prev.id) ?? rows[0] ?? null
        })
      })
      .catch((error: unknown) => {
        if (!cancelled) setLoadError(error instanceof Error ? error.message : '成果库加载失败')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [projectId])

  useEffect(() => {
    if (projectId) return
    let cancelled = false
    setOverviewLoading(true)
    Promise.allSettled(projects.map(async (project) => {
      const rows = await fetchAchievements(project.id)
      const dates = rows
        .map((item) => item.confirmed_at || item.updated_at || item.created_at)
        .filter((value): value is string => Boolean(value))
      return {
        projectId: project.id,
        count: rows.length,
        month: rows.filter((item) => isThisMonth(item.confirmed_at || item.updated_at || item.created_at)).length,
        lastUpdated: dates.sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0] || null,
      }
    }))
      .then((results) => {
        if (cancelled) return
        const next: Record<number, { count: number; month: number; lastUpdated: string | null }> = {}
        for (const result of results) if (result.status === 'fulfilled') next[result.value.projectId] = result.value
        setProjectAchievementSummary(next)
      })
      .finally(() => { if (!cancelled) setOverviewLoading(false) })
    return () => { cancelled = true }
  }, [projectId, projects])

  useEffect(() => {
    setOverviewPage(1)
  }, [projectSearch])

  useEffect(() => {
    if (!projectId) return
    let cancelled = false
    setTasksLoading(true)
    fetchTasks(projectId)
      .then((rows) => { if (!cancelled) setTasks(rows.filter((task) => !task.is_deleted)) })
      .catch(() => { if (!cancelled) setTasks([]) })
      .finally(() => { if (!cancelled) setTasksLoading(false) })
    return () => { cancelled = true }
  }, [projectId])

  useEffect(() => {
    if (!registerForm.related_task_id) {
      setSubtasks([])
      return
    }
    let cancelled = false
    setSubtasksLoading(true)
    fetchSubTasks(registerForm.related_task_id)
      .then((rows) => { if (!cancelled) setSubtasks(rows.filter((row) => !row.is_deleted)) })
      .catch(() => { if (!cancelled) setSubtasks([]) })
      .finally(() => { if (!cancelled) setSubtasksLoading(false) })
    return () => { cancelled = true }
  }, [registerForm.related_task_id])

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

  function reloadCurrentProject() {
    if (!projectId) return
    setLoading(true)
    setLoadError('')
    fetchAchievements(projectId)
      .then((rows) => {
        setItems(rows)
        setSelected((prev) => rows.find((item) => item.id === prev?.id) ?? rows[0] ?? null)
      })
      .catch((error: unknown) => setLoadError(error instanceof Error ? error.message : '成果库加载失败'))
      .finally(() => setLoading(false))
  }

  function openRegisterModal() {
    setRegisterError('')
    setRegisterForm(emptyForm(projectId))
    setRegisterOpen(true)
  }

  async function handleSaveAchievement() {
    if (!registerForm.project_id) { setRegisterError('请选择所属项目'); return }
    if (!registerForm.related_task_id) { setRegisterError('请选择关联重点工作'); return }
    if (!registerForm.name.trim()) { setRegisterError('请填写成果名称'); return }
    setRegisterSaving(true)
    setRegisterError('')
    try {
      const scenarioParts = [registerForm.description.trim(), registerForm.scenario.trim()].filter(Boolean)
      const created = await createAchievement({
        project_id: registerForm.project_id,
        related_task_id: registerForm.related_task_id,
        related_subtask_id: registerForm.related_subtask_id,
        name: registerForm.name.trim(),
        achievement_type: registerForm.achievement_type || '方案',
        owner: currentUser?.name || '',
        version: registerForm.version.trim() || 'V0.1',
        file_link: registerForm.file_link.trim(),
        scenario: scenarioParts.join('\n\n'),
        reuse_tag: registerForm.reuse_tag.trim(),
        source_type: 'manual',
        status: '已入库',
      })
      setRegisterOpen(false)
      setItems((prev) => [created, ...prev.filter((item) => item.id !== created.id)])
      setSelected(created)
      if (projectId !== registerForm.project_id) {
        navigate(`/work/achievements?projectId=${registerForm.project_id}`)
      }
    } catch (error: unknown) {
      setRegisterError(error instanceof Error ? error.message : '保存入库失败，请稍后重试')
    } finally {
      setRegisterSaving(false)
    }
  }

  function beginEditAchievement() {
    if (!selected) return
    setEditDraft({
      name: selected.name || '',
      version: selected.version || 'V0.1',
      file_link: selected.file_link || '',
      scenario: selected.scenario || '',
      reuse_tag: selected.reuse_tag || '',
    })
    setEditError('')
    setEditMode(true)
  }

  async function saveEditAchievement() {
    if (!selected) return
    if (!editDraft.name.trim()) { setEditError('请填写成果名称'); return }
    const resolvedProjectId = selected.project_id ?? projectId
    if (!resolvedProjectId) { setEditError('缺少所属项目'); return }
    setEditSaving(true)
    setEditError('')
    try {
      const updated = await updateAchievement(selected.id, {
        project_id: resolvedProjectId,
        related_task_id: selected.related_task_id ?? null,
        related_subtask_id: selected.related_subtask_id ?? null,
        name: editDraft.name.trim(),
        achievement_type: selected.achievement_type || '方案',
        owner: selected.owner || '',
        version: editDraft.version || 'V0.1',
        file_link: editDraft.file_link,
        scenario: editDraft.scenario,
        reuse_tag: editDraft.reuse_tag,
        source_type: String(selected.source_type || 'manual'),
        status: selected.status || '已入库',
      })
      setItems((prev) => prev.map((item) => (item.id === updated.id ? updated : item)))
      setSelected(updated)
      setEditMode(false)
    } catch (error: unknown) {
      setEditError(error instanceof Error ? error.message : '编辑成果信息失败')
    } finally {
      setEditSaving(false)
    }
  }

  function openAchievementLink(item: AchievementItem) {
    const action = getAchievementAddressAction(item.file_link)
    if (!action.ok) { alert(action.message); return }
    window.open(action.url, '_blank', 'noopener,noreferrer')
  }

  if (!projectId) {
    return (
      <div className="flex-1 overflow-y-auto bg-[#f7f9fc]">
        <div className="mx-auto max-w-[1500px] px-6 py-6">
          <div className="mb-5 flex items-center gap-4">
            {[
              ['项目', projects.length, 'bg-indigo-50 text-indigo-600', 'text-2xl'],
              ['已入库成果', overviewLoading ? '…' : overviewStats.total, 'bg-emerald-50 text-emerald-600', 'text-2xl'],
              ['本月新增成果', overviewLoading ? '…' : overviewStats.month, 'bg-amber-50 text-amber-600', 'text-2xl'],
              ['最近更新', overviewLoading ? '…' : overviewStats.latestProject, 'bg-sky-50 text-sky-600', 'text-sm'],
            ].map(([label, value, iconColorClass, valueSize]) => (
              <div key={label} className="flex flex-1 items-center gap-3 rounded border border-slate-200 bg-white p-4 shadow-sm">
                <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${iconColorClass}`}>
                  {label === '项目' && (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
                  )}
                  {label === '已入库成果' && (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                  )}
                  {label === '本月新增成果' && (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                  )}
                  {label === '最近更新' && (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                  )}
                </div>
                <div>
                  <p className="text-xs text-slate-500">{label}</p>
                  <p className={`mt-0.5 truncate font-black tabular-nums text-slate-950 ${valueSize}`}>{value}</p>
                </div>
              </div>
            ))}

            <div className="flex items-center gap-2">
              <div className="relative">
                <input value={projectSearch} onChange={(event) => setProjectSearch(event.target.value)} placeholder="搜索项目名称" className="w-52 rounded border border-slate-300 bg-white pl-3 pr-8 py-1.5 text-xs outline-none focus:border-sky-500" />
                <svg className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              </div>
              <button type="button" className="inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>
                筛选
              </button>
              <button type="button" onClick={openRegisterModal} className="inline-flex items-center gap-1 rounded bg-sky-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-sky-700">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                新增
              </button>
            </div>
          </div>

          <div className="achievement-project-picker-card overflow-hidden rounded border border-slate-200 bg-white shadow-sm">
            <div className="overflow-auto">
              <table className="w-full min-w-[980px] text-left text-sm">
                <thead className="border-b border-slate-200 bg-slate-50/70 text-sm font-bold text-slate-500">
                  <tr>
                    <th className="px-6 py-4">项目名称</th><th className="px-5 py-4">状态</th><th className="px-5 py-4">项目负责人</th><th className="px-5 py-4">企业教练</th><th className="px-5 py-4">成果数量</th><th className="px-5 py-4">最近更新</th><th className="px-5 py-4 text-center">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {!overviewLoading && visibleProjects.length === 0 ? (
                    <tr><td colSpan={7} className="px-5 py-12 text-center text-sm text-slate-400">暂无可查看项目</td></tr>
                  ) : pagedProjects.map((project) => {
                    const summary = projectAchievementSummary[project.id]
                    return <tr key={project.id} className="transition-colors hover:bg-blue-50/50">
                      <td className="px-6 py-3.5">
                        <p className="font-bold text-slate-950">{project.name}</p>
                        <p className="mt-0.5 text-xs text-slate-400">项目编号：{project.code || `#${project.id}`}</p>
                      </td>
                      <td className="px-4 py-3.5"><span className="rounded-md border border-blue-100 bg-blue-50 px-2.5 py-1 text-xs font-bold text-blue-700">{projectStatusLabel(project)}</span></td>
                      <td className="px-4 py-3.5 text-slate-700">{ownerText(project)}</td>
                      <td className="px-4 py-3.5 text-slate-700">{coachText(project)}</td>
                      <td className="px-4 py-3.5 font-semibold text-slate-800">{overviewLoading ? '…' : summary?.count ?? 0}</td>
                      <td className="px-4 py-3.5 text-slate-600">{overviewLoading ? '…' : formatDate(summary?.lastUpdated)}</td>
                      <td className="px-4 py-3.5 text-center">
                        <button type="button" onClick={() => navigate(`/work/achievements?projectId=${project.id}`)} className="rounded-md border border-blue-500 bg-white px-3 py-2 text-xs font-bold text-blue-600 transition hover:bg-blue-50">查看成果&nbsp;›</button>
                      </td>
                    </tr>
                  })}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t border-slate-200 px-6 py-4">
              <span className="text-sm text-slate-500">共 {visibleProjects.length} 条记录</span>
              <div className="flex items-center gap-2">
                <button type="button" disabled={overviewPage <= 1} onClick={() => setOverviewPage((page) => Math.max(1, page - 1))} className="h-9 w-9 rounded-md text-slate-400 hover:bg-slate-50 disabled:opacity-30">‹</button>
                <span className="grid h-9 min-w-9 place-items-center rounded-md border border-blue-500 px-2 text-sm font-bold text-blue-600">{overviewPage}</span>
                <button type="button" disabled={overviewPage >= overviewPageCount} onClick={() => setOverviewPage((page) => Math.min(overviewPageCount, page + 1))} className="h-9 w-9 rounded-md text-slate-400 hover:bg-slate-50 disabled:opacity-30">›</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-hidden bg-slate-50">
      <div className="mx-auto flex h-full max-w-[1600px] flex-col px-6 py-5">
        <header className="mb-5 shrink-0 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-[11px] font-extrabold uppercase tracking-[0.2em] text-sky-600">项目成果库</span>
                <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-black text-emerald-700">{projectStatusLabel(currentProject)}</span>
              </div>
              <h1 className="mt-2 truncate text-xl font-black tracking-tight text-slate-950">{currentProject?.name || '未识别项目'}</h1>
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                <span>负责人：{ownerText(currentProject)}</span>
                <span>Coach：{coachText(currentProject)}</span>
                <span>编号：{currentProject?.code || `#${projectId}`}</span>
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              <button type="button" onClick={() => navigate('/work/achievements')} className="rounded-lg border border-sky-200 bg-white px-3 py-2 text-xs font-black text-sky-700 shadow-sm hover:bg-sky-50">切换项目</button>
              <button type="button" onClick={reloadCurrentProject} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-black text-slate-600 shadow-sm hover:bg-slate-50">刷新</button>
              <button type="button" disabled className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-black text-slate-400">导出清单</button>
              <button type="button" onClick={openRegisterModal} disabled={projectArchived} className="rounded-lg bg-sky-600 px-4 py-2 text-xs font-black text-white shadow-sm hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50">登记成果</button>
            </div>
          </div>
        </header>

        <div className="mb-5 grid shrink-0 grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">成果总数</p>
              <p className="mt-0.5 text-lg font-black tabular-nums text-slate-950">{stats.total}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" /></svg>
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">本月新增</p>
              <p className="mt-0.5 text-lg font-black tabular-nums text-slate-950">{stats.month}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-50 text-purple-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" /></svg>
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">AI确认入库</p>
              <p className="mt-0.5 text-lg font-black tabular-nums text-slate-950">{stats.ai}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" /></svg>
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">手动登记</p>
              <p className="mt-0.5 text-lg font-black tabular-nums text-slate-950">{stats.manual}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-rose-50 text-rose-600">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V19.5a2.25 2.25 0 002.25 2.25h.75m0-3H12" /></svg>
            </div>
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">关联重点工作数</p>
              <p className="mt-0.5 text-lg font-black tabular-nums text-slate-950">{stats.taskCount}</p>
            </div>
          </div>
        </div>

        <div className="grid min-h-0 flex-1 gap-5 lg:grid-cols-[1fr_420px]">
          <main className="flex min-w-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-white px-4 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <select value={filterType} onChange={(event) => setFilterType(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs font-semibold text-slate-700 outline-none focus:border-sky-400">
                  <option>全部</option>
                  {ACHIEVEMENT_TYPES.map((type) => <option key={type}>{type}</option>)}
                </select>
                <select value={filterTaskId} onChange={(event) => setFilterTaskId(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs font-semibold text-slate-700 outline-none focus:border-sky-400">
                  <option value="">重点工作</option>
                  {tasks.map((task) => <option key={task.id} value={task.id}>{task.key_task}</option>)}
                </select>
                <select disabled className="rounded-lg border border-slate-200 bg-slate-100 px-2 py-1.5 text-xs font-semibold text-slate-400" title="关键任务筛选">
                  <option>关键任务</option>
                </select>
                <select value={filterSource} onChange={(event) => setFilterSource(event.target.value as (typeof SOURCE_OPTIONS)[number])} className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs font-semibold text-slate-700 outline-none focus:border-sky-400">
                  {SOURCE_OPTIONS.map((source) => <option key={source}>{source}</option>)}
                </select>
                <select value={filterDate} onChange={(event) => setFilterDate(event.target.value as (typeof DATE_OPTIONS)[number])} className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs font-semibold text-slate-700 outline-none focus:border-sky-400">
                  {DATE_OPTIONS.map((option) => <option key={option}>{option}</option>)}
                </select>
              </div>
              <div className="relative w-full sm:w-auto">
                <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索成果名称" className="w-full rounded-lg border border-slate-200 bg-white py-1.5 pl-9 pr-3 text-xs text-slate-700 outline-none focus:border-sky-400 sm:w-[220px]" />
                <svg className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>
              </div>
            </div>

            {loadError && <div className="mx-4 mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{loadError}</div>}

            <div className="min-h-0 flex-1 overflow-auto">
              <table className="w-full min-w-[1000px] text-left text-sm">
                <thead className="sticky top-0 z-10 border-b border-slate-200 bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-semibold">成果名称</th>
                    <th className="px-3 py-3 font-semibold">成果类型</th>
                    <th className="px-3 py-3 font-semibold">关联重点工作 / 关键任务</th>
                    <th className="px-3 py-3 font-semibold">来源</th>
                    <th className="px-3 py-3 font-semibold">提交/登记人</th>
                    <th className="px-3 py-3 font-semibold">确认/入库人</th>
                    <th className="px-3 py-3 text-right font-semibold">入库时间</th>
                    <th className="px-3 py-3 font-semibold">版本</th>
                    <th className="px-3 py-3 text-center font-semibold">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loading ? (
                    <tr><td colSpan={9} className="px-4 py-16 text-center text-sm text-slate-400">加载中...</td></tr>
                  ) : filteredItems.length === 0 ? (
                    <tr><td colSpan={9} className="px-4 py-16 text-center text-sm text-slate-400">暂无已入库成果</td></tr>
                  ) : filteredItems.map((item) => {
                    const active = selected?.id === item.id
                    const source = sourceLabel(item)
                    return (
                      <tr key={item.id} onClick={() => { setSelected(item); setEditMode(false) }} className={`cursor-pointer transition hover:bg-sky-50 ${active ? 'border-l-2 border-sky-500 bg-sky-50 ring-1 ring-inset ring-sky-200' : 'border-l-2 border-transparent'}`}>
                        <td className="px-4 py-3 font-semibold text-slate-900">{item.name || '未命名成果'}</td>
                        <td className="px-3 py-3"><span className={`rounded-md border px-2 py-0.5 text-xs font-bold ${typeBadgeClass(item.achievement_type)}`}>{item.achievement_type || '文档'}</span></td>
                        <td className="max-w-[260px] px-3 py-3 text-slate-600">
                          <p className="truncate">{taskName(tasks, item.related_task_id)}</p>
                          <p className="text-xs text-slate-400">关键任务：{keyTaskLabelForAchievement(item, subtaskById)}</p>
                        </td>
                        <td className="px-3 py-3"><span className={`rounded-full border px-2 py-0.5 text-xs font-black ${source === 'AI确认入库' ? 'border-purple-100 bg-purple-50 text-purple-700' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>{source}</span></td>
                        <td className="px-3 py-3 text-slate-600">{item.owner || '—'}</td>
                        <td className="px-3 py-3 text-slate-600">{item.confirmed_by || item.owner || '—'}</td>
                        <td className="px-3 py-3 text-right font-mono text-xs text-slate-500">{formatDate(item.confirmed_at || item.updated_at || item.created_at)}</td>
                        <td className="px-3 py-3 font-mono text-xs text-slate-500">{item.version || 'V0.1'}</td>
                        <td className="px-3 py-3 text-center">
                          <button type="button" onClick={(event) => { event.stopPropagation(); setSelected(item) }} className="rounded-md px-2 py-1 text-xs font-bold text-sky-700 hover:bg-sky-100">查看</button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </main>

          <aside className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            {!selected ? (
              <div className="m-4 flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-400">
                <svg className="mb-2 h-8 w-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>
                选择左侧成果查看详情
              </div>
            ) : (
              <div className="flex h-full flex-col">
                <div className="border-b border-slate-100 px-5 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[11px] font-extrabold uppercase tracking-[0.2em] text-sky-600">成果详情</p>
                      <h2 className="mt-1 text-lg font-bold leading-tight text-slate-900">{selected.name || '未命名成果'}</h2>
                    </div>
                    <span className={`shrink-0 rounded-md border px-2 py-0.5 text-xs font-bold ${typeBadgeClass(selected.achievement_type)}`}>{selected.achievement_type || '文档'}</span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-semibold text-slate-600">{selected.version || 'V0.1'}</span>
                    {selected.reuse_tag && <span className="rounded-md border border-sky-100 bg-sky-50 px-2 py-0.5 text-xs font-semibold text-sky-700">{selected.reuse_tag}</span>}
                    <span className={`rounded-full border px-2 py-0.5 text-[11px] font-black ${sourceLabel(selected) === 'AI确认入库' ? 'border-purple-100 bg-purple-50 text-purple-700' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>{sourceLabel(selected)}</span>
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto px-5 py-4">
                  {editMode ? (
                    <div className="space-y-3">
                      {editError && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{editError}</div>}
                      <div className="grid grid-cols-2 gap-3">
                        <input value={editDraft.name} onChange={(event) => setEditDraft((prev) => ({ ...prev, name: event.target.value }))} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400" placeholder="成果名称" />
                        <input value={editDraft.version} onChange={(event) => setEditDraft((prev) => ({ ...prev, version: event.target.value }))} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400" placeholder="版本" />
                      </div>
                      <input value={editDraft.reuse_tag} onChange={(event) => setEditDraft((prev) => ({ ...prev, reuse_tag: event.target.value }))} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400" placeholder="标签" />
                      <textarea value={editDraft.scenario} onChange={(event) => setEditDraft((prev) => ({ ...prev, scenario: event.target.value }))} rows={5} className="w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400" placeholder="成果描述" />
                      <input value={editDraft.file_link} onChange={(event) => setEditDraft((prev) => ({ ...prev, file_link: event.target.value }))} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400" placeholder="文件链接/存储地址" />
                      <div className="flex gap-2">
                        <button type="button" onClick={saveEditAchievement} disabled={editSaving} className="flex-1 rounded-lg bg-sky-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-50">保存</button>
                        <button type="button" onClick={() => setEditMode(false)} className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50">取消</button>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-5">
                      <section>
                        <h3 className="mb-2 text-xs font-black uppercase tracking-wide text-slate-400">摘要与追溯</h3>
                        <div className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl border border-slate-100 bg-slate-50/60 p-3 text-sm">
                          <Info label="所属项目" value={currentProject?.name || selected.special_project || '—'} />
                          <Info label="来源" value={sourceLabel(selected)} />
                          <Info label="关联重点工作" value={selectedTaskName} span />
                          <Info label="关联关键任务" value={keyTaskLabelForAchievement(selected, subtaskById)} span />
                          <Info label="提交人" value={selected.owner || '—'} />
                          <Info label="确认/入库人" value={selected.confirmed_by || selected.owner || '—'} />
                          <div className="col-span-2">
                            {selected.source_submission_id ? (
                              <button type="button" className="text-xs font-bold text-sky-700 hover:underline">查看原始提交 #{selected.source_submission_id}</button>
                            ) : (
                              <span className="text-xs text-slate-400">查看原始提交：手动登记无原始提交</span>
                            )}
                          </div>
                        </div>
                      </section>

                      <section>
                        <h3 className="mb-2 text-xs font-black uppercase tracking-wide text-slate-400">成果描述</h3>
                        <p className="rounded-xl border border-slate-100 bg-slate-50/60 p-3 text-sm leading-relaxed text-slate-700 whitespace-pre-wrap">{selected.scenario || '暂无成果说明'}</p>
                      </section>

                      <section>
                        <h3 className="mb-2 text-xs font-black uppercase tracking-wide text-slate-400">附件与链接</h3>
                        {selected.file_link ? (
                          <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-3">
                            <p className="break-all text-xs text-slate-600">{selected.file_link}</p>
                            <button type="button" onClick={() => openAchievementLink(selected)} className="mt-2 rounded-lg border border-sky-200 bg-white px-3 py-1.5 text-xs font-bold text-sky-700 hover:bg-sky-50">打开成果</button>
                          </div>
                        ) : <p className="text-sm text-slate-400">暂无附件与链接</p>}
                      </section>
                    </div>
                  )}
                </div>

                {!editMode && (
                  <div className="border-t border-slate-100 px-5 py-3">
                    <button type="button" onClick={beginEditAchievement} disabled={projectArchived} className="w-full rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50">编辑成果信息</button>
                  </div>
                )}
              </div>
            )}
          </aside>
        </div>
      </div>

      {registerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/45">
          <div className="max-h-[90vh] w-full max-w-4xl overflow-hidden rounded-xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div>
                <h2 className="text-lg font-bold text-slate-900">成果登记</h2>
                <p className="mt-0.5 text-xs text-slate-500">登记本项目已形成的成果，并关联到重点工作与关键任务。</p>
              </div>
              <button type="button" onClick={() => setRegisterOpen(false)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100">×</button>
            </div>
            <div className="max-h-[68vh] overflow-y-auto px-6 py-4">
              {registerError && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{registerError}</div>}
              <div className="space-y-4">
                <section className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
                  <h3 className="text-xs font-black uppercase tracking-wide text-slate-500">上下文关联</h3>
                  <div className="mt-2 grid grid-cols-3 gap-3">
                    <FormSelect label="所属项目 *" value={registerForm.project_id ?? ''} onChange={(value) => setRegisterForm((prev) => ({ ...prev, project_id: value ? Number(value) : null, related_task_id: null, related_subtask_id: null }))}>
                      <option value="">请选择项目</option>
                      {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                    </FormSelect>
                    <FormSelect label="关联重点工作 *" value={registerForm.related_task_id ?? ''} onChange={(value) => setRegisterForm((prev) => ({ ...prev, related_task_id: value ? Number(value) : null, related_subtask_id: null }))} disabled={!registerForm.project_id || tasksLoading}>
                      <option value="">{!registerForm.project_id ? '请先选择项目' : tasksLoading ? '加载中...' : '请选择重点工作'}</option>
                      {tasks.map((task) => <option key={task.id} value={task.id}>{task.key_task}</option>)}
                    </FormSelect>
                    <FormSelect label="关联关键任务" value={registerForm.related_subtask_id ?? ''} onChange={(value) => setRegisterForm((prev) => ({ ...prev, related_subtask_id: value ? Number(value) : null }))} disabled={!registerForm.related_task_id || subtasksLoading}>
                      <option value="">{!registerForm.related_task_id ? '请先选择重点工作' : subtasksLoading ? '加载中...' : subtasks.length === 0 ? '暂无关键任务' : '未指定关键任务'}</option>
                      {subtasks.map((st) => <option key={st.id} value={st.id}>{st.title}</option>)}
                    </FormSelect>
                  </div>
                </section>
                <section className="rounded-lg border border-slate-200 bg-white p-4">
                  <h3 className="text-xs font-black uppercase tracking-wide text-slate-500">成果定义</h3>
                  <div className="mt-2 grid grid-cols-12 gap-3">
                    <div className="col-span-8">
                      <FormInput label="成果名称 *" value={registerForm.name} onChange={(value) => setRegisterForm((prev) => ({ ...prev, name: value }))} placeholder="例如：S1资料清单初稿" />
                    </div>
                    <div className="col-span-2">
                      <FormSelect label="成果类型 *" value={registerForm.achievement_type} onChange={(value) => setRegisterForm((prev) => ({ ...prev, achievement_type: value }))}>
                        {ACHIEVEMENT_TYPES.map((type) => <option key={type}>{type}</option>)}
                      </FormSelect>
                    </div>
                    <div className="col-span-2">
                      <FormInput label="版本" value={registerForm.version} onChange={(value) => setRegisterForm((prev) => ({ ...prev, version: value }))} placeholder="V0.1" />
                    </div>
                    <div className="col-span-6">
                      <FormInput label="标签" value={registerForm.reuse_tag} onChange={(value) => setRegisterForm((prev) => ({ ...prev, reuse_tag: value }))} placeholder="例如：内部复用、交付材料" />
                    </div>
                    <div className="col-span-6">
                      <FormInput label="文件链接/存储地址" value={registerForm.file_link} onChange={(value) => setRegisterForm((prev) => ({ ...prev, file_link: value }))} placeholder="知识库、网盘或文档链接" />
                    </div>
                    <div className="col-span-6">
                      <FormTextarea label="适用场景" value={registerForm.scenario} onChange={(value) => setRegisterForm((prev) => ({ ...prev, scenario: value }))} placeholder="说明该成果适用于哪些场景" />
                    </div>
                    <div className="col-span-6">
                      <FormTextarea label="成果说明" value={registerForm.description} onChange={(value) => setRegisterForm((prev) => ({ ...prev, description: value }))} placeholder="补充成果内容、使用方式或注意事项" />
                    </div>
                  </div>
                </section>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 border-t border-slate-200 px-6 py-3">
              <button type="button" onClick={() => setRegisterOpen(false)} disabled={registerSaving} className="rounded border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-50">取消</button>
              <button type="button" onClick={handleSaveAchievement} disabled={registerSaving || projectArchived} className="rounded bg-sky-600 px-4 py-2 text-sm font-bold text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50">{registerSaving ? '保存中...' : '保存入库'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Info({ label, value, span = false }: { label: string; value: string; span?: boolean }) {
  return (
    <div className={span ? 'col-span-2' : ''}>
      <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-0.5 text-sm font-medium text-slate-800">{value}</p>
    </div>
  )
}

function DetailSection({ title, children }: { title: string; children: string }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <h3 className="mb-2 border-b border-slate-100 pb-1.5 text-xs font-bold text-slate-500">{title}</h3>
      <p className="whitespace-pre-wrap text-sm leading-6 text-slate-600">{children}</p>
    </section>
  )
}

function FormInput({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <label className="space-y-1.5">
      <span className="text-xs font-bold text-slate-600">{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400" />
    </label>
  )
}

function FormTextarea({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <label className="space-y-1.5">
      <span className="text-xs font-bold text-slate-600">{label}</span>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} rows={3} className="w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400" />
    </label>
  )
}

function FormSelect({ label, value, onChange, disabled, children }: { label: string; value: string | number; onChange: (value: string) => void; disabled?: boolean; children: ReactNode }) {
  return (
    <label className="space-y-1.5">
      <span className="text-xs font-bold text-slate-600">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled} className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-sky-400 disabled:bg-slate-50 disabled:text-slate-400">
        {children}
      </select>
    </label>
  )
}
