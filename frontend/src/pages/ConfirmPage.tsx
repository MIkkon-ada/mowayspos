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
  coordinatorFeedbackTaskCard,
} from '../api/confirmations'
import { fetchSubtasksByAssignee, type SubTaskWithParent } from '../api/subtasks'
import { fetchTasks } from '../api/tasks'
import { useProject } from '../context/ProjectContext'
import type { ConfirmationItem, TaskItem } from '../types'
import { fmtFull, fmtShort } from '../utils/time'
import * as SS from '../domain/submissionStatus'
import { getConfirmationContext } from '../domain/confirmationFlow'
import { isProjectArchived } from '../domain/projectLifecycleStatus'
import { buildConfirmationTaskCards, normalizeReviewCardData } from '../domain/confirmationTaskCards'
import { buildConfirmationAssetProjection } from '../domain/confirmationAssets'
import { getProjectDisplayName } from '../domain/projectDisplay'

type WriteMode = 'task_new' | 'subtask_update' | 'subtask_new'
type ConfirmViewMode = 'all' | 'coordinator' | 'ceo'

const REVIEWER_PROJECT_ROLES = new Set(['owner', 'coordinator', 'project_ceo', 'super_admin'])

// Inline icon helpers (avoid react-icons dependency)
function IconChevronDown({ size = 12, className = '' }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  )
}
function IconSearch({ size = 12, className = '' }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
    </svg>
  )
}
function IconFileText({ size = 20, className = '' }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" /><path d="M10 9H8" /><path d="M16 13H8" /><path d="M16 17H8" />
    </svg>
  )
}
function IconMail({ size = 20, className = '' }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="2" y="4" width="20" height="16" rx="2" /><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  )
}
function IconCheckCircle({ size = 14, className = '' }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><path d="m22 4-10 10L8 10" />
    </svg>
  )
}
function IconAlertCircle({ size = 14, className = '' }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  )
}
function IconArrowRight({ size = 14, className = '' }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M5 12h14" /><path d="m12 5 7 7-7 7" />
    </svg>
  )
}
function IconCrown({ size = 14, className = '' }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M2 4l3 12h14l3-12-6 7-4-7-4 7-6-7zm3 16h14" /><path d="M12 4v4" />
    </svg>
  )
}

function IconX({ size = 18, className = '' }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M18 6 6 18" /><path d="m6 6 12 12" />
    </svg>
  )
}

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
  if (status === 'coordinator_given') return '统筹已反馈'
  if (status === 'pending_ceo_decision') return '已转企业教练'
  if (status === 'ceo_decided') return '企业教练已批示'
  return '未判断'
}

