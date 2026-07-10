import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getProjects,
  createProject,
  patchProject,
  archiveProject,
  type ProjectCreatePayload,
} from '../api/projects'
import { fetchPeople } from '../api/people'
import { ApiError } from '../api/client'
import { ErrorState } from '../components/common/ErrorState'
import { LoadingState } from '../components/common/LoadingState'
import { PeopleMultiPicker } from '../components/people/PeopleMultiPicker'
import { useProject } from '../context/ProjectContext'
import {
  getProjectPrimaryStatus,
  getProjectStatusBadge,
  getProjectStatusLabel,
  isProjectActive,
  isProjectArchived,
} from '../domain/projectLifecycleStatus'
import { canManageProjects } from '../domain/permissions'
import { getProjectRoleLabel } from '../domain/roleLabels'
import type { Person, Project } from '../types'

type InitialMembers = {
  project_ceo: number[]
  owner: number[]
  coordinator: number[]
  member: number[]
}

const EMPTY_MEMBERS: InitialMembers = {
  project_ceo: [],
  owner: [],
  coordinator: [],
  member: [],
}

const MEMBER_ROLES: Array<{ key: keyof InitialMembers; label: string }> = [
  { key: 'owner', label: getProjectRoleLabel('owner') },
  { key: 'project_ceo', label: getProjectRoleLabel('project_ceo') },
  { key: 'coordinator', label: getProjectRoleLabel('coordinator') },
  { key: 'member', label: getProjectRoleLabel('member') },
]

type FormState = {
  mode: 'create' | 'edit'
  editId: number | null
  name: string
  code: string
  description: string
  status: string
  start_date: string
  end_date: string
}

const EMPTY_FORM: FormState = {
  mode: 'create',
  editId: null,
  name: '',
  code: '',
  description: '',
  status: 'active',
  start_date: '',
  end_date: '',
}

