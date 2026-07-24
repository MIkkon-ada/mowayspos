import { useEffect, useState } from 'react'
import { fetchPeople } from '../api/people'
import { getProjectMembers } from '../api/projects'
import { fetchTasks } from '../api/tasks'
import { fetchSubTasksBatch } from '../api/subtasks'
import { getOverview } from '../api/dashboard'
import { useProject } from '../context/ProjectContext'
import { getProjectRoleLabel } from '../domain/roleLabels'
import type { Person, Project, ProjectMember, TaskItem, SubTaskItem } from '../types'


const PROJ_ROLE_ORDER: Record<string, number> = {
  project_ceo: 0, owner: 1, coordinator: 2, member: 3,
}
const PROJ_ROLE_LABEL: Record<string, string> = {
  project_ceo: getProjectRoleLabel('project_ceo'),
  owner:       getProjectRoleLabel('owner'),
  coordinator: getProjectRoleLabel('coordinator'),
  member:      getProjectRoleLabel('member'),
}
const PROJ_ROLE_CLS: Record<string, string> = {
  project_ceo: 'bg-slate-800 text-white',
  owner:       'bg-emerald-100 text-emerald-700',
  coordinator: 'bg-purple-100 text-purple-700',
  member:      'bg-amber-100 text-amber-700',
}
const PROJ_COLORS = ['#2563EB', '#059669', '#F59E0B', '#7C3AED', '#0891B2']
const AVATAR_COLORS = ['#2563EB', '#059669', '#F59E0B', '#8B5CF6', '#0891B2', '#6366F1', '#EC4899', '#D97706']

function avaColor(name?: string) {
  return AVATAR_COLORS[((name?.charCodeAt(0) ?? 0)) % AVATAR_COLORS.length]
}

/** 从任务/子任务中推断出的人员，补充到角色图中（不影响正式项目成员） */
function addInferredRole(
  roleMap: Map<number, PersonRole[]>,
  membersMap: Map<number, ProjectMember[]>,
  peopleByName: Map<string, Person>,
  project: Project,
  rawName: string,
  role: string,
) {
  const person = peopleByName.get(rawName.trim())
  if (!person) return
  // 如果已有正式角色，不再用推断的 member 覆盖
  const existing = roleMap.get(person.id) ?? []
  if (existing.some((r) => r.project.id === project.id)) return
  existing.push({ project, role })
  roleMap.set(person.id, existing)

  const members = membersMap.get(project.id) ?? []
  members.push({
    id: -person.id,
    project_id: project.id,
    person_id: person.id,
    person_name_snapshot: person.name,
    role,
    note: null,
    joined_at: '',
  } as unknown as ProjectMember)
  membersMap.set(project.id, members)
}

type PersonRole = { project: Project; role: string }
type ViewMode = 'project' | 'people'

