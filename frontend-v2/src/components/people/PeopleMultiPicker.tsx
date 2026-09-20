import type { Person } from '../../types'

type PickerRole = {
  key: string
  label: string
}

type PeopleMultiPickerProps = {
  people: Person[]
  roles: PickerRole[]
  selectedByRole: Record<string, number[]>
  onToggle: (roleKey: string, personId: number) => void
  error?: string | null
  warning?: string | null
  emptyHint?: string
  loadingHint?: string
}

export function PeopleMultiPicker({
  people,
  roles,
  selectedByRole,
  onToggle,
  error,
  warning,
  emptyHint = '人员列表加载中…',
  loadingHint = '人员列表加载中…',
}: PeopleMultiPickerProps) {
  return (
    <div className="admin-form-wide init-members">
      <div className="init-members-head">
        <span>初始成员配置</span>
        {error ? <span className="login-error">{error}</span> : null}
      </div>
      {people.length > 0 ? (
        <>
          {warning ? <div className="readonly-hint init-members-warn">{warning}</div> : null}
          <div className="init-members-grid">
            {roles.map(({ key, label }) => (
              <div key={key} className="init-members-col">
                <div className="init-members-col-title">{label}</div>
                <div className="init-members-list">
                  {people.map((person) => (
                    <label key={person.id} className="init-members-item">
                      <input
                        type="checkbox"
                        checked={selectedByRole[key]?.includes(person.id) ?? false}
                        onChange={() => onToggle(key, person.id)}
                      />
                      <span>
                        {person.name}
                        {person.department ? `（${person.department}）` : ''}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </>
      ) : !error ? (
        <div className="readonly-hint">{emptyHint || loadingHint}</div>
      ) : null}
    </div>
  )
}
