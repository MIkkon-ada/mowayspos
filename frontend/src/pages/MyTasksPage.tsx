import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProject } from '../context/ProjectContext'
import { createUpdate, fetchMyUpdates, type UpdateHistoryItem } from '../api/updates'
import {
  fetchSubtasksByAssignee,
  isPendingConfirmation,
  patchSubTaskStatus,
  type SubTaskWithParent,
} from '../api/subtasks'
import { fmtPlanTime } from '../utils/time'
import { normalizeTaskStatus } from '../domain/myTasksFlow'
import { getProjectDisplayName } from '../domain/projectDisplay'
import { toast } from '../utils/toast'
import { Skel } from '../components/Skeleton'

// ─── Types ────────────────────────────────────────────────────────────────────

type QuickModal =
  | { kind: 'progress'; task: SubTaskWithParent; completeAfterSubmit?: boolean }
  | { kind: 'issue'; task: SubTaskWithParent }
  | null

type ProgressEntry = {
  id: number
  date: string
  submitter: string
  completed: string
  nextSteps: string[]
  issues: string[]
}

type ProjectGroup = {
  key: string
  projectId: number | null
  projectName: string
  tasks: SubTaskWithParent[]
  accentIdx: number
}

// ─── Constants ────────────────────────────────────────────────────────────────

const STATUS_META: Record<string, { label: string; color: string; bg: string }> = {
  未开始: { label: '未开始', color: '#64748B', bg: '#F1F5F9' },
  进行中: { label: '进行中', color: '#2563EB', bg: '#DBEAFE' },
  已完成: { label: '已完成', color: '#059669', bg: '#D1FAE5' },
  延期:   { label: '延期',   color: '#DC2626', bg: '#FEE2E2' },
  暂缓:   { label: '暂缓',   color: '#D97706', bg: '#FEF3C7' },
}

const STATUS_ORDER: Record<string, number> = {
  进行中: 0, 未开始: 1, 延期: 2, 暂缓: 3, 已完成: 4,
}

const ACCENTS = ['#2563EB', '#0EA5E9', '#8B5CF6', '#10B981', '#F59E0B', '#EF4444']

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getStatusMeta(status?: string) {
  return STATUS_META[normalizeTaskStatus(status)] ?? STATUS_META['未开始']
}

function accent(i: number) { return ACCENTS[i % ACCENTS.length] }

function fmtDateTime(iso: string): string {
  try {
    const d = new Date(iso)
    const today = new Date()
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    if (d.toDateString() === today.toDateString()) return `今天 ${hh}:${mm}`
    const mo = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    return `${d.getFullYear()}-${mo}-${dd} ${hh}:${mm}`
  } catch { return iso }
}

function groupTasksByProject(tasks: SubTaskWithParent[], projects: Array<{ id: number; name: string }>): ProjectGroup[] {
  const map = new Map<string, ProjectGroup>()
  let idx = 0
  for (const task of tasks) {
    const projectId   = task.parent_project_id ?? null
    const projectName = getProjectDisplayName(projects, task, '未命名项目')
    const key = `${projectId ?? 'null'}::${projectName}`
    const g = map.get(key)
    if (g) {
      g.tasks.push(task)
    } else {
      map.set(key, { key, projectId, projectName, tasks: [task], accentIdx: idx++ })
    }
  }
  return Array.from(map.values()).map((g) => ({
    ...g,
    tasks: [...g.tasks].sort((a, b) => {
      const oa = STATUS_ORDER[normalizeTaskStatus(a.status)] ?? 99
      const ob = STATUS_ORDER[normalizeTaskStatus(b.status)] ?? 99
      return oa !== ob ? oa - ob : String(a.plan_time || '').localeCompare(String(b.plan_time || ''))
    }),
  }))
}

function countByStatus(tasks: SubTaskWithParent[]) {
  return {
    waiting:  tasks.filter((t) => normalizeTaskStatus(t.status) === '未开始').length,
    progress: tasks.filter((t) => normalizeTaskStatus(t.status) === '进行中').length,
    blocked:  tasks.filter((t) => ['延期', '暂缓'].includes(normalizeTaskStatus(t.status))).length,
    done:     tasks.filter((t) => normalizeTaskStatus(t.status) === '已完成').length,
  }
}

