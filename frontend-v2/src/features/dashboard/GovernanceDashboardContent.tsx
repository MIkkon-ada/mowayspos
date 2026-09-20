import type { GovernanceAction, GovernanceDashboardOverview, GovernanceInitiative } from '../../types'
import { actionMeta, healthLabel, healthTone } from './governanceDashboard'

export type ProjectHealthRow = {
  id: number
  name: string
  nextMilestone: string
  health: 'healthy' | 'watch' | 'risk' | 'unstarted'
}

type Props = {
  governance: GovernanceDashboardOverview
  projectHealthRows: ProjectHealthRow[]
  onOpenAction: (action: GovernanceAction) => void
  onOpenProject: (projectId: number) => void
  onOpenInitiative: (initiative: GovernanceInitiative) => void
}

const actionDisplay = {
  decision: { label: '需高层决策', helper: '影响关键节点', role: '推动：高层', tone: 'red' },
  coordination: { label: '需 PM 协调', helper: '跨部门依赖', role: '推动：PM', tone: 'amber' },
  owner_confirmation: { label: '待责任人确认', helper: 'AI 草稿已就绪', role: '推动：责任人', tone: 'violet' },
} as const

const signalCards = [
  { kind: 'decision' as const, value: (governance: GovernanceDashboardOverview) => governance.signals.pending_decisions },
  { kind: 'coordination' as const, value: (governance: GovernanceDashboardOverview) => governance.signals.pending_coordination },
  { kind: 'owner_confirmation' as const, value: (governance: GovernanceDashboardOverview) => governance.signals.pending_owner_confirmation },
]

function SignalIcon({ tone }: { tone: 'red' | 'amber' | 'violet' }) {
  const glyph = tone === 'red' ? '!' : tone === 'amber' ? '↗' : '✓'
  const className = tone === 'red'
    ? 'bg-red-50 text-red-600'
    : tone === 'amber'
      ? 'bg-amber-50 text-amber-600'
      : 'bg-violet-50 text-violet-600'
  return <span className={`grid h-10 w-10 place-items-center rounded-xl text-lg font-bold ${className}`} aria-hidden="true">{glyph}</span>
}

function initial(name: string) {
  return name.trim().slice(0, 1) || '—'
}

