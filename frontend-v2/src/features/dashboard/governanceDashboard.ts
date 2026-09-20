import type {
  DashboardOverview,
  GovernanceAction,
  GovernanceDashboardOverview,
  GovernanceHealth,
  GovernanceInitiative,
} from '../../types'

const actionRank: Record<GovernanceAction['kind'], number> = {
  decision: 0,
  coordination: 1,
  owner_confirmation: 2,
}

const healthLabels: Record<GovernanceHealth, string> = {
  healthy: '健康',
  watch: '关注',
  risk: '风险',
  unstarted: '未启动',
}

const healthTones: Record<GovernanceHealth, string> = {
  healthy: 'text-emerald-700 bg-emerald-50',
  watch: 'text-amber-700 bg-amber-50',
  risk: 'text-red-700 bg-red-50',
  unstarted: 'text-slate-600 bg-slate-100',
}

export function emptyGovernance(): GovernanceDashboardOverview {
  return {
    signals: { pending_decisions: 0, pending_coordination: 0, pending_owner_confirmation: 0 },
    actions: [],
    initiatives: [],
  }
}

export function aggregateGovernanceOverviews(overviews: DashboardOverview[]): GovernanceDashboardOverview {
  const aggregate = emptyGovernance()
  const actions = new Map<string, GovernanceAction>()
  const initiatives = new Map<string, GovernanceInitiative>()

  for (const overview of overviews) {
    const governance = overview.governance
    if (!governance) continue
    aggregate.signals.pending_decisions += governance.signals.pending_decisions || 0
    aggregate.signals.pending_coordination += governance.signals.pending_coordination || 0
    aggregate.signals.pending_owner_confirmation += governance.signals.pending_owner_confirmation || 0

    for (const action of governance.actions) {
      actions.set(`${action.kind}:${action.id}:${action.project_id ?? 'none'}`, action)
    }
    for (const initiative of governance.initiatives) {
      initiatives.set(`${initiative.key_task_id}:${initiative.project_id ?? 'none'}`, initiative)
    }
  }

  aggregate.actions = Array.from(actions.values())
    .sort((left, right) => actionRank[left.kind] - actionRank[right.kind]
      || (left.due_at ?? '9999-12-31').localeCompare(right.due_at ?? '9999-12-31')
      || left.title.localeCompare(right.title, 'zh-CN'))
    .slice(0, 3)
  aggregate.initiatives = Array.from(initiatives.values())
    .sort((left, right) => (left.next_milestone_at ?? '9999-12-31').localeCompare(right.next_milestone_at ?? '9999-12-31')
      || left.title.localeCompare(right.title, 'zh-CN'))
    .slice(0, 6)
  return aggregate
}

export function healthLabel(health: GovernanceHealth): string {
  return healthLabels[health]
}

export function healthTone(health: GovernanceHealth): string {
  return healthTones[health]
}

export function actionMeta(action: GovernanceAction): string {
  const owner = action.accountable_owner || '未指定责任人'
  if (action.due_at) return `${owner} · 截止 ${action.due_at}`
  if (action.waiting_days !== null) return `${owner} · 已等待 ${action.waiting_days} 天`
  return owner
}
