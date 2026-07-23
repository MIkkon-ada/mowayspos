import { useProject } from '../context/ProjectContext'
import { formatProjectRoleLabels } from '../domain/roleLabels'

function roleLabels(roles: string[]): string {
  return formatProjectRoleLabels(roles)
}

export function ProjectSelector({ dark }: { dark?: boolean }) {
  const { projects, currentProjectId, currentProject, setCurrentProjectId, currentUser } = useProject()

  if (projects.length === 0) {
    return (
      <span style={{ fontSize: dark ? 11 : 13, color: dark ? '#94A3B8' : '#94A3B8' }}>
        暂无可用项目
      </span>
    )
  }

  const handleChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const val = event.target.value
    setCurrentProjectId(val === '' ? null : Number(val))
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <select
        value={currentProjectId ?? ''}
        onChange={handleChange}
        aria-label="切换项目"
        style={
          dark
            ? {
                width: '100%',
                background: 'rgba(15, 23, 42, 0.6)',
                color: '#E2E8F0',
                border: '1px solid rgba(148, 163, 184, 0.2)',
                borderRadius: 6,
                padding: '6px 8px',
                fontSize: 12,
                fontWeight: 500,
                cursor: 'pointer',
                outline: 'none',
              }
            : {
                maxWidth: 220,
                background: '#F8FAFC',
                color: '#334155',
                border: '1px solid #E2E8F0',
                borderRadius: 8,
                padding: '6px 32px 6px 12px',
                fontSize: 13,
                fontWeight: 500,
                cursor: 'pointer',
                outline: 'none',
                appearance: 'none',
                WebkitAppearance: 'none',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }
        }
      >
        {currentUser?.is_tech_admin ? <option value="">全局视图</option> : null}
        {projects.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
            {p.code ? `（${p.code}）` : ''}
          </option>
        ))}
      </select>
      {dark && (
        <span style={{ fontSize: 10, color: '#94A3B8', padding: '0 2px' }}>
          {currentProject ? roleLabels(currentProject.user_roles) : '未选择项目'}
        </span>
      )}
    </div>
  )
}
