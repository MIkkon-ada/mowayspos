import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { confirmKeyTaskCompletion, fetchKeyTaskExecutionWorkspace, reopenKeyTask, setKeyTaskRisk, type ExecutionPlan, type KeyTaskWorkspace } from '../../api/keyTaskWorkspace'
import { updateMonthlyPlan } from '../../api/monthlyPlans'
import { getProjectMembers } from '../../api/projects'
import { buildWorkReportEntryUrl } from '../../domain/workReportEntry'
import type { ProjectMember } from '../../types'
import { AchievementList } from './AchievementList'
import { CurrentProgressCard } from './CurrentProgressCard'
import { ExecutionPlanCreateDrawer } from './ExecutionPlanCreateDrawer'
import { ExecutionPlanDetailDrawer } from './ExecutionPlanDetailDrawer'
import { ExecutionPlanSidebar } from './ExecutionPlanSidebar'
import { ExecutionTimeline } from './ExecutionTimeline'
import { IssueList } from './IssueList'
import { KeyTaskHeader } from './KeyTaskHeader'
import { KeyTaskRequirementCard } from './KeyTaskRequirementCard'

export function KeyTaskExecutionWorkspace({ keyTaskId, onBack, projectId }: { keyTaskId: number; onBack?: () => void; projectId?: number | null }) {
  const navigate = useNavigate()
  const [workspace, setWorkspace] = useState<KeyTaskWorkspace | null>(null)
  const [selectedPlan, setSelectedPlan] = useState<ExecutionPlan | null>(null)
  const [creatingPlan, setCreatingPlan] = useState(false)
  const [editingPlan, setEditingPlan] = useState<ExecutionPlan | null>(null)
  const [projectMembers, setProjectMembers] = useState<ProjectMember[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    fetchKeyTaskExecutionWorkspace(keyTaskId)
      .then((data) => { if (!cancelled) setWorkspace(data) })
      .catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : '加载执行工作台失败') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [keyTaskId, refreshKey])

  useEffect(() => {
    if ((!creatingPlan && !editingPlan) || !workspace?.project?.id) return
    let cancelled = false
    getProjectMembers(workspace.project.id)
      .then((members) => { if (!cancelled) setProjectMembers(members) })
      .catch(() => { if (!cancelled) setProjectMembers([]) })
    return () => { cancelled = true }
  }, [creatingPlan, editingPlan, workspace?.project?.id])

  const refresh = () => setRefreshKey((value) => value + 1)
  const submitUpdate = () => {
    const resolvedProjectId = projectId ?? workspace?.project?.id
    if (resolvedProjectId) navigate(buildWorkReportEntryUrl(resolvedProjectId, keyTaskId, 'report'))
    else navigate(`/work/submit?subtaskId=${keyTaskId}`)
  }
  const confirm = async () => {
    if (!window.confirm('确认将该关键任务标记为已完成？')) return
    await confirmKeyTaskCompletion(keyTaskId)
    refresh()
  }
  const reopen = async () => {
    const reason = window.prompt('请填写重新打开原因')
    if (!reason?.trim()) return
    await reopenKeyTask(keyTaskId, reason.trim())
    refresh()
  }
  const changeRisk = async () => {
    const currentNote = workspace?.key_task.risk_note.trim() || ''
    if (currentNote) {
      if (!window.confirm('确认解除该关键任务的风险标记？')) return
      await setKeyTaskRisk(keyTaskId, '')
      refresh()
      return
    }
    const note = window.prompt('请填写风险原因')
    if (!note?.trim()) return
    await setKeyTaskRisk(keyTaskId, note.trim())
    refresh()
  }
  const markPlanCompleted = async (plan: ExecutionPlan) => {
    const actualOutput = window.prompt('请填写实际产出后标记完成', plan.actual_output || '')
    if (!actualOutput?.trim()) return
    await updateMonthlyPlan(plan.id, { status: '已完成', actual_output: actualOutput.trim() })
    setSelectedPlan(null)
    refresh()
  }

  if (loading) return <main className="p-8 text-sm text-slate-500">正在加载关键任务执行工作台…</main>
  if (error || !workspace) return <main className="p-8"><p className="text-sm text-red-700">{error || '工作台数据不可用'}</p><button type="button" onClick={refresh} className="mt-3 rounded border px-3 py-2 text-sm">重新加载</button>{onBack && <button type="button" onClick={onBack} className="ml-2 rounded border px-3 py-2 text-sm">返回</button>}</main>
  return (
    <main className="flex-1 min-h-0 overflow-y-auto bg-slate-50">
      <div className="mx-auto max-w-[1440px] space-y-4 px-4 pb-12 sm:px-6">
        {onBack && <button type="button" onClick={onBack} className="pt-4 text-sm font-medium text-slate-500 hover:text-blue-600">← 返回</button>}
        <KeyTaskHeader workspace={workspace} onSubmitUpdate={submitUpdate} onAddPlan={() => setCreatingPlan(true)} onConfirmCompletion={() => void confirm()} onReopen={() => void reopen()} onChangeRisk={() => void changeRisk()} />
        <KeyTaskRequirementCard workspace={workspace} />
        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <CurrentProgressCard progress={workspace.latest_submission} />
          <aside className="order-2 xl:col-start-2 xl:row-span-4">
            <ExecutionPlanSidebar plans={workspace.execution_plans} summary={workspace.plan_summary} canManage={workspace.permissions.can_manage_execution_plans && workspace.key_task.status !== '已完成'} onAdd={() => setCreatingPlan(true)} onOpen={setSelectedPlan} />
          </aside>
          <div className="order-3 min-w-0"><AchievementList items={workspace.achievements} /></div>
          {workspace.issues.length > 0 && <div className="order-4 min-w-0"><IssueList items={workspace.issues} /></div>}
          <div className="order-5 min-w-0"><ExecutionTimeline events={workspace.timeline} /></div>
        </div>
      </div>
      {(creatingPlan || editingPlan) && <ExecutionPlanCreateDrawer keyTaskId={keyTaskId} defaultAssigneeId={workspace.key_task.owner.id ?? null} members={projectMembers} plan={editingPlan} onClose={() => { setCreatingPlan(false); setEditingPlan(null) }} onCreated={refresh} />}
      <ExecutionPlanDetailDrawer open={Boolean(selectedPlan)} plan={selectedPlan} workspace={workspace} onClose={() => setSelectedPlan(null)} onSubmitUpdate={submitUpdate} onEdit={(plan) => { setSelectedPlan(null); setEditingPlan(plan) }} onMarkCompleted={(plan) => void markPlanCompleted(plan)} />
    </main>
  )
}
