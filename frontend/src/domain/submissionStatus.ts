// Canonical confirm_status constants — mirrors backend app/domain/submission_status.py.
// Business logic must use these; never compare raw Chinese strings directly.

export const S_NEW                  = '待确认'
export const S_PENDING_OWNER        = '待负责人审核'
export const S_RETURNED             = '已打回提交人'
export const S_WITHDRAWN            = '已撤回'
export const S_PERMANENTLY_REJECTED = '不入库'
export const S_WAITING_COORDINATOR  = '已转交统筹人'
export const S_COORDINATOR_GIVEN    = '统筹人已反馈'
export const S_WAITING_CEO          = '待CEO决策'
export const S_CEO_DECIDED          = 'CEO已批示'
export const S_CONFIRMED            = '已入库'
export const S_NEEDS_REVISION       = '需修改'

// Legacy aliases — old DB rows and optimistic-UI patches may carry these.
// normalize() maps them to the canonical value before any business check.
const LEGACY_ALIASES: Record<string, string> = {
  '已确认':     S_CONFIRMED,
  '待入库':     S_CONFIRMED,
  '已驳回':     S_RETURNED,
  '已转交统筹': S_WAITING_COORDINATOR,
}

export function normalize(status: string | undefined | null): string {
  if (!status) return S_NEW
  return LEGACY_ALIASES[status] ?? status
}

// Business groups (mirrors backend frozensets)
export const CONFIRMED_AND_STORED         = new Set([S_CONFIRMED])
export const RETURNED_TO_SUBMITTER        = new Set([S_RETURNED])
export const WAITING_COORDINATOR_FEEDBACK = new Set([S_WAITING_COORDINATOR, S_COORDINATOR_GIVEN])
export const WAITING_CEO_DECISION         = new Set([S_WAITING_CEO])
export const PENDING_OWNER_REVIEW         = new Set([S_NEW, S_PENDING_OWNER, S_COORDINATOR_GIVEN, S_CEO_DECIDED])
export const OWNER_ACTIONABLE             = new Set([S_NEW, S_PENDING_OWNER, S_COORDINATOR_GIVEN, S_CEO_DECIDED])
export const TRANSFERABLE_TO_COORDINATOR  = new Set([S_NEW, S_PENDING_OWNER])
export const ESCALATABLE_TO_CEO           = new Set([S_NEW, S_PENDING_OWNER, S_COORDINATOR_GIVEN])
export const ALL_TERMINAL                 = new Set([S_CONFIRMED, S_WITHDRAWN, S_PERMANENTLY_REJECTED])

// Human-readable display labels (canonical value → label shown in UI)
export const DISPLAY_LABEL: Record<string, string> = {
  [S_NEW]:                  '待确认',
  [S_PENDING_OWNER]:        '待审核',
  [S_RETURNED]:             '已退回',
  [S_WITHDRAWN]:            '已撤回',
  [S_PERMANENTLY_REJECTED]: '不入库',
  [S_WAITING_COORDINATOR]:  '已转交统筹',
  [S_COORDINATOR_GIVEN]:    '统筹已反馈',
  [S_WAITING_CEO]:          '待企业教练决策',
  [S_CEO_DECIDED]:          '企业教练已批示',
  [S_CONFIRMED]:            '已入库',
  [S_NEEDS_REVISION]:       '需修改',
}

// Tailwind class pairs for status badges (canonical key)
export const STATUS_BADGE_CLASS: Record<string, string> = {
  [S_NEW]:                  'bg-amber-100 text-amber-700',
  [S_PENDING_OWNER]:        'bg-amber-100 text-amber-700',
  [S_RETURNED]:             'bg-red-100 text-red-700',
  [S_WITHDRAWN]:            'bg-slate-100 text-slate-600',
  [S_PERMANENTLY_REJECTED]: 'bg-red-100 text-red-700',
  [S_WAITING_COORDINATOR]:  'bg-purple-100 text-purple-700',
  [S_COORDINATOR_GIVEN]:    'bg-purple-100 text-purple-700',
  [S_WAITING_CEO]:          'bg-blue-100 text-blue-700',
  [S_CEO_DECIDED]:          'bg-blue-100 text-blue-700',
  [S_CONFIRMED]:            'bg-emerald-100 text-emerald-700',
  [S_NEEDS_REVISION]:       'bg-orange-100 text-orange-700',
}

// Dot colors for history timeline (canonical key)
export const STATUS_DOT_COLOR: Record<string, string> = {
  [S_NEW]:                  '#F59E0B',
  [S_PENDING_OWNER]:        '#F59E0B',
  [S_RETURNED]:             '#EF4444',
  [S_WITHDRAWN]:            '#94A3B8',
  [S_PERMANENTLY_REJECTED]: '#EF4444',
  [S_WAITING_COORDINATOR]:  '#8B5CF6',
  [S_COORDINATOR_GIVEN]:    '#8B5CF6',
  [S_WAITING_CEO]:          '#3B82F6',
  [S_CEO_DECIDED]:          '#3B82F6',
  [S_CONFIRMED]:            '#10B981',
  [S_NEEDS_REVISION]:       '#F97316',
}
