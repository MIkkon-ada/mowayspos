import { fetchSubTasks } from '../../api/subtasks'
import type { TaskReport, TaskReportAchievement, TaskReportProgress } from '../../api/updates'
import type { SubTaskItem } from '../../types'
import type { VoiceUpdateTaskReportsSectionProps } from './voiceUpdateResultTypes'

const STATUS_OPTIONS = ['未开始', '进行中', '延期', '已完成', '暂缓']

function lines(value: string): string[] {
  return value.split('\n').map((item) => item.trim()).filter(Boolean)
}

export function VoiceUpdateTaskReportsSection({
  phase,
  taskReports,
  setTaskReports,
  keyTaskIssues,
  setKeyTaskIssues,
  selectedSubtaskId,
  cardEdits,
  updateCardEdit,
  projectTasksForSuggest,
  voiceSubtasksContext,
}: VoiceUpdateTaskReportsSectionProps) {
  const primaryIndex = taskReports.findIndex((report) => report.type === 'progress' && report.matched_subtask_id === selectedSubtaskId)
  const primaryItem = primaryIndex >= 0 ? { report: taskReports[primaryIndex], index: primaryIndex } : null
  const otherItems = taskReports
    .map((report, index) => ({ report, index }))
    .filter(({ index }) => index !== primaryIndex)

  function updateReport(index: number, patch: Partial<TaskReportProgress> | Record<string, unknown>) {
    setTaskReports((previous) => previous.map((report, reportIndex) => reportIndex === index ? { ...report, ...patch } as TaskReport : report))
  }

  function updateAchievements(index: number, value: string) {
    const names = lines(value)
    setTaskReports((previous) => previous.map((report, reportIndex) => {
      if (reportIndex !== index) return report
      const existing = report.achievements ?? []
      const achievements: TaskReportAchievement[] = names.map((name, achievementIndex) => ({
        ...(existing[achievementIndex] ?? { achievement_type: '其他' }),
        name,
      }))
      return { ...report, achievements } as TaskReport
    }))
  }

  function renderOwnership(report: TaskReport, index: number) {
    const edit = cardEdits[index] ?? { taskId: null, subtaskId: null, subtasks: [] as SubTaskItem[], editorOpen: false, modified: false }
    const context = report.type === 'progress'
      ? voiceSubtasksContext.find((item) => item.id === report.matched_subtask_id)
      : null
    const taskName = edit.modified && edit.taskId
      ? projectTasksForSuggest.find((task) => task.id === edit.taskId)?.key_task
      : report.type === 'progress'
        ? report.parent_key_task || context?.parent_key_task
        : report.type === 'suggest_new_subtask'
          ? report.parent_key_task
          : ''
    const subtaskName = report.type === 'progress'
      ? (edit.modified && edit.subtaskId
          ? edit.subtasks.find((item) => item.id === edit.subtaskId)?.title
          : report.matched_subtask_title)
      : ''

    return (
      <div className="voice-update-report-ownership">
        <span>归属：{taskName || '未选择重点工作'}{subtaskName ? ` · ${subtaskName}` : ''}</span>
        <button
          type="button"
          onClick={async () => {
            const editorOpen = !edit.editorOpen
            updateCardEdit(index, { editorOpen })
            if (editorOpen && edit.taskId && report.type === 'progress' && edit.subtasks.length === 0) {
              const subtasks = await fetchSubTasks(edit.taskId).catch(() => [] as SubTaskItem[])
              updateCardEdit(index, { subtasks: subtasks.filter((item) => !item.is_deleted) })
            }
          }}
        >
          {edit.editorOpen ? '收起归属' : '修改归属'}
        </button>
        {edit.editorOpen && (
          <div className="voice-update-report-ownership-editor">
            <select
              value={edit.taskId ?? ''}
              onChange={async (event) => {
                const taskId = event.target.value ? Number(event.target.value) : null
                updateCardEdit(index, { taskId, subtaskId: null, subtasks: [], modified: true })
                if (taskId && report.type === 'progress') {
                  const subtasks = await fetchSubTasks(taskId).catch(() => [] as SubTaskItem[])
                  updateCardEdit(index, { taskId, subtasks: subtasks.filter((item) => !item.is_deleted), modified: true })
                }
              }}
            >
              <option value="">选择重点工作</option>
              {projectTasksForSuggest.map((task) => <option key={task.id} value={task.id}>{task.key_task}</option>)}
            </select>
            {report.type === 'progress' && (
              <select value={edit.subtaskId ?? ''} disabled={!edit.taskId} onChange={(event) => updateCardEdit(index, { subtaskId: event.target.value ? Number(event.target.value) : null, modified: true })}>
                <option value="">选择关键任务</option>
                {edit.subtasks.map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}
              </select>
            )}
          </div>
        )}
      </div>
    )
  }

  function renderReport(report: TaskReport, index: number, primary: boolean) {
    const progress = report.type === 'progress' ? report : null
    const title = progress?.matched_subtask_title || ('title' in report ? report.title : 'AI 识别项')
    const completed = report.completed == null ? '' : String(report.completed)
    const matchingKeyIssues = progress
      ? keyTaskIssues.map((issue, issueIndex) => ({ issue, issueIndex })).filter(({ issue }) => issue.key_task_title === progress.parent_key_task)
      : []

    return (
      <article key={index} className={`voice-update-report-card${primary ? ' is-primary' : ''}`}>
        <header>
          <div>
            <span>{progress ? (primary ? '本次汇报任务' : '其他进展') : report.type === 'suggest_new_subtask' ? '建议新增关键任务' : '新建关键任务'}</span>
            <h3>{title}</h3>
          </div>
          {progress?.status_update && <em>{progress.status_update}</em>}
        </header>
        {renderOwnership(report, index)}
        <div className="voice-update-progress-editor">
          <div className="voice-update-progress-field">
            <label>本次完成</label>
            <textarea value={completed} disabled={phase === 'submitted'} onChange={(event) => updateReport(index, { completed: event.target.value })} placeholder="本次具体完成了哪些工作？" />
          </div>
          <div className="voice-update-progress-field">
            <label>下一步计划</label>
            <textarea value={(report.next_steps ?? []).join('\n')} disabled={phase === 'submitted'} onChange={(event) => updateReport(index, { next_steps: lines(event.target.value) })} placeholder="每行填写一项下一步计划" />
          </div>
          <div className="voice-update-progress-field">
            <label>问题与风险</label>
            <textarea value={(report.subtask_issues ?? []).map((item) => typeof item === 'string' ? item : String((item as unknown as Record<string, unknown>).description ?? '')).join('\n')} disabled={phase === 'submitted'} onChange={(event) => updateReport(index, { subtask_issues: lines(event.target.value) })} placeholder="每行填写一个问题或风险，没有可留空" />
          </div>
          {matchingKeyIssues.map(({ issue, issueIndex }) => (
            <div className="voice-update-progress-field" key={`key-issue-${issueIndex}`}>
              <label>重点工作问题 · {issue.issue_type}</label>
              <textarea
                value={issue.description}
                disabled={phase === 'submitted'}
                onChange={(event) => setKeyTaskIssues((previous) => previous.map((item, currentIndex) => currentIndex === issueIndex ? { ...item, description: event.target.value } : item))}
              />
            </div>
          ))}
          <div className="voice-update-progress-field">
            <label>取得的成果</label>
            <textarea value={(report.achievements ?? []).map((item) => item.name).join('\n')} disabled={phase === 'submitted'} onChange={(event) => updateAchievements(index, event.target.value)} placeholder="每行填写一项成果" />
            {(report.achievements ?? []).map((achievement, achievementIndex) => (
              <input
                key={`${achievement.name}-${achievementIndex}`}
                value={achievement.file_link ?? ''}
                disabled={phase === 'submitted'}
                onChange={(event) => setTaskReports((previous) => previous.map((item, currentIndex) => currentIndex === index ? {
                  ...item,
                  achievements: item.achievements.map((entry, currentAchievementIndex) => currentAchievementIndex === achievementIndex ? { ...entry, file_link: event.target.value } : entry),
                } as TaskReport : item))}
                placeholder={`${achievement.name}的存储地址（可选）`}
              />
            ))}
          </div>
          {progress && (
            <div className="voice-update-progress-field">
              <label>任务状态建议</label>
              <select value={progress.status_update || '进行中'} disabled={phase === 'submitted'} onChange={(event) => updateReport(index, { status_update: event.target.value })}>
                {STATUS_OPTIONS.map((status) => <option key={status} value={status}>{status}</option>)}
              </select>
            </div>
          )}
        </div>
      </article>
    )
  }

  if (taskReports.length === 0) return null

  return (
    <div className="voice-update-task-reports">
      {primaryItem && renderReport(primaryItem.report, primaryItem.index, true)}
      {otherItems.length > 0 && <h3 className="voice-update-other-results-title">其他 AI 识别项</h3>}
      {otherItems.map(({ report, index }) => renderReport(report, index, false))}
    </div>
  )
}
