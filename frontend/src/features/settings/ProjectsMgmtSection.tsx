import { createPortal } from 'react-dom'
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useProject } from '../../context/ProjectContext'
import {
  getProjects,
  getProjectMembers,
  createProject,
  patchProject,
  archiveProject,
  approveProject,
  dispatchProject,
  returnProject,
  addProjectMember,
  removeProjectMember,
  batchImportProjects,
} from '../../api/projects'
import type { BatchImportRow, ProjectProfilePayload } from '../../api/projects'
import type { Person, Project, ProjectMember, TaskItem } from '../../types'
import type { SubTaskWithParent } from '../../api/subtasks'
import { fetchPeople } from '../../api/people'
import { fetchTasks } from '../../api/tasks'
import { fetchSubtasksByProject } from '../../api/subtasks'
import { fmtPlanTime } from '../../utils/time'
import { toast } from '../../utils/toast'
import { canManageProjects } from '../../domain/permissions'
import {
  getProjectPrimaryStatus,
  getProjectStatusBadge,
  isProjectArchived,
} from '../../domain/projectLifecycleStatus'
import { getProjectRoleLabel } from '../../domain/roleLabels'
import { SectionTitle } from './settingsShared'
import { NewProjectForm, ProjectInitModal, type TeamMap } from './ProjectInitModal'
import { OwnerSubmitModal } from './OwnerSubmitModal'
import { getPickerPosition } from './projectPickerPosition.js'

// ── 常量 ──────────────────────────────────────────────────────

const EMPTY_TEAM: TeamMap = { owner: [], coordinator: [], member: [], project_ceo: [] }

const EMPTY_NEW_FORM: NewProjectForm = {
  name: '',
  project_type: '博维内部项目',
  client_name: '',
  background: '',
  objectives: '',
  expected_outcomes: '',
  start_date: '',
  end_date: '',
}

const STATUS_TABS: { key: string; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'draft', label: '草稿' },
  { key: 'dispatched', label: '已派发' },
  { key: 'pending_review', label: '待审核' },
  { key: 'returned', label: '已退回' },
  { key: 'active', label: '进行中' },
  { key: 'archived', label: '已归档' },
]

const STAGE_DESCRIPTIONS: Record<string, string> = {
  draft: '项目草稿，等待配置企业教练、负责人和初始成员。',
  dispatched: '项目已下发，等待负责人完善立项信息和推进表草案。',
  pending_review: '负责人已提交，等待企业教练审核立项和推进表草案。',
  returned: '企业教练已退回，等待负责人修改立项信息和推进表草案。',
  active: '项目已确立，工作推进表初版已形成，正在执行。',
  archived: '项目已归档，仅可查看。',
}

const IMPORT_COL_MAP: Record<string, keyof BatchImportRow> = {
  项目: 'project_name',
  阶段: 'project_name',
  关键任务: 'key_task',
  关键成果: 'key_achievement',
  完成标准: 'completion_standard',
  统筹人: 'coordinator',
  负责人: 'owner',
  协同: 'collaborators',
  成员: 'collaborators',
  计划时间: 'plan_time',
  当前状态: 'status',
  状态: 'status',
  问题与需协调事项: 'issue',
  问题: 'issue',
}

// ── 辅助函数 ──────────────────────────────────────────────────

function buildProjectForm(project: Project): NewProjectForm {
  return {
    name: project.name ?? '',
    project_type: project.project_type?.trim() || '博维内部项目',
    client_name: project.client_name?.trim() || '',
    background: project.background?.trim() || '',
    objectives: project.objectives?.trim() || '',
    expected_outcomes: project.expected_outcomes?.trim() || '',
    start_date: project.start_date ?? '',
    end_date: project.end_date ?? '',
  }
}

function buildTeamMapFromMembers(projectMembers: ProjectMember[]): TeamMap {
  const team: TeamMap = { ...EMPTY_TEAM }
  projectMembers.forEach((member) => {
    const role = member.role as keyof TeamMap
    if (!(role in team)) return
    if (!team[role].includes(member.person_id)) {
      team[role] = [...team[role], member.person_id]
    }
  })
  return team
}

function getMemberNamesByRole(projectMembers: ProjectMember[], role: string): string[] {
  return projectMembers.filter((m) => m.role === role).map((m) => m.person_name_snapshot).filter(Boolean)
}

function summarizeProjectRoleLine(projectMembers: ProjectMember[], project: Project) {
  const ceoNames = getMemberNamesByRole(projectMembers, 'project_ceo')
  const ownerNames = getMemberNamesByRole(projectMembers, 'owner')
  const coordinatorNames = getMemberNamesByRole(projectMembers, 'coordinator')
  const memberNames = getMemberNamesByRole(projectMembers, 'member')
  return {
    ceoText: ceoNames.length > 0 ? ceoNames.join('、') : '未配置',
    ownerText: ownerNames.length > 0 ? ownerNames.join('、') : project.owners?.join('、') || '未配置',
    coordinatorText: coordinatorNames.length > 0 ? coordinatorNames.join('、') : project.coordinator?.trim() || '未配置',
    memberText: memberNames.length > 0 ? `${memberNames.length}人` : `${project.collaborators?.length ?? 0}人`,
  }
}

function splitPlanTime(planTime?: string): { start: string; end: string } {
  if (!planTime?.trim()) return { start: '—', end: '—' }
  const s = planTime.trim()
  for (const sep of ['~', '～', '至', '→', ' - ']) {
    const idx = s.indexOf(sep)
    if (idx > 0) {
      const start = s.slice(0, idx).trim()
      const end = s.slice(idx + sep.length).trim()
      if (start && end) return { start, end }
    }
  }
  return { start: s, end: '—' }
}

function formatPlanTimeShort(startDate?: string, endDate?: string): string {
  if (!startDate && !endDate) return '未填写'
  const s = startDate ? fmtPlanTime(startDate) : '?'
  const e = endDate ? fmtPlanTime(endDate) : '?'
  return `${s} → ${e}`
}

type DraftSummary = {
  objectives: number
  taskCount: number
  subtaskCount: number
  ownerConfigured: number
  planConfigured: number
  taskTotal: number
}

function getDraftSummary(tasks: TaskItem[], subtasks: SubTaskWithParent[], project: Project): DraftSummary {
  return {
    objectives: project.objectives?.trim() ? 1 : 0,
    taskCount: tasks.length,
    subtaskCount: subtasks.length,
    ownerConfigured: subtasks.filter((s) => (s.assignee ?? '').trim()).length,
    planConfigured: subtasks.filter((s) => (s.plan_time ?? '').trim()).length,
    taskTotal: subtasks.length,
  }
}

type DraftRow = {
  objective: string
  keyTask: string
  standard: string
  seq: string
  subTask: string
  assignee: string
  planStart: string
  planEnd: string
  collaborator: string
  note: string
  isTaskOnly: boolean
}

