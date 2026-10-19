import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getProject, getProjectMembers, approveProject, dispatchProject, returnProject } from '../api/projects'
import { fetchTasks } from '../api/tasks'
import { fetchSubTasksBatch } from '../api/subtasks'
import { useProject } from '../context/ProjectContext'
import { projectEditPath, projectOwnerSubmitPath } from '../domain/projectEntryRoutes'
import { DetailPanel } from '../features/settings/ProjectsMgmtSection'
import { ApprovalMaterialsWorkbenchModal } from '../features/settings/ProjectsMgmtSection'
import { ProjectCloseFlowDrawer } from '../features/settings/ProjectCloseFlowDrawer'
import type { Project, ProjectMember, TaskItem, SubTaskWithParent } from '../types'
import { toast } from '../utils/toast'

export default function ProjectDetailPage() {
  const { projectId: pidStr } = useParams<{ projectId: string }>()
  const projectId = Number(pidStr)
  const navigate = useNavigate()
  const { currentUser, reloadProjects } = useProject()

  const [project, setProject] = useState<Project | null>(null)
  const [members, setMembers] = useState<ProjectMember[]>([])
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [subtasks, setSubtasks] = useState<SubTaskWithParent[]>([])
  const [loading, setLoading] = useState(true)
  const [planError, setPlanError] = useState('')
  const [reloadVersion, setReloadVersion] = useState(0)
  const [reviewLoading, setReviewLoading] = useState(false)

  // modals
  const [approvalMaterialsProject, setApprovalMaterialsProject] = useState<Project | null>(null)
  const [closeFlowProjectId, setCloseFlowProjectId] = useState<number | null>(null)

  const myPersonId = currentUser?.person_id ?? null
  useEffect(() => {
    if (!projectId) return
    setLoading(true)
    setProject(null)
    setMembers([])
    setTasks([])
    setSubtasks([])
    setPlanError('')
    let cancelled = false

    async function loadProjectDetail() {
      try {
        // Only the project request determines whether this project exists. Member
        // and task data are supplementary and must not hide a valid project.
        const proj = await getProject(projectId)
        if (cancelled) return
        setProject(proj)

        const [memberResult, taskResult] = await Promise.allSettled([
          getProjectMembers(projectId),
          fetchTasks(projectId),
        ])
        if (cancelled) return
        if (memberResult.status === 'fulfilled') setMembers(memberResult.value)
        else setPlanError('项目成员加载失败，请重新加载审核材料')

        if (taskResult.status !== 'fulfilled') {
          console.error('Failed to load project tasks:', taskResult.reason)
          setPlanError('工作计划加载失败，请重新加载审核材料')
          return
        }

        const tasksData = taskResult.value
        setTasks(tasksData)
        const taskIds = tasksData.map((t) => t.id)
        if (taskIds.length > 0) {
          try {
            const batch = await fetchSubTasksBatch(taskIds)
            if (cancelled) return
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
          } catch (err) {
            console.error('Failed to load project subtasks:', err)
            if (!cancelled) setPlanError('关键任务加载失败，请重新加载审核材料')
          }
        }
      } catch (err) {
        console.error('Failed to load project detail:', err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadProjectDetail()
    return () => { cancelled = true }
  }, [projectId, reloadVersion])

  async function handleApprove() {
    if (!project || reviewLoading || planError) return
    setReviewLoading(true)
    try {
      const updated = await approveProject(project.id, {})
      setProject(updated)
      setApprovalMaterialsProject(null)
      reloadProjects()
      toast.success('立项审核通过，项目已进入执行阶段')
    } catch (error: unknown) { toast.error(error instanceof Error ? error.message : '审核失败，请重试') }
    finally { setReviewLoading(false) }
  }

  async function handleDispatch() {
    if (!project) return
    try {
      const result = await dispatchProject(project.id)
      setProject((current) => current ? { ...current, status: result.status, lifecycle_status: result.status } : current)
      reloadProjects()
      toast.success(`项目“${project.name}”已下发给负责人`)
    } catch (error: unknown) { toast.error(error instanceof Error ? error.message : '下发失败，请重试') }
  }

  async function handleReturn(reason?: string) {
    if (!project || reviewLoading) return
    if (reason === undefined) { setApprovalMaterialsProject(project); return }
    setReviewLoading(true)
    try {
      const updated = await returnProject(project.id, reason || undefined)
      setProject(updated)
      setApprovalMaterialsProject(null)
      reloadProjects()
      toast.success('已退回，负责人可修改原方案后重新提交')
    } catch (error: unknown) { toast.error(error instanceof Error ? error.message : '退回失败，请重试') }
    finally { setReviewLoading(false) }
  }

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
          onEdit={() => navigate(projectEditPath(project.id))}
          onDispatch={() => void handleDispatch()}
          onOwnerSubmit={() => navigate(projectOwnerSubmitPath(project.id))}
          onOpenApprovalMaterials={() => {
            setApprovalMaterialsProject(project)
          }}
          onReturn={() => void handleReturn()}
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
          canReview={project.status === 'pending_review' && (roles.isRealProjectCeo || roles.isSuperAdmin)}
          loading={reviewLoading}
          planError={planError}
          planLoading={loading}
          onRetry={() => setReloadVersion((value) => value + 1)}
          onClose={() => !reviewLoading && setApprovalMaterialsProject(null)}
          onApprove={() => void handleApprove()}
          onReturn={(reason) => void handleReturn(reason)}
        />
      )}

      <ProjectCloseFlowDrawer
        open={closeFlowProjectId === project.id}
        project={closeFlowProjectId === project.id ? project : null}
        currentPersonId={myPersonId}
        roles={roles}
        onClose={() => setCloseFlowProjectId(null)}
        onChanged={async (changedProjectId) => {
          const updated = await getProject(changedProjectId)
          setProject(updated)
          reloadProjects()
        }}
      />
    </div>
  )
}
