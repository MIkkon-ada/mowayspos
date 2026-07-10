import { useState } from 'react'
import { ownerSubmitProfile } from '../../api/projects'
import type { ProjectProfilePayload } from '../../api/projects'
import { createTask } from '../../api/tasks'
import { toast } from '../../utils/toast'
import type { Project } from '../../types'

/**
 * 负责人立项填报弹窗（复用组件）。
 * DashboardPage 与 ProjectsMgmtSection 共用，避免两套不一致逻辑。
 *
 * 提交时：先批量创建重点工作(createTask)，再调用 ownerSubmitProfile 进入企业教练审核。
 */
type Props = {
  project: Project
  onClose: () => void
  onSuccess?: (result: Project & { submitted_for_review: boolean }) => void
}

const FIELDS: { key: keyof ProjectProfilePayload; label: string; placeholder: string }[] = [
  { key: 'project_type', label: '项目类型', placeholder: '博维内部项目 / 博维-客户项目' },
  { key: 'client_name', label: '客户名称', placeholder: '客户/甲方名称（内部项目可留空）' },
  { key: 'background', label: '项目背景', placeholder: '说明项目的背景和来源…' },
  { key: 'objectives', label: '项目目标', placeholder: '描述需要达成的目标…' },
  { key: 'expected_outcomes', label: '预期交付物', placeholder: '列出预期的交付成果…' },
  { key: 'start_date', label: '开始日期', placeholder: '' },
  { key: 'end_date', label: '结束日期', placeholder: '' },
]

export function OwnerSubmitModal({ project, onClose, onSuccess }: Props) {
  const [fillForm, setFillForm] = useState<ProjectProfilePayload>(() => ({
    project_type: (project as any).project_type ?? '',
    client_name: (project as any).client_name ?? '',
    background: (project as any).background ?? '',
    objectives: (project as any).objectives ?? '',
    expected_outcomes: (project as any).expected_outcomes ?? '',
    start_date: (project as any).start_date ?? '',
    end_date: (project as any).end_date ?? '',
  }))
  const [inlineTasks, setInlineTasks] = useState<{ key_task: string; plan_time: string }[]>([
    { key_task: '', plan_time: '' },
  ])
  const [fillLoading, setFillLoading] = useState(false)

  function addInlineTask() {
    setInlineTasks((prev) => [...prev, { key_task: '', plan_time: '' }])
  }
  function removeInlineTask(i: number) {
    setInlineTasks((prev) => prev.filter((_, idx) => idx !== i))
  }
  function updateInlineTask(i: number, field: 'key_task' | 'plan_time', val: string) {
    setInlineTasks((prev) => prev.map((t, idx) => (idx === i ? { ...t, [field]: val } : t)))
  }

  async function handleSubmit() {
    if (!project?.id) return
    const validTasks = inlineTasks.filter((t) => t.key_task.trim())
    if (validTasks.length === 0) {
      toast.error('请至少添加一条重点工作')
      return
    }
    setFillLoading(true)
    try {
      for (const t of validTasks) {
        await createTask({
          project_id: project.id,
          key_task: t.key_task.trim(),
          plan_time: t.plan_time.trim() || undefined,
        })
      }
      const result = await ownerSubmitProfile(project.id, fillForm)
      if (result.submitted_for_review) {
        toast.success('已提交审核，等待企业教练审核通过后正式启动')
      } else {
        toast.success('立项信息已提交，项目已自动启动')
      }
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
      <div className="bg-white rounded-2xl shadow-2xl w-[520px] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="px-6 py-4 border-b" style={{ borderColor: '#E9EFF6' }}>
          <div className="text-sm font-bold text-slate-800">填写立项信息 — {project.name}</div>
          <div className="text-xs text-slate-400 mt-0.5">提交后进入企业教练审核</div>
        </div>
        <div className="px-6 py-5 space-y-3 overflow-y-auto" style={{ maxHeight: '65vh' }}>
          {FIELDS.map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="block text-xs font-semibold text-slate-600 mb-1">{label}</label>
              <input
                type={key.includes('date') ? 'date' : 'text'}
                value={(fillForm as any)[key] ?? ''}
                onChange={(e) => setFillForm((prev) => ({ ...prev, [key]: e.target.value }))}
                placeholder={placeholder}
                className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/30"
              />
            </div>
          ))}

          <div className="pt-1">
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-slate-600">
                重点工作 <span className="text-red-400">*</span>
              </label>
              <button
                type="button"
                onClick={addInlineTask}
                className="cursor-pointer text-xs text-amber-600 font-semibold hover:text-amber-700"
              >
                + 添加任务
              </button>
            </div>
            <div className="space-y-2">
              {inlineTasks.map((t, i) => (
                <div key={i} className="flex gap-2 items-center">
                  <input
                    value={t.key_task}
                    onChange={(e) => updateInlineTask(i, 'key_task', e.target.value)}
                    placeholder="重点工作名称（必填）"
                    className="flex-1 border border-slate-200 rounded-xl px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/30"
                  />
                  <input
                    value={t.plan_time}
                    onChange={(e) => updateInlineTask(i, 'plan_time', e.target.value)}
                    placeholder="计划时间"
                    className="w-28 border border-slate-200 rounded-xl px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/30"
                  />
                  <button
                    type="button"
                    onClick={() => removeInlineTask(i)}
                    className="cursor-pointer w-6 h-6 flex items-center justify-center rounded-full text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors text-base leading-none flex-shrink-0"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="flex gap-2 px-6 pb-5 pt-1">
          <button
            type="button"
            onClick={onClose}
            disabled={fillLoading}
            className="cursor-pointer flex-1 py-2 rounded-xl border border-slate-200 text-slate-500 text-sm hover:bg-slate-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={fillLoading}
            className="cursor-pointer flex-1 py-2 rounded-xl text-white text-sm font-semibold disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg,#D97706,#F59E0B)' }}
          >
            {fillLoading ? '提交中…' : '提交'}
          </button>
        </div>
      </div>
    </div>
  )
}
