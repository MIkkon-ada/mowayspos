import { useMemo, useState } from 'react'
import type { CSSProperties } from 'react'
import type { Project, SubTaskItem, TaskItem } from '../../types'
import { buildPlanRows, type PlanTableRow } from './planTableViewModel'
import { WORK_PROGRESS_VIEW_COLUMNS, WORK_PROGRESS_OPTIONAL_COLUMNS, type WorkProgressOptionalColumnKey } from './workProgressColumnSizing'
import { useWorkProgressColumnLayout } from './useWorkProgressColumnLayout'
import './workProgressWorkspace.css'

type Props = {
  project: Project | null
  tasks: TaskItem[]
  taskSubMap: Record<number, SubTaskItem[]>
  statusFilter?: string
  ownerFilter?: string
  searchText?: string
  quickFilter?: 'all' | 'overdue' | 'risk' | 'issues'
  issueTaskIds?: ReadonlySet<number>
  issueSubtaskIds?: ReadonlySet<number>
  loading?: boolean
  optionalColumns?: readonly WorkProgressOptionalColumnKey[]
  onOpenSubTask?: (subtask: SubTaskItem) => void
  onEditSubTask?: (task: TaskItem, subtask: SubTaskItem) => void
}

function CellText({ value, empty = '—', className = '', title }: { value?: string | null; empty?: string; className?: string; title?: string }) {
  const text = value?.trim() || empty
  return <span className={`wp-cell-text${text === '—' || text.startsWith('同一重点工作') ? ' is-empty' : ''}${className ? ` ${className}` : ''}`} title={title || text}>{text}</span>
}

function ProgressPoints({ value, empty = '—' }: { value?: string | null; empty?: string }) {
  if (!value?.trim() || value.trim() === '—') return <CellText empty={empty} />
  const points = value?.split(/\r?\n|[；;]/)
    .map((point) => point.trim().replace(/^(?:(?:[-•·]|\d+[.、．)]|[（(]\d+[）)])\s*)+/, '').trim())
    .filter(Boolean) ?? []
  if (!points.length) return <CellText empty={empty} />
  return <ul className="wp-progress-points">{points.map((point, index) => <li key={index}>{point}</li>)}</ul>
}

function TaskTableRow({ row, onOpen, onEdit, onOpenAcceptance, optionalColumns }: { row: PlanTableRow; onOpen?: Props['onOpenSubTask']; onEdit?: Props['onEditSubTask']; onOpenAcceptance: (task: TaskItem) => void; optionalColumns: readonly WorkProgressOptionalColumnKey[] }) {
  const subtask = row.subtask
  const period = [row.planStart, row.planEnd].filter((value) => value && value !== '—')
  const planTime = [...new Set(period)].join(' — ') || '待安排'
  const submission = subtask?.latest_confirmed_submission
  const confirmedProgress = subtask?.latest_confirmed_progress
  const progressSummary = confirmedProgress?.summary?.trim() || submission?.summary
  const progressMeta = confirmedProgress?.summary?.trim()
    ? [confirmedProgress.confirmed_at?.slice(0, 10), confirmedProgress.actor, confirmedProgress.source_label].filter(Boolean).join(' · ')
    : submission ? [submission.confirmed_at?.slice(0, 10), submission.submitter].filter(Boolean).join(' · ') : ''
  const statusMarkers = row.statusMarkers.filter((marker) => marker.kind === 'risk' || marker.kind === 'overdue')
  return <tr className={row.showTaskCells ? 'wp-row-start' : undefined}>
    {row.showTaskCells && <td className="wp-workstream-cell" rowSpan={row.taskRowSpan}>
      <CellText value={row.workstream} />
      <button type="button" className="wp-standard-link" onClick={() => onOpenAcceptance(row.task)}>查看验收标准</button>
    </td>}
    <td className="wp-key-task-cell">
      {subtask && onOpen
        ? <button type="button" className="wp-task-link" onClick={() => onOpen(subtask)} title={row.keyTask}>{row.keyTask}</button>
        : <CellText value={row.keyTask} />}
      {subtask && onEdit && optionalColumns.length > 0 && <button type="button" className="wp-edit-fields" onClick={() => onEdit(row.task, subtask)}>编辑字段</button>}
    </td>
    {optionalColumns.map((key) => <td key={key} className="wp-optional-cell"><CellText value={key === 'expectedOutcome' ? subtask?.expected_outcome : key === 'goal' ? subtask?.goal : subtask?.bowei_role} /></td>)}
    <td className="wp-owner-cell"><CellText value={row.responsible} /></td>
    <td className="wp-time-cell"><CellText value={planTime} empty="待安排" /></td>
    <td className="wp-status-cell"><span className={`wp-status wp-status--${row.statusTone}`}>{row.status}</span>{statusMarkers.map((marker) => <span key={marker.kind} className={`wp-marker wp-marker--${marker.kind}`}>{marker.label}</span>)}</td>
    <td className="wp-progress-cell"><ProgressPoints value={progressSummary} empty="暂无已确认进展" />
      {progressMeta && <small>{progressMeta}</small>}
    </td>
    <td className="wp-next-step-cell">{confirmedProgress?.source_label === '会议纪要' && confirmedProgress.action_items?.length
      ? <ul className="wp-progress-points">{confirmedProgress.action_items.map((item, index) => <li key={item.fact_id || index}><strong>{item.code ? `${item.code} ` : ''}</strong>{item.content}<small className="block text-slate-500">{[item.owner && `负责人：${item.owner}`, item.tracker && `追踪：${item.tracker}`, item.due_date && `期限：${item.due_date}`].filter(Boolean).join(' · ')}</small></li>)}</ul>
      : <ProgressPoints value={row.nextStep} />}</td>
  </tr>
}

