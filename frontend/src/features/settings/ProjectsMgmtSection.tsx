import { createPortal } from 'react-dom'
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useProject } from '../../context/ProjectContext'
import {
  getProjects,
  getProjectMembers,
  createProject,
  patchProject,
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
import { fmtPlanTime, fmtDate } from '../../utils/time'
import { toast } from '../../utils/toast'
import { canManageProjects } from '../../domain/permissions'
import {
  getProjectPrimaryStatus,
  getProjectStatusBadge,
} from '../../domain/projectLifecycleStatus'
import { getProjectRoleLabel } from '../../domain/roleLabels'
import { NewProjectForm, ProjectInitModal, type TeamMap } from './ProjectInitModal'
import { OwnerSubmitModal } from './OwnerSubmitModal'
import { getPickerPosition } from './projectPickerPosition.js'
import { ProjectCloseFlowDrawer } from './ProjectCloseFlowDrawer'
import { getProjectCloseMainAction } from '../../domain/projectCloseUi'

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

const PAGE_SIZE = 10

const STATUS_LABEL_MAP: Record<string, string> = {
  draft: '草稿', dispatched: '已派发', pending_review: '待审核', returned: '已退回',
  active: '进行中', pending_close: '结束审核中', ended: '已结束', archived: '已归档',
}

const STATUS_COLOR_MAP: Record<string, string> = {
  draft: 'text-slate-500 bg-slate-100',
  dispatched: 'text-amber-700 bg-amber-50',
  pending_review: 'text-orange-700 bg-orange-50',
  returned: 'text-red-600 bg-red-50',
  active: 'text-sky-600 bg-sky-50',
  pending_close: 'text-indigo-600 bg-indigo-50',
  ended: 'text-emerald-600 bg-emerald-50',
  archived: 'text-slate-400 bg-slate-50',
}

const STAGE_DESCRIPTIONS: Record<string, string> = {
  draft: '项目尚未下发，可继续编辑项目基础信息和角色配置。',
  dispatched: '项目已下发，等待负责人完善立项信息和推进表草案。',
  pending_review: '负责人已提交，等待企业教练审核立项和推进表草案。',
  returned: '企业教练已退回，请负责人修改后重新提交。',
  active: '项目已进入执行阶段，可进入工作推进表查看推进情况。',
  pending_close: '项目结束申请已提交，等待企业教练审核。',
  ended: '项目已结束，可查看结束档案并等待技术归档。',
  archived: '项目已归档，可查看归档资料和复盘结果。',
}

const ACTION_REMINDERS: Record<string, string> = {
  draft: '项目尚未下发，可继续编辑项目资料与角色配置。',
  dispatched: '项目已下发，等待负责人完善立项信息和工作推进表雏形。',
  pending_review: '负责人已提交立项信息和工作推进表雏形，请企业教练审核项目完成准则、重点工作和关键任务安排。',
  returned: '项目已被企业教练退回，请负责人根据意见修改后重新提交。',
  active: '项目已进入执行阶段，可进入工作推进表查看重点工作、关键任务和进展记录。',
  pending_close: '项目结束申请正在审核中，可查看材料；申请人可修改或取消，企业教练可审核。',
  ended: '项目结束申请已批准，可查看结束档案。',
  archived: '项目已归档，可查看项目档案和历史记录。',
}

function getReminderToneClass(status: string): string {
  if (status === 'pending_review') return 'border-amber-200 bg-amber-50 text-amber-900'
  if (status === 'returned') return 'border-orange-200 bg-orange-50 text-orange-900'
  if (status === 'active') return 'border-emerald-200 bg-emerald-50 text-emerald-900'
  if (status === 'pending_close') return 'border-orange-200 bg-orange-50 text-orange-900'
  if (status === 'ended') return 'border-indigo-200 bg-indigo-50 text-indigo-900'
  if (status === 'archived') return 'border-slate-200 bg-slate-50 text-slate-700'
  return 'border-sky-200 bg-sky-50 text-sky-900'
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
  planRange: string
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
      const planRange = task.plan_time?.trim() || '—'
      rows.push({
        objective, keyTask: task.key_task || '—', standard, seq: '—',
        subTask: '关键任务待补充', assignee: task.owner?.trim() || '—',
        planRange, collaborator, note: '—', isTaskOnly: true,
      })
    } else {
      taskSubs.forEach((sub, idx) => {
        const planRange = sub.plan_time?.trim() || task.plan_time?.trim() || '—'
        rows.push({
          objective, keyTask: task.key_task || '—', standard, seq: String(idx + 1),
          subTask: sub.title || '—', assignee: sub.assignee?.trim() || '—',
          planRange, collaborator, note: sub.notes?.trim() || '—', isTaskOnly: false,
        })
      })
    }
  }
  return rows
}

type MainAction = { label: string; type: 'edit' | 'dispatch' | 'ownerSubmit' | 'approvalMaterials' | 'workProgress' | 'viewDetail' | 'closeRequest' | 'closeReview' | 'closeArchiveView' | 'projectArchive' }

