import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  getPending,
  confirmSubmission,
  rejectSubmission,
  transferCoordinator,
  escalateCeo,
  confirmTaskCard,
  rejectTaskCard,
  transferTaskCardCoordinator,
  escalateTaskCardCeo,
  ceoDecide,
  ceoDecideTaskCard,
  coordinatorFeedback,
} from '../api/confirmations'
import { fetchMyUpdates } from '../api/updates'
import { fetchSubtasksByAssignee, type SubTaskWithParent } from '../api/subtasks'
import { fetchTasks } from '../api/tasks'
import { useProject } from '../context/ProjectContext'
import type { ConfirmationItem, TaskItem } from '../types'
import { fmtFull, fmtShort } from '../utils/time'
import * as SS from '../domain/submissionStatus'
import { getConfirmationContext } from '../domain/confirmationFlow'
import { isProjectArchived } from '../domain/projectLifecycleStatus'
import { buildConfirmationTaskCards, normalizeReviewCardData } from '../domain/confirmationTaskCards'
import { getProjectDisplayName } from '../domain/projectDisplay'

type WriteMode = 'task_new' | 'subtask_update' | 'subtask_new'
type ConfirmViewMode = 'mine' | 'all' | 'coordinator' | 'ceo'

const REVIEWER_PROJECT_ROLES = new Set(['owner', 'coordinator', 'project_ceo', 'super_admin'])

function fmtTime(s?: string | null) { return fmtFull(s) }

function renderVal(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—'
  if (Array.isArray(v)) {
    if (v.length === 0) return '—'
    return v.map((item) => {
      if (typeof item === 'object' && item !== null) {
        const o = item as Record<string, unknown>
        return String(o.name ?? o.description ?? '')
      }
      return String(item)
    }).filter(Boolean).join('、')
  }
  if (typeof v === 'number') return v < 1 ? `${Math.round(v * 100)}%` : String(v)
  return String(v)
}

const STATUS_DOT: Record<string, string> = {
  '进行中': '#3B82F6', '已完成': '#10B981', '延期': '#EF4444', '暂缓': '#F59E0B', '未开始': '#94A3B8',
}

const ISSUE_STYLE: Record<string, { bg: string; text: string }> = {
  '风险':   { bg: '#FEE2E2', text: '#991B1B' },
  '待协调': { bg: '#DBEAFE', text: '#1D4ED8' },
  '需决策': { bg: '#EDE9FE', text: '#5B21B6' },
  '问题':   { bg: '#FEF3C7', text: '#92400E' },
}

const ISSUE_PRIORITY: Record<string, number> = { '需决策': 4, '风险': 3, '待协调': 2, '问题': 1 }

function deduplicateIssues(issues: Record<string, unknown>[]): Record<string, unknown>[] {
  const seen = new Map<string, Record<string, unknown>>()
  for (const issue of issues) {
    const desc = String(issue.description || '').trim()
    if (!desc) continue
    const existing = seen.get(desc)
    if (!existing) {
      seen.set(desc, issue)
    } else {
      const ep = ISSUE_PRIORITY[String(existing.issue_type || '问题')] ?? 1
      const np = ISSUE_PRIORITY[String(issue.issue_type || '问题')] ?? 1
      if (np > ep) seen.set(desc, issue)
    }
  }
  return Array.from(seen.values())
}