function buildDraftRows(tasks: TaskItem[], subtasks: SubTaskWithParent[], project: Project): DraftRow[] {
  const objText = project.objectives?.trim()
  const objective = objText ? (objText.length > 10 ? objText.slice(0, 10) + '…' : objText) : '—'
  const rows: DraftRow[] = []
  for (const task of tasks) {
    const taskSubs = subtasks.filter((s) => s.parent_task_id === task.id || s.task_id === task.id)
    const standard = task.completion_standard?.trim() || '—'
    const collaborator = task.collaborators?.trim() || '—'
    if (taskSubs.length === 0) {
      const { start, end } = splitPlanTime(task.plan_time)
      rows.push({
        objective, keyTask: task.key_task || '—', standard, seq: '—',
        subTask: '关键任务待补充', assignee: task.owner?.trim() || '—',
        planStart: start, planEnd: end, collaborator, note: '—', isTaskOnly: true,
      })
    } else {
      taskSubs.forEach((sub, idx) => {
        const { start, end } = splitPlanTime(sub.plan_time)
        rows.push({
          objective, keyTask: task.key_task || '—', standard, seq: String(idx + 1),
          subTask: sub.title || '—', assignee: sub.assignee?.trim() || '—',
          planStart: start, planEnd: end, collaborator, note: sub.notes?.trim() || '—', isTaskOnly: false,
        })
      })
    }
  }
  return rows
}

type MainAction = { label: string; type: 'dispatch' | 'ownerSubmit' | 'approve' | 'viewDetail' }

function getMainAction(
  status: string,
  isSuperAdmin: boolean,
  isCompanyCeo: boolean,
  isRealProjectCeo: boolean,
  isRealOwner: boolean,
): MainAction {
  switch (status) {
    case 'draft':
      return (isSuperAdmin || isCompanyCeo)
        ? { label: '下发项目', type: 'dispatch' }
        : { label: '查看档案', type: 'viewDetail' }
    case 'dispatched':
      return isRealOwner
        ? { label: '完善立项信息', type: 'ownerSubmit' }
        : { label: '查看档案', type: 'viewDetail' }
    case 'pending_review':
      return (isRealProjectCeo || isSuperAdmin)
        ? { label: '审核立项', type: 'approve' }
        : { label: '查看档案', type: 'viewDetail' }
    case 'returned':
      return isRealOwner
        ? { label: '修改立项信息', type: 'ownerSubmit' }
        : { label: '查看档案', type: 'viewDetail' }
    default:
      return { label: '查看档案', type: 'viewDetail' }
  }
}

// ── 主组件 ────────────────────────────────────────────────────

