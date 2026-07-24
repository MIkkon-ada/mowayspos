import { useNavigate } from 'react-router-dom'
import { useProject } from '../context/ProjectContext'
import { getProjectStatusBadge } from '../domain/projectLifecycleStatus'
import { getProjectRoleLabel } from '../domain/roles'
import type { Project } from '../types'

export function MemberProjectsPage() {
  const navigate = useNavigate()
  const { projects } = useProject()

  return (
    <div className="flex h-full min-h-0 flex-col" style={{ background: '#F1F5F9' }}>
      <header className="h-16 flex-shrink-0 border-b bg-white px-6 flex items-center" style={{ borderColor: '#E2E8F0' }}>
        <div>
          <h1 className="text-base font-bold text-slate-900">我的项目</h1>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto px-8 py-7">
        {projects.length === 0 ? (
          <div className="flex items-center justify-center py-20 text-slate-400">暂无可见项目</div>
        ) : (
          <div className="grid gap-5 xl:grid-cols-3 lg:grid-cols-2">
            {projects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                onEnter={() => navigate(`/member/projects/${project.id}`)}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

function ProjectCard({ project, onEnter }: { project: Project; onEnter: () => void }) {
  const badge = getProjectStatusBadge(project)

  return (
    <article
      className="group flex min-h-[200px] flex-col rounded-3xl border bg-white p-6 transition-all hover:-translate-y-0.5 hover:shadow-xl"
      style={{ borderColor: '#E2E8F0', boxShadow: '0 10px 28px rgba(15,23,42,0.06)' }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold {badge.className}">
            <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${badge.className}`}>
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: badge.tone === 'success' ? '#10B981' : badge.tone === 'neutral' ? '#94A3B8' : '#F59E0B' }} />
              {badge.label}
            </span>
          </div>
          <h2 className="text-lg font-bold text-slate-900">{project.name}</h2>
        </div>
        <div
          className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-2xl text-base font-black text-white"
          style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}
        >
          {project.name.slice(0, 1)}
        </div>
      </div>

      <p className="mt-3 line-clamp-2 text-sm leading-6 text-slate-500">{project.description || '暂无描述'}</p>

      {project.user_roles && project.user_roles.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {project.user_roles.map((role) => (
            <span key={role} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">{getProjectRoleLabel(role)}</span>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={onEnter}
        className="mt-auto flex h-11 items-center justify-center rounded-2xl text-sm font-bold text-white transition-transform group-hover:scale-[1.01]"
        style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}
      >
        进入项目
      </button>
    </article>
  )
}
