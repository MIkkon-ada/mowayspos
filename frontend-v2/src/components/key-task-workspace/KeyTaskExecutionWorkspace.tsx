import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { confirmKeyTaskCompletion, fetchKeyTaskExecutionWorkspace, reopenKeyTask, setKeyTaskRisk, type ExecutionPlan, type KeyTaskWorkspace } from '../../api/keyTaskWorkspace'
import { updateMonthlyPlan } from '../../api/monthlyPlans'
import { getProjectMembers } from '../../api/projects'
import { buildWorkReportEntryUrl } from '../../domain/workReportEntry'
import { ChevronDownIcon } from '../icons/ChevronDownIcon'
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

export function KeyTaskExecutionWorkspace({ keyTaskId, onBack, projectId, onRiskChanged }: { keyTaskId: number; onBack?: () => void; projectId?: number | null; onRiskChanged?: () => void }) {
  const navigate = useNavigate()
  const [workspace, setWorkspace] = useState<KeyTaskWorkspace | null>(null)
  const [selectedPlan, setSelectedPlan] = useState<ExecutionPlan | null>(null)
  const [creatingPlan, setCreatingPlan] = useState(false)
  const [editingPlan, setEditingPlan] = useState<ExecutionPlan | null>(null)
  const [projectMembers, setProjectMembers] = useState<ProjectMember[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshKey, setRefreshKey] = useState(0)
  const [riskDialogMode, setRiskDialogMode] = useState<'mark' | 'remove' | null>(null)
  const [riskNoteDraft, setRiskNoteDraft] = useState('')
  const [riskSaving, setRiskSaving] = useState(false)
  const [riskError, setRiskError] = useState('')

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
  const changeRisk = () => {
    const currentNote = workspace?.key_task.risk_note.trim() || ''
    setRiskDialogMode(currentNote ? 'remove' : 'mark')
    setRiskNoteDraft(currentNote)
    setRiskError('')
  }
  const saveRiskChange = async () => {
    if (!riskDialogMode) return
    const note = riskDialogMode === 'remove' ? '' : riskNoteDraft.trim()
    if (riskDialogMode === 'mark' && !note) {
      setRiskError('请填写风险原因')
      return
    }
    setRiskSaving(true)
    setRiskError('')
    try {
      await setKeyTaskRisk(keyTaskId, note)
      setRiskDialogMode(null)
      refresh()
      onRiskChanged?.()
    } catch (reason) {
      if (reason instanceof ApiError && reason.status >= 500) {
        setRiskError('服务器保存失败（服务端错误），风险原因仍保留在表单中；请稍后重试。')
      } else if (reason instanceof ApiError && reason.status === 0) {
        setRiskError('网络连接失败，风险原因仍保留在表单中；请检查网络后重试。')
      } else {
        setRiskError(reason instanceof Error ? reason.message : '保存风险标记失败，请重试')
      }
    } finally {
      setRiskSaving(false)
    }
  }
  const markPlanCompleted = async (plan: ExecutionPlan) => {
    const actualOutput = window.prompt('请填写实际产出后标记完成', plan.actual_output || '')
    if (!actualOutput?.trim()) return
    await updateMonthlyPlan(plan.id, { status: '已完成', actual_output: actualOutput.trim() })
    setSelectedPlan(null)
    refresh()
  }

  if (loading) return <main className="p-8 text-sm text-slate-500" aria-label="关键任务执行详情">正在加载关键任务执行工作台…</main>
  if (error || !workspace) return <main className="p-8" aria-label="关键任务执行详情"><p className="text-sm text-red-700">{error || '工作台数据不可用'}</p><button type="button" onClick={refresh} className="mt-3 rounded border px-3 py-2 text-sm">重新加载</button>{onBack && <button type="button" onClick={onBack} className="ml-2 rounded border px-3 py-2 text-sm">返回</button>}</main>
  return (
    <main className="flex-1 min-h-0 overflow-y-auto bg-slate-50" aria-label="关键任务执行详情">
      <div className="mx-auto max-w-[1440px] space-y-4 px-4 pb-24 sm:px-6 min-[800px]:pb-12">
        {onBack && <button type="button" onClick={onBack} className="inline-flex items-center gap-1 pt-4 text-sm font-medium text-slate-500 hover:text-blue-600"><ChevronDownIcon className="h-4 w-4 rotate-90" />返回</button>}
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
      {riskDialogMode && <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4">
        <section role="dialog" aria-modal="true" aria-labelledby="risk-dialog-title" className="w-full max-w-lg rounded-xl bg-white p-6 shadow-2xl">
          <h2 id="risk-dialog-title" className="text-lg font-semibold text-slate-900">{riskDialogMode === 'remove' ? '解除风险' : '标记风险'}</h2>
          {riskDialogMode === 'remove'
            ? <p className="mt-3 text-sm leading-6 text-slate-600">当前原因：{riskNoteDraft}。确认后将清除该关键任务的风险标记。</p>
            : <div className="mt-4">
              <label htmlFor="key-task-risk-note" className="mb-1.5 block text-sm font-medium text-slate-700">风险原因</label>
              <textarea id="key-task-risk-note" aria-label="风险原因" value={riskNoteDraft} onChange={(event) => setRiskNoteDraft(event.target.value)} maxLength={500} rows={4} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-800 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" placeholder="说明风险情况及影响" />
              <p className="mt-1 text-right text-xs text-slate-500">{riskNoteDraft.length}/500</p>
            </div>}
          {riskError && <p role="alert" className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{riskError}</p>}
          <div className="mt-5 flex justify-end gap-2">
            <button type="button" onClick={() => setRiskDialogMode(null)} disabled={riskSaving} className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-50">取消</button>
            <button type="button" onClick={() => void saveRiskChange()} disabled={riskSaving || (riskDialogMode === 'mark' && !riskNoteDraft.trim())} className="rounded-md bg-blue-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">{riskSaving ? '正在保存…' : riskDialogMode === 'remove' ? '确认解除风险' : '保存风险'}</button>
          </div>
        </section>
      </div>}
    </main>
  )
}
