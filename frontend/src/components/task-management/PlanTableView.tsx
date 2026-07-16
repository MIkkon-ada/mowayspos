import { useMemo, useRef, useState } from 'react'
import type { CSSProperties, KeyboardEvent } from 'react'
import type { Project, SubTaskItem, TaskItem } from '../../types'
import { PlanTableStatusBar } from './PlanTableStatusBar'
import { PlanTableToolbar } from './PlanTableToolbar'
import {
  buildPlanRows,
  EMPTY_PLAN_CELL,
  PLAN_TABLE_BUSINESS_HEADERS,
  PLAN_TABLE_COLUMN_WIDTHS,
  PLAN_TABLE_ROW_NUMBER_WIDTH,
  type PlanTableRow,
} from './planTableViewModel'
import { usePlanTableZoom } from './usePlanTableZoom'
import './planTableExcel.css'

type Props = {
  project: Project | null
  tasks: TaskItem[]
  taskSubMap: Record<number, SubTaskItem[]>
  searchText?: string
  loading?: boolean
  exportDisabled?: boolean
  onExport?: () => void
  onOpenSubTask?: (subtask: SubTaskItem) => void
}

function displayText(value: string) {
  if ([EMPTY_PLAN_CELL, '未填写项目目标', '未填写评价标准', '暂无关键任务'].includes(value)) {
    return <span className="plan-table-placeholder">{value}</span>
  }
  return value
}

function headerClass(index: number): string {
  if (index === 0) return 'plan-table-column-header plan-table-sticky-objective'
  if (index === 1) return 'plan-table-column-header plan-table-sticky-task'
  return 'plan-table-column-header'
}

export function PlanTableView({
  project,
  tasks,
  taskSubMap,
  searchText = '',
  loading = false,
  exportDisabled = false,
  onExport,
  onOpenSubTask,
}: Props) {
  const workspaceRef = useRef<HTMLDivElement>(null)
  const [selectedSubTaskId, setSelectedSubTaskId] = useState<number | null>(null)
  const rows = useMemo(
    () => buildPlanRows({ project, tasks, taskSubMap, searchText }),
    [project, searchText, taskSubMap, tasks],
  )
  const {
    zoomPercent,
    setZoomPercent,
    zoomIn,
    zoomOut,
    fitWidth,
    resetView,
  } = usePlanTableZoom(workspaceRef)

  const handleResetView = () => {
    setSelectedSubTaskId(null)
    resetView()
  }

  const openKeyTask = (row: PlanTableRow) => {
    if (!row.subtask) return
    setSelectedSubTaskId(row.subtask.id)
    onOpenSubTask?.(row.subtask)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTableCellElement>, row: PlanTableRow) => {
    if (!row.subtask || (event.key !== 'Enter' && event.key !== ' ')) return
    event.preventDefault()
    openKeyTask(row)
  }

  const keyTaskCount = rows.filter((row) => row.subtask !== null).length
  const emptyTaskCount = rows.filter((row) => row.subtask === null).length
  const tableTitle = project?.name?.trim()
    ? `${project.name.trim()}目标与重点工作计划表`
    : '目标与重点工作计划表'
  const canvasStyle = {
    '--plan-table-zoom': zoomPercent / 100,
  } as CSSProperties

  return (
    <section className="plan-table-excel-view" aria-label="Excel 式工作推进表">
      <PlanTableToolbar
        zoomPercent={zoomPercent}
        onZoomOut={zoomOut}
        onZoomIn={zoomIn}
        onFitWidth={fitWidth}
        onResetView={handleResetView}
        onExport={() => onExport?.()}
        exportDisabled={exportDisabled || loading}
        exportLabel={loading || exportDisabled ? '关键任务加载中…' : '导出 Excel'}
      />

      <div ref={workspaceRef} className="plan-table-workspace" data-testid="plan-table-workspace">
        <div className="plan-table-canvas" style={canvasStyle} data-zoom-percent={zoomPercent}>
          <table className="plan-table-excel-grid">
            <colgroup>
              <col style={{ width: PLAN_TABLE_ROW_NUMBER_WIDTH }} />
              {PLAN_TABLE_COLUMN_WIDTHS.map((width, index) => <col key={`${PLAN_TABLE_BUSINESS_HEADERS[index]}-${width}`} style={{ width }} />)}
            </colgroup>
            <thead>
              <tr>
                <th colSpan={PLAN_TABLE_BUSINESS_HEADERS.length + 1} className="plan-table-title-cell">
                  {tableTitle}
                </th>
              </tr>
              <tr>
                <th className="plan-table-column-header plan-table-sticky-row-number" aria-label="行号">#</th>
                {PLAN_TABLE_BUSINESS_HEADERS.map((header, index) => (
                  <th key={header} className={headerClass(index)}>{header}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr className="plan-table-empty-row">
                  <td colSpan={PLAN_TABLE_BUSINESS_HEADERS.length + 1}>当前筛选条件下没有匹配的关键任务</td>
                </tr>
              ) : rows.map((row) => {
                const selected = row.subtask?.id === selectedSubTaskId
                return (
                  <tr key={`${row.task.id}-${row.subtask?.id ?? 'empty'}-${row.sequence}`}>
                    <td className="plan-table-row-number-cell plan-table-sticky-row-number">{row.sequence}</td>
                    {row.showObjective && (
                      <td rowSpan={row.objectiveRowSpan} className="plan-table-sticky-objective">
                        {displayText(row.objective)}
                      </td>
                    )}
                    {row.showTaskCells && (
                      <>
                        <td rowSpan={row.taskRowSpan} className="plan-table-task-name plan-table-sticky-task">
                          {displayText(row.task.key_task || EMPTY_PLAN_CELL)}
                        </td>
                        <td rowSpan={row.taskRowSpan}>
                          {displayText(row.task.completion_standard || row.task.key_achievement || '未填写评价标准')}
                        </td>
                      </>
                    )}
                    <td className="plan-table-row-number-cell">{row.sequence}</td>
                    <td
                      className={`plan-table-key-task-cell${selected ? ' plan-table-key-task-cell--selected' : ''}`}
                      role={row.subtask ? 'button' : undefined}
                      tabIndex={row.subtask ? 0 : undefined}
                      onClick={() => openKeyTask(row)}
                      onKeyDown={(event) => handleKeyDown(event, row)}
                    >
                      {displayText(row.keyTask)}
                    </td>
                    <td>{displayText(row.responsible)}</td>
                    <td>{displayText(row.planStart)}</td>
                    <td>{displayText(row.planEnd)}</td>
                    <td>{displayText(row.assistingPerson)}</td>
                    <td>
                      <div className="plan-table-completion">
                        <span className={`plan-table-status plan-table-status--${row.statusTone}`}>{row.status}</span>
                        {row.completionNote && <span className="plan-table-completion__note">{row.completionNote}</span>}
                      </div>
                    </td>
                    <td>{displayText(row.remarks)}</td>
                    {row.showTaskCells && (
                      <>
                        <td rowSpan={row.taskRowSpan}>{displayText(row.projectManager)}</td>
                        <td rowSpan={row.taskRowSpan}>{displayText(row.taskPlanStart)}</td>
                        <td rowSpan={row.taskRowSpan}>{displayText(row.taskPlanEnd)}</td>
                      </>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <PlanTableStatusBar
        keyTaskCount={keyTaskCount}
        emptyTaskCount={emptyTaskCount}
        zoomPercent={zoomPercent}
        onZoomChange={setZoomPercent}
        onZoomOut={zoomOut}
        onZoomIn={zoomIn}
        onResetView={handleResetView}
      />
    </section>
  )
}
