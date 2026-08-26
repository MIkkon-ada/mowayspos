import { getProjectPrimaryStatus, getProjectStatusBadge } from '../../domain/projectLifecycleStatus'
import { getProjectLifecycleStage, type ProjectTodo, type ProjectTodoAction } from './projectsWorkbench'

export type ProjectTodoViewModel = {
  todo: ProjectTodo
  ownerName: string
  coachName: string
}

export function ProjectTodoSection({
  items,
  totalCount,
  onAction,
  onShowAll,
}: {
  items: ProjectTodoViewModel[]
  totalCount: number
  onAction: (todo: ProjectTodo, action?: ProjectTodoAction) => void
  onShowAll?: () => void
}) {
  if (totalCount === 0) return null

  return (
    <section aria-label="待我处理" className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900">待我处理</h2>
            <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-bold text-red-600">{totalCount}</span>
          </div>
          <p className="mt-1 text-sm text-slate-500">这些项目需要您当前处理</p>
        </div>
        {totalCount > items.length && onShowAll && (
          <button type="button" onClick={onShowAll} className="text-sm font-semibold text-sky-700 hover:text-sky-800">
            查看全部待处理
          </button>
        )}
      </div>

      <div className="mt-4 space-y-3">
        {items.map(({ todo, ownerName, coachName }) => {
          const status = getProjectPrimaryStatus(todo.project)
          const badge = getProjectStatusBadge(todo.project)
          const stage = getProjectLifecycleStage(status)
          const missingCount = todo.materialChecks.filter((check) => !check.complete).length
          const normalizedChecks = todo.materialChecks.map((check) => ({ ...check, label: check.label.trim() })).filter((check) => check.label)
          const missingLabels = normalizedChecks.filter((check) => !check.complete).map((check) => check.label)
          const completedLabels = normalizedChecks.filter((check) => check.complete).map((check) => check.label)
          return (
            <article key={todo.project.id} className="relative overflow-hidden rounded-xl border border-amber-200 bg-amber-50/40 px-4 py-3">
              <div className="absolute inset-y-0 left-0 w-1 bg-amber-400" aria-hidden="true" />
              <div className="pl-1">
                <div className="project-todo-summary flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold text-amber-700">{stage.label}</span>
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${badge.className}`}>{badge.label}</span>
                    </div>
                    <h3 className="mt-1 text-base font-bold text-slate-900">{todo.project.name}</h3>
                    <p className="mt-1 text-sm font-medium text-slate-700">{todo.title}</p>
                    <p className="mt-1 text-xs leading-relaxed text-slate-500">{todo.description}</p>
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 lg:max-w-xs lg:justify-end">
                    <span>项目负责人：{ownerName || '未配置'}</span>
                    <span>Coach：{coachName || '未配置'}</span>
                  </div>
                </div>
                <div className="project-todo-action-row mt-3 flex flex-col gap-3 border-t border-amber-200 pt-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0 text-xs">
                    {todo.materialChecks.length > 0 ? (
                      <>
                        <div className={missingCount > 0 ? 'font-semibold text-amber-700' : 'font-semibold text-emerald-600'}>
                          {missingCount > 0
                            ? (missingLabels.length > 0 ? `待补充：${missingLabels.join('、')}` : `尚有 ${missingCount} 项信息待完善`)
                            : '项目计划已填写完整'}
                        </div>
                        {completedLabels.length > 0 && (
                          <div className="mt-1 text-slate-500">已完成 {completedLabels.join('、')}</div>
                        )}
                      </>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2 self-start sm:self-auto">
                    {todo.secondaryAction && todo.secondaryActionLabel && (
                      <button
                        type="button"
                        onClick={(event) => { event.stopPropagation(); onAction(todo, todo.secondaryAction) }}
                        className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
                      >
                        {todo.secondaryActionLabel}
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={(event) => { event.stopPropagation(); onAction(todo, todo.action) }}
                      className="rounded-lg bg-[#2170e4] px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#1b5fc7]"
                    >
                      {todo.actionLabel} <span aria-hidden="true">→</span>
                    </button>
                  </div>
                </div>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
