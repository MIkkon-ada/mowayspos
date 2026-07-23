import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { exportTasksToExcel } from '../utils/exportTasksExcel'
import { exportPlanTableToExcel } from '../utils/exportPlanTableExcel'
import { createTask, deleteTask, fetchTaskLogs, fetchTaskUpdates, fetchTasks, updateTask, extractTasksFromOutline, batchCreateTasks, restoreTask } from '../api/tasks'
import type { TaskLog, TaskPayload, TaskUpdate, TaskDraft } from '../api/tasks'
import { fetchSubTasks, fetchSubTasksBatch, createSubTask, patchSubTaskStatus, isPendingConfirmation, updateSubTask, deleteSubTask, restoreSubTask, fetchSubtaskDetail } from '../api/subtasks'
import type { SubTaskDetail, SubTaskPayload } from '../api/subtasks'
import { createUpdate } from '../api/updates'
import { ApiError, apiGet } from '../api/client'
import { getProject, getProjectMembers } from '../api/projects'
import { useProject } from '../context/ProjectContext'
import { canEditSubTaskStatus, canManageProjectTrash, canManageProjectWork } from '../domain/taskPermission'
import type { TaskItem, SubTaskItem, Project, ProjectMember } from '../types'
import { getProjectById, getProjectDisplayName, getProjectIdFromRecord } from '../domain/projectDisplay'
import { isProjectActive, isProjectArchived } from '../domain/projectLifecycleStatus'
import { PlanTableViewV2 } from '../components/task-management/PlanTableViewV2'
import { toast } from '../utils/toast'

const NOT_STARTED = new Set(['未开始', 'not_started', 'notstarted'])
const IN_PROGRESS  = new Set(['推进中', '进行中', 'in_progress'])
const COMPLETED    = new Set(['已完成', '完成', 'completed'])
const DELAYED      = new Set(['延期', '已延期', 'delayed'])
const PAUSED       = new Set(['暂停', '暂缓', '已暂停', 'paused'])

function norm(s?: string | null) { return String(s ?? '').trim().toLowerCase().replace(/\s+/g, '_') }
function shortDate(s?: string | null) {
  if (!s) return '-'
  if (s.includes('T')) return s.replace('T', ' ').slice(0, 16)
  return s.replace(/(\d{4})年(\d{1,2})月/g, '$1/$2')
}
function count(tasks: TaskItem[], set: Set<string>) { return tasks.filter((t) => set.has(norm(t.status))).length }
// 判断是否为「延期/过期」任务（与 Dashboard 后端逻辑一致：状态为延期 OR 计划时间已过期且未完成）
function isOverdueTask(t: TaskItem) {
  return DELAYED.has(norm(t.status)) || (
    !COMPLETED.has(norm(t.status)) && !PAUSED.has(norm(t.status)) && isPlanOverdue(t.plan_time ?? '')
  )
}

const STATUS_BADGE: Record<string, { cls: string; dot: string; label: string }> = {
  '进行中': { cls: 'bg-blue-100 text-blue-700',    dot: '#3B82F6', label: '进行中' },
  '推进中': { cls: 'bg-blue-100 text-blue-700',    dot: '#3B82F6', label: '进行中' },
  '已完成': { cls: 'bg-emerald-100 text-emerald-700', dot: '#10B981', label: '已完成' },
  '延期':   { cls: 'bg-red-100 text-red-700',      dot: '#EF4444', label: '延期' },
  '暂停':   { cls: 'bg-amber-100 text-amber-700',  dot: '#F59E0B', label: '暂缓' },
  '暂缓':   { cls: 'bg-amber-100 text-amber-700',  dot: '#F59E0B', label: '暂缓' },
  '未开始': { cls: 'bg-slate-100 text-slate-600',  dot: '#94A3B8', label: '未启动' },
}

function getBadge(status?: string) {
  return STATUS_BADGE[status ?? ''] ?? { cls: 'bg-slate-100 text-slate-600', dot: '#94A3B8', label: status ?? '-' }
}

const PROJECT_COLORS = ['#2563EB', '#059669', '#F59E0B', '#8B5CF6', '#0891B2', '#6366F1', '#EC4899']
function projectColor(names: string[], name?: string) {
  const idx = names.indexOf(name ?? '') % PROJECT_COLORS.length
  return PROJECT_COLORS[Math.max(0, idx)]
}
function projectForTask(projects: Project[], task?: TaskItem | null) {
  if (!task) return null
  const projectId = getProjectIdFromRecord(task)
  if (projectId != null) {
    return getProjectById(projects, projectId)
  }
  return null
}
function projectForSubTask(projects: Project[], tasks: TaskItem[], sub?: SubTaskDetail | SubTaskItem | null) {
  if (!sub) return null
  const parent = tasks.find((task) => task.id === sub.task_id)
  if (parent) return projectForTask(projects, parent)
  const parentProjectId = (sub as any).parent_task?.project_id
  if (typeof parentProjectId === 'number') {
    return getProjectById(projects, parentProjectId)
  }
  return null
}
function projectPeopleText(value?: string[] | string | null) {
  if (Array.isArray(value)) return value.filter(Boolean).join('、') || '—'
  return value?.trim() || '—'
}
function subTaskProgress(subs?: SubTaskItem[] | null) {
  if (!subs?.length) return { done: 0, total: 0, label: '0/0' }
  const done = subs.filter((s) => COMPLETED.has(norm(s.status))).length
  return { done, total: subs.length, label: `${done}/${subs.length}` }
}

function taskProjectKey(projects: Project[], task: TaskItem) {
  const project = projectForTask(projects, task)
  if (project) return `project:${project.id}`
  return `legacy:${getProjectDisplayName(projects, task) || '（未分类）'}`
}

function groupProjectName(projects: Project[], key: string, tasks: TaskItem[]) {
  const projectId = key.startsWith('project:') ? Number(key.slice('project:'.length)) : null
  if (projectId != null && Number.isFinite(projectId)) {
    const matched = projects.find((p) => p.id === projectId)
    if (matched) return matched.name
  }
  const firstTask = tasks[0]
  return getProjectDisplayName(projects, firstTask) || '（未分类）'
}

function initials(name?: string) { return (name ?? '?').slice(0, 1) }

function parseProgressTimeline(notes?: string | null): { date: string; text: string }[] {
  if (!notes?.trim()) return []
  const lines = notes.split('\n').filter(Boolean)
  const entries: { date: string; text: string[] }[] = []
  for (const line of lines) {
    const m = line.match(/^\[(\d{4}-\d{2}-\d{2})\]\s*(.*)/)
    if (m) {
      entries.push({ date: m[1], text: [m[2].trim()] })
    } else if (entries.length > 0) {
      entries[entries.length - 1].text.push(line.trim())
    } else {
      entries.push({ date: '', text: [line.trim()] })
    }
  }
  return entries.map((e) => ({ date: e.date, text: e.text.filter(Boolean).join(' ') }))
}

const AVATAR_COLORS = ['#2563EB', '#059669', '#8B5CF6', '#0891B2', '#D97706', '#F59E0B', '#EC4899', '#6366F1']

const TASK_PROJECT_CONTEXT_REQUIRED_MESSAGE = '请先选择项目后查看工作推进表'
const TASK_PROJECT_CONTEXT_EMPTY_MESSAGE = '当前没有可查看的项目工作推进表'
const TASK_PROJECT_CONTEXT_MISSING_ENTRY_MESSAGE = '当前入口缺少项目上下文，请从项目进入工作推进表，或先选择项目。'
const TASK_PROJECT_PERMISSION_DENIED_MESSAGE = '你没有权限查看该项目工作推进表。'
function avatarColor(name: string) {
  let h = 0
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) & 0xffff
  return AVATAR_COLORS[h % AVATAR_COLORS.length]
}

function Avatar({ name, size = 24 }: { name: string; size?: number }) {
  return (
    <span
      style={{
        width: size, height: size, borderRadius: '50%', border: '2px solid #fff',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        fontSize: size * 0.42, fontWeight: 700, color: '#fff', flexShrink: 0,
        background: avatarColor(name), marginLeft: -6,
      }}
    >
      {initials(name)}
    </span>
  )
}

function AvatarSingle({ name }: { name: string }) {
  return (
    <div className="flex items-center gap-1">
      <span style={{ marginLeft: 0 }}><Avatar name={name} /></span>
      <span className="text-slate-600 ml-1">{name}</span>
    </div>
  )
}

function CollabAvatars({ raw }: { raw?: string }) {
  const names = (raw ?? '').split(/[,，、]/).map((s) => s.trim()).filter(Boolean)
  if (!names.length) return <span className="text-slate-300">—</span>
  const show = names.slice(0, 3)
  const extra = names.length - show.length
  return (
    <div className="flex items-center">
      {show.map((n) => <Avatar key={n} name={n} />)}
      {extra > 0 && (
        <span style={{ width: 24, height: 24, borderRadius: '50%', border: '2px solid #fff', background: '#D97706', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, fontWeight: 700, color: '#fff', flexShrink: 0, marginLeft: -6 }}>
          +{extra}
        </span>
      )}
    </div>
  )
}

function ResultBadge({ text }: { text?: string }) {
  if (!text) return <span className="text-slate-300">—</span>
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold"
      style={{ background: '#EFF6FF', color: '#1D4ED8' }}
    >
      {text.slice(0, 14)}{text.length > 14 ? '…' : ''}
    </span>
  )
}

function OwnerCell({ name }: { name?: string }) {
  if (!name) return <span className="text-slate-300">—</span>
  const names = name.split(/[,，、]/).map((s) => s.trim()).filter(Boolean)
  if (names.length === 1) {
    return (
      <div className="flex items-center gap-1.5">
        <Avatar name={names[0]} size={22} />
        <span className="text-slate-600 text-xs">{names[0]}</span>
      </div>
    )
  }
  return (
    <div className="flex items-center gap-1">
      <div className="flex" style={{ marginLeft: 6 }}>
        {names.slice(0, 3).map((n) => <Avatar key={n} name={n} size={22} />)}
        {names.length > 3 && (
          <span style={{ width: 22, height: 22, borderRadius: '50%', border: '2px solid #fff', background: '#94A3B8', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, fontWeight: 700, color: '#fff', marginLeft: -6 }}>
            +{names.length - 3}
          </span>
        )}
      </div>
      <span className="text-slate-500 text-xs ml-1">{names.slice(0, 2).join('、')}{names.length > 2 ? '…' : ''}</span>
    </div>
  )
}

