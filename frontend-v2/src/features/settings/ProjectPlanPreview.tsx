import type { ProjectWorkProgressTaskDraft } from '../../api/projects'
import type { TaskItem, ProjectMember } from '../../types'
import type { SubTaskWithParent } from '../../api/subtasks'

export function buildPlanPreviewTasks(tasks: TaskItem[], subtasks: SubTaskWithParent[], members: ProjectMember[]): ProjectWorkProgressTaskDraft[] {
  const names = new Map(members.map((member) => [member.person_id, member.person_name_snapshot]))
  const period = (value: string | undefined) => (value ?? '').split(/\s*(?:~|至|到)\s*/)
  return tasks.map((task) => ({ id: task.id, title: task.key_task, goal: task.key_achievement || '', acceptance_criteria: task.completion_standard || '', process: task.plan_process || '',
    subtasks: subtasks.filter((sub) => sub.parent_task_id === task.id || sub.task_id === task.id).map((sub) => ({
      id: sub.id, title: sub.title, assignee: sub.assignee, evaluation_standard: sub.completion_criteria,
      helper: (sub.collaborator_ids ?? []).map((id) => names.get(id) ?? `人员 ${id}`).join('、') || ((sub.notes ?? '').startsWith('协助人：') ? (sub.notes ?? '').slice(4) : ''),
      plan_start: sub.start_date || period(sub.plan_time)[0] || '', plan_end: sub.due_date || period(sub.plan_time)[1] || '',
    })),
  }))
}

export function ProjectPlanPreview({ tasks }: { tasks: ProjectWorkProgressTaskDraft[] }) {
  return <div className="initiation-plan-preview space-y-5" aria-label="完整工作推进方案">
    {tasks.length === 0 && <p className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">尚未填写工作计划。</p>}
    {tasks.map((task, index) => <section key={task.id ?? index} className="initiation-preview-workstream overflow-hidden rounded-xl border border-slate-200 bg-white">
      <header className="border-b border-slate-200 bg-slate-50 px-5 py-4">
        <p className="initiation-eyebrow">重点工作 {String(index + 1).padStart(2, '0')}</p><h3 className="text-base font-semibold text-slate-900">{task.title || '未命名重点工作'}</h3>
        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
          <div><dt className="text-xs text-slate-500">重点工作目标</dt><dd className="mt-1 whitespace-pre-wrap leading-6 text-slate-700">{task.goal || task.description || '待填写'}</dd></div>
          <div><dt className="text-xs text-slate-500">重点工作验收标准 / 关键成果</dt><dd className="mt-1 whitespace-pre-wrap leading-6 text-slate-700">{task.acceptance_criteria || '待填写'}</dd></div>
        </dl>
        {task.process && <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-600">推进流程：{task.process}</p>}
      </header>
      <div className="overflow-x-auto"><table className="w-full min-w-[660px] table-fixed text-left text-sm">
        <thead className="border-b border-slate-200 text-xs text-slate-500"><tr><th className="w-[28%] px-4 py-3">关键任务</th><th className="w-[13%] px-3 py-3">负责人</th><th className="w-[14%] px-3 py-3">协助人</th><th className="w-[20%] px-3 py-3">时间段</th><th className="w-[25%] px-3 py-3">评价指标</th></tr></thead>
        <tbody>{(task.subtasks ?? []).map((sub, subIndex) => <tr key={sub.id ?? subIndex} className="border-b border-slate-100 align-top last:border-0"><td className="break-words px-4 py-3 font-medium text-slate-800">{sub.title || '待填写'}</td><td className="break-words px-3 py-3">{sub.assignee || '待指定'}</td><td className="break-words px-3 py-3">{sub.helper || '—'}</td><td className="px-3 py-3 text-xs leading-5 text-slate-600">{sub.plan_start || '开始日期待定'}<br />至 {sub.plan_end || '结束日期待定'}</td><td className="whitespace-pre-wrap break-words px-3 py-3 leading-6 text-slate-600">{sub.evaluation_standard || '待填写'}</td></tr>)}</tbody>
      </table></div>
    </section>)}
  </div>
}
