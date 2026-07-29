import { useMemo, useState } from 'react'
import type { KeyboardEvent } from 'react'
import type { Project, ProjectMember, SubTaskItem, TaskItem } from '../../types'
import {
  buildPlanRows,
  EMPTY_PLAN_CELL,
  getPlanStatusTone,
  type PlanTableRow,
} from './planTableViewModel'
import { fetchSubtaskDetail } from '../../api/subtasks'
import type { SubTaskDetail, SubTaskPayload } from '../../api/subtasks'
import './planTableExcelV2.css'

/** ── Props ── */
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
  projectMembers?: ProjectMember[]
  onUpdateSubTask?: (id: number, payload: Omit<SubTaskPayload, 'project_id'>) => Promise<SubTaskItem>
}

type EditLevel = 'full' | 'self' | 'none'

/** ── 权限判定 ── */
function getEditLevel(args: {
  isTechAdmin?: boolean
  projectRoles?: string[]
  currentUserName?: string
  subAssignee?: string
}): EditLevel {
  const { isTechAdmin, projectRoles, currentUserName, subAssignee } = args
  if (!currentUserName || !subAssignee) return 'none'
  if (isTechAdmin) return 'full'
  if (projectRoles?.some((r) => r === 'owner' || r === 'coordinator')) return 'full'
  if (currentUserName === subAssignee) return 'self'
  return 'none'
}

/** ── 格式化工具 ── */
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

function splitNumberedList(text: string): Array<{ num: string; content: string }> {
  const trimmed = text.trim()
  if (!trimmed) return []
  const segments = trimmed.split(/\s*\n+\s*|\s*[；;]\s*/).filter(Boolean)
  const items: Array<{ num: string; content: string }> = []
  for (const seg of segments) {
    const match = seg.match(/^(\d+[.、])\s*(.*)$/)
    if (match) {
      items.push({ num: match[1].replace(/[、]/, '.'), content: match[2].trim() })
    } else if (items.length > 0) {
      items[items.length - 1].content += '；' + seg.trim()
    } else {
      items.push({ num: '', content: seg.trim() })
    }
  }
  if (items.length === 0) items.push({ num: '', content: trimmed })
  return items
}

/* ──────────────────── 子组件 ──────────────────── */

/** 重点工作卡片 */
function TaskCard({
  task,
  onOpenStandard,
}: {
  task: TaskItem
  onOpenStandard: (task: TaskItem) => void
}) {
  const hasStandard = Boolean(task.completion_standard || task.key_achievement)
  return (
      <div
      className="v2-task-card"
      role="button"
      tabIndex={0}
      onClick={(e) => { e.stopPropagation(); onOpenStandard(task) }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpenStandard(task) }
      }}
    >
      <div className="v2-task-card__body">
        <div className="v2-task-card__title">{task.key_task || EMPTY_PLAN_CELL}</div>
        {hasStandard && (
          <button type="button" className="v2-task-card__std-btn" onClick={(e) => { e.stopPropagation(); onOpenStandard(task) }}>
            查看评价标准
          </button>
        )}
      </div>
    </div>
  )
}

/** 重点工作评价标准弹窗 */
function TaskStandardModal({
  task,
  onClose,
}: {
  task: TaskItem | null
  onClose: () => void
}) {
  if (!task) return null
  const standardText = task.completion_standard || task.key_achievement || '未填写评价标准'
  return (
    <div className="v2-modal-overlay" onClick={onClose}>
      <div className="v2-modal" onClick={(e) => e.stopPropagation()}>
        <div className="v2-modal__header">
          <h3 className="v2-modal__title">{task.key_task}</h3>
          <button type="button" className="v2-modal__close" onClick={onClose} aria-label="关闭">×</button>
        </div>
        <div className="v2-modal__body">
          <div className="v2-modal__section-title">评价标准</div>
          <StandardList text={standardText} />
        </div>
      </div>
    </div>
  )
}