export function TaskManagementPage() {
  const { currentProjectId, projects, currentUser, currentProjectRoles } = useProject()
  const [tasks, setTasks]             = useState<TaskItem[]>([])
  const [loading, setLoading]         = useState(false)
  const [selectedTask, setSelectedTask] = useState<TaskItem | null>(null)
  const [formOpen, setFormOpen]       = useState(false)
  const [formTask, setFormTask]       = useState<TaskItem | null>(null)  // null = 新增
  const [taskLogs, setTaskLogs]       = useState<TaskLog[]>([])
  const [taskUpdates, setTaskUpdates] = useState<TaskUpdate[]>([])
  const [subTasks, setSubTasks]       = useState<SubTaskItem[]>([])
  const [trashedSubTasks, setTrashedSubTasks] = useState<SubTaskItem[]>([])
  const [subTaskFormOpen, setSubTaskFormOpen] = useState(false)
  const [editingSubTask, setEditingSubTask] = useState<SubTaskItem | SubTaskDetail | null>(null)
  const [projectMembersByProject, setProjectMembersByProject] = useState<Record<number, ProjectMember[]>>({})
  // inline sub-task expand in table
  const [taskSubMap, setTaskSubMap]     = useState<Record<number, SubTaskItem[]>>({})
  const [expandedTasks, setExpandedTasks] = useState<Set<number>>(new Set())
  // 关键任务详情面板
  const [selectedSubTask, setSelectedSubTask] = useState<SubTaskDetail | null>(null)
  const [subDetailLoading, setSubDetailLoading] = useState(false)
  const [sourceCollapsed, setSourceCollapsed] = useState(true)
  const [subEditField, setSubEditField] = useState<string | null>(null)
  const [subEditVal, setSubEditVal] = useState('')
  const [subSaving, setSubSaving] = useState(false)
  const [subEditMode, setSubEditMode] = useState(false)
  const [subEditDraft, setSubEditDraft] = useState<Record<string, string>>({})
  const [importOpen, setImportOpen] = useState(false)
  const [searchParams] = useSearchParams()
  const [search, setSearch]           = useState('')
  const [filterStatus, setFilterStatus] = useState(() => searchParams.get('status') ?? '')
  const [filterOwner, setFilterOwner] = useState('')
  const [showDeleted, setShowDeleted] = useState(false)
  // viewProjectId：null=全部任务，非null=特定项目
  const [viewProjectId, setViewProjectId] = useState<number | null>(null)
  const [autoSelectedTaskProjectId, setAutoSelectedTaskProjectId] = useState<number | null>(null)
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())
  const [viewMode, setViewMode] = useState<'execution' | 'plan'>('plan')
  const [planTableLoading, setPlanTableLoading] = useState(false)
  const [progressOpen, setProgressOpen] = useState(false)
  const [progressText, setProgressText] = useState('')
  const [progressSubmitState, setProgressSubmitState] = useState<'idle' | 'submitting' | 'done'>('idle')
  const [selectedProjectKey, setSelectedProjectKey] = useState<string | null>(null)
  const [resolvedProjectDetail, setResolvedProjectDetail] = useState<Project | null>(null)
  const effectiveTaskProjectId = viewProjectId ?? currentProjectId ?? autoSelectedTaskProjectId
  const projectFromContext = useMemo(
    () => projects.find((project) => project.id === effectiveTaskProjectId) ?? null,
    [effectiveTaskProjectId, projects],
  )
  const resolvedProjectForContext = resolvedProjectDetail?.id === effectiveTaskProjectId
    ? resolvedProjectDetail
    : null
  const resolvedTaskProjects = useMemo(() => {
    const byId = new Map(projects.map((project) => [project.id, project]))
    if (resolvedProjectForContext) byId.set(resolvedProjectForContext.id, resolvedProjectForContext)
    return [...byId.values()]
  }, [projects, resolvedProjectForContext])
  // 专项下拉选项来自全部可见项目，而非已加载任务
  const availableTaskProjects = useMemo(
    () => resolvedTaskProjects.filter((project) => isProjectActive(project) || isProjectArchived(project)),
    [resolvedTaskProjects],
  )
  const requiresProjectSelection = effectiveTaskProjectId == null && availableTaskProjects.length > 1
  const hasNoTaskProjects = effectiveTaskProjectId == null && availableTaskProjects.length === 0
  const projectOptions = resolvedTaskProjects.map((p) => p.name)
  const ownerNames = [...new Set(resolvedTaskProjects.flatMap((p) => p.owners ?? []))]
  const focusedProject = projectFromContext ?? resolvedProjectForContext ?? null
  const projectArchived = isProjectArchived(focusedProject)
  const trashProject = resolvedTaskProjects.find((p) => p.id === effectiveTaskProjectId) ?? null
  const canManageTrash = currentUser?.is_tech_admin || resolvedTaskProjects.some((p) =>
    canManageProjectTrash({ isTechAdmin: false, projectRoles: p.user_roles ?? [] }),
  )


  // 侧边栏切换项目时重置为全部
  useEffect(() => {
    setViewProjectId(null)
  }, [currentProjectId])

  useEffect(() => {
    const rawProjectId = searchParams.get('projectId')
    if (rawProjectId === null) {
      setViewProjectId(null)
      return
    }
    const pid = Number(rawProjectId)
    setViewProjectId(Number.isFinite(pid) ? pid : null)
  }, [searchParams])

  useEffect(() => {
    let cancelled = false
    if (effectiveTaskProjectId == null || projectFromContext) {
      setResolvedProjectDetail(null)
      return () => { cancelled = true }
    }

    setResolvedProjectDetail(null)
    getProject(effectiveTaskProjectId)
      .then((project) => {
        if (!cancelled && project.id === effectiveTaskProjectId) setResolvedProjectDetail(project)
      })
      .catch(() => {
        if (!cancelled) setResolvedProjectDetail(null)
      })
    return () => { cancelled = true }
  }, [effectiveTaskProjectId, projectFromContext])

  useEffect(() => {
    if (viewProjectId != null || currentProjectId != null) {
      setAutoSelectedTaskProjectId(null)
      return
    }
    if (availableTaskProjects.length === 1) {
      setAutoSelectedTaskProjectId(availableTaskProjects[0].id)
      return
    }
    setAutoSelectedTaskProjectId(null)
  }, [viewProjectId, currentProjectId, availableTaskProjects])

  useEffect(() => {
    setSelectedTask(null)
    setExpandedTasks(new Set())
    setTaskLogs([])
    setTaskUpdates([])
    setSubTasks([])
    setTrashedSubTasks([])
  }, [effectiveTaskProjectId])

  useEffect(() => {
    if (showDeleted && !canManageTrash) {
      setShowDeleted(false)
    }
  }, [showDeleted, canManageTrash])

  const openTaskHandled = useRef(false)

  useEffect(() => {
    let cancelled = false
    if (showDeleted && !canManageTrash) {
      setShowDeleted(false)
      return () => { cancelled = true }
    }
    if (effectiveTaskProjectId == null) {
      setTasks([])
      setLoading(false)
      return () => { cancelled = true }
    }
    setLoading(true)
    // 工作推进表是项目级页面：没有明确项目上下文时不请求全局任务列表，避免普通项目角色触发后端全局读权限 403。
    const taskProjectId = effectiveTaskProjectId
    const openTaskId = searchParams.get('open_task')
    fetchTasks(taskProjectId, showDeleted)
      .then((d) => {
        if (cancelled) return
        const loaded = Array.isArray(d) ? d : []
        setTasks(loaded)
        // Auto-open task when navigated from 我的工作台
        if (openTaskId && !openTaskHandled.current) {
          const target = loaded.find(t => String(t.id) === openTaskId)
          if (target) {
            openTaskHandled.current = true
            openDetail(target)
          }
        }
      })
      .catch((err) => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 403) {
          toast.error(TASK_PROJECT_PERMISSION_DENIED_MESSAGE)
          return
        }
        toast.error(TASK_PROJECT_CONTEXT_MISSING_ENTRY_MESSAGE)
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [effectiveTaskProjectId, showDeleted, canManageTrash, searchParams])

  // 专项下拉选项来自全部可见项目，而非已加载任务

  function loadTasks(nextDeleted = showDeleted) {
    const effectiveDeleted = nextDeleted && canManageTrash
    const taskProjectId = effectiveTaskProjectId
    if (taskProjectId == null) {
      setTasks([])
      toast.error(TASK_PROJECT_CONTEXT_REQUIRED_MESSAGE)
      return Promise.resolve()
    }
    return fetchTasks(taskProjectId, effectiveDeleted)
      .then((d) => setTasks(Array.isArray(d) ? d : []))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 403) {
          toast.error(TASK_PROJECT_PERMISSION_DENIED_MESSAGE)
          return
        }
        toast.error(TASK_PROJECT_CONTEXT_MISSING_ENTRY_MESSAGE)
      })
  }

  function loadTaskSubTaskBuckets(taskId: number) {
    return Promise.all([
      fetchSubTasks(taskId, false).catch(() => [] as SubTaskItem[]),
      fetchSubTasks(taskId, true).catch(() => [] as SubTaskItem[]),
    ]).then(([active, deleted]) => {
      setSubTasks(active)
      setTrashedSubTasks(deleted)
      return { active, deleted }
    })
  }

  function handleProjectFilter(name: string) {
    if (!name) return setViewProjectId(null)
    const pid = Number(name)
    setViewProjectId(Number.isFinite(pid) ? pid : null)
  }

  const planBaseTasks = useMemo(() => tasks
    .filter((t) => {
      const taskProject = projectForTask(resolvedTaskProjects, t)
      if (filterStatus) {
        const isDelayedFilter = norm(filterStatus) === '延期' || norm(filterStatus) === '已延期'
        if (isDelayedFilter) {
          if (!isOverdueTask(t)) return false
        } else {
          if (norm(t.status) !== norm(filterStatus)) return false
        }
      }
      if (viewProjectId != null && taskProject?.id !== viewProjectId) return false
      if (filterOwner && !(projectForTask(resolvedTaskProjects, t)?.owners ?? []).includes(filterOwner)) return false
      return true
    })
    .sort((a, b) => {
      const bottomGroup = (s?: string) => NOT_STARTED.has(norm(s)) || COMPLETED.has(norm(s))
      const ag = bottomGroup(a.status) ? 1 : 0
      const bg = bottomGroup(b.status) ? 1 : 0
      if (ag !== bg) return ag - bg
      const at = a.created_at ?? ''
      const bt = b.created_at ?? ''
      return at.localeCompare(bt)
    }), [filterOwner, filterStatus, resolvedTaskProjects, tasks, viewProjectId])

  const filtered = useMemo(() => planBaseTasks.filter((task) => {
    if (!search) return true
    const taskProject = projectForTask(resolvedTaskProjects, task)
    const projectName = taskProject?.name ?? getProjectDisplayName(resolvedTaskProjects, task)
    return task.key_task?.includes(search) || projectName.includes(search)
  }), [planBaseTasks, resolvedTaskProjects, search])

  function ensurePlanTableSubTasksLoaded() {
    if (planTableLoading) return
    const missingTasks = planBaseTasks.filter((task) => !(task.id in taskSubMap))
    if (missingTasks.length === 0) return
    const missingIds = missingTasks.map((task) => task.id)
    setPlanTableLoading(true)
    fetchSubTasksBatch(missingIds, false)
      .then((batch) => {
        setTaskSubMap((prev) => {
          const next = { ...prev }
          missingIds.forEach((taskId) => {
            // 后端可能因权限跳过某些 task，对未返回的 key 置空避免重复请求
            next[taskId] = batch[String(taskId)] ?? []
          })
          return next
        })
      })
      .catch(() => {
        // 批量接口失败：兜底置空，避免反复请求卡住首屏
        setTaskSubMap((prev) => {
          const next = { ...prev }
          missingIds.forEach((taskId) => { next[taskId] = [] })
          return next
        })
      })
      .finally(() => setPlanTableLoading(false))
  }

  useEffect(() => {
    if (viewMode !== 'plan') return
    ensurePlanTableSubTasksLoaded()
  }, [viewMode, planBaseTasks, planTableLoading, taskSubMap])

  // 进入计划视图时预加载项目成员列表（用于责任人下拉）
  useEffect(() => {
    if (viewMode !== 'plan' || !focusedProject) return
    ensureProjectMembersLoaded(focusedProject.id)
  }, [viewMode, focusedProject])

  const planTableReady = !planTableLoading && planBaseTasks.every((task) => task.id in taskSubMap)

  function assignmentMembers(projectId: number | null | undefined) {
    if (!projectId) return []
    return projectMembersByProject[projectId] ?? []
  }

  function ensureProjectMembersLoaded(projectId: number | null | undefined) {
    if (!projectId || projectMembersByProject[projectId]) return
    getProjectMembers(projectId)
      .then((members) => setProjectMembersByProject((prev) => ({ ...prev, [projectId]: members })))
      .catch(() => setProjectMembersByProject((prev) => ({ ...prev, [projectId]: [] })))
  }

  function canAssignSubTasks(task: TaskItem | null | undefined) {
    const taskProject = projectForTask(resolvedTaskProjects, task)
    return !!(
      task &&
      isProjectActive(taskProject) &&
      canManageProjectWork({ isTechAdmin: currentUser?.is_tech_admin, projectRoles: taskProject?.user_roles ?? [] })
    )
  }

  function openSubTaskAssignment(task: TaskItem, subTask?: SubTaskItem | SubTaskDetail | null) {
    const taskProject = projectForTask(resolvedTaskProjects, task)
    if (!isProjectActive(taskProject)) {
      toast.warning('项目尚未进入执行阶段，暂不能维护执行期关键任务。')
      return
    }
    if (!canManageProjectWork({ isTechAdmin: currentUser?.is_tech_admin, projectRoles: taskProject?.user_roles ?? [] })) return
    focusTask(task)
    setEditingSubTask(subTask ?? null)
    ensureProjectMembersLoaded(task.project_id ?? currentProjectId)
    setSubTaskFormOpen(true)
  }

  // ===== Selection 统一入口：所有切换焦点状态必须走这几个 helper，避免漏清互斥状态 =====
  // 互斥规则：task / subtask / project 三者只能选一；subtask 可叠在 task 之上（用于「返回重点工作」）
  function focusTask(task: TaskItem) {
    setSelectedTask(task)
    setSelectedSubTask(null)
    setSubDetailLoading(false)
    setSelectedProjectKey(null)
  }

  function focusSubTask(st: SubTaskItem, opts?: { keepTask?: boolean }) {
    setSelectedSubTask(null)
    setSubDetailLoading(true)
    setSubEditField(null)
    setSelectedProjectKey(null)
    if (!opts?.keepTask) setSelectedTask(null)
    fetchSubtaskDetail(st.id)
      .then((d) => setSelectedSubTask(d))
      .catch(() => setSelectedSubTask({ ...st } as SubTaskDetail))
      .finally(() => setSubDetailLoading(false))
  }

  function focusProject(key: string) {
    setSelectedProjectKey(key)
    setSelectedTask(null)
    setSelectedSubTask(null)
    setSubDetailLoading(false)
  }

  function clearSelection() {
    setSelectedTask(null)
    setSelectedSubTask(null)
    setSubDetailLoading(false)
    setSelectedProjectKey(null)
  }

  function openSubDetail(st: SubTaskItem) {
    focusSubTask(st)
  }

  async function handleSubStatusUpdate(status: string) {
    if (!selectedSubTask) return
    setSubSaving(true)
    try {
      const updated = await patchSubTaskStatus(selectedSubTask.id, status)
      if (isPendingConfirmation(updated)) {
        toast.success('已提交至 AI 确认中心，等待项目负责人确认')
        return
      }
      const merged = { ...selectedSubTask, ...updated }
      setSelectedSubTask(merged as SubTaskDetail)
      setSubTasks((prev) => prev.map((x) => x.id === selectedSubTask.id ? { ...x, status } : x))
      setTaskSubMap((prev) => {
        const tid = selectedSubTask.task_id
        return { ...prev, [tid]: (prev[tid] ?? []).map((x) => x.id === selectedSubTask.id ? { ...x, status } : x) }
      })
    } finally { setSubSaving(false) }
  }

  async function handleSubFieldSave() {
    if (!selectedSubTask || !subEditField) return
    setSubSaving(true)
    try {
      const projectId = selectedTask?.project_id ?? currentProjectId
      if (!projectId) throw new Error('missing project_id')
      const payload: SubTaskPayload = {
        project_id: projectId,
        title: selectedSubTask.title,
        assignee: selectedSubTask.assignee,
        plan_time: selectedSubTask.plan_time,
        status: selectedSubTask.status,
        completion_criteria: selectedSubTask.completion_criteria ?? '',
        notes: selectedSubTask.notes ?? '',
      }
      ;(payload as Record<string, unknown>)[subEditField] = subEditVal
      const updated = await updateSubTask(selectedSubTask.id, payload)
      const merged = { ...selectedSubTask, ...updated }
      setSelectedSubTask(merged as SubTaskDetail)
      setSubTasks((prev) => prev.map((x) => x.id === selectedSubTask.id ? { ...x, ...updated } : x))
    } finally {
      setSubSaving(false)
      setSubEditField(null)
    }
  }

  async function handleSubDraftSave() {
    if (!selectedSubTask) return
    setSubSaving(true)
    try {
      const projectId = selectedTask?.project_id ?? currentProjectId
      if (!projectId) throw new Error('missing project_id')
      const payload: SubTaskPayload = {
        project_id: projectId,
        title: subEditDraft.title ?? selectedSubTask.title,
        assignee: subEditDraft.assignee ?? selectedSubTask.assignee,
        plan_time: subEditDraft.plan_time ?? selectedSubTask.plan_time ?? '',
        status: subEditDraft.status ?? selectedSubTask.status,
        completion_criteria: subEditDraft.completion_criteria ?? selectedSubTask.completion_criteria ?? '',
        notes: subEditDraft.notes ?? selectedSubTask.notes ?? '',
      }
      const updated = await updateSubTask(selectedSubTask.id, payload)
      const merged = { ...selectedSubTask, ...updated }
      setSelectedSubTask(merged as SubTaskDetail)
      setSubTasks((prev) => prev.map((x) => x.id === selectedSubTask.id ? { ...x, ...updated } : x))
      setTaskSubMap((prev) => {
        const tid = selectedSubTask.task_id
        return { ...prev, [tid]: (prev[tid] ?? []).map((x) => x.id === selectedSubTask.id ? { ...x, ...updated } : x) }
      })
      setSubEditMode(false)
      setSubEditDraft({})
    } finally {
      setSubSaving(false)
    }
  }

  function openDetail(task: TaskItem) {
    focusTask(task)
    setTaskLogs([])
    setTaskUpdates([])
    setSubTasks([])
    setTrashedSubTasks([])
    setProgressOpen(false)
    setProgressText('')
    setProgressSubmitState('idle')
    fetchTaskLogs(task.id).then(setTaskLogs).catch(() => {})
    fetchTaskUpdates(task.id).then(setTaskUpdates).catch(() => {})
    loadTaskSubTaskBuckets(task.id).catch(() => {})
    ensureProjectMembersLoaded(task.project_id ?? currentProjectId)
  }

  async function handleProgressSubmit() {
    if (!progressText.trim() || !currentUser || !selectedTask) return
    const projectId = selectedTask.project_id ?? currentProjectId
    if (!projectId) return
    setProgressSubmitState('submitting')
    try {
      await createUpdate({
        project_id: projectId,
        source_type: '任务进展',
        title: `${selectedTask.key_task} 进展更新`,
        transcript_text: progressText.trim(),
        submitter: currentUser.name,
      })
      setProgressSubmitState('done')
      setTimeout(() => {
        setProgressOpen(false)
        setProgressText('')
        setProgressSubmitState('idle')
      }, 1500)
    } catch {
      setProgressSubmitState('idle')
      toast.error('提交失败，请重试')
    }
  }

  function toggleInlineSubTasks(e: React.MouseEvent, taskId: number) {
    e.stopPropagation()
    if (showDeleted) return
    setExpandedTasks((prev) => {
      const next = new Set(prev)
      if (next.has(taskId)) {
        // 折叠：若当前选中的 subtask 属于该 task，清空 selection，避免右侧面板残留已折叠任务的子项
        if (selectedSubTask && selectedSubTask.task_id === taskId) {
          clearSelection()
        }
        next.delete(taskId)
        return next
      }
      next.add(taskId)
      if (!(taskId in taskSubMap)) {
        fetchSubTasks(taskId, false)
          .then((subs) => setTaskSubMap((p) => ({ ...p, [taskId]: subs })))
          .catch(() => setTaskSubMap((p) => ({ ...p, [taskId]: [] })))
      }
      return next
    })
  }

  function handleRestoreSubTask(st: SubTaskItem) {
    if (!confirm(`确认恢复关键任务「${st.title}」？恢复后会重新计算重点工作状态。`)) return
    restoreSubTask(st.id).then(() => {
      if (selectedTask) {
        loadTaskSubTaskBuckets(selectedTask.id).catch(() => {})
        refreshParentTask(selectedTask.id)
      }
    }).catch(() => toast.error('恢复失败'))
  }

  // 关键任务变更后由后端汇总重点工作状态，前端只刷新最新事实。
  function refreshParentTask(taskId: number) {
    const effectiveDeleted = showDeleted && canManageTrash
    const taskProjectId = effectiveTaskProjectId
    if (taskProjectId == null) return
    fetchTasks(taskProjectId, effectiveDeleted).then((rows) => {
      const safeRows = Array.isArray(rows) ? rows : []
      setTasks(safeRows)
      const fresh = safeRows.find((t) => t.id === taskId)
      if (fresh) setSelectedTask((prev) => prev?.id === taskId ? fresh : prev)
    }).catch(() => {})
  }

  function maybePromptCloseKeyTask(taskId: number, nextSubs: SubTaskItem[]) {
    const parentTask = tasks.find((t) => t.id === taskId)
    if (!parentTask || COMPLETED.has(norm(parentTask.status))) return
    if (!nextSubs.length || !nextSubs.every((s) => COMPLETED.has(norm(s.status)))) return
    const taskProject = projectForTask(resolvedTaskProjects, parentTask)
    const canClose = !!canManageProjectTrash({ isTechAdmin: currentUser?.is_tech_admin, projectRoles: taskProject?.user_roles ?? [] })
    if (!canClose) {
      toast.warning('该重点工作下的关键任务已全部完成，请项目负责人确认是否关闭重点工作。')
      return
    }
    if (!confirm(`重点工作「${parentTask.key_task}」下的关键任务已全部完成，是否现在关闭该重点工作？`)) return
    const projectId = parentTask.project_id ?? currentProjectId
    if (!projectId) return
    updateTask(parentTask.id, {
      project_id: projectId,
      key_task: parentTask.key_task,
      key_achievement: parentTask.key_achievement,
      completion_standard: parentTask.completion_standard,
      coordinator: parentTask.coordinator,
      owner: parentTask.owner,
      collaborators: parentTask.collaborators,
      plan_time: parentTask.plan_time,
      status: '已完成',
      problem_note: parentTask.problem_note,
    })
      .then((updated) => {
        setTasks((prev) => prev.map((t) => t.id === updated.id ? updated : t))
        setSelectedTask((prev) => prev?.id === updated.id ? updated : prev)
      })
      .catch(() => toast.error('关闭重点工作失败，请稍后重试'))
  }

  function toggleGroupCollapse(key: string) {
    setCollapsedGroups((prev) => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n })
  }

  function groupRowSpan(groupTasks: TaskItem[]) {
    return groupTasks.reduce((sum, t) => {
      const subs = taskSubMap[t.id]
      // undefined = still loading (1 skeleton row); array = loaded (0..n rows)
      const extra = expandedTasks.has(t.id) ? (subs === undefined ? 1 : subs.length) : 0
      return sum + 1 + extra
    }, 0)
  }

  function handleDelete(task: TaskItem) {
    if (!confirm(`确认删除重点工作「${task.key_task}」？其下关键任务会一并进入回收站，可由负责人或技术管理员恢复。`)) return
    deleteTask(task.id).then(() => {
      loadTasks(false)
      if (selectedTask?.id === task.id) setSelectedTask(null)
      setTaskSubMap((prev) => {
        const next = { ...prev }
        delete next[task.id]
        return next
      })
      setTrashedSubTasks([])
    }).catch(() => toast.error('删除失败'))
  }

  function handleRestoreTask(task: TaskItem) {
    if (!confirm(`确认恢复重点工作「${task.key_task}」？系统会同时恢复这次随重点工作一起删除的关键任务。`)) return
    restoreTask(task.id).then((restored) => {
      setShowDeleted(false)
      setSelectedTask(restored)
      loadTasks(false)
      loadTaskSubTaskBuckets(restored.id).catch(() => {})
      setTaskSubMap((prev) => {
        const next = { ...prev }
        delete next[task.id]
        return next
      })
    }).catch(() => toast.error('恢复失败'))
  }

  // 按专项分组（保持首次出现的顺序），用于 rowspan 合并
  const groupedRows = useMemo(() => {
    const order: string[] = []
    const map = new Map<string, { key: string; tasks: TaskItem[] }>()
    for (const t of filtered) {
      const key = taskProjectKey(resolvedTaskProjects, t)
      if (!map.has(key)) { map.set(key, { key, tasks: [] }); order.push(key) }
      map.get(key)!.tasks.push(t)
    }
    return order.map((key) => map.get(key)!)
  }, [filtered, resolvedTaskProjects])

  function handleExport() {
    const proj = resolvedTaskProjects.find((p) => p.id === (viewProjectId ?? currentProjectId))
    const title = proj ? `${proj.name} 工作推进表` : '工作推进表'
    exportTasksToExcel(filtered, title, resolvedTaskProjects)
  }

  function handlePlanExport() {
    if (!focusedProject || !planTableReady) return
    void exportPlanTableToExcel({
      project: focusedProject,
      tasks: planBaseTasks,
      taskSubMap,
      searchText: search,
    })
  }

