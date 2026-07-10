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
      <div
        className="flex max-h-[92vh] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
        style={{ width: 'min(1280px, 96vw)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── 固定标题栏 ── */}
        <div className="flex-shrink-0 border-b px-8 py-3.5" style={{ borderColor: '#E9EFF6' }}>
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <div className="text-base font-bold text-slate-800">填写立项信息 — {project.name}</div>
              <div className="mt-0.5 text-xs leading-relaxed text-slate-500">
                补全项目资料并维护工作推进表雏形，提交后由企业教练审核。
              </div>
            </div>
            <span className="flex-shrink-0 rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-medium text-slate-500">
              状态：待负责人完善
            </span>
          </div>
        </div>

        {/* ── 左右分栏主体 (flex-1 + min-h-0 让双栏各自滚动) ── */}
        <div className="flex flex-1 min-h-0">
          {/* 左栏：项目基础信息 */}
          <div
            className="flex-shrink-0 overflow-y-auto border-r px-6 py-4"
            style={{ width: '380px', borderColor: '#E9EFF6' }}
          >
            <div className="mb-3 flex items-center gap-2">
              <div className="h-3 w-0.5 rounded-full bg-slate-400" />
              <div className="text-xs font-bold uppercase tracking-wider text-slate-500">项目基础信息</div>
            </div>

            <div className="space-y-2.5">
              {FIELDS.map(({ key, label, placeholder }) => {
                const isLongText = key === 'background' || key === 'objectives' || key === 'expected_outcomes'
                const isDate = key === 'start_date' || key === 'end_date'

                if (isDate) {
                  // 日期在同一行内相邻展示
                  if (key === 'start_date') {
                    return (
                      <div key="dates" className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="mb-1 block text-[11px] font-semibold text-slate-500">{label}</label>
                          <input
                            type="date"
                            value={(fillForm as any)[key] ?? ''}
                            onChange={(e) => setFillForm((prev) => ({ ...prev, [key]: e.target.value }))}
                            className="w-full rounded-md border border-slate-200 bg-slate-50/50 px-2.5 py-2 text-sm text-slate-600 placeholder:text-slate-400 focus:border-slate-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-slate-300"
                          />
                        </div>
                        <div>
                          <label className="mb-1 block text-[11px] font-semibold text-slate-500">结束日期</label>
                          <input
                            type="date"
                            value={(fillForm as any)['end_date'] ?? ''}
                            onChange={(e) => setFillForm((prev) => ({ ...prev, end_date: e.target.value }))}
                            className="w-full rounded-md border border-slate-200 bg-slate-50/50 px-2.5 py-2 text-sm text-slate-600 placeholder:text-slate-400 focus:border-slate-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-slate-300"
                          />
                        </div>
                      </div>
                    )
                  }
                  return null
                }

                if (isLongText) {
                  return (
                    <div key={key}>
                      <label className="mb-1 block text-[11px] font-semibold text-slate-500">{label}</label>
                      <textarea
                        value={(fillForm as any)[key] ?? ''}
                        onChange={(e) => setFillForm((prev) => ({ ...prev, [key]: e.target.value }))}
                        placeholder={placeholder}
                        rows={2}
                        className="w-full resize-none rounded-md border border-slate-200 bg-slate-50/50 px-3 py-2 text-sm placeholder:text-slate-400 focus:border-slate-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-slate-300"
                      />
                    </div>
                  )
                }
                return (
                  <div key={key}>
                    <label className="mb-1 block text-[11px] font-semibold text-slate-500">{label}</label>
                    <input
                      type="text"
                      value={(fillForm as any)[key] ?? ''}
                      onChange={(e) => setFillForm((prev) => ({ ...prev, [key]: e.target.value }))}
                      placeholder={placeholder}
                      className="w-full rounded-md border border-slate-200 bg-slate-50/50 px-3 py-2 text-sm placeholder:text-slate-400 focus:border-slate-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-slate-300"
                    />
                  </div>
                )
              })}
            </div>
          </div>

          {/* 右栏：工作推进表雏形 */}
          <div className="flex min-w-0 flex-1 flex-col overflow-y-auto px-6 py-4">
            {/* 标题行 */}
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-3 w-0.5 rounded-full bg-amber-400" />
                <div className="text-xs font-bold uppercase tracking-wider text-slate-500">工作推进表雏形</div>
              </div>
              <button
                type="button"
                onClick={addTaskDraft}
                className="cursor-pointer flex-shrink-0 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-amber-600 transition-colors hover:border-amber-300 hover:bg-amber-50"
              >
                + 新增重点工作
              </button>
            </div>
            <p className="mb-3 text-[11px] leading-relaxed text-slate-400">
              重点工作用于归类工作方向；关键任务才需要明确责任人、协助人和计划时间。
            </p>

            {/* 重点工作列表 */}
            <div className="space-y-3">
              {draftTasks.map((task, taskIndex) => (
                <div key={taskIndex} className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                  {/* 组头 */}
                  <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/70 px-4 py-1.5">
                    <div className="text-xs font-semibold text-slate-600">重点工作 {taskIndex + 1}</div>
                    <button
                      type="button"
                      onClick={() => removeTaskDraft(taskIndex)}
                      disabled={draftTasks.length <= 1}
                      className="cursor-pointer text-[11px] text-slate-400 transition-colors hover:text-slate-600 disabled:cursor-not-allowed disabled:opacity-30"
                    >
                      删除
                    </button>
                  </div>

                  {/* 标题 + 说明 */}
                  <div className="grid gap-2 px-4 py-2 md:grid-cols-2">
                    <input
                      value={task.title}
                      onChange={(e) => updateTaskDraft(taskIndex, 'title', e.target.value)}
                      placeholder="重点工作标题（如：开发并应用项目运营系统）"
                      className="rounded border border-slate-200 bg-slate-50/50 px-2.5 py-1.5 text-sm placeholder:text-slate-400 focus:border-slate-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-slate-300"
                    />
                    <input
                      value={task.description}
                      onChange={(e) => updateTaskDraft(taskIndex, 'description', e.target.value)}
                      placeholder="重点工作说明 / 评价标准"
                      className="rounded border border-slate-200 bg-slate-50/50 px-2.5 py-1.5 text-sm placeholder:text-slate-400 focus:border-slate-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-slate-300"
                    />
                  </div>

                  {/* 关键任务表格 */}
                  <div className="border-t border-slate-100 px-4 py-2">
                    <div className="mb-1.5 flex items-center justify-between">
                      <div className="text-xs font-semibold text-slate-500">关键任务</div>
                      <button
                        type="button"
                        onClick={() => addSubTaskDraft(taskIndex)}
                        className="cursor-pointer text-[11px] font-medium text-amber-600 transition-colors hover:text-amber-700"
                      >
                        + 新增
                      </button>
                    </div>

                    {/* 表头 */}
                    <div className="mb-1 grid grid-cols-[1fr_1fr_72px_72px_1fr_1fr_20px] gap-1 px-0.5">
                      <span className="text-[10px] font-semibold text-slate-400">关键任务</span>
                      <span className="text-[10px] font-semibold text-slate-400">评价标准</span>
                      <span className="text-[10px] font-semibold text-slate-400">责任人</span>
                      <span className="text-[10px] font-semibold text-slate-400">协助人</span>
                      <span className="text-[10px] font-semibold text-slate-400">开始</span>
                      <span className="text-[10px] font-semibold text-slate-400">结束</span>
                      <span />
                    </div>

                    {/* 数据行 */}
                    {task.subtasks.map((subtask, subIndex) => (
                      <div
                        key={subIndex}
                        className="mb-1 grid grid-cols-[1fr_1fr_72px_72px_1fr_1fr_20px] gap-1"
                      >
                        <input
                          value={subtask.title}
                          onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'title', e.target.value)}
                          placeholder="标题"
                          className="min-w-0 rounded border border-slate-200 bg-slate-50/50 px-1.5 py-1 text-[11px] placeholder:text-slate-400 focus:border-slate-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-slate-300"
                        />
                        <input
                          value={subtask.evaluation_standard}
                          onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'evaluation_standard', e.target.value)}
                          placeholder="评价标准"
                          className="min-w-0 rounded border border-slate-200 bg-slate-50/50 px-1.5 py-1 text-[11px] placeholder:text-slate-400 focus:border-slate-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-slate-300"
                        />
                        <input
                          value={subtask.assignee}
                          onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'assignee', e.target.value)}
                          placeholder="责任人"
                          className="min-w-0 rounded border border-slate-200 bg-slate-50/50 px-1 py-1 text-[11px] placeholder:text-slate-400 focus:border-slate-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-slate-300"
                        />
                        <input
                          value={subtask.helper}
                          onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'helper', e.target.value)}
                          placeholder="协助人"
                          className="min-w-0 rounded border border-slate-200 bg-slate-50/50 px-1 py-1 text-[11px] placeholder:text-slate-400 focus:border-slate-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-slate-300"
                        />
                        <input
                          type="date"
                          value={subtask.plan_start}
                          onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'plan_start', e.target.value)}
                          aria-label="计划开始"
                          className="min-w-0 rounded border border-slate-200 bg-slate-50/50 px-1 py-1 text-[11px] text-slate-600 focus:border-slate-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-slate-300"
                        />
                        <div className="flex items-center gap-0.5">
                          <input
                            type="date"
                            value={subtask.plan_end}
                            onChange={(e) => updateSubTaskDraft(taskIndex, subIndex, 'plan_end', e.target.value)}
                            aria-label="计划结束"
                            className="min-w-0 flex-1 rounded border border-slate-200 bg-slate-50/50 px-1 py-1 text-[11px] text-slate-600 focus:border-slate-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-slate-300"
                          />
                          <button
                            type="button"
                            onClick={() => removeSubTaskDraft(taskIndex, subIndex)}
                            disabled={task.subtasks.length <= 1}
                            className="cursor-pointer flex-shrink-0 rounded px-0.5 text-xs leading-none text-slate-300 transition-colors hover:text-slate-500 disabled:cursor-not-allowed disabled:opacity-20"
                            title="删除"
                          >
                            ×
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── 固定底部操作栏 ── */}
        <div className="flex-shrink-0 flex items-center justify-end gap-3 border-t px-8 py-3" style={{ borderColor: '#E9EFF6' }}>
          <button
            type="button"
            onClick={onClose}
            disabled={fillLoading}
            className="cursor-pointer rounded-lg px-5 py-2 text-sm text-slate-500 transition-colors hover:bg-slate-50 disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={fillLoading}
            className="cursor-pointer rounded-lg px-6 py-2 text-sm font-semibold text-white transition-colors disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg,#D97706,#F59E0B)' }}
          >
            {fillLoading ? '提交中…' : '提交立项审核'}
          </button>
        </div>
      </div>
    </div>
  )
}
