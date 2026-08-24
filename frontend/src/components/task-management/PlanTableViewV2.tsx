import { useMemo, useState } from 'react'
import type { KeyboardEvent } from 'react'
import type { Project, SubTaskItem, TaskItem } from '../../types'
import { buildPlanRows, EMPTY_PLAN_CELL, type PlanTableRow } from './planTableViewModel'
import './planTableExcelV2.css'

type Props = {
  project: Project | null
  tasks: TaskItem[]
  taskSubMap: Record<number, SubTaskItem[]>
  searchText?: string
  loading?: boolean
  exportDisabled?: boolean
  onExport?: () => void
  canCreateTask?: boolean
  onCreateTask?: () => void
  currentUserName?: string
  projectRoles?: string[]
  isTechAdmin?: boolean
  onOpenSubTask?: (subtask: SubTaskItem) => void
}

function formatPlanTime(start: string, end: string): string {
  if (start === EMPTY_PLAN_CELL && end === EMPTY_PLAN_CELL) return EMPTY_PLAN_CELL
  if (start === '持续') return '持续'
  if (end === EMPTY_PLAN_CELL) return start
  if (start === end) return start
  return `${start} ~ ${end}`
}

function cellText(value: string) {
  return [EMPTY_PLAN_CELL, '未填写项目目标', '未填写评价标准', '暂无关键任务'].includes(value)
    ? <span className="v2-cell-placeholder">{value}</span>
    : value
}

function formatConfirmedAt(value: string): string {
  const normalized = String(value ?? '').trim()
  return normalized ? normalized.slice(0, 10) : EMPTY_PLAN_CELL
}

function splitNumberedList(text: string): Array<{ num: string; content: string }> {
  const parts = text.trim().split(/\s*\n+\s*|\s*[；;]\s*/).filter(Boolean)
  return parts.map((part) => {
    const match = part.match(/^(\d+[.、])\s*(.*)$/)
    return match ? { num: match[1].replace('、', '.'), content: match[2].trim() } : { num: '', content: part.trim() }
  })
}

function TaskStandardModal({ task, onClose }: { task: TaskItem | null; onClose: () => void }) {
  if (!task) return null
  const items = splitNumberedList(task.completion_standard || task.key_achievement || '未填写评价标准')
  return <div className="v2-modal-overlay" onClick={onClose}><div className="v2-modal" onClick={(event) => event.stopPropagation()}><div className="v2-modal__header"><h3 className="v2-modal__title">{task.key_task}</h3><button type="button" className="v2-modal__close" onClick={onClose} aria-label="关闭">×</button></div><div className="v2-modal__body"><div className="v2-modal__section-title">评价标准</div><ul className="v2-std-list">{items.map((item, index) => <li key={`${item.num}-${index}`} className="v2-std-list__item">{item.num && <span className="v2-std-list__num">{item.num}</span>}<span className="v2-std-list__text">{item.content}</span></li>)}</ul></div></div></div>
}

function ProjectStandardModal({ project, onClose }: { project: Project | null; onClose: () => void }) {
  if (!project?.objectives?.trim()) return null
  return <div className="v2-modal-overlay" onClick={onClose}><div className="v2-modal" onClick={(event) => event.stopPropagation()}><div className="v2-modal__header"><h3 className="v2-modal__title">项目完成标准</h3><button type="button" className="v2-modal__close" onClick={onClose} aria-label="关闭">×</button></div><div className="v2-modal__body"><ul className="v2-std-list">{splitNumberedList(project.objectives).map((item, index) => <li key={`${item.num}-${index}`} className="v2-std-list__item">{item.num && <span className="v2-std-list__num">{item.num}</span>}<span className="v2-std-list__text">{item.content}</span></li>)}</ul></div></div></div>
}

function TaskCard({ task, onOpenStandard }: { task: TaskItem; onOpenStandard: (task: TaskItem) => void }) {
  const hasStandard = Boolean(task.completion_standard || task.key_achievement)
  return <div className="v2-task-card" role="button" tabIndex={0} onClick={(event) => { event.stopPropagation(); onOpenStandard(task) }} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onOpenStandard(task) } }}><div className="v2-task-card__body"><div className="v2-task-card__title">{task.key_task || EMPTY_PLAN_CELL}</div>{hasStandard && <button type="button" className="v2-task-card__std-btn" onClick={(event) => { event.stopPropagation(); onOpenStandard(task) }}>查看评价标准</button>}</div></div>
}

