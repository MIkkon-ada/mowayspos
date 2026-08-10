import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ownerSubmitProfile } from '../../api/projects'
import { fetchPeople } from '../../api/people'
import type { ProjectProfilePayload, ProjectWorkProgressTaskDraft } from '../../api/projects'
import { toast } from '../../utils/toast'
import type { Person, Project } from '../../types'

type Props = {
  project: Project
  onClose: () => void
  onSuccess?: (result: Project & { submitted_for_review: boolean }) => void
}

type LocalSubTaskDraft = {
  title: string
  evaluation_standard: string
  assignee: string
  assigneeId: number | ''
  helper: string
  helperIds: number[]
  plan_start: string
  plan_end: string
}

type LocalTaskDraft = {
  title: string
  description: string
  owner: string
  helper: string
  plan_start: string
  plan_end: string
  subtasks: LocalSubTaskDraft[]
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
  owner: '',
  helper: '',
  plan_start: '',
  plan_end: '',
  subtasks: [{ ...EMPTY_SUBTASK }],
}

function cloneEmptyTask(): LocalTaskDraft {
  return { ...EMPTY_TASK, subtasks: [{ ...EMPTY_SUBTASK }] }
}

function composeProjectPeriod(startDate?: string, endDate?: string): string {
  const start = (startDate ?? '').trim()
  const end = (endDate ?? '').trim()
  if (start && end) return `${start} 至 ${end}`
  return start || end
}

