import { useState } from 'react'
import { ownerSubmitProfile } from '../../api/projects'
import type { ProjectProfilePayload, ProjectWorkProgressTaskDraft } from '../../api/projects'
import { toast } from '../../utils/toast'
import type { Project } from '../../types'

type Props = {
  project: Project
  onClose: () => void
  onSuccess?: (result: Project & { submitted_for_review: boolean }) => void
}

type LocalSubTaskDraft = {
  title: string
  evaluation_standard: string
  assignee: string
  helper: string
  plan_start: string
  plan_end: string
}

type LocalTaskDraft = {
  title: string
  description: string
  owner: string
  helper: string
  plan_start: string
  plan_end: string
  subtasks: LocalSubTaskDraft[]
}

type ParsedPeriod = {
  start: string
  end: string
}

const EMPTY_SUBTASK: LocalSubTaskDraft = {
  title: '',
  evaluation_standard: '',
  assignee: '',
  helper: '',
  plan_start: '',
  plan_end: '',
}

const EMPTY_TASK: LocalTaskDraft = {
  title: '',
  description: '',
  owner: '',
  helper: '',
  plan_start: '',
  plan_end: '',
  subtasks: [{ ...EMPTY_SUBTASK }],
}

function cloneEmptyTask(): LocalTaskDraft {
  return { ...EMPTY_TASK, subtasks: [{ ...EMPTY_SUBTASK }] }
}

function composeProjectPeriod(startDate?: string, endDate?: string): string {
  const start = (startDate ?? '').trim()
  const end = (endDate ?? '').trim()
  if (start && end) return `${start} 至 ${end}`
  return start || end
}

function parseProjectPeriod(value: string): ParsedPeriod {
  return parsePeriodValue(value)
}

function composeTaskPeriod(startDate?: string, endDate?: string): string {
  const start = (startDate ?? '').trim()
  const end = (endDate ?? '').trim()
  if (start && end) return `${start} - ${end}`
  return start || end
}

function parseTaskPeriod(value: string): ParsedPeriod {
  return parsePeriodValue(value)
}

function parsePeriodValue(value: string): ParsedPeriod {
  const text = value.trim()
  if (!text) return { start: '', end: '' }

  for (const delimiter of ['至', '~', '到']) {
    if (!text.includes(delimiter)) continue
    const parts = text.split(delimiter).map((part) => part.trim()).filter(Boolean)
    if (parts.length >= 2) {
      return { start: parts[0], end: parts.slice(1).join(' ') }
    }
  }

  const spacedDashMatch = text.match(/^(.+?)\s+[-–—]\s+(.+)$/)
  if (spacedDashMatch) {
    return { start: spacedDashMatch[1].trim(), end: spacedDashMatch[2].trim() }
  }

  return { start: text, end: '' }
}

function toPayloadDraft(tasks: LocalTaskDraft[]): ProjectWorkProgressTaskDraft[] {
  return tasks
    .map((task) => ({
      title: task.title.trim(),
      description: task.description.trim(),
      owner: task.owner.trim(),
      helper: task.helper.trim(),
      plan_start: task.plan_start,
      plan_end: task.plan_end,
      subtasks: task.subtasks
        .map((subtask) => ({
          title: subtask.title.trim(),
          evaluation_standard: subtask.evaluation_standard.trim(),
          assignee: subtask.assignee.trim(),
          helper: subtask.helper.trim(),
          plan_start: subtask.plan_start,
          plan_end: subtask.plan_end,
        }))
        .filter((subtask) => subtask.title),
    }))
    .filter((task) => task.title)
}