export function PlanTableViewV2({ project, tasks, taskSubMap, searchText = '', loading = false, canCreateTask = false, onCreateTask, onOpenSubTask }: Props) {
  const [selectedSubTaskId, setSelectedSubTaskId] = useState<number | null>(null)
  const [showProjectStandard, setShowProjectStandard] = useState(false)
  const [standardTask, setStandardTask] = useState<TaskItem | null>(null)
  const hasProjectStandard = Boolean(project?.objectives?.trim())
  const rows = useMemo(() => buildPlanRows({ project, tasks, taskSubMap, searchText }), [project, searchText, taskSubMap, tasks])

  const openKeyTask = (row: PlanTableRow) => {
    if (!row.subtask) return
    setSelectedSubTaskId(row.subtask.id)
    onOpenSubTask?.(row.subtask)
  }
  const handleKeyDown = (event: KeyboardEvent<HTMLElement>, row: PlanTableRow) => {
    if (!row.subtask || (event.key !== 'Enter' && event.key !== ' ')) return
    event.preventDefault()
    openKeyTask(row)
  }
  if (loading) return <div className="h-40 flex items-center justify-center text-slate-400 text-sm">加载中...</div>

  return <section className="v2-plan-view" aria-label="工作推进表">
    <div className="v2-table-actions"><div className="v2-table-actions__project"><span className="v2-table-actions__label">项目：</span><span className="v2-table-actions__name">{project?.name || '未选择项目'}</span></div><div className="v2-table-actions__buttons">{hasProjectStandard && (<button type="button" className="v2-project-banner__toggle" onClick={() => setShowProjectStandard(true)}>评价标准</button>)}{canCreateTask && onCreateTask && <button type="button" className="v2-project-banner__create" onClick={onCreateTask}>新增重点工作</button>}</div></div>
    <div className="v2-table-scroll"><div className="v2-table-canvas v2-sheet-frame"><table className="v2-grid"><colgroup><col style={{ width: 300 }} /><col style={{ width: 360 }} /><col style={{ width: 80 }} /><col style={{ width: 130 }} /><col style={{ width: 155 }} /><col style={{ width: 280 }} /></colgroup><thead><tr><th className="v2-th v2-th--sticky-task">重点工作</th><th className="v2-th">关键任务</th><th className="v2-th">负责人</th><th className="v2-th">计划时间</th><th className="v2-th">协同人</th><th className="v2-th">最新已确认提交</th></tr></thead><tbody>{rows.length === 0 ? <tr className="v2-empty-row"><td colSpan={6}>当前筛选条件下没有匹配的关键任务</td></tr> : rows.map((row) => { const selected = row.subtask?.id === selectedSubTaskId; const canClick = row.subtask !== null; const submission = row.latestConfirmedSubmission; return <tr key={`${row.task.id}-${row.subtask?.id ?? 'empty'}-${row.sequence}`} className={`${selected ? 'v2-tr--selected' : ''}${canClick ? ' v2-tr--clickable' : ''}`} role={canClick ? 'button' : undefined} tabIndex={canClick ? 0 : undefined} onClick={canClick ? () => openKeyTask(row) : undefined} onKeyDown={canClick ? (event) => handleKeyDown(event, row) : undefined}>{row.showTaskCells && <td rowSpan={row.taskRowSpan} className="v2-td v2-td--task v2-th--sticky-task v2-td--task-card"><TaskCard task={row.task} onOpenStandard={setStandardTask} /></td>}<td className={`v2-td v2-td--keytask${selected ? ' v2-td--selected' : ''}`}>{canClick ? <span className="v2-keytask-line"><span className="v2-keytask-line__text">{row.keyTask}</span>{row.statusMarkers.map((marker) => <span key={marker.kind} className={`v2-status-marker v2-status-marker--${marker.kind}`}>{marker.label}</span>)}</span> : cellText(row.keyTask)}</td><td className="v2-td v2-td--person">{cellText(row.responsible)}</td><td className="v2-td v2-td--time">{cellText(formatPlanTime(row.planStart, row.planEnd))}</td><td className="v2-td v2-td--person">{cellText(row.assistingPerson)}</td><td className="v2-td v2-td--latest-submission">{submission ? <div className="v2-latest-submission"><div className="v2-latest-submission__meta">{formatConfirmedAt(submission.confirmed_at)} · {submission.submitter || EMPTY_PLAN_CELL}</div><div className="v2-latest-submission__summary">{submission.summary || EMPTY_PLAN_CELL}</div></div> : <span className="v2-cell-placeholder">暂无已确认提交</span>}</td></tr> })}</tbody></table></div></div>
    <TaskStandardModal task={standardTask} onClose={() => setStandardTask(null)} />
    {showProjectStandard && <ProjectStandardModal project={project} onClose={() => setShowProjectStandard(false)} />}
  </section>
}