function parseProgressForSubtask(updates: UpdateHistoryItem[], subtaskId: number): ProgressEntry[] {
  const result: ProgressEntry[] = []
  for (const u of updates) {
    let parsed: Record<string, unknown> | null = null
    if (u.ai_result_json) {
      try { parsed = JSON.parse(u.ai_result_json) } catch { /* ignore */ }
    }
    if (!parsed && u['human_result'] && typeof u['human_result'] === 'object') {
      parsed = u['human_result'] as Record<string, unknown>
    }
    if (!parsed) continue
    const reports = (parsed.task_reports ?? []) as unknown[]
    for (const r of reports) {
      const report = r as Record<string, unknown>
      if (report.type === 'progress' && report.matched_subtask_id === subtaskId) {
        const completed = typeof report.completed === 'string'
          ? report.completed
          : Array.isArray(report.completed) ? (report.completed as string[]).join('；') : ''
        result.push({
          id: u.id,
          date: u.created_at,
          submitter: u.submitter,
          completed,
          nextSteps: Array.isArray(report.next_steps) ? report.next_steps as string[] : [],
          issues:    Array.isArray(report.subtask_issues) ? report.subtask_issues as string[] : [],
        })
        break
      }
    }
  }
  return result.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function MyTasksPage() {
  const { currentUser, projects } = useProject()
  const [subtasks,        setSubtasks]        = useState<SubTaskWithParent[]>([])
  const [allUpdates,      setAllUpdates]      = useState<UpdateHistoryItem[]>([])
  const [loading,         setLoading]         = useState(true)
  const [fetchError,      setFetchError]      = useState<string | null>(null)
  const [projectFilter,   setProjectFilter]   = useState<number | null>(null)
  const [selectedTaskId,  setSelectedTaskId]  = useState<number | null>(null)
  const [modal,           setModal]           = useState<QuickModal>(null)
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())

  function toggleGroup(key: string) {
    setCollapsedGroups((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  function reload() {
    const assignee = currentUser?.name || currentUser?.username
    if (!assignee) return
    setLoading(true); setFetchError(null)
    fetchSubtasksByAssignee(assignee, null)
      .then((data) => {
        const list = data.filter((s) => !s.is_deleted)
        if (list.length > 0 || !currentUser?.username || currentUser.username === assignee) {
          setSubtasks(list); return
        }
        return fetchSubtasksByAssignee(currentUser.username, null)
          .then((fb) => setSubtasks(fb.filter((s) => !s.is_deleted)))
      })
      .catch((e: unknown) => setFetchError(e instanceof Error ? e.message : '加载失败，请刷新重试'))
      .finally(() => setLoading(false))
    fetchMyUpdates().then(setAllUpdates).catch(() => {})
  }

  useEffect(() => { reload() }, [currentUser?.name]) // eslint-disable-line react-hooks/exhaustive-deps

  const visibleTasks  = useMemo(() =>
    projectFilter === null ? [...subtasks] : subtasks.filter((s) => s.parent_project_id === projectFilter),
    [subtasks, projectFilter])

  const projectGroups = useMemo(() => groupTasksByProject(visibleTasks, projects), [visibleTasks, projects])
  const stats         = useMemo(() => countByStatus(visibleTasks), [visibleTasks])

  const selectedTask  = useMemo(() => {
    if (selectedTaskId != null) return visibleTasks.find((t) => t.id === selectedTaskId) ?? null
    return visibleTasks[0] ?? null
  }, [selectedTaskId, visibleTasks])

  const progressRecords = useMemo(() => {
    if (!selectedTask) return []
    return parseProgressForSubtask(allUpdates, selectedTask.id)
  }, [allUpdates, selectedTask])

  useEffect(() => {
    if (!visibleTasks.length) { if (selectedTaskId !== null) setSelectedTaskId(null); return }
    if (!selectedTask || !visibleTasks.some((t) => t.id === selectedTask.id))
      setSelectedTaskId(visibleTasks[0].id)
  }, [visibleTasks, selectedTask, selectedTaskId])

  return (
    <div className="flex h-full min-h-0 flex-col" style={{ background: '#F1F5F9' }}>

      {/* ── Compact header ── */}
      <header className="flex-shrink-0 border-b bg-white px-6 py-2.5" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex items-center gap-4">
          <div className="flex-shrink-0">
            <h1 className="text-sm font-bold text-slate-800">我的工作台</h1>
            <p className="text-[11px] text-slate-400">按项目汇总我负责的关键任务</p>
          </div>

          {/* Stat chips */}
          <div className="flex items-center gap-2">
            <StatChip label="待开始"    value={stats.waiting}  color="#64748B" />
            <StatChip label="进行中"    value={stats.progress} color="#2563EB" highlight />
            <StatChip label="延期/暂缓" value={stats.blocked}  color="#DC2626" />
            <StatChip label="已完成"    value={stats.done}     color="#059669" />
          </div>

          {/* Controls */}
          <div className="ml-auto flex items-center gap-2">
            <div className="relative">
              <select
                value={projectFilter ?? ''}
                onChange={(e) => setProjectFilter(e.target.value ? Number(e.target.value) : null)}
                className="appearance-none rounded-lg border border-slate-200 bg-white py-1.5 pl-2.5 pr-6 text-xs text-slate-600 focus:outline-none"
              >
                <option value="">全部项目</option>
                {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <svg className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2" width="10" height="10" fill="none" stroke="#94A3B8" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 9l-7 7-7-7"/>
              </svg>
            </div>
            <button
              onClick={reload}
              className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-500 hover:bg-slate-50"
            >
              <svg width="11" height="11" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
              </svg>
              刷新
            </button>
          </div>
        </div>
      </header>

      {/* ── Body ── */}
      <main className="min-h-0 flex-1 overflow-hidden">
        {loading ? (
          <CompactLoadingState />
        ) : fetchError ? (
          <EmptyState title={fetchError} />
        ) : visibleTasks.length === 0 ? (
          <EmptyState
            title="暂无分配给你的关键任务"
            subtitle="如果你参与了项目，请让负责人在重点工作下分配关键任务。"
          />
        ) : (
          <div className="flex h-full min-h-0">

            {/* ── Left: compact list 55% ── */}
            <div
              className="flex-shrink-0 overflow-y-auto border-r"
              style={{ width: '55%', borderColor: '#E2E8F0', background: '#F8FAFC' }}
            >
              <div className="px-3 py-3 space-y-2">
                {projectGroups.map((group) => {
                  const ac = accent(group.accentIdx)
                  const collapsed = collapsedGroups.has(group.key)
                  return (
                    <div key={group.key}>
                      {/* Group header */}
                      <button
                        type="button"
                        onClick={() => toggleGroup(group.key)}
                        className="flex w-full items-center gap-2 px-2 py-1.5 rounded-md hover:bg-slate-200/60 text-left"
                      >
                        <span
                          className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded"
                          style={{ background: ac }}
                        >
                          <svg width="11" height="11" fill="none" stroke="#fff" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M3 7a2 2 0 012-2h4l2 2h10a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"/>
                          </svg>
                        </span>
                        <span className="text-xs font-bold text-slate-700">{group.projectName}</span>
                        <span
                          className="rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
                          style={{ background: `${ac}20`, color: ac }}
                        >
                          {group.tasks.length}
                        </span>
                        <svg
                          width="12" height="12" fill="none" stroke="#94A3B8" viewBox="0 0 24 24"
                          className="ml-auto flex-shrink-0 transition-transform duration-150"
                          style={{ transform: collapsed ? 'rotate(180deg)' : 'none' }}
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 15l7-7 7 7"/>
                        </svg>
                      </button>

                      {!collapsed && (
                        <div
                          className="overflow-hidden rounded-xl border bg-white"
                          style={{ borderColor: '#E2E8F0' }}
                        >
                          {group.tasks.map((task, i) => (
                            <SubtaskRow
                              key={task.id}
                              task={task}
                              ac={ac}
                              selected={selectedTask?.id === task.id}
                              isLast={i === group.tasks.length - 1}
                              onSelect={() => setSelectedTaskId(task.id)}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* ── Right: detail 45% ── */}
            <div className="flex min-h-0 flex-1 flex-col bg-white">
              {selectedTask ? (
                <RightPanel
                  key={selectedTask.id}
                  task={selectedTask}
                  projects={projects}
                  progressRecords={progressRecords}
                  onOpenProgress={() => setModal({ kind: 'progress', task: selectedTask })}
                  onOpenComplete={() => setModal({ kind: 'progress', task: selectedTask, completeAfterSubmit: true })}
                  onOpenIssue={() => setModal({ kind: 'issue', task: selectedTask })}
                />
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-slate-400">
                  请从左侧选择一个关键任务
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {modal && (
        <TaskUpdateModal
          modal={modal}
          currentUserName={currentUser?.name ?? ''}
          onClose={() => setModal(null)}
          onSubmitted={() => { setModal(null); reload() }}
        />
      )}
    </div>
  )
}

// ─── StatChip ─────────────────────────────────────────────────────────────────

function StatChip({ label, value, color, highlight }: {
  label: string; value: number; color: string; highlight?: boolean
}) {
  return (
    <div
      className="flex items-center gap-1.5 rounded-lg px-2.5 py-1"
      style={{
        background: highlight ? `${color}14` : '#F1F5F9',
        border: `1px solid ${highlight ? color + '30' : '#E2E8F0'}`,
      }}
    >
      <span className="text-sm font-bold leading-none" style={{ color }}>{value}</span>
      <span className="text-[11px] text-slate-400">{label}</span>
    </div>
  )
}

// ─── SubtaskRow ───────────────────────────────────────────────────────────────

function SubtaskRow({ task, ac, selected, isLast, onSelect }: {
  task: SubTaskWithParent; ac: string; selected: boolean; isLast: boolean; onSelect: () => void
}) {
  const meta      = getStatusMeta(task.status)
  const updatedAt = task.updated_at ? fmtDateTime(task.updated_at) : null

  return (
    <div
      role="button" tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => e.key === 'Enter' && onSelect()}
      className="flex cursor-pointer items-center gap-3 px-4 outline-none transition-colors"
      style={{
        minHeight: 68,
        borderLeft: selected ? `3px solid ${ac}` : '3px solid transparent',
        background: selected ? '#EFF6FF' : 'transparent',
        borderBottom: isLast ? 'none' : '1px solid #F1F5F9',
      }}
    >
      {/* Status */}
      <span
        className="flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold whitespace-nowrap"
        style={{ background: meta.bg, color: meta.color }}
      >
        {meta.label}
      </span>

      {/* Title + meta */}
      <div className="min-w-0 flex-1 py-3">
        <p className="line-clamp-1 text-sm font-semibold leading-5 text-slate-800">{task.title}</p>
        <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-slate-400">
          <span>{task.assignee}</span>
          {task.plan_time && (
            <>
              <span className="text-slate-200">·</span>
              <span>{fmtPlanTime(task.plan_time)}</span>
            </>
          )}
        </div>
      </div>

      {/* Last updated */}
      {updatedAt && (
        <p className="flex-shrink-0 whitespace-nowrap text-[10px] text-slate-300">{updatedAt}</p>
      )}
    </div>
  )
}

// ─── RightPanel ───────────────────────────────────────────────────────────────
// key={task.id} is set by caller — local state resets automatically on task switch

function RightPanel({ task, projects, progressRecords, onOpenProgress, onOpenComplete, onOpenIssue }: {
  task: SubTaskWithParent
  projects: Array<{ id: number; name: string }>
  progressRecords: ProgressEntry[]
  onOpenProgress: () => void
  onOpenComplete: () => void
  onOpenIssue: () => void
}) {
  const navigate = useNavigate()
  const meta = getStatusMeta(task.status)

  const [showAll,      setShowAll]      = useState(false)
  const [descExpanded, setDescExpanded] = useState(false)

  const description = (task.notes?.trim() || task.completion_criteria?.trim()) || ''
  const visibleRecords = showAll ? progressRecords : progressRecords.slice(0, 2)

  return (
    <div className="flex h-full min-h-0 flex-col">

      {/* Scrollable content */}
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">

        {/* Breadcrumb */}
        <nav className="mb-3 flex items-center gap-1 text-xs text-slate-400 truncate">
          <span className="max-w-[110px] truncate">{getProjectDisplayName(projects, task, '—')}</span>
          <span className="flex-shrink-0">›</span>
          <span className="max-w-[130px] truncate">{task.parent_key_task || '—'}</span>
          <span className="flex-shrink-0">›</span>
          <span className="font-medium text-slate-500 flex-shrink-0">关键任务</span>
        </nav>

        {/* Title */}
        <h2 className="mb-3 line-clamp-2 text-base font-bold leading-snug text-slate-800">
          {task.title}
        </h2>

        {/* Status summary */}
        <div
          className="mb-5 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl px-4 py-3 text-xs"
          style={{ background: '#F8FAFC', border: '1px solid #E9EFF6' }}
        >
          <span
            className="rounded-full px-2.5 py-0.5 font-bold text-[11px]"
            style={{ background: meta.bg, color: meta.color }}
          >
            {meta.label}
          </span>

          <div className="flex items-center gap-1 text-slate-500">
            <span className="text-slate-400">负责人</span>
            <span className="font-semibold text-slate-700">{task.assignee || '—'}</span>
          </div>

          {task.plan_time && (
            <div className="flex items-center gap-1 text-slate-500">
              <svg width="11" height="11" fill="none" stroke="#94A3B8" strokeWidth="1.8" viewBox="0 0 24 24">
                <rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>
              </svg>
              <span className="text-slate-600">{fmtPlanTime(task.plan_time)}</span>
            </div>
          )}

          {task.updated_at && (
            <div className="flex items-center gap-1 text-slate-400">
              <span>最近更新</span>
              <span className="text-slate-600">{fmtDateTime(task.updated_at)}</span>
            </div>
          )}

          <button
            type="button"
            onClick={() => navigate(`/project/${task.parent_project_id}/tasks?open_task=${task.parent_task_id}`)}
            className="ml-auto flex-shrink-0 text-[11px] font-semibold text-indigo-500 hover:text-indigo-700"
          >
            查看重点工作 →
          </button>
        </div>

        {/* Progress timeline */}
        <section className="mb-5">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-bold text-slate-700">进度记录</span>
            {progressRecords.length > 0 && (
              <span className="text-xs text-slate-400">{progressRecords.length} 条</span>
            )}
          </div>

          {progressRecords.length === 0 ? (
            <div
              className="rounded-xl px-4 py-8 text-center"
              style={{ background: '#F8FAFC', border: '1px dashed #CBD5E1' }}
            >
              <p className="text-sm text-slate-400">暂无进展记录</p>
              <p className="mt-1 text-xs text-slate-300">点击底部"更新进展"提交第一次进展</p>
            </div>
          ) : (
            <>
              {/* Timeline */}
              <div className="relative pl-7">
                {/* vertical rail */}
                <div
                  className="absolute bottom-2 left-2 top-2"
                  style={{ width: 2, background: '#E2E8F0' }}
                />
                <div className="space-y-4">
                  {visibleRecords.map((entry, i) => (
                    <TimelineEntry key={entry.id} entry={entry} isLatest={i === 0} />
                  ))}
                </div>
              </div>

              {progressRecords.length > 2 && (
                <button
                  type="button"
                  onClick={() => setShowAll(v => !v)}
                  className="mt-3 flex w-full items-center justify-center gap-1 text-xs font-semibold text-indigo-500 hover:text-indigo-700"
                >
                  {showAll ? '收起' : `查看全部记录（${progressRecords.length} 条）`}
                  <svg
                    width="11" height="11" fill="none" stroke="currentColor" viewBox="0 0 24 24"
                    style={{ transform: showAll ? 'rotate(180deg)' : 'none', transition: 'transform .15s' }}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 9l-7 7-7-7"/>
                  </svg>
                </button>
              )}
            </>
          )}
        </section>

        {/* Task description — collapsible, low priority */}
        {description && (
          <section>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-bold text-slate-700">任务说明</span>
              <button
                type="button"
                onClick={() => setDescExpanded(v => !v)}
                className="text-xs text-slate-400 hover:text-slate-600"
              >
                {descExpanded ? '收起' : '展开'}
              </button>
            </div>
            <p
              className={`whitespace-pre-line rounded-xl px-4 py-3 text-sm leading-6 text-slate-600 ${descExpanded ? '' : 'line-clamp-3'}`}
              style={{ background: '#FAFAFA', border: '1px solid #E9EFF6' }}
            >
              {description}
            </p>
          </section>
        )}
      </div>

      {/* Fixed bottom action bar */}
      <div
        className="flex-shrink-0 border-t px-5 py-3"
        style={{ borderColor: '#E9EFF6', background: '#fff' }}
      >
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenProgress}
            className="h-9 flex-1 rounded-lg text-sm font-semibold text-white"
            style={{ background: 'linear-gradient(135deg,#1d4ed8,#3b82f6)' }}
          >
            更新进展
          </button>
          <button
            type="button"
            onClick={onOpenComplete}
            className="h-9 rounded-lg border border-emerald-300 px-3 text-sm font-semibold text-emerald-600 hover:bg-emerald-50"
          >
            提交完成
          </button>
          <button
            type="button"
            onClick={onOpenIssue}
            className="h-9 rounded-lg border border-amber-300 px-3 text-sm font-semibold text-amber-600 hover:bg-amber-50"
          >
            上报问题
          </button>
          <button
            type="button"
            className="h-9 rounded-lg border border-slate-200 px-3 text-sm font-semibold text-slate-500 hover:bg-slate-50"
          >
            更多
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── TimelineEntry ────────────────────────────────────────────────────────────

function TimelineEntry({ entry, isLatest }: { entry: ProgressEntry; isLatest: boolean }) {
  return (
    <div className="relative">
      {/* Dot */}
      <div
        className="absolute rounded-full border-2 border-white"
        style={{
          left: -21,
          top: 5,
          width: 10,
          height: 10,
          background: isLatest ? '#2563EB' : '#CBD5E1',
          boxShadow: isLatest ? '0 0 0 3px #DBEAFE' : 'none',
        }}
      />

      {/* Header */}
      <div className="mb-1.5 flex items-center gap-2">
        <span className="text-[11px] font-semibold text-slate-500">{fmtDateTime(entry.date)}</span>
        <span className="text-[11px] text-slate-400">{entry.submitter}</span>
        {isLatest && (
          <span
            className="rounded-full px-1.5 py-0.5 text-[10px] font-bold"
            style={{ background: '#DBEAFE', color: '#1d4ed8' }}
          >
            最新
          </span>
        )}
      </div>

      {/* 3-col content */}
      <div
        className="grid gap-3 rounded-xl p-3"
        style={{
          gridTemplateColumns: '1fr 1fr 1fr',
          background: '#F8FAFC',
          border: '1px solid #E9EFF6',
        }}
      >
        <EntryCol label="本次完成">
          {entry.completed ? (
            <p className="whitespace-pre-line text-xs leading-5 text-slate-700">{entry.completed}</p>
          ) : <Dash />}
        </EntryCol>

        <EntryCol label="下一步计划">
          {entry.nextSteps.length > 0 ? (
            <ul className="space-y-0.5">
              {entry.nextSteps.map((s, i) => (
                <li key={i} className="flex items-start gap-1 text-xs leading-5 text-slate-700">
                  <span className="mt-2 h-1 w-1 flex-shrink-0 rounded-full bg-slate-400" />
                  {s}
                </li>
              ))}
            </ul>
          ) : <Dash />}
        </EntryCol>

        <EntryCol label="问题 / 风险">
          {entry.issues.length > 0 ? (
            <ul className="space-y-0.5">
              {entry.issues.map((s, i) => (
                <li key={i} className="flex items-start gap-1 text-xs leading-5 text-amber-700">
                  <span className="mt-2 h-1 w-1 flex-shrink-0 rounded-full bg-amber-400" />
                  {s}
                </li>
              ))}
            </ul>
          ) : <Dash />}
        </EntryCol>
      </div>
    </div>
  )
}

function EntryCol({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-slate-400">{label}</p>
      {children}
    </div>
  )
}

function Dash() {
  return <p className="text-xs text-slate-300">暂无</p>
}

// ─── TaskUpdateModal ──────────────────────────────────────────────────────────

function TaskUpdateModal({ modal, currentUserName, onClose, onSubmitted }: {
  modal: Exclude<QuickModal, null>
  currentUserName: string
  onClose: () => void
  onSubmitted: () => void
}) {
  const isIssue            = modal.kind === 'issue'
  const completeAfterSubmit = modal.kind === 'progress' && Boolean(modal.completeAfterSubmit)
  const [text,      setText]      = useState('')
  const [issueType, setIssueType] = useState('问题')
  const [saving,    setSaving]    = useState(false)

  async function handleSubmit() {
    const content = text.trim()
    if (!content) return
    const projectId = modal.task.parent_project_id
    if (!projectId) { toast.error('该关键任务缺少项目归属，无法提交。'); return }
    setSaving(true)
    try {
      await createUpdate({
        project_id:      projectId,
        source_type:     isIssue ? '我的工作台-问题上报' : '我的工作台-进展更新',
        title:           `${modal.task.title}${isIssue ? '问题上报' : '进展更新'}`,
        transcript_text: isIssue
          ? `关键任务：${modal.task.title}\n重点工作：${modal.task.parent_key_task}\n问题类型：${issueType}\n问题描述：${content}`
          : `关键任务：${modal.task.title}\n重点工作：${modal.task.parent_key_task}\n本次进展：${content}`,
        submitter:   currentUserName,
        human_result: isIssue
          ? {
              summary: content,
              special_project: modal.task.parent_special_project,
              related_task: modal.task.parent_key_task,
              key_task_issues: [{
                key_task_title: modal.task.parent_key_task,
                issue_type: issueType,
                description: content,
                need_coordination: [],
                priority: issueType === '需决策' ? '高' : '中',
              }],
            }
          : {
              summary: content,
              special_project: modal.task.parent_special_project,
              related_task: modal.task.parent_key_task,
              task_reports: [{
                type: 'progress',
                matched_subtask_id: modal.task.id,
                matched_subtask_title: modal.task.title,
                completed: content,
                achievements: [],
                subtask_issues: [],
                next_steps: [],
                status_update: '进行中',
              }],
            },
      })
      if (!isIssue && completeAfterSubmit) {
        const r = await patchSubTaskStatus(modal.task.id, '已完成')
        if (isPendingConfirmation(r)) toast.info('已提交至 AI 确认中心，请等待项目负责人确认。')
      }
      onSubmitted()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : '提交失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 p-4">
      <div className="w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b px-5 py-4" style={{ borderColor: '#E9EFF6' }}>
          <div>
            <h2 className="text-base font-bold text-slate-800">
              {isIssue ? '上报问题' : completeAfterSubmit ? '提交完成' : '更新进展'}
            </h2>
            <p className="mt-0.5 text-xs text-slate-400">
              {modal.task.parent_key_task} / {modal.task.title}
            </p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100">
            <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div className="space-y-4 p-5">
          {isIssue && (
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-slate-500">问题类型</label>
              <select
                value={issueType}
                onChange={(e) => setIssueType(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm focus:outline-none"
              >
                <option>问题</option>
                <option>风险</option>
                <option>需协调</option>
                <option>需决策</option>
              </select>
            </div>
          )}
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-slate-500">
              {isIssue ? '问题描述' : '本次进展'}
            </label>
            <textarea
              rows={6}
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:outline-none"
              placeholder={
                isIssue
                  ? '描述遇到的问题、影响范围和需要协助的内容。'
                  : completeAfterSubmit
                    ? '说明已经完成了什么、交付了什么成果。'
                    : '说明已完成内容、当前进展和下一步计划。'
              }
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t px-5 py-4" style={{ borderColor: '#E9EFF6' }}>
          <button
            onClick={onClose}
            className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600"
          >
            取消
          </button>
          <button
            disabled={saving || !text.trim()}
            onClick={handleSubmit}
            className="rounded-xl px-5 py-2 text-sm font-bold text-white disabled:opacity-50"
            style={{ background: isIssue ? '#D97706' : 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}
          >
            {saving ? '提交中...' : '提交'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Loading / Empty ──────────────────────────────────────────────────────────

function CompactLoadingState() {
  return (
    <div className="flex h-full min-h-0">
      <div className="w-[55%] border-r p-4 space-y-3" style={{ borderColor: '#E2E8F0' }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 rounded-xl border bg-white px-4 py-3" style={{ borderColor: '#E9EFF6' }}>
            <Skel width={40} height={18} radius={9} />
            <div className="flex-1 space-y-1.5">
              <Skel width="70%" height={13} />
              <Skel width="40%" height={10} />
            </div>
          </div>
        ))}
      </div>
      <div className="flex-1 p-6 space-y-4">
        <Skel width="50%" height={12} />
        <Skel width="90%" height={20} />
        <Skel width="100%" height={60} radius={12} />
        <Skel width="40%" height={14} />
        <Skel width="100%" height={100} radius={12} />
      </div>
    </div>
  )
}

function EmptyState({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100">
        <svg width="28" height="28" fill="none" stroke="#CBD5E1" strokeWidth="1.5" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
        </svg>
      </div>
      <p className="text-sm font-semibold text-slate-500">{title}</p>
      {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
    </div>
  )
}
