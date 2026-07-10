import { useProject } from '../context/ProjectContext'
import { formatProjectRoleLabels } from '../domain/roleLabels'

function roleLabels(roles: string[]): string {
  return formatProjectRoleLabels(roles)
}

export function ProjectSelector() {
  const { projects, currentProjectId, currentProject, setCurrentProjectId, currentUser } = useProject()

  if (projects.length === 0) {
    return <span className="project-selector-empty">暂无可用项目</span>
  }

  const handleChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const val = event.target.value
    setCurrentProjectId(val === '' ? null : Number(val))
  }

  return (
    <div className="project-selector">
      <select
        className="project-selector-select"
        value={currentProjectId ?? ''}
        onChange={handleChange}
        aria-label="切换项目"
      >
        {currentUser?.is_tech_admin ? <option value="">全局视图</option> : null}
        {projects.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
            {p.code ? `（${p.code}）` : ''}
          </option>
        ))}
      </select>
      {currentProject ? (
        <span className="project-selector-role">{roleLabels(currentProject.user_roles)}</span>
      ) : null}
    </div>
  )
}
