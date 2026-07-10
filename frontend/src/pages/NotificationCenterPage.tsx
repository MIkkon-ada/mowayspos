import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { fetchNotifications, fetchUnreadCount, markAllRead, markRead, type NotificationItem } from '../api/notifications'

// ── 工具：清理末尾多余标点 ────────────────────────────────────
function cleanText(s?: string | null): string {
  if (!s) return ''
  return s.trim().replace(/[，,。；;：:\s]+$/, '')
}

// ── 是否需要用户处理 ──────────────────────────────────────────
function requiresAction(type: string): boolean {
  return [
    'project_dispatch',
    'submission_rejected',
    'submission_pending',
    'issue_assigned',
    'decision_pending',
    'subtask_assigned',
    'task_assigned',
  ].includes(type)
}

// ── Tab 定义 ──────────────────────────────────────────────────
type FilterKey = 'all' | 'action' | 'info'
const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'action', label: '待我处理' },
  { key: 'info', label: '仅通知' },
]

// ── 解析 body 中的结构化字段 ──────────────────────────────────
type ParsedMeta = {
  role?: string
  operator?: string
  dateLabel?: string   // 如"启动日期"
  dateValue?: string   // 如"2026-06-25"
  deadline?: string
  detail?: string
}

function parseNotificationMeta(body: string | null | undefined): ParsedMeta {
  if (!body) return {}
  const raw = body.replace(/\s+/g, ' ').trim()

  const roleMatch = raw.match(/角色[:：]\s*([^，,；;]+)/)
  const operatorMatch = raw.match(/操作人[:：]\s*([^，,；;]+)/)
  const deadlineMatch = raw.match(/截止时间[:：]\s*([^，,；;]+)/)

  // 日期类：启动日期、下发日期等
  const dateMatch = raw.match(/([一-龥]+日期)[:：]\s*([^，,；;\s]+)/)

  let detail = raw
    .replace(/角色[:：]\s*[^，,；;]+[，,；;]?\s*/g, '')
    .replace(/操作人[:：]\s*[^，,；;]+[，,；;]?\s*/g, '')
    .replace(/截止时间[:：]\s*[^，,；;]+[，,；;]?\s*/g, '')
    .replace(/([一-龥]+日期)[:：]\s*[^，,；;\s]+[，,；;]?\s*/g, '')
    .trim()

  return {
    role: roleMatch?.[1]?.trim(),
    operator: cleanText(operatorMatch?.[1]),
    deadline: cleanText(deadlineMatch?.[1]),
    dateLabel: dateMatch?.[1],
    dateValue: cleanText(dateMatch?.[2]),
    detail: cleanText(detail) || undefined,
  }
}

// ── 前端合并：同专项同用户短时间内多条成员变更合并展示 ────────
// 注：后端应从源头合并，此处为展示层兜底
type MergedNotification = NotificationItem & { mergedRoles?: string[] }

function mergeProjectMemberNotifications(items: NotificationItem[]): MergedNotification[] {
  const result: MergedNotification[] = []
  const mergeMap = new Map<string, MergedNotification>()

  for (const item of items) {
    if (item.type === 'project_member_added' || item.type === 'project_member_changed') {
      const key = `${item.project_id}_${item.created_at?.slice(0, 10)}`
      const meta = parseNotificationMeta(item.body)
      if (mergeMap.has(key)) {
        const existing = mergeMap.get(key)!
        if (meta.role && !existing.mergedRoles?.includes(meta.role)) {
          existing.mergedRoles = [...(existing.mergedRoles ?? []), meta.role]
        }
        // 取最新的 is_read 状态（有任一未读则标记为未读）
        if (!item.is_read) existing.is_read = false
      } else {
        const merged: MergedNotification = { ...item, mergedRoles: meta.role ? [meta.role] : [] }
        mergeMap.set(key, merged)
        result.push(merged)
      }
    } else {
      result.push({ ...item })
    }
  }
  return result
}

// ── 时间分组 ──────────────────────────────────────────────────
type TimeGroup = '今天' | '昨天' | '更早'
function getTimeGroup(createdAt: string | null | undefined): TimeGroup {
  if (!createdAt) return '更早'
  const d = new Date(createdAt)
  const now = new Date()
  const todayStr = now.toDateString()
  const yesterdayStr = new Date(now.getTime() - 86400000).toDateString()
  if (d.toDateString() === todayStr) return '今天'
  if (d.toDateString() === yesterdayStr) return '昨天'
  return '更早'
}

function formatTime(s?: string | null, group?: TimeGroup): string {
  if (!s) return '-'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s.slice(0, 16).replace('T', ' ')
  const pad = (n: number) => String(n).padStart(2, '0')
  const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`
  if (group === '今天') return `今天 ${hm}`
  if (group === '昨天') return `昨天 ${hm}`
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${hm}`
}