export function GovernanceDashboardContent({ governance, projectHealthRows, onOpenAction, onOpenProject, onOpenInitiative }: Props) {
  return (
    <div className="space-y-5">
      <section aria-label="当前需要关注">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-800">当前需要关注</h2>
          <span className="text-xs text-slate-400">管理信号</span>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {signalCards.map(({ kind, value }) => {
            const display = actionDisplay[kind]
            return (
              <div key={kind} className="flex min-h-24 items-center gap-3 rounded-2xl border border-[#E9EFF6] bg-white p-4 shadow-sm">
                <SignalIcon tone={display.tone} />
                <div>
                  <p className="text-xs font-medium text-slate-500">{display.label}</p>
                  <p className="mt-1 text-3xl font-bold leading-none text-slate-800">{value(governance)}</p>
                </div>
                <span className="ml-auto self-end text-xs text-slate-400">{display.helper}</span>
              </div>
            )
          })}
        </div>
      </section>

      <section aria-label="执行治理概览" className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(300px,0.7fr)]">
        <article className="rounded-2xl border border-[#E9EFF6] bg-white shadow-sm">
          <div className="flex items-center justify-between px-5 pb-3 pt-5">
            <h2 className="text-sm font-bold text-slate-800">需要处理</h2>
            <span className="text-xs font-medium text-blue-500">查看全部 →</span>
          </div>
          {governance.actions.length ? (
            <div>
              {governance.actions.map((action) => {
                const display = actionDisplay[action.kind]
                const dotClass = display.tone === 'red' ? 'bg-red-500' : display.tone === 'amber' ? 'bg-amber-500' : 'bg-violet-500'
                return (
                  <button key={`${action.kind}-${action.id}`} type="button" onClick={() => onOpenAction(action)} className="grid w-full grid-cols-[8px_minmax(0,1fr)_auto] items-center gap-3 border-t border-slate-100 px-5 py-3.5 text-left hover:bg-slate-50">
                    <span className={`h-2 w-2 rounded-full ${dotClass}`} aria-hidden="true" />
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-semibold text-slate-700">{action.title}</span>
                      <span className="mt-1 block text-xs text-slate-400">{actionMeta(action)}</span>
                    </span>
                    <span className="rounded-md bg-slate-50 px-2 py-1 text-xs font-medium text-slate-500">{display.role}</span>
                  </button>
                )
              })}
            </div>
          ) : <p className="border-t border-slate-100 px-5 py-5 text-center text-xs text-slate-400">当前无待处理治理事项</p>}
        </article>

        <article className="rounded-2xl border border-[#E9EFF6] bg-white shadow-sm">
          <div className="flex items-center justify-between px-5 pb-3 pt-5">
            <h2 className="text-sm font-bold text-slate-800">项目健康</h2>
            <span className="text-xs font-medium text-blue-500">项目组合 →</span>
          </div>
          {projectHealthRows.length ? (
            <div className="px-5 pb-3">
              {projectHealthRows.map((project) => (
                <button key={project.id} type="button" onClick={() => onOpenProject(project.id)} className="flex w-full items-center gap-2 border-t border-slate-100 py-3 text-left hover:text-blue-600">
                  <span className={`h-2 w-2 rounded-full ${project.health === 'risk' ? 'bg-red-500' : project.health === 'watch' ? 'bg-amber-500' : project.health === 'healthy' ? 'bg-emerald-500' : 'bg-slate-400'}`} aria-hidden="true" />
                  <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium text-slate-700">{project.name}</span><span className="mt-1 block truncate text-xs text-slate-400">下个节点：{project.nextMilestone || '未设置'}</span></span>
                  <span className={`rounded-full px-2 py-1 text-xs font-semibold ${healthTone(project.health)}`}>{healthLabel(project.health)}</span>
                </button>
              ))}
            </div>
          ) : <p className="border-t border-slate-100 px-5 py-5 text-center text-xs text-slate-400">暂无项目健康数据</p>}
        </article>
      </section>

      <section aria-label="重点 Initiative" className="overflow-hidden rounded-2xl border border-[#E9EFF6] bg-white shadow-sm">
        <div className="flex items-center justify-between px-5 pb-4 pt-5">
          <div><h2 className="text-sm font-bold text-slate-800">重点 Initiative</h2><p className="mt-1 text-xs text-slate-400">责任、协同、确认状态和下个节点</p></div>
          <span className="text-xs font-medium text-blue-500">全部 Initiative →</span>
        </div>
        {governance.initiatives.length ? (
          <div className="overflow-x-auto">
            <div className="min-w-[760px]">
              <div className="grid grid-cols-[minmax(190px,1.5fr)_minmax(150px,1fr)_90px_110px_minmax(140px,1fr)_80px] gap-3 bg-slate-50 px-5 py-2.5 text-xs text-slate-400">
                <span>Initiative</span><span>结果责任 / 协同</span><span>正式进展</span><span>Evidence</span><span>下个节点</span><span>状态</span>
              </div>
              {governance.initiatives.map((initiative) => (
                <button key={`${initiative.project_id ?? 'none'}-${initiative.key_task_id}`} type="button" onClick={() => onOpenInitiative(initiative)} className="grid w-full grid-cols-[minmax(190px,1.5fr)_minmax(150px,1fr)_90px_110px_minmax(140px,1fr)_80px] items-center gap-3 border-t border-slate-100 px-5 py-3.5 text-left hover:bg-slate-50">
                  <span className="min-w-0"><span className="block truncate text-xs text-slate-400">{initiative.workstream_title || '未归属重点工作'}</span><span className="mt-1 block truncate text-sm font-semibold text-slate-700">{initiative.title}</span></span>
                  <span className="flex min-w-0 items-center gap-2"><span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-blue-50 text-xs font-bold text-blue-600">{initial(initiative.accountable_owner)}</span><span className="truncate text-xs font-medium text-slate-600">{initiative.accountable_owner || '未指定'}</span><span className="flex shrink-0 -space-x-1">{initiative.collaborators.slice(0, 3).map((person) => <span key={`${initiative.key_task_id}-${person.id ?? person.name}`} className="grid h-5 w-5 place-items-center rounded-full border-2 border-white bg-slate-100 text-[10px] font-bold text-slate-500">{initial(person.name)}</span>)}</span><span className="shrink-0 text-xs text-slate-400">{initiative.collaborators.length ? `协同 ${initiative.collaborators.length}` : '—'}</span></span>
                  <span className="text-sm font-semibold text-slate-700">{initiative.official_progress === null ? '—' : `${initiative.official_progress}%`}</span>
                  <span className="text-xs font-medium text-emerald-700">{initiative.evidence_total ? `${initiative.evidence_confirmed}/${initiative.evidence_total}` : '—'}</span>
                  <span className="min-w-0"><span className="block truncate text-xs font-medium text-slate-600">{initiative.next_milestone || '未设置'}</span><span className="mt-1 block text-xs text-slate-400">{initiative.next_milestone_at || '—'}</span></span>
                  <span className={`justify-self-start rounded-full px-2 py-1 text-xs font-semibold ${healthTone(initiative.health)}`}>{healthLabel(initiative.health)}</span>
                </button>
              ))}
            </div>
          </div>
        ) : <p className="border-t border-slate-100 px-5 py-5 text-center text-xs text-slate-400">暂无可展示的关键任务</p>}
      </section>
    </div>
  )
}
