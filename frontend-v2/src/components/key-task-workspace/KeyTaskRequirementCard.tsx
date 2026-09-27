import type { KeyTaskWorkspace } from '../../api/keyTaskWorkspace'

export function KeyTaskRequirementCard({ workspace }: { workspace: KeyTaskWorkspace }) {
  const definition = workspace.key_task.completion_definition.trim()
  return <section
    aria-label="任务完成标准"
    className={`rounded-xl border px-5 py-4 shadow-sm sm:px-6 ${definition ? 'border-sky-200 bg-sky-50/70' : 'border-amber-300 bg-amber-50'}`}
  >
    <div className="flex items-start gap-3">
      <span aria-hidden="true" className={`mt-0.5 grid size-7 shrink-0 place-items-center rounded-full text-sm font-bold ${definition ? 'bg-sky-100 text-sky-800' : 'bg-amber-100 text-amber-800'}`}>
        {definition ? '准' : '!'}
      </span>
      <div className="min-w-0">
        <h2 className={`text-sm font-bold ${definition ? 'text-sky-950' : 'text-amber-950'}`}>完成标准</h2>
        {definition
          ? <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-800">{definition}</p>
          : <p className="mt-1 text-sm leading-6 text-amber-900">这项任务还没有填写完成标准。开始执行前，建议联系项目负责人确认交付要求。</p>}
      </div>
    </div>
  </section>
}
