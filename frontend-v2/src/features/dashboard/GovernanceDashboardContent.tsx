import { useState } from 'react'
import type { GovernanceDashboardOverview } from '../../types'

export type ProjectOverviewRow = {
  id: number
  name: string
  statusLabel: string
  statusClassName: string
  completedWorkstreams: number
  totalWorkstreams: number
  openIssues: number
  latestUpdate: string
  pendingDecisions: number
  pendingCoordination: number
}

type Focus = 'all' | 'decision' | 'coordination'
type IssueStatus = '待决策' | '待协调'

type Props = {
  governance: GovernanceDashboardOverview
  projectRows: ProjectOverviewRow[]
  onOpenProject: (projectId: number) => void
  onOpenIssueCenter: (projectId?: number, status?: IssueStatus) => void
}

function formatWorkstreamUpdate(value: string) {
  if (!value) return '暂无重点工作更新'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return `更新于 ${value.slice(0, 10)}`
  return `更新于 ${parsed.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })}`
}

export function GovernanceDashboardContent({ governance, projectRows, onOpenProject, onOpenIssueCenter }: Props) {
  const [focus, setFocus] = useState<Focus>('all')
  const decisions = governance.signals.pending_decisions
  const coordination = governance.signals.pending_coordination
  const pendingTotal = decisions + coordination
  const attentionProjects = projectRows.filter((project) => project.pendingDecisions + project.pendingCoordination > 0).length
  const visibleProjects = projectRows.filter((project) =>
    focus === 'all' || (focus === 'decision' ? project.pendingDecisions > 0 : project.pendingCoordination > 0),
  )

  const focusOptions = [
    { key: 'all' as const, label: '全部项目', count: projectRows.length },
    { key: 'decision' as const, label: '有待决策', count: projectRows.filter((project) => project.pendingDecisions > 0).length },
    { key: 'coordination' as const, label: '有待协调', count: projectRows.filter((project) => project.pendingCoordination > 0).length },
  ]

  return <div className="mx-auto max-w-[1440px] space-y-5">
    <section aria-labelledby="management-focus-title" className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-100 px-5 py-5 sm:px-6">
        <div>
          <p className="text-[11px] font-bold tracking-[0.16em] text-sky-700">管理简报</p>
          <h2 id="management-focus-title" className="mt-2 text-xl font-bold tracking-tight text-slate-900">管理层关注</h2>
          <p className="mt-1 text-sm text-slate-500">
            {pendingTotal > 0 ? `当前有 ${pendingTotal} 项待决策或待协调问题，涉及 ${attentionProjects} 个项目。` : '当前没有待决策或待协调的问题。'}
          </p>
        </div>
        <button type="button" onClick={() => onOpenIssueCenter()} className="inline-flex min-h-9 items-center rounded-lg border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition-colors hover:border-sky-300 hover:text-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-500">
          进入问题中心
        </button>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3">
        <button type="button" onClick={() => setFocus('decision')} aria-pressed={focus === 'decision'} className={`flex items-center justify-between gap-3 border-b border-r border-slate-100 px-5 py-4 text-left transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-sky-500 sm:border-b-0 sm:px-6 ${focus === 'decision' ? 'bg-rose-50/50' : ''}`}>
          <span className="text-sm font-medium text-slate-600">待决策问题</span>
          <strong className={`text-2xl tabular-nums ${decisions > 0 ? 'text-rose-700' : 'text-slate-800'}`}>{decisions}</strong>
        </button>
        <button type="button" onClick={() => setFocus('coordination')} aria-pressed={focus === 'coordination'} className={`flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4 text-left transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-sky-500 sm:border-b-0 sm:border-r sm:px-6 ${focus === 'coordination' ? 'bg-amber-50/50' : ''}`}>
          <span className="text-sm font-medium text-slate-600">待协调问题</span>
          <strong className={`text-2xl tabular-nums ${coordination > 0 ? 'text-amber-700' : 'text-slate-800'}`}>{coordination}</strong>
        </button>
        <div className="col-span-2 flex items-center justify-between gap-3 px-5 py-4 sm:col-span-1 sm:px-6">
          <span className="text-sm font-medium text-slate-600">涉及项目</span>
          <strong className="text-2xl tabular-nums text-slate-900">{attentionProjects}</strong>
        </div>
      </div>
    </section>

    <section aria-labelledby="portfolio-title" className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-slate-100 px-5 py-5 sm:px-6">
        <div>
          <h2 id="portfolio-title" className="text-lg font-bold text-slate-900">项目概况</h2>
          <p className="mt-1 text-sm text-slate-500">按项目查看管理关注点；进入问题中心处理具体问题。</p>
        </div>
        <span className="text-xs font-medium text-slate-500">当前范围 {projectRows.length} 个项目</span>
      </div>
      <div className="flex flex-wrap gap-2 border-b border-slate-100 px-5 py-3 sm:px-6" role="group" aria-label="筛选项目">
        {focusOptions.map((option) => <button key={option.key} type="button" onClick={() => setFocus(option.key)} aria-pressed={focus === option.key} className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-sky-500 ${focus === option.key ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>{option.label} <span className="ml-1 tabular-nums">{option.count}</span></button>)}
      </div>

      <div className="hidden grid-cols-[minmax(240px,1.7fr)_minmax(180px,1.1fr)_minmax(150px,1fr)_minmax(140px,1fr)_auto] gap-4 bg-slate-50 px-6 py-3 text-xs font-semibold text-slate-500 xl:grid">
        <span>项目</span><span>管理关注</span><span>重点工作</span><span>待闭环问题</span><span>最近工作更新</span>
      </div>
      {visibleProjects.length > 0 ? <div className="divide-y divide-slate-100">
        {visibleProjects.map((project) => <div key={project.id} className="grid gap-3 px-5 py-4 transition-colors hover:bg-slate-50/80 sm:grid-cols-2 sm:gap-4 sm:px-6 xl:grid-cols-[minmax(240px,1.7fr)_minmax(180px,1.1fr)_minmax(150px,1fr)_minmax(140px,1fr)_auto] xl:items-center">
          <div className="min-w-0">
            <button type="button" onClick={() => onOpenProject(project.id)} className="max-w-full text-left text-sm font-bold leading-5 text-slate-900 hover:text-sky-700 focus:outline-none focus:underline">{project.name}</button>
            <span className={`ml-2 inline-block rounded px-1.5 py-0.5 align-middle text-[11px] font-medium ${project.statusClassName}`}>{project.statusLabel}</span>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {project.pendingDecisions > 0 ? <button type="button" onClick={() => onOpenIssueCenter(project.id, '待决策')} className="rounded-md bg-rose-50 px-2 py-1 text-xs font-semibold text-rose-700 hover:bg-rose-100 focus:outline-none focus:ring-2 focus:ring-rose-400">待决策 {project.pendingDecisions}</button> : null}
            {project.pendingCoordination > 0 ? <button type="button" onClick={() => onOpenIssueCenter(project.id, '待协调')} className="rounded-md bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-700 hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-400">待协调 {project.pendingCoordination}</button> : null}
            {project.pendingDecisions + project.pendingCoordination === 0 ? <span className="text-xs text-slate-400">暂无待决策或协调问题</span> : null}
          </div>
          <p className="text-xs text-slate-600"><span className="text-slate-400 xl:hidden">重点工作： </span>{project.totalWorkstreams > 0 ? `${project.completedWorkstreams} / ${project.totalWorkstreams} 项已完成` : '尚无重点工作'}</p>
          <p className="text-xs text-slate-600"><span className="text-slate-400 xl:hidden">问题： </span>{project.openIssues > 0 ? `${project.openIssues} 项待闭环` : '暂无待闭环问题'}</p>
          <p className="text-xs text-slate-500">{formatWorkstreamUpdate(project.latestUpdate)}</p>
        </div>)}
      </div> : <div className="px-6 py-8 text-center text-sm text-slate-500">{projectRows.length === 0 ? '当前范围没有可查看的项目。' : '当前筛选下没有需要关注的项目。'}</div>}
    </section>
  </div>
}
