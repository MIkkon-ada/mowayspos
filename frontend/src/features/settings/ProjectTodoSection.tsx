import { getProjectPrimaryStatus, getProjectStatusBadge } from '../../domain/projectLifecycleStatus'
import { getProjectLifecycleStage, type ProjectTodo } from './projectsWorkbench'

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
  onAction: (todo: ProjectTodo) => void
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
          return (
            <article key={todo.project.id} className="relative overflow-hidden rounded-xl border border-amber-200 bg-amber-50/40 px-4 py-3">
              <div className="absolute inset-y-0 left-0 w-1 bg-amber-400" aria-hidden="true" />
              <div className="flex flex-wrap items-start justify-between gap-3 pl-1">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold text-amber-700">{stage.label}</span>
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${badge.className}`}>{badge.label}</span>
                  </div>
                  <h3 className="mt-1 text-base font-bold text-slate-900">{todo.project.name}</h3>
                  <p className="mt-1 text-sm font-medium text-slate-700">{todo.title}</p>
                  <p className="mt-1 text-xs leading-relaxed text-slate-500">{todo.description}</p>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                    <span>项目负责人：{ownerName || '未配置'}</span>
                    <span>Coach：{coachName || '未配置'}</span>
                  </div>
                  {todo.materialChecks.length > 0 && (
                    <div className="mt-3 rounded-lg border border-amber-100 bg-white/70 px-3 py-2">
                      <div className="text-xs font-semibold text-slate-700">
                        {missingCount > 0 ? `尚有 ${missingCount} 项信息待完善` : '项目计划已填写完整'}
                      </div>
                      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                        {todo.materialChecks.map((check) => (
                          <span key={check.key} className={check.complete ? 'text-emerald-600' : 'text-amber-700'}>
                            {check.complete ? '✓' : '○'} {check.label}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={(event) => { event.stopPropagation(); onAction(todo) }}
                  className="shrink-0 self-end rounded-lg bg-[#2170e4] px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#1b5fc7]"
                >
                  {todo.actionLabel} <span aria-hidden="true">→</span>
                </button>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
