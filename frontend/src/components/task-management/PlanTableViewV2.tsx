import { useMemo, useState } from 'react'
import type { KeyboardEvent } from 'react'
import type { Project, SubTaskItem, TaskItem } from '../../types'
import {
  buildPlanRows,
  EMPTY_PLAN_CELL,
  getPlanStatusLabel,
  type PlanTableRow,
} from './planTableViewModel'

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

/** 合并计划时间为紧凑格式 */
function formatPlanTime(start: string, end: string): string {
  if (start === EMPTY_PLAN_CELL && end === EMPTY_PLAN_CELL) return EMPTY_PLAN_CELL
  if (start === '持续') return '持续'
  if (end === EMPTY_PLAN_CELL) return start
  if (start === end) return start
  return `${start} ~ ${end}`
}

function statusClass(tone: PlanTableRow['statusTone']): string {
  const map: Record<string, string> = {
    neutral: 'v2-status--neutral',
    blue: 'v2-status--blue',
    green: 'v2-status--green',
    red: 'v2-status--red',
    amber: 'v2-status--amber',
  }
  return map[tone] ?? 'v2-status--neutral'
}

function cellText(value: string) {
  if ([EMPTY_PLAN_CELL, '未填写项目目标', '未填写评价标准', '暂无关键任务'].includes(value)) {
    return <span className="v2-cell-placeholder">{value}</span>
  }
  return value
}

/** 把 "1.xxx；2.yyy" 或 "1.xxx\n2.yyy" 拆分为编号列表 */
function splitNumberedList(text: string): Array<{ num: string; content: string }> {
  const trimmed = text.trim()
  if (!trimmed) return []

  // 先按换行或中文/英文分号拆成片段
  const segments = trimmed.split(/\s*\n+\s*|\s*[；;]\s*/).filter(Boolean)
  const items: Array<{ num: string; content: string }> = []

  for (const seg of segments) {
    const match = seg.match(/^(\d+[\.、])\s*(.*)$/)
    if (match) {
      items.push({ num: match[1].replace(/[、]/, '.'), content: match[2].trim() })
    } else if (items.length > 0) {
      // 没有编号，追加到上一项
      items[items.length - 1].content += '；' + seg.trim()
    } else {
      items.push({ num: '', content: seg.trim() })
    }
  }

  if (items.length === 0) {
    items.push({ num: '', content: trimmed })
  }
  return items
}

function countStatus(subtasks: SubTaskItem[], status: string): number {
  return subtasks.filter((s) => getPlanStatusLabel(s.status) === status).length
}