export function CoordinatePage() {
  const { projects, currentUser } = useProject()
  const [people, setPeople]           = useState<Person[]>([])
  const [personRoles, setPersonRoles] = useState<Map<number, PersonRole[]>>(new Map())
  const [projectMembers, setProjectMembers] = useState<Map<number, ProjectMember[]>>(new Map())
  const [completionMap, setCompletionMap]   = useState<Map<string, number>>(new Map())
  const [loading, setLoading]         = useState(false)
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null)
  const [selectedPersonId, setSelectedPersonId]   = useState<number | null>(null)
  const [viewMode, setViewMode]       = useState<ViewMode>('project')

  useEffect(() => {
    if (projects.length === 0) return
    let cancelled = false
    setLoading(true)

    Promise.all([
      fetchPeople(),
      ...projects.map((p) => getProjectMembers(p.id).catch(() => [] as ProjectMember[])),
      fetchTasks(null).catch(() => [] as TaskItem[]),
      getOverview(null).catch(() => null),
    ]).then(async ([peopleList, ...rest]) => {
      if (cancelled) return
      const overviewData = rest[rest.length - 1] as any
      const allMembersArr = rest.slice(0, projects.length) as ProjectMember[][]
      const allTasks = rest[projects.length] as TaskItem[]

      const taskIds = allTasks.map((t) => t.id)
      const subTaskMap = taskIds.length
        ? await fetchSubTasksBatch(taskIds).catch(() => ({} as Record<string, SubTaskItem[]>))
        : ({} as Record<string, SubTaskItem[]>)

      const roleMap   = new Map<number, PersonRole[]>()
      const membersMap = new Map<number, ProjectMember[]>()

      projects.forEach((project, idx) => {
        const members = allMembersArr[idx]
        membersMap.set(project.id, members)
        members.forEach((m) => {
          const list = roleMap.get(m.person_id) ?? []
          list.push({ project, role: m.role })
          roleMap.set(m.person_id, list)
        })
      })

      // 从任务/子任务中推断项目参与人员（未在项目成员表中的）
      const peopleByName = new Map<string, Person>()
      ;(peopleList as Person[]).forEach((p) => { peopleByName.set(p.name, p) })

      allTasks.forEach((task) => {
        const project = projects.find((p) => p.id === task.project_id)
        if (!project) return
        if (task.owner) addInferredRole(roleMap, membersMap, peopleByName, project, task.owner, 'member')
      })

      Object.entries(subTaskMap).forEach(([taskId, subs]) => {
        const task = allTasks.find((t) => String(t.id) === taskId)
        const project = task ? projects.find((p) => p.id === task.project_id) : undefined
        if (!project) return
        subs.forEach((sub) => {
          if (sub.assignee) addInferredRole(roleMap, membersMap, peopleByName, project, sub.assignee, 'member')
          if (sub.notes) {
            // 协同人格式：姓名1、姓名2，或 协同人：姓名1/姓名2
            const cleaned = sub.notes.replace(/^协同人[：:]\s*/, '')
            const collaborators = cleaned.split(/[、/\\,，;；\\s]+/)
            collaborators.forEach((name) => {
              const trimmed = name.replace(/[（(].*?[）)]/g, '').trim()
              if (trimmed && !trimmed.includes('全员') && !trimmed.includes('待指定') && !trimmed.includes('项目经理')) {
                addInferredRole(roleMap, membersMap, peopleByName, project, trimmed, 'member')
              }
            })
          }
        })
      })

      const cmap = new Map<string, number>()
      ;((overviewData?.project_cards as any[]) ?? []).forEach((card: any) => {
        const name = card.special_project ?? card.name ?? ''
        if (name) cmap.set(name, card.completion_rate ?? 0)
      })

      setPeople(peopleList as Person[])
      setPersonRoles(roleMap)
      setProjectMembers(membersMap)
      setCompletionMap(cmap)
    }).catch(() => {}).finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [projects])

  // 当前用户在某项目的参与标签
  function myBadge(project: Project): { label: string; cls: string } | null {
    if (!currentUser) return null
    const myId = (currentUser as any).person_id ?? (currentUser as any).id
    const members = projectMembers.get(project.id) ?? []
    const me = members.find((m) => m.person_id === myId || m.person_name_snapshot === currentUser.name)
    if (!me) return null
    if (me.role === 'owner')       return { label: '我负责', cls: 'bg-emerald-100 text-emerald-700' }
    if (me.role === 'coordinator') return { label: '我统筹', cls: 'bg-purple-100 text-purple-700' }
    if (me.role === 'project_ceo') return { label: '我参与', cls: 'bg-indigo-100 text-indigo-700' }
    return { label: '我参与', cls: 'bg-amber-100 text-amber-700' }
  }

  // 项目的统筹人和负责人
  function projectKeyPeople(project: Project) {
    const members = projectMembers.get(project.id) ?? []
    const coordinators = members.filter((m) => m.role === 'coordinator').map((m) => m.person_name_snapshot)
    const owners       = members.filter((m) => m.role === 'owner').map((m) => m.person_name_snapshot)
    return { coordinators, owners }
  }

  // 每人的最高项目角色（纯项目角色，不看系统字段）
  function getBestRole(p: Person): { label: string; cls: string } {
    const roles = personRoles.get(p.id) ?? []
    if (!roles.length) return { label: '协同成员', cls: 'bg-amber-100 text-amber-700' }
    const best = roles.slice().sort((a, b) => (PROJ_ROLE_ORDER[a.role] ?? 9) - (PROJ_ROLE_ORDER[b.role] ?? 9))[0]
    return { label: PROJ_ROLE_LABEL[best.role] ?? best.role, cls: PROJ_ROLE_CLS[best.role] ?? 'bg-amber-100 text-amber-700' }
  }

  // 某人参与的专项名列表
  function getProjectDuties(p: Person): string[] {
    return (personRoles.get(p.id) ?? []).map((r) => r.project.name)
  }

  // 当前用户可见的人员：管理员看全部，普通用户只看同项目成员
  const visiblePeople = (() => {
    if (currentUser?.can_view_all) return people
    const ids = new Set<number>()
    const names = new Set<string>()
    projectMembers.forEach((members) => {
      members.forEach((m) => { ids.add(m.person_id); names.add(m.person_name_snapshot) })
    })
    return people.filter((p) => ids.has(p.id) || names.has(p.name))
  })()

  // 不过滤，用高亮代替——所有可见人员都显示
  const displayPeople = visiblePeople

  // 点选专项时：哪些人属于该专项（用于高亮人员卡）
  const highlightedPersonIds = (() => {
    if (!selectedProjectId) return null
    const members = projectMembers.get(selectedProjectId) ?? []
    return { ids: new Set(members.map(m => m.person_id)), names: new Set(members.map(m => m.person_name_snapshot)) }
  })()

  // 点选人员时：该人参与哪些专项（用于高亮专项卡）
  const highlightedProjectIds = selectedPersonId
    ? new Set((personRoles.get(selectedPersonId) ?? []).map(r => r.project.id))
    : null

  function isPersonLit(p: Person) {
    if (!highlightedPersonIds) return true
    return highlightedPersonIds.ids.has(p.id) || highlightedPersonIds.names.has(p.name)
  }
  function isProjectLit(projId: number) {
    if (!highlightedProjectIds) return true
    return highlightedProjectIds.has(projId)
  }

  // 人在选中项目里的角色
  function getRoleInProject(p: Person, projectId: number): { label: string; cls: string } | null {
    const members = projectMembers.get(projectId) ?? []
    const m = members.find((x) => x.person_id === p.id || x.person_name_snapshot === p.name)
    if (!m) return null
    return { label: PROJ_ROLE_LABEL[m.role] ?? m.role, cls: PROJ_ROLE_CLS[m.role] ?? 'bg-amber-100 text-amber-700' }
  }

  const selectedProject = projects.find((p) => p.id === selectedProjectId)

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <header className="h-16 flex items-center px-6 gap-3 flex-shrink-0 bg-white border-b" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex-1">
          <h1 className="text-base font-bold text-slate-800">组织与分工</h1>
        </div>
        {/* 视角切换 */}
        <div className="flex rounded-lg border overflow-hidden" style={{ borderColor: '#E9EFF6' }}>
          {(['project', 'people'] as ViewMode[]).map((m) => (
            <button
              key={m}
              onClick={() => setViewMode(m)}
              className={`px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${viewMode === m ? 'bg-blue-600 text-white' : 'bg-white text-slate-500 hover:bg-slate-50'}`}
            >
              {m === 'project' ? '专项视角' : '人员视角'}
            </button>
          ))}
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6" style={{ background: '#F1F5F9' }}>
      <div className="flex flex-col gap-6">
        {loading ? (
          <div className="py-16 text-center text-slate-400 text-sm">加载中…</div>
        ) : (
          <>
            {/* ── 专项卡片 ── */}
            <section style={{ order: viewMode === 'people' ? 2 : 1 }}>
                <h2 className="text-sm font-bold text-slate-700 mb-3">
                  {projects.length} 个专项
                  {selectedProjectId && selectedProject && <span className="ml-2 text-blue-500 font-normal">· 当前：{selectedProject.name}</span>}
                </h2>
                <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' }}>
                  {projects.map((proj, i) => {
                    const pct = completionMap.get(proj.name) ?? 0
                    const { coordinators, owners } = projectKeyPeople(proj)
                    const badge = myBadge(proj)
                    const isSelected = selectedProjectId === proj.id
                    const lit = isProjectLit(proj.id)
                    const color = PROJ_COLORS[i % PROJ_COLORS.length]
                    return (
                      <div
                        key={proj.id}
                        onClick={() => { setSelectedProjectId(isSelected ? null : proj.id); setSelectedPersonId(null) }}
                        className="bg-white rounded-2xl p-4 cursor-pointer transition-all hover:-translate-y-0.5"
                        style={{
                          border: `1.5px solid ${isSelected ? color : '#E9EFF6'}`,
                          boxShadow: isSelected ? `0 0 0 3px ${color}22` : '0 1px 4px rgba(15,23,42,0.06)',
                          opacity: lit ? 1 : 0.35,
                          transition: 'opacity 0.2s, border-color 0.2s, box-shadow 0.2s',
                        }}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div
                            className="w-8 h-8 rounded-xl flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
                            style={{ background: color }}
                          >
                            {proj.name.slice(0, 1)}
                          </div>
                          {badge && (
                            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${badge.cls}`}>{badge.label}</span>
                          )}
                        </div>
                        <p className="text-sm font-bold text-slate-800 leading-snug mb-2">{proj.name}</p>
                        <div className="space-y-0.5 mb-3">
                          {coordinators.length > 0 && (
                            <p className="text-xs text-slate-400">
                              <span className="text-slate-500 font-medium">统筹</span> · {coordinators.join('、')}
                            </p>
                          )}
                          {owners.length > 0 && (
                            <p className="text-xs text-slate-400">
                              <span className="text-slate-500 font-medium">负责</span> · {owners.join('、')}
                            </p>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: '#EEF2F7' }}>
                            <div
                              className="h-full rounded-full transition-all duration-500"
                              style={{ width: `${pct}%`, background: pct > 50 ? '#059669' : pct > 20 ? color : '#F59E0B' }}
                            />
                          </div>
                          <span className="text-xs font-bold" style={{ color, minWidth: 32, textAlign: 'right' }}>{pct}%</span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </section>

            {/* ── 成员卡片 ── */}
            <section style={{ order: viewMode === 'people' ? 1 : 2 }}>
              <h2 className="text-sm font-bold text-slate-700 mb-3">
                {selectedProjectId && selectedProject ? `${selectedProject.name} · 成员` : '相关成员'}
                <span className="ml-1.5 text-slate-400 font-normal">（{displayPeople.length} 人）</span>
              </h2>
              <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>
                {displayPeople.map((p) => {
                  const roleInProject = selectedProjectId ? getRoleInProject(p, selectedProjectId) : null
                  const { label: roleLabel, cls: roleCls } = roleInProject ?? getBestRole(p)
                  const duties = getProjectDuties(p)
                  const isPersonSelected = selectedPersonId === p.id
                  const lit = isPersonLit(p)
                  return (
                    <div
                      key={p.id}
                      onClick={() => { setSelectedPersonId(isPersonSelected ? null : p.id); setSelectedProjectId(null) }}
                      className="bg-white rounded-2xl p-4 transition-all hover:shadow-md cursor-pointer"
                      style={{
                        border: `1.5px solid ${isPersonSelected ? '#2563EB' : '#E9EFF6'}`,
                        boxShadow: isPersonSelected ? '0 0 0 3px #2563EB22' : '0 1px 4px rgba(15,23,42,0.06)',
                        opacity: lit ? 1 : 0.35,
                        transition: 'opacity 0.2s, border-color 0.2s, box-shadow 0.2s',
                      }}
                    >
                      <div className="flex items-center gap-3 mb-3">
                        <div
                          className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm flex-shrink-0"
                          style={{ background: avaColor(p.name) }}
                        >
                          {p.name?.slice(0, 1)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-bold text-slate-800">{p.name}</span>
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold ${roleCls}`}>{roleLabel}</span>
                          </div>
                          {duties.length > 0 && (
                            <p className="text-xs text-slate-400 mt-0.5 truncate">
                              负责专项：{duties.join('、')}
                            </p>
                          )}
                        </div>
                      </div>
                      {/* 参与项目列表 */}
                      {(
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {(personRoles.get(p.id) ?? [])
                            .sort((a, b) => (PROJ_ROLE_ORDER[a.role] ?? 9) - (PROJ_ROLE_ORDER[b.role] ?? 9))
                            .map((r) => {
                              const isActive = selectedProjectId === r.project.id
                              const projIdx = projects.findIndex((x) => x.id === r.project.id)
                              const color = PROJ_COLORS[projIdx % PROJ_COLORS.length] ?? '#6B7280'
                              return (
                                <span
                                  key={r.project.id}
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    setSelectedProjectId(isActive ? null : r.project.id)
                                    setSelectedPersonId(null)
                                  }}
                                  className="text-xs px-2 py-0.5 rounded-full cursor-pointer transition-all hover:opacity-90"
                                  style={{
                                    background: isActive ? color + '20' : '#F1F5F9',
                                    color: isActive ? color : '#475569',
                                    border: `1px solid ${isActive ? color + '60' : '#E9EFF6'}`,
                                  }}
                                >
                                  {r.project.name} · {PROJ_ROLE_LABEL[r.role] ?? r.role}
                                </span>
                              )
                            })}
                        </div>
                      )}
                    </div>
                  )
                })}
                {displayPeople.length === 0 && (
                  <div className="col-span-3 py-12 text-center text-slate-400 text-sm">该专项暂无成员数据</div>
                )}
              </div>
            </section>
          </>
        )}
      </div>
      </div>
    </div>
  )
}
