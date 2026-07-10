import { useCallback, useEffect, useState } from 'react'
import { fmtFull } from '../utils/time'
import { useNavigate, useParams } from 'react-router-dom'
import {
  getProjectMembers,
  addProjectMember,
  updateProjectMember,
  removeProjectMember,
} from '../api/projects'
import { fetchPeople } from '../api/people'
import { ApiError } from '../api/client'
import { ErrorState } from '../components/common/ErrorState'
import { LoadingState } from '../components/common/LoadingState'
import { PeoplePicker } from '../components/people/PeoplePicker'
import { useProject } from '../context/ProjectContext'
import { canManageProjectMembers } from '../domain/permissions'
import { getProjectRoleLabel } from '../domain/roleLabels'
import type { Person, ProjectMember } from '../types'

const ROLE_LABEL: Record<string, string> = {
  owner:       getProjectRoleLabel('owner'),
  coordinator: getProjectRoleLabel('coordinator'),
  member:      getProjectRoleLabel('member'),
  project_ceo: getProjectRoleLabel('project_ceo'),
}

const ROLES = ['owner', 'coordinator', 'member', 'project_ceo']

export function ProjectMembersPage() {
  const { currentUser } = useProject()
  const { projectId } = useParams()
  const navigate = useNavigate()
  const pid = Number(projectId)

  const [members, setMembers] = useState<ProjectMember[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [banner, setBanner] = useState<string | null>(null)
  const [personId, setPersonId] = useState('')
  const [role, setRole] = useState('member')
  const [note, setNote] = useState('')
  const [people, setPeople] = useState<Person[]>([])
  const [peopleError, setPeopleError] = useState<string | null>(null)

  const isSuperAdmin = canManageProjectMembers(currentUser)

  const load = useCallback(() => {
    if (!isSuperAdmin || Number.isNaN(pid)) return
    setLoading(true)
    setError(null)
    getProjectMembers(pid)
      .then(setMembers)
      .catch((err) => setError(err instanceof ApiError ? err.message : '加载成员失败'))
      .finally(() => setLoading(false))
  }, [isSuperAdmin, pid])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!isSuperAdmin) return
    fetchPeople()
      .then((list) => setPeople(list.filter((person) => person.is_active !== false)))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 403) {
          setPeopleError('无权获取人员列表，请改用 person_id 手动输入')
        } else if (err instanceof ApiError && err.isUnauthorized) {
          setPeopleError('登录已失效，请重新登录')
        } else {
          setPeopleError('人员列表加载失败，请改用 person_id 手动输入')
        }
      })
  }, [isSuperAdmin])

  const takenForRole = new Set(members.filter((member) => member.role === role).map((member) => member.person_id))

  if (!isSuperAdmin) {
    return <Hint title="无权限访问" subtitle="成员管理仅对超级管理员或公司 CEO 开放。" />
  }

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    setBanner(null)
    const idNum = Number(personId)
    if (!personId.trim() || Number.isNaN(idNum)) {
      setBanner('请输入有效的 person_id')
      return
    }
    try {
      await addProjectMember(pid, { person_id: idNum, role, note: note.trim() })
      setBanner('成员已添加')
      setPersonId('')
      setNote('')
      load()
    } catch (err) {
      setBanner(err instanceof ApiError ? `添加失败：${err.message}` : '添加失败')
    }
  }

  const handleRoleChange = async (member: ProjectMember, newRole: string) => {
    if (newRole === member.role) return
    setBanner(null)
    try {
      await updateProjectMember(pid, member.id, { role: newRole })
      setBanner('角色已更新')
      load()
    } catch (err) {
      setBanner(err instanceof ApiError ? err.message : '更新失败')
      load()
    }
  }

  const handleRemove = async (member: ProjectMember) => {
    if (!window.confirm(`确认移除「${member.person_name_snapshot}」的 ${ROLE_LABEL[member.role] ?? member.role} 角色？`)) return
    setBanner(null)
    try {
      await removeProjectMember(pid, member.id)
      setBanner('成员已移除')
      load()
    } catch (err) {
      setBanner(err instanceof ApiError ? err.message : '移除失败')
    }
  }

  return (
    <div className="admin-page">
      <main className="page-content fade-up">
        <div className="page-action-row">
          <h2 className="page-action-title">成员管理 · 项目 #{projectId}</h2>
          <button type="button" className="panel-link" onClick={() => navigate('/admin/projects')}>
            ← 返回项目管理
          </button>
        </div>

        {banner ? <div className="action-banner">{banner}</div> : null}

        <section className="card admin-form-card">
          <div className="panel-head">
            <h2 className="panel-title">新增成员角色</h2>
          </div>
          <form className="admin-form" onSubmit={handleAdd}>
            <label className="submit-field">
              <span>人员</span>
              <PeoplePicker
                people={people}
                value={personId ? Number(personId) : ''}
                onChange={(next) => setPersonId(next === '' ? '' : String(next))}
                disabledPersonIds={[...takenForRole]}
                allowManualFallback
                manualValue={personId}
                onManualChange={setPersonId}
                error={peopleError}
                placeholder="请选择人员…"
              />
            </label>
            <label className="submit-field">
              <span>角色</span>
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                {ROLES.map((value) => (
                  <option key={value} value={value}>
                    {ROLE_LABEL[value]}
                  </option>
                ))}
              </select>
            </label>
            <label className="submit-field">
              <span>备注</span>
              <input value={note} onChange={(e) => setNote(e.target.value)} />
            </label>
            <div className="admin-form-wide">
              <button type="submit" className="primary-action">
                添加成员
              </button>
            </div>
          </form>
        </section>

        {loading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : (
          <section className="card">
            <div className="panel-head">
              <h2 className="panel-title">成员列表</h2>
              <span className="records-count">共 {members.length} 条</span>
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>姓名</th>
                    <th>角色</th>
                    <th>备注</th>
                    <th>加入时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {members.map((member) => (
                    <tr key={member.id}>
                      <td className="record-title">{member.person_name_snapshot || `#${member.person_id}`}</td>
                      <td>
                        <select
                          className="confirm-mini-select"
                          value={member.role}
                          onChange={(e) => handleRoleChange(member, e.target.value)}
                        >
                          {ROLES.map((value) => (
                            <option key={value} value={value}>
                              {ROLE_LABEL[value]}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>{member.note || '-'}</td>
                      <td>{fmtFull(member.joined_at) || '-'}</td>
                      <td>
                        <button
                          type="button"
                          className="table-action danger"
                          onClick={() => handleRemove(member)}
                        >
                          移除
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </main>
    </div>
  )
}

function Hint({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="center-message">
      <div className="center-message-title">{title}</div>
      {subtitle ? <div className="center-message-subtitle">{subtitle}</div> : null}
    </div>
  )
}