function parseProjectPeriod(value: string): ParsedPeriod {
  return parsePeriodValue(value)
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
      title: task.title.trim(),
      description: task.description.trim(),
      owner: task.owner.trim(),
      helper: task.helper.trim(),
      plan_start: task.plan_start,
      plan_end: task.plan_end,
      subtasks: task.subtasks
        .map((subtask) => ({
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

function AssigneePicker({
  people,
  value,
  disabled,
  onChange,
}: {
  people: Person[]
  value: number | ''
  disabled?: boolean
  onChange: (value: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [menuPosition, setMenuPosition] = useState<{ top: number; left: number; width: number } | null>(null)
  const anchorRef = useRef<HTMLButtonElement | null>(null)
  const selected = people.find((person) => person.id === value)
  const filtered = people.filter((person) => {
    const haystack = `${person.name} ${person.department ?? ''}`.toLowerCase()
    return haystack.includes(query.trim().toLowerCase())
  })

  useEffect(() => {
    if (!open) return undefined
    const closeMenu = () => setOpen(false)
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
    setMenuPosition({ top: rect.bottom + 6, left: rect.left, width: Math.max(rect.width, 240) })
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
        className="flex h-9 w-full items-center justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2.5 text-left text-xs font-semibold text-slate-700 outline-none transition-colors hover:border-blue-300 hover:bg-white focus:border-blue-400 focus:bg-white focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span className="truncate">{selected?.name ?? '请选择负责人'}</span>
        <span className={`text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}>⌄</span>
      </button>
      {open && menuPosition && createPortal(
        <div
          className="fixed z-[100] overflow-hidden rounded-xl border border-slate-200 bg-white p-2 shadow-[0_16px_36px_rgba(15,23,42,0.18)]"
          style={{ top: menuPosition.top, left: menuPosition.left, width: menuPosition.width }}
          role="listbox"
        >
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索姓名或部门"
            className="mb-2 h-8 w-full rounded-lg border border-slate-200 bg-slate-50 px-2.5 text-xs text-slate-700 outline-none focus:border-blue-400 focus:bg-white"
          />
          <div className="max-h-52 space-y-0.5 overflow-y-auto">
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
  disabled,
  onChange,
}: {
  people: Person[]
  value: number[]
  excludedId: number | ''
  disabled?: boolean
  onChange: (personId: number) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [menuPosition, setMenuPosition] = useState<{ top: number; left: number; width: number } | null>(null)
  const anchorRef = useRef<HTMLButtonElement | null>(null)
  const selectedPeople = people.filter((person) => value.includes(person.id))
  const filtered = people.filter((person) => {
    if (person.id === excludedId) return false
    const haystack = `${person.name} ${person.department ?? ''}`.toLowerCase()
    return haystack.includes(query.trim().toLowerCase())
  })

  useEffect(() => {
    if (!open) return undefined
    const closeMenu = () => setOpen(false)
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
    setMenuPosition({ top: rect.bottom + 6, left: rect.left, width: Math.max(rect.width, 260) })
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
        className="flex min-h-9 w-full items-center justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-left text-xs font-semibold text-slate-700 outline-none transition-colors hover:border-blue-300 hover:bg-white focus:border-blue-400 focus:bg-white focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span className="min-w-0 truncate">
          {selectedPeople.length > 0 ? selectedPeople.map((person) => person.name).join('、') : '请选择协助人'}
        </span>
        <span className={`shrink-0 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}>⌄</span>
      </button>
      {open && menuPosition && createPortal(
        <div
          className="fixed z-[100] overflow-hidden rounded-xl border border-slate-200 bg-white p-2 shadow-[0_16px_36px_rgba(15,23,42,0.18)]"
          style={{ top: menuPosition.top, left: menuPosition.left, width: menuPosition.width }}
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
          <div className="max-h-52 space-y-0.5 overflow-y-auto">
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

export function OwnerSubmitModal({ project, onClose, onSuccess }: Props) {
  const [people, setPeople] = useState<Person[]>([])
  const [peopleLoading, setPeopleLoading] = useState(true)
  const [peopleError, setPeopleError] = useState('')
  const [fillForm, setFillForm] = useState<ProjectProfilePayload>(() => ({
    project_type: project.project_type ?? '',
    client_name: project.client_name ?? '',
    background: project.background ?? '',
    objectives: project.objectives ?? '',
    expected_outcomes: project.expected_outcomes ?? '',
    start_date: project.start_date ?? '',
    end_date: project.end_date ?? '',
  }))
  const [projectPeriod, setProjectPeriod] = useState(() => composeProjectPeriod(project.start_date, project.end_date))
  const [draftTasks, setDraftTasks] = useState<LocalTaskDraft[]>([cloneEmptyTask()])
  const [fillLoading, setFillLoading] = useState(false)

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
    setDraftTasks((prev) => [...prev, cloneEmptyTask()])
  }

  function removeTaskDraft(index: number) {
    setDraftTasks((prev) => (prev.length <= 1 ? prev : prev.filter((_, idx) => idx !== index)))
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
    const workProgressDraft = toPayloadDraft(draftTasks)
    if (workProgressDraft.length === 0) {
      toast.error('请至少新增一条重点工作')
      return
    }
    const subtaskCount = workProgressDraft.reduce((total, task) => total + (task.subtasks?.length ?? 0), 0)
    if (subtaskCount === 0) {
      toast.error('请至少添加一个关键任务')
      return
    }
    if (workProgressDraft.some((task) => task.subtasks?.some((subtask) => !subtask.assignee_id))) {
      toast.error('请选择关键任务负责人')
      return
    }

    const parsedProjectPeriod = parseProjectPeriod(projectPeriod)
    setFillLoading(true)
    try {
      const result = await ownerSubmitProfile(project.id, {
        ...fillForm,
        start_date: parsedProjectPeriod.start,
        end_date: parsedProjectPeriod.end,
        work_progress_draft: workProgressDraft,
      })
      toast.success('已提交审核，等待企业教练审核通过后正式启动')
      if (onSuccess) onSuccess(result)
      else onClose()
    } catch (e: any) {
      toast.error(e?.message || '提交失败，请重试')
    } finally {
      setFillLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-4"
      style={{ background: 'rgba(15,23,42,0.45)' }}
      onClick={() => !fillLoading && onClose()}
    >
      <div
        className="owner-submit-workbench-shell flex h-[92vh] w-[96vw] max-w-[1440px] flex-col overflow-hidden rounded-2xl border border-slate-200/80 bg-[#f7f9fc] text-slate-900 shadow-[0_28px_80px_rgba(15,23,42,0.24)]"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="owner-submit-workbench-header flex min-h-[76px] shrink-0 items-center justify-between border-b border-slate-200 bg-white px-7 py-4">
          <div className="flex min-w-0 items-center gap-3.5">
            <div className="h-11 w-1.5 rounded-full bg-orange-500" aria-hidden="true" />
            <div className="min-w-0">
              <h2 className="truncate text-xl font-bold tracking-[-0.02em] text-slate-900">
                填写立项信息 — {project.name}
              </h2>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-orange-200 bg-orange-50 px-2.5 py-1 text-[11px] font-bold text-orange-700">
                  待负责人完善
                </span>
                <span className="text-xs text-slate-500">补全项目资料，提交后进入企业教练审核。</span>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={fillLoading}
            className="ml-4 rounded-full px-3 py-2 text-xl leading-none text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50"
            aria-label="关闭"
          >
            ×
          </button>
        </header>

        <main className="owner-submit-workbench-main min-h-0 flex-1 overflow-x-hidden overflow-y-auto bg-[#f7f9fc] pb-6">
          <div className="owner-submit-workbench-columns mx-auto flex max-w-[1440px] flex-col items-stretch gap-5 px-5 py-5 lg:flex-row lg:items-start lg:px-7">
            <aside className="owner-submit-left-pane w-full shrink-0 space-y-4 lg:sticky lg:top-5 lg:w-[300px] xl:w-[330px]">
              <section className="owner-submit-core-card overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_8px_24px_rgba(15,23,42,0.05)]">
                <h3 className="sr-only">项目核心信息</h3>
                <div className="p-5">
                  <div className="space-y-5">
                    <div className="space-y-2">
                      <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                        项目名称
                      </label>
                      <input
                        value={project.name}
                        disabled
                        className="w-full border-none bg-transparent p-0 text-xl font-bold text-slate-900 placeholder:text-slate-300 focus:ring-0 disabled:opacity-100"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                        项目周期 / 时间段
                      </label>
                      <input
                        value={projectPeriod}
                        onChange={(e) => setProjectPeriod(e.target.value)}
                        placeholder="例如：2026-07-01 至 2026-12-31"
                        className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-800 placeholder:text-slate-400 focus:border-orange-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-orange-100"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                        项目完成准则 / 验收标准
                      </label>
                      <textarea
                        value={fillForm.objectives ?? ''}
                        onChange={(e) => setFillForm((prev) => ({ ...prev, objectives: e.target.value }))}
                        placeholder="描述项目完成后如何验收，例如关键结果、通过标准、交付边界等"
                        rows={3}
                        className="w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 text-sm leading-relaxed text-slate-700 placeholder:text-slate-400 focus:border-orange-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-orange-100"
                      />
                    </div>
                  </div>

                  <details className="group mt-4">
                    <summary className="flex cursor-pointer select-none items-center gap-2 text-sm font-semibold text-orange-700 transition-opacity hover:opacity-80">
                      <span className="text-base leading-none transition-transform group-open:rotate-90">›</span>
                      补充详细信息
                    </summary>
                    <div className="mt-4 space-y-4 border-t border-slate-200/80 pt-4">
                      <div className="space-y-1.5">
                        <label className="block text-[11px] font-semibold text-slate-500">客户名称</label>
                        <input
                          value={fillForm.client_name ?? ''}
                          onChange={(e) => setFillForm((prev) => ({ ...prev, client_name: e.target.value }))}
                          placeholder="内部项目可留空"
                          className="h-9 w-full rounded border border-slate-200 bg-white px-3 text-sm text-slate-700 placeholder:text-slate-400 focus:border-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-100"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="block text-[11px] font-semibold text-slate-500">项目类型</label>
                        <input
                          value={fillForm.project_type ?? ''}
                          onChange={(e) => setFillForm((prev) => ({ ...prev, project_type: e.target.value }))}
                          placeholder="博维内部项目"
                          className="h-9 w-full rounded border border-slate-200 bg-white px-3 text-sm text-slate-700 placeholder:text-slate-400 focus:border-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-100"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="block text-[11px] font-semibold text-slate-500">项目背景</label>
                        <textarea
                          value={fillForm.background ?? ''}
                          onChange={(e) => setFillForm((prev) => ({ ...prev, background: e.target.value }))}
                          placeholder="说明项目来源及必要性，可选"
                          rows={3}
                          className="w-full resize-none rounded border border-slate-200 bg-white px-3 py-2 text-sm leading-relaxed text-slate-700 placeholder:text-slate-400 focus:border-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-100"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="block text-[11px] font-semibold text-slate-500">补充说明</label>
                        <textarea
                          value={fillForm.expected_outcomes ?? ''}
                          onChange={(e) => setFillForm((prev) => ({ ...prev, expected_outcomes: e.target.value }))}
                          placeholder="其他需要备注的信息，可选"
                          rows={5}
                          className="w-full resize-none rounded border border-slate-200 bg-white px-3 py-2 text-sm leading-relaxed text-slate-700 placeholder:text-slate-400 focus:border-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-100"
                        />
                      </div>
                    </div>
                  </details>
                </div>
              </section>
            </aside>

            <section className="owner-submit-right-pane flex-1 min-w-0">
              <div className="owner-submit-workplan-heading mb-5 flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex min-w-0 flex-wrap items-center gap-3">
                    <h3 className="shrink-0 text-lg font-semibold text-slate-900">工作推进方案</h3>
                    <span className="mt-1 block max-w-3xl text-xs leading-5 text-slate-500">
                      规划重点工作方向，并细化关键任务执行计划。重点工作用于归类工作方向；关键任务才需要明确责任人、协助人和时间段。
                    </span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={addTaskDraft}
                  className="flex shrink-0 items-center gap-1.5 rounded-xl border border-blue-200 bg-white px-4 py-2.5 text-xs font-bold text-blue-700 shadow-sm transition-colors hover:border-blue-300 hover:bg-blue-50"
                >
                  + 新增重点工作
                </button>
              </div>

              <div>
                {draftTasks.map((task, taskIndex) => (
                  <div
                    key={taskIndex}
                    className="owner-submit-task-group mb-4 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_8px_24px_rgba(15,23,42,0.05)]"
                  >
                    <div className="owner-submit-task-group-header flex items-start gap-3 border-b border-slate-200 bg-slate-50 px-5 py-4">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white shadow-sm">
                        {taskIndex + 1}
                      </div>
                      <div className="grid flex-1 grid-cols-1 gap-4 md:grid-cols-2">
                        <div>
                          <label className="block text-[10px] font-semibold uppercase text-slate-500/80">
                            重点工作名称
                          </label>
                          <input
                            value={task.title}
                            onChange={(e) => updateTaskDraft(taskIndex, 'title', e.target.value)}
                            placeholder="请输入重点工作"
                            className="w-full border-none bg-transparent p-0 text-base font-bold text-slate-900 placeholder:text-slate-400 focus:ring-0"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] font-semibold uppercase text-slate-500/80">
                            目标成果 / 验收标准
                          </label>
                          <input
                            value={task.description}
                            onChange={(e) => updateTaskDraft(taskIndex, 'description', e.target.value)}
                            placeholder="请输入完成准则"
                            className="w-full border-none bg-transparent p-0 text-sm font-medium text-slate-700 placeholder:text-slate-400 focus:ring-0"
                          />
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeTaskDraft(taskIndex)}
                        disabled={draftTasks.length <= 1}
                        className="rounded-lg px-2 py-1 text-xs font-semibold text-slate-400 transition-colors hover:bg-red-50 hover:text-red-500 disabled:cursor-not-allowed disabled:opacity-30"
                        aria-label={`删除重点工作 ${taskIndex + 1}`}
                      >
                        删除
                      </button>
                    </div>

                    <div className="overflow-x-auto px-3 pb-1">
                      <table className="owner-submit-subtask-table min-w-[920px] w-full border-separate border-spacing-0 text-left text-sm">
                        <thead>
                          <tr className="border-b border-slate-200 bg-white text-[11px] font-bold tracking-wide text-slate-500">
                            <th className="w-[250px] py-2 pl-6 pr-3">关键任务</th>
                            <th className="w-[100px] px-3 py-2">责任人</th>
                            <th className="w-[100px] px-3 py-2">协助人</th>
                            <th className="w-[160px] px-3 py-2">时间段</th>
                            <th className="px-3 py-2">备注 / 标准</th>
                            <th className="w-[60px] px-3 py-2">操作</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {task.subtasks.map((subtask, subIndex) => (
                            <tr key={subIndex} className="group transition-colors hover:bg-blue-50/40">
                              <td className="py-3 pl-6 pr-3">
                                <input
                                  value={subtask.title}
                                  onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'title', e.target.value)}
                                  placeholder="例如：任务名称"
                                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100"
                                />
                              </td>
                              <td className="px-3 py-2.5 align-top">
                                <AssigneePicker
                                  people={people}
                                  value={subtask.assigneeId}
                                  disabled={peopleLoading || Boolean(peopleError)}
                                  onChange={(value) => updateSubTaskAssignee(taskIndex, subIndex, value)}
                                />
                              </td>
                              <td className="px-3 py-2.5 align-top">
                                <HelperPicker
                                  people={people}
                                  value={subtask.helperIds}
                                  excludedId={subtask.assigneeId}
                                  disabled={peopleLoading || Boolean(peopleError)}
                                  onChange={(personId) => toggleSubTaskHelper(taskIndex, subIndex, personId)}
                                />
                              </td>
                              <td className="px-3 py-3">
                                <input
                                  value={composeTaskPeriod(subtask.plan_start, subtask.plan_end)}
                                  onChange={(e) => updateSubTaskPeriod(taskIndex, subIndex, e.target.value)}
                                  placeholder="7.1 - 7.5"
                                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-2 text-sm text-slate-700 placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100"
                                />
                              </td>
                              <td className="px-3 py-3">
                                <input
                                  value={subtask.evaluation_standard}
                                  onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'evaluation_standard', e.target.value)}
                                  placeholder="补充说明，可选"
                                  className="w-full border-none p-0 bg-transparent text-sm text-slate-600 placeholder:text-slate-300 focus:ring-0"
                                />
                              </td>
                              <td className="px-3 py-3 text-right">
                                <button
                                  type="button"
                                  onClick={() => removeSubTaskDraft(taskIndex, subIndex)}
                                  disabled={task.subtasks.length <= 1}
                                  className="rounded px-1.5 py-1 text-[11px] text-slate-400 opacity-70 transition-opacity hover:bg-red-50 hover:text-red-500 hover:opacity-100 group-hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-20"
                                >
                                  删除
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    <div className="bg-white px-6 py-2.5">
                      <button
                        type="button"
                        onClick={() => addSubTaskDraft(taskIndex)}
                        className="text-xs font-bold text-blue-700 transition-colors hover:text-blue-800 hover:underline"
                      >
                        + 新增关键任务
                      </button>
                    </div>
                  </div>
                ))}
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
      </div>
    </div>
  )
}