// ── 通知类型 → 视觉配置 ───────────────────────────────────────
type ToneConfig = {
  bg: string         // icon 方块背景色
  text: string       // icon 颜色
  icon: React.ReactNode
}

function getToneConfig(type: string): ToneConfig {
  switch (type) {
    case 'project_kickoff':
      return { bg: '#EFF6FF', text: '#2563EB', icon: <IconRocket /> }
    case 'project_dispatch':
      return { bg: '#FFF7ED', text: '#EA580C', icon: <IconClipboardEdit /> }
    case 'project_member_added':
    case 'project_member_changed':
      return { bg: '#F0FDF4', text: '#16A34A', icon: <IconUsers /> }
    case 'project_archived':
      return { bg: '#F8FAFC', text: '#64748B', icon: <IconArchive /> }
    case 'project_created':
      return { bg: '#EFF6FF', text: '#2563EB', icon: <IconFolder /> }
    case 'submission_pending':
    case 'submission_confirmed':
    case 'submission_rejected':
      return { bg: '#EFF6FF', text: '#2563EB', icon: <IconCheck /> }
    case 'task_assigned':
    case 'task_updated':
    case 'subtask_assigned':
      return { bg: '#F0FDF4', text: '#16A34A', icon: <IconTask /> }
    case 'achievement_submitted':
      return { bg: '#F0FDF4', text: '#059669', icon: <IconStar /> }
    case 'issue_created':
    case 'issue_updated':
    case 'issue_assigned':
      return { bg: '#FFFBEB', text: '#D97706', icon: <IconAlert /> }
    case 'decision_pending':
    case 'decision_resolved':
      return { bg: '#FFFBEB', text: '#B45309', icon: <IconGavel /> }
    case 'meeting_created':
    case 'meeting_updated':
      return { bg: '#F5F3FF', text: '#7C3AED', icon: <IconClock /> }
    default:
      return { bg: '#F1F5F9', text: '#64748B', icon: <IconBell /> }
  }
}

// ── 图标组件 ──────────────────────────────────────────────────
function IconRocket() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 00-2.91-.09zM12 15l-3-3a22 22 0 012-3.95A12.88 12.88 0 0122 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 01-4 2z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" />
    </svg>
  )
}

function IconClipboardEdit() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
      <rect x="9" y="3" width="6" height="4" rx="1" strokeLinecap="round" strokeLinejoin="round" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h2l5-5 2 2-5 5H9v-2z" />
    </svg>
  )
}

function IconUsers() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
    </svg>
  )
}

function IconArchive() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 8v13H3V8M1 3h22v5H1zM10 12h4" />
    </svg>
  )
}

function IconFolder() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
    </svg>
  )
}

function IconCheck() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}

function IconTask() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
    </svg>
  )
}

function IconStar() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
    </svg>
  )
}

function IconAlert() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86l-8.5 15A2 2 0 003.54 22h16.92a2 2 0 001.75-3.14l-8.5-15a2 2 0 00-3.42 0z" />
    </svg>
  )
}

function IconGavel() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 6l3 1m0 0l-3 9a5 5 0 006 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5 5 0 006 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
    </svg>
  )
}

function IconClock() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6l4 2" />
    </svg>
  )
}

function IconBell() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
    </svg>
  )
}