/** 项目完成标准弹窗 */
function ProjectStandardModal({
  project,
  onClose,
}: {
  project: Project | null
  onClose: () => void
}) {
  if (!project) return null
  const objectives = project.objectives?.trim()
  if (!objectives) return null
  return (
    <div className="v2-modal-overlay" onClick={onClose}>
      <div className="v2-modal" onClick={(e) => e.stopPropagation()}>
        <div className="v2-modal__header">
          <h3 className="v2-modal__title">项目完成标准</h3>
          <button type="button" className="v2-modal__close" onClick={onClose} aria-label="关闭">×</button>
        </div>
        <div className="v2-modal__body">
          <StandardList text={objectives} />
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

/* ──────────────────── 关键任务编辑弹窗 ──────────────────── */

function SubTaskEditModal({
  subtask,
  detail,
  task,
  project,
  memberNames,
  editLevel,
  onClose,
  onSave,
}: {
  subtask: SubTaskItem
  detail: SubTaskDetail | null
  task?: TaskItem
  project?: Project | null
  memberNames: string[]
  editLevel: EditLevel
  onClose: () => void
  onSave: (id: number, payload: Omit<SubTaskPayload, 'project_id'>) => Promise<void>
}) {
  const [title, setTitle] = useState(subtask.title || '')
  const [assignee, setAssignee] = useState(subtask.assignee || '')
  const [planTime, setPlanTime] = useState(subtask.plan_time || '')
  const [status, setStatus] = useState(subtask.status || '未开始')
  const [notes, setNotes] = useState(subtask.notes || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const canEditAll = editLevel === 'full'
  const canEditAssignee = editLevel === 'full'
  const canEditBasics = editLevel === 'full' || editLevel === 'self'

  async function handleSubmit() {
    setError('')
    setSaving(true)
    try {
      // 校验计划时间：placeholder 文本或无法识别的格式存为空
      const rawPlanTime = planTime.trim()
      const isValidPlanTime = !rawPlanTime
        || rawPlanTime === '持续'
        || /[a-df-zA-DF-Z]/.test(rawPlanTime) // 含字母视为 placeholder
        || /\d{4}/.test(rawPlanTime) // 至少包含4位数字（年份）
        || /月/.test(rawPlanTime)   // 或含"月"
      await onSave(subtask.id, {
        title: title.trim() || subtask.title,
        assignee,
        plan_time: isValidPlanTime ? rawPlanTime : '',
        status,
        completion_criteria: subtask.completion_criteria || '',
        notes: notes.trim(),
      })
      onClose()
    } catch {
      setError('保存失败，请重试')
    } finally {
      setSaving(false)
    }
  }

  const progress = parseProgressTimeline(subtask.notes)
  const latestReport = useMemo(
    () => [...(detail?.work_reports ?? [])]
      .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''))[0],
    [detail],
  )
  const reportText = (items?: string[]) => items?.filter(Boolean).join('；') || '暂无'

  const infoSection = (
    <div className="v2-info-section">
      <div className="v2-info-section__grid">
        <div className="v2-info-item">
          <span className="v2-info-item__label">所属项目</span>
          <span className="v2-info-item__value">{project?.name || '—'}</span>
        </div>
        <div className="v2-info-item">
          <span className="v2-info-item__label">重点工作</span>
          <span className="v2-info-item__value">{task?.key_task || '—'}</span>
        </div>
        <div className="v2-info-item v2-info-item--full">
          <span className="v2-info-item__label">关键任务</span>
          <span className="v2-info-item__value v2-info-item__value--bold">{subtask.title || '—'}</span>
        </div>
        <div className="v2-info-item">
          <span className="v2-info-item__label">责任人</span>
          <span className="v2-info-item__value">{subtask.assignee || '—'}</span>
        </div>
        <div className="v2-info-item">
          <span className="v2-info-item__label">计划时间</span>
          <span className="v2-info-item__value">{subtask.plan_time || '—'}</span>
        </div>
        <div className="v2-info-item">
          <span className="v2-info-item__label">当前状态</span>
          <span className={`v2-info-item__value v2-status ${statusClass(getPlanStatusTone(subtask.status))}`}>{subtask.status || '—'}</span>
        </div>
      </div>

      {subtask.completion_criteria && (
        <div className="v2-info-block">
          <span className="v2-info-block__label">完成标准</span>
          <div className="v2-info-block__content">{subtask.completion_criteria}</div>
        </div>
      )}

      <div className="v2-info-block">
        <span className="v2-info-block__label">最新进展</span>
        {progress.length > 0 ? (
          <ul className="v2-progress-list">
            {progress.map((p, idx) => (
              <li key={idx} className="v2-progress-list__item">
                {p.date && <span className="v2-progress-list__date">{p.date}</span>}
                <span className="v2-progress-list__text">{p.text}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="v2-info-block__content v2-info-block__content--empty">暂无进展记录</div>
        )}
      </div>
    </div>
  )

  if (!canEditBasics) {
    return (
      <div className="v2-modal-overlay" onClick={onClose}>
        <div className="v2-modal v2-modal--readonly" onClick={(e) => e.stopPropagation()}>
          <div className="v2-modal__header">
            <h3 className="v2-modal__title">关键任务详情</h3>
            <button type="button" className="v2-modal__close" onClick={onClose} aria-label="关闭">×</button>
          </div>
          <div className="v2-modal__body">
            {infoSection}
            <p className="v2-edit-form__readonly-hint">你无权编辑此关键任务，仅能查看。</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="v2-modal-overlay" onClick={onClose}>
      <div className="v2-modal v2-modal--edit" onClick={(e) => e.stopPropagation()}>
        <div className="v2-modal__header">
          <div className="v2-edit-form__context">
            <h3 className="v2-modal__title">关键任务详情</h3>
            <p>{project?.name || '—'} · {task?.key_task || '—'}</p>
          </div>
          <div className="v2-modal__header-tags">
            <span className={`v2-status ${statusClass(getPlanStatusTone(status))}`}>{status || '未开始'}</span>
            {canEditAll && <span className="v2-tag v2-tag--full">全部权限</span>}
            {editLevel === 'self' && <span className="v2-tag v2-tag--self">责任人</span>}
          </div>
          <button type="button" className="v2-modal__close" onClick={onClose} aria-label="关闭">×</button>
        </div>
        <div className="v2-modal__body">
          <div className="v2-edit-form v2-edit-form--compact">
            <label className="v2-edit-form__label">
              关键任务名称
              <input
                className="v2-edit-form__input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={!canEditBasics || saving}
                placeholder="请输入关键任务名称"
              />
            </label>

            <div className="v2-edit-form__grid">
              <label className="v2-edit-form__label">
                责任人
                {canEditAssignee ? (
                  <select
                    className="v2-edit-form__select"
                    value={assignee}
                    onChange={(e) => setAssignee(e.target.value)}
                    disabled={saving}
                  >
                    <option value="">— 请选择 —</option>
                    {memberNames.map((name) => (
                      <option key={name} value={name}>{name}</option>
                    ))}
                  </select>
                ) : (
                  <div className="v2-edit-form__locked">
                    <input
                      className="v2-edit-form__input v2-edit-form__input--disabled"
                      value={assignee}
                      disabled
                    />
                    <span className="v2-edit-form__lock-hint">仅负责人可修改</span>
                  </div>
                )}
              </label>

              <label className="v2-edit-form__label">
                协同人 / 备注
                <input
                  className="v2-edit-form__input"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  disabled={!canEditBasics || saving}
                  placeholder="协同人姓名，多个用、分隔"
                />
              </label>

              <label className="v2-edit-form__label">
                计划时间
                <input
                  className="v2-edit-form__input"
                  value={planTime}
                  onChange={(e) => setPlanTime(e.target.value)}
                  disabled={!canEditBasics || saving}
                  placeholder="yyyy-mm-dd ~ yyyy-mm-dd"
                />
              </label>

              <label className="v2-edit-form__label">
                当前状态
                <select
                  className="v2-edit-form__select"
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  disabled={!canEditBasics || saving}
                >
                  <option value="未开始">未开始</option>
                  <option value="进行中">进行中</option>
                  <option value="已完成">已完成</option>
                  <option value="已暂停">已暂停</option>
                </select>
              </label>
            </div>

            {latestReport && (
              <section className="v2-edit-form__latest-progress" aria-label="最新进度">
                <div className="v2-edit-form__latest-progress-header">
                  <strong>最新进度</strong>
                  <span>
                    {latestReport.created_at?.replace('T', ' ').slice(0, 16) || '暂无汇报时间'}
                    {latestReport.submitter ? ` · ${latestReport.submitter}` : ''}
                  </span>
                </div>
                <p className="v2-edit-form__latest-progress-line"><b>已完成：</b>{reportText(latestReport.completed_items)}</p>
                <p className="v2-edit-form__latest-progress-line v2-edit-form__latest-progress-line--next"><b>下一步：</b>{reportText(latestReport.next_steps)}</p>
              </section>
            )}

            {error && <p className="v2-edit-form__error">{error}</p>}
          </div>
        </div>

        <div className="v2-modal__footer">
          <span>修改将同步到工作推进表</span>
          <div className="v2-edit-form__actions">
            <button type="button" className="v2-btn v2-btn--cancel" onClick={onClose} disabled={saving}>
              取消
            </button>
            <button
              type="button"
              className="v2-btn v2-btn--primary"
              onClick={handleSubmit}
              disabled={saving || !title.trim()}
            >
              {saving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ──────────────────── 主组件 ──────────────────── */

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
  currentUserName,
  projectRoles,
  isTechAdmin,
  projectMembers,
  onUpdateSubTask,
}: Props) {
  const [selectedSubTaskId, setSelectedSubTaskId] = useState<number | null>(null)
  const [showProjectStandard, setShowProjectStandard] = useState(false)
  const [standardTask, setStandardTask] = useState<TaskItem | null>(null)
  const [editingSubTask, setEditingSubTask] = useState<SubTaskItem | null>(null)
  const [editingSubTaskDetail, setEditingSubTaskDetail] = useState<SubTaskDetail | null>(null)

  const rows = useMemo(
    () => buildPlanRows({ project, tasks, taskSubMap, searchText }),
    [project, searchText, taskSubMap, tasks],
  )

  const memberNames = useMemo(
    () => {
      const names = new Set((projectMembers ?? []).map((m) => m.person_name_snapshot).filter(Boolean))
      // 从重点工作 owner 和关键任务 assignee 中补充可选责任人
      tasks.forEach((t) => { if (t.owner?.trim()) names.add(t.owner.trim()) })
      Object.values(taskSubMap).flat().forEach((s) => { if (s.assignee?.trim()) names.add(s.assignee.trim()) })
      return [...names]
    },
    [projectMembers, tasks, taskSubMap],
  )

  /** 点击关键任务行 → 弹出编辑弹窗 */
  const openKeyTask = (row: PlanTableRow) => {
    if (!row.subtask) return
    setSelectedSubTaskId(row.subtask.id)
    setEditingSubTask(row.subtask)
    setEditingSubTaskDetail(null)
    void fetchSubtaskDetail(row.subtask.id)
      .then(setEditingSubTaskDetail)
      .catch(() => setEditingSubTaskDetail(null))
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>, row: PlanTableRow) => {
    if (!row.subtask || (event.key !== 'Enter' && event.key !== ' ')) return
    event.preventDefault()
    openKeyTask(row)
  }

  async function handleEditSave(id: number, payload: Omit<SubTaskPayload, 'project_id'>) {
    if (!onUpdateSubTask) return
    await onUpdateSubTask(id, payload)
    setEditingSubTask(null)
    setEditingSubTaskDetail(null)
  }

  if (loading) {
    return <div className="h-40 flex items-center justify-center text-slate-400 text-sm">加载中...</div>
  }

  return (
    <section className="v2-plan-view" aria-label="工作推进表">
      <div className="v2-table-actions">
        <div className="v2-table-actions__project">
          <span className="v2-table-actions__label">项目：</span>
          <span className="v2-table-actions__name">{project?.name || '未选择项目'}</span>
        </div>
        <div className="v2-table-actions__buttons">
          <button type="button" className="v2-project-banner__toggle" onClick={() => setShowProjectStandard(true)}>
            评价标准
          </button>
          {canCreateTask && onCreateTask && (
            <button type="button" className="v2-project-banner__create" onClick={onCreateTask}>
              新增重点工作
            </button>
          )}
        </div>
      </div>

      {/* 表格主体 */}
      <div className="v2-table-scroll">
        <div className="v2-table-canvas v2-sheet-frame">
          <table className="v2-grid">
            <colgroup>
              <col style={{ width: 300 }} />
              <col style={{ width: 430 }} />
              <col style={{ width: 80 }} />
              <col style={{ width: 130 }} />
              <col style={{ width: 155 }} />
              <col style={{ width: 85 }} />
            </colgroup>
            <thead>
              <tr>
                <th className="v2-th v2-th--sticky-task">重点工作</th>
                <th className="v2-th">关键任务</th>
                <th className="v2-th">负责人</th>
                <th className="v2-th">计划时间</th>
                <th className="v2-th">协同人</th>
                <th className="v2-th">状态</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr className="v2-empty-row">
                  <td colSpan={6}>当前筛选条件下没有匹配的关键任务</td>
                </tr>
              ) : (
                rows.map((row) => {
                  const selected = row.subtask?.id === selectedSubTaskId
                      const planTime = formatPlanTime(row.planStart, row.planEnd)
                          const canClick = row.subtask !== null
                      return (
                    <tr
                      key={`${row.task.id}-${row.subtask?.id ?? 'empty'}-${row.sequence}`}
                      className={`${selected ? 'v2-tr--selected' : ''}${canClick ? ' v2-tr--clickable' : ''}`}
                      role={canClick ? 'button' : undefined}
                      tabIndex={canClick ? 0 : undefined}
                      onClick={canClick ? () => openKeyTask(row) : undefined}
                      onKeyDown={canClick ? (e) => handleKeyDown(e, row) : undefined}
                    >
                      {row.showTaskCells && (
                        <td
                          rowSpan={row.taskRowSpan}
                          className="v2-td v2-td--task v2-td--sticky-task v2-td--task-card"
                        >
                              <TaskCard
                                task={row.task}
                                onOpenStandard={setStandardTask}
                              />
                        </td>
                      )}

                      {/* 关键任务 */}
                      <td
                        className={`v2-td v2-td--keytask${selected ? ' v2-td--selected' : ''}`}
                      >
                            {canClick ? (
                              <span className="v2-keytask-line">
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

      {/* 弹窗 */}
      <TaskStandardModal task={standardTask} onClose={() => setStandardTask(null)} />
      {showProjectStandard && (
        <ProjectStandardModal project={project} onClose={() => setShowProjectStandard(false)} />
      )}
      {editingSubTask && (
          <SubTaskEditModal
            subtask={editingSubTask}
            detail={editingSubTaskDetail}
          task={rows.find((r) => r.task.id === editingSubTask.task_id)?.task}
          project={project}
          memberNames={memberNames}
          editLevel={getEditLevel({
            isTechAdmin,
            projectRoles,
            currentUserName,
            subAssignee: editingSubTask.assignee,
          })}
          onClose={() => {
            setEditingSubTask(null)
            setEditingSubTaskDetail(null)
          }}
          onSave={handleEditSave}
        />
          )}

    </section>
  )
}

function parseProgressTimeline(notes?: string | null): { date: string; text: string }[] {
  if (!notes?.trim()) return []
  const lines = notes.split('\n').filter(Boolean)
  const entries: { date: string; text: string[] }[] = []
  for (const line of lines) {
    const m = line.match(/^\[(\d{4}-\d{2}-\d{2})\]\s*(.*)/)
    if (m) {
      entries.push({ date: m[1], text: [m[2].trim()] })
    } else if (entries.length > 0) {
      entries[entries.length - 1].text.push(line.trim())
    } else {
      entries.push({ date: '', text: [line.trim()] })
    }
  }
  return entries.map((e) => ({ date: e.date, text: e.text.filter(Boolean).join(' ') }))
}
