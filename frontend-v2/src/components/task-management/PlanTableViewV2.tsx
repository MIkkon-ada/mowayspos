import { useMemo, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import type { Project, SubTaskItem, TaskItem } from '../../types'
import {
  getPlanStatusLabel,
  buildPlanRows,
  EMPTY_PLAN_CELL,
  type PlanTableRow,
} from './planTableViewModel'
import {
  getPlanRowCellValue,
  PLAN_TABLE_COLUMNS,
  type PlanTableColumnKey,
} from './planTableColumns'
import { PlanTableToolbar } from './PlanTableToolbar'
import { usePlanTableColumnLayout } from './usePlanTableColumnLayout'
import { usePlanTableZoom } from './usePlanTableZoom'
import './planTableExcel.css'
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

function cellText(value: string): ReactNode {
  return [EMPTY_PLAN_CELL, '未填写项目目标', '未填写验收标准', '暂无关键任务'].includes(value)
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
    return match
      ? { num: match[1].replace('、', '.'), content: match[2].trim() }
      : { num: '', content: part.trim() }
  })
}

function TaskStandardModal({ task, onClose }: { task: TaskItem | null; onClose: () => void }) {
  if (!task) return null
  const items = splitNumberedList(task.completion_standard || task.key_achievement || '未填写评价标准')
  return <div className="v2-modal-overlay" onClick={onClose}>
    <div className="v2-modal" onClick={(event) => event.stopPropagation()}>
      <div className="v2-modal__header">
        <h3 className="v2-modal__title">{task.key_task}</h3>
        <button type="button" className="v2-modal__close" onClick={onClose} aria-label="关闭">×</button>
      </div>
      <div className="v2-modal__body">
        <div className="v2-modal__section-title">评价标准</div>
        <ul className="v2-std-list">
          {items.map((item, index) => <li key={`${item.num}-${index}`} className="v2-std-list__item">
            {item.num && <span className="v2-std-list__num">{item.num}</span>}
            <span className="v2-std-list__text">{item.content}</span>
          </li>)}
        </ul>
      </div>
    </div>
  </div>
}

function ProjectStandardModal({ project, onClose }: { project: Project | null; onClose: () => void }) {
  if (!project?.objectives?.trim()) return null
  return <div className="v2-modal-overlay" onClick={onClose}>
    <div className="v2-modal" onClick={(event) => event.stopPropagation()}>
      <div className="v2-modal__header">
        <h3 className="v2-modal__title">项目完成标准</h3>
        <button type="button" className="v2-modal__close" onClick={onClose} aria-label="关闭">×</button>
      </div>
      <div className="v2-modal__body">
        <ul className="v2-std-list">
          {splitNumberedList(project.objectives).map((item, index) => <li key={`${item.num}-${index}`} className="v2-std-list__item">
            {item.num && <span className="v2-std-list__num">{item.num}</span>}
            <span className="v2-std-list__text">{item.content}</span>
          </li>)}
        </ul>
      </div>
    </div>
  </div>
}

function TaskCard({ task, onOpenStandard }: { task: TaskItem; onOpenStandard: (task: TaskItem) => void }) {
  const hasStandard = Boolean(task.completion_standard || task.key_achievement)
  return <div
    className="v2-task-card"
    role="button"
    tabIndex={0}
    onClick={(event) => { event.stopPropagation(); onOpenStandard(task) }}
    onKeyDown={(event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        onOpenStandard(task)
      }
    }}
  >
    <div className="v2-task-card__body">
      <div className="v2-task-card__title">{task.key_task || EMPTY_PLAN_CELL}</div>
      {hasStandard && <button
        type="button"
        className="v2-task-card__std-btn"
        onClick={(event) => { event.stopPropagation(); onOpenStandard(task) }}
      >查看评价标准</button>}
    </div>
  </div>
}

function renderCellContent(
  columnKey: PlanTableColumnKey,
  row: PlanTableRow,
): ReactNode {
  if (columnKey === 'keyTask') {
    if (!row.subtask) return cellText(row.keyTask)
    return <span className="v2-keytask-line">
      <span className="v2-keytask-line__text">{row.keyTask}</span>
      {row.statusMarkers.map((marker) => <span key={marker.kind} className={`v2-status-marker v2-status-marker--${marker.kind}`}>
        {marker.label}
      </span>)}
    </span>
  }

  if (columnKey === 'status') {
    return <span className={`v2-status-text v2-status-text--${row.statusTone}`}>
      {getPlanStatusLabel(row.status)}
    </span>
  }

  if (columnKey === 'latestProgress' && row.latestConfirmedSubmission) {
    const submission = row.latestConfirmedSubmission
    return <div className="v2-latest-submission">
      <div className="v2-latest-submission__meta">
        {formatConfirmedAt(submission.confirmed_at)} · {submission.submitter || EMPTY_PLAN_CELL}
      </div>
      <div className="v2-latest-submission__summary">{submission.summary || EMPTY_PLAN_CELL}</div>
    </div>
  }

  return cellText(getPlanRowCellValue(row, columnKey))
}

