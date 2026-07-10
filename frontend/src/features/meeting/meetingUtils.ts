import { fmtFull } from '../../utils/time'
import type { MeetingItem } from '../../types'

export type PublishStatus = 'draft' | 'published' | 'returned'

export const TYPE_LABEL: Record<string, string> = {
  weekly: '周会',
  monthly: '月会',
  review: '评审会',
  special: '专项会',
  discuss: '讨论会',
  kickoff: '启动会',
}

export const TYPE_STYLE: Record<string, string> = {
  周会: 'bg-blue-100 text-blue-700',
  月会: 'bg-blue-100 text-blue-700',
  评审会: 'bg-purple-100 text-purple-700',
  专项会: 'bg-emerald-100 text-emerald-700',
  讨论会: 'bg-orange-100 text-orange-700',
  启动会: 'bg-amber-100 text-amber-700',
}

export const STATUS_CONFIG: Record<PublishStatus, { cls: string; label: string }> = {
  draft: { cls: 'bg-amber-100 text-amber-700', label: '草稿' },
  published: { cls: 'bg-emerald-100 text-emerald-700', label: '已发布' },
  returned: { cls: 'bg-red-100 text-red-700', label: '已退回' },
}

export function typeLabel(raw?: string) {
  return TYPE_LABEL[raw ?? ''] ?? raw ?? '-'
}

export function getStatus(m: MeetingItem): PublishStatus {
  const s = m.publish_status as string | undefined
  if (s === 'published' || s === 'returned') return s
  return 'draft'
}

export function detectSpeakers(text: string): string[] {
  const set = new Set<string>()
  const re = /Speaker\s*(\d+)/g
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) set.add(`Speaker ${m[1]}`)
  return [...set].sort((a, b) => Number(a.replace('Speaker ', '')) - Number(b.replace('Speaker ', '')))
}

export function fmtTime(raw?: string | null) {
  return raw ? fmtFull(raw) : '-'
}

export function renderVal(value: unknown): string {
  if (value == null || value === '') return '-'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.map(renderVal).filter(Boolean).join(', ')
  if (typeof value === 'object') return Object.values(value as Record<string, unknown>).map(renderVal).filter(Boolean).join(', ')
  return String(value)
}
