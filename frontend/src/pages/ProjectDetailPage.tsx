import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getProject, getProjectMembers } from '../api/projects'
import { fetchTasks } from '../api/tasks'
import { fetchSubTasksBatch } from '../api/subtasks'
import { useProject } from '../context/ProjectContext'
import { DetailPanel } from '../features/settings/ProjectsMgmtSection'
import { ApprovalMaterialsWorkbenchModal } from '../features/settings/ProjectsMgmtSection'
import type { Project, ProjectMember, TaskItem, SubTaskWithParent } from '../types'

export default function ProjectDetailPage() {
  const { projectId: pidStr } = useParams<{ projectId: string }>()
  const projectId = Number(pidStr)
  const navigate = useNavigate()
  const { currentUser } = useProject()

  const [project, setProject] = useState<Project | null>(null)
  const [members, setMembers] = useState<ProjectMember[]>([])
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [subtasks, setSubtasks] = useState<SubTaskWithParent[]>([])
  const [loading, setLoading] = useState(true)

  // modals
  const [approvalMaterialsProject, setApprovalMaterialsProject] = useState<Project | null>(null)
  const [closeFlowProjectId, setCloseFlowProjectId] = useState<number | null>(null)

  const myPersonId = currentUser?.person_id ?? null

  useEffect(() => {
    if (!projectId) return
    setLoading(true)
    Promise.all([
      getProject(projectId),
      getProjectMembers(projectId),
      fetchTasks(projectId),
    ])
      .then(([proj, mems, tasksData]) => {
        setProject(proj)
        setMembers(mems)
        setTasks(tasksData)
        // fetch subtasks for all tasks
        const taskIds = tasksData.map((t) => t.id)
        if (taskIds.length > 0) {
          return fetchSubTasksBatch(taskIds).then((batch) => {
            const allSubs: SubTaskWithParent[] = []
            tasksData.forEach((task) => {
              const subs = batch[String(task.id)] ?? []
              subs.forEach((sub) => {
                allSubs.push({
                  ...sub,
                  parent_key_task: task.key_task || '',
                  parent_task_id: task.id,
                  parent_project_id: task.project_id || projectId,
                  parent_special_project: '',
                } as SubTaskWithParent)
              })
            })
            setSubtasks(allSubs)
          })
        }
      })
      .catch((err) => {
        console.error('Failed to load project detail:', err)
      })
      .finally(() => setLoading(false))
  }, [projectId])

  // 角色
  const roles = useMemo(() => {
    const isSuperAdmin = Boolean(currentUser?.is_tech_admin)
    const isCompanyCeo = Boolean(currentUser?.is_ceo) && !isSuperAdmin
    const isRealProjectCeo = Boolean(myPersonId && members.some((m) => m.person_id === myPersonId && m.role === 'project_ceo'))
    const isRealOwner = Boolean(myPersonId && members.some((m) => m.person_id === myPersonId && m.role === 'owner'))
    return { isSuperAdmin, isCompanyCeo, isRealProjectCeo, isRealOwner }
  }, [currentUser, members, myPersonId])

  const goBack = () => navigate('/home/projects')

  if (loading) {
    return (
      <div className="min-h-screen bg-[#F8FAFC]">
        <div className="mx-auto max-w-[1440px] px-6 py-5">
          <button onClick={goBack} className="mb-4 flex cursor-pointer items-center gap-1 text-sm text-sky-600 hover:text-sky-700">
            ← 返回项目管理
          </button>
          <p className="py-12 text-center text-sm text-slate-400">加载中...</p>
        </div>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="min-h-screen bg-[#F8FAFC]">
        <div className="mx-auto max-w-[1440px] px-6 py-5">
          <button onClick={goBack} className="mb-4 flex cursor-pointer items-center gap-1 text-sm text-sky-600 hover:text-sky-700">
            ← 返回项目管理
          </button>
          <p className="py-12 text-center text-sm text-slate-400">项目不存在或已被删除</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#F8FAFC]">
      {/* 返回 + 详情面板 */}
      <div className="mx-auto max-w-[1100px] px-6 py-5">
        <button
          onClick={goBack}
          className="mb-4 inline-flex cursor-pointer items-center gap-1 rounded-lg text-sm text-sky-600 transition-colors hover:text-sky-700"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7" />
          </svg>
          返回项目管理
        </button>

        <DetailPanel
          project={project}
          projectMembers={members}
          tasks={tasks}
          subtasks={subtasks}
          roles={roles}
          wide
          onClose={goBack}
          onEdit={() => navigate(`/home/projects?edit=${project.id}`)}
          onDispatch={async () => {
            // TODO: dispatch logic
          }}
          onOwnerSubmit={() => {
            // TODO: owner submit logic - needs OwnerFillProject modal
          }}
          onOpenApprovalMaterials={() => {
            setApprovalMaterialsProject(project)
          }}
          onReturn={() => {
            // TODO: return logic
          }}
          onWorkProgress={() => navigate(`/work/tasks?projectId=${project.id}`)}
          onOpenCloseFlow={() => {
            setCloseFlowProjectId(project.id)
          }}
          onOpenArchive={() => navigate(`/home/projects/${project.id}/archive`)}
        />
      </div>

      {/* 审核材料弹窗 */}
      {approvalMaterialsProject && (
        <ApprovalMaterialsWorkbenchModal
          project={approvalMaterialsProject}
          projectMembers={members}
          tasks={tasks}
          subtasks={subtasks}
          canReview={roles.isRealProjectCeo || roles.isSuperAdmin}
          loading={false}
          onClose={() => setApprovalMaterialsProject(null)}
          onApprove={() => {
            // TODO: approve logic
            setApprovalMaterialsProject(null)
          }}
          onReturn={() => {
            // TODO: return logic
            setApprovalMaterialsProject(null)
          }}
        />
      )}
    </div>
  )
}