function handleFormSave(payload: TaskPayload) {
    const pid = payload.project_id ?? viewProjectId ?? currentProjectId
    if (!pid) {
      toast.error('请选择专项')
      return
    }
    const finalPayload = { ...payload, project_id: pid }
    const req = formTask
      ? updateTask(formTask.id, finalPayload)
      : createTask(finalPayload)
    req.then(() => {
      setFormOpen(false)
      setFormTask(null)
      loadTasks(false)
    }).catch(() => toast.error('保存失败，请重试'))
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {formOpen && (
        <TaskFormModal
          task={formTask}
          projects={resolvedTaskProjects}
          onSave={handleFormSave}
          onClose={() => { setFormOpen(false); setFormTask(null) }}
        />
      )}
      {importOpen && currentProjectId && (
        <OutlineImportModal
          defaultProjectId={currentProjectId}
          projects={resolvedTaskProjects}
          onCreated={(newTasks) => {
            setTasks((prev) => [...prev, ...newTasks])
            setImportOpen(false)
          }}
          onClose={() => setImportOpen(false)}
        />
      )}
      {subTaskFormOpen && selectedTask && (
        <SubTaskAssignmentModal
          taskId={selectedTask.id}
          projectId={selectedTask.project_id ?? currentProjectId}
          editingSubTask={editingSubTask}
          projectMembers={assignmentMembers(selectedTask.project_id ?? currentProjectId)}
          extraNames={(() => {
            const pid = selectedTask.project_id ?? currentProjectId
            const names = new Set<string>()
            tasks.forEach((t) => { if (t.project_id === pid && t.owner?.trim()) names.add(t.owner.trim()) })
            subTasks.forEach((s) => { if (s.project_id === pid && s.assignee?.trim()) names.add(s.assignee.trim()) })
            return [...names]
          })()}
          onSave={(st) => {
            setSubTasks((prev) => {
              const exists = prev.some((item) => item.id === st.id)
              return exists ? prev.map((item) => item.id === st.id ? { ...item, ...st } : item) : [...prev, st]
            })
            setSubTaskFormOpen(false)
            setEditingSubTask(null)
            setTaskSubMap((p) => {
              const rows = p[st.task_id] ?? []
              const exists = rows.some((item) => item.id === st.id)
              return { ...p, [st.task_id]: exists ? rows.map((item) => item.id === st.id ? { ...item, ...st } : item) : [...rows, st] }
            })
            refreshParentTask(st.task_id)
          }}
          onClose={() => { setSubTaskFormOpen(false); setEditingSubTask(null) }}
        />
      )}

      {/* Top Bar */}
      <header className={`${viewMode === 'plan' ? 'min-h-12 px-5 py-1.5 gap-2' : 'min-h-16 px-6 py-2 gap-3'} flex items-center flex-shrink-0 bg-white border-b flex-wrap`} style={{ borderColor: '#E9EFF6' }}>
        <div className="min-w-[260px] flex-shrink-0">
          <h1 className="text-base font-bold text-slate-800">工作推进表</h1>
          {viewMode === 'execution' && <p className="text-xs text-slate-400 mt-0.5">按项目、重点工作、关键任务追踪真实推进状态</p>}
        </div>
        <div className="inline-flex items-center rounded-lg border border-slate-200 bg-slate-50 p-0.5">
          <button
            type="button"
            onClick={() => {
              setViewMode('plan')
              clearSelection()
            }}
            className={`px-3 py-1.5 text-sm font-semibold rounded-md transition-colors ${viewMode === 'plan' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
          >
            表格视图
          </button>
          <button
            type="button"
            onClick={() => setViewMode('execution')}
            className={`px-3 py-1.5 text-sm font-semibold rounded-md transition-colors ${viewMode === 'execution' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
          >
            执行详情
          </button>
        </div>

        {/* Filters */}
        <div className="flex flex-1 items-center justify-end gap-2 flex-wrap">
          <select
            value={String(effectiveTaskProjectId ?? '')}
            onChange={(event) => {
              handleProjectFilter(event.target.value)
              setAutoSelectedTaskProjectId(null)
            }}
            className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-700 cursor-pointer focus:outline-none font-medium"
          >
            <option value="">请选择项目</option>
            {availableTaskProjects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <select
            value={filterStatus}
            onChange={(event) => setFilterStatus(event.target.value)}
            className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-700 cursor-pointer focus:outline-none font-medium"
          >
            <option value="">全部状态</option>
            <option value="未开始">未开始</option>
            <option value="进行中">进行中</option>
            <option value="已完成">已完成</option>
            <option value="延期">延期</option>
            <option value="暂缓">暂缓</option>
          </select>
          <select
            value={filterOwner}
            onChange={(e) => setFilterOwner(e.target.value)}
            className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 bg-white text-slate-700 cursor-pointer focus:outline-none font-medium"
          >
            <option value="">全部负责人</option>
            {ownerNames.map((o) => <option key={o}>{o}</option>)}
          </select>
          <div className="relative">
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" style={{ width: 13, height: 13 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={viewMode === 'plan' ? '搜索重点工作、关键任务、责任人' : '搜索重点工作…'}
              className="pl-8 pr-3 py-1.5 text-sm bg-slate-50 border border-slate-200 rounded-lg focus:outline-none w-64"
            />
          </div>
        </div>

        {viewMode === 'execution' && (
        <div className="plan-execution-actions flex items-center gap-2 ml-1 flex-shrink-0">
          <div className="inline-flex items-center rounded-lg border border-slate-200 bg-slate-50 p-0.5">
            <button
              onClick={() => { clearSelection(); setExpandedTasks(new Set()); setShowDeleted(false) }}
              className={`px-3 py-1.5 text-sm font-semibold rounded-md transition-colors ${!showDeleted ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
            >
              在办
            </button>
            {canManageTrash && (
              <button
                onClick={() => {
                  clearSelection()
                  setExpandedTasks(new Set())
                  setSearch('')
                  setFilterStatus('')
                  setFilterOwner('')
                  setShowDeleted(true)
                }}
                className={`px-3 py-1.5 text-sm font-semibold rounded-md transition-colors ${showDeleted ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
              >
                回收站
              </button>
            )}
          </div>
          <select
            defaultValue=""
            onChange={(e) => {
              const action = e.target.value
              if (!action) return
              if (action === 'export') handleExport()
              if (action === 'import') setImportOpen(true)
              if (action === 'create') { setFormTask(null); setFormOpen(true) }
              e.currentTarget.value = ''
            }}
            className="cursor-pointer min-w-[220px] px-4 py-2 rounded-lg border border-slate-200 bg-white text-slate-700 text-sm font-semibold focus:outline-none hover:bg-slate-50"
          >
            <option value="" disabled>操作</option>
            <option value="export">导出表格</option>
            {!showDeleted && canManageProjectWork({ isTechAdmin: currentUser?.is_tech_admin, projectRoles: currentProjectRoles }) && currentProjectId && !projectArchived && (
              <option value="import">从大纲导入</option>
            )}
            {!showDeleted && !projectArchived && canManageProjectWork({ isTechAdmin: currentUser?.is_tech_admin, projectRoles: currentProjectRoles }) && <option value="create">新增重点工作</option>}
          </select>
        </div>
        )}
      </header>

      {/* Sub-header: stat chips + batch bar */}
      {viewMode === 'execution' && (
      <div className="bg-white border-b px-6 py-3 space-y-2.5 flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
        {/* Status chips */}
        <div className="flex items-center gap-3">
          {[
            { label: '未启动', filterVal: '未开始', val: count(tasks, NOT_STARTED), bg: '#F8FAFC', border: '#E2E8F0', color: '#64748B', iconBg: '#E2E8F0',
              icon: <svg style={{ width: 15, height: 15 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" strokeWidth="2" /><path strokeLinecap="round" strokeWidth="2" d="M12 8v4" /><circle cx="12" cy="16" r="0.5" fill="currentColor" /></svg> },
            { label: '进行中', filterVal: '进行中', val: count(tasks, IN_PROGRESS),  bg: '#EFF6FF', border: '#BFDBFE', color: '#2563EB', iconBg: '#DBEAFE',
              icon: <svg style={{ width: 15, height: 15 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg> },
            { label: '已完成', filterVal: '已完成', val: count(tasks, COMPLETED),    bg: '#F0FDF4', border: '#BBF7D0', color: '#059669', iconBg: '#D1FAE5',
              icon: <svg style={{ width: 15, height: 15 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg> },
            { label: '延期',   filterVal: '延期',   val: count(tasks, DELAYED), bg: '#FEF2F2', border: '#FECACA', color: '#DC2626', iconBg: '#FEE2E2',
              icon: <svg style={{ width: 15, height: 15 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg> },
            { label: '暂缓',   filterVal: '暂缓',   val: count(tasks, PAUSED),       bg: '#FFFBEB', border: '#FDE68A', color: '#D97706', iconBg: '#FEF3C7',
              icon: <svg style={{ width: 15, height: 15 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg> },
          ].map(({ label, filterVal, val, bg, border, color, iconBg, icon }) => {
            const isActive = norm(filterStatus) === norm(filterVal)
            return (
              <div
                key={label}
                onClick={() => setFilterStatus(isActive ? '' : filterVal)}
                className="flex items-center gap-2.5 px-4 py-2.5 rounded-xl cursor-pointer transition-all hover:scale-[1.03]"
                style={{
                  background: bg,
                  border: `${isActive ? '2px' : '1.5px'} solid ${isActive ? color : border}`,
                  boxShadow: isActive ? `0 0 0 3px ${color}22` : undefined,
                }}
              >
                <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: iconBg, color }}>
                  {icon}
                </div>
                <div>
                  <p className="text-xs font-medium leading-none" style={{ color }}>{label}</p>
                  <p className="text-xl font-bold leading-none mt-0.5" style={{ color }}>{val}</p>
                </div>
              </div>
            )
          })}
        </div>

      </div>
      )}

      {/* Main */}
      <div className="flex-1 min-w-0 min-h-0 flex overflow-hidden" style={{ background: viewMode === 'plan' ? '#F8FAFC' : '#F1F5F9' }}>
        <div
          className={viewMode === 'plan' ? 'work-progress-plan-shell flex-1 min-w-0 overflow-hidden flex flex-col' : 'flex-1 overflow-y-auto'}
          style={viewMode === 'plan'
            ? { background: '#F8FAFC' }
            : { background: '#F1F5F9', padding: '16px 20px 20px', paddingRight: 20 }}
        >
          {hasNoTaskProjects ? (
            <div className="h-40 flex items-center justify-center">
              <div className="text-center text-slate-400">
                <div className="text-sm font-semibold">{TASK_PROJECT_CONTEXT_EMPTY_MESSAGE}</div>
                <div className="text-xs mt-1">可在项目进入执行阶段后查看工作推进表。</div>
              </div>
            </div>
          ) : requiresProjectSelection ? (
            <div className="h-40 flex items-center justify-center">
              <div className="text-center text-slate-500">
                <div className="text-sm font-semibold">{TASK_PROJECT_CONTEXT_REQUIRED_MESSAGE}</div>
                <div className="text-xs mt-1">请在顶部项目下拉框中选择一个项目。</div>
              </div>
            </div>
          ) : viewMode === 'plan' ? (
            <PlanTableViewV2
              project={focusedProject}
              tasks={planBaseTasks}
              taskSubMap={taskSubMap}
              searchText={search}
              loading={planTableLoading}
              exportDisabled={!planTableReady}
              onExport={handlePlanExport}
              currentUserName={currentUser?.name}
              projectRoles={currentProjectRoles ?? []}
              isTechAdmin={currentUser?.is_tech_admin ?? false}
              projectMembers={projectMembersByProject[focusedProject?.id ?? 0] ?? []}
              onUpdateSubTask={async (id, payload) => {
                const updated = await updateSubTask(id, {
                  ...payload,
                  project_id: focusedProject!.id,
                })
                setTaskSubMap((prev) => {
                  const next = { ...prev }
                  for (const tid of Object.keys(next)) {
                    const list = next[Number(tid)]
                    const idx = list.findIndex((s) => s.id === id)
                    if (idx >= 0) {
                      next[Number(tid)] = [...list]
                      next[Number(tid)][idx] = updated
                      break
                    }
                  }
                  return next
                })
                return updated
              }}
            />
          ) : loading ? (
            <div className="h-40 flex items-center justify-center text-slate-400 text-sm">加载中...</div>
          ) : filtered.length === 0 ? (
            <div className="h-40 flex items-center justify-center">
              <div className="text-center text-slate-400">
                <div className="text-sm font-semibold">暂无数据</div>
                <div className="text-xs mt-1">当前筛选条件下没有重点工作</div>
              </div>
            </div>
          ) : (
            <div className="rounded-2xl bg-white border overflow-hidden shadow-sm" style={{ borderColor: '#E2E8F0' }}>
              {/* 表头 */}
              <div className="flex items-center px-4 py-2.5 border-b select-none" style={{ borderColor: '#E9EFF6', background: '#F8FAFC' }}>
                <div style={{ width: 28 }} />
                <div className="flex-1 min-w-0 pl-1 text-xs font-semibold text-slate-400">层级 / 名称</div>
                <div className="text-xs font-semibold text-slate-400 flex-shrink-0" style={{ width: 136 }}>负责人</div>
                <div className="text-xs font-semibold text-slate-400 flex-shrink-0" style={{ width: 108 }}>计划时间</div>
                <div className="text-xs font-semibold text-slate-400 flex-shrink-0" style={{ width: 96 }}>状态</div>
                <div className="text-xs font-semibold text-slate-400 flex-shrink-0" style={{ width: 68 }}>关键任务</div>
                <div className="text-xs font-semibold text-slate-400 flex-shrink-0 text-center" style={{ width: 60 }}>风险</div>
                <div className="text-xs font-semibold text-slate-400 flex-shrink-0 text-right" style={{ width: 68 }}>操作</div>
              </div>

              {groupedRows.map(({ key, tasks: groupTasks }) => {
                const resolvedGroupName = groupProjectName(resolvedTaskProjects, key, groupTasks)
                const groupProject = key.startsWith('project:')
                  ? resolvedTaskProjects.find((p) => p.id === Number(key.slice('project:'.length))) ?? null
                  : focusedProject
                const groupColor = projectColor(projectOptions, resolvedGroupName)
                const groupDone = count(groupTasks, COMPLETED)
                const groupInProgress = count(groupTasks, IN_PROGRESS)
                const groupDelayed = count(groupTasks, DELAYED)
                const groupStatus = groupDelayed > 0 ? '延期' : groupInProgress > 0 ? '进行中' : groupDone === groupTasks.length ? '已完成' : '未启动'
                const groupBadge = getBadge(groupStatus)
                const groupOwner = projectPeopleText(groupProject?.owners)
                const collapsed = collapsedGroups.has(key)
                const isSelProj = selectedProjectKey === key

                return (
                  <div key={key} className="border-b last:border-b-0" style={{ borderColor: '#E2E8F0' }}>
                    {/* 项目行 */}
                    <div
                      className={`flex items-center px-3 py-3 cursor-pointer select-none transition-colors ${isSelProj ? 'bg-blue-50' : 'hover:bg-slate-50/80'}`}
                      style={{ borderLeft: `3px solid ${groupColor}` }}
                    >
                      <button type="button" onClick={(e) => { e.stopPropagation(); toggleGroupCollapse(key) }}
                        className="w-7 h-7 flex items-center justify-center rounded-md text-slate-400 hover:text-slate-600 flex-shrink-0">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style={{ width: 13, height: 13, transition: 'transform 0.15s', transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }}>
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 9l6 6 6-6" />
                        </svg>
                      </button>
                      <div className="flex-1 min-w-0 flex items-center gap-2 cursor-pointer" role="button" tabIndex={0} onClick={() => focusProject(key)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); focusProject(key) } }}>
                        <span className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0" style={{ background: `${groupColor}18`, color: groupColor }}>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style={{ width: 12, height: 12 }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 7a2 2 0 012-2h4l2 2h10a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" /></svg>
                        </span>
                        <span className="text-sm font-bold text-slate-800 truncate">{resolvedGroupName}</span>
                        {groupOwner && groupOwner !== '—' && (
                          <span className="text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0" style={{ background: '#EFF6FF', color: '#1D4ED8' }}>负责人：{groupOwner}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 flex-shrink-0" style={{ width: 136 }}>
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold ${groupBadge.cls}`}>
                          <span className="w-1.5 h-1.5 rounded-full" style={{ background: groupBadge.dot }} />{groupBadge.label}
                        </span>
                      </div>
                      <div className="text-xs text-slate-400 flex-shrink-0" style={{ width: 108 }}>{groupTasks.length}个任务</div>
                      <div style={{ width: 96 }} /><div style={{ width: 68 }} /><div style={{ width: 60 }} /><div style={{ width: 68 }} />
                    </div>

                    {/* 重点工作行 */}
                    {!collapsed && groupTasks.map((task, i) => {
                      const taskProject = projectForTask(resolvedTaskProjects, task)
                      const badge = getBadge(task.status)
                      const taskExpanded = expandedTasks.has(task.id)
                      const inlineSubs = showDeleted ? [] : (taskSubMap[task.id] ?? null)
                      const canExpand = !showDeleted
                      const canAssignThisTask = canAssignSubTasks(task)
                      const rowDeleted = !!task.is_deleted
                      const subProgress = subTaskProgress(inlineSubs)
                      const taskOwner = projectPeopleText(taskProject?.owners ?? task.owner)
                      const isSelTask = selectedTask?.id === task.id

                      return (
                        <div key={task.id}>
                          <div
                            className={`flex items-center border-t transition-colors ${isSelTask ? 'bg-blue-50/80' : rowDeleted ? 'bg-orange-50/60' : 'hover:bg-slate-50/60'}`}
                            style={{ borderColor: '#E9EFF6', paddingLeft: 36, paddingRight: 12, paddingTop: 10, paddingBottom: 10 }}
                          >
                            {canExpand ? (
                              <button type="button" onClick={(e) => toggleInlineSubTasks(e, task.id)}
                                className="w-5 h-5 flex items-center justify-center rounded text-slate-400 hover:text-slate-600 flex-shrink-0 mr-1.5">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style={{ width: 12, height: 12, transition: 'transform 0.15s', transform: taskExpanded ? 'rotate(90deg)' : 'rotate(0deg)' }}>
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                                </svg>
                              </button>
                            ) : <span style={{ width: 21 }} />}
                            <span className="text-xs font-bold px-1.5 py-0.5 rounded flex-shrink-0 mr-2" style={{ background: '#EEF2FF', color: '#6D28D9', minWidth: 20, textAlign: 'center' }}>{i + 1}</span>
                            <div className="flex-1 min-w-0 flex items-center gap-1.5 cursor-pointer" role="button" tabIndex={0} onClick={() => openDetail(task)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openDetail(task) } }}>
                              <span className="text-sm font-medium text-slate-800 truncate">{task.key_task || '-'}</span>
                              {rowDeleted && <span className="text-xs px-1.5 py-0.5 rounded-full font-semibold flex-shrink-0" style={{ background: '#FFEDD5', color: '#C2410C' }}>已删除</span>}
                            </div>
                            <div className="flex-shrink-0" style={{ width: 136 }}><OwnerCell name={taskOwner} /></div>
                            <div className="text-xs text-slate-500 flex-shrink-0" style={{ width: 108 }}>{shortDate(task.plan_time)}</div>
                            <div className="flex-shrink-0" style={{ width: 96 }}>
                              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${badge.cls}`} style={{ whiteSpace: 'nowrap' }}>
                                <span className="w-1.5 h-1.5 rounded-full" style={{ background: badge.dot }} />{badge.label}
                              </span>
                            </div>
                            <div className="text-xs font-bold text-blue-600 flex-shrink-0" style={{ width: 68 }}>{subProgress.label}</div>
                            <div className="flex-shrink-0 flex justify-center" style={{ width: 60 }}>
                              {isOverdueTask(task) ? (
                                <span className="w-6 h-6 rounded-full bg-red-50 text-red-500 flex items-center justify-center">
                                  <svg viewBox="0 0 20 20" fill="currentColor" style={{ width: 12, height: 12 }}><path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" /></svg>
                                </span>
                              ) : (
                                <span className="w-6 h-6 rounded-full bg-emerald-50 text-emerald-500 flex items-center justify-center">
                                  <svg viewBox="0 0 20 20" fill="currentColor" style={{ width: 12, height: 12 }}><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" /></svg>
                                </span>
                              )}
                            </div>
                            <div className="flex-shrink-0 flex justify-end gap-2" style={{ width: 120 }}>
                              {canAssignThisTask && (
                                <button type="button" onClick={(e) => { e.stopPropagation(); openSubTaskAssignment(task) }} className="text-xs text-indigo-600 font-semibold hover:text-indigo-700">新增关键任务</button>
                              )}
                              <button type="button" onClick={(e) => { e.stopPropagation(); openDetail(task) }} className="text-xs text-blue-600 font-semibold hover:text-blue-700">查看</button>
                            </div>
                          </div>

                          {/* 关键任务行 */}
                          {canExpand && taskExpanded && (
                            inlineSubs === null ? (
                              <div className="border-t text-xs text-slate-400 py-2.5" style={{ borderColor: '#E9EFF6', paddingLeft: 76 }}>关键任务加载中...</div>
                            ) : inlineSubs.length === 0 ? (
                              <div className="border-t text-xs text-slate-400 py-2.5" style={{ borderColor: '#E9EFF6', paddingLeft: 76 }}>暂无关键任务</div>
                            ) : inlineSubs.map((st, subIdx) => {
                              const stBadge = getBadge(st.status)
                              const canEditThisSub = canEditSubTaskStatus({
                                isTechAdmin: currentUser?.is_tech_admin,
                                projectRoles: taskProject?.user_roles ?? [],
                                currentUserName: currentUser?.name,
                                assignee: st.assignee,
                              })
                              const isSelSub = selectedSubTask?.id === st.id
                              return (
                                <div
                                  key={st.id}
                                  className={`flex items-center border-t transition-colors cursor-pointer ${isSelSub ? 'bg-purple-50/80' : 'hover:bg-purple-50/40'}`}
                                  style={{ borderColor: '#E9EFF6', borderLeft: `4px solid ${groupColor}`, paddingLeft: 60, paddingRight: 12, paddingTop: 8, paddingBottom: 8 }}
                                  onClick={(e) => { e.stopPropagation(); openSubDetail(st) }}
                                >
                                  <span className="flex-shrink-0 w-4" />
                                  <span className="text-xs font-semibold flex-shrink-0 mr-2" style={{ color: groupColor, minWidth: 30 }}>{i+1}.{subIdx+1}</span>
                                  <span className="text-sm text-slate-700 truncate flex-1">{st.title}</span>
                                  <div className="flex-shrink-0" style={{ width: 136 }}><OwnerCell name={st.assignee} /></div>
                                  <div className="text-xs text-slate-500 flex-shrink-0" style={{ width: 108 }}>{shortDate(st.plan_time)}</div>
                                  <div className="flex-shrink-0" style={{ width: 96 }} onClick={(e) => e.stopPropagation()}>
                                    {canEditThisSub ? (
                                      <select value={st.status} onChange={(e) => {
                                        const ns = e.target.value
                                        patchSubTaskStatus(st.id, ns)
                                          .then((updated) => {
                                            if (isPendingConfirmation(updated)) { alert('已提交至 AI 确认中心，等待项目负责人确认'); return }
                                            setTaskSubMap((prev) => ({ ...prev, [task.id]: (prev[task.id] ?? []).map((x) => x.id === st.id ? { ...x, ...updated } : x) }))
                                          })
                                          .catch(() => toast.error('更新失败'))
                                      }}
                                        className="text-xs border rounded-full px-2 py-0.5 font-bold cursor-pointer focus:outline-none"
                                        style={{ background: stBadge.cls.includes('blue') ? '#EFF6FF' : stBadge.cls.includes('emerald') ? '#F0FDF4' : stBadge.cls.includes('red') ? '#FEF2F2' : stBadge.cls.includes('amber') ? '#FFFBEB' : '#F8FAFC', color: stBadge.dot, border: `1.5px solid ${stBadge.dot}50` }}>
                                        {['未开始','进行中','已完成','暂缓'].map((s) => <option key={s}>{s}</option>)}
                                      </select>
                                    ) : (
                                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${stBadge.cls}`}>
                                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: stBadge.dot }} />{stBadge.label}
                                      </span>
                                    )}
                                  </div>
                                  <div style={{ width: 68 }} /><div style={{ width: 60 }} />
                                  <div className="flex justify-end gap-2 flex-shrink-0" style={{ width: 96 }}>
                                    {canAssignThisTask && (
                                      <button type="button" onClick={(e) => { e.stopPropagation(); openSubTaskAssignment(task, st) }} className="text-xs text-indigo-600 hover:text-indigo-700 font-semibold">编辑</button>
                                    )}
                                    <button type="button" onClick={(e) => { e.stopPropagation(); openSubDetail(st) }} className="text-xs text-indigo-500 hover:text-indigo-700 font-semibold">详情</button>
                                  </div>
                                </div>
                              )
                            })
                          )}
                        </div>
                      )
                    })}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {(viewMode === 'execution' || selectedSubTask || subDetailLoading) && <aside
          data-testid="work-progress-detail-panel"
          className="w-[380px] flex-shrink-0 border-l bg-white flex flex-col overflow-hidden"
          style={{ borderColor: '#E2E8F0' }}
        >
          {(() => {
            const projectDetail = selectedProjectKey
              ? (
                  selectedProjectKey.startsWith('project:')
                    ? resolvedTaskProjects.find((project) => project.id === Number(selectedProjectKey.slice('project:'.length))) ?? null
                    : resolvedTaskProjects.find((project) => project.name === selectedProjectKey) ?? null
                )
              : null
            const selectedTaskProject = projectForTask(resolvedTaskProjects, selectedTask)
            const selectedTaskArchived = isProjectArchived(selectedTaskProject)
            const selectedSubProject = projectForSubTask(resolvedTaskProjects, tasks, selectedSubTask)
            const subParent = selectedSubTask
              ? tasks.find((task) => task.id === selectedSubTask.task_id) ?? null
              : null

            if (selectedSubTask || subDetailLoading) {
              const badge = getBadge(selectedSubTask?.status)
              const subCanEdit = selectedSubTask && !isProjectArchived(selectedSubProject) && canEditSubTaskStatus({
                isTechAdmin: currentUser?.is_tech_admin,
                projectRoles: selectedSubProject?.user_roles ?? [],
                currentUserName: currentUser?.name,
                assignee: selectedSubTask.assignee,
              })
              return (
                <div className="flex flex-col h-full overflow-hidden bg-white">
                  {/* 顶部：返回 + 标题 + 关闭 */}
                  <div className="px-4 pt-3 pb-2 border-b flex-shrink-0" style={{ borderColor: '#E2E8F0', background: '#F8FAFC' }}>
                    <div className="flex items-center justify-between mb-1">
                      <button
                        onClick={() => { setSelectedSubTask(null); setSubDetailLoading(false); setSubEditField(null) }}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-blue-600 transition-colors"
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style={{ width: 12, height: 12 }}>
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
                        </svg>
                        {selectedTask ? '返回重点工作' : '返回列表'}
                      </button>
                      <button
                        onClick={() => clearSelection()}
                        className="w-6 h-6 flex items-center justify-center rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100"
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style={{ width: 13, height: 13 }}>
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                    <p className="text-xs font-semibold" style={{ color: '#94A3B8' }}>关键任务详情</p>
                    <h2 className="text-sm font-bold mt-0.5 leading-snug" style={{ color: '#1E293B' }}>{selectedSubTask?.title ?? '加载中...'}</h2>
                  </div>

                  {/* 滚动区 — 精简紧凑 */}
                  <div className="flex-1 overflow-y-auto p-3 space-y-2">
                    {subDetailLoading && !selectedSubTask ? (
                      <p className="text-xs text-center py-8" style={{ color: '#94A3B8' }}>加载中…</p>
                    ) : selectedSubTask ? (
                      <>
                        {/* 状态 + 责任人 + 计划时间 */}
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold whitespace-nowrap"
                            style={{
                              background: badge.label === '已完成' ? '#DCFCE7' : badge.label === '进行中' ? '#DBEAFE' : badge.label === '暂缓' ? '#FEF3C7' : '#F1F5F9',
                              color: badge.label === '已完成' ? '#15803D' : badge.label === '进行中' ? '#2563EB' : badge.label === '暂缓' ? '#B45309' : '#64748B'
                            }}>
                            <span className="w-1.5 h-1.5 rounded-full" style={{
                              background: badge.label === '已完成' ? '#22C55E' : badge.label === '进行中' ? '#3B82F6' : badge.label === '暂缓' ? '#F59E0B' : '#94A3B8'
                            }} />{badge.label}
                          </span>
                          {selectedSubTask.assignee && (
                            <span className="text-xs font-semibold" style={{ color: '#475569' }}>责任人：{selectedSubTask.assignee}</span>
                          )}
                          {selectedSubTask.plan_time && (
                            <span className="text-xs" style={{ color: '#94A3B8' }}>{selectedSubTask.plan_time}</span>
                          )}
                        </div>

                        {/* 基本信息 */}
                        <div className="rounded border overflow-hidden" style={{ borderColor: '#E2E8F0', background: '#FFF' }}>
                          {([
                            { label: '所属项目', value: selectedSubProject?.name },
                            { label: '重点工作', value: subParent?.key_task ?? selectedSubTask.parent_task?.key_task },
                            { label: '负责人', value: selectedSubTask.assignee },
                          ] as { label: string; value?: string }[]).filter((r) => r.value).map((row) => (
                            <div key={row.label} className="flex gap-2 px-2.5 py-1.5 border-b last:border-b-0" style={{ borderColor: '#F1F5F9' }}>
                              <span className="w-14 shrink-0 text-xs font-semibold" style={{ color: '#94A3B8' }}>{row.label}</span>
                              <span className="flex-1 text-xs font-medium" style={{ color: '#334155' }}>{row.value || '—'}</span>
                            </div>
                          ))}
                        </div>

                        {/* 当前状态 */}
                        {subCanEdit ? (
                          <div>
                            <p className="text-xs font-bold mb-0.5" style={{ color: '#64748B' }}>当前状态</p>
                            <select
                              value={selectedSubTask.status ?? ''}
                              onChange={(e) => handleSubStatusUpdate(e.target.value)}
                              disabled={subSaving || selectedTaskArchived}
                              className="w-full rounded border px-2.5 py-1 text-xs font-bold focus:outline-none"
                              style={{ borderColor: '#E2E8F0', background: '#FFF', color: '#334155' }}
                            >
                              {['未开始', '进行中', '已完成', '暂缓'].map((s) => <option key={s}>{s}</option>)}
                            </select>
                          </div>
                        ) : null}

                        {/* 完成标准 */}
                        {selectedSubTask.completion_criteria && (
                          <div>
                            <p className="text-xs font-bold mb-0.5" style={{ color: '#64748B' }}>评价标准</p>
                            <div className="rounded px-2.5 py-1.5 text-xs leading-relaxed" style={{ background: '#EEF2FF', color: '#3730A3', border: '1px solid #C7D2FE' }}>
                              {selectedSubTask.completion_criteria}
                            </div>
                          </div>
                        )}

                        {/* 最新进展 */}
                        <div>
                          <p className="text-xs font-bold mb-0.5" style={{ color: '#64748B' }}>最新进展</p>
                          {parseProgressTimeline(selectedSubTask.notes).length > 0 ? (
                            <div className="space-y-1">
                              {parseProgressTimeline(selectedSubTask.notes).map((entry, idx) => (
                                <div key={`${entry.date}-${idx}`} className="rounded px-2.5 py-1.5" style={{ background: '#F8FAFC', border: '1px solid #F1F5F9' }}>
                                  <span className="text-xs" style={{ color: '#334155' }}>
                                    {entry.date && <span style={{ color: '#94A3B8', fontSize: '11px', marginRight: '6px' }}>[{entry.date}]</span>}
                                    {entry.text}
                                  </span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-xs" style={{ color: '#CBD5E1' }}>暂无进展记录</p>
                          )}
                        </div>

                        {/* 来源信息 */}
                        {selectedSubTask.source_submission && (
                          <div>
                            <p className="text-xs font-bold mb-0.5" style={{ color: '#64748B' }}>来源</p>
                            <div className="rounded px-2.5 py-1.5" style={{ background: '#F0F9FF', border: '1px solid #BAE6FD' }}>
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="px-1.5 py-0.5 rounded text-xs font-bold" style={{ background: '#DBEAFE', color: '#1D4ED8' }}>{selectedSubTask.source_submission.source_type}</span>
                                <span className="text-xs" style={{ color: '#64748B' }}>{selectedSubTask.source_submission.submitter}</span>
                                <span className="text-xs" style={{ color: '#94A3B8' }}>{selectedSubTask.source_submission.created_at?.slice(0, 10)}</span>
                              </div>
                              {selectedSubTask.source_submission.title && (
                                <p className="text-xs font-medium mt-0.5" style={{ color: '#334155' }}>{selectedSubTask.source_submission.title}</p>
                              )}
                            </div>
                          </div>
                        )}

                        {/* 关联成果 */}
                        {selectedSubTask.related_achievements && selectedSubTask.related_achievements.length > 0 && (
                          <div>
                            <p className="text-xs font-bold mb-0.5" style={{ color: '#64748B' }}>关联成果（{selectedSubTask.related_achievements.length}）</p>
                            <div className="space-y-1">
                              {selectedSubTask.related_achievements.map((ach) => (
                                <div key={ach.id} className="rounded px-2.5 py-1.5" style={{ background: '#FFFBEB', border: '1px solid #FDE68A' }}>
                                  <p className="text-xs font-semibold" style={{ color: '#92400E' }}>{ach.name}</p>
                                  <p className="text-xs" style={{ color: '#B45309' }}>{ach.achievement_type} · {ach.status}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* 关联问题 */}
                        {selectedSubTask.related_issues && selectedSubTask.related_issues.length > 0 && (
                          <div>
                            <p className="text-xs font-bold mb-0.5" style={{ color: '#64748B' }}>关键问题（{selectedSubTask.related_issues.length}）</p>
                            <div className="space-y-1">
                              {selectedSubTask.related_issues.map((issue) => (
                                <div key={issue.id} className="rounded px-2.5 py-1.5" style={{ background: '#FEF2F2', border: '1px solid #FECACA' }}>
                                  <p className="text-xs leading-relaxed" style={{ color: '#991B1B' }}>{issue.description}</p>
                                  <p className="text-xs" style={{ color: '#DC2626' }}>{issue.issue_type} · {issue.priority} · {issue.status}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    ) : null}
                  </div>
                </div>
              )
            }

            if (selectedTask) {
              const badge = getBadge(selectedTask.status)
              const detailProgress = subTaskProgress(subTasks)
              const canOwn = canManageProjectWork({ isTechAdmin: currentUser?.is_tech_admin, projectRoles: selectedTaskProject?.user_roles ?? [] })
              const canAssignSelectedTask = canAssignSubTasks(selectedTask)
              const selectedTaskActive = isProjectActive(selectedTaskProject)
              const canTrashTask = !!(selectedTaskProject && canManageProjectTrash({ isTechAdmin: currentUser?.is_tech_admin, projectRoles: selectedTaskProject.user_roles ?? [] }))
              return (
                <div className="flex flex-col h-full overflow-hidden">
                  {/* 标题栏 */}
                  <div className="px-5 py-4 border-b flex-shrink-0 flex items-start justify-between gap-3" style={{ borderColor: '#E9EFF6' }}>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-slate-400">重点工作详情</p>
                      <h2 className="text-sm font-bold text-slate-900 mt-0.5 leading-snug">{selectedTask.key_task}</h2>
                    </div>
                    <button
                      onClick={() => clearSelection()}
                      className="w-6 h-6 flex items-center justify-center rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 flex-shrink-0"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style={{ width: 13, height: 13 }}>
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>

                  {/* 滚动区 */}
                  <div className="flex-1 overflow-y-auto p-5 space-y-4">
                    {/* 状态 + 进度 */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${badge.cls}`}>
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: badge.dot }} />{badge.label}
                      </span>
                      {subTasks.length > 0 && (
                        <span className="text-xs font-semibold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-full">{detailProgress.label} 关键任务</span>
                      )}
                    </div>

                    {/* 基本信息 */}
                    <div className="rounded-xl border overflow-hidden" style={{ borderColor: '#E9EFF6' }}>
                      {([
                        { label: '所属项目', value: selectedTaskProject?.name ?? getProjectDisplayName(resolvedTaskProjects, selectedTask) },
                        { label: '项目负责人', value: projectPeopleText(selectedTaskProject?.owners ?? selectedTask.owner) },
                        { label: '统筹人', value: projectPeopleText(selectedTaskProject?.coordinator ?? selectedTask.coordinator) },
                        { label: '协助人', value: projectPeopleText(selectedTask.collaborators) },
                        { label: '计划时间', value: shortDate(selectedTask.plan_time) },
                      ] as { label: string; value?: string }[]).filter((r) => r.value).map((row) => (
                        <div key={row.label} className="flex gap-3 px-4 py-2.5 border-b last:border-b-0" style={{ borderColor: '#F1F5F9' }}>
                          <span className="w-16 shrink-0 text-xs font-semibold text-slate-400">{row.label}</span>
                          <span className="flex-1 text-xs font-semibold text-slate-700">{row.value || '—'}</span>
                        </div>
                      ))}
                    </div>

                    {/* 完成标准 */}
                    {selectedTask.completion_standard && (
                      <div>
                        <p className="text-xs font-bold text-slate-500 mb-1.5">完成标准</p>
                        <div className="rounded-lg bg-indigo-50 border border-indigo-100 px-3 py-2.5 text-xs text-indigo-900 leading-relaxed">{selectedTask.completion_standard}</div>
                      </div>
                    )}

                    {/* 关键成果 */}
                    {selectedTask.key_achievement && (
                      <div>
                        <p className="text-xs font-bold text-slate-500 mb-1.5">关键成果</p>
                        <div className="rounded-lg bg-amber-50 border border-amber-100 px-3 py-2.5 text-xs text-amber-900 leading-relaxed">{selectedTask.key_achievement}</div>
                      </div>
                    )}

                    {/* 当前问题 */}
                    {selectedTask.problem_note && (
                      <div>
                        <p className="text-xs font-bold text-slate-500 mb-1.5">当前问题</p>
                        <div className="rounded-lg bg-red-50 border border-red-100 px-3 py-2.5 text-xs text-red-900 leading-relaxed">{selectedTask.problem_note}</div>
                      </div>
                    )}

                    {/* 最近汇报 */}
                    {taskUpdates.length > 0 && (
                      <div>
                        <p className="text-xs font-bold text-slate-500 mb-1.5">最近汇报（{taskUpdates.length}）</p>
                        <div className="space-y-1.5">
                          {taskUpdates.map((u) => (
                            <div key={u.id} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                              <div className="flex items-center gap-1.5 mb-1">
                                <span className="text-xs text-slate-500 font-semibold">{u.submitter}</span>
                                <span className="text-xs text-slate-400">{u.created_at}</span>
                              </div>
                              <p className="text-xs text-slate-700 leading-relaxed">{u.transcript_text}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 关键任务列表 */}
                    {subTasks.length > 0 && (
                      <div>
                        <p className="text-xs font-bold text-slate-500 mb-1.5">关键任务（{subTasks.length}）</p>
                        <div className="space-y-1.5">
                          {subTasks.map((sub) => {
                            const subBadge = getBadge(sub.status)
                            return (
                              <div key={sub.id} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 flex items-start gap-2">
                                <div className="flex-1 min-w-0">
                                  <p className="text-xs font-semibold text-slate-700 leading-snug truncate">{sub.title}</p>
                                  <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                                    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs font-semibold ${subBadge.cls}`}>
                                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: subBadge.dot }} />{subBadge.label}
                                    </span>
                                    {sub.assignee && <span className="text-xs text-slate-400">{sub.assignee}</span>}
                                  </div>
                                </div>
                                <button
                                  onClick={() => openSubDetail(sub)}
                                  className="flex-shrink-0 text-xs text-indigo-500 hover:text-indigo-700 font-semibold px-2 py-1 rounded-md hover:bg-indigo-50 transition-colors"
                                >
                                  详情
                                </button>
                                {canAssignSelectedTask && (
                                  <button
                                    onClick={() => openSubTaskAssignment(selectedTask, sub)}
                                    className="flex-shrink-0 text-xs text-slate-500 hover:text-indigo-700 font-semibold px-2 py-1 rounded-md hover:bg-indigo-50 transition-colors"
                                  >
                                    编辑关键任务
                                  </button>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* 进展提交表单（progressOpen 控制） */}
                  {progressOpen && !selectedTaskArchived && (
                    <div className="border-t px-4 py-3 space-y-3 flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
                      <p className="text-xs font-bold text-slate-500">更新工作进展</p>
                      <textarea
                        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:border-blue-400"
                        rows={3}
                        placeholder="描述本次完成了什么、下一步计划、遇到的问题..."
                        value={progressText}
                        onChange={(e) => setProgressText(e.target.value)}
                        disabled={progressSubmitState !== 'idle'}
                      />
                      <div className="flex items-center justify-between">
                        <button
                          onClick={() => { setProgressOpen(false); setProgressText(''); setProgressSubmitState('idle') }}
                          className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-500 text-xs font-semibold hover:bg-slate-50"
                          disabled={progressSubmitState === 'submitting'}
                        >
                          取消
                        </button>
                        {progressSubmitState === 'done' ? (
                          <p className="text-xs font-semibold text-emerald-600 bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-lg">
                            已提交至 AI 确认中心，负责人确认后将显示在工作推进表。
                          </p>
                        ) : (
                          <button
                            onClick={handleProgressSubmit}
                            disabled={!progressText.trim() || progressSubmitState === 'submitting'}
                            className="px-4 py-1.5 rounded-lg text-white text-xs font-bold disabled:opacity-50"
                            style={{ background: 'linear-gradient(135deg,#0284C7,#0EA5E9)' }}
                          >
                            {progressSubmitState === 'submitting' ? '提交中…' : '提交进展'}
                          </button>
                        )}
                      </div>
                    </div>
                  )}

                  {/* 操作栏 */}
                  {!selectedTaskArchived && (
                    <div className="border-t px-4 py-3 flex gap-2 flex-wrap flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
                      <button onClick={() => { setFormTask(selectedTask); setFormOpen(true) }} className="px-3 py-1.5 rounded-lg text-white text-xs font-bold" style={{ background: '#0284C7' }}>编辑</button>
                      <button onClick={() => setProgressOpen(true)} className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-700 text-xs font-semibold">更新进展</button>
                      {canAssignSelectedTask && <button onClick={() => openSubTaskAssignment(selectedTask)} className="px-3 py-1.5 rounded-lg border border-indigo-200 text-indigo-600 text-xs font-semibold disabled:opacity-50">新增关键任务</button>}
                      {canOwn && !selectedTaskActive && (
                        <span className="text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-1.5">
                          项目尚未进入执行阶段，暂不能维护执行期关键任务。
                        </span>
                      )}
                      {canTrashTask && <button onClick={() => handleDelete(selectedTask)} className="px-3 py-1.5 rounded-lg border border-red-200 text-red-500 text-xs font-semibold">删除</button>}
                    </div>
                  )}
                </div>
              )
            }

            if (projectDetail) {
              const projectTasks = groupedRows.find((row) => row.key === selectedProjectKey)?.tasks ?? []
              return (
                <div className="h-full flex flex-col">
                  <div className="px-5 py-4 border-b" style={{ borderColor: '#E9EFF6' }}>
                    <p className="text-xs font-semibold text-slate-400">项目详情</p>
                    <h2 className="text-lg font-bold text-slate-900 mt-1">{projectDetail.name}</h2>
                  </div>
                  <div className="p-5 space-y-5">
                    <div className="rounded-xl border overflow-hidden" style={{ borderColor: '#E9EFF6' }}>
                      {[
                        { label: '项目负责人', value: projectPeopleText(projectDetail.owners) },
                        { label: '统筹人', value: projectPeopleText(projectDetail.coordinator) },
                        { label: '协同成员', value: projectPeopleText(projectDetail.collaborators) },
                        { label: '重点工作', value: `${projectTasks.length} 个` },
                      ].map((row) => (
                        <div key={row.label} className="flex gap-3 px-4 py-3 border-b last:border-b-0" style={{ borderColor: '#F1F5F9' }}>
                          <span className="w-16 shrink-0 text-xs font-semibold text-slate-400">{row.label}</span>
                          <span className="flex-1 text-sm font-semibold text-slate-700 leading-relaxed">{row.value || '—'}</span>
                        </div>
                      ))}
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-500 mb-2">重点工作概览</p>
                      <div className="space-y-2">
                        {projectTasks.slice(0, 6).map((task) => (
                          <button key={task.id} onClick={() => openDetail(task)} className="w-full text-left rounded-xl border border-slate-100 bg-slate-50 px-3 py-2 hover:bg-blue-50">
                            <p className="text-sm font-semibold text-slate-700 truncate">{task.key_task}</p>
                            <p className="text-xs text-slate-400 mt-0.5">{task.status || '—'} · {shortDate(task.plan_time)}</p>
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )
            }

            return (
              <div className="h-full flex items-center justify-center p-8 text-center">
                <div>
                  <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-500 flex items-center justify-center mx-auto mb-3">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style={{ width: 22, height: 22 }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5h6M9 12h6M9 19h6M5 5h.01M5 12h.01M5 19h.01" /></svg>
                  </div>
                  <p className="text-sm font-bold text-slate-700">选择左侧项目、重点工作或关键任务查看详情</p>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">树状表格负责浏览层级，右侧面板负责查看和处理详情。</p>
                </div>
              </div>
            )
          })()}
        </aside>}

      </div>
    </div>
  )
}

// ─── 大纲导入弹窗 ────────────────────────────────────────────────────────────

function OutlineImportModal({ defaultProjectId, projects, onCreated, onClose }: {
  defaultProjectId: number
  projects: { id: number; name: string }[]
  onCreated: (tasks: TaskItem[]) => void
  onClose: () => void
}) {
  const [step, setStep] = useState<'input' | 'preview'>('input')
  const [selectedProjectId, setSelectedProjectId] = useState<number>(defaultProjectId)
  const [aiSuggestion, setAiSuggestion] = useState<{ name: string; guess: string; confidence: number } | null>(null)
  const [outlineText, setOutlineText] = useState('')
  const [extracting, setExtracting] = useState(false)
  const [drafts, setDrafts] = useState<TaskDraft[]>([])
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [provider, setProvider] = useState<string | null>(null)
  const [providerLabel, setProviderLabel] = useState('')
  const [noEngine, setNoEngine] = useState(false)

  useEffect(() => {
    apiGet<{ provider: string; display_name: string }[]>('/api/llm-config/available').then((list) => {
      if (list.length === 0) { setNoEngine(true); return }
      setProvider(list[0].provider)
      setProviderLabel(list[0].display_name)
    }).catch(() => setNoEngine(true))
  }, [])

  async function handleExtract() {
    if (!outlineText.trim() || !provider) return
    setExtracting(true)
    setError('')
    setAiSuggestion(null)
    try {
      const res = await extractTasksFromOutline({
        project_id: selectedProjectId,
        text: outlineText.trim(),
        llm_provider: provider,
        project_names: projects.map((p) => p.name),
      })
      if (!res.tasks.length) { setError('AI 未能从文本中提取到任务，请补充更多细节后重试'); return }
      setDrafts(res.tasks)
      if (res.suggested_project) {
        const matched = projects.find((p) => p.name === res.suggested_project)
        if (matched) {
          setSelectedProjectId(matched.id)
          setAiSuggestion({ name: res.suggested_project, guess: res.project_guess, confidence: res.confidence })
        }
      }
      setStep('preview')
    } catch (e: any) {
      setError(e?.message || 'AI 提取失败，请检查 API Key 配置')
    } finally {
      setExtracting(false)
    }
  }

  async function handleCreate() {
    const valid = drafts.filter((d) => d.key_task.trim())
    if (!valid.length) return
    setCreating(true)
    try {
      const created = await batchCreateTasks({ project_id: selectedProjectId, tasks: valid })
      onCreated(created)
    } catch {
      toast.error('批量创建失败，请重试')
    } finally {
      setCreating(false)
    }
  }

  function updateDraft(i: number, field: keyof TaskDraft, val: string) {
    setDrafts((prev) => prev.map((d, idx) => idx === i ? { ...d, [field]: val } : d))
  }

  function removeDraft(i: number) {
    setDrafts((prev) => prev.filter((_, idx) => idx !== i))
  }

  const inputCls = 'w-full border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:border-blue-400'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(15,23,42,0.45)' }}>
      <div className="bg-white rounded-2xl shadow-2xl flex flex-col" style={{ width: 720, maxWidth: '95vw', maxHeight: '90vh' }}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-base font-bold text-slate-800">从大纲导入重点工作</h2>
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-slate-400">导入至</span>
                <select
                  value={selectedProjectId}
                  onChange={(e) => { setSelectedProjectId(Number(e.target.value)); setAiSuggestion(null) }}
                  className="text-xs border border-indigo-200 rounded-lg px-2 py-1 bg-indigo-50 text-indigo-700 font-semibold focus:outline-none focus:border-indigo-400 cursor-pointer"
                >
                  {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
                {aiSuggestion && (
                  <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: aiSuggestion.confidence >= 0.9 ? '#F0FDF4' : '#FFFBEB', color: aiSuggestion.confidence >= 0.9 ? '#15803D' : '#B45309', border: `1px solid ${aiSuggestion.confidence >= 0.9 ? '#BBF7D0' : '#FDE68A'}` }}>
                    ? AI推断 · {aiSuggestion.confidence >= 0.9 ? '高置信' : '中置信'}
                  </span>
                )}
              </div>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              {step === 'input' ? '粘贴项目大纲、计划文档或任务列表，AI 自动提取' : `已提取 ${drafts.length} 条任务草稿，可逐行编辑后确认创建`}
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400">
            <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {step === 'input' ? (
            <div className="space-y-3">
              {noEngine ? (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-700">
                  <p className="font-semibold mb-1">尚未配置 AI 引擎</p>
                  <p>请前往<strong>系统设置 → 模型配置</strong>填写至少一个 API Key 并启用，再回来使用此功能。</p>
                </div>
              ) : (
                <>
                  {providerLabel && (
                    <p className="text-xs text-slate-400">将使用 <span className="font-semibold text-slate-600">{providerLabel}</span> 提取任务</p>
                  )}
                  <textarea
                    className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:border-blue-400"
                    rows={12}
                    placeholder={"示例：\n1. 知识库AI化 — 负责人：张三，6月底前完成，预期产出：知识问答原型\n2. 顾问作业智能辅助 — 李四负责，Q3完成\n3. 交付流程标准化 …\n\n支持任意格式：Word 粘贴、会议纪要、脑图文字、随手记录均可"}
                    value={outlineText}
                    onChange={(e) => setOutlineText(e.target.value)}
                    disabled={extracting}
                  />
                  {error && <p className="text-xs text-red-500">{error}</p>}
                </>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              {drafts.map((d, i) => (
                <div key={i} className="border border-slate-200 rounded-xl p-3 space-y-2" style={{ background: '#FAFBFD' }}>
                  <div className="flex items-start gap-2">
                    <span className="text-xs font-bold text-slate-400 mt-2 w-5 flex-shrink-0">#{i + 1}</span>
                    <div className="flex-1 grid grid-cols-2 gap-2">
                      <div className="col-span-2">
                        <label className="block text-xs font-semibold text-slate-500 mb-1">重点工作 *</label>
                        <input className={inputCls} value={d.key_task} onChange={(e) => updateDraft(i, 'key_task', e.target.value)} placeholder="任务名称" />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-500 mb-1">负责人</label>
                        <input className={inputCls} value={d.owner} onChange={(e) => updateDraft(i, 'owner', e.target.value)} placeholder="姓名" />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-500 mb-1">统筹人</label>
                        <input className={inputCls} value={d.coordinator} onChange={(e) => updateDraft(i, 'coordinator', e.target.value)} placeholder="姓名" />
                      </div>
                      <div className="col-span-2">
                        <label className="block text-xs font-semibold text-slate-500 mb-1">协作人</label>
                        <input className={inputCls} value={d.collaborators} onChange={(e) => updateDraft(i, 'collaborators', e.target.value)} placeholder="多人用逗号分隔" />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-500 mb-1">计划时间</label>
                        <input className={inputCls} value={d.plan_time} onChange={(e) => updateDraft(i, 'plan_time', e.target.value)} placeholder="2026-06 或 2026-06~2026-09" />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-500 mb-1">状态</label>
                        <select className={inputCls} value={d.status} onChange={(e) => updateDraft(i, 'status', e.target.value)}>
                          {STATUS_OPTIONS.map((s) => <option key={s}>{s}</option>)}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-500 mb-1">期望成果</label>
                        <input className={inputCls} value={d.key_achievement} onChange={(e) => updateDraft(i, 'key_achievement', e.target.value)} placeholder="主要产出物" />
                      </div>
                      <div className="col-span-2">
                        <label className="block text-xs font-semibold text-slate-500 mb-1">完成标准</label>
                        <input className={inputCls} value={d.completion_standard} onChange={(e) => updateDraft(i, 'completion_standard', e.target.value)} placeholder="何为完成" />
                      </div>
                    </div>
                    <button onClick={() => removeDraft(i)} className="mt-1.5 p-1 rounded hover:bg-red-50 text-slate-300 hover:text-red-400 flex-shrink-0">
                      <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                  </div>
                </div>
              ))}
              {drafts.length === 0 && <p className="text-sm text-slate-400 text-center py-6">所有草稿已删除</p>}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t flex items-center justify-between flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
          {step === 'preview' ? (
            <>
              <button onClick={() => setStep('input')} className="px-4 py-2 rounded-lg border border-slate-200 text-slate-600 text-sm font-semibold hover:bg-slate-50">返回修改</button>
              <button
                onClick={handleCreate}
                disabled={creating || drafts.length === 0}
                className="px-5 py-2 rounded-lg text-white text-sm font-bold disabled:opacity-50"
                style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}
              >
                {creating ? '创建中…' : `确认创建 ${drafts.length} 条任务`}
              </button>
            </>
          ) : (
            <>
              <button onClick={onClose} className="px-4 py-2 rounded-lg border border-slate-200 text-slate-600 text-sm font-semibold hover:bg-slate-50">取消</button>
              {!noEngine && (
                <button
                  onClick={handleExtract}
                  disabled={!outlineText.trim() || extracting || !provider}
                  className="px-5 py-2 rounded-lg text-white text-sm font-bold disabled:opacity-50"
                  style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}
                >
                  {extracting ? 'AI 提取中…' : 'AI 提取任务'}
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── 新增/编辑关键任务派发弹窗 ─────────────────────────────────────────────────

const ASSISTING_PERSON_PREFIX = '协助人：'

function splitAssistingPersonFromNotes(raw?: string | null) {
  const lines = String(raw ?? '').split('\n')
  const first = lines[0] ?? ''
  if (!first.startsWith(ASSISTING_PERSON_PREFIX)) return { assistingPerson: '', noteText: String(raw ?? '') }
  return {
    assistingPerson: first.slice(ASSISTING_PERSON_PREFIX.length).trim(),
    noteText: lines.slice(1).join('\n').trim(),
  }
}

function buildNotesWithAssistingPerson(assistingPerson: string, noteText: string) {
  const lines = []
  if (assistingPerson.trim()) lines.push(`${ASSISTING_PERSON_PREFIX}${assistingPerson.trim()}`)
  if (noteText.trim()) lines.push(noteText.trim())
  return lines.join('\n')
}

function uniqueProjectMemberNames(projectMembers: ProjectMember[], currentName?: string | null, extraNames?: string[]) {
  const names = projectMembers.map((member) => member.person_name_snapshot).filter(Boolean)
  if (currentName?.trim()) names.push(currentName.trim())
  extraNames?.forEach((n) => { if (n?.trim()) names.push(n.trim()) })
  return [...new Set(names)]
}

function SubTaskAssignmentModal({ taskId, projectId, editingSubTask, projectMembers, extraNames, onSave, onClose }: {
  taskId: number
  projectId: number | null
  editingSubTask: SubTaskItem | SubTaskDetail | null
  projectMembers: ProjectMember[]
  extraNames?: string[]
  onSave: (st: SubTaskItem) => void
  onClose: () => void
}) {
  const parsedNotes = splitAssistingPersonFromNotes(editingSubTask?.notes)
  const memberNames = uniqueProjectMemberNames(projectMembers, editingSubTask?.assignee, extraNames)
  const [title, setTitle] = useState(editingSubTask?.title ?? '')
  const [assignee, setAssignee] = useState(editingSubTask?.assignee ?? memberNames[0] ?? '')
  const [assistingPerson, setAssistingPerson] = useState(parsedNotes.assistingPerson)
  const [planTime, setPlanTime] = useState(editingSubTask?.plan_time ?? '')
  const [status, setStatus] = useState(editingSubTask?.status ?? '未开始')
  const [criteria, setCriteria] = useState(editingSubTask?.completion_criteria ?? '')
  const [notes, setNotes] = useState(parsedNotes.noteText)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!assignee && memberNames.length > 0) setAssignee(memberNames[0])
  }, [assignee, memberNames])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim() || !assignee.trim()) return
    if (!projectId) return
    const payload: SubTaskPayload = {
      project_id: projectId,
      title: title.trim(),
      assignee: assignee.trim(),
      plan_time: planTime.trim(),
      status,
      completion_criteria: criteria.trim(),
      notes: buildNotesWithAssistingPerson(assistingPerson, notes),
    }
    setSaving(true)
    try {
      const saved = editingSubTask
        ? await updateSubTask(editingSubTask.id, payload)
        : await createSubTask(taskId, payload)
      onSave(saved)
    } catch {
      toast.error(editingSubTask ? '更新失败，请重试' : '创建失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  const inputCls = "w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-400"
  const labelCls = "block text-xs font-semibold text-slate-500 mb-1"

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center" style={{ background: 'rgba(15,23,42,0.4)' }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full overflow-hidden" style={{ maxWidth: 560, maxHeight: '90vh' }}>
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: '#E9EFF6' }}>
          <div>
            <h2 className="text-sm font-bold text-slate-800">{editingSubTask ? '编辑关键任务' : '新增关键任务'}</h2>
            <p className="text-xs text-slate-400 mt-0.5">执行期关键任务派发：责任人与协助人仅来自当前项目成员。</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400">
            <svg style={{ width: 15, height: 15 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="overflow-y-auto px-5 py-4 space-y-4" style={{ maxHeight: 'calc(90vh - 132px)' }}>
          <div>
            <label className={labelCls}>关键任务名称 *</label>
            <input required className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="描述具体要做什么" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>责任人 *</label>
              <select required className={inputCls} value={assignee} onChange={(e) => setAssignee(e.target.value)}>
                <option value="">请选择责任人</option>
                {memberNames.map((name) => <option key={name} value={name}>{name}</option>)}
              </select>
            </div>
            <div>
              <label className={labelCls}>协助人</label>
              <select className={inputCls} value={assistingPerson} onChange={(e) => setAssistingPerson(e.target.value)}>
                <option value="">可不指定</option>
                {memberNames.map((name) => <option key={name} value={name}>{name}</option>)}
              </select>
            </div>
          </div>

          {memberNames.length === 0 && (
            <p className="rounded-lg bg-amber-50 border border-amber-100 text-amber-700 text-xs px-3 py-2">
              暂未加载到项目成员，请确认当前项目已配置成员后再派发关键任务。
            </p>
          )}

          <div>
            <label className={labelCls}>时间段</label>
            <input className={inputCls} value={planTime} onChange={(e) => setPlanTime(e.target.value)} placeholder="如：2026年6月 或 2026年6月~2026年8月" />
          </div>

          <div>
            <label className={labelCls}>当前状态</label>
            <select className={inputCls} value={status} onChange={(e) => setStatus(e.target.value)}>
              {STATUS_OPTIONS.map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>

          <div>
            <label className={labelCls}>备注 / 标准</label>
            <textarea className={inputCls} rows={2} value={criteria} onChange={(e) => setCriteria(e.target.value)} placeholder="可填写完成标准、验收口径或交付说明" />
          </div>

          <div>
            <label className={labelCls}>补充说明</label>
            <textarea className={inputCls} rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="可选；保存到现有备注字段" />
          </div>
        </form>

        <div className="px-5 py-4 border-t flex justify-end gap-3 flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
          <button type="button" onClick={onClose} className="px-4 py-2 rounded-xl border border-slate-200 text-slate-600 text-sm font-semibold hover:bg-slate-50">取消</button>
          <button onClick={handleSubmit as any} disabled={saving || memberNames.length === 0} className="px-5 py-2 rounded-xl text-white text-sm font-bold hover:opacity-90 disabled:opacity-50" style={{ background: 'linear-gradient(135deg,#6366F1,#818CF8)' }}>
            {saving ? '保存中…' : editingSubTask ? '保存关键任务' : '创建关键任务'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── 新增/编辑重点工作弹窗 ────────────────────────────────────────────────────

const YEARS  = [2025, 2026, 2027, 2028]
const MONTHS = [1,2,3,4,5,6,7,8,9,10,11,12]
// 「延期」不再作为可手选状态：延期由计划时间过期且未完成自动计算（isOverdueTask），与 Dashboard 后端逻辑一致。
// 旧数据 status='延期' 仍能在 STATUS_BADGE 正常展示，但用户无法再手动选成「延期」。
const STATUS_OPTIONS = ['未开始','进行中','已完成','暂缓']

function parsePlanTime(val: string) {
  // 支持 "2026年5月~2026年8月" 或 "2026年5月" 或 "2026-06" 或 "5-6月"
  const rangeMatch = val.match(/(\d{4})年(\d{1,2})月[~\-～至到](\d{4})年(\d{1,2})月/)
  if (rangeMatch) return { sy: +rangeMatch[1], sm: +rangeMatch[2], ey: +rangeMatch[3], em: +rangeMatch[4] }
  const singleMatch = val.match(/(\d{4})年(\d{1,2})月/)
  if (singleMatch) return { sy: +singleMatch[1], sm: +singleMatch[2], ey: +singleMatch[1], em: +singleMatch[2] }
  const isoRangeMatch = val.match(/(\d{4})-(\d{2})[~\-～至到](\d{4})-(\d{2})/)
  if (isoRangeMatch) return { sy: +isoRangeMatch[1], sm: +isoRangeMatch[2], ey: +isoRangeMatch[3], em: +isoRangeMatch[4] }
  const isoMatch = val.match(/(\d{4})-(\d{2})/)
  if (isoMatch) return { sy: +isoMatch[1], sm: +isoMatch[2], ey: +isoMatch[1], em: +isoMatch[2] }
  return { sy: 2026, sm: new Date().getMonth() + 1, ey: 2026, em: new Date().getMonth() + 1 }
}

function isPlanOverdue(planTime: string): boolean {
  if (!planTime) return false
  const { ey, em } = parsePlanTime(planTime)
  const now = new Date()
  // ey*12+em < 当前年*12+当前月（注意 getMonth() 从 0 开始）
  return ey * 12 + em < now.getFullYear() * 12 + (now.getMonth() + 1)
}

function formatPlanTime(sy: number, sm: number, ey: number, em: number) {
  if (sy === ey && sm === em) return `${sy}年${sm}月`
  return `${sy}年${sm}月~${ey}年${em}月`
}

function TaskFormModal({ task, projects, onSave, onClose }: {
  task: TaskItem | null
  projects: Project[]
  onSave: (p: TaskPayload) => void
  onClose: () => void
}) {
  const parsed = parsePlanTime(task?.plan_time ?? '')
  const initialProject = projectForTask(projects, task) ?? projects[0] ?? null
  const [form, setForm] = useState<TaskPayload>({
    project_id: initialProject?.id ?? projects[0]?.id ?? 0,
    key_task:        task?.key_task ?? '',
    key_achievement: task?.key_achievement ?? '',
    completion_standard: task?.completion_standard ?? '',
    owner:           task?.owner ?? '',
    collaborators:   task?.collaborators ?? '',
    plan_time:       task?.plan_time ?? '',
    status:          task?.status ?? '未开始',
    problem_note:    task?.problem_note ?? '',
  })
  const [sy, setSy] = useState(parsed.sy)
  const [sm, setSm] = useState(parsed.sm)
  const [ey, setEy] = useState(parsed.ey)
  const [em, setEm] = useState(parsed.em)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    onSave({ ...form, plan_time: formatPlanTime(sy, sm, ey, em) })
  }

  const inputCls = "w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
  const selectCls = "border border-slate-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none focus:border-blue-400 cursor-pointer"
  const labelCls = "block text-xs font-semibold text-slate-500 mb-1"

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(15,23,42,0.4)' }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full overflow-hidden" style={{ maxWidth: 640, maxHeight: '90vh' }}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: '#E9EFF6' }}>
          <h2 className="text-base font-bold text-slate-800">{task ? '编辑重点工作' : '新增重点工作'}</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400">
            <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="overflow-y-auto px-6 py-5 space-y-4" style={{ maxHeight: 'calc(90vh - 130px)' }}>
          {/* 专项 */}
          <div>
            <label className={labelCls}>专项 *</label>
            <select
              className={inputCls}
              value={form.project_id ?? ''}
              onChange={e => {
                const nextProjectId = e.target.value ? Number(e.target.value) : (projects[0]?.id ?? form.project_id)
                setForm((f) => ({
                  ...f,
                  project_id: nextProjectId,
                }))
              }}
            >
              {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>

          {/* 重点工作 */}
          <div>
            <label className={labelCls}>重点工作 *</label>
            <input required className={inputCls} value={form.key_task} onChange={e => setForm(f => ({ ...f, key_task: e.target.value }))} placeholder="描述本任务的核心工作内容" />
          </div>

          {/* 关键成果 */}
          <div>
            <label className={labelCls}>关键成果</label>
            <input className={inputCls} value={form.key_achievement} onChange={e => setForm(f => ({ ...f, key_achievement: e.target.value }))} placeholder="如：方案、SOP、报告..." />
          </div>

          {/* 完成标准 */}
          <div>
            <label className={labelCls}>完成标准</label>
            <textarea className={inputCls} rows={2} value={form.completion_standard} onChange={e => setForm(f => ({ ...f, completion_standard: e.target.value }))} placeholder="如何判断该任务已完成" />
          </div>

          {/* 计划完成时间 */}
          <div>
            <label className={labelCls}>计划时间段</label>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-slate-500">从</span>
              <select className={selectCls} value={sy} onChange={e => setSy(+e.target.value)}>
                {YEARS.map(y => <option key={y}>{y}</option>)}
              </select>
              <span className="text-xs text-slate-500">年</span>
              <select className={selectCls} value={sm} onChange={e => setSm(+e.target.value)}>
                {MONTHS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
              <span className="text-xs text-slate-500">月 &nbsp; 至</span>
              <select className={selectCls} value={ey} onChange={e => setEy(+e.target.value)}>
                {YEARS.map(y => <option key={y}>{y}</option>)}
              </select>
              <span className="text-xs text-slate-500">年</span>
              <select className={selectCls} value={em} onChange={e => setEm(+e.target.value)}>
                {MONTHS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
              <span className="text-xs text-slate-500">月</span>
            </div>
            <p className="text-xs text-slate-400 mt-1">预览：{formatPlanTime(sy, sm, ey, em)}</p>
          </div>

          <div>
            <label className={labelCls}>当前状态</label>
            <select className={inputCls} value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
              {STATUS_OPTIONS.map(s => <option key={s}>{s}</option>)}
            </select>
            <p className="text-xs text-slate-400 mt-1">已完成状态由关键任务完成情况汇总，直接保存已完成会由后端校验。</p>
          </div>

          {/* 问题与协调 */}
          <div>
            <label className={labelCls}>问题与协调</label>
            <textarea className={inputCls} rows={2} value={form.problem_note} onChange={e => setForm(f => ({ ...f, problem_note: e.target.value }))} placeholder="当前存在的阻碍或需协调的事项" />
          </div>
        </form>

        {/* Footer */}
        <div className="px-6 py-4 border-t flex justify-end gap-3 flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
          <button type="button" onClick={onClose} className="px-5 py-2 rounded-xl border border-slate-200 text-slate-600 text-sm font-semibold hover:bg-slate-50">取消</button>
          <button type="submit" form="" onClick={handleSubmit as any} className="px-5 py-2 rounded-xl text-white text-sm font-bold hover:opacity-90" style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}>
            {task ? '保存修改' : '创建任务'}
          </button>
        </div>
      </div>
    </div>
  )
}
