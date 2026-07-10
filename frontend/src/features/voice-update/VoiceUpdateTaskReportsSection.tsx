import { fetchSubTasks } from '../../api/subtasks'
import { formatIssueItems } from '../../domain/voiceUpdateFlow'
import type { TaskReport } from '../../api/updates'
import type { VoiceUpdateTaskReportsSectionProps } from './voiceUpdateResultTypes'
import type { SubTaskItem } from '../../types'
import { TASK_LEVEL_LABELS } from '../../utils/taskPresentation'

export function VoiceUpdateTaskReportsSection({
  phase,
  taskReports,
  setTaskReports,
  keyTaskIssues,
  cardEdits,
  updateCardEdit,
  projectTasksForSuggest,
  voiceSubtasksContext,
}: VoiceUpdateTaskReportsSectionProps) {
  return (
    <div>
                      {taskReports.length > 0 && (
                        <div className="mb-4 space-y-3">
                          {taskReports.length > 1 && (
                            <div className="flex items-center gap-2">
                              <div className="w-1 h-3.5 rounded-full" style={{ background: '#4338CA' }} />
                              <span className="text-xs font-bold text-indigo-700">AI 任务解析</span>
                              <span className="text-xs text-slate-400">· 共 {taskReports.length} 项</span>
                            </div>
                          )}
                          {taskReports.map((r, i) => {
                            const isSuggest = r.type === 'suggest_new_subtask'
                            const isNew = !isSuggest && r.type === 'new_task'
                            const matched = !isSuggest && !isNew && !!(r as Extract<TaskReport, {type:'progress'}>).matched_subtask_id
                            const statusUpdate = (!isSuggest && !isNew) ? (r as Extract<TaskReport, {type:'progress'}>).status_update : null
                            const STATUS_STYLE: Record<string, {bg:string;color:string}> = {
                              '已完成': { bg: '#D1FAE5', color: '#065F46' },
                              '延期': { bg: '#FEE2E2', color: '#991B1B' },
                              '进行中': { bg: '#DBEAFE', color: '#1E40AF' },
                              '暂缓': { bg: '#FEF3C7', color: '#92400E' },
                            }
                            const sStyle = statusUpdate ? (STATUS_STYLE[statusUpdate] ?? { bg: '#F1F5F9', color: '#475569' }) : null
                            const title = isSuggest
                              ? (r as Extract<TaskReport, {type:'suggest_new_subtask'}>).title
                              : isNew
                                ? (r as Extract<TaskReport, {type:'new_task'}>).title
                                : (r as Extract<TaskReport, {type:'progress'}>).matched_subtask_title || `未匹配${TASK_LEVEL_LABELS.subtask}`
                            const completed = r.completed
                            const achs = r.achievements ?? []
                            const issues = formatIssueItems(r.subtask_issues ?? [])
                            const nexts = r.next_steps ?? []
                            const e = cardEdits[i] ?? { taskId: null, subtaskId: null, subtasks: [] as SubTaskItem[], editorOpen: false, modified: false }
                            const aiParentKeyTask = r.type === 'progress'
                              ? ((r as Extract<TaskReport, {type:'progress'}>).parent_key_task
                                  || voiceSubtasksContext.find((item) => item.id === (r as Extract<TaskReport, {type:'progress'}>).matched_subtask_id)?.parent_key_task
                                  || '')
                              : ((r as Record<string, unknown>).parent_key_task as string | undefined) || ''
                            const dispKeyTask = (e.modified && e.taskId)
                              ? (projectTasksForSuggest.find((t) => t.id === e.taskId)?.key_task ?? `未关联${TASK_LEVEL_LABELS.task}`)
                              : aiParentKeyTask || `未关联${TASK_LEVEL_LABELS.task}`
                            const aiSubtaskName = r.type === 'progress'
                              ? ((r as Extract<TaskReport, {type:'progress'}>).matched_subtask_title || '')
                              : ((r as Record<string,unknown>).title as string | undefined) || ''
                            const dispSubtask = (e.modified && e.subtaskId)
                              ? (e.subtasks.find((sub) => sub.id === e.subtaskId)?.title ?? `未关联${TASK_LEVEL_LABELS.subtask}`)
                              : aiSubtaskName || (isSuggest ? `待新增${TASK_LEVEL_LABELS.subtask}` : `未关联${TASK_LEVEL_LABELS.subtask}`)
                            const needsParent = isSuggest && !((r as Record<string,unknown>).parent_task_id) && !(e.modified && e.taskId)
                            const borderColor = isSuggest ? (needsParent ? '#FCD34D' : '#86EFAC') : isNew ? '#DDD6FE' : matched ? '#BFDBFE' : '#E2E8F0'
                            const headerBg = isSuggest ? '#FFFBEB' : isNew ? '#F5F3FF' : matched ? '#EFF6FF' : '#F8FAFC'
                            return (
                              <div key={i} className="rounded-2xl overflow-hidden" style={{ border: `1px solid ${borderColor}` }}>
                                  <div className="flex items-center gap-2 px-4 py-3" style={{ background: headerBg }}>
                                    <div className="flex-1 min-w-0">
                                      <div className="flex items-center gap-2 flex-wrap">
                                        {isSuggest && <span className="text-[10px] px-1.5 py-px rounded font-bold flex-shrink-0" style={{ background: '#FEF3C7', color: '#92400E' }}>建议新增关键任务</span>}
                                        {isNew && <span className="text-[10px] px-1.5 py-px rounded font-bold flex-shrink-0" style={{ background: '#EDE9FE', color: '#5B21B6' }}>新建关键任务</span>}
                                        {!isSuggest && !isNew && matched && <span className="text-[10px] font-bold text-blue-400 flex-shrink-0">✔</span>}
                                        {!isSuggest && !isNew && !matched && <span className="text-[10px] text-slate-400 flex-shrink-0">?</span>}
                                        <span className="text-sm font-bold text-slate-800 leading-snug">{title}</span>
                                      </div>
                                      {isSuggest && (
                                        <button
                                          type="button"
                                          onClick={() => {
                                            const suggest = r as Extract<TaskReport, {type:'suggest_new_subtask'}>
                                            const text = `任务名称：${suggest.title}\n负责人：${suggest.assignee || ''}\n计划时间：${suggest.plan_start || ''} ~ ${suggest.plan_end || ''}\n完成内容：${suggest.completed || ''}\n问题：${formatIssueItems(suggest.subtask_issues).join('；') || '无'}\n下一步：${(suggest.next_steps || []).join('；') || '无'}`
                                            navigator.clipboard.writeText(text).then(() => {
                                              const btn = document.activeElement as HTMLButtonElement
                                              if (btn) {
                                                const orig = btn.textContent
                                                btn.textContent = '✓ 已复制'
                                                setTimeout(() => { btn.textContent = orig }, 1500)
                                              }
                                            })
                                          }}
                                          className="mt-1.5 text-[10px] font-semibold text-amber-600 hover:text-amber-700 flex items-center gap-1"
                                        >
                                          <svg style={{ width: 11, height: 11 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" /></svg>
                                          复制任务信息
                                        </button>
                                      )}
                                    {isNew && (
                                      <p className="text-xs text-violet-500 mt-0.5">{(r as Extract<TaskReport, {type:'new_task'}>).plan_start} ~ {(r as Extract<TaskReport, {type:'new_task'}>).plan_end}</p>
                                    )}
                                  </div>
                                  {sStyle && statusUpdate && (
                                    <span className="flex-shrink-0 text-xs px-2 py-1 rounded-full font-semibold" style={sStyle}>{statusUpdate}</span>
                                  )}
                                </div>
                                <div style={{ borderTop: `1px solid ${isSuggest ? '#FEF3C7' : '#E9EFF6'}` }}>
                                  <div className="flex items-center gap-1.5 px-3 py-1.5 flex-wrap" style={{ background: isSuggest ? '#FFFBEB' : '#F8FBFF' }}>
                                    <span className="text-[10px] font-semibold text-slate-400">归属</span>
                                    <span className="text-[10px] text-slate-300">·</span>
                                    <span className={`text-[10px] font-semibold ${dispKeyTask === `未关联${TASK_LEVEL_LABELS.task}` ? 'text-amber-500 italic' : 'text-slate-500'}`}>{dispKeyTask}</span>
                                    {!isSuggest && (
                                      <>
                                        <span className="text-[10px] text-slate-300">·</span>
                                        <span className={`text-[10px] font-semibold ${dispSubtask === `未关联${TASK_LEVEL_LABELS.subtask}` ? 'text-amber-500 italic' : 'text-slate-500'}`}>{dispSubtask}</span>
                                      </>
                                    )}
                                    {needsParent && !e.editorOpen && <span className="text-[10px] text-amber-600 font-bold ml-0.5">⚠️需选择</span>}
                                    <button
                                      type="button"
                                      onClick={async () => {
                                        const newOpen = !e.editorOpen
                                        updateCardEdit(i, { editorOpen: newOpen })
                                        if (newOpen && e.taskId && e.subtasks.length === 0 && !isSuggest) {
                                          const subs = await fetchSubTasks(e.taskId).catch(() => [] as SubTaskItem[])
                                          updateCardEdit(i, { subtasks: (subs as SubTaskItem[]).filter((sub) => !sub.is_deleted) })
                                        }
                                      }}
                                      className="ml-auto text-[11px] font-semibold hover:opacity-70 flex-shrink-0"
                                      style={{ color: e.editorOpen ? '#64748B' : '#2563EB' }}
                                    >
                                      {e.editorOpen ? '收起' : '修改归属'}
                                    </button>
                                  </div>
                                  {needsParent && (
                                    <div className="px-3 py-2" style={{ background: '#FFFBEB', borderTop: '1px solid #FEF3C7' }}>
                                      <p className="text-[11px] font-semibold text-amber-700">负责人确认前必须选择归属{TASK_LEVEL_LABELS.task}</p>
                                    </div>
                                  )}
                                  {e.editorOpen && (
                                    <div className="px-3 pb-2.5 pt-1.5 space-y-1.5" style={{ background: '#EFF6FF', borderTop: '1px solid #BFDBFE' }}>
                                      <select
                                        value={e.taskId ?? ''}
                                        onChange={async (ev) => {
                                          const taskId = ev.target.value ? Number(ev.target.value) : null
                                          updateCardEdit(i, { taskId, subtaskId: null, subtasks: [], modified: true })
                                          if (taskId && !isSuggest) {
                                            const subs = await fetchSubTasks(taskId).catch(() => [] as SubTaskItem[])
                                            updateCardEdit(i, { taskId, subtasks: (subs as SubTaskItem[]).filter((sub) => !sub.is_deleted), modified: true })
                                          }
                                        }}
                                        className="w-full text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white cursor-pointer focus:outline-none"
                                      >
                                        <option value="">{`选择${TASK_LEVEL_LABELS.task}`}</option>
                                        {projectTasksForSuggest.map((t) => <option key={t.id} value={t.id}>{t.key_task}</option>)}
                                      </select>
                                      {!isSuggest && (
                                        <select
                                          value={e.subtaskId ?? ''}
                                          disabled={!e.taskId}
                                          onChange={(ev) => updateCardEdit(i, { subtaskId: ev.target.value ? Number(ev.target.value) : null, modified: true })}
                                          className="w-full text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white cursor-pointer focus:outline-none disabled:opacity-50"
                                        >
                                          <option value="">{`选择${TASK_LEVEL_LABELS.subtask}`}</option>
                                          {e.subtasks.map((sub) => <option key={sub.id} value={sub.id}>{sub.title}</option>)}
                                        </select>
                                      )}
                                      {e.modified && !isSuggest && e.taskId && !e.subtaskId && (
                                        <p className="text-[11px] text-amber-600 font-semibold">{`⚠️ 请选择${TASK_LEVEL_LABELS.subtask}`}</p>
                                      )}
                                    </div>
                                  )}
                                </div>
                                <div className="bg-white">
                                  {isSuggest ? (
                                    <>
                                      <div className="px-4 py-3" style={{ borderTop: '1px solid #FEF3C7' }}>
                                        <p className="text-[11px] font-semibold mb-1" style={{ color: '#92400E' }}>建议内容</p>
                                        {completed
                                          ? <p className="text-sm text-slate-700 leading-relaxed">{String(completed)}</p>
                                          : <p className="text-xs text-slate-300 italic">未提供</p>
                                        }
                                      </div>
                                      {issues.length > 0 && (
                                        <div className="px-4 py-3" style={{ borderTop: '1px solid #FEF3C7', background: '#FFFBEB' }}>
                                          <p className="text-[11px] font-semibold mb-1.5" style={{ color: '#92400E' }}>建议原因</p>
                                          <ul className="space-y-1">
                                            {issues.map((iss, ii) => (
                                              <li key={ii} className="text-xs leading-relaxed flex items-start gap-1.5 text-amber-800">
                                                <span className="flex-shrink-0 mt-0.5">·</span>
                                                <span>{iss}</span>
                                              </li>
                                            ))}
                                          </ul>
                                        </div>
                                      )}
                                      <div className="px-4 py-3" style={{ borderTop: '1px solid #FEF3C7' }}>
                                        <p className="text-[11px] font-semibold mb-1" style={{ color: '#92400E' }}>下一步</p>
                                        {nexts.length > 0
                                          ? <ul className="space-y-0.5">{nexts.map((n, ni) => (
                                              <li key={ni} className="text-xs text-slate-700 leading-relaxed flex items-start gap-1.5">
                                                <span className="flex-shrink-0 text-amber-300 mt-0.5">·</span>
                                                <span>{String(n)}</span>
                                              </li>
                                            ))}</ul>
                                          : <p className="text-xs text-slate-300 italic">未提供</p>
                                        }
                                      </div>
                                    </>
                                  ) : (
                                    <>
                                      <div className="px-4 py-3" style={{ borderTop: '1px solid #F1F5F9' }}>
                                        <p className="text-[11px] font-semibold text-slate-400 mb-1">本次完成</p>
                                        {completed
                                          ? <p className="text-sm text-slate-700 leading-relaxed">{String(completed)}</p>
                                          : <p className="text-xs text-slate-300 italic">未提供</p>
                                        }
                                      </div>
                                      {achs.length > 0 && (
                                        <div className="px-4 py-3 space-y-2" style={{ borderTop: '1px solid #F1F5F9' }}>
                                          <p className="text-[11px] font-semibold text-slate-400">成果文件</p>
                                          {achs.map((ach, ai) => (
                                            <div key={ai} className="flex items-center gap-2">
                                              <span className="text-xs text-slate-600 flex-shrink-0 max-w-[120px] truncate" title={String(ach.name)}>{String(ach.name)}</span>
                                              <input
                                                type="text"
                                                value={String(ach.file_link ?? '')}
                                                onChange={(e) => {
                                                  const val = e.target.value
                                                  setTaskReports((prev) => prev.map((rep, ri) => {
                                                    if (ri !== i) return rep
                                                    const newAchs = (rep.achievements ?? []).map((a, xi) => (
                                                      xi === ai ? { ...a, file_link: val } : a
                                                    ))
                                                    return { ...rep, achievements: newAchs }
                                                  }))
                                                }}
                                                placeholder="存储地址（可选）"
                                                className="flex-1 text-xs border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-400/30"
                                              />
                                            </div>
                                          ))}
                                        </div>
                                      )}
                                      {issues.length > 0 && (
                                        <div className="px-4 py-3" style={{ borderTop: '1px solid #FEE2E2', background: '#FFF8F8' }}>
                                          <p className="text-[11px] font-semibold mb-1.5" style={{ color: '#B91C1C' }}>问题 / 风险</p>
                                          <ul className="space-y-1">
                                            {issues.map((iss, ii) => (
                                              <li key={ii} className="text-xs leading-relaxed flex items-start gap-1.5" style={{ color: '#DC2626' }}>
                                                <span className="flex-shrink-0 mt-0.5">·</span>
                                                <span>{iss}</span>
                                              </li>
                                            ))}
                                          </ul>
                                        </div>
                                      )}
                                      <div className="px-4 py-3" style={{ borderTop: '1px solid #F1F5F9' }}>
                                        <p className="text-[11px] font-semibold text-slate-400 mb-1">下一步计划</p>
                                        {nexts.length > 0
                                          ? <ul className="space-y-0.5">{nexts.map((n, ni) => (
                                              <li key={ni} className="text-xs text-slate-700 leading-relaxed flex items-start gap-1.5">
                                                <span className="flex-shrink-0 text-slate-300 mt-0.5">·</span>
                                                <span>{String(n)}</span>
                                              </li>
                                            ))}</ul>
                                          : <p className="text-xs text-slate-300 italic">未提供</p>
                                        }
                                      </div>
                                    </>
                                  )}
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      )}
      
          </div>
  )
}