export function PlanTableViewV2({ project, tasks, taskSubMap, searchText = '', statusFilter = '', ownerFilter = '', quickFilter = 'all', issueTaskIds = new Set<number>(), issueSubtaskIds = new Set<number>(), loading = false, optionalColumns = [], onOpenSubTask, onEditSubTask }: Props) {
  const [acceptanceTask, setAcceptanceTask] = useState<TaskItem | null>(null)
  const enabledOptionalColumns = useMemo(() => WORK_PROGRESS_OPTIONAL_COLUMNS.filter((column) => optionalColumns.includes(column.key)).map((column) => column.key), [optionalColumns])
  const rows = useMemo(() => buildPlanRows({ project, tasks, taskSubMap, searchText, statusFilter, ownerFilter, quickFilter, issueTaskIds, issueSubtaskIds }), [project, tasks, taskSubMap, searchText, statusFilter, ownerFilter, quickFilter, issueTaskIds, issueSubtaskIds])
  const sizingRows = useMemo(() => buildPlanRows({ project, tasks, taskSubMap }), [project, tasks, taskSubMap])
  const columns = useMemo(() => [
    ...WORK_PROGRESS_VIEW_COLUMNS.slice(0, 2),
    ...WORK_PROGRESS_OPTIONAL_COLUMNS.filter((column) => enabledOptionalColumns.includes(column.key)),
    ...WORK_PROGRESS_VIEW_COLUMNS.slice(2),
  ], [enabledOptionalColumns])
  const { scrollRef, widths, startResize, changeWidth, resetWidth } = useWorkProgressColumnLayout(sizingRows, loading, project?.id, enabledOptionalColumns)
  const tableWidth = columns.reduce((sum, column) => sum + widths[column.key], 0)
  if (loading) return <div className="wp-empty" role="status">正在加载项目工作…</div>
  return <section className="wp-workspace" aria-label="项目工作推进表">
    <div ref={scrollRef} className="wp-table-scroll" key={project?.id}>
      {rows.length ? <table className="wp-table" aria-label="工作推进明细" style={{ width: tableWidth, '--wp-workstream-width': `${widths.workstream}px` } as CSSProperties}>
        <colgroup>{columns.map((column) => <col key={column.key} className={`wp-col-${column.key}`} style={{ width: widths[column.key] }} />)}</colgroup>
        <thead><tr>
          {columns.map((column) => <th key={column.key} scope="col" aria-label={column.label}>
            {column.label}
            <button type="button" className="wp-column-resizer" aria-label={`调整${column.label}列宽`} title="拖动调整列宽，双击恢复自动宽度"
              onPointerDown={(event) => startResize(column.key, event)} onDoubleClick={() => resetWidth(column.key)}
              onKeyDown={(event) => {
                if (event.key === 'Home') { event.preventDefault(); resetWidth(column.key) }
                if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
                  event.preventDefault()
                  changeWidth(column.key, widths[column.key] + (event.key === 'ArrowRight' ? 10 : -10))
                }
              }} />
          </th>)}
        </tr></thead>
        <tbody>{rows.map((row) => <TaskTableRow key={`${row.task.id}-${row.subtask?.id ?? 'empty'}`} row={row} onOpen={onOpenSubTask} onEdit={onEditSubTask} onOpenAcceptance={setAcceptanceTask} optionalColumns={enabledOptionalColumns} />)}</tbody>
      </table> : <div className="wp-empty">当前条件下没有匹配的重点工作或关键任务，请调整筛选条件。</div>}
    </div>
    {acceptanceTask && <div className="wp-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setAcceptanceTask(null) }}>
      <section className="wp-acceptance-modal" role="dialog" aria-modal="true" aria-labelledby="wp-acceptance-title">
        <header className="wp-acceptance-modal-header"><div><h2 id="wp-acceptance-title">重点工作验收标准</h2><p>{acceptanceTask.key_task}</p></div><button type="button" aria-label="关闭验收标准" onClick={() => setAcceptanceTask(null)}>×</button></header>
        <div className="wp-acceptance-modal-content">{acceptanceTask.completion_standard?.trim() || '该重点工作暂未填写验收标准。'}</div>
        <footer className="wp-acceptance-modal-footer"><button type="button" className="wp-button wp-button--primary" onClick={() => setAcceptanceTask(null)}>知道了</button></footer>
      </section>
    </div>}
  </section>
}