// ── 通知卡片 ──────────────────────────────────────────────────
function NotificationCard({
  item,
  group,
  onClick,
}: {
  item: MergedNotification
  group: TimeGroup
  onClick: (item: MergedNotification) => void
}) {
  const meta = parseNotificationMeta(item.body)
  const tone = getToneConfig(item.type)
  const isAction = requiresAction(item.type)
  const roles = item.mergedRoles ?? (meta.role ? [meta.role] : [])

  // 合并成员通知的标题统一为"你已加入专项"
  const displayTitle =
    (item.type === 'project_member_added' || item.type === 'project_member_changed')
      ? item.title.replace('你已被加入', '你已加入')
      : item.title

  // 第二行：meta 信息拼成一行
  const metaParts: string[] = []
  if (roles.length > 0) metaParts.push(`当前角色：${roles.join('、')}`)
  if (meta.detail) metaParts.push(meta.detail)
  if (meta.operator) metaParts.push(`操作人：${meta.operator}`)
  if (meta.deadline) metaParts.push(`截止：${meta.deadline}`)
  if (meta.dateLabel && meta.dateValue) metaParts.push(`${meta.dateLabel}：${meta.dateValue}`)

  return (
    <button
      type="button"
      onClick={() => onClick(item)}
      className="group w-full flex items-center gap-3 rounded-lg border bg-white text-left transition hover:shadow-sm hover:border-blue-200"
      style={{
        borderColor: item.is_read ? '#E9EEF4' : '#BFDBFE',
        opacity: item.is_read ? 0.78 : 1,
        padding: '12px 14px',
        minHeight: 72,
      }}
    >
      {/* 未读蓝点 */}
      <div style={{ width: 8, flexShrink: 0, display: 'flex', justifyContent: 'center' }}>
        {!item.is_read && (
          <span className="block w-1.5 h-1.5 rounded-full mt-0.5" style={{ background: '#2563EB' }} />
        )}
      </div>

      {/* 类型图标方块 40×40 */}
      <div
        className="flex-shrink-0 flex items-center justify-center rounded-lg"
        style={{ width: 40, height: 40, background: tone.bg, color: tone.text }}
      >
        {tone.icon}
      </div>

      {/* 主体：两行 */}
      <div className="flex-1 min-w-0">
        {/* 第一行：标题 + 状态标签 */}
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="truncate text-sm"
            style={{ fontWeight: item.is_read ? 500 : 600, color: item.is_read ? '#64748B' : '#0F172A' }}
          >
            {displayTitle}
          </span>
          {isAction && !item.is_read && (
            <span className="flex-shrink-0 inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-bold leading-none"
              style={{ background: '#FEF3C7', color: '#D97706', border: '1px solid #FDE68A' }}>
              待处理
            </span>
          )}
          {!isAction && (
            <span className="flex-shrink-0 inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none"
              style={{ background: '#F1F5F9', color: '#94A3B8', border: '1px solid #E2E8F0' }}>
              仅通知
            </span>
          )}
        </div>
        {/* 第二行：meta 摘要 */}
        {metaParts.length > 0 && (
          <p className="mt-0.5 text-xs truncate" style={{ color: '#94A3B8' }}>
            {metaParts.join('　·　')}
          </p>
        )}
      </div>

      {/* 右侧：时间 + 操作按钮（同行，不撑高卡片） */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <span className="text-xs tabular-nums whitespace-nowrap" style={{ color: '#94A3B8' }}>
          {formatTime(item.created_at, group)}
        </span>
        {item.link && (
          <span
            className="inline-flex items-center justify-center rounded-md px-2.5 py-1 text-xs font-semibold whitespace-nowrap"
            style={
              isAction
                ? { background: '#2563EB', color: '#fff' }
                : { background: '#F1F5F9', color: '#475569', border: '1px solid #E2E8F0' }
            }
          >
            {isAction ? '去处理' : '查看详情'}
          </span>
        )}
      </div>
    </button>
  )
}

// ── 主页面 ────────────────────────────────────────────────────
const PAGE_SIZE = 20

export function NotificationCenterPage() {
  const navigate = useNavigate()
  const { projectId } = useParams()
  const [filter, setFilter] = useState<FilterKey>('all')
  const [items, setItems] = useState<NotificationItem[]>([])
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(true)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    fetchUnreadCount().then((r) => setUnreadCount(r.count)).catch(() => {})
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setPage(1)
    fetchNotifications({ page: 1, pageSize: PAGE_SIZE })
      .then((rows) => {
        if (cancelled) return
        setItems(rows)
        setHasMore(rows.length === PAGE_SIZE)
      })
      .catch(() => { if (!cancelled) { setItems([]); setHasMore(false) } })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  // 前端过滤：全部 / 待我处理 / 仅通知
  const merged = useMemo(() => mergeProjectMemberNotifications(items), [items])

  const filtered = useMemo(() => {
    if (filter === 'action') return merged.filter((i) => requiresAction(i.type))
    if (filter === 'info') return merged.filter((i) => !requiresAction(i.type))
    return merged
  }, [merged, filter])

  // 按时间分组
  const grouped = useMemo(() => {
    const groups: { label: TimeGroup; items: MergedNotification[] }[] = [
      { label: '今天', items: [] },
      { label: '昨天', items: [] },
      { label: '更早', items: [] },
    ]
    for (const item of filtered) {
      const g = getTimeGroup(item.created_at)
      groups.find((gr) => gr.label === g)!.items.push(item)
    }
    return groups.filter((g) => g.items.length > 0)
  }, [filtered])

  const actionCount = useMemo(
    () => merged.filter((i) => requiresAction(i.type) && !i.is_read).length,
    [merged],
  )

  async function loadMore() {
    if (loadingMore || !hasMore) return
    const next = page + 1
    setLoadingMore(true)
    try {
      const rows = await fetchNotifications({ page: next, pageSize: PAGE_SIZE })
      setItems((prev) => [...prev, ...rows])
      setPage(next)
      setHasMore(rows.length === PAGE_SIZE)
    } finally {
      setLoadingMore(false)
    }
  }

  async function handleMarkAll() {
    await markAllRead()
    setItems((prev) => prev.map((i) => ({ ...i, is_read: true })))
    setUnreadCount(0)
  }

  async function openItem(item: MergedNotification) {
    if (!item.is_read) {
      await markRead(item.id)
      setItems((prev) => prev.map((n) => (n.id === item.id ? { ...n, is_read: true } : n)))
      setUnreadCount((prev) => Math.max(0, prev - 1))
    }
    if (item.link) navigate(item.link)
  }

  const back = projectId ? `/project/${projectId}` : '/home'

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: '#F4F7FB' }}>
      <div className="flex min-h-full w-full flex-col" style={{ maxWidth: 1280, padding: '0 28px' }}>

        {/* ── 紧凑 Toolbar ── */}
        <div
          className="flex items-center justify-between gap-4 border-b"
          style={{ height: 64, borderColor: '#E2E8F0', background: '#F4F7FB', position: 'sticky', top: 0, zIndex: 10 }}
        >
          {/* 左：图标 + 标题 + 副标题 */}
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg" style={{ background: '#EFF6FF', color: '#2563EB' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
            </div>
            <div className="flex items-baseline gap-2 min-w-0">
              <h1 className="text-base font-bold text-slate-900 whitespace-nowrap">
                {filter === 'action' ? '待我处理' : filter === 'info' ? '仅通知' : '全部通知'}
              </h1>
              {unreadCount > 0 && (
                <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">
                  {unreadCount}
                </span>
              )}
              <span className="hidden sm:inline text-xs text-slate-400 truncate">查看与你相关的项目动作、待处理事项和系统提醒</span>
            </div>
          </div>
          {/* 右：操作按钮 */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              type="button"
              onClick={() => navigate(back)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              ← 返回工作台
            </button>
            <button
              type="button"
              onClick={handleMarkAll}
              disabled={unreadCount === 0}
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-white transition disabled:cursor-not-allowed"
              style={{ background: unreadCount === 0 ? '#CBD5E1' : '#2563EB' }}
            >
              ✓ 全部标为已读
            </button>
          </div>
        </div>

        {/* ── Tabs ── */}
        <div className="flex items-end gap-5 border-b" style={{ borderColor: '#E2E8F0', height: 40 }}>
          {FILTERS.map(({ key, label }) => {
            const active = filter === key
            const badge = key === 'action' ? actionCount : 0
            return (
              <button
                key={key}
                type="button"
                onClick={() => setFilter(key)}
                className="relative h-full text-sm font-semibold transition"
                style={{ color: active ? '#2563EB' : '#64748B' }}
              >
                <span className="inline-flex items-center gap-1.5">
                  {label}
                  {badge > 0 && (
                    <span className="inline-flex min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-bold"
                      style={{ background: active ? '#DBEAFE' : '#F1F5F9', color: active ? '#1D4ED8' : '#64748B' }}>
                      {badge}
                    </span>
                  )}
                </span>
                <span className="absolute inset-x-0 bottom-0 h-0.5 rounded-full"
                  style={{ background: active ? '#2563EB' : 'transparent' }} />
              </button>
            )
          })}
        </div>

        {/* ── 通知列表 ── */}
        <div className="flex-1 py-3">
          {loading ? (
            <div className="flex items-center justify-center py-16 text-slate-500 text-sm">加载通知中...</div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white text-slate-300 shadow-sm">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
              </div>
              <div className="mt-3 text-base font-semibold text-slate-700">暂无通知</div>
              <div className="mt-1 text-xs text-slate-400">切换筛选条件，或稍后刷新查看。</div>
            </div>
          ) : (
            <div className="space-y-4">
              {grouped.map(({ label, items: groupItems }) => (
                <div key={label}>
                  {/* 时间分组标题：弱化 */}
                  <div className="flex items-center gap-2 mb-1.5" style={{ height: 28 }}>
                    <span className="text-[11px] font-semibold tracking-wide" style={{ color: '#94A3B8' }}>{label}</span>
                    <div className="flex-1 border-t" style={{ borderColor: '#E9EEF4' }} />
                  </div>
                  <div className="space-y-1.5">
                    {groupItems.map((item) => (
                      <NotificationCard key={item.id} item={item} group={label} onClick={openItem} />
                    ))}
                  </div>
                </div>
              ))}

              <div className="flex items-center justify-between gap-3 py-2">
                <div className="text-xs text-slate-400">当前已加载 {items.length} 条</div>
                <button
                  type="button"
                  onClick={loadMore}
                  disabled={!hasMore || loadingMore}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loadingMore ? '加载中...' : hasMore ? '加载更多' : '没有更多了'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