export function ProjectsMgmtSection() {
  const { reloadProjects, currentUser, globalUserRoles } = useProject()
  const [projects, setProjects] = useState<Project[]>([])
  const [people, setPeople] = useState<Person[]>([])
  const [loading, setLoading] = useState(true)
  const [members, setMembers] = useState<Record<number, ProjectMember[]>>({})

  // 状态 tabs + 搜索
  const [activeTab, setActiveTab] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')

  // 右侧详情面板
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)

  // 推进表雏形数据
  const [projectTasksMap, setProjectTasksMap] = useState<Record<number, TaskItem[]>>({})
  const [projectSubtasksMap, setProjectSubtasksMap] = useState<Record<number, SubTaskWithParent[]>>({})

  // 新建项目
  const [showNew, setShowNew] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newForm, setNewForm] = useState<NewProjectForm>(EMPTY_NEW_FORM)
  const [newTeam, setNewTeam] = useState<TeamMap>({ ...EMPTY_TEAM })

  // 编辑项目
  const [showEdit, setShowEdit] = useState(false)
  const [editProjectId, setEditProjectId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<NewProjectForm>(EMPTY_NEW_FORM)
  const [editTeam, setEditTeam] = useState<TeamMap>({ ...EMPTY_TEAM })
  const [editingProject, setEditingProject] = useState(false)

  // 下发
  const [dispatchingId, setDispatchingId] = useState<number | null>(null)

  // 审核
  const [approveModal, setApproveModal] = useState<{ pid: number; name: string } | null>(null)
  const [approveForm, setApproveForm] = useState<ProjectProfilePayload>({})
  const [approveLoading, setApproveLoading] = useState(false)

  // 负责人完善立项
  const [ownerFillProject, setOwnerFillProject] = useState<Project | null>(null)

  // 批量导入
  const [importOpen, setImportOpen] = useState(false)
  const [importText, setImportText] = useState('')
  const [importRows, setImportRows] = useState<BatchImportRow[]>([])
  const [importing, setImporting] = useState(false)

  // 更多菜单
  const [menuState, setMenuState] = useState<{ pid: number; anchorEl: HTMLButtonElement } | null>(null)

  // ── 初始加载 ──
  useEffect(() => {
    let cancelled = false
    async function loadInitialData() {
      try {
        const [projectRows, peopleRows] = await Promise.all([getProjects(true), fetchPeople()])
        if (cancelled) return
        setProjects(projectRows)
        setPeople(peopleRows)
        const memberResults = await Promise.allSettled(
          projectRows.map(async (p) => [p.id, await getProjectMembers(p.id)] as const),
        )
        if (cancelled) return
        const nextMembers: Record<number, ProjectMember[]> = {}
        memberResults.forEach((r) => { if (r.status === 'fulfilled') nextMembers[r.value[0]] = r.value[1] })
        setMembers(nextMembers)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void loadInitialData()
    return () => { cancelled = true }
  }, [])

  // ── 加载推进表雏形数据（tasks + subtasks）──
  useEffect(() => {
    let cancelled = false
    Promise.allSettled(
      projects.map(async (p) => {
        const [tasks, subtasks] = await Promise.all([
          fetchTasks(p.id).catch(() => [] as TaskItem[]),
          fetchSubtasksByProject(p.id).catch(() => [] as SubTaskWithParent[]),
        ])
        return { pid: p.id, tasks, subtasks }
      }),
    ).then((results) => {
      if (cancelled) return
      const nextTasks: Record<number, TaskItem[]> = {}
      const nextSubs: Record<number, SubTaskWithParent[]> = {}
      results.forEach((r) => {
        if (r.status === 'fulfilled') {
          nextTasks[r.value.pid] = r.value.tasks
          nextSubs[r.value.pid] = r.value.subtasks
        }
      })
      setProjectTasksMap(nextTasks)
      setProjectSubtasksMap(nextSubs)
    })
    return () => { cancelled = true }
  }, [projects])

  // ── 角色化视图判定 ──
  const isOwnerView =
    !currentUser?.is_tech_admin && !currentUser?.is_ceo
    && !globalUserRoles.includes('project_ceo') && globalUserRoles.includes('owner')
  const isProjectCeoView =
    !currentUser?.is_tech_admin && !currentUser?.is_ceo
    && globalUserRoles.includes('project_ceo')

  const isFullAdmin = Boolean(currentUser?.is_tech_admin || currentUser?.is_ceo)
  const canManage = canManageProjects(currentUser, globalUserRoles)
  const myPersonId = currentUser?.person_id

  // ── 角色过滤后的项目（不含 tab/search 过滤）──
  const roleFilteredProjects = useMemo(() => {
    let list = projects
    if (isOwnerView) list = list.filter((p) => p.user_roles?.includes('owner'))
    else if (isProjectCeoView) list = list.filter((p) => p.user_roles?.includes('project_ceo'))
    return list
  }, [projects, isOwnerView, isProjectCeoView])

  // ── 状态 tab 数量 ──
  const tabCounts = useMemo(() => {
    const counts: Record<string, number> = { all: roleFilteredProjects.length }
    for (const p of roleFilteredProjects) {
      const s = getProjectPrimaryStatus(p)
      counts[s] = (counts[s] ?? 0) + 1
    }
    return counts
  }, [roleFilteredProjects])

  // ── tab + 搜索过滤 ──
  const filteredProjects = useMemo(() => {
    let list = roleFilteredProjects
    if (activeTab !== 'all') list = list.filter((p) => getProjectPrimaryStatus(p) === activeTab)
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase()
      list = list.filter((p) => p.name.toLowerCase().includes(q))
    }
    return list
  }, [roleFilteredProjects, activeTab, searchQuery])

  const selectedProject = selectedProjectId != null
    ? projects.find((p) => p.id === selectedProjectId) ?? null
    : null
  const approveProjectRow = approveModal
    ? projects.find((p) => p.id === approveModal.pid) ?? null
    : null
  const approveTasks = approveModal ? projectTasksMap[approveModal.pid] ?? [] : []
  const approveSubtasks = approveModal ? projectSubtasksMap[approveModal.pid] ?? [] : []
  const approveDraftSummary = approveProjectRow
    ? getDraftSummary(approveTasks, approveSubtasks, approveProjectRow)
    : { objectives: 0, taskCount: 0, subtaskCount: 0, ownerConfigured: 0, planConfigured: 0, taskTotal: 0 }
  const approveDraftRows = approveProjectRow
    ? buildDraftRows(approveTasks, approveSubtasks, approveProjectRow)
    : []

  // ── Handlers ──

  function resetNewForm() {
    setNewForm(EMPTY_NEW_FORM)
    setNewTeam({ ...EMPTY_TEAM })
  }

  async function handleCreate() {
    const name = newForm.name.trim()
    if (!name) return
    if (newForm.project_type === '博维-客户项目' && !newForm.client_name.trim()) {
      toast.warning('客户项目需要填写客户名称'); return
    }
    if (projects.some((p) => p.name === name)) {
      toast.warning(`项目"${name}"已存在`); return
    }
    setCreating(true)
    try {
      const project = await createProject({
        name,
        project_type: newForm.project_type,
        client_name: newForm.client_name.trim(),
        background: newForm.background.trim(),
        objectives: newForm.objectives.trim(),
        expected_outcomes: newForm.expected_outcomes.trim(),
        start_date: newForm.start_date,
        end_date: newForm.end_date,
        owner_ids: newTeam.owner,
        coordinator_ids: newTeam.coordinator,
        member_ids: newTeam.member,
        project_ceo_ids: newTeam.project_ceo,
      })
      setProjects((prev) => [...prev, project])
      reloadProjects()
      resetNewForm()
      setShowNew(false)
      toast.success(`项目"${name}"已立项`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '创建失败')
    } finally {
      setCreating(false)
    }
  }

  async function openProjectEditor(project: Project) {
    setMenuState(null)
    setShowNew(false)
    setShowEdit(true)
    setEditProjectId(project.id)
    setEditForm(buildProjectForm(project))
    const pm = members[project.id] ?? (await getProjectMembers(project.id).catch(() => []))
    if (!members[project.id] && pm.length > 0) setMembers((prev) => ({ ...prev, [project.id]: pm }))
    setEditTeam(buildTeamMapFromMembers(pm))
  }

  function closeProjectEditor() {
    setShowEdit(false)
    setEditProjectId(null)
    setEditForm(EMPTY_NEW_FORM)
    setEditTeam({ ...EMPTY_TEAM })
  }

  async function syncProjectMembers(projectId: number, nextTeam: TeamMap) {
    const currentMembers = members[projectId] ?? (await getProjectMembers(projectId).catch(() => []))
    const currentByRole = new Map<string, ProjectMember[]>()
    currentMembers.forEach((m) => {
      const list = currentByRole.get(m.role) ?? []
      list.push(m); currentByRole.set(m.role, list)
    })
    for (const [role, currentList] of currentByRole) {
      const nextIds = new Set(nextTeam[role as keyof TeamMap] ?? [])
      await Promise.all(
        currentList.filter((m) => !nextIds.has(m.person_id)).map((m) => removeProjectMember(projectId, m.id)),
      )
    }
    const refreshed = await getProjectMembers(projectId)
    const refreshedByRole = new Map<string, Set<number>>()
    refreshed.forEach((m) => {
      const set = refreshedByRole.get(m.role) ?? new Set<number>()
      set.add(m.person_id); refreshedByRole.set(m.role, set)
    })
    for (const role of Object.keys(nextTeam) as Array<keyof TeamMap>) {
      for (const personId of nextTeam[role]) {
        if (!(refreshedByRole.get(role)?.has(personId) ?? false)) {
          const member = await addProjectMember(projectId, { person_id: personId, role })
          refreshed.push(member)
          const set = refreshedByRole.get(role) ?? new Set<number>()
          set.add(personId); refreshedByRole.set(role, set)
        }
      }
    }
    setMembers((prev) => ({ ...prev, [projectId]: refreshed }))
    return refreshed
  }

  async function handleSaveProjectEdit() {
    if (editProjectId === null) return
    const name = editForm.name.trim()
    if (!name) { toast.warning('项目名称不能为空'); return }
    if (editForm.project_type === '博维-客户项目' && !editForm.client_name.trim()) {
      toast.warning('客户项目需要填写客户名称'); return
    }
    setEditingProject(true)
    try {
      const updated = await patchProject(editProjectId, {
        name,
        project_type: editForm.project_type,
        client_name: editForm.client_name.trim(),
        background: editForm.background.trim(),
        objectives: editForm.objectives.trim(),
        expected_outcomes: editForm.expected_outcomes.trim(),
        start_date: editForm.start_date,
        end_date: editForm.end_date,
      })
      setProjects((prev) => prev.map((p) => (p.id === editProjectId ? { ...p, ...updated } : p)))
      await syncProjectMembers(editProjectId, editTeam)
      reloadProjects()
      closeProjectEditor()
      toast.success('项目已保存')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '保存失败')
    } finally {
      setEditingProject(false)
    }
  }

  async function handleDispatch(pid: number) {
    const pm = members[pid]
    if (pm) {
      const hasCeo = pm.some((m) => m.role === 'project_ceo')
      const hasOwner = pm.some((m) => m.role === 'owner')
      if (!hasCeo || !hasOwner) { toast.warning('请先配置企业教练和负责人后再下发项目。'); return }
    }
    setDispatchingId(pid)
    try {
      const result = await dispatchProject(pid)
      toast.success(`已下发给 ${result.dispatched_to} 位负责人`)
      const rows = await getProjects(true)
      setProjects(rows)
      reloadProjects()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '下发失败')
    } finally {
      setDispatchingId(null)
    }
  }

  async function handleApprove() {
    if (!approveModal) return
    setApproveLoading(true)
    try {
      const updated = await approveProject(approveModal.pid, approveForm)
      setProjects((prev) => prev.map((p) => (p.id === approveModal.pid ? { ...p, ...updated } : p)))
      reloadProjects()
      toast.success(`项目"${approveModal.name}"已审核通过并启动`)
      setApproveModal(null)
      setApproveForm({})
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '审核失败')
    } finally {
      setApproveLoading(false)
    }
  }

  async function handleReturn(pid: number, name: string) {
    const reason = window.prompt(`确认退回"${name}"的立项申请？\n请输入退回原因（可选）：`)
    if (reason === null) return
    try {
      const updated = await returnProject(pid, reason || undefined)
      setProjects((prev) => prev.map((p) => (p.id === pid ? { ...p, ...updated } : p)))
      reloadProjects()
      toast.success(`已退回"${name}"`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '退回失败')
    }
  }

  async function handleArchive(pid: number, name: string) {
    if (!window.confirm(`确认归档"${name}"？归档后将不再显示在常规列表中。`)) return
    await archiveProject(pid)
    setProjects((prev) => prev.map((p) => (p.id === pid ? { ...p, is_active: false } : p)))
    reloadProjects()
  }

  async function handleUnarchive(pid: number, name: string) {
    if (!window.confirm(`确认恢复"${name}"？`)) return
    const updated = await patchProject(pid, { status: 'active' })
    setProjects((prev) => prev.map((p) => (p.id === pid ? { ...p, ...updated, is_active: true } : p)))
    reloadProjects()
  }

  function parseImportText(text: string): BatchImportRow[] {
    const lines = text.split('\n').map((l) => l.trimEnd()).filter((l) => l.trim())
    if (lines.length < 2) return []
    const headers = lines[0].split('\t')
    const mapped = headers.map((h) => IMPORT_COL_MAP[h.trim()] ?? null)
    if (!mapped.some((f) => f === 'project_name')) return []
    const rows: BatchImportRow[] = []
    for (let i = 1; i < lines.length; i++) {
      const cells = lines[i].split('\t')
      const row: Partial<BatchImportRow> = {}
      mapped.forEach((field, index) => {
        if (!field) return
        const value = cells[index]?.trim()
        if (!value) return
        row[field] = value
      })
      if (row.project_name && row.key_task) rows.push(row as BatchImportRow)
    }
    return rows
  }

  function handleImportTextChange(text: string) {
    setImportText(text)
    setImportRows(parseImportText(text))
  }

  async function handleImportConfirm() {
    if (!importRows.length) return
    setImporting(true)
    try {
      const result = await batchImportProjects(importRows)
      toast.success(`导入完成：新建 ${result.projects_created} 个项目，创建 ${result.tasks_created} 条任务`)
      const rows = await getProjects(true)
      setProjects(rows)
      reloadProjects()
      setImportOpen(false)
      setImportText('')
      setImportRows([])
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '导入失败')
    } finally {
      setImporting(false)
    }
  }

  // ── 项目级角色判定 ──
  function getProjectRoles(pid: number) {
    const isSuperAdmin = Boolean(currentUser?.is_tech_admin)
    const isCompanyCeo = Boolean(currentUser?.is_ceo) && !isSuperAdmin
    const pm = members[pid] ?? []
    const isRealProjectCeo = Boolean(myPersonId && pm.some((m) => m.person_id === myPersonId && m.role === 'project_ceo'))
    const isRealOwner = Boolean(myPersonId && pm.some((m) => m.person_id === myPersonId && m.role === 'owner'))
    return { isSuperAdmin, isCompanyCeo, isRealProjectCeo, isRealOwner }
  }

  // ── 渲染 ──

  if (loading) {
    return (
      <div className="space-y-3">
        <SectionTitle inline>项目管理</SectionTitle>
        <p className="py-8 text-center text-sm text-slate-400">加载中...</p>
      </div>
    )
  }

  const menuProject = menuState ? projects.find((p) => p.id === menuState.pid) ?? null : null

  return (
    <div className="space-y-3">
      {/* 标题栏 */}
      <div className="flex items-center justify-between gap-3">
        <SectionTitle inline>{isOwnerView ? '我负责的项目' : isProjectCeoView ? '我企业教练的项目' : '项目管理'}</SectionTitle>
        <div className="flex items-center gap-2">
          {isFullAdmin && (
            <button type="button" onClick={() => setImportOpen(true)}
              className="cursor-pointer inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-600 hover:bg-indigo-100">
              批量导入
            </button>
          )}
          {isFullAdmin && (
            <button type="button" onClick={() => setShowNew(true)}
              className="cursor-pointer inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-white"
              style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}>
              新建项目
            </button>
          )}
        </div>
      </div>

      {/* 状态 tabs */}
      <div className="flex items-center gap-1 overflow-x-auto pb-1">
        {STATUS_TABS.map((tab) => {
          const count = tabCounts[tab.key] ?? 0
          const isActive = activeTab === tab.key
          return (
            <button key={tab.key} type="button" onClick={() => setActiveTab(tab.key)}
              className={`cursor-pointer flex-shrink-0 inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                isActive ? 'bg-sky-600 text-white' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}>
              {tab.label}
              <span className={`rounded-full px-1.5 text-[10px] font-bold ${isActive ? 'bg-white/25 text-white' : 'bg-slate-100 text-slate-500'}`}>
                {count}
              </span>
            </button>
          )
        })}
      </div>

      {/* 搜索 */}
      <input
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        placeholder="搜索项目名称…"
        className="w-full max-w-sm rounded-lg border border-slate-200 px-3 py-1.5 text-sm outline-none focus:border-sky-400"
      />

      {/* 两栏布局：左列表 + 右详情 */}
      <div className="flex gap-4 items-start">
        {/* 左侧项目列表 */}
        <div className="flex-1 min-w-0 space-y-2">
          {filteredProjects.length === 0 ? (
            <div className="rounded-xl border border-slate-100 bg-white py-10 text-center text-sm text-slate-400">暂无项目</div>
          ) : (
            filteredProjects.map((project) => {
              const status = getProjectPrimaryStatus(project)
              const roles = getProjectRoles(project.id)
              const mainAction = getMainAction(status, roles.isSuperAdmin, roles.isCompanyCeo, roles.isRealProjectCeo, roles.isRealOwner)
              const tasks = projectTasksMap[project.id] ?? []
              const subtasks = projectSubtasksMap[project.id] ?? []
              const summary = getDraftSummary(tasks, subtasks, project)
              const pm = members[project.id] ?? []
              const teamLine = summarizeProjectRoleLine(pm, project)
              const isSelected = selectedProjectId === project.id
              const showReturn = status === 'pending_review' && (roles.isRealProjectCeo || roles.isSuperAdmin)

              // 更多菜单项
              const moreItems: { label: string; tone?: 'danger'; onClick: () => void }[] = []
              if (roles.isSuperAdmin || (roles.isCompanyCeo && status === 'draft')) {
                moreItems.push({ label: '编辑项目', onClick: () => { setMenuState(null); void openProjectEditor(project) } })
              }
              if (roles.isSuperAdmin && status === 'active') {
                moreItems.push({ label: '归档', tone: 'danger', onClick: () => { setMenuState(null); void handleArchive(project.id, project.name) } })
              }
              if (roles.isSuperAdmin && status === 'archived') {
                moreItems.push({ label: '恢复', onClick: () => { setMenuState(null); void handleUnarchive(project.id, project.name) } })
              }

              return (
                <LifecycleCard
                  key={project.id}
                  project={project}
                  status={status}
                  teamLine={teamLine}
                  summary={summary}
                  mainAction={mainAction}
                  mainBusy={dispatchingId === project.id}
                  showReturn={showReturn}
                  isSelected={isSelected}
                  hasMore={moreItems.length > 0}
                  onSelect={() => setSelectedProjectId(project.id)}
                  onMainAction={() => {
                    if (mainAction.type === 'dispatch') void handleDispatch(project.id)
                    else if (mainAction.type === 'ownerSubmit') setOwnerFillProject(project)
                    else if (mainAction.type === 'approve') { setSelectedProjectId(project.id); setApproveModal({ pid: project.id, name: project.name }) }
                    else setSelectedProjectId(project.id)
                  }}
                  onReturn={() => void handleReturn(project.id, project.name)}
                  onOpenMore={async (anchorEl) => {
                    if (!members[project.id]) {
                      try { const rows = await getProjectMembers(project.id); setMembers((prev) => ({ ...prev, [project.id]: rows })) } catch {}
                    }
                    setMenuState({ pid: project.id, anchorEl })
                  }}
                />
              )
            })
          )}
        </div>

        {/* 右侧详情面板 */}
        <div className="w-[440px] flex-shrink-0 sticky top-4">
          {selectedProject ? (
            <DetailPanel
              project={selectedProject}
              projectMembers={members[selectedProject.id] ?? []}
              tasks={projectTasksMap[selectedProject.id] ?? []}
              subtasks={projectSubtasksMap[selectedProject.id] ?? []}
              roles={getProjectRoles(selectedProject.id)}
              onClose={() => setSelectedProjectId(null)}
              onDispatch={() => void handleDispatch(selectedProject.id)}
              onOwnerSubmit={() => setOwnerFillProject(selectedProject)}
              onApprove={() => setApproveModal({ pid: selectedProject.id, name: selectedProject.name })}
              onReturn={() => void handleReturn(selectedProject.id, selectedProject.name)}
            />
          ) : (
            <div className="rounded-xl border border-slate-100 bg-white py-16 text-center text-sm text-slate-400">
              选择左侧项目查看详情
            </div>
          )}
        </div>
      </div>

      {/* 新建项目弹窗 */}
      {showNew && (
        <ProjectInitModal
          open={showNew}
          creating={creating}
          people={people}
          form={newForm}
          setForm={setNewForm}
          team={newTeam}
          setTeam={setNewTeam}
          onClose={() => { setShowNew(false); resetNewForm() }}
          onSubmit={handleCreate}
        />
      )}

      {/* 编辑项目弹窗 */}
      {showEdit && editProjectId !== null && (
        <ProjectInitModal
          open={showEdit}
          creating={editingProject}
          mode="edit"
          people={people}
          form={editForm}
          setForm={setEditForm}
          team={editTeam}
          setTeam={setEditTeam}
          onClose={closeProjectEditor}
          onSubmit={handleSaveProjectEdit}
        />
      )}

      {/* 批量导入弹窗 */}
      {importOpen && (
        <ProjectBatchImportModal
          open={importOpen}
          importing={importing}
          text={importText}
          rows={importRows}
          onTextChange={handleImportTextChange}
          onClose={() => { if (!importing) { setImportOpen(false); setImportText(''); setImportRows([]) } }}
          onConfirm={handleImportConfirm}
        />
      )}

      {/* 审核弹窗 */}
      {approveModal && (
        <ProjectApproveModal
          open={Boolean(approveModal)}
          loading={approveLoading}
          name={approveModal.name}
          form={approveForm}
          draftSummary={approveDraftSummary}
          draftRows={approveDraftRows}
          onChangeForm={setApproveForm}
          onClose={() => !approveLoading && setApproveModal(null)}
          onConfirm={handleApprove}
        />
      )}

      {/* 负责人完善立项弹窗 */}
      {ownerFillProject && (
        <OwnerSubmitModal
          project={ownerFillProject}
          onClose={() => setOwnerFillProject(null)}
          onSuccess={() => {
            setOwnerFillProject(null)
            getProjects(true).then(setProjects).catch(() => {})
            reloadProjects()
          }}
        />
      )}

      {/* 更多菜单 */}
      {menuProject && menuState && (
        <LifecycleMoreMenu
          anchorEl={menuState.anchorEl}
          onClose={() => setMenuState(null)}
          items={
            (() => {
              const status = getProjectPrimaryStatus(menuProject)
              const roles = getProjectRoles(menuProject.id)
              const items: { label: string; tone?: 'danger'; onClick: () => void }[] = []
              if (roles.isSuperAdmin || (roles.isCompanyCeo && status === 'draft')) {
                items.push({ label: '编辑项目', onClick: () => { setMenuState(null); void openProjectEditor(menuProject) } })
              }
              if (roles.isSuperAdmin && status === 'active') {
                items.push({ label: '归档', tone: 'danger', onClick: () => { setMenuState(null); void handleArchive(menuProject.id, menuProject.name) } })
              }
              if (roles.isSuperAdmin && status === 'archived') {
                items.push({ label: '恢复', onClick: () => { setMenuState(null); void handleUnarchive(menuProject.id, menuProject.name) } })
              }
              return items
            })()
          }
        />
      )}
    </div>
  )
}

// ── 生命周期卡片 ──────────────────────────────────────────────

function LifecycleCard({
  project, status, teamLine, summary, mainAction, mainBusy, showReturn, isSelected, hasMore,
  onSelect, onMainAction, onReturn, onOpenMore,
}: {
  project: Project
  status: string
  teamLine: { ceoText: string; ownerText: string; coordinatorText: string; memberText: string }
  summary: DraftSummary
  mainAction: MainAction
  mainBusy: boolean
  showReturn: boolean
  isSelected: boolean
  hasMore: boolean
  onSelect: () => void
  onMainAction: () => void
  onReturn: () => void
  onOpenMore: (anchorEl: HTMLButtonElement) => void
}) {
  const statusBadge = getProjectStatusBadge(project)
  const projectType = project.project_type?.trim() || ''
  const stageDesc = STAGE_DESCRIPTIONS[status] ?? ''
  const draftText = summary.taskTotal === 0
    ? '推进表草案未完善'
    : `目标 ${summary.objectives}｜重点工作 ${summary.taskCount}｜关键任务 ${summary.subtaskCount}｜已指派 ${summary.ownerConfigured}/${summary.taskTotal}｜计划 ${summary.planConfigured}/${summary.taskTotal}`

  return (
    <div
      onClick={onSelect}
      className={`cursor-pointer rounded-xl border bg-white px-4 py-3 transition-colors ${isSelected ? 'border-sky-300 bg-sky-50/40' : 'border-slate-200 hover:border-slate-300'}`}
      style={{ boxShadow: '0 1px 3px rgba(15,23,42,0.04)' }}
    >
      {/* 第一层：标题行 */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-sm font-bold text-slate-800">{project.name}</h3>
            <span className={`flex-shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${statusBadge.className}`}>{statusBadge.label}</span>
            {projectType && <span className="flex-shrink-0 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-500">{projectType}</span>}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
          {showReturn && (
            <button type="button" onClick={onReturn}
              className="cursor-pointer rounded-lg border border-orange-200 bg-orange-50 px-2.5 py-1.5 text-xs font-semibold text-orange-700 hover:bg-orange-100">
              退回修改
            </button>
          )}
          <button type="button" onClick={onMainAction} disabled={mainBusy}
            className="cursor-pointer rounded-lg px-3 py-1.5 text-xs font-semibold text-white shadow-sm disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg,#2563EB,#0EA5E9)' }}>
            {mainBusy ? '处理中…' : mainAction.label}
          </button>
          {hasMore && (
            <button type="button" onClick={(e) => onOpenMore(e.currentTarget)}
              className="cursor-pointer rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-semibold text-slate-400 hover:bg-slate-50">
              ⋯
            </button>
          )}
        </div>
      </div>

      {/* 第二层：阶段说明 */}
      <p className="mt-1.5 text-xs text-slate-500">{stageDesc}</p>

      {/* 第三层：核心人员 */}
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-slate-600">
        <span>企业教练：{teamLine.ceoText}</span>
        <span>负责人：{teamLine.ownerText}</span>
        <span>统筹人：{teamLine.coordinatorText}</span>
        <span>成员：{teamLine.memberText}</span>
      </div>

      {/* 第四层：计划信息 */}
      <div className="mt-1 text-[11px] text-slate-500">
        计划时间：{formatPlanTimeShort(project.start_date, project.end_date)}
      </div>

      {/* 第五层：推进表雏形摘要 */}
      <div className="mt-1 text-[11px] text-slate-500">
        <span className={summary.taskTotal === 0 ? 'text-orange-500' : 'text-slate-600'}>{draftText}</span>
      </div>
    </div>
  )
}

// ── 更多菜单 ──────────────────────────────────────────────────

function LifecycleMoreMenu({
  anchorEl, onClose, items,
}: {
  anchorEl: HTMLButtonElement
  onClose: () => void
  items: { label: string; tone?: 'danger'; onClick: () => void }[]
}) {
  const panelRef = useRef<HTMLDivElement>(null)
  const [position, setPosition] = useState({ top: 0, left: 0 })

  useLayoutEffect(() => {
    let mounted = true
    const updatePosition = () => {
      const rect = anchorEl.getBoundingClientRect()
      const pw = panelRef.current?.getBoundingClientRect().width ?? 200
      const ph = panelRef.current?.getBoundingClientRect().height ?? 200
      const next = getPickerPosition(rect, { width: Math.max(200, pw), height: Math.min(260, ph) }, { width: window.innerWidth, height: window.innerHeight })
      if (mounted) setPosition({ top: next.top, left: next.left })
    }
    updatePosition()
    const raf = window.requestAnimationFrame(updatePosition)
    const handleMouseDown = (e: MouseEvent) => {
      const t = e.target as Node | null
      if (!t) return
      if (panelRef.current?.contains(t)) return
      if (anchorEl.contains(t)) return
      onClose()
    }
    const handleScroll = (e: Event) => {
      const t = e.target as Node | null
      if (t && panelRef.current?.contains(t)) return
      onClose()
    }
    document.addEventListener('mousedown', handleMouseDown)
    document.addEventListener('scroll', handleScroll, true)
    window.addEventListener('resize', updatePosition)
    return () => {
      mounted = false
      window.cancelAnimationFrame(raf)
      document.removeEventListener('mousedown', handleMouseDown)
      document.removeEventListener('scroll', handleScroll, true)
      window.removeEventListener('resize', updatePosition)
    }
  }, [anchorEl, onClose])

  if (items.length === 0) return null

  return createPortal(
    <div ref={panelRef}
      className="fixed z-[1000] w-[200px] overflow-hidden rounded-xl border bg-white shadow-2xl"
      style={{ top: position.top, left: position.left, maxHeight: 260 }}
      onMouseDown={(e) => e.stopPropagation()} onClick={(e) => e.stopPropagation()}>
      <div className="p-1.5">
        {items.map((item) => (
          <button key={item.label} type="button"
            onClick={() => { onClose(); item.onClick() }}
            className="flex w-full items-center rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-50"
            style={{ color: item.tone === 'danger' ? '#DC2626' : '#334155' }}>
            {item.label}
          </button>
        ))}
      </div>
    </div>,
    document.body,
  )
}

// ── 右侧详情面板 ──────────────────────────────────────────────

function DetailPanel({
  project, projectMembers, tasks, subtasks, roles, onClose,
  onDispatch, onOwnerSubmit, onApprove, onReturn,
}: {
  project: Project
  projectMembers: ProjectMember[]
  tasks: TaskItem[]
  subtasks: SubTaskWithParent[]
  roles: { isSuperAdmin: boolean; isCompanyCeo: boolean; isRealProjectCeo: boolean; isRealOwner: boolean }
  onClose: () => void
  onDispatch: () => void
  onOwnerSubmit: () => void
  onApprove: () => void
  onReturn: () => void
}) {
  const status = getProjectPrimaryStatus(project)
  const statusBadge = getProjectStatusBadge(project)
  const teamLine = summarizeProjectRoleLine(projectMembers, project)
  const summary = getDraftSummary(tasks, subtasks, project)
  const draftRows = buildDraftRows(tasks, subtasks, project)
  const stageDesc = STAGE_DESCRIPTIONS[status] ?? ''
  const mainAction = getMainAction(status, roles.isSuperAdmin, roles.isCompanyCeo, roles.isRealProjectCeo, roles.isRealOwner)
  const showReturn = status === 'pending_review' && (roles.isRealProjectCeo || roles.isSuperAdmin)

  const infoRow = (label: string, value?: string) => (
    <div className="flex gap-2 py-1">
      <span className="w-16 shrink-0 text-xs font-semibold text-slate-400">{label}</span>
      <span className="flex-1 text-xs text-slate-700">{value?.trim() || '未填写'}</span>
    </div>
  )

  return (
    <div className="flex max-h-[calc(100vh-180px)] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white" style={{ boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
      {/* 标题栏 */}
      <div className="flex items-start justify-between gap-2 border-b px-4 py-3" style={{ borderColor: '#E9EFF6' }}>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="truncate text-sm font-bold text-slate-900">{project.name}</h2>
            <span className={`flex-shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${statusBadge.className}`}>{statusBadge.label}</span>
          </div>
          <p className="mt-0.5 text-xs text-slate-400">{stageDesc}</p>
        </div>
        <button type="button" onClick={onClose}
          className="flex-shrink-0 rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
          <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
        </button>
      </div>

      {/* 滚动区 */}
      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-3">
        {/* 1. 基本信息 */}
        <div>
          <p className="mb-1 text-xs font-bold text-slate-500">项目基本信息</p>
          <div className="rounded-lg border border-slate-100 px-3 py-1">
            {infoRow('项目名称', project.name)}
            {infoRow('项目状态', statusBadge.label)}
            {infoRow('项目类型', project.project_type)}
            {infoRow('计划时间', formatPlanTimeShort(project.start_date, project.end_date))}
            {infoRow('客户名称', project.client_name)}
          </div>
        </div>

        {/* 2. 核心人员 */}
        <div>
          <p className="mb-1 text-xs font-bold text-slate-500">核心人员</p>
          <div className="rounded-lg border border-slate-100 px-3 py-1">
            {infoRow('企业教练', teamLine.ceoText)}
            {infoRow('负责人', teamLine.ownerText)}
            {infoRow('统筹人', teamLine.coordinatorText)}
            {infoRow('成员', teamLine.memberText)}
          </div>
        </div>

        {/* 3. 立项信息 */}
        <div>
          <p className="mb-1 text-xs font-bold text-slate-500">立项信息</p>
          <div className="space-y-1.5">
            <div className="rounded-lg border border-slate-100 px-3 py-2">
              <div className="text-[11px] text-slate-400">项目背景</div>
              <div className="mt-0.5 text-xs leading-relaxed text-slate-700">{project.background?.trim() || '未填写'}</div>
            </div>
            <div className="rounded-lg border border-slate-100 px-3 py-2">
              <div className="text-[11px] text-slate-400">项目目标</div>
              <div className="mt-0.5 text-xs leading-relaxed text-slate-700">{project.objectives?.trim() || '未填写'}</div>
            </div>
            <div className="rounded-lg border border-slate-100 px-3 py-2">
              <div className="text-[11px] text-slate-400">预期交付物</div>
              <div className="mt-0.5 text-xs leading-relaxed text-slate-700">{project.expected_outcomes?.trim() || '未填写'}</div>
            </div>
          </div>
        </div>

        {/* 4. 当前阶段 */}
        <div>
          <p className="mb-1 text-xs font-bold text-slate-500">当前阶段</p>
          <div className="rounded-lg border border-sky-100 bg-sky-50/60 px-3 py-2 text-xs text-slate-700">{stageDesc}</div>
        </div>

        {/* 5. 工作推进表雏形 */}
        <div>
          <p className="mb-1 text-xs font-bold text-slate-500">
            {status === 'active' ? '工作推进表初版' : '工作推进表雏形'}
          </p>

          {/* 摘要 */}
          <div className="mb-2 flex flex-wrap gap-1.5">
            {[
              { label: '目标', val: summary.objectives },
              { label: '重点工作', val: summary.taskCount },
              { label: '关键任务', val: summary.subtaskCount },
              { label: '已指派', val: `${summary.ownerConfigured}/${summary.taskTotal}` },
              { label: '计划', val: `${summary.planConfigured}/${summary.taskTotal}` },
            ].map((item) => (
              <span key={item.label} className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
                {item.label} <span className="text-sky-600">{item.val}</span>
              </span>
            ))}
          </div>

          {/* 类 Excel 草案明细表 */}
          {draftRows.length === 0 ? (
            <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-4 text-center text-xs text-slate-400">
              推进表草案未完善
            </div>
          ) : (
            <DraftProgressTable rows={draftRows} />
          )}
        </div>
      </div>

      {/* 操作栏 */}
      {mainAction.type !== 'viewDetail' && (
        <div className="flex gap-2 border-t px-4 py-2.5" style={{ borderColor: '#E9EFF6' }}>
          {showReturn && (
            <button type="button" onClick={onReturn}
              className="cursor-pointer rounded-lg border border-orange-200 bg-orange-50 px-3 py-1.5 text-xs font-semibold text-orange-700 hover:bg-orange-100">
              退回修改
            </button>
          )}
          <button type="button"
            onClick={() => {
              if (mainAction.type === 'dispatch') onDispatch()
              else if (mainAction.type === 'ownerSubmit') onOwnerSubmit()
              else if (mainAction.type === 'approve') onApprove()
            }}
            className="cursor-pointer flex-1 rounded-lg px-3 py-1.5 text-xs font-semibold text-white"
            style={{ background: 'linear-gradient(135deg,#2563EB,#0EA5E9)' }}>
            {mainAction.label === '完善立项信息' ? '完善立项与推进表草案'
              : mainAction.label === '审核立项' ? '审核立项与推进表草案'
              : mainAction.label === '修改立项信息' ? '修改立项与推进表草案'
              : mainAction.label}
          </button>
        </div>
      )}
    </div>
  )
}

// ── 类 Excel 草案明细表 ──────────────────────────────────────

function DraftProgressTable({ rows }: { rows: DraftRow[] }) {
  const cols = ['目标', '重点工作', '评价标准', '序号', '关键任务', '责任人', '计划开始', '计划结束', '协同人', '备注']
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="w-full text-[11px]" style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: '#F8FAFC' }}>
            {cols.map((c) => (
              <th key={c} className="whitespace-nowrap border-b border-r px-2 py-1.5 text-left font-semibold text-slate-500 last:border-r-0" style={{ borderColor: '#E2E8F0' }}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx} className={row.isTaskOnly ? 'bg-orange-50/40' : idx % 2 === 0 ? 'bg-white' : 'bg-slate-50/40'}>
              <td className="border-b border-r px-2 py-1.5 text-slate-600" style={{ borderColor: '#E2E8F0', maxWidth: 80, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.objective}>{row.objective}</td>
              <td className="border-b border-r px-2 py-1.5 font-semibold text-slate-700" style={{ borderColor: '#E2E8F0', maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.keyTask}>{row.keyTask}</td>
              <td className="border-b border-r px-2 py-1.5 text-slate-600" style={{ borderColor: '#E2E8F0', maxWidth: 80, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.standard}>{row.standard}</td>
              <td className="border-b border-r px-2 py-1.5 text-center text-slate-500" style={{ borderColor: '#E2E8F0' }}>{row.seq}</td>
              <td className={`border-b border-r px-2 py-1.5 ${row.isTaskOnly ? 'text-orange-500' : 'text-slate-700'}`} style={{ borderColor: '#E2E8F0', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.subTask}>{row.subTask}</td>
              <td className="border-b border-r px-2 py-1.5 text-slate-600" style={{ borderColor: '#E2E8F0', whiteSpace: 'nowrap' }}>{row.assignee}</td>
              <td className="border-b border-r px-2 py-1.5 text-slate-500" style={{ borderColor: '#E2E8F0', whiteSpace: 'nowrap' }}>{row.planStart}</td>
              <td className="border-b border-r px-2 py-1.5 text-slate-500" style={{ borderColor: '#E2E8F0', whiteSpace: 'nowrap' }}>{row.planEnd}</td>
              <td className="border-b border-r px-2 py-1.5 text-slate-600" style={{ borderColor: '#E2E8F0', maxWidth: 80, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.collaborator}>{row.collaborator}</td>
              <td className="border-b px-2 py-1.5 text-slate-500" style={{ borderColor: '#E2E8F0', maxWidth: 80, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.note}>{row.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── 审核弹窗 ──────────────────────────────────────────────────

function ProjectApproveModal({
  open, loading, name, form, draftSummary, draftRows, onChangeForm, onClose, onConfirm,
}: {
  open: boolean
  loading: boolean
  name: string
  form: ProjectProfilePayload
  draftSummary: DraftSummary
  draftRows: DraftRow[]
  onChangeForm: (next: ProjectProfilePayload) => void
  onClose: () => void
  onConfirm: () => void
}) {
  const fields: Array<{ key: keyof ProjectProfilePayload; label: string; type: 'text' | 'date' }> = [
    { key: 'project_type', label: '项目类型', type: 'text' },
    { key: 'client_name', label: '客户名称', type: 'text' },
    { key: 'background', label: '项目背景', type: 'text' },
    { key: 'objectives', label: '项目目标', type: 'text' },
    { key: 'expected_outcomes', label: '预期交付物', type: 'text' },
    { key: 'start_date', label: '开始日期', type: 'date' },
    { key: 'end_date', label: '结束日期', type: 'date' },
  ]
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-3" onClick={() => { if (!loading) onClose() }}>
      <div className="w-[520px] overflow-hidden rounded-2xl bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="border-b px-6 py-4" style={{ borderColor: '#E9EFF6' }}>
          <div className="text-sm font-bold text-slate-800">审核立项与推进表草案</div>
          <div className="mt-0.5 text-xs text-slate-400">负责人提交的信息可在这里修正后再确立，详细内容可在项目详情面板查看</div>
        </div>
        <div className="max-h-[60vh] space-y-3 overflow-y-auto px-6 py-5">
          <div className="rounded-xl border border-purple-200 bg-purple-50 px-4 py-2.5">
            <span className="text-sm font-semibold text-slate-700">{name}</span>
          </div>
          <section className="rounded-xl border border-amber-200 bg-amber-50/60 px-4 py-3">
            <div className="mb-2 flex items-center justify-between">
              <div className="text-xs font-bold text-slate-700">工作推进表雏形</div>
              <div className="text-[11px] text-slate-400">详细内容可在项目详情面板查看</div>
            </div>
            <div className="mb-2 flex flex-wrap gap-2">
              <span className="rounded-md bg-white px-2 py-1 text-[11px] font-semibold text-slate-600">
                重点工作数量 <span className="text-amber-600">{draftSummary.taskCount}</span>
              </span>
              <span className="rounded-md bg-white px-2 py-1 text-[11px] font-semibold text-slate-600">
                关键任务数量 <span className="text-amber-600">{draftSummary.subtaskCount}</span>
              </span>
            </div>
            {draftRows.length === 0 ? (
              <div className="rounded-lg border border-dashed border-amber-200 bg-white/70 px-3 py-3 text-center text-xs text-slate-400">
                暂无工作推进表雏形
              </div>
            ) : (
              <div className="space-y-1.5">
                {draftRows.slice(0, 3).map((row, index) => (
                  <div key={`${row.keyTask}-${row.subTask}-${index}`} className="rounded-lg bg-white px-3 py-2 text-xs text-slate-600">
                    <div className="font-semibold text-slate-700">{row.keyTask}</div>
                    <div className="mt-0.5 text-slate-500">关键任务：{row.subTask}</div>
                  </div>
                ))}
              </div>
            )}
          </section>
          {fields.map(({ key, label, type }) => (
            <div key={key}>
              <label className="mb-1 block text-xs font-semibold text-slate-600">{label}</label>
              {key === 'background' || key === 'objectives' || key === 'expected_outcomes' ? (
                <textarea value={(form[key] as string) ?? ''} onChange={(e) => onChangeForm({ ...form, [key]: e.target.value })} rows={3}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-purple-400 focus:ring-2 focus:ring-purple-400/20" />
              ) : (
                <input type={type} value={(form[key] as string) ?? ''} onChange={(e) => onChangeForm({ ...form, [key]: e.target.value })}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-purple-400 focus:ring-2 focus:ring-purple-400/20" />
              )}
            </div>
          ))}
        </div>
        <div className="flex gap-2 px-6 pb-5 pt-3">
          <button type="button" onClick={onClose} disabled={loading}
            className="cursor-pointer flex-1 rounded-xl border border-slate-200 py-2 text-sm text-slate-500 hover:bg-slate-50">取消</button>
          <button type="button" onClick={onConfirm} disabled={loading}
            className="cursor-pointer flex-1 rounded-xl py-2 text-sm font-semibold text-white disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg,#7E22CE,#A855F7)' }}>
            {loading ? '处理中…' : '审核并确立'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 批量导入弹窗 ──────────────────────────────────────────────

function ProjectBatchImportModal({
  open, importing, text, rows, onTextChange, onClose, onConfirm,
}: {
  open: boolean
  importing: boolean
  text: string
  rows: BatchImportRow[]
  onTextChange: (value: string) => void
  onClose: () => void
  onConfirm: () => void
}) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-3" onClick={() => { if (!importing) onClose() }}>
      <div className="flex max-h-[88vh] w-[760px] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b px-6 py-4" style={{ borderColor: '#E9EFF6' }}>
          <div>
            <div className="text-sm font-bold text-slate-800">批量导入项目</div>
            <div className="mt-0.5 text-xs text-slate-400">从 Excel 复制制表符分隔数据，粘贴到下面的文本框中</div>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100">
            <svg style={{ width: 15, height: 15 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-4">
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
            <div className="font-semibold text-slate-600">支持的列名</div>
            <div className="mt-1 flex flex-wrap gap-2">
              {['项目/阶段', '关键任务', '关键成果', '完成标准', '统筹人', '负责人', '协同/成员', '计划时间', '当前状态', '问题与需协调事项'].map((label) => (
                <span key={label} className="rounded-md border border-slate-200 bg-white px-2 py-0.5 text-slate-600">{label}</span>
              ))}
            </div>
          </div>
          <textarea value={text} onChange={(e) => onTextChange(e.target.value)}
            placeholder={`从 Excel 粘贴数据（含表头），示例：\n项目\t关键任务\t负责人\t统筹人\t计划时间\t当前状态\n知识平台\t制定方案\t张三\t李四\t4-5月\t未启动`}
            className="h-40 w-full resize-none rounded-xl border border-slate-200 p-3 font-mono text-xs outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-400/20" />
          {text && rows.length === 0 && <div className="px-1 text-xs text-red-500">未识别到有效数据，请检查表头是否包含"项目"和"关键任务"。</div>}
          {rows.length > 0 && (
            <div>
              <div className="mb-2 text-xs font-semibold text-slate-500">解析预览，共 {rows.length} 行</div>
              <div className="overflow-x-auto rounded-xl border" style={{ borderColor: '#E9EFF6' }}>
                <table className="w-full text-xs">
                  <thead>
                    <tr style={{ background: '#F8FAFC' }}>
                      {['项目', '关键任务', '负责人', '统筹人', '计划时间', '状态', '问题'].map((label) => (
                        <th key={label} className="whitespace-nowrap px-3 py-2 text-left font-semibold text-slate-500">{label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, index) => (
                      <tr key={index} className="border-t" style={{ borderColor: '#F1F5F9' }}>
                        <td className="whitespace-nowrap px-3 py-2 font-semibold text-indigo-700">{row.project_name}</td>
                        <td className="max-w-xs truncate px-3 py-2 text-slate-700">{row.key_task}</td>
                        <td className="whitespace-nowrap px-3 py-2 text-slate-600">{row.owner || '-'}</td>
                        <td className="whitespace-nowrap px-3 py-2 text-slate-600">{row.coordinator || '-'}</td>
                        <td className="whitespace-nowrap px-3 py-2 text-slate-600">{fmtPlanTime(row.plan_time)}</td>
                        <td className="whitespace-nowrap px-3 py-2"><span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-semibold text-slate-600">{row.status || '未填写'}</span></td>
                        <td className="max-w-xs truncate px-3 py-2 text-amber-600">{row.issue || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
        <div className="flex items-center justify-between border-t px-6 py-4" style={{ borderColor: '#E9EFF6' }}>
          <div className="text-xs text-slate-400">{rows.length > 0 ? `将创建或匹配 ${rows.length} 个项目` : '粘贴后会自动解析预览'}</div>
          <div className="flex gap-2">
            <button type="button" onClick={onClose} className="rounded-xl px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">取消</button>
            <button type="button" onClick={onConfirm} disabled={importing || rows.length === 0}
              className="rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}>
              {importing ? '导入中…' : `确认导入 ${rows.length} 行`}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
