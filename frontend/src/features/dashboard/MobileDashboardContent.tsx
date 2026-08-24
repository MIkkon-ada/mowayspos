type DashboardRecord = Record<string, unknown>

export type RoleQueueType = 'pending_decisions' | 'pending_review' | 'pending_coordinator' | 'in_progress'

type Metric = {
  label: string
  value: number
  sub: string
  tone: string
  onClick?: () => void
}

export type MobileDashboardContentProps = {
  scopeOptions: Array<{ value: string; label: string }>
  selectedScope: string
  selectedMonth: string
  monthOptions: string[]
  onScopeChange: (value: string) => void
  onMonthChange: (value: string) => void
  total: number
  notStarted: number
  inProgress: number
  completed: number
  delayed: number
  paused: number
  achievements: number
  pendingDecisions: number
  canViewDecisions: boolean
  recentTasks: DashboardRecord[]
  delayedTasks: DashboardRecord[]
  roleQueue: { type: RoleQueueType; count: number; items: DashboardRecord[] }
  completionRows: Array<{ id: number; name: string; done: number; total: number; rate: number }>
  onOpenTasks: (status?: string) => void
  onOpenAchievements: () => void
  onOpenRoleQueue: (type: RoleQueueType) => void
  onOpenNotifications: () => void
  projectNotice?: { title: string; detail: string; tone: 'warning' | 'review'; actionLabel?: string }
  onOpenProjectNotice?: () => void
  formatPlanTime: (value?: string | null) => string
  projectNameFromRecord: (record: DashboardRecord) => string
}

const ROLE_QUEUE_META: Record<RoleQueueType, { title: string; empty: string; tone: string }> = {
  pending_decisions: { title: '需决策事项', empty: '暂无待决策事项', tone: 'text-red-600 bg-red-50 border-red-200' },
  pending_review: { title: '待审核内容', empty: '暂无待审核内容', tone: 'text-blue-600 bg-blue-50 border-blue-200' },
  pending_coordinator: { title: '待给出建议', empty: '暂无待处理事项', tone: 'text-violet-600 bg-violet-50 border-violet-200' },
  in_progress: { title: '流程推进中', empty: '暂无进行中提交', tone: 'text-emerald-600 bg-emerald-50 border-emerald-200' },
}

const STATUS_TONE: Record<string, string> = {
  '进行中': 'bg-blue-100 text-blue-700',
  '推进中': 'bg-blue-100 text-blue-700',
  '已完成': 'bg-emerald-100 text-emerald-700',
  '延期': 'bg-red-100 text-red-700',
  '暂缓': 'bg-amber-100 text-amber-700',
  '未开始': 'bg-slate-100 text-slate-600',
  '待审核': 'bg-violet-100 text-violet-700',
}