function taskCardDecisionTone(status?: string) {
  if (status === 'confirmed') return 'bg-emerald-50 text-emerald-600'
  if (status === 'returned') return 'bg-orange-50 text-orange-600'
  if (status === 'transferred_to_coordinator') return 'bg-violet-50 text-violet-600'
  if (status === 'coordinator_given') return 'bg-indigo-50 text-indigo-600'
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
  const [pendingAction, setPendingAction] = useState<'return' | 'transfer' | 'ceo' | null>(null)
  const [actionNote, setActionNote] = useState('')
  const [opLogsOpen, setOpLogsOpen] = useState(false)
  const [showTranscript, setShowTranscript] = useState(false)
  const [selectedCardIndex, setSelectedCardIndex] = useState(0)
  const [cardDecisions, setCardDecisions] = useState<Record<number, 'confirm' | 'return' | 'transfer' | 'ceo'>>({})
  const [coordinatorCardNote, setCoordinatorCardNote] = useState('')

  const selectedProject = selected?.project_id != null ? projects.find((p) => p.id === selected.project_id) ?? null : null
  const projectArchived = isProjectArchived(selectedProject)
  const canUseOwnerActions = Boolean(
    currentUser?.is_tech_admin ||
    selectedProject?.user_roles?.includes('owner'),
  )

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
  const defaultViewMode: ConfirmViewMode = 'all'

  // 从 URL 解析初始视图
  const resolveInitialView = (): ConfirmViewMode => {
    const urlView = searchParams.get('view')
    if (urlView === 'ceo' && canUseCoachDecisionView) return 'ceo'
    if (urlView === 'coordinator' && canUseCoordinatorView) return 'coordinator'
    if (urlView === 'all' && isReviewer) return 'all'
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

  const [filterStatus, setFilterStatus] = useState(defaultViewMode === 'all' ? 'owner_actionable' : '')
  const [filterProject, setFilterProject] = useState('')
  const [filterSubmitter, setFilterSubmitter] = useState('')
  const [search, setSearch] = useState('')

  // ceo / coordinator 视图下清除状态筛选
  const isCoachView = viewMode === 'ceo'
  const isCoordinatorView = viewMode === 'coordinator'

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

  // 统一 effect：深链初始化及手动切换时同步 filterStatus
  useEffect(() => {
    if (viewMode === 'ceo' || viewMode === 'coordinator') {
      setFilterStatus('')
    } else if (viewMode === 'all') {
      setFilterStatus('owner_actionable')
    } else {
      setFilterStatus('')
    }
  }, [viewMode])

  function switchView(nextView: ConfirmViewMode) {
    if (isCoordinatorView && coordinatorActing) return
    setViewMode(nextView)
    setSelected(null)
    setWriteToAchievements(true)
    setWriteToIssues(true)
    setActionNote('')
    setPendingAction(null)
    setActionError(null)
    setActionSuccess(null)
    setCoachNote('')
    setCoachActing(false)
    setCoordinatorNote('')
    setCoordinatorCardNote('')
    if (nextView === 'all') {
      setFilterStatus('owner_actionable')
    } else {
      setFilterStatus('')
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
  const [writeToAchievements, setWriteToAchievements] = useState(true)

  const [pendingItemTypes, setPendingItemTypes] = useState<Record<number, string>>({})
  const [pendingItemHelpers, setPendingItemHelpers] = useState<Record<number, string>>({})
  const [pendingItemNotes, setPendingItemNotes] = useState<Record<number, string>>({})

  const [coachNote, setCoachNote] = useState('')
  const [coachActing, setCoachActing] = useState(false)

  const [coordinatorNote, setCoordinatorNote] = useState('')
  const [coordinatorActing, setCoordinatorActing] = useState(false)

  const coordinatorInteractionLocked = isCoordinatorView && coordinatorActing

  // 负责人 all 视图下的操作范围切换
  const [cardEditMode, setCardEditMode] = useState<Record<number, boolean>>({})
  const [cardProjOverride, setCardProjOverride] = useState<Record<number, string>>({})
  const [cardKeyTaskOverride, setCardKeyTaskOverride] = useState<Record<number, number | null>>({})
  const [cardSubtaskOverride, setCardSubtaskOverride] = useState<Record<number, number | null>>({})

  const [projectTasks, setProjectTasks] = useState<TaskItem[]>([])
  const [submitterSubtasks, setSubmitterSubtasks] = useState<SubTaskWithParent[]>([])
  const [suggestTaskSelections, setSuggestTaskSelections] = useState<Record<number, number | null>>({})

  const [editProject, setEditProject] = useState('')
  const [editStatus, setEditStatus] = useState('进行中')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError(null)
    setSelected(null)
    setItems([])
    if (viewMode === 'ceo') {
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
      getPending(coordProjectId, 'coordinator', { includeCardLevel: true })
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
  }, [currentProjectId, pendingProjectId, viewMode, urlProjectId, urlSubmissionId, urlCardIndex])

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
    setLoadError(null)
    setWriteToAchievements(true)
    setWriteToIssues(true)
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
    setCoordinatorCardNote('')
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

    let shouldOpenCard = false
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
      shouldOpenCard = item.ceo_decision_scope === 'card' && pendingIndices.length > 0
    } else if (isCoachView) {
      const pendingIndices = item.pending_ceo_card_indices ?? []
      setSelectedCardIndex(pendingIndices.length > 0 ? pendingIndices[0] : 0)
    } else if (isCoordinatorView && item.coordinator_decision_scope === 'card') {
      const pendingIndices = item.pending_coordinator_card_indices ?? []
      if (urlCardIndex !== undefined && pendingIndices.includes(urlCardIndex)) {
        setSelectedCardIndex(urlCardIndex)
      } else if (pendingIndices.length > 0) {
        setSelectedCardIndex(pendingIndices[0])
      } else {
        setSelectedCardIndex(0)
      }
      shouldOpenCard = urlCardIndex !== undefined && pendingIndices.length > 0
    } else if (isCoordinatorView) {
      setSelectedCardIndex(0)
    } else if (urlCardIndex !== undefined) {
      setSelectedCardIndex(urlCardIndex)
      shouldOpenCard = true
    } else {
      setSelectedCardIndex(0)
    }

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
      let patchedTaskReports = Array.isArray(base.task_reports)
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
        achievements: (hasTaskReports
          ? assetProjection.submissionAchievements.map((achievement) => achievement.item)
          : ((base.achievements as unknown[]) || [])
        ).map((a) => ({
          ...(a as Record<string, unknown>),
          write_achievement: writeToAchievements,
        })),
        issues: (hasTaskReports ? [] : ((base.issues as unknown[]) || [])).map((i) => ({
          ...(i as Record<string, unknown>),
          write_issue: writeToIssues,
        })),
      }
      // Review the deduplicated projection and route each issue back to its source scope.
      if (hasPendingItems) {
        const classified = effectivePendingItems.map((projected, idx) => {
          const item = projected.item
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
          const reportIssues = new Map<number, Record<string, unknown>[]>()
          const submissionIssues: Record<string, unknown>[] = []
          effectivePendingItems.forEach((projected, idx) => {
            if (projected.source === 'task_report' && projected.reportIndex !== undefined) {
              const existing = reportIssues.get(projected.reportIndex) ?? []
              existing.push(classified[idx])
              reportIssues.set(projected.reportIndex, existing)
            } else {
              submissionIssues.push(classified[idx])
            }
          })
          patchedTaskReports = (patchedTaskReports as Record<string, unknown>[]).map((report, reportIndex) => ({
            ...report,
            subtask_issues: reportIssues.get(reportIndex) ?? [],
          }))
          humanResult.task_reports = patchedTaskReports
          humanResult.key_task_issues = submissionIssues
          humanResult.issues = []
          humanResult.pending_items = classified
        } else {
          humanResult.issues = classified
          humanResult.key_task_issues = []
        }
      }

      const response = await confirmSubmission(selected.id, currentUser.name, humanResult)
      const updated = response.submission ?? { ...selected, confirm_status: SS.S_CONFIRMED }
      setItems((prev) => prev.map((i) => i.id === selected.id ? updated : i))
      setSelected(updated)
      setActionSuccess('已确认入库')
      setActionNote('')
      setPendingAction(null)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setActionError(`操作失败：${msg}`)
    } finally { setActing(false) }
  }

  async function handleDecision(action: 'return' | 'transfer' | 'ceo') {
    if (!selected || !currentUser) return
    const note = actionNote.trim()
    if (!note) return
    setActionError(null)
    setActionSuccess(null)
    setActing(true)
    try {
      const response = action === 'return'
        ? await rejectSubmission(selected.id, note, currentUser.name)
        : action === 'transfer'
          ? await transferCoordinator(selected.id, note, currentUser.name)
          : await escalateCeo(selected.id, note, currentUser.name)
      const nextStatus = action === 'return'
        ? SS.S_RETURNED
        : action === 'transfer'
          ? SS.S_WAITING_COORDINATOR
          : SS.S_WAITING_CEO
      const updated = response.submission ?? { ...selected, confirm_status: nextStatus }
      setItems((prev) => prev.map((i) => i.id === selected.id ? updated : i))
      setSelected(updated)
      setActionSuccess(action === 'return' ? '已退回' : action === 'transfer' ? '已转交统筹人' : '已提交企业教练决策')
      setActionNote('')
      setPendingAction(null)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setActionError(`操作失败：${msg}`)
    } finally {
      setActing(false)
    }
  }

  async function handleTaskCardDecision(action: 'confirm' | 'return' | 'transfer' | 'ceo') {
    if (!selected || !currentUser) return
    if (activeCardBackendIndex == null) {
      setActionError('当前提交中不存在可处理的任务卡')
      return
    }
    const cardIndex = activeCardBackendIndex
    const note = actionNote.trim() || (
      action === 'return' ? '退回并重新编辑' : action === 'transfer' ? '转交统筹人' : action === 'ceo' ? '转交企业教练' : ''
    )
    setActionError(null)
    setActionSuccess(null)
    setActing(true)
    try {
      const response = action === 'confirm'
        ? await confirmTaskCard(selected.id, cardIndex, currentUser.name)
        : action === 'return'
          ? await rejectTaskCard(selected.id, cardIndex, note, currentUser.name)
          : action === 'transfer'
            ? await transferTaskCardCoordinator(selected.id, cardIndex, note, currentUser.name)
            : await escalateTaskCardCeo(selected.id, cardIndex, note, currentUser.name)
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
    if (activeCardBackendIndex == null) {
      setActionError('当前提交中不存在可处理的任务卡')
      return
    }
    setActionError(null)
    setActionSuccess(null)
    setCoachActing(true)
    try {
      await ceoDecideTaskCard(selected.id, activeCardBackendIndex, coachNote, currentUser.name)
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
      setCoordinatorNote('')
      // 重新加载 coordinator 待办
      try {
        await reloadCoordinatorItems()
        setActionSuccess('统筹意见已提交，事项已返回项目负责人。')
      } catch {
        setActionSuccess('统筹意见已提交，但待办列表刷新失败，请手动刷新页面。')
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setActionError(`操作失败：${msg}`)
    } finally {
      setCoordinatorActing(false)
    }
  }

  async function handleCoordinatorCardFeedback() {
    if (!selected || !currentUser || !coordinatorCardNote.trim()) return
    if (activeCardBackendIndex == null) {
      setActionError('当前提交中不存在可处理的任务卡')
      return
    }
    setActionError(null)
    setActionSuccess(null)
    setCoordinatorActing(true)
    try {
      await coordinatorFeedbackTaskCard(
        selected.id,
        activeCardBackendIndex,
        coordinatorCardNote,
        currentUser.name,
      )
      setCoordinatorCardNote('')
      try {
        await reloadCoordinatorItems()
        setActionSuccess('任务卡统筹意见已提交，事项已返回项目负责人。')
      } catch {
        setActionSuccess('统筹意见已提交，但待办列表刷新失败，请手动刷新页面。')
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setActionError(`操作失败：${msg}`)
    } finally {
      setCoordinatorActing(false)
    }
  }

  function reloadCoordinatorItems() {
    const coordProjectId = urlProjectId ?? null
    return getPending(coordProjectId, 'coordinator', { includeCardLevel: true })
      .then((d) => {
        setItems(d)
        const same = selected ? d.find((item) => item.id === selected.id) : undefined
        if (same) {
          pickItem(same)
          const indices = same.pending_coordinator_card_indices ?? []
          if (indices.length > 0) {
            setSelectedCardIndex(indices[0])
          }
        } else if (d[0]) {
          pickItem(d[0])
        } else {
          setSelected(null)
        }
      })
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

  const pendingCount = items.filter(i => SS.OWNER_ACTIONABLE.has(SS.normalize(i.confirm_status))).length
  const allProjects = [...new Set(items.map((i) => String(projectNameFromConfirmation(i, projects) || '')).filter(Boolean))]
  const allSubmitters = [...new Set(items.map((i) => i.submitter).filter(Boolean))]

  const visibleItems = items.filter((item) => {
    if (filterStatus === 'owner_actionable' && !SS.OWNER_ACTIONABLE.has(SS.normalize(item.confirm_status))) return false
    if (filterStatus && filterStatus !== 'owner_actionable' && SS.normalize(item.confirm_status) !== filterStatus) return false
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

  // 选中状态与可见列表一致性保护
  // 确保 selected 始终可见于左栏列表，避免「列表空但显示详情幽灵」的问题
  useEffect(() => {
    if (loading) return
    if (!selected) return
    // 左栏无可见记录 → 清空所有选中状态
    if (visibleItems.length === 0) {
      setSelected(null)
      return
    }
    // 当前 selected 不在 visibleItems 中
    if (!visibleItems.some(v => v.id === selected.id)) {
      // 深链：尝试调整 filterStatus 使深链记录可见
      if (urlSubmissionId === selected.id) {
        const item = items.find(i => i.id === selected.id)
        if (item) {
          const s = SS.normalize(item.confirm_status)
          if (filterStatus === 'owner_actionable' && !SS.OWNER_ACTIONABLE.has(s)) {
            setFilterStatus('')
          } else if (filterStatus && filterStatus !== 'owner_actionable' && s !== filterStatus) {
            setFilterStatus('')
          }
        }
      } else {
        // 非深链：选第一条可见记录
        pickItem(visibleItems[0])
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleItems.length, selected, loading, urlSubmissionId, items, filterStatus])

  const selectedLogStatus = selected ? SS.normalize(selected.confirm_status) : ''
  const opLogs = selected && selectedLogStatus !== SS.S_NEW && selectedLogStatus !== SS.S_PENDING_OWNER
    ? [selected]
    : []
  const selectedResult = selected ? (getHumanResult(selected) || getAIResult(selected)) : null
  const hasTaskReports = Array.isArray(selectedResult?.task_reports) && (selectedResult!.task_reports as unknown[]).length > 0
  const assetProjection = buildConfirmationAssetProjection(selectedResult)
  const submissionAchievements = assetProjection.submissionAchievements
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
  const selectedStatus = SS.normalize(selected?.confirm_status)
  const hasAnyPersistedTaskCard = taskCards.some((card) => card.isPersistedTaskCard)
  const hasPendingSubmissionCards = taskCards.some((card) =>
    card.confirmationStatus === 'transferred_to_coordinator' ||
    card.confirmationStatus === ('pending_ceo_' + 'decision'),
  )
  const submissionActionsLocked = acting || projectArchived || hasPendingSubmissionCards
  const activeCardIndex = Math.min(selectedCardIndex, Math.max(taskCards.length - 1, 0))
  const activeCard = taskCards[activeCardIndex]
  /** 调用后端单卡 API 时使用的索引：使用后端原始索引，fallback 时不可调用 */
  const activeCardBackendIndex = activeCard?.isPersistedTaskCard ? activeCard.backendCardIndex! : null
  const cardWaitingCoordinator =
    activeCard?.confirmationStatus === 'transferred_to_coordinator'
  const activeReviewCard = activeCard ? normalizeReviewCardData(activeCard, {
    cardIndex: activeCardIndex,
    totalCards: taskCards.length,
    fallbackProjectName: selectedProjectName || editProject,
    fallbackTaskName: confirmationContext.keyTaskName || selected?.related_task || '',
  }) : null
  const originalTranscript = String(selected?.transcript_text || '').trim()
  const activeReviewEvidence = activeReviewCard?.evidence.length
    ? activeReviewCard.evidence
    : taskCards.length === 1 && originalTranscript
      ? [originalTranscript]
      : []

  const isProcessed = selected && SS.normalize(selected.confirm_status) !== SS.S_NEW
  const isConfirmed = selected ? SS.CONFIRMED_AND_STORED.has(SS.normalize(selected.confirm_status)) : false

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

  const effectivePendingItems = assetProjection.allIssues
  const hasPendingItems = effectivePendingItems.length > 0
  const canEditSubmissionIssues = viewMode === 'all' && canUseOwnerActions && Boolean(selected) && SS.OWNER_ACTIONABLE.has(selectedStatus)

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <header data-confirm-header="compact" className="flex-shrink-0 bg-white border-b px-5 py-3" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex items-center gap-2">
          <h1 className="mr-2 whitespace-nowrap text-lg font-bold text-slate-900">AI 确认中心</h1>
          <div className="flex items-center gap-2 flex-1 min-w-0">
            {/* Tab buttons */}
            <div className="flex rounded-lg border overflow-hidden" style={{ borderColor: '#E9EFF6' }}>
              {isReviewer && (
                <button onClick={() => switchView('all')} disabled={coordinatorInteractionLocked} className={`px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1 ${viewMode === 'all' ? 'bg-blue-600 text-white' : 'bg-white text-slate-500 hover:bg-slate-50'}`}>
                  待确认
                  {pendingCount > 0 && <span className={`px-1.5 py-0.5 rounded-full text-xs font-bold ${viewMode === 'all' ? 'bg-white/20 text-white' : 'bg-orange-100 text-orange-600'}`}>{pendingCount}</span>}
                </button>
              )}
              {canUseCoordinatorView && (
                <button onClick={() => switchView('coordinator')} disabled={coordinatorInteractionLocked} className={`px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1 ${viewMode === 'coordinator' ? 'bg-blue-600 text-white' : 'bg-white text-slate-500 hover:bg-slate-50'}`}>
                  待我统筹
                  {items.length > 0 && viewMode !== 'coordinator' && <span className="px-1.5 py-0.5 rounded-full text-xs font-bold bg-purple-100 text-purple-600">{items.filter(i => SS.normalize(i.confirm_status) === SS.S_WAITING_COORDINATOR).length || 0}</span>}
                </button>
              )}
              {canUseCoachDecisionView && (
                <button onClick={() => switchView('ceo')} disabled={coordinatorInteractionLocked} className={`px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1 ${viewMode === 'ceo' ? 'bg-blue-600 text-white' : 'bg-white text-slate-500 hover:bg-slate-50'}`}>
                  待我决策
                  {items.length > 0 && viewMode !== 'ceo' && <span className="px-1.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-700">{items.filter(i => SS.normalize(i.confirm_status) === SS.S_WAITING_CEO).length || 0}</span>}
                </button>
              )}
            </div>

            {/* Filters & search - all views consistent */}
            <select value={filterProject} onChange={(e) => setFilterProject(e.target.value)} className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white text-slate-600 cursor-pointer focus:outline-none min-w-[110px]">
              <option value="">全部项目</option>
              {allProjects.map((p) => <option key={p}>{p}</option>)}
            </select>
            {viewMode === 'all' && (
              <select value={filterSubmitter} onChange={(e) => setFilterSubmitter(e.target.value)} className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white text-slate-600 cursor-pointer focus:outline-none min-w-[110px]">
                <option value="">全部提交人</option>
                {allSubmitters.map((s) => <option key={s}>{s}</option>)}
              </select>
            )}
            {!isCoachView && !isCoordinatorView && (
              <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 bg-white text-slate-600 cursor-pointer focus:outline-none min-w-[100px]">
                <option value="">全部状态</option>
                <option value="owner_actionable">待负责人处理</option>
                <option value={SS.S_RETURNED}>已退回</option>
                <option value={SS.S_WAITING_COORDINATOR}>已转交统筹</option>
                <option value={SS.S_WAITING_CEO}>待企业教练决策</option>
                <option value={SS.S_CONFIRMED}>已入库</option>
              </select>
            )}
            <div className="relative ml-auto">
              <IconSearch size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} type="text" placeholder="搜索记录/任务卡…" className="pl-7 pr-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:border-blue-300 w-40" />
            </div>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-hidden flex flex-col p-4 gap-3" style={{ background: '#F1F5F9' }}>
        <div data-confirm-layout="three-column" className="flex-1 overflow-hidden min-h-0" style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 0.8fr) minmax(500px, 1.6fr) minmax(280px, 0.9fr)', gap: '12px' }}>

          {/* Left: queue panel */}
          <section data-confirm-panel="queue" className="flex flex-col bg-white rounded-2xl border overflow-hidden" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
            {/* Panel header with numbered badge */}
            <div className="px-4 py-3 border-b flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
              <div className="flex items-center gap-2">
                <span className="flex-shrink-0 w-5 h-5 rounded-md bg-blue-500 text-white text-[11px] font-bold flex items-center justify-center">1</span>
                <span className="text-sm font-bold text-slate-800">审核队列</span>
                <span className="text-xs text-slate-400">（找记录）</span>
              </div>
            </div>

            {/* List */}
            <div className="overflow-y-auto flex-1 px-3 py-2 space-y-2">
              {loadError && !loading && visibleItems.length > 0 && (
                <div className="rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-xs text-red-600">{loadError}</div>
              )}
              {loading ? (
                <div className="py-10 text-center text-xs text-slate-400 flex flex-col items-center gap-2">
                  <IconFileText size={28} className="text-slate-300" />
                  加载中…
                </div>
              ) : visibleItems.length === 0 ? (
                <div className="py-10 text-center text-xs text-slate-400 flex flex-col items-center gap-2">
                  <IconFileText size={28} className="text-slate-300" />
                  <span>
                    {loadError ? loadError : viewMode === 'ceo' ? '暂无待决策事项' : viewMode === 'coordinator' ? '暂无待统筹事项' : viewMode === 'all' ? '暂无待确认事项' : '暂无提交记录'}
                  </span>
                </div>
              ) : visibleItems.map((item) => {
                const isSelected = selected?.id === item.id
                const r = getHumanResult(item) || getAIResult(item)
                const summary = String(r?.summary || item.title || '').slice(0, 36)
                const normStatus = SS.normalize(item.confirm_status)

                // Status dot color
                let statusDotColor = '#94A3B8'
                let statusTagLabel = ''
                let statusTagBg = ''
                let statusTagText = ''
                if (normStatus === SS.S_NEW || normStatus === SS.S_PENDING_OWNER) {
                  statusDotColor = '#3B82F6'
                  statusTagLabel = 'NEW'
                  statusTagBg = '#DBEAFE'
                  statusTagText = '#1D4ED8'
                } else if (normStatus === SS.S_WAITING_COORDINATOR) {
                  statusDotColor = '#8B5CF6'
                  statusTagLabel = 'PENDING_COORD'
                  statusTagBg = '#EDE9FE'
                  statusTagText = '#6D28D9'
                } else if (normStatus === SS.S_CONFIRMED) {
                  statusDotColor = '#10B981'
                } else if (normStatus === SS.S_RETURNED) {
                  statusDotColor = '#EF4444'
                }

                return (
                  <div
                    key={item.id}
                    onClick={() => {
                      if (isCoordinatorView && coordinatorActing) return
                      pickItem(item)
                    }}
                    aria-disabled={isCoordinatorView && coordinatorActing}
                    className={`group px-3 py-2.5 transition-all border rounded-xl ${isCoordinatorView && coordinatorActing ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'}`}
                    style={{
                      borderColor: isSelected ? '#93C5FD' : '#F1F5F9',
                      background: isSelected ? '#EFF6FF' : undefined,
                      boxShadow: isSelected ? '0 1px 6px rgba(37,99,235,0.08)' : undefined,
                    }}
                  >
                    <div className="flex items-start gap-2.5">
                      {/* Status dot */}
                      <span className="mt-1.5 w-2 h-2 rounded-full flex-shrink-0" style={{ background: statusDotColor }} />

                      <div className="min-w-0 flex-1">
                        {/* Title row */}
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-[13px] font-medium text-slate-700 leading-5 line-clamp-2">{summary || '—'}</p>
                          <span className="text-[11px] text-slate-400 font-medium flex-shrink-0">{taskCards.length > 0 ? taskCards.length : ''}</span>
                        </div>

                        {/* Meta row */}
                        <div className="mt-1.5 flex items-center gap-2 flex-wrap">
                          {statusTagLabel && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold" style={{ background: statusTagBg, color: statusTagText }}>
                              {statusTagLabel}
                            </span>
                          )}
                          <span className="text-[11px] text-slate-400 truncate max-w-[120px]">{projectNameFromConfirmation(item, projects)}</span>
                          <span className="text-[10px] text-slate-300">·</span>
                          <span className="text-[11px] text-slate-400">{fmtShort(item.created_at)}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}

              {/* Bottom hint */}
              {visibleItems.length > 0 && (
                <div className="py-2 text-center">
                  <span className="text-[11px] text-slate-400">已加载全部</span>
                </div>
              )}
            </div>
          </section>

          {/* Center: review panel */}
          <section data-confirm-panel="review" className="flex flex-col bg-white rounded-2xl border overflow-hidden" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
            {/* Panel header with numbered badge */}
            <div className="px-4 py-3 border-b flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
              <div className="flex items-center gap-2">
                <span className="flex-shrink-0 w-5 h-5 rounded-md bg-purple-500 text-white text-[11px] font-bold flex items-center justify-center">2</span>
                <span className="text-sm font-bold text-slate-800">审核内容</span>
                <span className="text-xs text-slate-400">（看内容）</span>
              </div>
            </div>

            {selected ? (
              <>
                <div className="flex-1 overflow-y-auto min-h-0 px-4 py-3 space-y-4">
                  {taskCards.length > 1 && (
                  <div data-confirm-task-switch className="flex gap-2 overflow-x-auto border-b border-slate-100 pb-3">
                    {taskCards.map((card, cardIndex) => {
                      const isActive = cardIndex === activeCardIndex
                      return (
                        <button type="button" key={card.id + '-switch-' + cardIndex}
                          onClick={() => {
                            if (coordinatorInteractionLocked) return
                            setSelectedCardIndex(cardIndex)
                            setCoordinatorCardNote('')
                            setPendingAction(null)
                            setActionNote('')
                          }}
                          disabled={coordinatorInteractionLocked}
                          className={'min-w-[160px] rounded-xl border px-3 py-2 text-left transition disabled:opacity-50 ' + (isActive ? 'border-blue-300 bg-blue-50 text-blue-700' : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50')}>
                          <span className="block text-[10px] text-slate-400">任务卡 {cardIndex + 1}/{taskCards.length}</span>
                          <span className="mt-1 block truncate text-xs font-bold">{card.structure.projectName} · {card.structure.subtaskName !== '-' ? card.structure.subtaskName : card.title}</span>
                        </button>
                      )
                    })}
                  </div>
                  )}

                  {activeCard && activeReviewCard ? (
                    <article data-confirm-card-detail className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                      <header className="flex items-start justify-between gap-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white px-5 py-4">
                        <div className="min-w-0">
                          <div className="mb-1 flex items-center gap-2">
                            <span className="text-[10px] font-bold text-blue-600">{activeCard.isPersistedTaskCard ? activeReviewCard.cardIndexText : '本次提交概览'}</span>
                            <span className={'rounded-full px-2 py-0.5 text-[10px] font-bold ' + taskCardDecisionTone(activeCard.confirmationStatus)}>{taskCardDecisionLabel(activeCard.confirmationStatus)}</span>
                          </div>
                          <h2 className="text-lg font-bold text-slate-900">{activeReviewCard.title || '—'}</h2>
                        </div>
                      </header>

                      <div className="space-y-3 p-4">
                        <section className="rounded-xl border-l-4 border-blue-400 bg-blue-50/60 px-4 py-3">
                          <h3 className="text-xs font-bold text-slate-700">原文证据</h3>
                          {activeReviewEvidence.length > 0 ? (
                            <div className="mt-2 space-y-1.5">{activeReviewEvidence.map((item, index) => <p key={index} className="text-sm leading-6 text-slate-600">“{item}”</p>)}</div>
                          ) : <p className="mt-2 text-sm text-slate-400">—</p>}
                        </section>

                        <div className="grid grid-cols-2 gap-3">
                          {[
                            { title: '本次完成', items: activeReviewCard.completed, tone: 'border-emerald-100', titleClass: 'text-emerald-700' },
                            { title: '下一步计划', items: activeReviewCard.nextSteps, tone: 'border-blue-100', titleClass: 'text-blue-700' },
                            { title: '问题与风险', items: activeReviewCard.pendingItems, tone: 'border-orange-100', titleClass: 'text-orange-700' },
                            { title: '取得的成果', items: activeReviewCard.achievements, tone: 'border-violet-100', titleClass: 'text-violet-700' },
                          ].map((section) => (
                            <section key={section.title} className={'min-h-[116px] rounded-xl border bg-white p-4 ' + section.tone}>
                              <h3 className={'text-xs font-bold ' + section.titleClass}>{section.title}</h3>
                              {section.items.length > 0 ? (
                                <ul className="mt-2 space-y-1.5">{section.items.map((item, index) => <li key={index} className="text-sm leading-6 text-slate-600">• {item}</li>)}</ul>
                              ) : <p className="mt-2 text-sm text-slate-400">—</p>}
                            </section>
                          ))}
                        </div>

                        {(activeCard.coordinatorNote || activeCard.ceoNote) && (
                          <div className="grid grid-cols-2 gap-3">
                            {activeCard.coordinatorNote && (
                              <section className="min-h-[96px] rounded-xl border border-indigo-100 bg-indigo-50/30 p-4">
                                <h3 className="text-xs font-bold text-indigo-800">统筹反馈</h3>
                                <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-600">{activeCard.coordinatorNote}</p>
                              </section>
                            )}
                            {activeCard.ceoNote && (
                              <section className="min-h-[96px] rounded-xl border border-violet-100 bg-violet-50/30 p-4">
                                <h3 className="text-xs font-bold text-violet-800">企业教练批示</h3>
                                <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-600">{activeCard.ceoNote}</p>
                              </section>
                            )}
                          </div>
                        )}
                      </div>
                    </article>
                  ) : (
                    <div className="flex min-h-72 items-center justify-center text-sm text-slate-400">暂无可审核内容</div>
                  )}

                  {/* 操作日志 */}
                  <div className="rounded-xl border-t pt-3" style={{ borderColor: '#E9EFF6' }}>
                    <button onClick={() => setOpLogsOpen(!opLogsOpen)} className="flex items-center justify-between w-full group">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-700">操作日志</span>
                        <span className="px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-500">{opLogs.length}</span>
                      </div>
                      <IconChevronDown size={12} className={`text-slate-400 transition-transform ${opLogsOpen ? 'rotate-180' : ''}`} />
                    </button>
                    {opLogsOpen && (
                      <div className="mt-2 max-h-40 overflow-y-auto space-y-1">
                        {opLogs.length === 0 ? (
                          <p className="text-xs text-slate-400 text-center py-3">暂无操作记录</p>
                        ) : opLogs.map((item, idx) => {
                          const action = getConfirmActionLabel(item.confirm_status)
                          const time = fmtShort((item as Record<string, unknown>).updated_at as string || item.created_at)
                          const isDone = SS.CONFIRMED_AND_STORED.has(SS.normalize(item.confirm_status))
                          const dotColor = isDone ? '#3B82F6' : SS.normalize(item.confirm_status) === SS.S_RETURNED ? '#F97316' : '#8B5CF6'
                          return (
                            <div key={item.id} className="flex items-start gap-2 px-2 py-1.5 rounded-md hover:bg-slate-50">
                              <span className="mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: dotColor }} />
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center justify-between">
                                  <span className="text-xs font-medium text-slate-700">{action}</span>
                                  <span className="text-[10px] text-slate-400">{time}</span>
                                </div>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                </div>

              </>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center py-12 text-slate-400">
                <IconMail size={32} className="text-slate-300 mb-3" />
                <p className="text-sm">请从左侧队列选择一条提交记录</p>
              </div>
            )}
          </section>
          {/* Right: action-preview panel */}
          <aside data-confirm-panel="action-preview" className="flex flex-col bg-white rounded-2xl border overflow-hidden" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
            {/* Panel header with numbered badge */}
            <div className="px-4 py-3 border-b flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
              <div className="flex items-center gap-2">
                <span className="flex-shrink-0 w-5 h-5 rounded-md bg-amber-500 text-white text-[11px] font-bold flex items-center justify-center">3</span>
                <span className="text-sm font-bold text-slate-800">判断与入库</span>
                <span className="text-xs text-slate-400">（处理操作）</span>
              </div>
            </div>

            <div className="overflow-y-auto flex-1 px-4 py-3">
              {selected ? (
                <div className="space-y-4">
                  <section>
                    <div className="mb-2.5 flex items-center justify-between gap-3">
                      <h3 className="text-xs font-bold text-slate-700">当前记录概览</h3>
                      <button type="button" onClick={() => setShowTranscript(true)} className="text-xs font-medium text-blue-600 hover:text-blue-700">查看原始内容</button>
                    </div>
                    <div className="space-y-2 rounded-xl border border-slate-100 bg-slate-50/60 p-3 text-xs">
                      <div className="flex justify-between"><span className="w-14 flex-shrink-0 text-slate-400">项目</span><span className="truncate font-medium text-slate-700">{selectedProjectName || '—'}</span></div>
                      <div className="flex justify-between"><span className="w-14 flex-shrink-0 text-slate-400">提交人</span><span className="font-medium text-slate-700">{selected?.submitter || '—'}</span></div>
                      <div className="flex items-center justify-between"><span className="w-14 flex-shrink-0 text-slate-400">来源</span><SourceBadge type={selected?.source_type} /></div>
                      <div className="flex justify-between"><span className="w-14 flex-shrink-0 text-slate-400">时间</span><span className="font-medium text-slate-700">{fmtShort(selected?.created_at)}</span></div>
                      <div className="flex items-center justify-between"><span className="w-14 flex-shrink-0 text-slate-400">状态</span><StatusBadge status={selected?.confirm_status} /></div>
                      <div className="flex justify-between"><span className="w-14 flex-shrink-0 text-slate-400">记录ID</span><span className="font-medium text-slate-700">{String((selected as Record<string, unknown>).record_id || selected.id)}</span></div>
                    </div>
                  </section>

                  {activeCard?.isPersistedTaskCard && (
                    <section className="rounded-xl border border-blue-100 bg-blue-50/60 p-3">
                      <p className="text-[10px] text-slate-400">当前审批对象 · 任务卡 {activeCardIndex + 1}/{taskCards.length}</p>
                      <p className="mt-1 text-xs font-bold leading-5 text-blue-700">{activeCard.structure.projectName || '—'} &gt; {activeCard.structure.keyTaskName || '—'} &gt; {activeCard.structure.subtaskName || '—'}</p>
                    </section>
                  )}

                  {(actionError || actionSuccess) && (
                    <div className="space-y-2">
                      {actionError && <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"><IconAlertCircle size={14} />{actionError}</div>}
                      {actionSuccess && <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700"><IconCheckCircle size={14} />{actionSuccess}</div>}
                    </div>
                  )}

                  {viewMode === 'all' && canUseOwnerActions && SS.OWNER_ACTIONABLE.has(selectedStatus) && activeCard?.isPersistedTaskCard && (
                    <section data-confirm-card-actions>
                      <h3 className="mb-2.5 text-sm font-bold text-slate-800">负责人操作</h3>
                      {projectArchived && <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">项目已归档，无法执行操作。</div>}
                      {cardWaitingCoordinator && <div className="mb-3 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-xs text-violet-700">当前任务卡正在等待统筹反馈，暂不可继续处理。</div>}

                      <div className="space-y-2">
                        <button type="button" onClick={() => { setPendingAction(null); setActionNote(''); void handleTaskCardDecision('confirm') }} disabled={acting || projectArchived || cardWaitingCoordinator} className="h-10 w-full rounded-lg bg-blue-600 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50">确认当前任务卡入库</button>
                        <button type="button" onClick={() => { setPendingAction('return'); setActionNote('') }} disabled={acting || projectArchived || cardWaitingCoordinator} className="h-10 w-full rounded-lg border border-orange-300 bg-white text-sm font-semibold text-orange-600 transition hover:bg-orange-50 disabled:opacity-50">退回当前任务卡</button>
                        {!cardWaitingCoordinator && activeCard.confirmationStatus !== 'coordinator_given' && (
                          <button type="button" onClick={() => { setPendingAction('transfer'); setActionNote('') }} disabled={acting || projectArchived} className="h-10 w-full rounded-lg border border-violet-300 bg-white text-sm font-semibold text-violet-600 transition hover:bg-violet-50 disabled:opacity-50">转交统筹人</button>
                        )}
                        <button type="button" onClick={() => { setPendingAction('ceo'); setActionNote('') }} disabled={acting || projectArchived || cardWaitingCoordinator} className="h-10 w-full rounded-lg border border-slate-300 bg-white text-sm font-semibold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50">转交企业教练</button>
                      </div>

                      {pendingAction && (
                        <div data-confirm-action-note className="mt-3 rounded-xl border border-slate-200 bg-slate-50/60 p-3">
                          <p className="text-xs font-bold text-slate-700">
                            {pendingAction === 'return' ? '退回原因' : pendingAction === 'transfer' ? '转交统筹说明' : '转交企业教练说明'}
                            <span className="ml-1 text-red-500">*</span>
                          </p>
                          <textarea value={actionNote} onChange={(event) => setActionNote(event.target.value)} placeholder={pendingAction === 'return' ? '请说明需要提交人修改的内容…' : pendingAction === 'transfer' ? '请说明需要统筹人反馈或协调的事项…' : '请说明需要企业教练决策的事项…'} disabled={acting} className="mt-2 min-h-20 w-full resize-none rounded-lg border border-slate-200 bg-white p-3 text-sm focus:border-blue-300 focus:outline-none" />
                          <div className="mt-3 flex gap-2">
                            <button type="button" onClick={() => { setPendingAction(null); setActionNote('') }} disabled={acting} className="h-9 flex-1 rounded-lg border border-slate-200 bg-white text-xs text-slate-600">取消</button>
                            <button type="button" onClick={() => void handleTaskCardDecision(pendingAction)} disabled={acting || !actionNote.trim()} className="h-9 flex-1 rounded-lg bg-blue-600 text-xs font-bold text-white disabled:opacity-50">确认提交</button>
                          </div>
                        </div>
                      )}
                      <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-[10px] leading-5 text-slate-500">确认无需填写说明；退回或转交时才填写对应原因。操作仅作用于当前任务卡。</p>
                    </section>
                  )}

                  {viewMode === 'all' && canUseOwnerActions && SS.OWNER_ACTIONABLE.has(selectedStatus) && !hasAnyPersistedTaskCard && (
                    <>
                      <section className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-700">
                        本次提交未生成结构化任务卡，将自动使用整条提交兼容流程。
                      </section>
                      <section className="rounded-xl border border-slate-200 p-3">
                        <h3 className="mb-2 text-sm font-bold text-slate-900">入库范围</h3>
                        <p className="mb-2 text-[11px] text-slate-500">工作推进表始终写入；成果和问题按现有开关处理。</p>
                        <button type="button" role="switch" aria-checked={writeToAchievements} onClick={() => setWriteToAchievements((value) => !value)} disabled={submissionActionsLocked} className="mb-2 flex w-full items-center justify-between rounded-lg border border-slate-200 px-3 py-2"><span className="text-xs font-semibold">成果库</span><ToggleSwitch on={writeToAchievements} /></button>
                        <button type="button" role="switch" aria-checked={writeToIssues} onClick={() => setWriteToIssues((value) => !value)} disabled={submissionActionsLocked} className="flex w-full items-center justify-between rounded-lg border border-slate-200 px-3 py-2"><span className="text-xs font-semibold">问题中心</span><ToggleSwitch on={writeToIssues} /></button>
                      </section>
                      <section>
                        <h3 className="mb-2 text-sm font-bold text-slate-800">整条提交操作</h3>
                        <div className="space-y-2">
                          <button type="button" onClick={handleConfirm} disabled={submissionActionsLocked} className="h-10 w-full rounded-lg bg-blue-600 text-sm font-semibold text-white disabled:opacity-50">确认入库</button>
                          <button type="button" onClick={() => { setPendingAction('return'); setActionNote('') }} disabled={submissionActionsLocked} className="h-10 w-full rounded-lg border border-orange-200 bg-white text-sm font-semibold text-orange-600 disabled:opacity-50">退回提交人</button>
                          <button type="button" onClick={() => { setPendingAction('transfer'); setActionNote('') }} disabled={submissionActionsLocked || !SS.TRANSFERABLE_TO_COORDINATOR.has(selectedStatus)} className="h-10 w-full rounded-lg border border-violet-200 bg-white text-sm font-semibold text-violet-600 disabled:opacity-50">转交统筹人</button>
                          <button type="button" onClick={() => { setPendingAction('ceo'); setActionNote('') }} disabled={submissionActionsLocked || !SS.ESCALATABLE_TO_CEO.has(selectedStatus)} className="h-10 w-full rounded-lg border border-slate-200 bg-white text-sm font-semibold text-slate-600 disabled:opacity-50">转交企业教练</button>
                        </div>
                        {pendingAction && (
                          <div className="mt-3 rounded-xl border border-slate-200 p-3">
                            <p className="text-xs font-bold text-slate-700">{pendingAction === 'return' ? '退回原因' : pendingAction === 'transfer' ? '转交统筹说明' : '转交企业教练说明'}<span className="ml-1 text-red-500">*</span></p>
                            <textarea value={actionNote} onChange={(event) => setActionNote(event.target.value)} disabled={acting} className="mt-2 min-h-20 w-full resize-none rounded-lg border border-slate-200 p-3 text-sm" />
                            <div className="mt-3 flex gap-2"><button type="button" onClick={() => { setPendingAction(null); setActionNote('') }} className="h-9 flex-1 rounded-lg border border-slate-200">取消</button><button type="button" onClick={() => handleDecision(pendingAction)} disabled={acting || !actionNote.trim()} className="h-9 flex-1 rounded-lg bg-blue-600 text-white disabled:opacity-50">确认提交</button></div>
                          </div>
                        )}
                      </section>
                    </>
                  )}

                  {/* ===== COORDINATOR VIEW ===== */}
                  {viewMode === 'coordinator' && (
                    <div className="space-y-4">
                      {/* 提交级统筹反馈 */}
                      {selected && selected.coordinator_decision_scope === 'submission' ? (
                        <section className="rounded-xl border p-3" style={{ borderColor: '#A5B4FC', background: 'linear-gradient(135deg,#EEF2FF,#E0E7FF)' }}>
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-sm font-bold text-indigo-800">提供统筹意见</span>
                            <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-indigo-100 text-indigo-700">整条提交</span>
                          </div>
                          <div className="mb-3 p-2 rounded-lg bg-white/70 text-xs text-slate-600">
                            <span className="font-semibold">负责人转交说明：</span>{selected.reject_reason || '（无）'}
                          </div>
                          <textarea value={coordinatorNote} onChange={(e) => setCoordinatorNote(e.target.value)} placeholder="请输入统筹反馈意见（必填）…" disabled={coordinatorActing} className="w-full border border-indigo-200 rounded-xl p-3 text-sm focus:outline-none resize-none mb-3 disabled:opacity-50" style={{ minHeight: 72, background: 'white' }} />
                          <button onClick={handleCoordinatorFeedback} disabled={coordinatorActing || !coordinatorNote.trim()} className="w-full py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 disabled:opacity-50" style={{ background: 'linear-gradient(135deg,#4F46E5,#818CF8)' }}>
                            {coordinatorActing ? '提交中…' : '提交反馈'}
                          </button>
                        </section>
                      ) : (
                        <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-3 text-center text-sm text-slate-400">
                          无需提交级统筹反馈
                        </div>
                      )}

                      {/* 任务卡级统筹反馈 */}
                      {activeCard && activeCard.isPersistedTaskCard && activeCard.confirmationStatus === 'transferred_to_coordinator' && (
                        <section className="rounded-xl border p-3" style={{ borderColor: '#A5B4FC', background: 'linear-gradient(135deg,#EEF2FF,#E0E7FF)' }}>
                          <div className="flex items-center justify-between gap-2 mb-2">
                            <span className="text-sm font-bold text-indigo-800">单卡统筹反馈</span>
                            <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-violet-100 text-violet-600">待统筹</span>
                          </div>
                          <div className="mb-3 p-2 rounded-lg bg-white/70 text-xs text-slate-600 space-y-1">
                            <div><span className="font-semibold">任务卡：</span>任务卡 {activeCardIndex + 1}</div>
                            <div><span className="font-semibold">负责人转交说明：</span>{activeCard.coordinatorRequestNote || '（无）'}</div>
                          </div>
                          <textarea value={coordinatorCardNote} onChange={(e) => setCoordinatorCardNote(e.target.value)} placeholder="请输入当前任务卡的统筹反馈（必填）…" disabled={coordinatorActing} className="w-full border border-indigo-200 rounded-xl p-3 text-sm focus:outline-none resize-none mb-3 disabled:opacity-50" style={{ minHeight: 72, background: 'white' }} />
                          <button onClick={handleCoordinatorCardFeedback} disabled={coordinatorActing || !coordinatorCardNote.trim()} className="w-full py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 disabled:opacity-50" style={{ background: 'linear-gradient(135deg,#4F46E5,#818CF8)' }}>
                            {coordinatorActing ? '提交中…' : '提交反馈'}
                          </button>
                        </section>
                      )}
                    </div>
                  )}

                  {/* ===== CEO VIEW ===== */}
                  {viewMode === 'ceo' && (
                    <div className="space-y-4">
                      {/* 提交级企业教练批示 */}
                      {selected && selected.ceo_decision_scope === 'submission' ? (
                        <section className="rounded-xl border p-3" style={{ borderColor: '#C4B5FD', background: 'linear-gradient(135deg,#F5F3FF,#EEF2FF)' }}>
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-sm font-bold text-violet-800">企业教练批示</span>
                            <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-violet-100 text-violet-700">整条提交</span>
                          </div>
                          <div className="mb-3 p-2 rounded-lg bg-white/70 text-xs text-slate-600">
                            <span className="font-semibold">负责人上报说明：</span>{selected.reject_reason || selected.ceo_note || '（无）'}
                          </div>
                          <textarea value={coachNote} onChange={(e) => setCoachNote(e.target.value)} placeholder="请输入企业教练批示意见（必填）…" className="w-full border border-violet-200 rounded-xl p-3 text-sm focus:outline-none resize-none mb-3" style={{ minHeight: 72, background: 'white' }} />
                          <button onClick={handleCoachSubmissionDecide} disabled={coachActing || !coachNote.trim()} className="w-full py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 disabled:opacity-50" style={{ background: 'linear-gradient(135deg,#7C3AED,#A78BFA)' }}>
                            {coachActing ? '提交中…' : '提交企业教练批示'}
                          </button>
                        </section>
                      ) : (
                        <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-3 text-center text-sm text-slate-400">
                          无需提交级企业教练批示
                        </div>
                      )}

                      {/* 单卡企业教练批示 */}
                      {activeCard && activeCard.isPersistedTaskCard && activeCard.confirmationStatus === 'pending_ceo_decision' && (
                        <section className="rounded-xl border p-3" style={{ borderColor: '#C4B5FD', background: 'linear-gradient(135deg,#F5F3FF,#EEF2FF)' }}>
                          <div className="flex items-center justify-between gap-2 mb-2">
                            <span className="text-sm font-bold text-violet-800">单卡企业教练批示</span>
                            <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-sky-100 text-sky-600">待决策</span>
                          </div>
                          <div className="mb-3 p-2 rounded-lg bg-white/70 text-xs text-slate-600 space-y-1">
                            <div><span className="font-semibold">任务卡：</span>任务卡 {activeCardIndex + 1}</div>
                            {activeCard.confirmationNote && <div><span className="font-semibold">负责人上报说明：</span>{activeCard.confirmationNote}</div>}
                          </div>
                          <textarea value={coachNote} onChange={(e) => setCoachNote(e.target.value)} placeholder="请输入企业教练批示意见（必填）…" className="w-full border border-violet-200 rounded-xl p-3 text-sm focus:outline-none resize-none mb-3" style={{ minHeight: 72, background: 'white' }} />
                          <button onClick={handleCoachCardDecide} disabled={coachActing || !coachNote.trim()} className="w-full py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 disabled:opacity-50" style={{ background: 'linear-gradient(135deg,#7C3AED,#A78BFA)' }}>
                            {coachActing ? '提交中…' : '提交企业教练批示'}
                          </button>
                        </section>
                      )}
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex-1 flex items-center justify-center text-slate-400 text-sm text-center py-12">
                  {viewMode === 'all' ? '请选择左侧记录查看审核操作' : '请选择左侧记录查看审核概览'}
                </div>
              )}
            </div>
          </aside>
        </div>

      </div>

      {/* 原始内容弹窗 */}
      {showTranscript && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-6" onClick={() => setShowTranscript(false)}>
          <div className="relative w-full max-w-2xl max-h-[80vh] bg-white rounded-2xl shadow-xl flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: '#E9EFF6' }}>
              <h2 className="text-sm font-bold text-slate-800">原始提交内容</h2>
              <button type="button" onClick={() => setShowTranscript(false)} className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors">
                <IconX />
              </button>
            </div>
            <div className="overflow-y-auto flex-1 p-5">
              {originalTranscript ? (
                <pre className="whitespace-pre-wrap break-words text-sm text-slate-700 leading-relaxed font-sans">{originalTranscript}</pre>
              ) : (
                <p className="text-sm text-slate-400 text-center py-12">暂无原始内容</p>
              )}
            </div>
            <div className="flex items-center justify-between px-5 py-3 border-t bg-slate-50/60" style={{ borderColor: '#E9EFF6' }}>
              <span className="text-xs text-slate-400">
                {selected?.submitter && `提交人：${selected.submitter}`}
                {selected?.created_at && ` · ${fmtShort(selected.created_at)}`}
              </span>
              <button type="button" onClick={() => setShowTranscript(false)} className="px-4 py-1.5 rounded-lg bg-white border border-slate-200 text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors">关闭</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