export function PlanTableViewV2({
  project,
  tasks,
  taskSubMap,
  searchText = '',
  loading = false,
  exportDisabled = false,
  onExport,
  canCreateTask = false,
  onCreateTask,
  onOpenSubTask,
}: Props) {
  const [selectedSubTaskId, setSelectedSubTaskId] = useState<number | null>(null)
  const [showProjectStandard, setShowProjectStandard] = useState(false)
  const [standardTask, setStandardTask] = useState<TaskItem | null>(null)
  const hasProjectStandard = Boolean(project?.objectives?.trim())
  const workspaceRef = useRef<HTMLDivElement>(null)
  const { zoomPercent, zoomIn, zoomOut, fitWidth, resetView } = usePlanTableZoom(workspaceRef)
  const { getColumnWidth, resetColumnWidths, startResize } = usePlanTableColumnLayout()
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

  return <section className="v2-plan-view" aria-label="项目工作推进表">
    <div className="v2-table-actions">
      <div className="v2-table-actions__project">
        <span className="v2-table-actions__label">项目：</span>
        <span className="v2-table-actions__name">{project?.name || '未选择项目'}</span>
      </div>
      <div className="v2-table-actions__buttons">
        {hasProjectStandard && <button type="button" className="v2-project-banner__toggle" onClick={() => setShowProjectStandard(true)}>
          评价标准
        </button>}
        {canCreateTask && onCreateTask && <button type="button" className="v2-project-banner__create" onClick={onCreateTask}>
          新增重点工作
        </button>}
      </div>
    </div>

    <PlanTableToolbar
      zoomPercent={zoomPercent}
      onZoomOut={zoomOut}
      onZoomIn={zoomIn}
      onFitWidth={fitWidth}
      onResetView={resetView}
      onExport={() => onExport?.()}
      exportDisabled={exportDisabled || !onExport}
    />
    <div className="v2-table-view-options">
      <span>拖拽表头右侧边界调整列宽，横向滚动查看完整字段</span>
      <button type="button" onClick={resetColumnWidths}>重置标准列宽</button>
    </div>

    <div ref={workspaceRef} className="v2-table-scroll">
      <div
        className="v2-table-canvas v2-sheet-frame"
        style={{
          zoom: zoomPercent / 100,
          ['--v2-wbs-width' as string]: `${getColumnWidth('wbsCode')}px`,
        }}
      >
        <table className="v2-grid">
          <colgroup>
            {PLAN_TABLE_COLUMNS.map((column) => <col key={column.key} className={`v2-col--${column.priority}`} style={{ width: `${getColumnWidth(column.key)}px` }} />)}
          </colgroup>
          <thead>
            <tr>
              {PLAN_TABLE_COLUMNS.map((column) => <th
                key={column.key}
                className={`v2-th v2-th--${column.key} v2-col--${column.priority}${column.key === 'wbsCode' ? ' v2-th--sticky-wbs' : ''}${column.key === 'workstream' ? ' v2-th--sticky-workstream' : ''}`}
              >
                <span className="v2-th__label">{column.label}</span>
                <button
                  type="button"
                  className="v2-th__resize-handle"
                  aria-label={`${column.label}列宽调整`}
                  title="拖拽调整列宽"
                  onPointerDown={(event) => startResize(column.key, event)}
                />
              </th>)}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0
              ? <tr className="v2-empty-row"><td colSpan={PLAN_TABLE_COLUMNS.length}>当前筛选条件下没有匹配的关键任务</td></tr>
              : rows.map((row) => {
                const selected = row.subtask?.id === selectedSubTaskId
                const canClick = row.subtask !== null
                return <tr
                  key={`${row.task.id}-${row.subtask?.id ?? 'empty'}-${row.sequence}`}
                  className={`${selected ? 'v2-tr--selected' : ''}${canClick ? ' v2-tr--clickable' : ''}`}
                  role={canClick ? 'button' : undefined}
                  tabIndex={canClick ? 0 : undefined}
                  onClick={canClick ? () => openKeyTask(row) : undefined}
                  onKeyDown={canClick ? (event) => handleKeyDown(event, row) : undefined}
                >
                  {PLAN_TABLE_COLUMNS.map((column) => {
                    const isTaskLevel = column.key === 'workstream' || column.key === 'deliverable'
                    if (isTaskLevel && !row.showTaskCells) return null
                    const isWorkstream = column.key === 'workstream'
                    const isWbs = column.key === 'wbsCode'
                    const className = `v2-td v2-td--${column.key} v2-col--${column.priority}${isWbs ? ' v2-td--sticky-wbs' : ''}${isWorkstream ? ' v2-td--sticky-workstream' : ''}${column.key === 'keyTask' && selected ? ' v2-td--selected' : ''}`
                    return <td key={column.key} rowSpan={isTaskLevel ? row.taskRowSpan : undefined} className={className}>
                      {isWorkstream
                        ? <TaskCard task={row.task} onOpenStandard={setStandardTask} />
                        : renderCellContent(column.key, row)}
                    </td>
                  })}
                </tr>
              })}
          </tbody>
        </table>
      </div>
    </div>

    <TaskStandardModal task={standardTask} onClose={() => setStandardTask(null)} />
    {showProjectStandard && <ProjectStandardModal project={project} onClose={() => setShowProjectStandard(false)} />}
  </section>
}
