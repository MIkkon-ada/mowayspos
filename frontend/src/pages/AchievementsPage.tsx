import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { createAchievement, fetchAchievements, updateAchievement } from '../api/achievements'
import { fetchTasks } from '../api/tasks'
import { fetchSubTasks } from '../api/subtasks'
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
  const count = project.member_counts?.project_ceo ?? 0
  return count > 0 ? `${count} 位企业教练` : '未配置'
}

function taskName(tasks: TaskItem[], taskId?: number | null): string {
  if (!taskId) return '未关联重点工作'
  return tasks.find((task) => task.id === taskId)?.key_task || `重点工作 #${taskId}`
}

function keyTaskLabelForAchievement(item: AchievementItem): string {
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
  const [filterType, setFilterType] = useState('全部')
  const [filterTaskId, setFilterTaskId] = useState('')
  const [filterSource, setFilterSource] = useState<(typeof SOURCE_OPTIONS)[number]>('全部')
  const [filterDate, setFilterDate] = useState<(typeof DATE_OPTIONS)[number]>('全部')
  const [keyword, setKeyword] = useState('')
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [tasksLoading, setTasksLoading] = useState(false)
  const [subtasks, setSubtasks] = useState<SubTaskItem[]>([])
  const [subtasksLoading, setSubtasksLoading] = useState(false)
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
      <div className="flex-1 overflow-y-auto bg-[#f6f8fb]">
        <div className="mx-auto max-w-[1440px] px-6 py-6">
          <div className="mb-6 flex items-start justify-between gap-5">
            <div>
              <p className="text-[11px] font-extrabold uppercase tracking-[0.24em] text-sky-600">PROJECT ACHIEVEMENT LIBRARY</p>
              <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950">项目成果库</h1>
              <p className="mt-2 text-sm text-slate-500">请先选择一个项目，进入后查看该项目已入库成果，也可以手动登记成果。</p>
            </div>
            <div className="w-80 rounded border border-slate-200 bg-white px-4 py-2.5 shadow-sm">
              <label className="text-[11px] font-bold uppercase tracking-wide text-slate-400">搜索项目名称</label>
              <input
                value={projectSearch}
                onChange={(event) => setProjectSearch(event.target.value)}
                placeholder="搜索项目名称"
                className="mt-1.5 w-full border-0 p-0 text-sm font-medium text-slate-800 outline-none placeholder:text-slate-300"
              />
            </div>
          </div>

          <div className="achievement-stat-bar mb-6 grid grid-cols-4 gap-4">
            {[
              ['可查看项目数', projects.length],
              ['已入库成果总数', '—'],
              ['本月新增成果', '—'],
              ['最近更新项目', '—'],
            ].map(([label, value]) => (
              <div key={label} className="rounded border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-[11px] font-bold uppercase tracking-wide text-slate-400">{label}</p>
                <p className="mt-2 text-2xl font-black tabular-nums text-slate-950">{value}</p>
              </div>
            ))}
          </div>

          <div className="achievement-project-picker-card overflow-hidden rounded border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-5 py-3">
              <div>
                <h2 className="text-base font-bold text-slate-900">选择项目成果库</h2>
                <p className="mt-0.5 text-xs text-slate-500">请先选择一个项目，进入后查看或登记该项目成果。</p>
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
                    <th className="px-4 py-2.5">成果数量</th>
                    <th className="px-4 py-2.5">最后更新</th>
                    <th className="px-4 py-2.5 text-center">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {visibleProjects.length === 0 ? (
                    <tr><td colSpan={7} className="px-5 py-12 text-center text-sm text-slate-400">暂无可查看项目</td></tr>
                  ) : visibleProjects.map((project) => (
                    <tr key={project.id} className="transition-colors hover:bg-sky-50/70">
                      <td className="px-5 py-2.5">
                        <p className="font-bold text-slate-950">{project.name}</p>
                        <p className="mt-0.5 text-xs text-slate-400">项目编号：{project.code || `#${project.id}`}</p>
                      </td>
                      <td className="px-4 py-2.5"><span className="rounded border border-sky-100 bg-sky-50 px-2 py-0.5 text-xs font-bold text-sky-700">{projectStatusLabel(project)}</span></td>
                      <td className="px-4 py-2.5 text-sm text-slate-600">{ownerText(project)}</td>
                      <td className="px-4 py-2.5 text-sm text-slate-600">{coachText(project)}</td>
                      <td className="px-4 py-2.5 text-sm text-slate-400">—</td>
                      <td className="px-4 py-2.5 text-sm text-slate-400">—</td>
                      <td className="px-4 py-2.5 text-center">
                        <button
                          type="button"
                          onClick={() => navigate(`/work/achievements?projectId=${project.id}`)}
                          className="rounded bg-sky-600 px-3 py-1.5 text-xs font-bold text-white transition hover:bg-sky-700"
                        >
                          进入成果库
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

  return (
    <div className="flex-1 overflow-hidden bg-[#f6f8fb]">
      <div className="mx-auto flex h-full max-w-[1440px] flex-col px-5 py-5">
        <header className="rounded-xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-extrabold uppercase tracking-[0.24em] text-sky-600">PROJECT ACHIEVEMENT LIBRARY</p>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="mt-1 text-3xl font-black tracking-tight text-slate-950">{currentProject?.name || '未识别项目'} 项目成果库</h1>
                <span className="mt-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-black text-emerald-700">{projectStatusLabel(currentProject)}</span>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-slate-500">
                <span>项目负责人：{ownerText(currentProject)}</span>
                <span>Coach / 企业教练：{coachText(currentProject)}</span>
                <span>项目编号：{currentProject?.code || `#${projectId}`}</span>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button type="button" onClick={() => navigate('/work/achievements')} className="rounded-xl border border-sky-200 bg-white px-3 py-2 text-xs font-black text-sky-700 hover:bg-sky-50">切换项目</button>
              <button type="button" onClick={reloadCurrentProject} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-black text-slate-600 hover:bg-slate-50">刷新</button>
              <button type="button" disabled className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-black text-slate-400">导出清单</button>
              <button type="button" onClick={openRegisterModal} disabled={projectArchived} className="rounded-xl bg-sky-600 px-4 py-2 text-xs font-black text-white shadow-sm hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50">登记成果</button>
            </div>
          </div>

          <div className="achievement-stat-bar mt-4 grid grid-cols-5 overflow-hidden rounded-lg border border-slate-200 bg-white">
            {[
              ['成果总数', stats.total],
              ['本月新增', stats.month],
              ['AI确认入库', stats.ai],
              ['手动登记', stats.manual],
              ['关联重点工作数', stats.taskCount],
            ].map(([label, value]) => (
              <div key={label} className="border-r border-slate-200 px-4 py-3 last:border-r-0">
                <p className="text-[11px] font-black uppercase tracking-wide text-slate-400">{label}</p>
                <p className="mt-1 text-2xl font-black tabular-nums text-slate-950">{value}</p>
              </div>
            ))}
          </div>
        </header>

        <div className="achievement-workbench-grid grid min-h-0 flex-1 gap-4 pt-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(380px,1fr)]">
          <main className="flex min-w-0 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="achievement-filter-bar flex flex-wrap items-center gap-2 border-b border-slate-200 bg-slate-50/90 px-4 py-2">
              <select value={filterType} onChange={(event) => setFilterType(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700">
                <option>全部</option>
                {ACHIEVEMENT_TYPES.map((type) => <option key={type}>{type}</option>)}
              </select>
              <select value={filterTaskId} onChange={(event) => setFilterTaskId(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700">
                <option value="">重点工作</option>
                {tasks.map((task) => <option key={task.id} value={task.id}>{task.key_task}</option>)}
              </select>
              <select disabled className="rounded-lg border border-slate-200 bg-slate-100 px-2 py-1.5 text-xs text-slate-400" title="关键任务筛选">
                <option>关键任务</option>
              </select>
              <select value={filterSource} onChange={(event) => setFilterSource(event.target.value as (typeof SOURCE_OPTIONS)[number])} className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700">
                {SOURCE_OPTIONS.map((source) => <option key={source}>{source}</option>)}
              </select>
              <select value={filterDate} onChange={(event) => setFilterDate(event.target.value as (typeof DATE_OPTIONS)[number])} className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs text-slate-700">
                {DATE_OPTIONS.map((option) => <option key={option}>{option}</option>)}
              </select>
              <input value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索成果名称" className="min-w-[220px] flex-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 outline-none focus:border-sky-400" />
            </div>

            {loadError && <div className="mx-4 mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{loadError}</div>}

            <div className="min-h-0 flex-1 overflow-auto">
              <table className="w-full min-w-[1120px] text-left text-sm">
                <thead className="sticky top-0 bg-slate-100/90 text-xs font-bold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-2">成果名称</th>
                    <th className="px-3 py-2">成果类型</th>
                    <th className="px-3 py-2">关联重点工作 / 关键任务</th>
                    <th className="px-3 py-2">来源</th>
                    <th className="px-3 py-2">提交/登记人</th>
                    <th className="px-3 py-2">确认/入库人</th>
                    <th className="px-3 py-2 text-right">入库时间</th>
                    <th className="px-3 py-2">版本</th>
                    <th className="px-3 py-2 text-center">操作</th>
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
                        <td className="px-4 py-2 font-semibold text-slate-900">{item.name || '未命名成果'}</td>
                        <td className="px-3 py-2"><span className={`rounded-md border px-2 py-0.5 text-xs font-bold ${typeBadgeClass(item.achievement_type)}`}>{item.achievement_type || '文档'}</span></td>
                        <td className="max-w-[240px] px-3 py-2 text-slate-600">
                          <p className="truncate">{taskName(tasks, item.related_task_id)}</p>
                          <p className="text-xs text-slate-400">关键任务：{keyTaskLabelForAchievement(item)}</p>
                        </td>
                        <td className="px-3 py-2"><span className={`rounded-full border px-2 py-0.5 text-xs font-black ${source === 'AI确认入库' ? 'border-purple-100 bg-purple-50 text-purple-700' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>{source}</span></td>
                        <td className="px-3 py-2 text-slate-600">{item.owner || '—'}</td>
                        <td className="px-3 py-2 text-slate-600">{item.confirmed_by || item.owner || '—'}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs text-slate-500">{formatDate(item.confirmed_at || item.updated_at || item.created_at)}</td>
                        <td className="px-3 py-2 font-mono text-xs text-slate-500">{item.version || 'V0.1'}</td>
                        <td className="px-3 py-2 text-center">
                          <button type="button" onClick={(event) => { event.stopPropagation(); setSelected(item) }} className="rounded-md px-2 py-1 text-xs font-bold text-sky-700 hover:bg-sky-100">查看</button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </main>

          <aside className="achievement-detail-panel min-h-0 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            {!selected ? (
              <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-400">选择左侧成果查看详情</div>
            ) : (
              <div className="space-y-3">
                <section className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
                  <p className="text-xs font-black uppercase tracking-wider text-sky-600">详情查看</p>
                  <p className="mt-1 text-[11px] font-bold uppercase tracking-wide text-slate-400">当前选中</p>
                  {editMode ? (
                    <div className="mt-3 space-y-3">
                      {editError && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{editError}</div>}
                      <input value={editDraft.name} onChange={(event) => setEditDraft((prev) => ({ ...prev, name: event.target.value }))} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400" />
                      <input value={editDraft.version} onChange={(event) => setEditDraft((prev) => ({ ...prev, version: event.target.value }))} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400" />
                      <input value={editDraft.reuse_tag} onChange={(event) => setEditDraft((prev) => ({ ...prev, reuse_tag: event.target.value }))} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400" placeholder="标签" />
                      <textarea value={editDraft.scenario} onChange={(event) => setEditDraft((prev) => ({ ...prev, scenario: event.target.value }))} rows={4} className="w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400" />
                      <input value={editDraft.file_link} onChange={(event) => setEditDraft((prev) => ({ ...prev, file_link: event.target.value }))} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400" placeholder="文件链接/存储地址" />
                      <div className="flex gap-2">
                        <button type="button" onClick={saveEditAchievement} disabled={editSaving} className="flex-1 rounded-lg bg-sky-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-50">保存</button>
                        <button type="button" onClick={() => setEditMode(false)} className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600">取消</button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <h2 className="mt-2 text-lg font-bold text-slate-900">{selected.name || '未命名成果'}</h2>
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        <span className={`rounded-md border px-2 py-0.5 text-xs font-bold ${typeBadgeClass(selected.achievement_type)}`}>{selected.achievement_type || '文档'}</span>
                        <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600">{selected.version || 'V0.1'}</span>
                        {selected.reuse_tag && <span className="rounded-md border border-sky-100 bg-sky-50 px-2 py-0.5 text-xs text-sky-700">{selected.reuse_tag}</span>}
                      </div>
                    </>
                  )}
                </section>

                <section className="rounded-lg border border-slate-200 bg-white p-3">
                  <h3 className="mb-2 border-b border-slate-100 pb-1.5 text-xs font-black text-slate-600">摘要与追溯</h3>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <Info label="所属项目" value={currentProject?.name || selected.special_project || '—'} />
                    <Info label="来源" value={sourceLabel(selected)} />
                    <Info label="关联重点工作" value={selectedTaskName} span />
                    <Info label="关联关键任务" value={keyTaskLabelForAchievement(selected)} span />
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

                <DetailSection title="成果描述">{selected.scenario || '暂无成果说明'}</DetailSection>
                <section className="rounded-lg border border-slate-200 bg-white p-3">
                  <h3 className="mb-2 border-b border-slate-100 pb-1.5 text-xs font-black text-slate-600">附件与链接</h3>
                  {selected.file_link ? (
                    <div className="space-y-2">
                      <p className="break-all rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">{selected.file_link}</p>
                      <button type="button" onClick={() => openAchievementLink(selected)} className="rounded-lg border border-sky-200 px-3 py-2 text-xs font-bold text-sky-700 hover:bg-sky-50">打开成果</button>
                    </div>
                  ) : <p className="text-sm text-slate-400">暂无附件与链接</p>}
                </section>
                <DetailSection title="使用场景与备注">{selected.reuse_tag || selected.scenario || '暂无备注'}</DetailSection>
                {!editMode && (
                  <button type="button" onClick={beginEditAchievement} disabled={projectArchived} className="w-full rounded-xl bg-slate-900 px-4 py-3 text-sm font-bold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50">编辑成果信息</button>
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
                    <FormSelect label="关联关键任务" value={registerForm.related_subtask_id ?? ''} onChange={(value) => setRegisterForm((prev) => ({ ...prev, related_subtask_id: value ? Number(value) : null }))} disabled>
                      <option value="">未指定关键任务</option>
                    </FormSelect>
                    <p className="mt-1 text-[11px] text-slate-400">当前成果可先关联到重点工作，关键任务精确绑定将在后续版本支持。</p>
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
