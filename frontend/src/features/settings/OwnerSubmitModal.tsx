import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ownerSubmitProfile } from '../../api/projects'
import { applyInitAnalysisRun } from '../../api/projectInitAi'
import { fetchPeople } from '../../api/people'
import type { ProjectWorkProgressTaskDraft } from '../../api/projects'
import { toast } from '../../utils/toast'
import type { Person, Project } from '../../types'
import { OwnerSubmitAiPanel, type ProjectInitAiDecision } from './OwnerSubmitAiPanel'
import type { ProjectInitAiDraft, ProjectInitCurrentDraft } from '../../api/projectInitAi'
import { buildAiMergePreview, toCurrentDraft, toSubmitDraft, type OwnerSubmitAiDecision as DraftDecision, type OwnerSubmitMergePreview } from './ownerSubmitDraft'

type Props = {
  project: Project
  onClose: () => void
  onSuccess?: (result: Project & { submitted_for_review: boolean }) => void
}

type LocalSubTaskDraft = {
  id?: number
  subtask_id?: number
  title: string
  evaluation_standard: string
  assignee: string
  assigneeId: number | ''
  helper: string
  helperIds: number[]
  plan_start: string
  plan_end: string
  evidence?: Array<{ attachment_id: number | null; file_name: string; location: string; excerpt: string; source_label?: string }>
}

type LocalTaskDraft = {
  id?: number
  task_id?: number
  title: string
  description: string
  goal: string
  acceptance_criteria: string
  process: string
  owner: string
  helper: string
  plan_start: string
  plan_end: string
  subtasks: LocalSubTaskDraft[]
  evidence?: Array<{ attachment_id: number | null; file_name: string; location: string; excerpt: string; source_label?: string }>
}

type ParsedPeriod = {
  start: string
  end: string
}

const EMPTY_SUBTASK: LocalSubTaskDraft = {
  title: '',
  evaluation_standard: '',
  assignee: '',
  assigneeId: '',
  helper: '',
  helperIds: [],
  plan_start: '',
  plan_end: '',
}

const EMPTY_TASK: LocalTaskDraft = {
  title: '',
  description: '',
  goal: '',
  acceptance_criteria: '',
  process: '',
  owner: '',
  helper: '',
  plan_start: '',
  plan_end: '',
  subtasks: [{ ...EMPTY_SUBTASK }],
}

function cloneEmptyTask(): LocalTaskDraft {
  return { ...EMPTY_TASK, subtasks: [{ ...EMPTY_SUBTASK }] }
}

function taskStableIdentity(task: Pick<LocalTaskDraft, 'id' | 'task_id'>): string | null {
  if (typeof task.task_id === 'number') return `task:${task.task_id}`
  if (typeof task.id === 'number') return `id:${task.id}`
  return null
}

function taskContentIdentity(task: Pick<LocalTaskDraft, 'title' | 'description'>): string {
  return `${task.title.trim()}\u0000${task.description.trim()}`
}

function composeProjectPeriod(startDate?: string, endDate?: string): string {
  const start = (startDate ?? '').trim()
  const end = (endDate ?? '').trim()
  if (start && end) return `${start} 至 ${end}`
  return start || end
}

function composeTaskPeriod(startDate?: string, endDate?: string): string {
  const start = (startDate ?? '').trim()
  const end = (endDate ?? '').trim()
  if (start && end) return `${start} - ${end}`
  return start || end
}

function parseTaskPeriod(value: string): ParsedPeriod {
  return parsePeriodValue(value)
}

function parsePeriodValue(value: string): ParsedPeriod {
  const text = value.trim()
  if (!text) return { start: '', end: '' }

  for (const delimiter of ['至', '~', '到']) {
    if (!text.includes(delimiter)) continue
    const parts = text.split(delimiter).map((part) => part.trim()).filter(Boolean)
    if (parts.length >= 2) {
      return { start: parts[0], end: parts.slice(1).join(' ') }
    }
  }

  const spacedDashMatch = text.match(/^(.+?)\s+[-–—]\s+(.+)$/)
  if (spacedDashMatch) {
    return { start: spacedDashMatch[1].trim(), end: spacedDashMatch[2].trim() }
  }

  return { start: text, end: '' }
}

function toPayloadDraft(tasks: LocalTaskDraft[]): ProjectWorkProgressTaskDraft[] {
  return tasks
    .map((task) => ({
      ...(task.id !== undefined ? { id: task.id } : {}),
      ...(task.task_id !== undefined ? { task_id: task.task_id } : {}),
      title: task.title.trim(),
      description: task.description.trim(),
      goal: task.goal.trim() || task.description.trim(),
      acceptance_criteria: task.acceptance_criteria.trim(),
      process: task.process.trim(),
      owner: task.owner.trim(),
      helper: task.helper.trim(),
      plan_start: task.plan_start,
      plan_end: task.plan_end,
      subtasks: task.subtasks
        .map((subtask) => ({
          ...(subtask.id !== undefined ? { id: subtask.id } : {}),
          ...(subtask.subtask_id !== undefined ? { subtask_id: subtask.subtask_id } : {}),
          title: subtask.title.trim(),
          evaluation_standard: subtask.evaluation_standard.trim(),
          assignee: subtask.assignee.trim(),
          assignee_id: subtask.assigneeId || undefined,
          helper: subtask.helper.trim(),
          helper_ids: subtask.helperIds,
          plan_start: subtask.plan_start,
          plan_end: subtask.plan_end,
        }))
        .filter((subtask) => subtask.title),
    }))
    .filter((task) => task.title)
}

type PickerMenuPosition = {
  top?: number
  bottom?: number
  left: number
  width: number
  maxHeight: number
}

function getPickerMenuPosition(rect: DOMRect, minWidth: number): PickerMenuPosition {
  const viewportMargin = 12
  const gap = 6
  const viewportHeight = window.innerHeight
  const viewportWidth = window.innerWidth
  const spaceBelow = Math.max(0, viewportHeight - rect.bottom - viewportMargin)
  const spaceAbove = Math.max(0, rect.top - viewportMargin)
  const opensAbove = spaceBelow < 220 && spaceAbove > spaceBelow
  const availableSpace = opensAbove ? spaceAbove : spaceBelow
  const maxHeight = Math.max(96, Math.min(320, availableSpace))
  const width = Math.min(Math.max(rect.width, minWidth), Math.max(160, viewportWidth - viewportMargin * 2))
  const left = Math.min(Math.max(viewportMargin, rect.left), Math.max(viewportMargin, viewportWidth - width - viewportMargin))

  return {
    top: opensAbove ? undefined : rect.bottom + gap,
    bottom: opensAbove ? viewportHeight - rect.top + gap : undefined,
    left,
    width,
    maxHeight,
  }
}

