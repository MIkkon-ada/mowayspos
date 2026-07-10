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

const FIELDS: { key: keyof ProjectProfilePayload; label: string; placeholder: string }[] = [
  { key: 'project_type', label: '项目类型', placeholder: '博维内部项目' },
  { key: 'client_name', label: '客户名称', placeholder: '内部项目可留空' },
  { key: 'background', label: '项目背景', placeholder: '说明项目的背景和来源…' },
  { key: 'objectives', label: '项目目标', placeholder: '描述需要达成的目标…' },
  { key: 'expected_outcomes', label: '预期交付物', placeholder: '列出预期交付成果…' },
  { key: 'start_date', label: '开始日期', placeholder: '' },
  { key: 'end_date', label: '结束日期', placeholder: '' },
]

function cloneEmptyTask(): LocalTaskDraft {
  return { ...EMPTY_TASK, subtasks: [{ ...EMPTY_SUBTASK }] }
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
    setFillLoading(true)
    try {
      const result = await ownerSubmitProfile(project.id, {
        ...fillForm,
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
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(15,23,42,0.45)' }}
      onClick={() => !fillLoading && onClose()}
    >
      <div className="flex max-h-[92vh] w-[820px] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        {/* 固定标题栏 */}
        <div className="flex-shrink-0 border-b px-6 py-3.5" style={{ borderColor: '#E9EFF6' }}>
          <div className="text-sm font-bold text-slate-800">填写立项信息 — {project.name}</div>
          <div className="mt-0.5 text-xs text-slate-400">提交后进入企业教练审核；工作推进表雏形会随立项信息一起保存。</div>
        </div>

        {/* 滚动内容区 */}
        <div className="flex-1 space-y-5 overflow-y-auto px-6 py-4">
          {/* A. 立项信息 — 两列紧凑布局 */}
          <section>
            <div className="mb-2 text-xs font-bold text-slate-500">立项信息</div>
            <div className="grid gap-2.5 md:grid-cols-2">
              {FIELDS.map(({ key, label, placeholder }) => {
                const isLongText = key === 'background' || key === 'objectives' || key === 'expected_outcomes'
                if (isLongText) {
                  return (
                    <div key={key} className="md:col-span-2">
                      <label className="mb-1 block text-xs font-semibold text-slate-600">{label}</label>
                      <textarea
                        value={(fillForm as any)[key] ?? ''}
                        onChange={(e) => setFillForm((prev) => ({ ...prev, [key]: e.target.value }))}
                        placeholder={placeholder}
                        rows={2}
                        className="w-full resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/30"
                      />
                    </div>
                  )
                }
                return (
                  <div key={key}>
                    <label className="mb-1 block text-xs font-semibold text-slate-600">{label}</label>
                    <input
                      type={key.includes('date') ? 'date' : 'text'}
                      value={(fillForm as any)[key] ?? ''}
                      onChange={(e) => setFillForm((prev) => ({ ...prev, [key]: e.target.value }))}
                      placeholder={placeholder}
                      className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/30"
                    />
                  </div>
                )
              })}
            </div>
          </section>

          {/* B. 工作推进表雏形 */}
          <section className="rounded-2xl border border-amber-200 bg-amber-50/40 p-4">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-sm font-bold text-slate-800">工作推进表雏形</div>
                <div className="mt-0.5 text-xs text-slate-500">先维护重点工作和关键任务草案。重点工作用于归类工作方向；关键任务才需要明确责任人、协助人和计划时间。</div>
              </div>
              <button
                type="button"
                onClick={addTaskDraft}
                className="cursor-pointer flex-shrink-0 rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-600"
              >
                新增重点工作
              </button>
            </div>

            <div className="space-y-3">
              {draftTasks.map((task, taskIndex) => (
                <div key={taskIndex} className="rounded-xl border border-slate-200 bg-white p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <div className="text-xs font-bold text-slate-500">重点工作 {taskIndex + 1}</div>
                    <button
                      type="button"
                      onClick={() => removeTaskDraft(taskIndex)}
                      disabled={draftTasks.length <= 1}
                      className="cursor-pointer text-xs text-slate-400 hover:text-red-500 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      删除重点工作
                    </button>
                  </div>

                  {/* 重点工作仅保留：标题 + 说明 */}
                  <div className="grid gap-2 md:grid-cols-2">
                    <input
                      value={task.title}
                      onChange={(e) => updateTaskDraft(taskIndex, 'title', e.target.value)}
                      placeholder="重点工作标题（如：开发并应用项目运营系统）"
                      className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    />
                    <input
                      value={task.description}
                      onChange={(e) => updateTaskDraft(taskIndex, 'description', e.target.value)}
                      placeholder="重点工作说明 / 评价标准"
                      className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    />
                  </div>

                  {/* 关键任务：保留全部可执行字段 */}
                  <div className="mt-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-semibold text-slate-500">关键任务</div>
                      <button
                        type="button"
                        onClick={() => addSubTaskDraft(taskIndex)}
                        className="cursor-pointer text-xs font-semibold text-amber-600 hover:text-amber-700"
                      >
                        新增关键任务
                      </button>
                    </div>

                    {task.subtasks.map((subtask, subIndex) => (
                      <div key={subIndex} className="grid gap-2 rounded-lg bg-slate-50 p-2 md:grid-cols-3">
                        <input
                          value={subtask.title}
                          onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'title', e.target.value)}
                          placeholder="关键任务标题"
                          className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                        />
                        <input
                          value={subtask.evaluation_standard}
                          onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'evaluation_standard', e.target.value)}
                          placeholder="评价标准"
                          className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                        />
                        <input
                          value={subtask.assignee}
                          onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'assignee', e.target.value)}
                          placeholder="责任人"
                          className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                        />
                        <input
                          value={subtask.helper}
                          onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'helper', e.target.value)}
                          placeholder="协助人"
                          className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                        />
                        <input
                          type="date"
                          value={subtask.plan_start}
                          onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'plan_start', e.target.value)}
                          aria-label="关键任务计划开始"
                          className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                        />
                        <div className="flex gap-2">
                          <input
                            type="date"
                            value={subtask.plan_end}
                            onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'plan_end', e.target.value)}
                            aria-label="关键任务计划结束"
                            className="min-w-0 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm"
                          />
                          <button
                            type="button"
                            onClick={() => removeSubTaskDraft(taskIndex, subIndex)}
                            disabled={task.subtasks.length <= 1}
                            className="cursor-pointer flex-shrink-0 rounded-lg px-2 text-xs text-slate-400 hover:bg-red-50 hover:text-red-500 disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            删除
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* 固定底部按钮 */}
        <div className="flex-shrink-0 flex gap-2 border-t px-6 py-3.5" style={{ borderColor: '#E9EFF6' }}>
          <button
            type="button"
            onClick={onClose}
            disabled={fillLoading}
            className="cursor-pointer flex-1 rounded-xl border border-slate-200 py-2 text-sm text-slate-500 hover:bg-slate-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={fillLoading}
            className="cursor-pointer flex-1 rounded-xl py-2 text-sm font-semibold text-white disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg,#D97706,#F59E0B)' }}
          >
            {fillLoading ? '提交中…' : '提交立项审核'}
          </button>
        </div>
      </div>
    </div>
  )
}
