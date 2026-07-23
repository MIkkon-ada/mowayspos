import { useState } from 'react'
import { fetchSubTasks } from '../../api/subtasks'
import type { TaskReport, TaskReportAchievement, TaskReportProgress } from '../../api/updates'
import type { SubTaskItem } from '../../types'
import type { VoiceUpdateTaskReportsSectionProps } from './voiceUpdateResultTypes'

const STATUS_OPTIONS = ['未开始', '进行中', '延期', '已完成', '暂缓']
const MATCH_LABELS = { matched: '已匹配归属', needs_confirmation: '需要确认归属', unmatched: '无法匹配' } as const

function lines(value: string): string[] {
  return value.split('\n').map((item) => item.trim()).filter(Boolean)
}

export function VoiceUpdateTaskReportsSection({
  phase,
  taskReports,
  setTaskReports,
  keyTaskIssues,
  setKeyTaskIssues,
  cardEdits,
  updateCardEdit,
  projectTasksForSuggest,
  voiceSubtasksContext,
}: VoiceUpdateTaskReportsSectionProps) {
  const [activeReportIndex, setActiveReportIndex] = useState(0)
  const safeActiveIndex = Math.min(activeReportIndex, Math.max(taskReports.length - 1, 0))
  const activeItem = taskReports[safeActiveIndex]
    ? { report: taskReports[safeActiveIndex], index: safeActiveIndex }
    : null

  function updateReport(index: number, patch: Partial<TaskReportProgress> | Record<string, unknown>) {
    setTaskReports((previous) => previous.map((report, reportIndex) => reportIndex === index ? { ...report, ...patch } as TaskReport : report))
  }

  function applyOwnership(index: number, candidateId: number | null, candidates: typeof voiceSubtasksContext) {
    const selected = candidates.find((item) => (item.subtask_id ?? item.id) === candidateId)
    updateReport(index, selected ? {
      matched_subtask_id: candidateId,
      matched_subtask_title: selected.subtask_title || selected.title,
      parent_task_id: selected.parent_task_id ?? null,
      parent_key_task: selected.parent_key_task,
      project_id: selected.project_id ?? selected.parent_project_id ?? null,
      project_name: selected.project_name || '',
      match_status: 'matched',
      match_reason: '用户手动确认归属',
      match_confidence: 1,
    } : { matched_subtask_id: null })
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

  function renderReport(report: TaskReport, index: number) {
    const progress = report.type === 'progress' ? report : null
    const completed = report.completed == null ? '' : String(report.completed)
    const matchingKeyIssues = progress
      ? keyTaskIssues.map((issue, issueIndex) => ({ issue, issueIndex })).filter(({ issue }) => issue.key_task_title === progress.parent_key_task)
      : []
    const ownershipCandidates = progress?.match_candidates?.length ? progress.match_candidates : voiceSubtasksContext

    return (
      <article key={index} className="voice-update-report-card is-primary">
        {!progress && renderOwnership(report, index)}
        {progress?.match_status && (
          <section className={`voice-update-agent-match is-${progress.match_status}`}>
            <div className="voice-update-agent-match-heading">
              <strong>{MATCH_LABELS[progress.match_status]}</strong>
              {progress.match_status === 'matched' && (
                <button type="button" onClick={() => updateCardEdit(index, { editorOpen: !(cardEdits[index]?.editorOpen ?? false) })}>
                  {cardEdits[index]?.editorOpen ? '收起修改' : '修改归属'}
                </button>
              )}
            </div>
            <span>{progress.project_name || '—'} &gt; {progress.parent_key_task || '—'} &gt; {progress.matched_subtask_title || '—'}</span>
            <small>{progress.match_reason || ''}</small>
            <div><b>原文证据</b>{(progress.evidence ?? []).map((item) => <q key={item}>{item}</q>)}</div>
            {progress.match_status === 'matched' && cardEdits[index]?.editorOpen && (
              <label>
                重新选择归属
                <select value={progress.matched_subtask_id ?? ''} onChange={(event) => applyOwnership(index, event.target.value ? Number(event.target.value) : null, voiceSubtasksContext)}>
                  <option value="">请选择项目、重点工作与关键任务</option>
                  {voiceSubtasksContext.map((item) => <option key={item.subtask_id ?? item.id} value={item.subtask_id ?? item.id}>{item.project_name || '—'} &gt; {item.parent_key_task || '—'} &gt; {item.subtask_title || item.title}</option>)}
                </select>
              </label>
            )}
            {progress.match_status === 'needs_confirmation' && (
              <label>
                选择候选归属
                <select value={progress.matched_subtask_id ?? ''} onChange={(event) => {
                  applyOwnership(index, event.target.value ? Number(event.target.value) : null, ownershipCandidates)
                }}>
                  <option value="">请选择候选任务，不会自动选中</option>
                  {ownershipCandidates.map((item) => <option key={item.subtask_id ?? item.id} value={item.subtask_id ?? item.id}>{item.project_name || '—'} &gt; {item.parent_key_task || '—'} &gt; {item.subtask_title || item.title}</option>)}
                </select>
              </label>
            )}
            {progress.match_status === 'unmatched' && (() => {
              const projectCandidates = voiceSubtasksContext.filter((item, candidateIndex, all) => all.findIndex((candidate) => (candidate.project_id ?? candidate.parent_project_id) === (item.project_id ?? item.parent_project_id)) === candidateIndex)
              const workstreamCandidates = voiceSubtasksContext.filter((item) => (item.project_id ?? item.parent_project_id) === progress.project_id).filter((item, candidateIndex, all) => all.findIndex((candidate) => candidate.parent_task_id === item.parent_task_id) === candidateIndex)
              const subtaskCandidates = voiceSubtasksContext.filter((item) => (item.project_id ?? item.parent_project_id) === progress.project_id && item.parent_task_id === progress.parent_task_id)
              return (
                <div className="voice-update-unmatched-ownership" aria-label="手动确认任务归属">
                  <label>选择项目<select value={progress.project_id ?? ''} onChange={(event) => {
                    const projectId = event.target.value ? Number(event.target.value) : null
                    const selected = projectCandidates.find((item) => (item.project_id ?? item.parent_project_id) === projectId)
                    updateReport(index, { project_id: projectId, project_name: selected?.project_name || '', parent_task_id: null, parent_key_task: '', matched_subtask_id: null, matched_subtask_title: '' })
                  }}><option value="">请选择项目</option>{projectCandidates.map((item) => <option key={item.project_id ?? item.parent_project_id} value={item.project_id ?? item.parent_project_id ?? ''}>{item.project_name || '—'}</option>)}</select></label>
                  <label>选择重点工作<select value={progress.parent_task_id ?? ''} disabled={!progress.project_id} onChange={(event) => {
                    const parentTaskId = event.target.value ? Number(event.target.value) : null
                    const selected = workstreamCandidates.find((item) => item.parent_task_id === parentTaskId)
                    updateReport(index, { parent_task_id: parentTaskId, parent_key_task: selected?.parent_key_task || '', matched_subtask_id: null, matched_subtask_title: '' })
                  }}><option value="">请选择重点工作</option>{workstreamCandidates.map((item) => <option key={item.parent_task_id} value={item.parent_task_id ?? ''}>{item.parent_key_task || '—'}</option>)}</select></label>
                  <label>选择关键任务<select value={progress.matched_subtask_id ?? ''} disabled={!progress.parent_task_id} onChange={(event) => applyOwnership(index, event.target.value ? Number(event.target.value) : null, subtaskCandidates)}><option value="">请选择关键任务</option>{subtaskCandidates.map((item) => <option key={item.subtask_id ?? item.id} value={item.subtask_id ?? item.id}>{item.subtask_title || item.title}</option>)}</select></label>
                </div>
              )
            })()}
          </section>
        )}
        <div className="voice-update-progress-editor">
          <div className="voice-update-progress-field">
            <label className="voice-update-field-label"><span className="is-complete">✓</span>本次完成</label>
            <div className="voice-update-field-control">
              <textarea value={completed} disabled={phase === 'submitted'} onChange={(event) => updateReport(index, { completed: event.target.value })} placeholder="本次具体完成了哪些工作？" />
              <span>{completed.length}/1000</span>
            </div>
          </div>
          <div className="voice-update-progress-field">
            <label className="voice-update-field-label"><span className="is-next">→</span>下一步计划</label>
            <div className="voice-update-field-control">
              <textarea value={(report.next_steps ?? []).join('\n')} disabled={phase === 'submitted'} onChange={(event) => updateReport(index, { next_steps: lines(event.target.value) })} placeholder="每行填写一项下一步计划" />
              <span>{(report.next_steps ?? []).join('\n').length}/1000</span>
            </div>
          </div>
          <div className="voice-update-progress-field">
            <label className="voice-update-field-label"><span className="is-risk">!</span>问题与风险</label>
            <div className="voice-update-field-control">
              <textarea value={(report.subtask_issues ?? []).map((item) => typeof item === 'string' ? item : String((item as unknown as Record<string, unknown>).description ?? '')).join('\n')} disabled={phase === 'submitted'} onChange={(event) => updateReport(index, { subtask_issues: lines(event.target.value) })} placeholder="每行填写一个问题或风险，没有可留空" />
              <span>{(report.subtask_issues ?? []).map((item) => typeof item === 'string' ? item : String((item as unknown as Record<string, unknown>).description ?? '')).join('\n').length}/1000</span>
            </div>
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
            <label className="voice-update-field-label"><span className="is-achievement">★</span>取得的成果</label>
            <div className="voice-update-field-control">
              <textarea value={(report.achievements ?? []).map((item) => item.name).join('\n')} disabled={phase === 'submitted'} onChange={(event) => updateAchievements(index, event.target.value)} placeholder="每行填写一项成果" />
              <span>{(report.achievements ?? []).map((item) => item.name).join('\n').length}/1000</span>
            </div>
          </div>
          {progress && (
            <div className="voice-update-progress-field">
              <label className="voice-update-field-label"><span className="is-status">⚑</span>任务状态建议</label>
              <div className="voice-update-status-options" role="radiogroup" aria-label="任务状态建议">
                {STATUS_OPTIONS.map((status) => (
                  <label key={status}>
                    <input
                      type="radio"
                      name={`voice-update-status-${index}`}
                      value={status}
                      checked={progress.status_update === status}
                      disabled={phase === 'submitted'}
                      onChange={(event) => updateReport(index, { status_update: event.target.value })}
                    />
                    <span>{status}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>
        {(
          <details className="voice-update-ownership-details">
            <summary>调整任务归属及成果链接</summary>
            {renderOwnership(report, index)}
            {(report.achievements ?? []).map((achievement, achievementIndex) => (
              <label className="voice-update-achievement-link" key={`${achievement.name}-${achievementIndex}`}>
                <span>{achievement.name}的存储地址</span>
                <input
                  value={achievement.file_link ?? ''}
                  disabled={phase === 'submitted'}
                  onChange={(event) => setTaskReports((previous) => previous.map((item, currentIndex) => currentIndex === index ? {
                    ...item,
                    achievements: item.achievements.map((entry, currentAchievementIndex) => currentAchievementIndex === achievementIndex ? { ...entry, file_link: event.target.value } : entry),
                  } as TaskReport : item))}
                  placeholder="可选"
                />
              </label>
            ))}
          </details>
        )}
      </article>
    )
  }

  if (taskReports.length === 0) {
    return (
      <div className="voice-update-task-reports voice-update-structured-empty" aria-label="待提取的结构化汇报字段">
        <article className="voice-update-report-card is-primary">
          <div className="voice-update-progress-editor">
            {[
              ['本次完成', 'AI 提取后将在此展示本次完成的工作', 'is-complete', '✓'],
              ['下一步计划', 'AI 提取后将在此展示下一步计划', 'is-next', '→'],
              ['问题与风险', 'AI 提取后将在此展示问题与风险', 'is-risk', '!'],
              ['取得的成果', 'AI 提取后将在此展示取得的成果', 'is-achievement', '★'],
            ].map(([label, placeholder, tone, icon]) => (
              <div className="voice-update-progress-field" key={label}>
                <label className="voice-update-field-label"><span className={tone}>{icon}</span>{label}</label>
                <div className="voice-update-field-control">
                  <textarea value="" disabled placeholder={placeholder} readOnly />
                  <span>0/1000</span>
                </div>
              </div>
            ))}
            <div className="voice-update-progress-field">
              <label className="voice-update-field-label"><span className="is-status">⚑</span>任务状态建议</label>
              <div className="voice-update-status-options" role="radiogroup" aria-label="任务状态建议">
                {STATUS_OPTIONS.map((status) => (
                  <label key={status}>
                    <input type="radio" name="voice-update-status" value={status} disabled />
                    <span>{status}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </article>
      </div>
    )
  }

  return (
    <div className="voice-update-task-reports">
      <h3 className="voice-update-agent-count">AI 已识别 {taskReports.length} 项工作</h3>
      {taskReports.length > 1 && (
        <nav className="voice-update-task-switcher" aria-label="切换 AI 识别任务卡">
          {taskReports.map((report, index) => {
            const progress = report.type === 'progress' ? report : null
            const label = progress
              ? `${progress.project_name || `任务卡 ${index + 1}`} · ${progress.matched_subtask_title || progress.parent_key_task || '待确认归属'}`
              : `任务卡 ${index + 1}/${taskReports.length}`
            return (
              <button type="button" key={index} className={`${index === safeActiveIndex ? 'is-active' : ''}${progress?.match_status && progress.match_status !== 'matched' ? ' is-unresolved' : ''}`} aria-current={index === safeActiveIndex ? 'true' : undefined} onClick={() => setActiveReportIndex(index)}>
                <span>{label}</span><small>任务卡 {index + 1}/{taskReports.length}</small>
              </button>
            )
          })}
        </nav>
      )}
      {activeItem && renderReport(activeItem.report, activeItem.index)}
    </div>
  )
}