export function OwnerSubmitModal({ project, onClose, onSuccess }: Props) {
  const [fillForm, setFillForm] = useState<ProjectProfilePayload>(() => ({
    project_type: project.project_type ?? '',
    client_name: project.client_name ?? '',
    background: project.background ?? '',
    objectives: project.objectives ?? '',
    expected_outcomes: project.expected_outcomes ?? '',
    start_date: project.start_date ?? '',
    end_date: project.end_date ?? '',
  }))
  const [projectPeriod, setProjectPeriod] = useState(() => composeProjectPeriod(project.start_date, project.end_date))
  const [draftTasks, setDraftTasks] = useState<LocalTaskDraft[]>([cloneEmptyTask()])
  const [fillLoading, setFillLoading] = useState(false)

  function addTaskDraft() {
    setDraftTasks((prev) => [...prev, cloneEmptyTask()])
  }

  function removeTaskDraft(index: number) {
    setDraftTasks((prev) => (prev.length <= 1 ? prev : prev.filter((_, idx) => idx !== index)))
  }

  function updateTaskDraft(index: number, field: keyof Omit<LocalTaskDraft, 'subtasks'>, value: string) {
    setDraftTasks((prev) => prev.map((task, idx) => (idx === index ? { ...task, [field]: value } : task)))
  }

  function addSubTaskDraft(taskIndex: number) {
    setDraftTasks((prev) =>
      prev.map((task, idx) =>
        idx === taskIndex ? { ...task, subtasks: [...task.subtasks, { ...EMPTY_SUBTASK }] } : task,
      ),
    )
  }

  function removeSubTaskDraft(taskIndex: number, subIndex: number) {
    setDraftTasks((prev) =>
      prev.map((task, idx) =>
        idx === taskIndex
          ? { ...task, subtasks: task.subtasks.length <= 1 ? task.subtasks : task.subtasks.filter((_, sidx) => sidx !== subIndex) }
          : task,
      ),
    )
  }

  function updateSubTaskDraft(taskIndex: number, subIndex: number, field: keyof LocalSubTaskDraft, value: string) {
    setDraftTasks((prev) =>
      prev.map((task, idx) =>
        idx === taskIndex
          ? {
              ...task,
              subtasks: task.subtasks.map((subtask, sidx) =>
                sidx === subIndex ? { ...subtask, [field]: value } : subtask,
              ),
            }
          : task,
      ),
    )
  }

  function updateSubTaskPeriod(taskIndex: number, subIndex: number, value: string) {
    const parsed = parseTaskPeriod(value)
    setDraftTasks((prev) =>
      prev.map((task, idx) =>
        idx === taskIndex
          ? {
              ...task,
              subtasks: task.subtasks.map((subtask, sidx) =>
                sidx === subIndex ? { ...subtask, plan_start: parsed.start, plan_end: parsed.end } : subtask,
              ),
            }
          : task,
      ),
    )
  }

  async function handleSubmit() {
    if (!project?.id) return
    const workProgressDraft = toPayloadDraft(draftTasks)
    if (workProgressDraft.length === 0) {
      toast.error('请至少新增一条重点工作')
      return
    }
    const subtaskCount = workProgressDraft.reduce((total, task) => total + (task.subtasks?.length ?? 0), 0)
    if (subtaskCount === 0) {
      toast.error('请至少添加一个关键任务')
      return
    }

    const parsedProjectPeriod = parseProjectPeriod(projectPeriod)
    setFillLoading(true)
    try {
      const result = await ownerSubmitProfile(project.id, {
        ...fillForm,
        start_date: parsedProjectPeriod.start,
        end_date: parsedProjectPeriod.end,
        work_progress_draft: workProgressDraft,
      })
      toast.success('已提交审核，等待企业教练审核通过后正式启动')
      if (onSuccess) onSuccess(result)
      else onClose()
    } catch (e: any) {
      toast.error(e?.message || '提交失败，请重试')
    } finally {
      setFillLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-4"
      style={{ background: 'rgba(15,23,42,0.45)' }}
      onClick={() => !fillLoading && onClose()}
    >
      <div
        className="owner-submit-workbench-shell flex h-[90vh] w-[96vw] max-w-[1280px] flex-col overflow-hidden rounded-xl bg-[#f6f9ff] text-slate-900 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="owner-submit-workbench-header flex h-[72px] shrink-0 items-center justify-between border-b border-[#e0c0b1] bg-white px-6">
          <div className="flex min-w-0 items-center gap-4">
            <div className="h-10 w-1.5 rounded-full bg-orange-500" aria-hidden="true" />
            <div className="min-w-0">
              <h2 className="truncate text-lg font-semibold tracking-[-0.01em] text-slate-900">
                填写立项信息 — {project.name}
              </h2>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <span className="rounded border border-orange-200 bg-orange-50 px-2 py-0.5 text-[11px] font-medium text-orange-800">
                  待负责人完善
                </span>
                <span className="text-xs text-slate-500">补全项目资料，提交后进入企业教练审核。</span>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={fillLoading}
            className="ml-4 rounded-full px-3 py-2 text-xl leading-none text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50"
            aria-label="关闭"
          >
            ×
          </button>
        </header>

        <main className="owner-submit-workbench-main flex-1 overflow-y-auto bg-[#f6f9ff] pb-8">
          <div className="owner-submit-workbench-columns mx-auto flex gap-6 items-start max-w-[1440px] px-6 py-6">
            <aside className="owner-submit-left-pane sticky top-6 w-[400px] shrink-0 space-y-6">
              <section className="owner-submit-core-card overflow-hidden rounded-xl border border-[#e0c0b1]/70 bg-white shadow-sm">
                <h3 className="sr-only">项目核心信息</h3>
                <div className="p-6">
                  <div className="space-y-6">
                    <div className="space-y-2">
                      <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                        项目名称
                      </label>
                      <input
                        value={project.name}
                        disabled
                        className="w-full border-none p-0 bg-transparent text-lg font-semibold text-slate-900 placeholder:text-slate-300 focus:ring-0 disabled:opacity-100"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                        项目周期 / 时间段
                      </label>
                      <input
                        value={projectPeriod}
                        onChange={(e) => setProjectPeriod(e.target.value)}
                        placeholder="例如：2026-07-01 至 2026-12-31"
                        className="w-full border-none p-0 bg-transparent text-base text-slate-800 placeholder:text-slate-300 focus:ring-0"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                        项目完成准则 / 验收标准
                      </label>
                      <textarea
                        value={fillForm.objectives ?? ''}
                        onChange={(e) => setFillForm((prev) => ({ ...prev, objectives: e.target.value }))}
                        placeholder="描述项目完成后如何验收，例如关键结果、通过标准、交付边界等"
                        rows={3}
                        className="w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-3 text-sm leading-relaxed text-slate-700 placeholder:text-slate-400 focus:border-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-100"
                      />
                    </div>
                  </div>

                  <details className="group mt-4">
                    <summary className="flex cursor-pointer select-none items-center gap-2 text-sm font-semibold text-orange-700 transition-opacity hover:opacity-80">
                      <span className="text-base leading-none transition-transform group-open:rotate-90">›</span>
                      补充详细信息
                    </summary>
                    <div className="mt-4 space-y-4 border-t border-slate-200/80 pt-4">
                      <div className="space-y-1.5">
                        <label className="block text-[11px] font-semibold text-slate-500">客户名称</label>
                        <input
                          value={fillForm.client_name ?? ''}
                          onChange={(e) => setFillForm((prev) => ({ ...prev, client_name: e.target.value }))}
                          placeholder="内部项目可留空"
                          className="h-9 w-full rounded border border-slate-200 bg-white px-3 text-sm text-slate-700 placeholder:text-slate-400 focus:border-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-100"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="block text-[11px] font-semibold text-slate-500">项目类型</label>
                        <input
                          value={fillForm.project_type ?? ''}
                          onChange={(e) => setFillForm((prev) => ({ ...prev, project_type: e.target.value }))}
                          placeholder="博维内部项目"
                          className="h-9 w-full rounded border border-slate-200 bg-white px-3 text-sm text-slate-700 placeholder:text-slate-400 focus:border-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-100"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="block text-[11px] font-semibold text-slate-500">项目背景</label>
                        <textarea
                          value={fillForm.background ?? ''}
                          onChange={(e) => setFillForm((prev) => ({ ...prev, background: e.target.value }))}
                          placeholder="说明项目来源及必要性，可选"
                          rows={3}
                          className="w-full resize-none rounded border border-slate-200 bg-white px-3 py-2 text-sm leading-relaxed text-slate-700 placeholder:text-slate-400 focus:border-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-100"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="block text-[11px] font-semibold text-slate-500">补充说明</label>
                        <textarea
                          value={fillForm.expected_outcomes ?? ''}
                          onChange={(e) => setFillForm((prev) => ({ ...prev, expected_outcomes: e.target.value }))}
                          placeholder="其他需要备注的信息，可选"
                          rows={5}
                          className="w-full resize-none rounded border border-slate-200 bg-white px-3 py-2 text-sm leading-relaxed text-slate-700 placeholder:text-slate-400 focus:border-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-100"
                        />
                      </div>
                    </div>
                  </details>
                </div>
              </section>
            </aside>

            <section className="owner-submit-right-pane flex-1 min-w-0">
              <div className="owner-submit-workplan-heading mb-4 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <h3 className="text-lg font-semibold text-slate-900">工作推进方案</h3>
                  <span className="text-sm italic text-slate-500">
                    规划重点工作方向，并细化关键任务执行计划。重点工作用于归类工作方向；关键任务才需要明确责任人、协助人和时间段。
                  </span>
                </div>
                <button
                  type="button"
                  onClick={addTaskDraft}
                  className="flex shrink-0 items-center gap-1.5 rounded-lg border border-orange-500 bg-white px-4 py-2 text-xs font-semibold text-orange-700 transition-colors hover:bg-orange-50"
                >
                  + 新增重点工作
                </button>
              </div>

              <div>
                {draftTasks.map((task, taskIndex) => (
                  <div
                    key={taskIndex}
                    className="owner-submit-task-group mb-6 bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm"
                  >
                    <div className="owner-submit-task-group-header flex items-start gap-4 border-b border-slate-200 bg-slate-100/70 px-6 py-4">
                      <div className="flex w-8 h-8 shrink-0 items-center justify-center rounded bg-orange-50 text-lg font-semibold text-orange-700">
                        {taskIndex + 1}
                      </div>
                      <div className="grid flex-1 grid-cols-1 gap-4 md:grid-cols-2">
                        <div>
                          <label className="block text-[10px] font-semibold uppercase text-slate-500/80">
                            重点工作名称
                          </label>
                          <input
                            value={task.title}
                            onChange={(e) => updateTaskDraft(taskIndex, 'title', e.target.value)}
                            placeholder="请输入重点工作"
                            className="w-full border-none p-0 bg-transparent text-lg font-semibold text-slate-900 placeholder:text-slate-300 focus:ring-0"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] font-semibold uppercase text-slate-500/80">
                            目标成果 / 验收标准
                          </label>
                          <input
                            value={task.description}
                            onChange={(e) => updateTaskDraft(taskIndex, 'description', e.target.value)}
                            placeholder="请输入完成准则"
                            className="w-full border-none p-0 bg-transparent text-sm text-slate-600 placeholder:text-slate-300 focus:ring-0"
                          />
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeTaskDraft(taskIndex)}
                        disabled={draftTasks.length <= 1}
                        className="rounded p-1 text-xs text-slate-400 transition-colors hover:text-red-500 disabled:cursor-not-allowed disabled:opacity-30"
                        aria-label={`删除重点工作 ${taskIndex + 1}`}
                      >
                        删除
                      </button>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="owner-submit-subtask-table w-full border-collapse text-left text-sm">
                        <thead>
                          <tr className="border-b border-slate-200/80 bg-slate-50/80 text-[11px] font-semibold text-slate-500">
                            <th className="w-[250px] py-2 pl-6 pr-3">关键任务</th>
                            <th className="w-[100px] px-3 py-2">责任人</th>
                            <th className="w-[100px] px-3 py-2">协助人</th>
                            <th className="w-[160px] px-3 py-2">时间段</th>
                            <th className="px-3 py-2">备注 / 标准</th>
                            <th className="w-[60px] px-3 py-2">操作</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {task.subtasks.map((subtask, subIndex) => (
                            <tr key={subIndex} className="group transition-colors hover:bg-slate-50">
                              <td className="py-3 pl-6 pr-3">
                                <input
                                  value={subtask.title}
                                  onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'title', e.target.value)}
                                  placeholder="例如：任务名称"
                                  className="w-full border-none p-0 bg-transparent text-sm text-slate-800 placeholder:text-slate-300 focus:ring-0"
                                />
                              </td>
                              <td className="px-3 py-3">
                                <input
                                  value={subtask.assignee}
                                  onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'assignee', e.target.value)}
                                  placeholder="责任人"
                                  className="w-full border-none p-0 bg-transparent text-sm text-slate-800 placeholder:text-slate-300 focus:ring-0"
                                />
                              </td>
                              <td className="px-3 py-3">
                                <input
                                  value={subtask.helper}
                                  onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'helper', e.target.value)}
                                  placeholder="协助人"
                                  className="w-full border-none p-0 bg-transparent text-sm text-slate-600 placeholder:text-slate-300 focus:ring-0"
                                />
                              </td>
                              <td className="px-3 py-3">
                                <input
                                  value={composeTaskPeriod(subtask.plan_start, subtask.plan_end)}
                                  onChange={(e) => updateSubTaskPeriod(taskIndex, subIndex, e.target.value)}
                                  placeholder="7.1 - 7.5"
                                  className="w-full border-none p-0 bg-transparent text-sm text-slate-600 placeholder:text-slate-300 focus:ring-0"
                                />
                              </td>
                              <td className="px-3 py-3">
                                <input
                                  value={subtask.evaluation_standard}
                                  onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'evaluation_standard', e.target.value)}
                                  placeholder="补充说明，可选"
                                  className="w-full border-none p-0 bg-transparent text-sm text-slate-600 placeholder:text-slate-300 focus:ring-0"
                                />
                              </td>
                              <td className="px-3 py-3 text-right">
                                <button
                                  type="button"
                                  onClick={() => removeSubTaskDraft(taskIndex, subIndex)}
                                  disabled={task.subtasks.length <= 1}
                                  className="rounded px-1.5 py-1 text-[11px] text-slate-400 opacity-70 transition-opacity hover:bg-red-50 hover:text-red-500 hover:opacity-100 group-hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-20"
                                >
                                  删除
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    <div className="bg-white px-6 py-2.5">
                      <button
                        type="button"
                        onClick={() => addSubTaskDraft(taskIndex)}
                        className="text-xs font-semibold text-orange-700 transition-colors hover:underline"
                      >
                        + 新增关键任务
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </main>

        <footer className="owner-submit-workbench-footer flex h-[72px] shrink-0 items-center justify-between border-t border-[#e0c0b1] bg-white px-6 shadow-[0_-4px_12px_-2px_rgba(0,0,0,0.05)]">
          <button
            type="button"
            onClick={onClose}
            disabled={fillLoading}
            className="h-10 rounded-lg border border-slate-300 px-6 text-sm font-semibold text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={fillLoading}
            className="h-10 rounded-lg bg-orange-600 px-10 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-orange-700 disabled:opacity-50"
          >
            {fillLoading ? '提交中…' : '提交立项审核'}
          </button>
        </footer>
      </div>
    </div>
  )
}
