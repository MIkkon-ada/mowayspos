import type { ProjectWorkbenchOverviewStats } from './projectsWorkbench'

type OverviewCard = {
  key: keyof ProjectWorkbenchOverviewStats
  label: string
  valueClassName?: string
}

const OVERVIEW_CARDS: OverviewCard[] = [
  { key: 'all', label: '全部项目' },
  { key: 'toComplete', label: '待完善', valueClassName: 'text-amber-600' },
  { key: 'toApprove', label: '待审批', valueClassName: 'text-violet-600' },
  { key: 'active', label: '进行中', valueClassName: 'text-emerald-600' },
  { key: 'archived', label: '已归档', valueClassName: 'text-slate-600' },
]

export function ProjectOverviewStats({ stats }: { stats: ProjectWorkbenchOverviewStats }) {
  return (
    <section aria-label="项目状态概览" className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {OVERVIEW_CARDS.map((card) => (
        <div key={card.key} className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <div className="text-xs font-medium text-slate-500">{card.label}</div>
          <div className={`mt-1 text-2xl font-bold tracking-tight ${card.valueClassName ?? 'text-slate-900'}`}>
            {stats[card.key]}
          </div>
        </div>
      ))}
    </section>
  )
}
