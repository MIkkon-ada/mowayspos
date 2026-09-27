import { useMemo, useState } from 'react'
import type { Project, SubTaskItem, TaskItem } from '../../types'
import { buildPlanRows, type PlanTableRow } from './planTableViewModel'
import './workProgressWorkspace.css'

type Props = {
  project: Project | null
  tasks: TaskItem[]
  taskSubMap: Record<number, SubTaskItem[]>
  statusFilter?: string
  ownerFilter?: string
  searchText?: string
  loading?: boolean
  onOpenSubTask?: (subtask: SubTaskItem) => void
}

function CellText({ value, empty = '—', className = '', title }: { value?: string | null; empty?: string; className?: string; title?: string }) {
  const text = value?.trim() || empty
  return <span className={`wp-cell-text${text === '—' || text.startsWith('同一重点工作') ? ' is-empty' : ''}${className ? ` ${className}` : ''}`} title={title || text}>{text}</span>
}

function TaskTableRow({ row, onOpen, onOpenAcceptance }: { row: PlanTableRow; onOpen?: Props['onOpenSubTask']; onOpenAcceptance: (task: TaskItem) => void }) {
  const subtask = row.subtask
  const period = [row.planStart, row.planEnd].filter((value) => value && value !== '—')
  const planTime = [...new Set(period)].join(' — ') || '待安排'
  const submission = subtask?.latest_confirmed_submission
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
    </td>
    <td className="wp-owner-cell"><CellText value={row.responsible} /></td>
    <td className="wp-time-cell"><CellText value={planTime} empty="待安排" /></td>
    <td className="wp-status-cell"><span className={`wp-status wp-status--${row.statusTone}`}>{row.status}</span>{statusMarkers.map((marker) => <span key={marker.kind} className={`wp-marker wp-marker--${marker.kind}`}>{marker.label}</span>)}</td>
    <td className="wp-progress-cell"><CellText value={submission?.summary} empty="暂无已确认进展" />
      {submission && (submission.confirmed_at || submission.submitter) && <small>{submission.confirmed_at?.slice(0, 10)}{submission.submitter ? ` · ${submission.submitter}` : ''}</small>}
    </td>
    <td className="wp-next-step-cell"><CellText value={row.nextStep} /></td>
  </tr>
}

export function PlanTableViewV2({ project, tasks, taskSubMap, searchText = '', statusFilter = '', ownerFilter = '', loading = false, onOpenSubTask }: Props) {
  const [acceptanceTask, setAcceptanceTask] = useState<TaskItem | null>(null)
  const rows = useMemo(() => buildPlanRows({ project, tasks, taskSubMap, searchText, statusFilter, ownerFilter }), [project, tasks, taskSubMap, searchText, statusFilter, ownerFilter])
  if (loading) return <div className="wp-empty" role="status">正在加载项目工作…</div>
  return <section className="wp-workspace" aria-label="项目工作推进表">
    <div className="wp-table-scroll" key={project?.id}>
      {rows.length ? <table className="wp-table" aria-label="工作推进明细">
        <colgroup><col className="wp-col-workstream"/><col className="wp-col-key-task"/><col className="wp-col-owner"/><col className="wp-col-time"/><col className="wp-col-status"/><col className="wp-col-progress"/><col className="wp-col-next-step"/></colgroup>
        <thead><tr>
          <th scope="col">重点工作</th><th scope="col">关键任务</th><th scope="col">负责人</th><th scope="col">计划时间</th><th scope="col">状态 / 风险</th><th scope="col">最新进展</th><th scope="col">下一步计划</th>
        </tr></thead>
        <tbody>{rows.map((row) => <TaskTableRow key={`${row.task.id}-${row.subtask?.id ?? 'empty'}`} row={row} onOpen={onOpenSubTask} onOpenAcceptance={setAcceptanceTask} />)}</tbody>
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