function text(value: unknown, fallback = '—') {
  return typeof value === 'string' && value.trim() ? value : fallback
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS_TONE[status] ?? 'bg-slate-100 text-slate-600'}`}>{status}</span>
}

function Section({ title, badge, onMore, children }: { title: string; badge?: number; onMore?: () => void; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-[#E9EFF6] bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-bold text-slate-800">{title}{badge ? <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-red-100 px-1 text-[11px] text-red-600">{badge}</span> : null}</h2>
        {onMore ? <button type="button" onClick={onMore} className="shrink-0 text-xs font-semibold text-blue-600">查看更多 →</button> : null}
      </div>
      {children}
    </section>
  )
}

export function MobileDashboardContent(props: MobileDashboardContentProps) {
  const {
    scopeOptions, selectedScope, selectedMonth, monthOptions, onScopeChange, onMonthChange,
    total, notStarted, inProgress, completed, delayed, paused, achievements, pendingDecisions, canViewDecisions,
    recentTasks, delayedTasks, roleQueue, completionRows, onOpenTasks, onOpenAchievements, onOpenRoleQueue, onOpenNotifications,
    projectNotice, onOpenProjectNotice,
    formatPlanTime, projectNameFromRecord,
  } = props
  const roleQueueMeta = ROLE_QUEUE_META[roleQueue.type]
  const roleQueueTitle = roleQueueMeta.title
  const metrics: Metric[] = [
    { label: '任务总数', value: total, sub: notStarted ? `未开始 ${notStarted} 项` : '全部已启动', tone: 'text-slate-800', onClick: () => onOpenTasks() },
    { label: '进行中', value: inProgress, sub: `占比 ${total ? Math.round(inProgress / total * 100) : 0}%`, tone: 'text-blue-600', onClick: () => onOpenTasks('推进中') },
    { label: '已完成', value: completed, sub: `完成率 ${total ? Math.round(completed / total * 100) : 0}%`, tone: 'text-emerald-600', onClick: () => onOpenTasks('已完成') },
    { label: '延期', value: delayed, sub: total ? `延期率 ${Math.round(delayed / total * 100)}%` : '无任务', tone: 'text-red-600', onClick: () => onOpenTasks('延期') },
    ...(canViewDecisions ? [{ label: '待决策', value: pendingDecisions, sub: pendingDecisions ? '需及时处理' : '暂无待决策', tone: 'text-amber-600', onClick: () => onOpenRoleQueue('pending_decisions') }] : []),
    { label: '成果数量', value: achievements, sub: '全部项目汇总', tone: 'text-violet-600', onClick: onOpenAchievements },
  ]
  const statusRows = [
    ['未启动', notStarted, 'bg-slate-500'],
    ['进行中', inProgress, 'bg-blue-600'],
    ['已完成', completed, 'bg-emerald-600'],
    ['延期', delayed, 'bg-red-600'],
    ['暂缓', paused, 'bg-amber-500'],
  ] as const

  return (
    <main className="min-[800px]:hidden min-w-0 flex-1 overflow-y-auto overflow-x-hidden bg-slate-100 p-4 pb-24">
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-base font-bold text-slate-800">首页驾驶舱</h1>
        <button type="button" onClick={onOpenNotifications} className="rounded-lg px-2 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-200">通知中心</button>
      </header>

      <div className="grid grid-cols-2 gap-2">
        <label className="sr-only" htmlFor="mobile-dashboard-scope">项目范围</label>
        <select id="mobile-dashboard-scope" value={selectedScope} onChange={(event) => onScopeChange(event.target.value)} className="min-w-0 rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs text-slate-700 outline-none focus:border-blue-400">
          {scopeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <label className="sr-only" htmlFor="mobile-dashboard-month">月份</label>
        <select id="mobile-dashboard-month" value={selectedMonth} onChange={(event) => onMonthChange(event.target.value)} className="min-w-0 rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs text-slate-700 outline-none focus:border-blue-400">
          <option value="">全部月份</option>
          {monthOptions.map((month) => <option key={month} value={month}>{month}</option>)}
        </select>
      </div>

      {projectNotice ? <section className={`mt-4 rounded-2xl border p-4 ${projectNotice.tone === 'warning' ? 'border-amber-200 bg-amber-50' : 'border-violet-200 bg-violet-50'}`}><p className={`text-sm font-semibold ${projectNotice.tone === 'warning' ? 'text-amber-800' : 'text-violet-800'}`}>{projectNotice.title}</p><p className={`mt-1 text-xs leading-5 ${projectNotice.tone === 'warning' ? 'text-amber-700' : 'text-violet-700'}`}>{projectNotice.detail}</p>{projectNotice.actionLabel && onOpenProjectNotice ? <button type="button" onClick={onOpenProjectNotice} className="mt-3 rounded-lg bg-amber-600 px-3 py-2 text-xs font-semibold text-white">{projectNotice.actionLabel}</button> : null}</section> : null}

      <section className="mt-4 grid grid-cols-2 gap-2" aria-label="风险与待办">
        <button type="button" onClick={() => onOpenTasks('延期')} className="rounded-2xl border border-red-200 bg-red-50 p-4 text-left text-red-700">
          <span className="text-xs font-semibold">延期任务</span>
          <strong className="mt-1 block text-3xl leading-none">{delayed}</strong>
          <span className="mt-2 block text-xs text-red-600">立即处理</span>
        </button>
        <button type="button" onClick={() => onOpenRoleQueue(roleQueue.type)} className={`rounded-2xl border p-4 text-left ${roleQueueMeta.tone}`}>
          <span className="text-xs font-semibold">{roleQueueTitle}</span>
          <strong className="mt-1 block text-3xl leading-none">{roleQueue.count}</strong>
          <span className="mt-2 block text-xs">角色待办</span>
        </button>
      </section>

      <Section title="任务概览">
        <div className="grid grid-cols-3 gap-1 divide-x divide-slate-100">
          {metrics.slice(0, 3).map((metric) => <button key={metric.label} type="button" onClick={metric.onClick} className="min-w-0 px-1 text-center"><strong className={`block text-xl ${metric.tone}`}>{metric.value}</strong><span className="mt-1 block text-[11px] text-slate-500">{metric.label}</span></button>)}
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2">
          {metrics.slice(3).map((metric) => <button key={metric.label} type="button" onClick={metric.onClick} className="rounded-xl bg-slate-50 px-2 py-2 text-left"><span className="block text-[11px] text-slate-500">{metric.label}</span><strong className={`mt-1 block text-base ${metric.tone}`}>{metric.value}</strong><span className="mt-1 block truncate text-[10px] text-slate-400">{metric.sub}</span></button>)}
        </div>
      </Section>

      <div className="mt-4 space-y-4">
        <Section title="本月重点" onMore={() => onOpenTasks()}>
          {recentTasks.length ? <div className="space-y-2">{recentTasks.slice(0, 3).map((task, index) => <button key={String(task.id ?? index)} type="button" onClick={() => onOpenTasks()} className="flex w-full items-start gap-2 rounded-xl p-2 text-left hover:bg-slate-50"><span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-blue-100 text-[11px] font-bold text-blue-600">{index + 1}</span><span className="min-w-0 flex-1"><span className="block line-clamp-2 text-xs font-semibold leading-5 text-slate-700">{text(task.key_task, '任务项')}</span><span className="mt-0.5 block text-[11px] text-slate-400">{text(task.owner, '')}</span></span><StatusBadge status={text(task.status, '进行中')} /></button>)}</div> : <p className="py-3 text-center text-xs text-slate-400">暂无数据</p>}
        </Section>

        <Section title="延迟任务" badge={delayed} onMore={() => onOpenTasks('延期')}>
          {delayedTasks.length ? <div className="space-y-2">{delayedTasks.slice(0, 4).map((task, index) => <button key={String(task.id ?? index)} type="button" onClick={() => onOpenTasks('延期')} className="w-full rounded-xl border border-red-100 bg-red-50/50 p-3 text-left"><span className="block line-clamp-2 text-xs font-semibold leading-5 text-slate-700">{text(task.key_task, '任务')}</span><span className="mt-1 block text-[11px] text-red-500">{task.is_overdue ? '超期' : '延期'} · {projectNameFromRecord(task)} · {text(task.owner, '—')} · {formatPlanTime(typeof task.plan_time === 'string' ? task.plan_time : null)}</span></button>)}</div> : <p className="py-3 text-center text-xs text-slate-400">暂无延期任务</p>}
        </Section>

        <Section title={roleQueueTitle} badge={roleQueue.count} onMore={() => onOpenRoleQueue(roleQueue.type)}>
          {roleQueue.items.length ? <div className="space-y-2">{roleQueue.items.slice(0, 3).map((item, index) => <button key={String(item.id ?? index)} type="button" onClick={() => onOpenRoleQueue(roleQueue.type)} className={`w-full rounded-xl border p-3 text-left ${roleQueueMeta.tone}`}><span className="block line-clamp-2 text-xs font-semibold leading-5 text-slate-700">{text(item.title ?? item.key_task ?? item.description, '提交事项')}</span><span className="mt-1 block text-[11px] text-slate-400">{text(item.submitter ?? item.owner, '')}{projectNameFromRecord(item) ? ` · ${projectNameFromRecord(item)}` : ''}</span></button>)}</div> : <p className="py-3 text-center text-xs text-slate-400">{roleQueueMeta.empty}</p>}
        </Section>

        <Section title="专项进度总览">
          {completionRows.length ? <div className="space-y-3">{completionRows.map((project) => <button key={project.id} type="button" onClick={() => onScopeChange(String(project.id))} className="block w-full text-left"><span className="flex items-center justify-between gap-3"><span className="truncate text-xs font-medium text-slate-700">{project.name}</span><span className="shrink-0 text-xs font-bold text-slate-700">{project.rate}%</span></span><span className="mt-1.5 block h-1.5 overflow-hidden rounded-full bg-slate-100"><span className="block h-full rounded-full bg-blue-500" style={{ width: `${project.rate}%` }} /></span><span className="mt-1 block text-[10px] text-slate-400">{project.total ? `${project.done}/${project.total}` : '暂无数据'}</span></button>)}</div> : <p className="py-3 text-center text-xs text-slate-400">暂无项目进度数据</p>}
        </Section>

        <Section title="任务状态分布">
          <div className="space-y-2">{statusRows.map(([label, value, tone]) => <div key={label} className="grid grid-cols-[10px_1fr_auto] items-center gap-2"><span className={`h-2.5 w-2.5 rounded-sm ${tone}`} /><span className="text-xs text-slate-600">{label}</span><strong className="text-xs text-slate-800">{value}</strong></div>)}</div>
        </Section>
      </div>
    </main>
  )
}
