import type { Person } from '../../types'

type PeoplePickerProps = {
  people: Person[]
  value: number | ''
  onChange: (personId: number | '') => void
  disabledPersonIds?: number[]
  disabledHint?: string
  placeholder?: string
  allowManualFallback?: boolean
  manualValue?: string
  onManualChange?: (value: string) => void
  error?: string | null
}

export function PeoplePicker({
  people,
  value,
  onChange,
  disabledPersonIds = [],
  disabledHint = '人员列表加载中…',
  placeholder = '请选择人员…',
  allowManualFallback = false,
  manualValue = '',
  onManualChange,
  error,
}: PeoplePickerProps) {
  const hasPeople = people.length > 0

  return (
    <>
      {hasPeople ? (
        <select
          value={value === '' ? '' : String(value)}
          onChange={(e) => {
            const next = e.target.value
            onChange(next ? Number(next) : '')
          }}
        >
          <option value="">{placeholder}</option>
          {people.map((person) => {
            const disabled = disabledPersonIds.includes(person.id)
            return (
              <option key={person.id} value={person.id} disabled={disabled}>
                {person.name}
                {person.department ? `（${person.department}）` : ''}
                {` · #${person.id}`}
                {disabled ? ' · 已是该角色' : ''}
              </option>
            )
          })}
        </select>
      ) : allowManualFallback ? (
        <input
          value={manualValue}
          onChange={(e) => onManualChange?.(e.target.value)}
          placeholder="person_id（人员列表不可用时手填）"
        />
      ) : (
        <div className="readonly-hint">{disabledHint}</div>
      )}
      {error ? <div className="login-error">{error}</div> : null}
    </>
  )
}