function AssigneePicker({
  people,
  value,
  rawName,
  disabled,
  onChange,
}: {
  people: Person[]
  value: number | ''
  rawName: string
  disabled?: boolean
  onChange: (value: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [menuPosition, setMenuPosition] = useState<PickerMenuPosition | null>(null)
  const anchorRef = useRef<HTMLButtonElement | null>(null)
  const menuRef = useRef<HTMLDivElement | null>(null)
  const selected = people.find((person) => person.id === value)
  const hasPendingRawName = !selected && !value && Boolean(rawName.trim())
  const filtered = people.filter((person) => {
    const haystack = `${person.name} ${person.department ?? ''}`.toLowerCase()
    return haystack.includes(query.trim().toLowerCase())
  })

  useEffect(() => {
    if (!open) return undefined
    const closeMenu = (event: Event) => {
      if (menuRef.current?.contains(event.target as Node)) return
      setOpen(false)
    }
    window.addEventListener('scroll', closeMenu, true)
    window.addEventListener('resize', closeMenu)
    return () => {
      window.removeEventListener('scroll', closeMenu, true)
      window.removeEventListener('resize', closeMenu)
    }
  }, [open])

  function toggleOpen() {
    if (open) {
      setOpen(false)
      return
    }
    const rect = anchorRef.current?.getBoundingClientRect()
    if (!rect) return
    setMenuPosition(getPickerMenuPosition(rect, 240))
    setOpen(true)
  }

  return (
    <div className="relative">
      <button
        type="button"
        ref={anchorRef}
        disabled={disabled}
        onClick={toggleOpen}
        aria-expanded={open}
        aria-haspopup="listbox"
        className={`owner-submit-picker-trigger ${selected || hasPendingRawName ? 'owner-submit-picker-filled' : 'owner-submit-picker-empty'} flex h-9 w-full items-center justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2.5 text-left text-xs font-semibold text-slate-700 outline-none transition-colors hover:border-blue-300 hover:bg-white focus:border-blue-400 focus:bg-white focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60`}
      >
        <span className="truncate">{selected?.name ?? (hasPendingRawName ? <>待自动添加：{rawName.trim()}</> : '请选择负责人')}</span>
        <svg
          aria-hidden="true"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`owner-submit-picker-chevron shrink-0 h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`}
        >
          <path d="m4 6 4 4 4-4" />
        </svg>
      </button>
      {hasPendingRawName && <p className="mt-1 text-[10px] leading-4 text-slate-500">将在提交时自动添加或匹配人员</p>}
      {open && menuPosition && createPortal(
        <div
          ref={menuRef}
          className="fixed z-[100] flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white p-2 shadow-[0_16px_36px_rgba(15,23,42,0.18)]"
          style={{ top: menuPosition.top, bottom: menuPosition.bottom, left: menuPosition.left, width: menuPosition.width, maxHeight: menuPosition.maxHeight }}
          role="listbox"
        >
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索姓名或部门"
            className="mb-2 h-8 w-full rounded-lg border border-slate-200 bg-slate-50 px-2.5 text-xs text-slate-700 outline-none focus:border-blue-400 focus:bg-white"
          />
          <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto">
            <button
              type="button"
              onClick={() => { onChange(''); setOpen(false); setQuery('') }}
              className="w-full rounded-lg px-2.5 py-2 text-left text-xs text-slate-400 hover:bg-slate-50"
            >
              请选择负责人
            </button>
            {filtered.map((person) => (
              <button
                key={person.id}
                type="button"
                onClick={() => { onChange(String(person.id)); setOpen(false); setQuery('') }}
                className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-xs transition-colors hover:bg-blue-50 ${person.id === value ? 'bg-blue-50 text-blue-700' : 'text-slate-700'}`}
              >
                <span className="min-w-0 truncate font-semibold">{person.name}</span>
                <span className="ml-2 shrink-0 text-[10px] text-slate-400">{person.department || '未填写部门'}</span>
              </button>
            ))}
            {filtered.length === 0 && <p className="px-2.5 py-3 text-xs text-slate-400">未找到匹配人员</p>}
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}

function HelperPicker({
  people,
  value,
  excludedId,
  rawName,
  disabled,
  onChange,
}: {
  people: Person[]
  value: number[]
  excludedId: number | ''
  rawName: string
  disabled?: boolean
  onChange: (personId: number) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [menuPosition, setMenuPosition] = useState<PickerMenuPosition | null>(null)
  const anchorRef = useRef<HTMLButtonElement | null>(null)
  const menuRef = useRef<HTMLDivElement | null>(null)
  const selectedPeople = people.filter((person) => value.includes(person.id))
  const hasPendingRawName = value.length === 0 && Boolean(rawName.trim())
  const filtered = people.filter((person) => {
    if (person.id === excludedId) return false
    const haystack = `${person.name} ${person.department ?? ''}`.toLowerCase()
    return haystack.includes(query.trim().toLowerCase())
  })

  useEffect(() => {
    if (!open) return undefined
    const closeMenu = (event: Event) => {
      if (menuRef.current?.contains(event.target as Node)) return
      setOpen(false)
    }
    window.addEventListener('scroll', closeMenu, true)
    window.addEventListener('resize', closeMenu)
    return () => {
      window.removeEventListener('scroll', closeMenu, true)
      window.removeEventListener('resize', closeMenu)
    }
  }, [open])

  function toggleOpen() {
    if (open) {
      setOpen(false)
      return
    }
    const rect = anchorRef.current?.getBoundingClientRect()
    if (!rect) return
    setMenuPosition(getPickerMenuPosition(rect, 240))
    setOpen(true)
  }

  return (
    <div className="relative">
      <button
        type="button"
        ref={anchorRef}
        disabled={disabled}
        onClick={toggleOpen}
        aria-expanded={open}
        aria-haspopup="listbox"
        className={`owner-submit-picker-trigger ${selectedPeople.length > 0 || hasPendingRawName ? 'owner-submit-picker-filled' : 'owner-submit-picker-empty'} flex min-h-9 w-full items-center justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-left text-xs font-semibold text-slate-700 outline-none transition-colors hover:border-blue-300 hover:bg-white focus:border-blue-400 focus:bg-white focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60`}
      >
        <span className="min-w-0 truncate">
          {selectedPeople.length > 0 ? selectedPeople.map((person) => person.name).join('、') : (hasPendingRawName ? <>待自动添加：{rawName.trim()}</> : '请选择协助人')}
        </span>
        <svg
          aria-hidden="true"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`owner-submit-picker-chevron shrink-0 h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`}
        >
          <path d="m4 6 4 4 4-4" />
        </svg>
      </button>
      {hasPendingRawName && <p className="mt-1 text-[10px] leading-4 text-slate-500">将在提交时自动添加或匹配人员</p>}
      {open && menuPosition && createPortal(
        <div
          ref={menuRef}
          className="fixed z-[100] flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white p-2 shadow-[0_16px_36px_rgba(15,23,42,0.18)]"
          style={{ top: menuPosition.top, bottom: menuPosition.bottom, left: menuPosition.left, width: menuPosition.width, maxHeight: menuPosition.maxHeight }}
          role="listbox"
          aria-multiselectable="true"
        >
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索姓名或部门"
            className="mb-2 h-8 w-full rounded-lg border border-slate-200 bg-slate-50 px-2.5 text-xs text-slate-700 outline-none focus:border-blue-400 focus:bg-white"
          />
          <div className="mb-1 flex items-center justify-between px-2.5 text-[11px] text-slate-400">
            <span>{value.length > 0 ? `已选 ${value.length} 人` : '可多选协助人'}</span>
            {value.length > 0 && (
              <button
                type="button"
                onClick={() => value.forEach((personId) => onChange(personId))}
                className="font-semibold text-blue-600 hover:text-blue-700"
              >
                清空
              </button>
            )}
          </div>
          <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto">
            {filtered.map((person) => {
              const checked = value.includes(person.id)
              return (
                <button
                  key={person.id}
                  type="button"
                  role="option"
                  aria-selected={checked}
                  onClick={() => onChange(person.id)}
                  className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition-colors hover:bg-blue-50 ${checked ? 'bg-blue-50 text-blue-700' : 'text-slate-700'}`}
                >
                  <span className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] ${checked ? 'border-blue-600 bg-blue-600 text-white' : 'border-slate-300 bg-white text-transparent'}`}>✓</span>
                  <span className="min-w-0 truncate font-semibold">{person.name}</span>
                  <span className="ml-auto shrink-0 text-[10px] text-slate-400">{person.department || '未填写部门'}</span>
                </button>
              )
            })}
            {filtered.length === 0 && <p className="px-2.5 py-3 text-xs text-slate-400">未找到匹配人员</p>}
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}

export function OwnerSubmitWorkbench({ project, onClose, onSuccess }: Props) {
  const [people, setPeople] = useState<Person[]>([])
  const [peopleLoading, setPeopleLoading] = useState(true)
  const [peopleError, setPeopleError] = useState('')
  const [draftTasks, setDraftTasks] = useState<LocalTaskDraft[]>([cloneEmptyTask()])
  const [selectedTaskIndex, setSelectedTaskIndex] = useState(0)
  const [editingTitleIndex, setEditingTitleIndex] = useState<number | null>(null)
  const [fillLoading, setFillLoading] = useState(false)
  const [showAiPanel, setShowAiPanel] = useState(false)
  const [aiPreview, setAiPreview] = useState<OwnerSubmitMergePreview | null>(null)
  const [aiError, setAiError] = useState('')
  const [aiAuditPendingRunId, setAiAuditPendingRunId] = useState<number | null>(null)
  const [aiAuditRetrying, setAiAuditRetrying] = useState(false)
  const draftTasksRef = useRef<LocalTaskDraft[]>(draftTasks)
  const savedAiDraftRef = useRef<ProjectInitAiDraft | null>(null)
  const savedAiDecisionsRef = useRef<DraftDecision[]>([])
  const pendingAiRunIdRef = useRef<number | null>(null)
  const savedAiRunIdRef = useRef<number | null>(null)
  const submittedResultRef = useRef<(Project & { submitted_for_review: boolean }) | null>(null)

  useEffect(() => {
    draftTasksRef.current = draftTasks
  }, [draftTasks])

  useEffect(() => {
    let cancelled = false
    setPeopleLoading(true)
    fetchPeople()
      .then((rows) => {
        if (cancelled) return
        setPeople(rows.filter((person) => person.is_active !== false))
        setPeopleError('')
      })
      .catch((error: any) => {
        if (cancelled) return
        setPeopleError(error?.message || '人员列表加载失败')
      })
      .finally(() => {
        if (!cancelled) setPeopleLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  function addTaskDraft() {
    setDraftTasks((prev) => {
      const nextIndex = prev.length
      setSelectedTaskIndex(nextIndex)
      return [...prev, cloneEmptyTask()]
    })
  }

  function removeTaskDraft(index: number) {
    setDraftTasks((prev) => {
      if (prev.length <= 1) return prev
      setSelectedTaskIndex((current) => current > index ? current - 1 : Math.min(current, prev.length - 2))
      return prev.filter((_, idx) => idx !== index)
    })
  }

  function updateTaskDraft(index: number, field: keyof Omit<LocalTaskDraft, 'subtasks'>, value: string) {
    setDraftTasks((prev) => prev.map((task, idx) => (idx === index ? { ...task, [field]: value } : task)))
  }

  function addSubTaskDraft(taskIndex: number) {
    setDraftTasks((prev) =>
      prev.map((task, idx) =>
        idx === taskIndex ? { ...task, subtasks: [...task.subtasks, { ...EMPTY_SUBTASK }] } : task,
      ),
    )
  }

  function removeSubTaskDraft(taskIndex: number, subIndex: number) {
    setDraftTasks((prev) =>
      prev.map((task, idx) =>
        idx === taskIndex
          ? { ...task, subtasks: task.subtasks.length <= 1 ? task.subtasks : task.subtasks.filter((_, sidx) => sidx !== subIndex) }
          : task,
      ),
    )
  }

  function updateSubTaskDraft(taskIndex: number, subIndex: number, field: keyof LocalSubTaskDraft, value: string) {
    setDraftTasks((prev) =>
      prev.map((task, idx) =>
        idx === taskIndex
          ? {
              ...task,
              subtasks: task.subtasks.map((subtask, sidx) =>
                sidx === subIndex ? { ...subtask, [field]: value } : subtask,
              ),
            }
          : task,
      ),
    )
  }

  function updateSubTaskAssignee(taskIndex: number, subIndex: number, value: string) {
    const assigneeId = value ? Number(value) : ''
    const person = people.find((item) => item.id === assigneeId)
    setDraftTasks((prev) =>
      prev.map((task, idx) =>
        idx === taskIndex
          ? {
              ...task,
              subtasks: task.subtasks.map((subtask, sidx) =>
                sidx === subIndex
                  ? {
                      ...subtask,
                      assigneeId,
                      assignee: person?.name ?? '',
                      helperIds: subtask.helperIds.filter((id) => id !== assigneeId),
                      helper: subtask.helperIds
                        .filter((id) => id !== assigneeId)
                        .map((id) => people.find((item) => item.id === id)?.name)
                        .filter(Boolean)
                        .join('、'),
                    }
                  : subtask,
              ),
            }
          : task,
      ),
    )
  }

  function toggleSubTaskHelper(taskIndex: number, subIndex: number, personId: number) {
    setDraftTasks((prev) =>
      prev.map((task, idx) =>
        idx === taskIndex
          ? {
              ...task,
              subtasks: task.subtasks.map((subtask, sidx) => {
                if (sidx !== subIndex) return subtask
                const helperIds = subtask.helperIds.includes(personId)
                  ? subtask.helperIds.filter((id) => id !== personId)
                  : [...subtask.helperIds, personId]
                return {
                  ...subtask,
                  helperIds,
                  helper: helperIds
                    .map((id) => people.find((item) => item.id === id)?.name)
                    .filter(Boolean)
                    .join('、'),
                }
              }),
            }
          : task,
      ),
    )
  }

  function updateSubTaskPeriod(taskIndex: number, subIndex: number, value: string) {
    const parsed = parseTaskPeriod(value)
    setDraftTasks((prev) =>
      prev.map((task, idx) =>
        idx === taskIndex
          ? {
              ...task,
              subtasks: task.subtasks.map((subtask, sidx) =>
                sidx === subIndex ? { ...subtask, plan_start: parsed.start, plan_end: parsed.end } : subtask,
              ),
            }
          : task,
      ),
    )
  }

  function currentAiDraft(tasks: LocalTaskDraft[] = draftTasks): ProjectInitCurrentDraft {
    return toCurrentDraft(toPayloadDraft(tasks))
  }

  function mergeContextFor(draft: ProjectInitCurrentDraft) {
    const taskIds = new Set<number>()
    const subtaskIds = new Set<number>()
    draft.forEach((task) => {
      const taskRecord = task as typeof task & { id?: number; task_id?: number }
      for (const id of [taskRecord.id, taskRecord.task_id]) if (typeof id === 'number' && Number.isInteger(id) && id > 0) taskIds.add(id)
      for (const subtask of task.subtasks ?? []) {
        const subtaskRecord = subtask as typeof subtask & { id?: number; subtask_id?: number }
        for (const id of [subtaskRecord.id, subtaskRecord.subtask_id]) if (typeof id === 'number' && Number.isInteger(id) && id > 0) subtaskIds.add(id)
      }
    })
    return {
      knownMemberIds: people.map((person) => person.id),
      knownTaskIds: [...taskIds],
      knownSubtaskIds: [...subtaskIds],
    }
  }

  function applyMergedDraftToForm(nextDraft: ProjectInitCurrentDraft) {
    const previousTasks = draftTasksRef.current
    const existingTaskIdentities = new Set(previousTasks.map(taskStableIdentity).filter((identity): identity is string => Boolean(identity)))
    const existingContentIdentities = new Set(previousTasks.filter((task) => !taskStableIdentity(task)).map(taskContentIdentity))
    const selectedTask = previousTasks[selectedTaskIndex]
    const nextTasks = nextDraft.map((task) => {
      const taskRecord = task as ProjectWorkProgressTaskDraft & { id?: number; task_id?: number; evidence?: unknown[] }
      return {
        ...(taskRecord.id !== undefined ? { id: taskRecord.id } : {}),
        ...(taskRecord.task_id !== undefined ? { task_id: taskRecord.task_id } : {}),
        title: taskRecord.title ?? '',
        description: taskRecord.description ?? '',
        goal: taskRecord.goal ?? taskRecord.description ?? '',
        acceptance_criteria: taskRecord.acceptance_criteria ?? '',
        process: taskRecord.process ?? '',
        owner: taskRecord.owner ?? '',
        helper: taskRecord.helper ?? '',
        plan_start: taskRecord.plan_start ?? '',
        plan_end: taskRecord.plan_end ?? '',
        evidence: Array.isArray(taskRecord.evidence) ? taskRecord.evidence as LocalTaskDraft['evidence'] : [],
        subtasks: (taskRecord.subtasks ?? []).map((subtask) => ({
          ...((subtask as typeof subtask & { id?: number }).id !== undefined ? { id: (subtask as typeof subtask & { id?: number }).id } : {}),
          ...((subtask as typeof subtask & { subtask_id?: number }).subtask_id !== undefined ? { subtask_id: (subtask as typeof subtask & { subtask_id?: number }).subtask_id } : {}),
          title: subtask.title ?? '',
          evaluation_standard: subtask.evaluation_standard ?? '',
          assignee: subtask.assignee ?? '',
          assigneeId: typeof subtask.assignee_id === 'number' ? subtask.assignee_id : '',
          helper: subtask.helper ?? '',
          helperIds: Array.isArray(subtask.helper_ids) ? [...subtask.helper_ids] : [],
          plan_start: subtask.plan_start ?? '',
          plan_end: subtask.plan_end ?? '',
          evidence: Array.isArray((subtask as typeof subtask & { evidence?: unknown[] }).evidence)
            ? (subtask as typeof subtask & { evidence?: LocalSubTaskDraft['evidence'] }).evidence
            : [],
        })),
      }
    }).filter((task) => task.title.trim()) as LocalTaskDraft[]
    const normalizedTasks = nextTasks.length > 0 ? nextTasks : [cloneEmptyTask()]
    const firstNewTaskIndex = normalizedTasks.findIndex((task) => {
      const identity = taskStableIdentity(task)
      if (identity) return !existingTaskIdentities.has(identity)
      return !existingContentIdentities.has(taskContentIdentity(task))
    })
    const selectedIdentity = selectedTask ? taskStableIdentity(selectedTask) : null
    const nextSelectedIndex = selectedTask
      ? normalizedTasks.findIndex((task) => (
          selectedIdentity ? taskStableIdentity(task) === selectedIdentity : taskContentIdentity(task) === taskContentIdentity(selectedTask)
        ))
      : -1
    setSelectedTaskIndex(nextSelectedIndex >= 0 ? nextSelectedIndex : (firstNewTaskIndex >= 0 ? firstNewTaskIndex : 0))
    setDraftTasks(normalizedTasks)
  }

  function handleAiDraft(draft: ProjectInitAiDraft, decisions: ProjectInitAiDecision[], runId: number) {
    try {
      const selectedDecisions = decisions as DraftDecision[]
      const current = currentAiDraft(draftTasksRef.current)
      const preview = buildAiMergePreview(current, draft, selectedDecisions, mergeContextFor(current))
      savedAiDraftRef.current = draft
      savedAiDecisionsRef.current = selectedDecisions
      pendingAiRunIdRef.current = runId
      setAiPreview(preview)
      setAiError('')
    } catch (error: any) {
      const message = error?.message || 'AI 草稿无法安全合并，请检查人员和任务 ID'
      setAiError(message)
      throw error
    }
  }

  function confirmAiPreview() {
    if (!aiPreview || !savedAiDraftRef.current) return
    try {
      const current = currentAiDraft(draftTasksRef.current)
      const latestPreview = buildAiMergePreview(current, savedAiDraftRef.current, savedAiDecisionsRef.current, mergeContextFor(current))
      applyMergedDraftToForm(latestPreview.draft)
      savedAiRunIdRef.current = pendingAiRunIdRef.current
      pendingAiRunIdRef.current = null
      setAiPreview(null)
      savedAiDraftRef.current = null
      savedAiDecisionsRef.current = []
      setShowAiPanel(false)
      setAiError('')
      toast.success('AI 草稿已合并到当前表单，请继续检查后提交')
    } catch (error: any) {
      setAiError(error?.message || 'AI 草稿无法安全合并，请检查人员和任务 ID')
    }
  }

  function cancelAiPreview() {
    setAiPreview(null)
    savedAiDraftRef.current = null
    savedAiDecisionsRef.current = []
    pendingAiRunIdRef.current = null
  }

  async function retryAiApplyAudit() {
    const runId = aiAuditPendingRunId
    const submittedResult = submittedResultRef.current
    if (!runId || !submittedResult || aiAuditRetrying) return
    setAiAuditRetrying(true)
    try {
      await applyInitAnalysisRun(project.id, runId)
      savedAiRunIdRef.current = null
      setAiAuditPendingRunId(null)
      setAiError('')
      toast.success('AI 分析审计已补记成功')
      if (onSuccess) onSuccess(submittedResult)
      else onClose()
    } catch (error: any) {
      setAiError(`工作推进表已成功提交，但 AI 审计仍未补记成功：${error?.message || '请稍后重试'}`)
    } finally {
      setAiAuditRetrying(false)
    }
  }

  async function handleSubmit() {
    if (!project?.id) return
    if (peopleLoading) {
      toast.error('人员列表加载中，请稍候')
      return
    }
    if (peopleError) {
      toast.error(peopleError)
      return
    }
    const workProgressDraft = toSubmitDraft(currentAiDraft())
    if (workProgressDraft.length === 0) {
      toast.error('请至少新增一条重点工作')
      return
    }
    const subtaskCount = workProgressDraft.reduce((total, task) => total + (task.subtasks?.length ?? 0), 0)
    if (subtaskCount === 0) {
      toast.error('请至少添加一个关键任务')
      return
    }
    if (workProgressDraft.some((task) => task.subtasks?.some((subtask) => !subtask.assignee_id && !subtask.assignee?.trim()))) {
      toast.error('请为每个关键任务填写负责人')
      return
    }

    if (aiAuditPendingRunId) {
      toast.error('工作推进表已经提交，请先补记 AI 审计，不要重复提交')
      return
    }
    setFillLoading(true)
    try {
      const result = await ownerSubmitProfile(project.id, {
        work_progress_draft: workProgressDraft,
      })
      submittedResultRef.current = result
      const auditRunId = savedAiRunIdRef.current
      if (auditRunId) {
        try {
          await applyInitAnalysisRun(project.id, auditRunId)
          savedAiRunIdRef.current = null
          setAiAuditPendingRunId(null)
        } catch (auditError: any) {
          setAiAuditPendingRunId(auditRunId)
          const message = `工作推进表已成功提交，但 AI 审计未记录：${auditError?.message || '请点击重试补记'}`
          setAiError(message)
          toast.error(message)
          return
        }
      }
      toast.success('已提交审核，等待企业教练审核通过后正式启动')
      if (onSuccess) onSuccess(result)
      else onClose()
    } catch (e: any) {
      toast.error(e?.message || '提交失败，请重试')
    } finally {
      setFillLoading(false)
    }
  }

  function renderApprovedLayout() {
    const task = draftTasks[selectedTaskIndex] ?? draftTasks[0]
    const taskPeriod = task
      ? composeTaskPeriod(task.plan_start, task.plan_end)
        || task.subtasks.map((subtask) => composeTaskPeriod(subtask.plan_start, subtask.plan_end)).find(Boolean)
        || '待安排时间'
      : '待安排时间'
    const projectOwner = project.owners?.[0] || '未配置'
    const projectCoordinator = project.coordinator || '未配置'
    const projectCoach = project.coaches?.[0] || '未配置'
    const memberCount = project.member_counts?.member ?? project.member_counts?.members ?? 0

    return (
      <section className="owner-submit-workbench-shell flex min-h-0 w-full flex-1 flex-col overflow-hidden bg-[#f7f9fc] text-slate-900">
        <header className="owner-submit-workbench-header flex min-h-[88px] shrink-0 items-center justify-between border-b border-slate-200 bg-white px-8 py-4">
          <div className="min-w-0">
            <div className="flex min-w-0 flex-wrap items-center gap-2.5">
              <h2 className="truncate text-2xl font-bold tracking-[-0.02em] text-slate-900">填写项目方案 — {project.name}</h2>
              <span className="rounded-full border border-orange-200 bg-orange-50 px-2.5 py-1 text-[11px] font-bold text-orange-700">待负责人完善</span>
            </div>
            <p className="mt-1 text-xs text-slate-500">完善项目计划内容，确认后提交企业教练审核</p>
          </div>
          <button type="button" onClick={onClose} disabled={fillLoading} className="ml-4 inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-800 disabled:opacity-50" aria-label="返回项目详情">
            <svg aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" /></svg>
            返回项目详情
          </button>
        </header>

        <main className="owner-submit-workbench-main min-h-0 flex-1 overflow-x-hidden overflow-y-auto bg-slate-50 pb-[88px]" data-testid="owner-submit-workbench-main">
          <div className="owner-submit-workbench-columns flex w-full flex-col gap-6 px-8 py-6 lg:flex-row">
            <aside className="owner-submit-left-pane self-start lg:sticky lg:top-4 lg:w-[360px] lg:shrink-0">
              <section className="owner-submit-project-summary owner-submit-project-summary-display owner-submit-core-card rounded-2xl border border-slate-200 bg-white px-5 py-4 sm:px-6" data-layout="compact" data-testid="owner-submit-project-summary">
                <h3 className="text-xl font-bold text-slate-900">项目概览</h3>
                <div className="mt-4 space-y-1">
                  <div className="owner-submit-project-info-row grid grid-cols-[130px_minmax(0,1fr)] items-start gap-3 py-1.5 text-sm"><span className="pt-0.5 text-slate-400">项目编号</span><p className="min-w-0 font-semibold text-slate-800">{project.code || '未填写'}</p></div>
                  <div className="owner-submit-project-info-row grid grid-cols-[130px_minmax(0,1fr)] items-start gap-3 py-1.5 text-sm"><span className="pt-0.5 text-slate-400">项目名称</span><p className="min-w-0 font-semibold text-slate-900">{project.name}</p></div>
                  <div className="owner-submit-project-info-row grid grid-cols-[130px_minmax(0,1fr)] items-start gap-3 py-1.5 text-sm"><span className="pt-0.5 text-slate-400">项目状态</span><div className="flex min-w-0 items-center gap-2 font-semibold text-slate-700"><span className="h-2 w-2 shrink-0 rounded-full bg-orange-500" />待负责人完善</div></div>
                  <div className="owner-submit-project-info-row grid grid-cols-[130px_minmax(0,1fr)] items-start gap-3 py-1.5 text-sm"><span className="pt-0.5 text-slate-400">项目周期</span><div className="flex min-w-0 items-center gap-2 font-semibold text-slate-700"><svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 shrink-0 text-slate-400" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></svg>{composeProjectPeriod(project.start_date, project.end_date) || '未设置'}</div></div>
                  <div className="owner-submit-project-info-row grid grid-cols-[130px_minmax(0,1fr)] items-start gap-3 py-1.5 text-sm"><span className="pt-0.5 text-slate-400">项目目标</span><p className="min-w-0 whitespace-pre-wrap leading-5 text-slate-600">{project.objectives?.trim() || '未填写'}</p></div>
                  <div className="owner-submit-project-info-row grid grid-cols-[130px_minmax(0,1fr)] items-start gap-3 py-1.5 text-sm"><span className="pt-0.5 text-slate-400">项目背景</span><p className="min-w-0 whitespace-pre-wrap leading-5 text-slate-600">{project.background?.trim() || '未填写'}</p></div>
                  <div className="owner-submit-project-info-row grid grid-cols-[130px_minmax(0,1fr)] items-start gap-3 py-1.5 text-sm"><span className="pt-0.5 text-slate-400">补充说明</span><p className="min-w-0 whitespace-pre-wrap leading-5 text-slate-600">{project.expected_outcomes?.trim() || '未填写'}</p></div>
                  <div className="owner-submit-project-info-row grid grid-cols-[130px_minmax(0,1fr)] items-start gap-3 py-1.5 text-sm"><span className="pt-0.5 text-slate-400">项目说明</span><p className="min-w-0 whitespace-pre-wrap leading-5 text-slate-600">{project.description?.trim() || '未填写'}</p></div>
                </div>
                <div className="mt-3 border-t border-slate-100 pt-3">
                  <span className="block text-sm font-bold text-slate-700">项目角色</span>
                  <div className="mt-2 space-y-1">
                    {[['负责人', projectOwner], ['统筹人', projectCoordinator], ['企业教练', projectCoach], ['成员', `${memberCount} 人`]].map(([label, value]) => <div key={label} className="owner-submit-project-role-row grid min-h-10 grid-cols-[130px_minmax(0,1fr)] items-center gap-3 rounded-lg px-0 py-1.5 text-sm transition-colors hover:bg-slate-50"><span className="text-slate-500">{label}</span><span className="min-w-0 text-slate-700">{value}</span></div>)}
                  </div>
                </div>
              </section>
            </aside>

            <section className="owner-submit-plan-section owner-submit-right-pane min-w-0 flex-1">
              <div className="owner-submit-workplan-heading mb-4 flex flex-wrap items-center justify-between gap-3">
                <h3 className="text-xl font-bold text-slate-900">工作推进方案</h3>
                <div className="flex shrink-0 flex-wrap gap-2"><button type="button" onClick={() => { setShowAiPanel((current) => !current); setAiError('') }} disabled={fillLoading} className="flex h-9 items-center gap-1.5 rounded-lg border border-violet-200 bg-violet-50 px-3.5 text-xs font-bold text-violet-700 transition-colors hover:border-violet-300 hover:bg-violet-100 disabled:opacity-50">{showAiPanel ? '收起 AI 草稿' : 'AI 分析文件 / AI 草稿'}</button><button type="button" onClick={addTaskDraft} className="owner-submit-primary-add flex h-9 items-center gap-1.5 rounded-lg border border-blue-200 bg-white px-3.5 text-xs font-bold text-blue-700 transition-colors hover:border-blue-300 hover:bg-blue-50">+ 新增重点工作</button></div>
              </div>
              {showAiPanel && <div className="mb-4" data-testid="owner-submit-ai-panel"><OwnerSubmitAiPanel projectId={project.id} currentDraft={currentAiDraft()} onApplyDraft={handleAiDraft} onClose={() => setShowAiPanel(false)} disabled={fillLoading} /></div>}
              {aiError && <div role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700"><p>{aiError}</p>{aiAuditPendingRunId && <button type="button" onClick={() => void retryAiApplyAudit()} disabled={aiAuditRetrying} className="mt-2 rounded-lg border border-red-300 bg-white px-3 py-1.5 font-semibold text-red-700 hover:bg-red-100 disabled:opacity-50">{aiAuditRetrying ? '正在补记审计…' : '重试补记 AI 审计'}</button>}</div>}
              {aiPreview && <section className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 p-4" aria-label="AI 草稿合并预览" data-testid="owner-submit-ai-preview"><div className="flex flex-wrap items-start justify-between gap-3"><div><h4 className="text-sm font-bold text-emerald-900">请确认 AI 草稿合并</h4><p className="mt-1 text-xs text-emerald-800">将新增 {aiPreview.addedTaskCount} 项重点工作，检测到 {aiPreview.changeCount} 项字段或结构变化；现有非空内容不会被覆盖。</p></div><div className="flex gap-2"><button type="button" onClick={cancelAiPreview} className="rounded-lg border border-emerald-300 bg-white px-3 py-2 text-xs font-bold text-emerald-800 hover:bg-emerald-100">取消</button><button type="button" onClick={confirmAiPreview} className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-700">确认合并到表单</button></div></div>{aiPreview.warnings.length > 0 && <div role="alert" className="mt-3 space-y-1 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"><p className="font-semibold">仍有 {aiPreview.warningCount} 条待确认提示：</p>{aiPreview.warnings.slice(0, 8).map((warning) => <p key={warning}>{warning}</p>)}</div>}</section>}

              {task && <div className="owner-submit-b-split h-auto min-h-0 overflow-hidden rounded-2xl border border-slate-200 bg-white" data-testid="owner-submit-b-split"><div className="flex h-auto min-h-0 flex-col lg:flex-row">
                <nav className="w-full shrink-0 border-b border-slate-200 bg-white p-3 lg:w-[228px] lg:border-b-0 lg:border-r" aria-label="重点工作列表"><div className="space-y-1">{draftTasks.map((item, index) => <button key={index} type="button" onClick={() => { setSelectedTaskIndex(index); setEditingTitleIndex(null) }} aria-current={index === selectedTaskIndex ? 'true' : undefined} className={`flex w-full items-start rounded-xl px-3 py-3 text-left transition-colors ${index === selectedTaskIndex ? 'bg-blue-50 text-blue-700' : 'text-slate-700 hover:bg-slate-50'}`}><span className="min-w-0 truncate text-sm font-semibold">{item.title.trim() || '未命名重点工作'}</span></button>)}</div></nav>
                <div className="min-w-0 flex-1 p-6 sm:p-8">
                  <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-4"><div className="flex min-w-0 flex-1 items-center gap-3"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-sm font-bold text-blue-700">{String(selectedTaskIndex + 1).padStart(2, '0')}</div><div className="min-w-0 flex-1">{editingTitleIndex === selectedTaskIndex ? <><label className="sr-only">重点工作名称</label><input autoFocus value={task.title} onChange={(e) => updateTaskDraft(selectedTaskIndex, 'title', e.target.value)} onBlur={() => setEditingTitleIndex(null)} onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur() }} placeholder="请输入重点工作名称" className="h-8 w-full min-w-0 border-0 bg-transparent px-0 text-xl font-bold text-slate-900 outline-none placeholder:text-slate-400 focus:ring-0" /></> : <button type="button" onClick={() => setEditingTitleIndex(selectedTaskIndex)} className={`owner-submit-title-display w-full rounded-lg px-0 text-left text-xl font-semibold ${task.title.trim() ? 'owner-submit-title-filled' : 'owner-submit-title-empty'}`} aria-label="编辑重点工作名称">{task.title.trim() || '未命名重点工作'}</button>}</div></div><details className="relative shrink-0"><summary aria-label={`重点工作 ${selectedTaskIndex + 1} 更多操作`} className="owner-submit-more-menu-trigger flex h-8 w-8 cursor-pointer list-none items-center justify-center rounded-lg text-lg hover:bg-slate-100">···</summary><div className="absolute right-0 top-9 z-20 w-32 rounded-lg border border-slate-200 bg-white p-1 shadow-lg"><button type="button" onClick={() => removeTaskDraft(selectedTaskIndex)} disabled={draftTasks.length <= 1} className="w-full rounded-md px-2.5 py-2 text-left text-xs text-slate-500 hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-30">删除重点工作</button></div></details></div>
                  <div className="owner-submit-goal-result mt-5 space-y-3" data-layout="stacked" data-testid="owner-submit-goal-result">
                    <div><label className="block text-sm font-bold text-slate-700">目标</label><input value={task.goal || task.description} onChange={(e) => updateTaskDraft(selectedTaskIndex, 'goal', e.target.value)} placeholder="请输入目标成果" className="owner-submit-goal-result-input mt-2 h-10 w-full border-0 bg-transparent px-0 py-0 text-lg leading-8 text-slate-700 outline-none placeholder:text-slate-400 focus:ring-0" /></div>
                    <div><label className="block text-sm font-bold text-slate-700">验收标准 / 关键成果</label><textarea value={task.acceptance_criteria} onChange={(e) => updateTaskDraft(selectedTaskIndex, 'acceptance_criteria', e.target.value)} placeholder="请输入验收标准或关键成果" rows={3} className="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-700 outline-none placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:ring-2 focus:ring-blue-100" /></div>
                    <div><label className="block text-sm font-bold text-slate-700">推进流程</label><textarea value={task.process} onChange={(e) => updateTaskDraft(selectedTaskIndex, 'process', e.target.value)} placeholder="请输入推进流程，例如：准备 → 执行 → 复盘" rows={2} className="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-700 outline-none placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:ring-2 focus:ring-blue-100" /></div>
                  </div>
                  <div className="mt-3 inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600"><svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></svg>计划时间：{taskPeriod}</div>
                  <div className="mt-6 flex items-center justify-between gap-3"><h4 className="text-base font-bold text-slate-800">关键任务</h4><button type="button" onClick={() => addSubTaskDraft(selectedTaskIndex)} className="text-xs font-bold text-blue-600 hover:text-blue-800 hover:underline">+ 新增关键任务</button></div>
                  <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200 lg:overflow-x-hidden"><table className="owner-submit-subtask-table table-fixed min-w-[680px] w-full lg:min-w-0 border-separate border-spacing-0 text-left text-sm"><thead><tr className="border-b border-slate-200 bg-slate-50 text-[11px] font-bold tracking-wide text-slate-500"><th className="w-[27%] py-2.5 pl-3 pr-2">关键任务</th><th className="w-[14%] px-2 py-2.5">负责人</th><th className="w-[16%] px-2 py-2.5">协助人</th><th className="w-[15%] px-2 py-2.5">时间段</th><th className="w-[23%] px-2 py-2.5">评价指标</th><th className="w-[5%] px-2 py-2.5">操作</th></tr></thead><tbody className="divide-y divide-slate-100">{task.subtasks.map((subtask, subIndex) => <tr key={subIndex} className="group hover:bg-blue-50/40"><td className="py-1.5 pl-3 pr-2"><div className="flex items-center gap-2"><span className="owner-submit-subtask-drag-handle shrink-0" aria-hidden="true"><svg viewBox="0 0 16 16" className="h-4 w-4" fill="currentColor"><circle cx="5" cy="3" r="1"/><circle cx="11" cy="3" r="1"/><circle cx="5" cy="8" r="1"/><circle cx="11" cy="8" r="1"/><circle cx="5" cy="13" r="1"/><circle cx="11" cy="13" r="1"/></svg></span><input value={subtask.title} onChange={(e) => updateSubTaskDraft(selectedTaskIndex, subIndex, 'title', e.target.value)} placeholder="例如：任务名称" className="h-9 min-w-0 flex-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 text-sm text-slate-800 placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100" /></div></td><td className="px-2 py-1.5 align-top"><AssigneePicker people={people} value={subtask.assigneeId} rawName={subtask.assignee} disabled={peopleLoading || Boolean(peopleError)} onChange={(value) => updateSubTaskAssignee(selectedTaskIndex, subIndex, value)} /></td><td className="px-2 py-1.5 align-top"><HelperPicker people={people} value={subtask.helperIds} excludedId={subtask.assigneeId} rawName={subtask.helper} disabled={peopleLoading || Boolean(peopleError)} onChange={(personId) => toggleSubTaskHelper(selectedTaskIndex, subIndex, personId)} /></td><td className="px-2 py-1.5"><div className="relative"><svg aria-hidden="true" viewBox="0 0 24 24" className="owner-submit-date-icon pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></svg><input value={composeTaskPeriod(subtask.plan_start, subtask.plan_end)} onChange={(e) => updateSubTaskPeriod(selectedTaskIndex, subIndex, e.target.value)} placeholder="7.1 - 7.5" className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 py-0 pl-8 pr-2.5 text-sm text-slate-700 placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100" /></div></td><td className="px-2 py-1.5"><input value={subtask.evaluation_standard} onChange={(e) => updateSubTaskDraft(selectedTaskIndex, subIndex, 'evaluation_standard', e.target.value)} placeholder="填写评价指标" className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 px-2.5 text-sm text-slate-700 placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100" /></td><td className="px-2 py-1.5 text-right"><button type="button" aria-label="删除关键任务" onClick={() => removeSubTaskDraft(selectedTaskIndex, subIndex)} disabled={task.subtasks.length <= 1} className="owner-submit-subtask-delete-icon inline-flex h-8 w-8 items-center justify-center rounded-lg hover:bg-red-50 disabled:cursor-not-allowed"><svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 7h16M10 11v6M14 11v6M9 7V4h6v3M6 7l1 13h10l1-13" /></svg></button></td></tr>)}</tbody></table></div>
                </div>
              </div></div>}
            </section>
          </div>
        </main>

        <footer className="owner-submit-workbench-footer sticky bottom-0 z-10 flex min-h-[72px] shrink-0 items-center justify-between border-t border-slate-200 bg-white/95 px-8 py-3 shadow-[0_-8px_20px_rgba(15,23,42,0.06)] backdrop-blur"><button type="button" onClick={onClose} disabled={fillLoading} className="h-10 rounded-xl border border-slate-200 bg-white px-5 text-sm font-bold text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50 disabled:opacity-50">取消</button><button type="button" onClick={handleSubmit} disabled={fillLoading} className="h-10 rounded-xl bg-orange-600 px-8 text-sm font-bold text-white shadow-[0_6px_16px_rgba(234,88,12,0.22)] transition-colors hover:bg-orange-700 disabled:opacity-50">{fillLoading ? '提交中…' : '提交立项审核'}</button></footer>
      </section>
    )
  }

  return renderApprovedLayout()

  /*
  return (
      <section className="owner-submit-workbench-shell flex min-h-0 w-full flex-1 flex-col overflow-hidden bg-[#f7f9fc] text-slate-900">
        <header className="owner-submit-workbench-header flex min-h-[64px] shrink-0 items-center justify-between border-b border-slate-200 bg-white px-5 py-3 sm:px-7">
          <div className="min-w-0">
            <div className="flex min-w-0 flex-wrap items-center gap-2.5">
              <h2 className="truncate text-xl font-bold tracking-[-0.02em] text-slate-900">
                填写项目方案 — {project.name}
              </h2>
              <span className="rounded-full border border-orange-200 bg-orange-50 px-2.5 py-1 text-[11px] font-bold text-orange-700">
                待负责人完善
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-500">完善项目计划内容，确认后提交企业教练审核</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={fillLoading}
            className="ml-4 inline-flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50"
            aria-label="返回项目详情"
          >
            <svg aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
            </svg>
            返回项目详情
          </button>
        </header>

        <main className="owner-submit-workbench-main min-h-0 flex-1 overflow-x-hidden overflow-y-auto bg-slate-50">
          <div className="owner-submit-workbench-columns flex w-full flex-col gap-5 px-4 py-5 sm:px-6 lg:flex-row lg:px-8">
            <aside className="owner-submit-left-pane sticky top-4 self-start lg:w-[280px] xl:w-[300px]">
            <section className="owner-submit-project-summary owner-submit-project-summary-display owner-submit-core-card space-y-5 rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-[0_8px_24px_rgba(15,23,42,0.05)] sm:px-6">
              <h3 className="mb-1.5 text-sm font-bold text-slate-800">项目核心信息</h3>
              <p className="text-xs text-slate-500">基础信息由管理层维护</p>
              <div className="grid grid-cols-1 gap-3">
                <div className="min-w-0">
                  <span className="block text-[10px] font-bold uppercase tracking-[0.08em] text-slate-400">项目名称</span>
                  <p className="mt-2 truncate text-xl font-bold tracking-[-0.01em] text-slate-900">{project.name}</p>
                </div>
                <div className="owner-submit-project-period-display min-w-0">
                  <span className="block text-[10px] font-bold uppercase tracking-[0.08em] text-slate-400">项目周期 / 时间段</span>
                  <div className="relative mt-2 flex min-h-10 items-center rounded-lg border border-slate-200 bg-slate-50 px-3 pl-9 text-sm font-semibold text-slate-800">
                    <svg aria-hidden="true" viewBox="0 0 24 24" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" strokeWidth="1.8">
                      <rect x="3" y="5" width="18" height="16" rx="2" />
                      <path d="M16 3v4M8 3v4M3 10h18" />
                    </svg>
                    <span>{composeProjectPeriod(project.start_date, project.end_date) || '未设置'}</span>
                  </div>
                </div>
                <div className="min-w-0">
                  <span className="block text-[10px] font-bold uppercase tracking-[0.08em] text-slate-400">项目完成准则 / 验收标准</span>
                  <div className="owner-submit-objectives-content mt-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
                    <span className="block text-[10px] font-bold uppercase tracking-[0.08em] text-slate-400">内容</span>
                    {project.objectives?.trim() ? (
                      <p className="mt-1 whitespace-pre-wrap text-sm leading-5 text-slate-800">{project.objectives.trim()}</p>
                    ) : (
                      <span className="mt-2 inline-flex rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs font-medium text-slate-400">未填写</span>
                    )}
                  </div>
                </div>
              </div>

              <details className="app-disclosure group mt-1">
                <summary className="ml-auto flex w-fit cursor-pointer select-none items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-blue-600 transition-colors hover:border-blue-200 hover:bg-blue-50">
                  补充详细信息
                    </summary>
                <div className="mt-3 grid grid-cols-1 gap-4 border-t border-slate-200 pt-4 md:grid-cols-2">
                      <div className="space-y-1.5">
                        <span className="block text-[11px] font-semibold text-slate-500">客户名称</span>
                        <p className="text-sm text-slate-700">{project.client_name?.trim() || '未填写'}</p>
                      </div>
                      <div className="space-y-1.5">
                        <span className="block text-[11px] font-semibold text-slate-500">项目类型</span>
                        <p className="text-sm text-slate-700">{project.project_type?.trim() || '未填写'}</p>
                      </div>
                      <div className="space-y-1.5">
                        <span className="block text-[11px] font-semibold text-slate-500">项目背景</span>
                        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{project.background?.trim() || '未填写'}</p>
                      </div>
                      <div className="space-y-1.5">
                        <span className="block text-[11px] font-semibold text-slate-500">补充说明</span>
                        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{project.expected_outcomes?.trim() || '未填写'}</p>
                      </div>
                      <div className="space-y-1.5 md:col-span-2">
                        <span className="block text-[11px] font-semibold text-slate-500">项目说明</span>
                        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{project.description?.trim() || '未填写'}</p>
                      </div>
                </div>
              </details>
            </section>
            </aside>

            <section className="owner-submit-plan-section owner-submit-right-pane flex-1 min-w-0">
              <div className="owner-submit-workplan-heading mb-4 flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex min-w-0 flex-wrap items-center gap-3">
                    <h3 className="shrink-0 text-xl font-semibold text-slate-900">工作推进方案</h3>
                    <span className="mt-1 block max-w-3xl text-xs leading-5 text-slate-500">重点工作用于归类工作方向；关键任务才需要明确责任人、协助人、时间段和备注标准。</span>
                  </div>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => { setShowAiPanel((current) => !current); setAiError('') }}
                    disabled={fillLoading}
                    className="flex h-9 items-center gap-1.5 rounded-lg border border-violet-200 bg-violet-50 px-3.5 text-xs font-bold text-violet-700 transition-colors hover:border-violet-300 hover:bg-violet-100 disabled:opacity-50"
                  >
                    {showAiPanel ? '收起 AI 草稿' : 'AI 分析文件 / AI 草稿'}
                  </button>
                  <button
                    type="button"
                    onClick={addTaskDraft}
                    className="owner-submit-primary-add flex h-9 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3.5 text-xs font-bold text-blue-700 transition-colors hover:border-blue-300 hover:bg-blue-50"
                  >
                    + 新增重点工作
                  </button>
                </div>
              </div>

              {showAiPanel && (
                <div className="mb-4" data-testid="owner-submit-ai-panel">
                  <OwnerSubmitAiPanel
                    projectId={project.id}
                    currentDraft={currentAiDraft()}
                    onApplyDraft={handleAiDraft}
                    onClose={() => setShowAiPanel(false)}
                    disabled={fillLoading}
                  />
                </div>
              )}

              {aiError && <div role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700">
                <p>{aiError}</p>
                {aiAuditPendingRunId && <button type="button" onClick={() => void retryAiApplyAudit()} disabled={aiAuditRetrying} className="mt-2 rounded-lg border border-red-300 bg-white px-3 py-1.5 font-semibold text-red-700 hover:bg-red-100 disabled:opacity-50">
                  {aiAuditRetrying ? '正在补记审计…' : '重试补记 AI 审计'}
                </button>}
              </div>}

              {aiPreview && (
                <section className="mb-4 rounded-2xl border border-amber-200 bg-amber-50 p-4" aria-label="AI 草稿合并预览" data-testid="owner-submit-ai-preview">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h4 className="text-sm font-bold text-emerald-900">请确认 AI 草稿合并</h4>
                      <p className="mt-1 text-xs text-emerald-800">将新增 {aiPreview.addedTaskCount} 项重点工作，检测到 {aiPreview.changeCount} 项字段或结构变化；现有非空内容不会被覆盖。</p>
                    </div>
                    <div className="flex gap-2">
                      <button type="button" onClick={cancelAiPreview} className="rounded-lg border border-emerald-300 bg-white px-3 py-2 text-xs font-bold text-emerald-800 hover:bg-emerald-100">取消</button>
                      <button type="button" onClick={confirmAiPreview} className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-700">确认合并到表单</button>
                    </div>
                  </div>
                  {aiPreview.warnings.length > 0 && <div role="alert" className="mt-3 space-y-1 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"><p className="font-semibold">仍有 {aiPreview.warningCount} 条待确认提示：</p>{aiPreview.warnings.slice(0, 8).map((warning) => <p key={warning}>{warning}</p>)}</div>}
                </section>
              )}

                  <div className="space-y-3">
                    {draftTasks.map((task, taskIndex) => {
                      const isExpanded = expandedTaskIndexes.has(taskIndex)
                      const taskPeriod = composeTaskPeriod(task.plan_start, task.plan_end)
                        || task.subtasks.map((subtask) => composeTaskPeriod(subtask.plan_start, subtask.plan_end)).find(Boolean)
                        || '待安排时间'
                      return (
                    <div key={taskIndex} className="owner-submit-task-group overflow-hidden rounded-2xl border border-slate-200 bg-white">
                      {isExpanded ? (
                        <>
                              <div className="owner-submit-task-group-header flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-slate-200 bg-slate-50 px-4 py-3">
                            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-blue-50 text-xs font-bold text-blue-700">
                              {String(taskIndex + 1).padStart(2, '0')}
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex min-w-0 flex-wrap items-center gap-2">
                                <label className="sr-only">重点工作名称</label>
                                <input
                                  value={task.title}
                                  onChange={(e) => updateTaskDraft(taskIndex, 'title', e.target.value)}
                                  placeholder="请输入重点工作"
                                  className="h-8 min-w-[180px] flex-1 border-0 bg-transparent px-0 text-base font-bold text-slate-900 outline-none placeholder:text-slate-400 focus:ring-0 sm:max-w-[360px] sm:flex-none"
                                />
                                <span className="owner-submit-task-status rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-600">方案编辑中</span>
                              </div>
                              <div className="flex min-w-0 items-center gap-2">
                                <label className="sr-only">目标成果 / 验收标准</label>
                                <input
                                  value={task.goal || task.description}
                                  onChange={(e) => updateTaskDraft(taskIndex, 'goal', e.target.value)}
                                  placeholder="请输入完成准则"
                                  className="h-6 w-full border-0 bg-transparent px-0 text-xs text-slate-500 outline-none placeholder:text-slate-400 focus:ring-0"
                                />
                              </div>
                            </div>
                            <div className="owner-submit-task-meta flex shrink-0 items-center gap-2 text-xs font-semibold text-slate-500">
                              <span className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3">
                                <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M8 12h8M12 8v8" /><path d="M7 3H5a2 2 0 0 0-2 2v4M17 3h2a2 2 0 0 1 2 2v4M7 21H5a2 2 0 0 1-2-2v-4M17 21h2a2 2 0 0 0 2-2v-4" /></svg>
                                {task.subtasks.length} 个关键任务
                              </span>
                              <span className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3">
                                <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></svg>
                                {taskPeriod}
                              </span>
                            </div>
                            <button type="button" onClick={() => collapseTask(taskIndex)} className="h-9 shrink-0 rounded-lg px-2.5 text-xs font-semibold text-slate-500 hover:bg-slate-100 hover:text-slate-700">收起</button>
                            <details className="relative shrink-0" onClick={(event) => event.stopPropagation()}>
                              <summary aria-label={`重点工作 ${taskIndex + 1} 更多操作`} className="flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded-lg text-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600">···</summary>
                              <div className="absolute right-0 top-10 z-20 w-32 rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
                                <button type="button" onClick={() => removeTaskDraft(taskIndex)} disabled={draftTasks.length <= 1} className="w-full rounded-md px-2.5 py-2 text-left text-xs text-slate-500 hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-30">删除重点工作</button>
                              </div>
                            </details>
                          </div>

                          <div className="overflow-x-auto">
                            <table className="owner-submit-subtask-table table-fixed min-w-[980px] w-full border-none bg-transparent p-0 border-separate border-spacing-0 text-left text-sm">
                              <thead>
                                <tr className="border-b border-slate-200 bg-white text-[11px] font-bold tracking-wide text-slate-500">
                                  <th className="w-[26%] py-2 pl-4 pr-2">关键任务</th>
                                  <th className="w-[14%] px-2 py-2">负责人</th>
                                  <th className="w-[16%] px-2 py-2">协助人</th>
                                  <th className="w-[15%] px-2 py-2">时间段</th>
                                  <th className="w-[24%] px-2 py-2">备注 / 标准</th>
                                  <th className="w-[5%] px-2 py-2">操作</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-100">
                                    {task.subtasks.map((subtask, subIndex) => (
                                      <tr key={subIndex} className="group hover:bg-blue-50/40">
                                        <td className="py-1.5 pl-4 pr-2">
                                          <div className="flex items-center gap-2">
                                            <span className="owner-submit-subtask-drag-handle shrink-0 text-slate-400" aria-hidden="true">
                                              <svg viewBox="0 0 16 16" className="h-4 w-4" fill="currentColor"><circle cx="5" cy="3" r="1"/><circle cx="11" cy="3" r="1"/><circle cx="5" cy="8" r="1"/><circle cx="11" cy="8" r="1"/><circle cx="5" cy="13" r="1"/><circle cx="11" cy="13" r="1"/></svg>
                                            </span>
                                            <input value={subtask.title} onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'title', e.target.value)} placeholder="例如：任务名称" className="h-9 min-w-0 flex-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 text-sm text-slate-800 placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100" />
                                          </div>
                                        </td>
                                        <td className="px-2 py-1.5 align-top"><AssigneePicker people={people} value={subtask.assigneeId} rawName={subtask.assignee} disabled={peopleLoading || Boolean(peopleError)} onChange={(value) => updateSubTaskAssignee(taskIndex, subIndex, value)} /></td>
                                        <td className="px-2 py-1.5 align-top"><HelperPicker people={people} value={subtask.helperIds} excludedId={subtask.assigneeId} rawName={subtask.helper} disabled={peopleLoading || Boolean(peopleError)} onChange={(personId) => toggleSubTaskHelper(taskIndex, subIndex, personId)} /></td>
                                        <td className="px-2 py-1.5">
                                          <div className="relative">
                                            <svg aria-hidden="true" viewBox="0 0 24 24" className="owner-submit-subtask-date-icon pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></svg>
                                            <input value={composeTaskPeriod(subtask.plan_start, subtask.plan_end)} onChange={(e) => updateSubTaskPeriod(taskIndex, subIndex, e.target.value)} placeholder="7.1 - 7.5" className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 py-0 pl-8 pr-2.5 text-sm text-slate-700 placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100" />
                                          </div>
                                        </td>
                                    <td className="px-2 py-1.5">
                                      <input value={subtask.evaluation_standard} onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'evaluation_standard', e.target.value)} placeholder="填写验收标准或说明" className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 px-2.5 text-sm text-slate-700 placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100" />
                                    </td>
                                    <td className="px-2 py-1.5 text-right">
                                          <button type="button" aria-label="删除关键任务" onClick={() => removeSubTaskDraft(taskIndex, subIndex)} disabled={task.subtasks.length <= 1} className="owner-submit-subtask-delete-icon inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 opacity-70 hover:bg-red-50 hover:text-red-500 hover:opacity-100 group-hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-20">
                                            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 7h16M10 11v6M14 11v6M9 7V4h6v3M6 7l1 13h10l1-13" /></svg>
                                          </button>
                                        </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          <div className="border-t border-slate-100 px-4 py-2">
                            <button type="button" onClick={() => addSubTaskDraft(taskIndex)} className="text-xs font-bold text-blue-600 hover:text-blue-800 hover:underline">+ 新增关键任务</button>
                          </div>
                        </>
                      ) : (
                            <div role="button" tabIndex={0} onClick={() => expandTask(taskIndex)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') expandTask(taskIndex) }} className="flex cursor-pointer items-center gap-3 px-4 py-3 hover:bg-slate-50">
                              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-blue-50 text-xs font-bold text-blue-700">{String(taskIndex + 1).padStart(2, '0')}</div>
                              <div className="min-w-0 flex-1 md:grid md:grid-cols-[42fr_43fr] md:gap-3">
                                <p className="truncate text-sm font-semibold text-slate-800">{task.title.trim() || '未命名重点工作'}</p>
                                <p className="truncate text-xs text-slate-500"><span className="text-slate-400">目标成果：</span>{(task.goal || task.description).trim() || '未填写目标成果'}</p>
                              </div>
                              <div className="owner-submit-task-meta hidden shrink-0 items-center gap-2 text-xs font-semibold text-slate-500 md:flex">
                                <span className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5">
                                  <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M8 12h8M12 8v8" /><path d="M7 3H5a2 2 0 0 0-2 2v4M17 3h2a2 2 0 0 1 2 2v4M7 21H5a2 2 0 0 1-2-2v-4M17 21h2a2 2 0 0 0 2-2v-4" /></svg>
                                  {task.subtasks.length} 个关键任务
                                </span>
                                <span className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5">
                                  <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></svg>
                                  {taskPeriod}
                                </span>
                              </div>
                              <span className="shrink-0 text-xs text-slate-500 md:hidden">{task.subtasks.length} 个关键任务</span>
                              <button type="button" onClick={(event) => { event.stopPropagation(); expandTask(taskIndex) }} className="h-8 shrink-0 rounded-lg px-2.5 text-xs font-semibold text-blue-600 hover:bg-blue-50">展开</button>
                          <details className="relative shrink-0" onClick={(event) => event.stopPropagation()}>
                            <summary aria-label={`重点工作 ${taskIndex + 1} 更多操作`} className="flex h-8 w-8 cursor-pointer list-none items-center justify-center rounded-lg text-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600">···</summary>
                            <div className="absolute right-0 top-9 z-20 w-32 rounded-lg border border-slate-200 bg-white p-1 shadow-lg">
                              <button type="button" onClick={() => removeTaskDraft(taskIndex)} disabled={draftTasks.length <= 1} className="w-full rounded-md px-2.5 py-2 text-left text-xs text-slate-500 hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-30">删除重点工作</button>
                            </div>
                          </details>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              <div className="mt-3">
                <button type="button" onClick={addTaskDraft} className="owner-submit-continue-add w-full h-10 rounded-lg border border-dashed border-slate-300 bg-white text-xs font-semibold text-blue-600 transition-colors hover:border-blue-300 hover:bg-blue-50">＋ 继续新增重点工作</button>
              </div>
            </section>
          </div>
        </main>

        <footer className="owner-submit-workbench-footer sticky bottom-0 z-10 flex min-h-[64px] shrink-0 items-center justify-between border-t border-slate-200 bg-white/95 px-5 py-3 shadow-[0_-8px_20px_rgba(15,23,42,0.06)] backdrop-blur lg:px-7">
          <button
            type="button"
            onClick={onClose}
            disabled={fillLoading}
            className="h-10 rounded-xl border border-slate-200 bg-white px-5 text-sm font-bold text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50 disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={fillLoading}
            className="h-10 rounded-xl bg-orange-600 px-8 text-sm font-bold text-white shadow-[0_6px_16px_rgba(234,88,12,0.22)] transition-colors hover:bg-orange-700 disabled:opacity-50"
          >
            {fillLoading ? '提交中…' : '提交立项审核'}
          </button>
        </footer>
      </section>
  )
  */
}