export function ProjectAdminPage() {
  const { currentUser } = useProject()
  const navigate = useNavigate()

  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [banner, setBanner] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [people, setPeople] = useState<Person[]>([])
  const [peopleError, setPeopleError] = useState<string | null>(null)
  const [initMembers, setInitMembers] = useState<InitialMembers>(EMPTY_MEMBERS)
  const [newProjectId, setNewProjectId] = useState<number | null>(null)

  const isSuperAdmin = canManageProjects(currentUser)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    getProjects(true)
      .then(setProjects)
      .catch((err) => setError(err instanceof ApiError ? err.message : '加载项目失败'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (isSuperAdmin) load()
  }, [isSuperAdmin, load])

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

  if (!isSuperAdmin) {
    return <Hint title="无权限访问" subtitle="项目管理对公司 CEO / 超级管理员开放。" />
  }

  const resetForm = () => {
    setForm(EMPTY_FORM)
    setFormError(null)
    setInitMembers(EMPTY_MEMBERS)
  }

  const toggleMember = (roleKey: keyof InitialMembers, personId: number) => {
    setInitMembers((prev) => {
      const current = prev[roleKey]
      const next = current.includes(personId)
        ? current.filter((id) => id !== personId)
        : [...current, personId]
      return { ...prev, [roleKey]: next }
    })
  }

  const startEdit = (project: Project) => {
    const primaryStatus = getProjectPrimaryStatus(project)
    setForm({
      mode: 'edit',
      editId: project.id,
      name: project.name,
      code: project.code ?? '',
      description: project.description ?? '',
      status: primaryStatus === 'archived' ? 'archived' : 'active',
      start_date: project.start_date ?? '',
      end_date: project.end_date ?? '',
    })
    setInitMembers(EMPTY_MEMBERS)
    setFormError(null)
    setNewProjectId(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)
    setBanner(null)
    try {
      if (form.mode === 'create') {
        if (!form.name.trim()) {
          setFormError('项目名称必填')
          return
        }
        const payload: ProjectCreatePayload = {
          name: form.name.trim(),
          code: form.code.trim(),
          description: form.description.trim(),
          status: form.status,
          start_date: form.start_date,
          end_date: form.end_date,
          project_ceo_ids: initMembers.project_ceo,
          owner_ids: initMembers.owner,
          coordinator_ids: initMembers.coordinator,
          member_ids: initMembers.member,
        }
        const created = await createProject(payload)
        setBanner(`项目「${created.name}」已创建（#${created.id}）`)
        setNewProjectId(created.id)
        resetForm()
        load()
        return
      }

      if (form.editId !== null) {
        await patchProject(form.editId, {
          name: form.name.trim(),
          code: form.code.trim(),
          description: form.description.trim(),
          status: form.status,
          start_date: form.start_date,
          end_date: form.end_date,
        })
        setBanner('项目已更新')
      }
      resetForm()
      load()
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : '保存失败')
    }
  }

  const handleArchive = async (project: Project) => {
    if (!window.confirm(`确认归档项目「${project.name}」？`)) return
    setBanner(null)
    setNewProjectId(null)
    try {
      await archiveProject(project.id)
      setBanner(`项目「${project.name}」已归档`)
      load()
    } catch (err) {
      setBanner(err instanceof ApiError ? `归档失败：${err.message}` : '归档失败')
    }
  }

  return (
    <div className="admin-page">
      <main className="page-content fade-up">
        <div className="page-action-row">
          <h2 className="page-action-title">项目管理</h2>
        </div>

        {banner ? (
          <div className="action-banner">
            {banner}
            {newProjectId !== null ? (
              <button
                type="button"
                className="panel-link"
                style={{ marginLeft: 12 }}
                onClick={() => navigate(`/admin/projects/${newProjectId}/members`)}
              >
                去成员管理 →
              </button>
            ) : null}
          </div>
        ) : null}

        <section className="card admin-form-card">
          <div className="panel-head">
            <h2 className="panel-title">{form.mode === 'create' ? '新建项目' : `编辑项目 #${form.editId}`}</h2>
            {form.mode === 'edit' ? (
              <button type="button" className="panel-link" onClick={resetForm}>
                取消编辑
              </button>
            ) : null}
          </div>

          <form className="admin-form" onSubmit={handleSubmit}>
            <label className="submit-field">
              <span>项目名称 *</span>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="必填"
              />
            </label>
            <label className="submit-field">
              <span>项目代号 code</span>
              <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
            </label>
            <label className="submit-field">
              <span>状态</span>
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                <option value="active">active</option>
                <option value="archived">archived</option>
              </select>
            </label>
            <label className="submit-field">
              <span>开始日期</span>
              <input
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                placeholder="YYYY-MM-DD"
              />
            </label>
            <label className="submit-field">
              <span>结束日期</span>
              <input
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                placeholder="YYYY-MM-DD"
              />
            </label>
            <label className="submit-field admin-form-wide">
              <span>描述</span>
              <textarea
                rows={2}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </label>

            {form.mode === 'create' ? (
              <PeopleMultiPicker
                people={people}
                roles={MEMBER_ROLES}
                selectedByRole={initMembers}
                onToggle={(roleKey, personId) => toggleMember(roleKey as keyof InitialMembers, personId)}
                error={peopleError}
                warning={
                  initMembers.owner.length === 0
                    ? '建议至少选择一名负责人（owner），否则项目无法正常接收提交。'
                    : null
                }
              />
            ) : null}

            {formError ? <div className="login-error admin-form-wide">{formError}</div> : null}
            <div className="admin-form-wide">
              <button type="submit" className="primary-action">
                {form.mode === 'create' ? '创建项目' : '保存修改'}
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
              <h2 className="panel-title">项目列表</h2>
              <span className="records-count">共 {projects.length} 条</span>
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>名称</th>
                    <th>代号</th>
                    <th>状态</th>
                    <th>成员</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {projects.map((project) => (
                    <tr key={project.id}>
                      <td>{project.id}</td>
                      <td className="record-title">{project.name}</td>
                      <td>{project.code || '-'}</td>
                      <td>
                        {(() => {
                          const badge = getProjectStatusBadge(project)
                          return (
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${badge.className}`}>
                              {badge.label}
                            </span>
                          )
                        })()}
                      </td>
                      <td>{memberSummary(project.member_counts)}</td>
                      <td className="admin-row-actions">
                        <button type="button" className="table-action" onClick={() => startEdit(project)}>
                          编辑
                        </button>
                        <button
                          type="button"
                          className="table-action"
                          onClick={() => navigate(`/admin/projects/${project.id}/members`)}
                        >
                          成员管理
                        </button>
                        {isProjectActive(project) ? (
                          <button
                            type="button"
                            className="table-action danger"
                            onClick={() => handleArchive(project)}
                          >
                            归档
                          </button>
                        ) : (
                          <span className="readonly-hint">{isProjectArchived(project) ? getProjectStatusLabel(project) : '未激活'}</span>
                        )}
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

function memberSummary(counts: Record<string, number> | undefined): string {
  if (!counts) return '-'
  const total = Object.values(counts).reduce((sum, value) => sum + (value || 0), 0)
  return String(total)
}

function Hint({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="center-message">
      <div className="center-message-title">{title}</div>
      {subtitle ? <div className="center-message-subtitle">{subtitle}</div> : null}
    </div>
  )
}
