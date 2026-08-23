import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { confirmKeyTaskCompletion, fetchKeyTaskExecutionWorkspace, reopenKeyTask, type ExecutionPlan, type KeyTaskWorkspace } from '../../api/keyTaskWorkspace'
import { updateMonthlyPlan } from '../../api/monthlyPlans'
import { buildWorkReportEntryUrl } from '../../domain/workReportEntry'
import { AchievementList } from './AchievementList'
import { CurrentProgressCard } from './CurrentProgressCard'
import { ExecutionPlanDetailDrawer } from './ExecutionPlanDetailDrawer'
import { ExecutionPlanTable } from './ExecutionPlanTable'
import { ExecutionTimeline } from './ExecutionTimeline'
import { IssueList } from './IssueList'
import { KeyTaskContextCard } from './KeyTaskContextCard'
import { KeyTaskHeader } from './KeyTaskHeader'

export function KeyTaskExecutionWorkspace({ keyTaskId, onBack, projectId }: { keyTaskId: number; onBack?: () => void; projectId?: number | null }) {
  const navigate = useNavigate(); const [workspace, setWorkspace] = useState<KeyTaskWorkspace | null>(null); const [selectedPlan, setSelectedPlan] = useState<ExecutionPlan | null>(null); const [error, setError] = useState(''); const [loading, setLoading] = useState(true); const [refreshKey, setRefreshKey] = useState(0)
  useEffect(() => { let cancelled = false; setLoading(true); setError(''); fetchKeyTaskExecutionWorkspace(keyTaskId).then((data) => { if (!cancelled) setWorkspace(data) }).catch((reason: unknown) => { if (!cancelled) setError(reason instanceof Error ? reason.message : '加载执行工作台失败') }).finally(() => { if (!cancelled) setLoading(false) }); return () => { cancelled = true } }, [keyTaskId, refreshKey])
  const refresh = () => setRefreshKey((value) => value + 1)
  const submitUpdate = () => { const resolvedProjectId = projectId ?? workspace?.project?.id; if (resolvedProjectId) navigate(buildWorkReportEntryUrl(resolvedProjectId, keyTaskId, 'report')); else navigate(`/work/submit?subtaskId=${keyTaskId}`) }
  const confirm = async () => { if (!window.confirm('确认将该关键任务标记为已完成？')) return; await confirmKeyTaskCompletion(keyTaskId); refresh() }
  const reopen = async () => { const reason = window.prompt('请填写重新打开原因'); if (!reason?.trim()) return; await reopenKeyTask(keyTaskId, reason.trim()); refresh() }
  const markPlanCompleted = async (plan: ExecutionPlan) => { const actualOutput = window.prompt('请填写实际产出后标记完成', plan.actual_output || ''); if (!actualOutput?.trim()) return; await updateMonthlyPlan(plan.id, { status: '已完成', actual_output: actualOutput.trim() }); setSelectedPlan(null); refresh() }
  if (loading) return <main className="p-8 text-sm text-slate-500">正在加载关键任务执行工作台…</main>
  if (error || !workspace) return <main className="p-8"><p className="text-sm text-red-700">{error || '工作台数据不可用'}</p><button type="button" onClick={refresh} className="mt-3 rounded border px-3 py-2 text-sm">重新加载</button>{onBack && <button type="button" onClick={onBack} className="ml-2 rounded border px-3 py-2 text-sm">返回</button>}</main>
  return <main className="min-h-full bg-slate-50"><div className="mx-auto max-w-[1440px] space-y-4 p-4 pb-24 min-[800px]:p-6">{onBack && <button type="button" onClick={onBack} className="text-sm font-medium text-slate-500 hover:text-blue-600">← 返回</button>}<KeyTaskHeader workspace={workspace} onSubmitUpdate={submitUpdate} onConfirmCompletion={() => void confirm()} onReopen={() => void reopen()} /><div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_330px]"><div className="space-y-4"><CurrentProgressCard progress={workspace.current_progress} /><ExecutionPlanTable plans={workspace.execution_plans} summary={workspace.plan_summary} onOpen={setSelectedPlan} /><AchievementList items={workspace.achievements} /><IssueList items={workspace.issues} /><ExecutionTimeline events={workspace.timeline} /></div><div className="xl:sticky xl:top-4 xl:self-start"><KeyTaskContextCard workspace={workspace} /></div></div></div><ExecutionPlanDetailDrawer open={Boolean(selectedPlan)} plan={selectedPlan} workspace={workspace} onClose={() => setSelectedPlan(null)} onSubmitUpdate={submitUpdate} onEdit={() => { setSelectedPlan(null); submitUpdate() }} onMarkCompleted={(plan) => void markPlanCompleted(plan)} /></main>
}
