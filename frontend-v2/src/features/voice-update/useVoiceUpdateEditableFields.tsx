import type { VoiceUpdateEditableFieldsSectionProps } from './voiceUpdateResultTypes'

export function useVoiceUpdateEditableFields({
  editValues,
  editingField,
  setEditingField,
  setEditValues,
}: Pick<
  VoiceUpdateEditableFieldsSectionProps,
  'editValues' | 'editingField' | 'setEditingField' | 'setEditValues'
>) {
  if (!editValues) return null

  const s = editValues

  function setField(key: string, val: unknown) {
    setEditValues((prev) => (prev ? { ...prev, [key]: val } : prev))
  }

  function arrToText(v: unknown): string {
    if (!Array.isArray(v)) return String(v ?? '')
    return v.map((item) => {
      if (typeof item === 'object' && item !== null) {
        const o = item as Record<string, unknown>
        return String(o.name ?? o.description ?? '')
      }
      return String(item)
    }).filter(Boolean).join('\n')
  }

  function arrNames(v: unknown): string[] {
    if (!Array.isArray(v) || v.length === 0) return []
    return v.map((item) => {
      if (typeof item === 'object' && item !== null) {
        const o = item as Record<string, unknown>
        return String(o.name ?? o.description ?? '')
      }
      return String(item)
    }).filter(Boolean)
  }

  const isEditing = (field: string) => editingField === field || editingField === 'all'
  const confidence = typeof s.confidence === 'number' ? s.confidence : 0
  const confPct = confidence < 1 ? Math.round(confidence * 100) : Math.round(confidence as number)
  const confColor = confPct >= 80 ? '#059669' : confPct >= 60 ? '#D97706' : '#DC2626'
  const confLabel = confPct >= 80 ? '可信度高' : confPct >= 60 ? '可信度中' : '可信度低'
  const statusColor = ({ '进行中': '#3B82F6', '已完成': '#10B981', '延期': '#EF4444', '暂缓': '#F59E0B', '未开始': '#94A3B8' } as Record<string, string>)[s.status_suggestion as string] ?? '#94A3B8'
  const COORD_CHIP_COLORS = ['#EFF6FF:#1D4ED8', '#F5F3FF:#5B21B6', '#F0FDF4:#065F46', '#FFF7ED:#92400E']

  function EditIcon({ field }: { field: string }) {
    const active = isEditing(field)
    return (
      <button
        onClick={() => setEditingField(active && editingField !== 'all' ? null : field)}
        className="p-1 rounded hover:bg-slate-100 transition-colors flex-shrink-0"
        title="编辑"
      >
        <svg style={{ width: 13, height: 13, color: active ? '#0369A1' : '#CBD5E1' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
        </svg>
      </button>
    )
  }

  return {
    s,
    setField,
    arrToText,
    arrNames,
    isEditing,
    EditIcon,
    confidence,
    confPct,
    confColor,
    confLabel,
    statusColor,
    COORD_CHIP_COLORS,
  }
}