function TaskCard({
  task,
  subtasks,
  index,
}: {
  task: TaskItem
  subtasks: SubTaskItem[]
  index: number
}) {
  const total = subtasks.length || 1
  const completed = countStatus(subtasks, '已完成')
  const inProgress = countStatus(subtasks, '进行中')
  const progress = Math.round((completed / total) * 100)

  return (
    <div className="v2-task-card">
      <div className="v2-task-card__index">{String(index + 1).padStart(2, '0')}</div>
      <div className="v2-task-card__body">
        <div className="v2-task-card__title">{task.key_task || EMPTY_PLAN_CELL}</div>
        <div className="v2-task-card__meta">
          {total} 项关键任务 · {completed} 完成 · {inProgress} 进行中
        </div>
        <div className="v2-task-card__progress">
          <div className="v2-task-card__progress-track">
            <div
              className="v2-task-card__progress-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

function StandardList({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false)
  const items = useMemo(() => splitNumberedList(text), [text])
  const hasMany = items.length > 3
  const visibleItems = expanded || !hasMany ? items : items.slice(0, 3)
  return (
    <ul className="v2-std-list">
      {visibleItems.map((item, i) => (
        <li key={i} className="v2-std-list__item">
          {item.num && <span className="v2-std-list__num">{item.num}</span>}
          <span className="v2-std-list__text">{item.content}</span>
        </li>
      ))}
      {hasMany && (
        <li className="v2-std-list__more">
          <button type="button" onClick={() => setExpanded((v) => !v)}>
            {expanded ? '收起' : '查看全部'}
          </button>
        </li>
      )}
    </ul>
  )
}

export function PlanTableViewV2({
  project,
  tasks,
  taskSubMap,
  searchText = '',
  loading = false,
  exportDisabled = false,
  onExport,
  onOpenSubTask,
}: Props) {
  const [selectedSubTaskId, setSelectedSubTaskId] = useState<number | null>(null)
  const [objectiveExpanded, setObjectiveExpanded] = useState(false)

  const rows = useMemo(
    () => buildPlanRows({ project, tasks, taskSubMap, searchText }),
    [project, searchText, taskSubMap, tasks],
  )

  const objective = project?.objectives?.trim() || project?.description?.trim() || ''
  const objectiveLines = useMemo(() => splitNumberedList(objective), [objective])
  // 摘要只取第一条目标，并去掉括号内的指标说明和末尾标点，保持简洁
  const objectiveSummary = (objectiveLines[0]?.content || objective)
    .split(/[【\[(]/)[0]
    .trim()
    .replace(/[;；。，,]+$/, '')
  const projectManagers = project?.owners?.filter(Boolean).join('、') || ''

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

  const keyTaskCount = rows.filter((r) => r.subtask !== null).length
  const emptyTaskCount = rows.filter((r) => r.subtask === null).length

  const completedCount = rows.filter((r) => r.subtask && getPlanStatusLabel(r.subtask.status) === '已完成').length
  const inProgressCount = rows.filter((r) => r.subtask && getPlanStatusLabel(r.subtask.status) === '进行中').length
  const notStartedCount = rows.filter((r) => r.subtask && getPlanStatusLabel(r.subtask.status) === '未开始').length
  const delayedCount = rows.filter((r) => r.subtask && getPlanStatusLabel(r.subtask.status) === '延期').length

  const taskIndexMap = useMemo(() => {
    const map = new Map<number, number>()
    let idx = 0
    for (const row of rows) {
      if (row.showTaskCells) {
        map.set(row.task.id, idx++)
      }
    }
    return map
  }, [rows])

  if (loading) {
    return <div className="h-40 flex items-center justify-center text-slate-400 text-sm">加载中...</div>
  }

  return (
    <section className="v2-plan-view" aria-label="工作推进表">
      {/* 项目目标 banner */}
      {objective && (
        <div className="v2-objective-banner">
          <div className="v2-objective-banner__left">
            <span className="v2-objective-banner__label">项目目标</span>
            <span className="v2-objective-banner__summary">
              {objectiveExpanded
                ? objectiveLines.map((l) => l.num + l.content).join('；')
                : objectiveSummary}
            </span>
          </div>
          <div className="v2-objective-banner__right">
            <span className="v2-objective-banner__stats">
              {keyTaskCount} 项任务 · {completedCount} 已完成 · {inProgressCount} 进行中
            </span>
            <button
              type="button"
              className="v2-objective-banner__toggle"
              onClick={() => setObjectiveExpanded((v) => !v)}
            >
              {objectiveExpanded ? '收起' : '展开'}
              <svg
                className={`v2-objective-banner__arrow${objectiveExpanded ? ' v2-objective-banner__arrow--up' : ''}`}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
            {projectManagers && (
              <span className="v2-objective-banner__pm">项目经理：{projectManagers}</span>
            )}
          </div>
        </div>
      )}

      {/* 表格主体 */}
      <div className="v2-table-scroll">
        <div className="v2-table-canvas">
          <table className="v2-grid">
            <colgroup>
              <col style={{ width: 52 }} />
              <col style={{ width: 280 }} />
              <col style={{ width: 260 }} />
              <col style={{ width: 240 }} />
              <col style={{ width: 90 }} />
              <col style={{ width: 120 }} />
              <col style={{ width: 120 }} />
              <col style={{ width: 90 }} />
            </colgroup>
            <thead>
              <tr>
                <th className="v2-th v2-th--sticky-num">#</th>
                <th className="v2-th v2-th--sticky-task">重点工作</th>
                <th className="v2-th v2-th--sticky-std">评价标准</th>
                <th className="v2-th">关键任务</th>
                <th className="v2-th">责任人</th>
                <th className="v2-th">计划时间</th>
                <th className="v2-th">协同人</th>
                <th className="v2-th">状态</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr className="v2-empty-row">
                  <td colSpan={8}>当前筛选条件下没有匹配的关键任务</td>
                </tr>
              ) : (
                rows.map((row) => {
                  const selected = row.subtask?.id === selectedSubTaskId
                  const planTime = formatPlanTime(row.planStart, row.planEnd)
                  const taskIdx = taskIndexMap.get(row.task.id) ?? 0
                  const subtasks = taskSubMap[row.task.id] ?? []
                  return (
                    <tr
                      key={`${row.task.id}-${row.subtask?.id ?? 'empty'}-${row.sequence}`}
                      className={selected ? 'v2-tr--selected' : ''}
                    >
                      {/* 序号 */}
                      <td className="v2-td v2-td--num v2-td--sticky-num">{row.sequence}</td>

                      {/* 重点工作 — task 级，rowSpan 合并 */}
                      {row.showTaskCells && (
                        <td
                          rowSpan={row.taskRowSpan}
                          className="v2-td v2-td--task v2-td--sticky-task v2-td--task-card"
                        >
                          <TaskCard task={row.task} subtasks={subtasks} index={taskIdx} />
                        </td>
                      )}

                      {/* 评价标准 — task 级，rowSpan 合并 */}
                      {row.showTaskCells && (
                        <td
                          rowSpan={row.taskRowSpan}
                          className="v2-td v2-td--std v2-td--sticky-std"
                        >
                          <StandardList text={row.task.completion_standard || row.task.key_achievement || '未填写评价标准'} />
                        </td>
                      )}

                      {/* 关键任务 — subtask 级，每行一个 */}
                      <td
                        className={`v2-td v2-td--keytask${selected ? ' v2-td--selected' : ''}`}
                        role={row.subtask ? 'button' : undefined}
                        tabIndex={row.subtask ? 0 : undefined}
                        onClick={() => openKeyTask(row)}
                        onKeyDown={(e) => handleKeyDown(e, row)}
                      >
                        {row.subtask ? (
                          <span className="v2-keytask-line">
                            <span className="v2-keytask-line__num">{row.subtaskIndex}.</span>
                            <span className="v2-keytask-line__text">{row.keyTask}</span>
                          </span>
                        ) : (
                          <span className="v2-cell-placeholder">{cellText(row.keyTask)}</span>
                        )}
                      </td>

                      {/* 责任人 */}
                      <td className="v2-td v2-td--person">{cellText(row.responsible)}</td>

                      {/* 计划时间 */}
                      <td className="v2-td v2-td--time">{cellText(planTime)}</td>

                      {/* 协同人 */}
                      <td className="v2-td v2-td--person">{cellText(row.assistingPerson)}</td>

                      {/* 状态 */}
                      <td className="v2-td v2-td--status">
                        <span className={`v2-status ${statusClass(row.statusTone)}`}>
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 底部统计栏 */}
      <div className="v2-footer-stats">
        <div className="v2-footer-stats__left">
          <span>共 {tasks.length} 项重点工作 · {keyTaskCount} 项关键任务</span>
          {emptyTaskCount > 0 && <span>{emptyTaskCount} 个重点工作暂无关键任务</span>}
        </div>
        <div className="v2-footer-stats__right">
          {onExport && (
            <button
              type="button"
              className="v2-export-btn"
              disabled={exportDisabled}
              onClick={onExport}
              title="导出 Excel"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              <span>导出</span>
            </button>
          )}
          <span className="v2-footer-stat v2-footer-stat--completed">{completedCount} 已完成</span>
          <span className="v2-footer-stat v2-footer-stat--inprogress">{inProgressCount} 进行中</span>
          <span className="v2-footer-stat v2-footer-stat--notstarted">{notStartedCount} 未开始</span>
          <span className="v2-footer-stat v2-footer-stat--delayed">{delayedCount} 逾期</span>
        </div>
      </div>
    </section>
  )
}