function getMainAction(
  status: string,
  isSuperAdmin: boolean,
  isCompanyCeo: boolean,
  isRealProjectCeo: boolean,
  isRealOwner: boolean,
): MainAction {
  const closeAction = getProjectCloseMainAction(status, { isSuperAdmin, isCompanyCeo, isRealProjectCeo, isRealOwner })
  if (closeAction && status !== 'active') return closeAction
  switch (status) {
    case 'draft':
      return (isSuperAdmin || isCompanyCeo)
        ? { label: '编辑项目', type: 'edit' }
        : { label: '查看详情', type: 'viewDetail' }
    case 'dispatched':
      return isRealOwner
        ? { label: '完善立项信息', type: 'ownerSubmit' }
        : { label: '查看详情', type: 'viewDetail' }
    case 'pending_review':
      return { label: '查看审核材料', type: 'approvalMaterials' }
    case 'returned':
      return isRealOwner
        ? { label: '修改立项信息', type: 'ownerSubmit' }
        : { label: '查看详情', type: 'viewDetail' }
    case 'active':
      return { label: '进入工作推进表', type: 'workProgress' }
    case 'archived':
      return { label: '查看项目档案', type: 'projectArchive' }
    default:
      return { label: '查看详情', type: 'viewDetail' }
  }
}

// ── 主组件 ────────────────────────────────────────────────────