function SourceBadge({ type }: { type?: string }) {
  if (!type || type === '语音更新') return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold" style={{ background: '#EFF6FF', border: '1px solid #BFDBFE', color: '#1D4ED8' }}>
      <svg style={{ width: 10, height: 10 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" /></svg>
      {type || '语音更新'}
    </span>
  )
  if (type === '会议纪要') return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold" style={{ background: '#F0FDF4', border: '1px solid #BBF7D0', color: '#15803D' }}>
      <svg style={{ width: 10, height: 10 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
      会议纪要
    </span>
  )
  return <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold bg-slate-100 text-slate-600">{type}</span>
}

function StatusBadge({ status }: { status?: string }) {
  const norm = SS.normalize(status)
  const cls = SS.STATUS_BADGE_CLASS[norm] ?? 'bg-slate-100 text-slate-600'
  const label = SS.DISPLAY_LABEL[norm] ?? (status ?? '-')
  return <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${cls}`}>{label}</span>
}

function ConfBadge({ val }: { val?: number | null }) {
  if (!val) return <span className="text-slate-400 text-xs">-</span>
  const pct = val < 1 ? Math.round(val * 100) : Math.round(val)
  const color = pct >= 85 ? '#059669' : pct >= 70 ? '#D97706' : '#DC2626'
  return <span style={{ color, fontWeight: 700, fontSize: 11 }}>{pct}%</span>
}

function getConfirmActionLabel(status?: string) {
  const norm = SS.normalize(status)
  if (norm === SS.S_CONFIRMED) return '确认入库'
  if (norm === SS.S_RETURNED) return '退回修改'
  if (norm === SS.S_WAITING_COORDINATOR) return '转交统筹人'
  if (norm === SS.S_WAITING_CEO) return '转交企业教练'
  if (norm === SS.S_PENDING_OWNER) return '待项目负责人处理'
  return '提交待确认'
}

function getConfirmActionSummary(item: ConfirmationItem) {
  const r = item as Record<string, unknown>
  const ai = (() => {
    try {
      const raw = r.ai_result_json
      return raw ? JSON.parse(String(raw)) as Record<string, unknown> : null
    } catch {
      return null
    }
  })()
  return String(ai?.summary || r.title || r.related_task || '变更记录')
}

function getConfirmActionNote(item: ConfirmationItem) {
  const note = String(item.reject_reason || item.coordinator_note || item.ceo_note || '').trim()
  if (note) return note
  const status = SS.normalize(item.confirm_status)
  if (status === SS.S_CONFIRMED) return '已完成确认并写入'
  if (status === SS.S_RETURNED) return '记录已退回，等待重新编辑'
  if (status === SS.S_WAITING_COORDINATOR) return '等待统筹人继续处理'
  if (status === SS.S_WAITING_CEO) return '等待企业教练决策'
  return '等待审核'
}

function Ava({ name }: { name: string }) {
  const COLORS = ['#3B82F6', '#8B5CF6', '#10B981', '#F59E0B', '#EF4444', '#06B6D4']
  const c = COLORS[(name.charCodeAt(0) || 0) % COLORS.length]
  return (
    <div className="w-6 h-6 rounded-full flex items-center justify-center text-white flex-shrink-0" style={{ background: c, fontSize: 11, fontWeight: 700 }}>
      {name.slice(0, 1)}
    </div>
  )
}

function ToggleSwitch({ on }: { on: boolean }) {
  return (
    <div className="relative flex-shrink-0" style={{ width: 36, height: 20 }}>
      <div className="absolute inset-0 rounded-full transition-colors" style={{ background: on ? '#0369A1' : '#E2E8F0' }} />
      <div className="absolute rounded-full bg-white transition-transform" style={{ width: 14, height: 14, top: 3, left: 3, boxShadow: '0 1px 3px rgba(0,0,0,0.2)', transform: on ? 'translateX(16px)' : 'translateX(0)' }} />
    </div>
  )
}

function TaskCardList({ title, items, emptyText, tone }: { title: string; items: string[]; emptyText: string; tone: 'done' | 'issue' | 'next' | 'achievement' }) {
  const style = {
    done: { bg: '#ECFDF5', border: '#BBF7D0', text: '#059669', icon: '✓' },
    issue: { bg: '#FFF7ED', border: '#FED7AA', text: '#D97706', icon: '!' },
    next: { bg: '#EFF6FF', border: '#BFDBFE', text: '#2563EB', icon: '→' },
    achievement: { bg: '#F5F3FF', border: '#DDD6FE', text: '#7C3AED', icon: '♕' },
  }[tone]
  const visibleItems = items.slice(0, 4)
  const moreCount = Math.max(items.length - visibleItems.length, 0)
  return (
    <section className="rounded-2xl border bg-white p-4 min-h-[180px] flex flex-col" style={{ borderColor: style.border }}>
      <div className="flex items-center gap-2">
        <span className="w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0" style={{ background: style.bg, color: style.text }}>{style.icon}</span>
        <p className="text-base font-bold text-slate-900">{title}</p>
      </div>
      <div className="mt-4 space-y-3 flex-1">
        {visibleItems.length > 0 ? visibleItems.map((item, idx) => (
          <div key={`${item}-${idx}`} className="flex items-start gap-2 text-[13px] text-slate-700">
            <span className="mt-2 w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: style.text }} />
            <span className="leading-6 overflow-hidden" style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>{item}</span>
          </div>
        )) : (
          <p className="text-[13px] text-slate-400 leading-5">{emptyText}</p>
        )}
      </div>
      {moreCount > 0 && <p className="mt-3 text-xs font-semibold" style={{ color: style.text }}>还有 {moreCount} 条</p>}
    </section>
  )
}

function taskCardDecisionLabel(status?: string) {
  if (status === 'confirmed') return '已确认'
  if (status === 'returned') return '已退回'
  if (status === 'transferred_to_coordinator') return '已转统筹'
  if (status === 'pending_ceo_decision') return '已转企业教练'
  if (status === 'ceo_decided') return '企业教练已批示'
  return '未判断'
}

function taskCardDecisionTone(status?: string) {
  if (status === 'confirmed') return 'bg-emerald-50 text-emerald-600'
  if (status === 'returned') return 'bg-orange-50 text-orange-600'
  if (status === 'transferred_to_coordinator') return 'bg-violet-50 text-violet-600'
  if (status === 'pending_ceo_decision') return 'bg-slate-100 text-slate-600'
  if (status === 'ceo_decided') return 'bg-sky-50 text-sky-600'
  return 'bg-slate-100 text-slate-500'
}

function projectNameFromConfirmation(item: ConfirmationItem | null | undefined, projects: { id: number; name: string }[]) {
  return getProjectDisplayName(projects, item)
}

export function ConfirmPage() {
  const { currentProjectId, currentUser, projects, globalUserRoles, currentCapabilities } = useProject()
  const [searchParams, setSearchParams] = useSearchParams()
  const [items, setItems] = useState<ConfirmationItem[]>([])
  const [selected, setSelected] = useState<ConfirmationItem | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [acting, setActing] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)
  const [pendingAction, setPendingAction] = useState<'reject' | 'supplement' | 'forward' | 'ceo' | null>(null)
  const [actionNote, setActionNote] = useState('')
  const [opLogsOpen, setOpLogsOpen] = useState(false)
  const [selectedCardIndex, setSelectedCardIndex] = useState(0)
  const [cardDetailOpen, setCardDetailOpen] = useState(false)
  const [cardDecisions, setCardDecisions] = useState<Record<number, 'confirm' | 'return' | 'transfer' | 'ceo'>>({})

  const selectedProject = selected?.project_id != null ? projects.find((p) => p.id === selected.project_id) ?? null : null
  const projectArchived = isProjectArchived(selectedProject)

  const urlProjectId = useMemo(() => {
    const raw = searchParams.get('projectId')
    if (!raw) return null
    const id = Number(raw)
    return Number.isFinite(id) ? id : null
  }, [searchParams])

  const pendingProjectId = urlProjectId ?? currentProjectId
  const hasReviewerRoleInAnyProject = useMemo(() => {
    const fromProjects = projects.some((project) =>
      (project.user_roles ?? []).some((role) => REVIEWER_PROJECT_ROLES.has(role)),
    )
    const fromGlobalRoles = globalUserRoles.some((role) => REVIEWER_PROJECT_ROLES.has(role))
    return fromProjects || fromGlobalRoles
  }, [projects, globalUserRoles])

  const isReviewer = !!(
    currentCapabilities?.canConfirm ||
    currentCapabilities?.canCoordinate ||
    currentCapabilities?.canCeoDecide ||
    currentUser?.can_confirm_all ||
    currentUser?.can_view_all ||
    currentUser?.is_tech_admin ||
    currentUser?.system_role === 'super_admin' ||
    hasReviewerRoleInAnyProject
  )

  const canUseCoachDecisionView = Boolean(
    currentUser?.is_tech_admin ||
    globalUserRoles.includes('project_ceo') ||
    projects.some((project) =>
      (project.user_roles ?? []).includes('project_ceo'),
    )
  )

  const canUseCoordinatorView = Boolean(
    currentUser?.is_tech_admin ||
    globalUserRoles.includes('coordinator') ||
    projects.some((project) =>
      (project.user_roles ?? []).includes('coordinator'),
    )
  )

  const initialRedirectDone = useRef(false)
  const initialViewResolved = useRef(false)
  const defaultViewMode: ConfirmViewMode = isReviewer ? 'all' : 'mine'

  // 从 URL 解析初始视图
  const resolveInitialView = (): ConfirmViewMode => {
    const urlView = searchParams.get('view')
    if (urlView === 'ceo' && canUseCoachDecisionView) return 'ceo'
    if (urlView === 'coordinator' && canUseCoordinatorView) return 'coordinator'
    if (urlView === 'all' && isReviewer) return 'all'
    if (urlView === 'mine') return 'mine'
    return defaultViewMode
  }
  const [viewMode, setViewMode] = useState<ConfirmViewMode>(defaultViewMode)
  useEffect(() => {
    if (!initialRedirectDone.current) {
      initialRedirectDone.current = true
      if (!initialViewResolved.current) {
        initialViewResolved.current = true
        setViewMode(resolveInitialView())
      } else {
        setViewMode(defaultViewMode)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isReviewer, canUseCoachDecisionView])

  const [filterStatus, setFilterStatus] = useState(SS.S_NEW)
  const [filterProject, setFilterProject] = useState('')
  const [filterSubmitter, setFilterSubmitter] = useState('')
  const [search, setSearch] = useState('')

  // ceo / coordinator 视图下清除状态筛选
  const isCoachView = viewMode === 'ceo'
  const isCoordinatorView = viewMode === 'coordinator'

  // 统一 effect：深链初始化及手动切换时同步 filterStatus
  useEffect(() => {
    if (viewMode === 'ceo' || viewMode === 'coordinator') {
      setFilterStatus('')
    }
  }, [viewMode])

  function switchView(nextView: ConfirmViewMode) {
    if (isCoordinatorView && coordinatorActing) return
    setViewMode(nextView)
    setSelected(null)
    setActionNote('')
    setActionError(null)
    setActionSuccess(null)
    setCoachNote('')
    setCoachActing(false)
    setCoordinatorNote('')
    if (nextView === 'ceo' || nextView === 'coordinator') {
      setFilterStatus('')
    } else {
      setFilterStatus(SS.S_NEW)
    }
    // 同步 URL：保留 projectId，清除 submissionId 和 cardIndex
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set('view', nextView)
    nextParams.delete('submissionId')
    nextParams.delete('cardIndex')
    const rawProjectId = searchParams.get('projectId')
    if (rawProjectId) {
      nextParams.set('projectId', rawProjectId)
    }
    setSearchParams(nextParams, { replace: true })
  }

  const [writeMode, setWriteMode] = useState<WriteMode>('task_new')
  const [targetSubtaskId, setTargetSubtaskId] = useState<number | null>(null)
  const [targetTaskId, setTargetTaskId] = useState<number | null>(null)
  const [newSubtaskTitle, setNewSubtaskTitle] = useState('')
  const [writeToIssues, setWriteToIssues] = useState(true)
  const [writeToAchievements, setWriteToAchievements] = useState(false)

  const [pendingItemTypes, setPendingItemTypes] = useState<Record<number, string>>({})
  const [pendingItemHelpers, setPendingItemHelpers] = useState<Record<number, string>>({})
  const [pendingItemNotes, setPendingItemNotes] = useState<Record<number, string>>({})

  const [coachNote, setCoachNote] = useState('')
  const [coachActing, setCoachActing] = useState(false)

  const [coordinatorNote, setCoordinatorNote] = useState('')
  const [coordinatorActing, setCoordinatorActing] = useState(false)

  const coordinatorInteractionLocked = isCoordinatorView && coordinatorActing

  const [cardEditMode, setCardEditMode] = useState<Record<number, boolean>>({})
  const [cardProjOverride, setCardProjOverride] = useState<Record<number, string>>({})
  const [cardKeyTaskOverride, setCardKeyTaskOverride] = useState<Record<number, number | null>>({})
  const [cardSubtaskOverride, setCardSubtaskOverride] = useState<Record<number, number | null>>({})

  const [projectTasks, setProjectTasks] = useState<TaskItem[]>([])
  const [submitterSubtasks, setSubmitterSubtasks] = useState<SubTaskWithParent[]>([])
  const [suggestTaskSelections, setSuggestTaskSelections] = useState<Record<number, number | null>>({})

  const [editProject, setEditProject] = useState('')
  const [editStatus, setEditStatus] = useState('进行中')

  const urlSubmissionId = useMemo(() => {
    const raw = searchParams.get('submissionId')
    if (!raw) return null
    const id = Number(raw)
    return Number.isFinite(id) ? id : null
  }, [searchParams])
  const urlCardIndex = useMemo(() => {
    const raw = searchParams.get('cardIndex')
    if (raw === null || raw === '') return undefined
    const idx = Number(raw)
    return Number.isFinite(idx) && idx >= 0 ? idx : undefined
  }, [searchParams])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError(null)
    setSelected(null)
    setItems([])
    if (viewMode === 'mine') {
      fetchMyUpdates()
        .then((d) => {
          if (!cancelled) {
            const mapped = d as unknown as ConfirmationItem[]
            setItems(mapped)
            const firstPending = mapped.find(i => SS.normalize(i.confirm_status) === SS.S_NEW || SS.normalize(i.confirm_status) === SS.S_PENDING_OWNER) || mapped[0]
            if (firstPending) pickItem(firstPending)
          }
        })
        .catch(() => { if (!cancelled) setLoadError('记录加载失败，请刷新重试') })
        .finally(() => { if (!cancelled) setLoading(false) })
    } else if (viewMode === 'ceo') {
      const ceoProjectId = urlProjectId ?? null
      getPending(ceoProjectId, 'ceo', { includeCardLevel: true })
        .then((d) => {
          if (!cancelled) {
            setItems(d)
            // 优先选择 URL 指定的 submissionId
            if (urlSubmissionId != null) {
              const target = d.find(i => i.id === urlSubmissionId) || d[0]
              if (target) pickItem(target)
            } else {
              const first = d[0]
              if (first) pickItem(first)
            }
          }
        })
        .catch(() => { if (!cancelled) setLoadError('记录加载失败，请刷新重试') })
        .finally(() => { if (!cancelled) setLoading(false) })
    } else if (viewMode === 'coordinator') {
      const coordProjectId = urlProjectId ?? null
      getPending(coordProjectId, 'coordinator')
        .then((d) => {
          if (!cancelled) {
            setItems(d)
            if (urlSubmissionId != null) {
              const target = d.find(i => i.id === urlSubmissionId) || d[0]
              if (target) pickItem(target)
            } else {
              const first = d[0]
              if (first) pickItem(first)
            }
          }
        })
        .catch(() => { if (!cancelled) setLoadError('记录加载失败，请刷新重试') })
        .finally(() => { if (!cancelled) setLoading(false) })
    } else {
      getPending(pendingProjectId, 'all')
        .then((d) => {
          if (!cancelled) {
            setItems(d)
            const firstPending = d.find(i => SS.normalize(i.confirm_status) === SS.S_NEW || SS.normalize(i.confirm_status) === SS.S_PENDING_OWNER) || d[0]
            const target = urlSubmissionId != null
              ? d.find(i => i.id === urlSubmissionId) ?? (firstPending ?? null)
              : firstPending ?? null
            if (target) pickItem(target)
          }
        })
        .catch(() => { if (!cancelled) setLoadError('记录加载失败，请刷新重试') })
        .finally(() => { if (!cancelled) setLoading(false) })
    }
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProjectId, pendingProjectId, viewMode, urlProjectId, urlSubmissionId])

  function getAIResult(item: ConfirmationItem): Record<string, unknown> | null {
    try {
      const raw = (item as Record<string, unknown>).ai_result_json
      return raw ? JSON.parse(raw as string) : null
    } catch { return null }
  }

  function getHumanResult(item: ConfirmationItem): Record<string, unknown> | null {
    try {
      const raw = (item as Record<string, unknown>).human_result_json
      return raw ? JSON.parse(raw as string) : null
    } catch { return null }
  }

  function pickItem(item: ConfirmationItem) {
    setSelected(item)
    const r = getAIResult(item)
    const aiProject = getProjectDisplayName(projects, { ...(item as Record<string, unknown>), ...(r ?? {}) })
    const itemProjectId = item.project_id ?? pendingProjectId ?? currentProjectId
    const fallback = projects.find((p) => p.id === itemProjectId)?.name ?? (projects[0]?.name ?? '')
    setEditProject(aiProject || fallback)
    setEditStatus(String(r?.status_suggestion || '进行中'))
    setPendingAction(null)
    setActionNote('')
    setCoachNote('')
    setCoordinatorNote('')
    setActionError(null)
    setActionSuccess(null)
    setSuggestTaskSelections({})
    setNewSubtaskTitle(String(r?.related_task || ''))

    const h = getHumanResult(item)
    const hTaskId = h?.selected_task_id ? Number(h.selected_task_id) : null
    const hSubtaskId = h?.selected_subtask_id ? Number(h.selected_subtask_id) : null
    if (hSubtaskId) {
      setWriteMode('subtask_update'); setTargetSubtaskId(hSubtaskId); setTargetTaskId(null)
    } else if (hTaskId) {
      setWriteMode('subtask_new'); setTargetTaskId(hTaskId); setTargetSubtaskId(null)
    } else {
      setWriteMode('task_new'); setTargetSubtaskId(null); setTargetTaskId(null)
    }

    const submitter = item.submitter
    if (submitter) fetchSubtasksByAssignee(submitter, itemProjectId).then(setSubmitterSubtasks).catch(() => setSubmitterSubtasks([]))
    if (itemProjectId) fetchTasks(itemProjectId).then(setProjectTasks).catch(() => setProjectTasks([]))
    setPendingItemTypes({})
    setPendingItemHelpers({})
    setPendingItemNotes({})
    setCardEditMode({})
    setCardProjOverride({})
    setCardKeyTaskOverride({})
    setCardSubtaskOverride({})

    // 深链 cardIndex：ceo 视图下优先定位待决策卡
    if (isCoachView && urlCardIndex !== undefined) {
      const pendingIndices = item.pending_ceo_card_indices ?? []
      if (pendingIndices.includes(urlCardIndex)) {
        setSelectedCardIndex(urlCardIndex)
      } else if (pendingIndices.length > 0) {
        setSelectedCardIndex(pendingIndices[0])
      } else {
        setSelectedCardIndex(0)
      }
    } else if (isCoachView) {
      const pendingIndices = item.pending_ceo_card_indices ?? []
      setSelectedCardIndex(pendingIndices.length > 0 ? pendingIndices[0] : 0)
    } else if (urlCardIndex !== undefined) {
      setSelectedCardIndex(urlCardIndex)
    } else {
      setSelectedCardIndex(0)
    }

    setCardDetailOpen(false)
    setCardDecisions({})
  }

  async function handleConfirm() {
    if (!selected || !currentUser) return
    setActionError(null)
    setActionSuccess(null)
    setActing(true)
    try {
      const base = getHumanResult(selected) || getAIResult(selected) || {}
      const taskBase = (base.task as Record<string, unknown>) || {}
      const keyTask = String(taskBase.key_task || base.related_task || base.summary || '')
      const keyAchievement = String(
        taskBase.key_achievement ||
        (Array.isArray(base.completed_items)
          ? (base.completed_items as string[]).join('；')
          : (base.completed_items || ''))
      )
      const patchedTaskReports = Array.isArray(base.task_reports)
        ? (base.task_reports as Record<string, unknown>[]).map((r, i) => {
            if (r.result_type === 'suggest_new_subtask') {
              return { ...r, parent_task_id: suggestTaskSelections[i] ?? r.parent_task_id ?? null }
            }
            return r
          })
        : base.task_reports
      const humanResult: Record<string, unknown> = {
        ...base,
        special_project: editProject,
        write_task_reports_achievements: writeToAchievements,
        write_task_reports_issues: writeToIssues,
        task_reports: patchedTaskReports,
        task: {
          ...taskBase,
          key_task: writeMode === 'subtask_new' ? newSubtaskTitle : keyTask,
          key_achievement: keyAchievement,
          special_project: editProject,
          status: editStatus,
          write_task: hasTaskReports ? false : (writeMode === 'task_new'),
          write_mode: hasTaskReports ? 'task_reports' : writeMode,
          target_subtask_id: targetSubtaskId,
          target_task_id: targetTaskId,
        },
        achievements: ((base.achievements as unknown[]) || []).map((a) => ({
          ...(a as Record<string, unknown>),
          write_achievement: writeToAchievements,
        })),
        issues: ((base.issues as unknown[]) || []).map((i) => ({
          ...(i as Record<string, unknown>),
          write_issue: writeToIssues,
        })),
      }
      // pending_items: reviewer classifies each item; transform back to confirmations.py format
      if (hasPendingItems) {
        const classified = effectivePendingItems.map((item, idx) => {
          const type = pendingItemTypes[idx] !== undefined
            ? pendingItemTypes[idx]
            : String(item.issue_type || '问题')
          return {
            description: String(item.description || ''),
            issue_type: type,
            priority: String(item.priority || '中'),
            need_coordination: pendingItemHelpers[idx]
              ? [pendingItemHelpers[idx]]
              : (Array.isArray(item.need_coordination) ? item.need_coordination as string[] : []),
            ...(item.related_task_title ? { key_task_title: String(item.related_task_title) } : {}),
            ...(pendingItemNotes[idx] ? { decision_note: pendingItemNotes[idx] } : {}),
            write_issue: writeToIssues,
          }
        })
        if (hasTaskReports) {
          humanResult.key_task_issues = classified
          humanResult.task_reports = (humanResult.task_reports as Record<string, unknown>[]).map(r => ({
            ...r,
            subtask_issues: [],
          }))
        } else {
          humanResult.issues = classified
          humanResult.key_task_issues = []
        }
      }

      await confirmSubmission(selected.id, currentUser.name, humanResult)
      const updated = { ...selected, confirm_status: SS.S_CONFIRMED }
      setItems((prev) => prev.map((i) => i.id === selected.id ? updated : i))
      setSelected(updated)
      setActionSuccess('已确认入库')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setActionError(`操作失败：${msg}`)
    } finally { setActing(false) }
  }

  async function handleDecision(action: 'return' | 'transfer' | 'ceo') {
    if (!selected || !currentUser) return
    const note = actionNote.trim() || (
      action === 'return' ? '退回并重新编辑' : action === 'transfer' ? '转交统筹人' : '提交企业教练决策'
    )
    setActionError(null)
    setActionSuccess(null)
    setActing(true)
    try {
      if (action === 'return') {
        await rejectSubmission(selected.id, note, currentUser.name)
      } else if (action === 'transfer') {
        await transferCoordinator(selected.id, note, currentUser.name)
      } else {
        await escalateCeo(selected.id, note, currentUser.name)
      }
      const nextStatus = action === 'return'
        ? SS.S_RETURNED
        : action === 'transfer'
          ? SS.S_WAITING_COORDINATOR
          : SS.S_WAITING_CEO
      const updated = { ...selected, confirm_status: nextStatus }
      setItems((prev) => prev.map((i) => i.id === selected.id ? updated : i))
      setSelected(updated)
      setActionSuccess(action === 'return' ? '已退回' : action === 'transfer' ? '已转交统筹人' : '已提交企业教练决策')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setActionError(`操作失败：${msg}`)
    } finally {
      setActing(false)
    }
  }

  async function handleTaskCardDecision(action: 'confirm' | 'return' | 'transfer' | 'ceo') {
    if (!selected || !currentUser) return
    const note = actionNote.trim() || (
      action === 'return' ? '退回并重新编辑' : action === 'transfer' ? '转交统筹人' : action === 'ceo' ? '转交企业教练' : ''
    )
    setActionError(null)
    setActionSuccess(null)
    setActing(true)
    try {
      const response = action === 'confirm'
        ? await confirmTaskCard(selected.id, activeCardIndex, currentUser.name)
        : action === 'return'
          ? await rejectTaskCard(selected.id, activeCardIndex, note, currentUser.name)
          : action === 'transfer'
            ? await transferTaskCardCoordinator(selected.id, activeCardIndex, note, currentUser.name)
            : await escalateTaskCardCeo(selected.id, activeCardIndex, note, currentUser.name)
      const updatedSubmission = (response as { submission?: ConfirmationItem }).submission
      const updated = updatedSubmission || selected
      setItems((prev) => prev.map((i) => i.id === selected.id ? updated : i))
      setSelected(updated)
      setCardDecisions(prev => ({ ...prev, [activeCardIndex]: action }))
      setActionSuccess(action === 'confirm' ? '已确认入库' : action === 'return' ? '已退回' : action === 'transfer' ? '已转交统筹人' : '已转交企业教练')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setActionError(`操作失败：${msg}`)
    } finally {
      setActing(false)
    }
  }

  // 提交级企业教练批示
  async function handleCoachSubmissionDecide() {
    if (!selected || !currentUser || !coachNote.trim()) return
    setActionError(null)
    setActionSuccess(null)
    setCoachActing(true)
    try {
      await ceoDecide(selected.id, coachNote, currentUser.name)
      setActionSuccess('企业教练批示已提交，事项已返回项目负责人。')
      setCoachNote('')
      // 重新加载 ceo 待办
      reloadCoachItems()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setActionError(`操作失败：${msg}`)
    } finally {
      setCoachActing(false)
    }
  }

  // 单卡企业教练批示
  async function handleCoachCardDecide() {
    if (!selected || !currentUser || !coachNote.trim()) return
    setActionError(null)
    setActionSuccess(null)
    setCoachActing(true)
    try {
      await ceoDecideTaskCard(selected.id, activeCardIndex, coachNote, currentUser.name)
      setActionSuccess('任务卡批示已提交，已返回项目负责人继续处理。')
      setCoachNote('')
      // 重新加载后检查是否还有待办卡
      reloadCoachItems()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setActionError(`操作失败：${msg}`)
    } finally {
      setCoachActing(false)
    }
  }

  // 协调人反馈
  async function handleCoordinatorFeedback() {
    if (!selected || !currentUser || !coordinatorNote.trim()) return
    setActionError(null)
    setActionSuccess(null)
    setCoordinatorActing(true)
    try {
      await coordinatorFeedback(selected.id, coordinatorNote, currentUser.name)
      setActionSuccess('统筹意见已提交，事项已返回项目负责人。')
      setCoordinatorNote('')
      // 重新加载 coordinator 待办
      reloadCoordinatorItems()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setActionError(`操作失败：${msg}`)
    } finally {
      setCoordinatorActing(false)
    }
  }

  function reloadCoordinatorItems() {
    const coordProjectId = urlProjectId ?? null
    getPending(coordProjectId, 'coordinator')
      .then((d) => {
        setItems(d)
        const nextItem =
          selected
            ? d.find((item) => item.id === selected.id) ?? d[0]
            : d[0]
        if (nextItem) {
          pickItem(nextItem)
        } else {
          setSelected(null)
        }
      })
      .catch(() => {})
  }

  function reloadCoachItems() {
    const ceoProjectId = urlProjectId ?? null
    getPending(ceoProjectId, 'ceo', { includeCardLevel: true })
      .then((d) => {
        setItems(d)
        if (selected && d.length > 0) {
          // 尝试保持当前 submission
          const same = d.find(i => i.id === selected.id)
          if (same) {
            setSelected(same)
            // 查找下一张待决策卡
            const indices = same.pending_ceo_card_indices ?? []
            if (indices.length > 0) {
              setSelectedCardIndex(indices[0])
            }
          } else {
            setSelected(d[0] || null)
          }
        } else {
          setSelected(null)
        }
      })
      .catch(() => {})
  }

  const pendingCount = items.filter(i => SS.normalize(i.confirm_status) === SS.S_NEW || SS.normalize(i.confirm_status) === SS.S_PENDING_OWNER).length
  const allProjects = [...new Set(items.map((i) => String(projectNameFromConfirmation(i, projects) || '')).filter(Boolean))]
  const allSubmitters = [...new Set(items.map((i) => i.submitter).filter(Boolean))]

  const visibleItems = items.filter((item) => {
    if (filterStatus && SS.normalize(item.confirm_status) !== filterStatus) return false
    if (filterProject && projectNameFromConfirmation(item, projects) !== filterProject) return false
    if (filterSubmitter && item.submitter !== filterSubmitter) return false
    if (search) {
      const q = search.toLowerCase()
      const r = getAIResult(item)
      const summary = String(r?.summary || r?.special_project || item.title || '')
      if (!item.submitter.toLowerCase().includes(q) &&
          !String(projectNameFromConfirmation(item, projects) || '').toLowerCase().includes(q) &&
          !summary.toLowerCase().includes(q)) return false
    }
    return true
  })

  const opLogs = items.filter((i) => SS.normalize(i.confirm_status) !== SS.S_NEW).slice(0, 5)
  const selectedResult = selected ? (getHumanResult(selected) || getAIResult(selected)) : null
  const hasTaskReports = Array.isArray(selectedResult?.task_reports) && (selectedResult!.task_reports as unknown[]).length > 0
  const hasPendingSuggests = hasTaskReports && (selectedResult!.task_reports as Record<string, unknown>[]).some(
    (r, i) => r.result_type === 'suggest_new_subtask' && !suggestTaskSelections[i] && !r.parent_task_id
  )
  const selectedProjectName = getProjectDisplayName(projects, {
    ...(selected as Record<string, unknown>),
    ...(selectedResult ?? {}),
  })
  const confirmationContext = getConfirmationContext({
    ...(selectedResult || {}),
    source_type: selected?.source_type,
    submitter: selected?.submitter,
    special_project: selectedProjectName,
    related_task: selectedResult?.related_task || selected?.related_task,
  })
  const taskCards = buildConfirmationTaskCards(selectedResult, {
    projectName: String(selectedProjectName || editProject || ''),
    fallbackKeyTaskName: confirmationContext.keyTaskName || selected?.related_task || '',
    fallbackSubtaskNames: confirmationContext.subtaskNames,
  })
  const activeCardIndex = Math.min(selectedCardIndex, Math.max(taskCards.length - 1, 0))
  const activeCard = taskCards[activeCardIndex]
  const activeReviewCard = activeCard ? normalizeReviewCardData(activeCard, {
    cardIndex: activeCardIndex,
    totalCards: taskCards.length,
    fallbackProjectName: selectedProjectName || editProject,
    fallbackTaskName: confirmationContext.keyTaskName || selected?.related_task || '',
  }) : null

  const isSubmitterView = viewMode === 'mine' && selected?.submitter === currentUser?.name
  const isProcessed = selected && SS.normalize(selected.confirm_status) !== SS.S_NEW
  const isConfirmed = selected ? SS.CONFIRMED_AND_STORED.has(SS.normalize(selected.confirm_status)) : false
  const isReturned = selected ? SS.normalize(selected.confirm_status) === SS.S_RETURNED : false

  const confirmedWrites: string[] = []
  if (isConfirmed && selectedResult) {
    confirmedWrites.push('工作推进表')
    const hasWriteAch = selectedResult.write_task_reports_achievements === true ||
      (Array.isArray(selectedResult.achievements) && (selectedResult.achievements as Record<string, unknown>[]).some(a => (a as Record<string, unknown>).write_achievement === true))
    if (hasWriteAch) confirmedWrites.push('成果库')
    const hasWriteIss = selectedResult.write_task_reports_issues === true ||
      (Array.isArray(selectedResult.issues) && (selectedResult.issues as Record<string, unknown>[]).some(i => (i as Record<string, unknown>).write_issue === true))
    if (hasWriteIss) confirmedWrites.push('问题中心')
  }

  const taskReports = hasTaskReports ? (selectedResult!.task_reports as Record<string, unknown>[]) : []
  const globalIssues = Array.isArray(selectedResult?.issues)
    ? (selectedResult!.issues as Record<string, unknown>[]) : []
  const keyTaskIssues = Array.isArray(selectedResult?.key_task_issues)
    ? (selectedResult!.key_task_issues as Record<string, unknown>[]) : []

  // Collect subtask-level issues from task_reports so they flow to the issues block only
  const subtaskIssuesList: Record<string, unknown>[] = []
  if (hasTaskReports) {
    for (const r of taskReports) {
      const sis = r.subtask_issues
      if (Array.isArray(sis)) {
        for (const si of sis as unknown[]) {
          if (typeof si === 'object' && si !== null) {
            subtaskIssuesList.push(si as Record<string, unknown>)
          } else if (typeof si === 'string' && (si as string).trim()) {
            subtaskIssuesList.push({ description: si, issue_type: '问题' })
          }
        }
      }
    }
  }
  const dedupedIssues = deduplicateIssues([...globalIssues, ...keyTaskIssues, ...subtaskIssuesList])
  const hasPendingItems = Array.isArray(selectedResult?.pending_items) && (selectedResult!.pending_items as unknown[]).length > 0
  const effectivePendingItems: Record<string, unknown>[] = hasPendingItems
    ? (selectedResult!.pending_items as Record<string, unknown>[])
    : dedupedIssues

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="flex-shrink-0 bg-white border-b" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex items-center px-5 gap-2.5 h-14">
          <div className="flex-1 min-w-0">
            <h1 className="text-sm font-bold text-slate-800">AI 确认中心</h1>
            <p className="text-[11px] text-slate-400 mt-0.5 truncate">
              {viewMode === 'ceo'
                ? '处理负责人上报的提交级或任务卡级决策事项。'
                : viewMode === 'coordinator'
                  ? '处理项目负责人转交的统筹意见事项。'
                  : viewMode === 'all'
                    ? '负责人确认 AI 提取结果后，正式写入工作推进表、成果库和问题中心。'
                    : '查看我提交的工作汇报、AI 提取结果和确认状态。'}
            </p>
          </div>
        <div className="flex rounded-lg border overflow-hidden" style={{ borderColor: '#E9EFF6' }}>
          <button onClick={() => switchView('mine')} disabled={coordinatorInteractionLocked} className={`px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50 ${viewMode === 'mine' ? 'bg-blue-600 text-white' : 'bg-white text-slate-500 hover:bg-slate-50'}`}>
            我的提交记录
          </button>
          {isReviewer && (
            <button onClick={() => switchView('all')} disabled={coordinatorInteractionLocked} className={`px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1 ${viewMode === 'all' ? 'bg-blue-600 text-white' : 'bg-white text-slate-500 hover:bg-slate-50'}`}>
              待确认
              {pendingCount > 0 && <span className={`px-1.5 py-0.5 rounded-full text-xs font-bold ${viewMode === 'all' ? 'bg-white/20 text-white' : 'bg-orange-100 text-orange-600'}`}>{pendingCount}</span>}
            </button>
          )}
          {canUseCoordinatorView && (
            <button onClick={() => switchView('coordinator')} disabled={coordinatorInteractionLocked} className={`px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50 ${viewMode === 'coordinator' ? 'bg-blue-600 text-white' : 'bg-white text-slate-500 hover:bg-slate-50'}`}>
              待我统筹
            </button>
          )}
          {canUseCoachDecisionView && (
            <button onClick={() => switchView('ceo')} disabled={coordinatorInteractionLocked} className={`px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50 ${viewMode === 'ceo' ? 'bg-blue-600 text-white' : 'bg-white text-slate-500 hover:bg-slate-50'}`}>
              待我决策
            </button>
          )}
        </div>
        {!isCoachView && !isCoordinatorView && (
        <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white text-slate-600 cursor-pointer focus:outline-none">
          <option value="">全部状态</option>
          <option value={SS.S_NEW}>待确认</option>
          <option value={SS.S_CONFIRMED}>已入库</option>
          <option value={SS.S_RETURNED}>已退回</option>
        </select>
        )}
        {!isCoachView && !isCoordinatorView && (
        <select value={filterProject} onChange={(e) => setFilterProject(e.target.value)} className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white text-slate-600 cursor-pointer focus:outline-none">
          <option value="">全部项目</option>
          {allProjects.map((p) => <option key={p}>{p}</option>)}
        </select>
        )}
        {viewMode === 'all' && (
        <select value={filterSubmitter} onChange={(e) => setFilterSubmitter(e.target.value)} className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white text-slate-600 cursor-pointer focus:outline-none">
          <option value="">全部提交人</option>
          {allSubmitters.map((s) => <option key={s}>{s}</option>)}
        </select>
        )}
        {!isCoachView && !isCoordinatorView && (
        <div className="relative">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" style={{ width: 12, height: 12 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
          <input value={search} onChange={(e) => setSearch(e.target.value)} type="text" placeholder="搜索记录/任务…" className="pl-7 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none w-36" />
        </div>
        )}
        </div>
      </header>

      <div className="flex-1 overflow-hidden flex flex-col p-4 gap-3" style={{ background: '#F1F5F9' }}>
        <div className="flex gap-3 flex-1 overflow-hidden min-h-0">

          {/* Left: compact list */}
          <div className="w-[400px] xl:w-[420px] flex-shrink-0 flex flex-col bg-white rounded-2xl border overflow-hidden" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
            <div className="px-4 py-3 border-b flex-shrink-0 flex items-center justify-between" style={{ borderColor: '#E9EFF6' }}>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-slate-800">
                  {viewMode === 'ceo' ? '待我决策事项' : viewMode === 'coordinator' ? '待我统筹' : viewMode === 'all' ? '待确认事项' : '我的提交记录'}
                </span>
                <span className="text-xs text-slate-400">({visibleItems.length})</span>
              </div>
              <div className="flex items-center gap-1 text-slate-400">
                <button type="button" className="w-7 h-7 rounded-lg hover:bg-slate-50 flex items-center justify-center" aria-label="排序">
                  <svg style={{ width: 14, height: 14 }} viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7h10M8 12h7M8 17h4" /></svg>
                </button>
                <button type="button" className="w-7 h-7 rounded-lg hover:bg-slate-50 flex items-center justify-center" aria-label="筛选">
                  <svg style={{ width: 14, height: 14 }} viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 5h18l-7 8v5l-4 2v-7L3 5z" /></svg>
                </button>
              </div>
            </div>
            <div className="overflow-y-auto flex-1 px-3 py-3 space-y-3">
              {loading ? (
                <div className="py-10 text-center text-xs text-slate-400">加载中…</div>
              ) : visibleItems.length === 0 ? (
                <div className="py-10 text-center text-xs">
                  {loadError ? (
                    <span className="text-red-400">{loadError}</span>
                  ) : (
                    <span className="text-slate-400">
                      {viewMode === 'ceo'
                        ? '暂无待你决策的事项。'
                        : viewMode === 'coordinator'
                          ? '暂无待你反馈的统筹事项。'
                          : viewMode === 'all'
                            ? '暂无待确认事项。\n可切换到"我的提交记录"查看自己提交的内容。'
                            : '暂无提交记录，可前往工作汇报提交进展。'}
                    </span>
                  )}
                </div>
              ) : visibleItems.map((item) => {
                const isSelected = selected?.id === item.id
                const r = getHumanResult(item) || getAIResult(item)
                const summary = String(r?.summary || item.title || '').slice(0, 36)
                const isCardScope = item.ceo_decision_scope === 'card'
                const cardPendingCount = (item.pending_ceo_card_indices ?? []).length
                return (
                  <div
                    key={item.id}
                    onClick={() => {
                      if (isCoordinatorView && coordinatorActing) return
                      pickItem(item)
                    }}
                    aria-disabled={isCoordinatorView && coordinatorActing}
                    className={`px-4 py-3 transition-colors border rounded-2xl ${isCoordinatorView && coordinatorActing ? 'cursor-not-allowed opacity-60' : 'cursor-pointer hover:bg-sky-50'}`}
                    style={{
                      borderColor: isSelected ? '#93C5FD' : '#EEF2F7',
                      borderLeft: `4px solid ${isSelected ? '#2563EB' : 'transparent'}`,
                      background: isSelected ? '#EFF6FF' : undefined,
                      minHeight: 90,
                    }}
                  >
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <Ava name={item.submitter} />
                        <SourceBadge type={item.source_type} />
                        {isCoachView && item.ceo_decision_scope === 'submission' && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-purple-50 text-purple-600">整条提交</span>
                        )}
                        {isCoachView && isCardScope && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-sky-50 text-sky-600">
                            任务卡级{cardPendingCount > 1 ? ` · ${cardPendingCount} 张待决策` : ''}
                          </span>
                        )}
                      </div>
                      <StatusBadge status={item.confirm_status} />
                    </div>
                    <p className="text-sm font-medium text-slate-700 leading-6 pl-7 truncate">{summary || '—'}</p>
                    <div className="flex items-center justify-between pl-7 mt-2">
                      <span className="text-xs text-slate-400">{fmtShort(item.created_at)}</span>
                      <ConfBadge val={item.confidence} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Right: detail panel */}
          <div className="flex-1 flex flex-col bg-white rounded-2xl border overflow-hidden" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
            {selected ? (
              <>
                {/* Detail header */}
                <div className="px-5 py-3 border-b flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex items-center gap-2 flex-wrap">
                      <span className="text-lg font-bold text-slate-900 truncate">
                        {String(confirmationContext.keyTaskName || selected?.related_task || '记录详情')}
                      </span>
                      <StatusBadge status={selected.confirm_status} />
                    </div>
                    <span className="text-xs text-slate-500 flex-shrink-0">记录ID：{String((selected as Record<string, unknown>).record_id || selected.id)}</span>
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-3 text-xs text-slate-500 flex-wrap">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <SourceBadge type={selected.source_type} />
                      <span className="font-medium text-slate-700">{selected.submitter}</span>
                      <span className="text-slate-300">|</span>
                      <span>{fmtTime(selected.created_at)}</span>
                      <span className="text-slate-300">|</span>
                      <span>置信度：<ConfBadge val={selected.confidence} /></span>
                    </div>
                    <button type="button" className="px-3 py-1.5 rounded-lg border border-slate-200 text-xs text-slate-600 bg-white hover:bg-slate-50">查看原始内容</button>
                  </div>
                </div>

                {/* Scrollable body */}
                <div className="flex-1 overflow-y-auto min-h-0 px-4 py-3 space-y-4">
                  {/* 企业教练决策区 — 仅提交级 */}
                  {isCoachView && selected && selected.ceo_decision_scope === 'submission' && (
                    <section className="rounded-[22px] border p-4" style={{ borderColor: '#C4B5FD', background: 'linear-gradient(135deg,#F5F3FF,#EEF2FF)' }}>
                      <div className="flex items-center gap-2 mb-3">
                        <svg style={{ width: 18, height: 18, color: '#7C3AED' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
                        </svg>
                        <span className="text-sm font-bold text-violet-800">企业教练批示</span>
                        <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-violet-100 text-violet-700">整条提交</span>
                      </div>
                      {/* 提交级：显示上报说明 */}
                      <div className="mb-3 p-3 rounded-xl bg-white/70 text-sm text-slate-600">
                        <span className="font-semibold text-slate-800">负责人上报说明：</span>
                        {selected.reject_reason || selected.ceo_note || '（无）'}
                      </div>
                      {actionError && (
                        <div className="mb-3 flex items-center gap-2 rounded-xl bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
                          <svg style={{ width: 14, height: 14, flexShrink: 0 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                          {actionError}
                        </div>
                      )}
                      {actionSuccess && (
                        <div className="mb-3 flex items-center gap-2 rounded-xl bg-emerald-50 border border-emerald-200 px-3 py-2 text-sm text-emerald-700">
                          <svg style={{ width: 14, height: 14, flexShrink: 0 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" /></svg>
                          {actionSuccess}
                        </div>
                      )}
                      <textarea
                        value={coachNote}
                        onChange={(e) => setCoachNote(e.target.value)}
                        placeholder="请输入企业教练批示意见（必填）…"
                        className="w-full border border-violet-200 rounded-xl p-3 text-sm focus:outline-none resize-none mb-3"
                        style={{ minHeight: 80, background: 'white' }}
                      />
                      <button
                        onClick={handleCoachSubmissionDecide}
                        disabled={coachActing || !coachNote.trim()}
                        className="w-full py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 disabled:opacity-50"
                        style={{ background: 'linear-gradient(135deg,#7C3AED,#A78BFA)' }}
                      >
                        {coachActing ? '提交中…' : '提交企业教练批示'}
                      </button>
                    </section>
                  )}

                  {/* 统筹反馈区 */}
                  {isCoordinatorView && selected && (
                    <section className="rounded-[22px] border p-4" style={{ borderColor: '#A5B4FC', background: 'linear-gradient(135deg,#EEF2FF,#E0E7FF)' }}>
                      <div className="flex items-center gap-2 mb-3">
                        <svg style={{ width: 18, height: 18, color: '#4F46E5' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                        </svg>
                        <span className="text-sm font-bold text-indigo-800">提供统筹意见</span>
                        <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-indigo-100 text-indigo-700">整条提交</span>
                      </div>
                      {/* 负责人转交说明 */}
                      <div className="mb-3 p-3 rounded-xl bg-white/70 text-sm text-slate-600">
                        <span className="font-semibold text-slate-800">负责人转交说明：</span>
                        {selected.reject_reason || '（无）'}
                      </div>
                      {/* 提交人信息 */}
                      <div className="mb-3 p-3 rounded-xl bg-white/70 text-sm text-slate-600 space-y-1">
                        <div><span className="font-semibold text-slate-800">提交人：</span>{selected.submitter || '—'}</div>
                        <div><span className="font-semibold text-slate-800">提交时间：</span>{fmtTime(selected.created_at)}</div>
                        <div><span className="font-semibold text-slate-800">提交标题：</span>{String(confirmationContext.keyTaskName || selected?.related_task || '—')}</div>
                      </div>
                      {actionError && (
                        <div className="mb-3 flex items-center gap-2 rounded-xl bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
                          <svg style={{ width: 14, height: 14, flexShrink: 0 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                          {actionError}
                        </div>
                      )}
                      {actionSuccess && (
                        <div className="mb-3 flex items-center gap-2 rounded-xl bg-emerald-50 border border-emerald-200 px-3 py-2 text-sm text-emerald-700">
                          <svg style={{ width: 14, height: 14, flexShrink: 0 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" /></svg>
                          {actionSuccess}
                        </div>
                      )}
                      <textarea
                        value={coordinatorNote}
                        onChange={(e) => setCoordinatorNote(e.target.value)}
                        placeholder="请输入统筹反馈意见（必填）…"
                        disabled={coordinatorActing}
                        className="w-full border border-indigo-200 rounded-xl p-3 text-sm focus:outline-none resize-none mb-3 disabled:opacity-50"
                        style={{ minHeight: 80, background: 'white' }}
                      />
                      <button
                        onClick={handleCoordinatorFeedback}
                        disabled={coordinatorActing || !coordinatorNote.trim()}
                        className="w-full py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 disabled:opacity-50"
                        style={{ background: 'linear-gradient(135deg,#4F46E5,#818CF8)' }}
                      >
                        {coordinatorActing ? '提交中…' : '提交反馈'}
                      </button>
                    </section>
                  )}

                  <section className="rounded-[22px] border bg-gradient-to-br from-slate-50 to-white p-4" style={{ borderColor: '#E5EEF9' }}>
                    <div className="flex items-center justify-between gap-3 mb-3">
                      <div>
                        <p className="text-sm font-bold text-slate-900">任务卡牌总览</p>
                        <p className="text-xs text-slate-400 mt-0.5">
                          {isCoachView ? '查看本次提交包含的任务卡内容' : '先看清本次提交包含哪些任务，再逐张判断'}
                        </p>
                      </div>
                      <span className="px-2.5 py-1 rounded-full bg-blue-50 text-blue-600 text-xs font-bold">{taskCards.length} 张卡</span>
                    </div>
                    <div className="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-3">
                      {taskCards.map((card, cardIndex) => {
                        const selectedCard = cardIndex === activeCardIndex
                        const localDecision = cardDecisions[cardIndex]
                        const backendDecision = card.confirmationStatus
                        const decisionStatus = localDecision === 'confirm' ? 'confirmed' : localDecision === 'return' ? 'returned' : localDecision === 'transfer' ? 'transferred_to_coordinator' : localDecision === 'ceo' ? 'pending_ceo_decision' : backendDecision
                        const decisionLabel = taskCardDecisionLabel(decisionStatus)
                        return (
                          <button
                            type="button"
                            key={`${card.id}-summary-${cardIndex}`}
                            onClick={() => { setSelectedCardIndex(cardIndex); setCardDetailOpen(true) }}
                            className="text-left rounded-2xl border bg-white p-4 transition-all hover:-translate-y-0.5 hover:shadow-md"
                            style={{ borderColor: selectedCard ? '#2563EB' : '#E5EEF9', boxShadow: selectedCard ? '0 10px 24px rgba(37,99,235,0.12)' : '0 1px 3px rgba(15,23,42,0.04)' }}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-xs text-slate-400 font-semibold">任务卡 {cardIndex + 1}</p>
                                <h2 className="mt-1 text-base font-bold text-slate-950 truncate">{card.title}</h2>
                              </div>
                              <span className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${taskCardDecisionTone(decisionStatus)}`}>{decisionLabel}</span>
                            </div>
                            <p className="mt-2 text-xs text-slate-500 truncate">{card.structure.projectName} / {card.structure.keyTaskName}</p>
                            <div className="mt-3 grid grid-cols-4 gap-1.5 text-center">
                              <span className="rounded-lg bg-emerald-50 py-1 text-[11px] font-semibold text-emerald-700">完成 {card.completedItems.length}</span>
                              <span className="rounded-lg bg-sky-50 py-1 text-[11px] font-semibold text-sky-700">成果 {card.achievements.length}</span>
                              <span className="rounded-lg bg-amber-50 py-1 text-[11px] font-semibold text-amber-700">事项 {card.pendingItems.length}</span>
                              <span className="rounded-lg bg-blue-50 py-1 text-[11px] font-semibold text-blue-700">下一步 {card.nextSteps.length}</span>
                            </div>
                          </button>
                        )
                      })}
                    </div>
                  </section>

                </div>

              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">← 点击左侧列表查看详情</div>
            )}
          </div>
        </div>

        {cardDetailOpen && activeCard && activeReviewCard && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-8 py-8">
            <div className="w-full max-w-5xl max-h-[86vh] overflow-hidden rounded-[24px] bg-white border shadow-2xl flex flex-col" style={{ borderColor: '#DDE8F6' }}>
              <div className="px-5 py-4 border-b flex items-start justify-between gap-4" style={{ borderColor: '#E9EFF6' }}>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-bold text-blue-600 bg-blue-50 rounded-full px-2.5 py-1">{activeReviewCard.cardIndexText}</span>
                    <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-600">{activeReviewCard.statusText}</span>
                  </div>
                  <h2 className="mt-2 text-xl font-bold text-slate-950 leading-8">{activeReviewCard.title}</h2>
                  <div className="mt-2 flex items-center gap-4 text-sm text-slate-500 flex-wrap">
                    <span className="inline-flex items-center gap-1.5">
                      <svg style={{ width: 15, height: 15 }} viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 7a2 2 0 012-2h4l2 2h10a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" /></svg>
                      项目：{activeReviewCard.projectName}
                    </span>
                    <span className="text-slate-300">|</span>
                    <span className="inline-flex items-center gap-1.5">
                      <svg style={{ width: 15, height: 15 }} viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" /></svg>
                      任务：{activeReviewCard.taskName}
                    </span>
                  </div>
                </div>
                <button type="button" onClick={() => setCardDetailOpen(false)} className="w-9 h-9 rounded-xl border border-slate-200 text-slate-400 hover:bg-slate-50 hover:text-slate-700 flex items-center justify-center">×</button>
              </div>

              <div className="overflow-y-auto p-5 space-y-4">
                <section className="rounded-2xl border bg-blue-50/70 px-4 py-3 flex items-start gap-3" style={{ borderColor: '#BFDBFE' }}>
                  <span className="mt-0.5 w-6 h-6 rounded-full bg-white text-blue-600 flex items-center justify-center flex-shrink-0 border border-blue-100">
                    <svg style={{ width: 14, height: 14 }} viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20 10 10 0 000-20z" /></svg>
                  </span>
                  <p className="text-sm leading-6 text-slate-700 overflow-hidden" style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                    <span className="font-bold text-slate-900">本卡重点：</span>{activeReviewCard.summary}
                  </p>
                </section>

                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 items-stretch">
                  <TaskCardList title="本周完成" items={activeReviewCard.completed} emptyText="暂无本周完成内容" tone="done" />
                  <TaskCardList title="需处理事项" items={activeReviewCard.pendingItems} emptyText="暂无需处理事项" tone="issue" />
                  <TaskCardList title="下一步计划" items={activeReviewCard.nextSteps} emptyText="暂无下一步计划" tone="next" />
                  <TaskCardList title="成果" items={activeReviewCard.achievements} emptyText="暂无可入库成果" tone="achievement" />
                </div>
              </div>

              <div className="px-5 py-4 border-t bg-slate-50" style={{ borderColor: '#E9EFF6' }}>
                {isCoachView ? (
                  activeCard.confirmationStatus === 'pending_ceo_decision' ? (
                    <>
                      <div className="flex items-center justify-between gap-3 mb-3">
                        <div>
                          <p className="text-xs font-bold text-slate-500 tracking-wider">企业教练批示</p>
                          <p className="text-xs text-slate-400 mt-1">处理当前任务卡的决策事项</p>
                        </div>
                        <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-sky-100 text-sky-600">待决策</span>
                      </div>
                      {activeCard.confirmationNote && (
                        <div className="mb-3 p-3 rounded-xl bg-white text-sm text-slate-600 border border-slate-200">
                          <span className="font-semibold text-slate-800">负责人上报说明：</span>
                          {activeCard.confirmationNote}
                        </div>
                      )}
                      {actionError && (
                        <div className="mb-3 flex items-center gap-2 rounded-xl bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
                          <svg style={{ width: 14, height: 14, flexShrink: 0 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                          {actionError}
                        </div>
                      )}
                      {actionSuccess && (
                        <div className="mb-3 flex items-center gap-2 rounded-xl bg-emerald-50 border border-emerald-200 px-3 py-2 text-sm text-emerald-700">
                          <svg style={{ width: 14, height: 14, flexShrink: 0 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" /></svg>
                          {actionSuccess}
                        </div>
                      )}
                      <textarea
                        value={coachNote}
                        onChange={(e) => setCoachNote(e.target.value)}
                        placeholder="请输入企业教练批示意见（必填）…"
                        className="w-full border border-violet-200 rounded-xl p-3 text-sm focus:outline-none resize-none mb-3"
                        style={{ minHeight: 72, background: 'white' }}
                      />
                      <button
                        onClick={handleCoachCardDecide}
                        disabled={coachActing || !coachNote.trim()}
                        className="w-full py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 disabled:opacity-50"
                        style={{ background: 'linear-gradient(135deg,#7C3AED,#A78BFA)' }}
                      >
                        {coachActing ? '提交中…' : '提交企业教练批示'}
                      </button>
                    </>
                  ) : activeCard.confirmationStatus === 'ceo_decided' ? (
                    <div className="py-4">
                      <div className="flex items-center gap-2 mb-3">
                        <svg style={{ width: 16, height: 16, color: '#059669' }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" /></svg>
                        <span className="text-sm font-bold text-emerald-700">企业教练已批示</span>
                      </div>
                      {activeCard.ceoNote && (
                        <div className="p-3 rounded-xl bg-emerald-50 text-sm text-slate-700 border border-emerald-100">
                          <span className="font-semibold">批示内容：</span>{activeCard.ceoNote}
                        </div>
                      )}
                      {activeCard.ceoOperator && (
                        <p className="mt-2 text-xs text-slate-400">
                          批示人：{activeCard.ceoOperator}{activeCard.ceoDecidedAt ? ` · ${activeCard.ceoDecidedAt}` : ''}
                        </p>
                      )}
                    </div>
                  ) : (
                    <div className="py-3 text-center text-xs text-slate-400">
                      该任务卡不需要企业教练决策。
                    </div>
                  )
                ) : viewMode === 'coordinator' ? (
                <div className="py-3 text-center text-xs text-slate-400">
                  请在上方填写统筹反馈意见后提交。
                </div>
                ) : viewMode === 'all' ? (
                <>
                {actionError && (
                  <div className="mb-3 flex items-center gap-2 rounded-xl bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
                    <svg style={{ width: 14, height: 14, flexShrink: 0 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    {actionError}
                  </div>
                )}
                {actionSuccess && (
                  <div className="mb-3 flex items-center gap-2 rounded-xl bg-emerald-50 border border-emerald-200 px-3 py-2 text-sm text-emerald-700">
                    <svg style={{ width: 14, height: 14, flexShrink: 0 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" /></svg>
                    {actionSuccess}
                  </div>
                )}
                <div className="flex items-center justify-between gap-3 mb-3">
                  <div>
                    <p className="text-xs font-bold text-slate-500 tracking-wider">单卡判断</p>
                    <p className="text-xs text-slate-400 mt-1">操作会直接写入后端，只处理当前这张任务卡</p>
                  </div>
                  {(cardDecisions[activeCardIndex] || activeCard.confirmationStatus !== 'pending') && (
                    <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${taskCardDecisionTone(activeCard.confirmationStatus)}`}>{taskCardDecisionLabel(activeCard.confirmationStatus)}</span>
                  )}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
                  <button type="button" onClick={() => handleTaskCardDecision('confirm')} disabled={acting || projectArchived} title={projectArchived ? '项目已归档，不可继续确认入库。' : undefined} className="h-11 rounded-xl bg-blue-600 text-white font-semibold disabled:opacity-50">确认入库</button>
                  <button type="button" onClick={() => handleTaskCardDecision('return')} disabled={acting || projectArchived} title={projectArchived ? '项目已归档，不可继续确认入库。' : undefined} className="h-11 rounded-xl border border-orange-300 text-orange-600 font-semibold bg-white disabled:opacity-50">退回并重新编辑</button>
                  <button type="button" onClick={() => handleTaskCardDecision('transfer')} disabled={acting || projectArchived} title={projectArchived ? '项目已归档，不可继续确认入库。' : undefined} className="h-11 rounded-xl border border-violet-300 text-violet-600 font-semibold bg-white disabled:opacity-50">转交统筹人</button>
                  <button type="button" onClick={() => handleTaskCardDecision('ceo')} disabled={acting || projectArchived} title={projectArchived ? '项目已归档，不可继续确认入库。' : undefined} className="h-11 rounded-xl border border-slate-200 text-slate-600 font-semibold bg-white disabled:opacity-50">转交企业教练</button>
                </div>
                </>
                ) : (
                <div className="py-3 text-center text-xs text-slate-400">
                  该视图下仅查看记录，如需处理请切换到「待确认」。
                </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Operation log — collapsible */}
        <div className="bg-white rounded-2xl border flex-shrink-0" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
          <button
            onClick={() => setOpLogsOpen(!opLogsOpen)}
            className="w-full flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition-colors rounded-2xl"
          >
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-700">操作日志</span>
              {opLogs.length > 0 && (
                <span className="px-1.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-500">{opLogs.length}</span>
              )}
            </div>
            <svg
              style={{ width: 14, height: 14, color: '#94A3B8', transition: 'transform 0.2s', transform: opLogsOpen ? 'rotate(180deg)' : undefined }}
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {opLogsOpen && (
            <div className="border-t" style={{ borderColor: '#E9EFF6' }}>
              {opLogs.length === 0 ? (
                <div className="py-4 text-center text-xs text-slate-400">暂无操作记录</div>
              ) : (
                <div className="px-4 py-2.5">
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-2.5">
                    {opLogs.map((item, idx) => {
                      const action = getConfirmActionLabel(item.confirm_status)
                      const summary = getConfirmActionSummary(item)
                      const note = getConfirmActionNote(item)
                      const time = fmtShort((item as Record<string, unknown>).updated_at as string || item.created_at)
                      const isDone = SS.CONFIRMED_AND_STORED.has(SS.normalize(item.confirm_status))
                      const borderColor = isDone ? '#DBEAFE' : SS.normalize(item.confirm_status) === SS.S_RETURNED ? '#FED7AA' : '#E9D5FF'
                      const dotColor = isDone ? '#3B82F6' : SS.normalize(item.confirm_status) === SS.S_RETURNED ? '#F97316' : '#8B5CF6'
                      return (
                        <div key={item.id} className="relative rounded-2xl border bg-white px-3 py-2.5" style={{ borderColor, boxShadow: '0 1px 2px rgba(15,23,42,0.04)' }}>
                          <div className="absolute left-4.5 top-4.5 bottom-3.5 w-px border-l border-dashed" style={{ borderColor: '#E2E8F0' }} />
                          <div className="flex items-start gap-2.5">
                            <span className="mt-0.5 w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: dotColor, boxShadow: `0 0 0 4px ${dotColor}18` }} />
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center justify-between gap-3">
                                <div className="flex items-center gap-2 min-w-0">
                                  <Ava name={item.submitter} />
                                  <span className="text-xs font-semibold text-slate-700 truncate">{item.submitter}</span>
                                </div>
                                <span className="text-[11px] text-slate-400 flex-shrink-0">{time}</span>
                              </div>
                              <div className="mt-2 flex items-center gap-2.5 flex-wrap">
                                <span className="text-sm font-bold text-slate-800">{action}</span>
                                <StatusBadge status={item.confirm_status} />
                              </div>
                              <p className="mt-1.5 text-xs text-slate-500 leading-5 line-clamp-1">{summary}</p>
                              <p className="mt-1 text-[11px] text-slate-400 leading-5 line-clamp-1">{note}</p>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