export function ProjectsMgmtSection() {
  const { reloadProjects, currentUser, globalUserRoles } = useProject()
  const navigate = useNavigate()
  const location = useLocation()
  const [projects, setProjects] = useState<Project[]>([])
  const [people, setPeople] = useState<Person[]>([])
  const [loading, setLoading] = useState(true)
  const [members, setMembers] = useState<Record<number, ProjectMember[]>>({})

  // 搜索 + 分页
  const [page, setPage] = useState(0)
  const [searchQuery, setSearchQuery] = useState('')

  // 流程相关
  const [closeFlowProjectId, setCloseFlowProjectId] = useState<number | null>(null)
  const [closeFlowRequestId, setCloseFlowRequestId] = useState<number | null>(null)

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
  const [approvalMaterialsProject, setApprovalMaterialsProject] = useState<Project | null>(null)
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

  // ── 搜索过滤 + 按名称排序 ──
  const filteredProjects = useMemo(() => {
    let list = [...roleFilteredProjects]
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase()
      list = list.filter((p) => p.name.toLowerCase().includes(q))
    }
    list.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
    return list
  }, [roleFilteredProjects, searchQuery])

  // ── 分页 ──
  const totalPages = Math.max(1, Math.ceil(filteredProjects.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages - 1)
  const currentPageItems = useMemo(() => {
    const start = safePage * PAGE_SIZE
    return filteredProjects.slice(start, start + PAGE_SIZE)
  }, [filteredProjects, safePage])

  // 搜索时重置到第0页
  useEffect(() => {
    setPage(0)
  }, [searchQuery])

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

  async function handleApprove(project: Project) {
    setApproveLoading(true)
    try {
      const updated = await approveProject(project.id, {})
      setProjects((prev) => prev.map((p) => (p.id === project.id ? { ...p, ...updated } : p)))
      reloadProjects()
      toast.success(`项目"${project.name}"已审核通过并启动`)
      setApprovalMaterialsProject(null)
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

  function openCloseFlow(project: Project, requestId?: number | null) {
    setSelectedProjectId(project.id)
    setCloseFlowProjectId(project.id)
    setCloseFlowRequestId(requestId ?? null)
  }

  function closeCloseFlow() {
    setCloseFlowProjectId(null); setCloseFlowRequestId(null)
    const params = new URLSearchParams(location.search)
    params.delete('closeRequestId')
    navigate({ pathname: location.pathname, search: params.toString() ? `?${params.toString()}` : '' }, { replace: true })
  }

  async function refreshProjectCloseState(projectId: number) {
    const rows = await getProjects(true)
    setProjects(rows)
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
      <div className="projects-lifecycle-page-shell -m-3 bg-[#F8FAFC] px-6 py-5">
        <p className="py-8 text-center text-sm text-slate-400">加载中...</p>
      </div>
    )
  }

  const menuProject = menuState ? projects.find((p) => p.id === menuState.pid) ?? null : null

  return (
    <div className="projects-lifecycle-workbench projects-lifecycle-page-shell -m-3 bg-[#F8FAFC] px-6 py-5">
      <section className="mx-auto flex max-w-[1440px] flex-col gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索项目名称..."
              className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm outline-none focus:border-sky-400 focus:bg-white sm:w-72"
            />
            <span className="whitespace-nowrap text-xs text-slate-400">
              共 {filteredProjects.length} 个项目
            </span>
          </div>
          <div className="flex items-center gap-2">
            {isFullAdmin && (
              <>
                <button type="button" onClick={() => setImportOpen(true)}
                  className="h-9 cursor-pointer rounded-lg border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-600 shadow-sm transition-colors hover:bg-slate-100">
                  批量导入
                </button>
                <button type="button" onClick={() => setShowNew(true)}
                  className="h-9 cursor-pointer rounded-lg bg-[#2170e4] px-3 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-[#1b5fc7]">
                  新建项目
                </button>
              </>
            )}
          </div>
      </section>

      <div className="mx-auto mt-5 max-w-[1200px]">{/* 宽表格 */}
        <section className="projects-lifecycle-project-queue min-w-0">
          {filteredProjects.length === 0 ? (
            <div className="rounded-2xl border border-slate-200 bg-white py-12 text-center text-sm text-slate-400 shadow-sm">暂无项目</div>
          ) : (
            <>
              <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
                <table className="w-full border-collapse">
                  <thead className="bg-slate-50">
                    <tr className="border-b border-slate-200 text-left text-xs font-bold tracking-wide text-slate-500">
                      <th className="py-3 pr-4 pl-5 whitespace-nowrap">项目名称</th>
                      <th className="py-3 pr-4 whitespace-nowrap">状态</th>
                      <th className="py-3 pr-4 whitespace-nowrap">项目周期</th>
                      <th className="py-3 pr-4 whitespace-nowrap">项目负责人</th>
                      <th className="py-3 pr-4 whitespace-nowrap">Coach / 企业教练</th>
                      <th className="py-3 pr-5 whitespace-nowrap text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {currentPageItems.map((project) => {
                      const status = getProjectPrimaryStatus(project)
                      const roles = getProjectRoles(project.id)
                      const pm = members[project.id] ?? []

                      // 提取负责人和教练
                      const ownerMembers = pm.filter((m) => m.role === 'owner')
                      const coachMembers = pm.filter((m) => m.role === 'project_ceo')
                      const ownerName = ownerMembers.map((m) => m.person_name_snapshot).join(', ') || (project as any).real_owner_name || '-'
                      const coachName = coachMembers.map((m) => m.person_name_snapshot).join(', ') || (project as any).real_project_ceo_name || '-'

                      // 行点击 → 跳转详情页
                      const goDetail = () => navigate(`/home/projects/${project.id}`)

                      // 主要操作按钮（行内快捷操作）
                      const mainAction = getMainAction(status, roles.isSuperAdmin, roles.isCompanyCeo, roles.isRealProjectCeo, roles.isRealOwner)
                      const actionLabel = (() => {
                        switch (mainAction.type) {
                          case 'edit': return '编辑'
                          case 'dispatch': return '派发'
                          case 'ownerSubmit': return '完善材料'
                          case 'approvalMaterials': return '审核材料'
                          case 'workProgress': return '工作进展'
                          case 'projectArchive': return '项目归档'
                          case 'closeRequest': return '结束流程'
                          case 'closeReview': return '审核结束'
                          case 'closeArchiveView': return '查看归档'
                          default: return '查看'
                        }
                      })()

                      const handleAction = () => {
                        if (mainAction.type === 'edit') void openProjectEditor(project)
                        else if (mainAction.type === 'dispatch') void handleDispatch(project.id)
                        else if (mainAction.type === 'ownerSubmit') setOwnerFillProject(project)
                        else if (mainAction.type === 'approvalMaterials') { setApprovalMaterialsProject(project) }
                        else if (mainAction.type === 'workProgress') navigate(`/work/tasks?projectId=${project.id}`)
                        else if (mainAction.type === 'projectArchive') navigate(`/home/projects/${project.id}/archive`)
                        else if (mainAction.type === 'closeRequest' || mainAction.type === 'closeReview' || mainAction.type === 'closeArchiveView') openCloseFlow(project)
                        else goDetail()
                      }

                      return (
                        <tr
                          key={project.id}
                          onClick={goDetail}
                          className="group cursor-pointer border-b border-slate-100 text-sm transition-colors hover:bg-sky-50/60 bg-white"
                        >
                          <td className="py-4 pr-4 pl-5">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-slate-800">{project.name}</span>
                              {(project as any).lifecycle_type && (
                                <span className="inline-block rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500">
                                  {(project as any).lifecycle_type.toUpperCase().includes('WEEKLY') ? '周报' :
                                   (project as any).lifecycle_type.toUpperCase().includes('MONTHLY') ? '月报' :
                                   (project as any).lifecycle_type}
                                </span>
                              )}
                            </div>
                            <div className="mt-0.5 text-[11px] text-slate-400">ID: {project.id}</div>
                          </td>
                          <td className="py-4 pr-4">
                            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-bold ${STATUS_COLOR_MAP[status] || 'text-slate-500 bg-slate-100'}`}>
                              {STATUS_LABEL_MAP[status] || status}
                            </span>
                          </td>
                          <td className="py-4 pr-4 text-sm text-slate-500 whitespace-nowrap">{formatPlanTimeShort(project.start_date, project.end_date)}</td>
                          <td className="py-4 pr-4 text-sm text-slate-600">{ownerName}</td>
                          <td className="py-4 pr-4 text-sm text-slate-600">{coachName}</td>
                          <td className="py-4 pr-5 text-right">
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); handleAction() }}
                              disabled={dispatchingId === project.id}
                              className="cursor-pointer rounded-lg bg-slate-900 px-3.5 py-1.5 text-xs font-semibold text-white transition-colors whitespace-nowrap hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {dispatchingId === project.id ? '派发中...' : actionLabel}
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              {/* 分页 */}
              {totalPages > 1 && (
                <div className="mt-4 flex items-center justify-center gap-1">
                  <button
                    type="button"
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={safePage === 0}
                    className="cursor-pointer rounded-lg px-3 py-1.5 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    上一页
                  </button>
                  <span className="px-3 text-xs text-slate-400">
                    第 {safePage + 1}/{totalPages} 页
                  </span>
                  <button
                    type="button"
                    onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                    disabled={safePage >= totalPages - 1}
                    className="cursor-pointer rounded-lg px-3 py-1.5 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    下一页
                  </button>
                </div>
              )}
            </>
          )}
        </section>
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

      {/* 审核材料弹窗 */}
      {approvalMaterialsProject && (
        <ApprovalMaterialsWorkbenchModal
          project={approvalMaterialsProject}
          projectMembers={members[approvalMaterialsProject.id] ?? []}
          tasks={projectTasksMap[approvalMaterialsProject.id] ?? []}
          subtasks={projectSubtasksMap[approvalMaterialsProject.id] ?? []}
          canReview={(() => {
            const roles = getProjectRoles(approvalMaterialsProject.id)
            return roles.isRealProjectCeo || roles.isSuperAdmin
          })()}
          loading={approveLoading}
          onClose={() => !approveLoading && setApprovalMaterialsProject(null)}
          onApprove={() => void handleApprove(approvalMaterialsProject)}
          onReturn={() => void handleReturn(approvalMaterialsProject.id, approvalMaterialsProject.name)}
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

      <ProjectCloseFlowDrawer
        open={closeFlowProjectId !== null}
        project={closeFlowProjectId !== null ? projects.find((project) => project.id === closeFlowProjectId) ?? null : null}
        currentPersonId={myPersonId ?? null}
        roles={closeFlowProjectId !== null ? getProjectRoles(closeFlowProjectId) : { isSuperAdmin: false, isCompanyCeo: false, isRealProjectCeo: false, isRealOwner: false }}
        initialRequestId={closeFlowRequestId}
        onClose={closeCloseFlow}
        onChanged={refreshProjectCloseState}
      />

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
  project, status, teamLine, mainAction, mainBusy, showReturn, isSelected, hasMore,
  onSelect, onMainAction, onReturn, onOpenMore,
}: {
  project: Project
  status: string
  teamLine: { ceoText: string; ownerText: string; coordinatorText: string; memberText: string }
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

  return (
    <div
      onClick={onSelect}
      className={`projects-lifecycle-card projects-lifecycle-queue-card relative cursor-pointer overflow-hidden rounded-xl border bg-white px-4 py-3 transition-all ${isSelected ? 'border-sky-200 bg-sky-50/30 shadow-sm' : 'border-slate-200 hover:border-slate-300 hover:shadow-sm'}`}
      style={{ boxShadow: '0 1px 4px rgba(15,23,42,0.05)' }}
    >
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${isSelected ? 'bg-sky-600' : 'bg-transparent'}`} />
      <div className="projects-lifecycle-card-title-row flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-sm font-bold text-slate-800">{project.name}</h3>
            <span className={`flex-shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${statusBadge.className}`}>{statusBadge.label}</span>
            {projectType && <span className="flex-shrink-0 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-500">{projectType}</span>}
          </div>
        </div>
        {hasMore && (
          <button type="button" onClick={(e) => { e.stopPropagation(); onOpenMore(e.currentTarget) }}
            className="cursor-pointer rounded-lg border border-slate-200 px-2 py-1 text-xs font-semibold text-slate-400 hover:bg-slate-50">
            ⋯
          </button>
        )}
      </div>

      <p className="projects-lifecycle-card-stage-row mt-2 flex items-start gap-1.5 text-xs leading-relaxed text-slate-600">
        <span className="mt-[3px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#2170e4]" />
        <span className="sr-only">当前阶段：</span>
        <span>{stageDesc}</span>
      </p>

      <div className="projects-lifecycle-card-people-line mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-600">
        <span>项目负责人：{teamLine.ownerText}</span>
        <span>企业教练：{teamLine.ceoText}</span>
      </div>

      <div className="projects-lifecycle-card-footer-row projects-lifecycle-card-meta-row mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-500">
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          <span>项目周期：{formatPlanTimeShort(project.start_date, project.end_date)}</span>
        </div>
      </div>

      <div className="projects-lifecycle-card-action-row mt-2 flex items-center justify-end gap-2 border-t border-slate-100 pt-2" onClick={(e) => e.stopPropagation()}>
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

export function DetailPanel({
  project, projectMembers, tasks, subtasks, roles, onClose, wide,
  onEdit, onDispatch, onOwnerSubmit, onOpenApprovalMaterials, onReturn, onWorkProgress, onOpenCloseFlow, onOpenArchive,
}: {
  project: Project
  projectMembers: ProjectMember[]
  tasks: TaskItem[]
  subtasks: SubTaskWithParent[]
  roles: { isSuperAdmin: boolean; isCompanyCeo: boolean; isRealProjectCeo: boolean; isRealOwner: boolean }
  onClose: () => void
  onEdit: () => void
  onDispatch: () => void
  onOwnerSubmit: () => void
  onOpenApprovalMaterials: () => void
  onReturn: () => void
  onWorkProgress: () => void
  onOpenCloseFlow: () => void
  onOpenArchive: () => void
  wide?: boolean
}) {
  const status = getProjectPrimaryStatus(project)
  const statusBadge = getProjectStatusBadge(project)
  const teamLine = summarizeProjectRoleLine(projectMembers, project)
  const summary = getDraftSummary(tasks, subtasks, project)
  const stageDesc = STAGE_DESCRIPTIONS[status] ?? ''
  const actionReminder = ACTION_REMINDERS[status] ?? stageDesc
  const showReturn = status === 'pending_review' && (roles.isRealProjectCeo || roles.isSuperAdmin)
  const canEditDraft = roles.isSuperAdmin || roles.isCompanyCeo
  const coreReady = Boolean(project.name?.trim() && project.objectives?.trim())
  const draftReady = summary.taskCount > 0 && summary.subtaskCount > 0
  const projectType = project.project_type?.trim() || '未填写'
  const clientName = project.client_name?.trim() || '内部项目 / 未填写'

  const infoBlock = (label: string, value?: string, fullWidth?: boolean) => (
    <div className={`min-w-0 ${fullWidth ? 'col-span-2' : ''}`}>
      <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">{label}</div>
      <div className={`mt-1 text-xs font-semibold leading-relaxed text-slate-700 ${wide ? '' : 'truncate'}`} title={value?.trim() || '未填写'}>{value?.trim() || '未填写'}</div>
    </div>
  )

  // 操作按钮定义
  const actionButtons: Array<{ label: string; primary?: boolean; danger?: boolean; onClick: () => void }> = []
  if (status === 'draft' && canEditDraft) {
    actionButtons.push({ label: '编辑项目', primary: true, onClick: onEdit })
    actionButtons.push({ label: '下发给负责人', onClick: onDispatch })
  }
  if (status === 'dispatched' && roles.isRealOwner) {
    actionButtons.push({ label: '完善立项信息', primary: true, onClick: onOwnerSubmit })
  }
  if (status === 'pending_review') {
    actionButtons.push({ label: '查看审核材料', primary: true, onClick: onOpenApprovalMaterials })
  }
  if (showReturn) {
    actionButtons.push({ label: '退回修改', danger: true, onClick: onReturn })
  }
  if (status === 'returned' && roles.isRealOwner) {
    actionButtons.push({ label: '修改立项信息', primary: true, onClick: onOwnerSubmit })
  }
  if (status === 'active') {
    actionButtons.push({ label: '进入工作推进表', primary: true, onClick: onWorkProgress })
    if (roles.isRealOwner || roles.isSuperAdmin) actionButtons.push({ label: '申请项目结束', onClick: onOpenCloseFlow })
  }
  if (status === 'pending_close') {
    actionButtons.push({ label: roles.isRealProjectCeo || roles.isSuperAdmin ? '审核结束申请' : '查看结束申请', primary: true, onClick: onOpenCloseFlow })
  }
  if (status === 'ended') {
    actionButtons.push({ label: '查看结束档案', onClick: onOpenCloseFlow })
  }
  if (status === 'archived') {
    actionButtons.push({ label: '查看项目档案', onClick: onOpenArchive })
  }

  const reminderTone = getReminderToneClass(status)

  const panelContent = (
    <>
      {/* 头部 */}
      <div className={`border-b border-slate-200 bg-white ${wide ? 'px-6 py-5' : 'px-5 py-4'}`}>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className={`truncate font-bold text-slate-900 ${wide ? 'text-xl' : 'text-lg'}`}>{project.name}</h2>
              <span className={`flex-shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${statusBadge.className}`}>{statusBadge.label}</span>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-500">{projectType}</span>
            </div>
            {/* 处理提醒 - 更轻量的样式 */}
            <div className={`mt-3 rounded-md border-l-4 px-3 py-2 ${reminderTone}`}>
              <div className="flex items-start gap-2">
                <svg className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <p className="text-xs leading-relaxed opacity-90">{actionReminder}</p>
              </div>
            </div>
          </div>
          <button type="button" onClick={onClose}
            className="flex-shrink-0 rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
      </div>

      {/* 宽屏布局：左右分栏 */}
      {wide ? (
        <div className="flex flex-1 gap-0 overflow-hidden">
          {/* 左侧：操作 + 完备度 */}
          <div className="w-[340px] flex-shrink-0 border-r border-slate-200 bg-slate-50/50 px-6 py-5">
            <p className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">下一步操作</p>
            <div className="space-y-2">
              {actionButtons.map((btn) => (
                <button
                  key={btn.label}
                  type="button"
                  onClick={btn.onClick}
                  className={`w-full rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors ${
                    btn.primary
                      ? 'bg-slate-900 text-white hover:bg-slate-800'
                      : btn.danger
                        ? 'border border-orange-200 bg-orange-50 text-orange-700 hover:bg-orange-100'
                        : 'border border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {btn.label}
                </button>
              ))}
            </div>

            <div className="mt-6">
              <p className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">立项资料完备度</p>
              <div className="space-y-2">
                {[
                  { label: '项目核心信息', value: coreReady ? '已完善' : '未完善', ready: coreReady },
                  { label: '工作推进表雏形', value: draftReady ? '已维护' : '未完善', ready: draftReady },
                  { label: '重点工作数量', value: String(summary.taskCount), ready: summary.taskCount > 0 },
                  { label: '关键任务数量', value: String(summary.subtaskCount), ready: summary.subtaskCount > 0 },
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between rounded-lg border border-slate-100 bg-white px-3 py-2 text-xs">
                    <span className="font-medium text-slate-600">{item.label}</span>
                    <span className={item.ready ? 'font-semibold text-emerald-600' : 'font-semibold text-orange-600'}>{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 右侧：核心信息 + 角色 */}
          <div className="flex-1 overflow-y-auto px-6 py-5">
            <section className="mb-6">
              <p className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">项目核心信息</p>
              <div className="grid grid-cols-2 gap-x-6 gap-y-4 rounded-xl border border-slate-100 bg-white px-5 py-4">
                {infoBlock('项目完成准则 / 验收标准', project.objectives, true)}
                {infoBlock('项目周期', formatPlanTimeShort(project.start_date, project.end_date))}
                {infoBlock('客户名称', clientName)}
                {infoBlock('项目类型', projectType)}
              </div>
            </section>

            <section className="mb-6">
              <p className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">项目角色</p>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: '企业教练', value: teamLine.ceoText },
                  { label: '项目负责人', value: teamLine.ownerText },
                  { label: '统筹人', value: teamLine.coordinatorText },
                  { label: '成员', value: teamLine.memberText },
                ].map((item) => (
                  <div key={item.label} className="rounded-lg border border-slate-100 bg-white px-4 py-3">
                    <div className="text-[11px] font-semibold text-slate-400">{item.label}</div>
                    <div className="mt-1 text-sm font-semibold text-slate-700">{item.value}</div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </div>
      ) : (
        <>
          {/* 窄屏：原垂直堆叠布局 */}
          <section className="border-b border-slate-200 px-5 py-4">
            <p className="mb-2 text-xs font-bold text-slate-500">下一步操作</p>
            <div className="space-y-2">
              {actionButtons.map((btn) => (
                <button
                  key={btn.label}
                  type="button"
                  onClick={btn.onClick}
                  className={`w-full rounded-lg px-4 py-2 text-sm font-semibold transition-colors ${
                    btn.primary
                      ? 'bg-slate-900 text-white hover:bg-slate-800'
                      : btn.danger
                        ? 'border border-orange-200 bg-orange-50 text-orange-700 hover:bg-orange-100'
                        : 'border border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {btn.label}
                </button>
              ))}
            </div>
          </section>

          <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
            <section>
              <p className="mb-2 text-xs font-bold text-slate-500">项目核心信息</p>
              <div className="grid grid-cols-2 gap-x-5 gap-y-3 rounded-lg border border-slate-100 bg-white px-4 py-3">
                {infoBlock('项目周期', formatPlanTimeShort(project.start_date, project.end_date))}
                {infoBlock('项目完成准则 / 验收标准', project.objectives)}
                {infoBlock('客户名称', clientName)}
                {infoBlock('项目类型', projectType)}
              </div>
            </section>

            <section>
              <p className="mb-2 text-xs font-bold text-slate-500">项目角色</p>
              <div className="flex flex-wrap gap-2">
                {[
                  `企业教练：${teamLine.ceoText}`,
                  `项目负责人：${teamLine.ownerText}`,
                  `统筹人：${teamLine.coordinatorText}`,
                  `成员：${teamLine.memberText}`,
                ].map((item) => (
                  <span key={item} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600">{item}</span>
                ))}
              </div>
            </section>

            <section>
              <p className="mb-2 text-xs font-bold text-slate-500">立项资料完备度</p>
              <div className="space-y-2">
                {[
                  { label: '项目核心信息：', value: coreReady ? '已完善' : '未完善', ready: coreReady },
                  { label: '工作推进表雏形：', value: draftReady ? '已维护' : '未完善', ready: draftReady },
                  { label: '重点工作数量', value: String(summary.taskCount), ready: summary.taskCount > 0 },
                  { label: '关键任务数量', value: String(summary.subtaskCount), ready: summary.subtaskCount > 0 },
                ].map((item) => (
                  <div key={item.label} className="flex items-center justify-between rounded-lg border border-slate-100 bg-white px-3 py-2 text-xs">
                    <span className="font-medium text-slate-600">{item.label}</span>
                    <span className={item.ready ? 'font-semibold text-emerald-600' : 'font-semibold text-orange-600'}>{item.value}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </>
      )}
    </>
  )

  return (
    <div className={`flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm ${wide ? 'max-h-[calc(100vh-140px)]' : 'max-h-[calc(100vh-170px)]'}`}>
      {panelContent}
    </div>
  )
}

// ── 类 Excel 草案明细表 ──────────────────────────────────────

function DraftProgressTable({ rows }: { rows: DraftRow[] }) {
  const cols = ['重点工作', '目标成果 / 验收标准', '关键任务', '责任人', '协助人', '时间段', '备注 / 标准']
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
              <td className="border-b border-r px-2 py-1.5 font-semibold text-slate-700" style={{ borderColor: '#E2E8F0', maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.keyTask}>{row.keyTask}</td>
              <td className="border-b border-r px-2 py-1.5 text-slate-600" style={{ borderColor: '#E2E8F0', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.standard}>{row.standard}</td>
              <td className={`border-b border-r px-2 py-1.5 ${row.isTaskOnly ? 'text-orange-500' : 'text-slate-700'}`} style={{ borderColor: '#E2E8F0', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.subTask}>{row.subTask}</td>
              <td className="border-b border-r px-2 py-1.5 text-slate-600" style={{ borderColor: '#E2E8F0', whiteSpace: 'nowrap' }}>{row.assignee}</td>
              <td className="border-b border-r px-2 py-1.5 text-slate-600" style={{ borderColor: '#E2E8F0', maxWidth: 90, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.collaborator}>{row.collaborator}</td>
              <td className="border-b border-r px-2 py-1.5 text-slate-500" style={{ borderColor: '#E2E8F0', whiteSpace: 'nowrap' }}>{row.planRange}</td>
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

export function ApprovalMaterialsWorkbenchModal({
  project,
  projectMembers,
  tasks,
  subtasks,
  canReview,
  loading,
  onClose,
  onApprove,
  onReturn,
}: {
  project: Project
  projectMembers: ProjectMember[]
  tasks: TaskItem[]
  subtasks: SubTaskWithParent[]
  canReview: boolean
  loading: boolean
  onClose: () => void
  onApprove: () => void
  onReturn: () => void
}) {
  const teamLine = summarizeProjectRoleLine(projectMembers, project)
  const draftSummary = getDraftSummary(tasks, subtasks, project)
  const draftRows = buildDraftRows(tasks, subtasks, project)
  const projectType = project.project_type?.trim() || '未填写'
  const clientName = project.client_name?.trim() || '内部项目 / 未填写'
  const background = project.background?.trim() || '未填写'
  const expectedOutcomes = project.expected_outcomes?.trim() || '未填写'
  const projectPeriod = formatPlanTimeShort(project.start_date, project.end_date)

  const rowsForTask = (task: TaskItem) => {
    const taskTitle = task.key_task || '—'
    return draftRows.filter((row) => row.keyTask === taskTitle)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-4"
      style={{ background: 'rgba(15,23,42,0.45)' }}
      onClick={() => !loading && onClose()}
    >
      <div
        className="projects-approval-workbench-shell flex h-[90vh] w-[96vw] max-w-[1280px] flex-col overflow-hidden rounded-xl bg-[#f6f9ff] text-slate-900 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="projects-approval-workbench-header flex h-[72px] shrink-0 items-center justify-between border-b border-[#e0c0b1] bg-white px-6">
          <div className="flex min-w-0 items-center gap-4">
            <div className="h-10 w-1.5 rounded-full bg-orange-500" aria-hidden="true" />
            <div className="min-w-0">
              <h2 className="truncate text-lg font-semibold tracking-[-0.01em] text-slate-900">
                查看审核材料 — {project.name}
              </h2>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className="rounded border border-orange-200 bg-orange-50 px-2 py-0.5 text-[11px] font-medium text-orange-800">
                  待企业教练审核
                </span>
                <span className="text-xs font-semibold text-slate-600">立项方案审核材料</span>
                <span className="text-xs text-slate-500">
                  负责人已提交立项信息和工作推进方案，请审核项目完成准则、重点工作和关键任务安排。
                </span>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="ml-4 rounded-full px-3 py-2 text-xl leading-none text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700"
            aria-label="关闭"
          >
            ×
          </button>
        </header>

        <main className="projects-approval-workbench-main flex-1 overflow-y-auto bg-[#f6f9ff] pb-8">
          <div className="projects-approval-workbench-columns mx-auto flex max-w-[1440px] items-start gap-6 px-6 py-6">
            <aside className="projects-approval-left-pane sticky top-6 w-[400px] shrink-0 space-y-6">
              <section className="overflow-hidden rounded-xl border border-[#e0c0b1]/70 bg-white shadow-sm">
                <h3 className="sr-only">项目核心信息</h3>
                <div className="space-y-6 p-6">
                  <div className="space-y-2">
                    <div className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500">项目名称</div>
                    <div className="text-lg font-semibold text-slate-900">{project.name}</div>
                  </div>
                  <div className="space-y-2">
                    <div className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500">项目周期 / 时间段</div>
                    <div className="text-base text-slate-800">{projectPeriod}</div>
                  </div>
                  <div className="space-y-2">
                    <div className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500">项目完成准则 / 验收标准</div>
                    <div className="rounded-lg border border-slate-200 bg-white px-3 py-3 text-sm leading-relaxed text-slate-700">
                      {project.objectives?.trim() || '未填写'}
                    </div>
                  </div>

                  <section className="projects-approval-role-pills space-y-2">
                    <div className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500">项目角色</div>
                    <div className="flex flex-wrap gap-2 text-xs text-slate-600">
                      <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1">企业教练：{teamLine.ceoText}</span>
                      <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1">项目负责人：{teamLine.ownerText}</span>
                      <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1">统筹人：{teamLine.coordinatorText}</span>
                      <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1">成员：{teamLine.memberText}</span>
                    </div>
                  </section>

                  <details className="group mt-4">
                    <summary className="projects-approval-supplement-summary flex cursor-pointer select-none items-center gap-2 rounded-lg border border-orange-100 bg-orange-50/40 px-3 py-2 text-sm font-semibold text-orange-700 outline-none transition-colors hover:bg-orange-50 focus-visible:ring-2 focus-visible:ring-orange-200">
                      <span className="text-base leading-none transition-transform group-open:rotate-90">›</span>
                      补充详细信息
                    </summary>
                    <div className="mt-4 space-y-4 border-t border-slate-200/80 pt-4 text-sm text-slate-700">
                      <div>
                        <div className="text-[11px] font-semibold text-slate-500">客户名称</div>
                        <div className="mt-1">{clientName}</div>
                      </div>
                      <div>
                        <div className="text-[11px] font-semibold text-slate-500">项目类型</div>
                        <div className="mt-1">{projectType}</div>
                      </div>
                      <div>
                        <div className="text-[11px] font-semibold text-slate-500">项目背景</div>
                        <div className="mt-1 leading-relaxed">{background}</div>
                      </div>
                      <div>
                        <div className="text-[11px] font-semibold text-slate-500">补充说明</div>
                        <div className="mt-1 leading-relaxed">{expectedOutcomes}</div>
                      </div>
                    </div>
                  </details>
                </div>
              </section>
            </aside>

            <section className="projects-approval-right-pane min-w-0 flex-1">
              <div className="mb-4 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <h3 className="text-lg font-semibold text-slate-900">工作推进方案</h3>
                  <span className="text-sm italic text-slate-500">
                    只读审核视图：核对重点工作方向、目标成果与关键任务执行安排。
                  </span>
                </div>
                <div className="flex shrink-0 gap-2 text-xs">
                  <span className="rounded-lg border border-orange-200 bg-white px-3 py-2 font-semibold text-orange-700">
                    重点工作 {draftSummary.taskCount}
                  </span>
                  <span className="rounded-lg border border-orange-200 bg-white px-3 py-2 font-semibold text-orange-700">
                    关键任务 {draftSummary.subtaskCount}
                  </span>
                </div>
              </div>

              {tasks.length === 0 ? (
                <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-400">
                  暂无工作推进表雏形
                </div>
              ) : (
                <div>
                  {tasks.map((task, taskIndex) => {
                    const rows = rowsForTask(task)
                    return (
                      <div key={task.id ?? taskIndex} className="mb-6 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                        <div className="flex items-start gap-4 border-b border-slate-200 bg-slate-100/70 px-6 py-4">
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-orange-50 text-lg font-semibold text-orange-700">
                            {taskIndex + 1}
                          </div>
                          <div className="grid flex-1 grid-cols-1 gap-4 md:grid-cols-2">
                            <div>
                              <div className="block text-[10px] font-semibold uppercase text-slate-500/80">重点工作名称</div>
                              <div className="mt-1 text-lg font-semibold text-slate-900">{task.key_task || '未填写'}</div>
                            </div>
                            <div>
                              <div className="block text-[10px] font-semibold uppercase text-slate-500/80">目标成果 / 验收标准</div>
                              <div className="mt-1 text-sm leading-relaxed text-slate-600">{task.completion_standard?.trim() || '未填写'}</div>
                            </div>
                          </div>
                        </div>

                        <div className="overflow-x-auto">
                          <table className="w-full border-collapse text-left text-sm">
                            <thead>
                              <tr className="border-b border-slate-200/80 bg-slate-50/80 text-[11px] font-semibold text-slate-500">
                                <th className="w-[250px] py-2 pl-6 pr-3">关键任务</th>
                                <th className="w-[100px] px-3 py-2">责任人</th>
                                <th className="w-[100px] px-3 py-2">协助人</th>
                                <th className="w-[160px] px-3 py-2">时间段</th>
                                <th className="px-3 py-2">备注 / 标准</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                              {rows.map((row, rowIndex) => (
                                <tr key={`${row.keyTask}-${row.subTask}-${rowIndex}`} className="hover:bg-slate-50">
                                  <td className="py-3 pl-6 pr-3 text-sm text-slate-800">{row.subTask}</td>
                                  <td className="px-3 py-3 text-sm text-slate-700">{row.assignee}</td>
                                  <td className="px-3 py-3 text-sm text-slate-600">{row.collaborator}</td>
                                  <td className="px-3 py-3 text-sm text-slate-600">{row.planRange}</td>
                                  <td className="px-3 py-3 text-sm text-slate-600">{row.note}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}

            </section>
          </div>
        </main>

        <footer className="projects-approval-workbench-footer flex h-[72px] shrink-0 items-center justify-between border-t border-[#e0c0b1] bg-white px-6 shadow-[0_-4px_12px_-2px_rgba(0,0,0,0.05)]">
          <button
            type="button"
            onClick={onClose}
            className="h-10 rounded-lg border border-slate-300 px-6 text-sm font-semibold text-slate-600 transition-colors hover:bg-slate-50"
          >
            关闭
          </button>
          {canReview && (
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={onReturn}
                disabled={loading}
                className="h-10 rounded-lg border border-orange-300 bg-white px-6 text-sm font-semibold text-orange-700 transition-colors hover:bg-orange-50 disabled:opacity-50"
              >
                退回修改
              </button>
              <button
                type="button"
                onClick={onApprove}
                disabled={loading}
                className="h-10 rounded-lg bg-orange-600 px-10 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-orange-700 disabled:opacity-50"
              >
                {loading ? '处理中…' : '审核通过'}
              </button>
            </div>
          )}
        </footer>
      </div>
    </div>
  )
}
