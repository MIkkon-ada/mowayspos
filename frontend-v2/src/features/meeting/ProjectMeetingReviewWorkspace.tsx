import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import type { MeetingItem } from '../../types'
import type { ProjectMeetingAgentAudit, ProjectMeetingAgentFact, ProjectMeetingEvidence, ProjectMeetingEvidenceSpan, ProjectMeetingProposalLineage, ProjectMeetingWorkProgressPreview } from '../../api/meetings'
import { FormalProjectMeetingMinutes } from './FormalProjectMeetingMinutes'
import { ChevronDownIcon } from '../../components/icons/ChevronDownIcon'

export type ProjectMeetingContext = {
  projectId: number
  projectName: string
  projectCode?: string
  members: Array<{ id?: number; name: string; role?: string }>
  workstreams: Array<{ id: number; title: string; status?: string }>
  keyTasks: Array<{ id: number; workstreamId: number; title: string; status?: string; assignee?: string; currentProgress?: { summary: string; nextStep: string; sourceLabel: string } }>
}

export type ProjectMeetingDraft = Pick<
  MeetingItem,
  'id' | 'project_id' | 'title' | 'meeting_type' | 'meeting_date' | 'location' | 'host' | 'participants' | 'organizer' | 'copied_to' | 'summary' | 'publish_status'
> & {
  agendaItems: ProjectMeetingAgentFact[]
  decisions: ProjectMeetingAgentFact[]
  completedItems: ProjectMeetingAgentFact[]
  nextStageWork: ProjectMeetingAgentFact[]
  risks: ProjectMeetingAgentFact[]
  priorActionTracking: ProjectMeetingAgentFact[]
  sourceFilename?: string
}

export type ExecutionScheduleChange = {
  id: number
  action?: 'update_execution_schedule' | 'create_execution_schedule' | 'confirm_work_progress' | 'review_unlinked_fact'
  scheduleId?: number | null
  workstreamId?: number | null
  parentSubtaskId?: number | null
  keyTaskId: number
  workstreamTitle?: string
  keyTaskTitle: string
  title: string
  before: Record<string, unknown>
  proposed: Record<string, unknown>
  evidence: Array<string | ProjectMeetingEvidenceSpan>
  reason?: string
  confidence?: number
  needsConfirmation?: boolean
  validationState?: 'ready' | 'needs_review' | 'blocked'
  validationErrors?: string[]
  executionStatus?: 'pending' | 'executed' | 'conflict' | 'ignored'
  conflictReason?: string[]
  lineage?: ProjectMeetingProposalLineage
}

export type ProjectMeetingReviewWorkspaceProps = {
  projectContext: ProjectMeetingContext
  meetingDraft: ProjectMeetingDraft
  meetingInfoEvidence: Record<string, ProjectMeetingEvidence>
  summaryEvidence?: ProjectMeetingEvidence
  openQuestions: ProjectMeetingAgentFact[]
  workProgressPreview?: ProjectMeetingWorkProgressPreview
  workProgressStale?: boolean
  agentAudit?: ProjectMeetingAgentAudit
  scheduleChanges: ExecutionScheduleChange[]
  isOwner: boolean
  busy?: boolean
  error?: string
  message?: string
  onSaveDraft: (draft: ProjectMeetingDraft) => void | Promise<void>
  onPublish: () => void | Promise<void>
  onApproveAndApply?: (selectedProposalIds: number[]) => void | Promise<void>
  onReviewUnlinkedFacts?: (payload: { decision: 'minutes_only' | 'link_task'; proposal_ids: number[]; key_task_id?: number }) => void | Promise<void>
  onApplyChanges: (selectedScheduleChangeIds: number[]) => void | Promise<void>
  onReturn: (reason: string) => void | Promise<void>
  onDownload: () => void | Promise<void>
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (Array.isArray(value)) return value.map(displayValue).join('、')
  if (typeof value === 'object') return Object.entries(value as Record<string, unknown>).map(([key, item]) => `${key}: ${displayValue(item)}`).join('；')
  return String(value)
}

function evidenceQuotes(evidence: Array<string | ProjectMeetingEvidenceSpan>): string[] {
  return evidence.map((item) => typeof item === 'string' ? item : item.quote).filter(Boolean)
}

function EvidenceBlock({ evidence }: { evidence?: ProjectMeetingEvidence | Array<string | ProjectMeetingEvidenceSpan> }) {
  const spans = Array.isArray(evidence) ? evidence : evidence?.evidence ?? []
  const quotes = evidenceQuotes(spans)
  if (!quotes.length) return null
  return <span className="sr-only">查看原文依据：{quotes.join('；')}</span>
}

function FactSection({ title, items, emptyLabel = '暂无内容' }: { title: string; items: ProjectMeetingAgentFact[]; emptyLabel?: string }) {
  return <section className="rounded-xl border border-slate-200 bg-white p-4">
    <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
    {items.length ? <ul className="mt-3 space-y-3 text-sm leading-6 text-slate-600">{items.map((item, index) => <li key={`${item.content}-${index}`} className="rounded-lg bg-slate-50 p-3">
      <div className="flex gap-2"><span className="text-sky-500">•</span><span>{item.content}</span>{item.needs_confirmation && <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700">建议核对原文</span>}</div>
      {item.source_note && <p className="mt-1 text-xs text-amber-700">需核对：{item.source_note}</p>}
      <EvidenceBlock evidence={item.evidence} />
    </li>)}</ul> : <p className="mt-3 text-sm text-slate-400">{emptyLabel}</p>}
  </section>
}

function ReviewRailCard({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return <section className="rounded-2xl border border-[#dfe7ef] bg-[#fffefa]/95 p-4 shadow-[0_8px_24px_rgba(25,52,72,0.06)]">
    <h2 className="text-sm font-semibold text-[#202f79]">{title}</h2>
    {description ? <p className="mt-1.5 text-[11px] leading-5 text-slate-500">{description}</p> : null}
    <div className="mt-3">{children}</div>
  </section>
}

function ReviewMetric({ value, label }: { value: number; label: string }) {
  return <div className="rounded-lg bg-[#f4f8f8] px-2 py-2 text-center">
    <strong className="block text-xl font-semibold text-[#202f79]">{value}</strong>
    <span className="text-[10px] text-slate-500">{label}</span>
  </div>
}

function LineageTrace({ change }: { change: ExecutionScheduleChange }) {
  const lineage = change.lineage
  if (!lineage) return null
  const meetingQuotes = Object.values(lineage.meeting_evidence ?? {}).flatMap((spans) => spans.map((span) => span.quote)).filter(Boolean)
  return <details className="app-disclosure mt-3 rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600">
    <summary className="cursor-pointer font-semibold text-slate-700">查看分析与来源追溯</summary>
    <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
      <section><h4 className="font-semibold text-slate-700">会议事实</h4><p className="mt-1">{lineage.source_fact_id}</p><p className="mt-1 text-slate-500">{meetingQuotes.length ? meetingQuotes.join('；') : '无字段级会议证据'}</p></section>
      <section><h4 className="font-semibold text-slate-700">项目匹配</h4><p className="mt-1">{lineage.source_match_id || '未匹配'}</p><p className="mt-1 text-slate-500">{lineage.project_evidence?.length ? displayValue(lineage.project_evidence) : '无项目基线证据'}</p></section>
      <section><h4 className="font-semibold text-slate-700">项目基线</h4><p className="mt-1">{lineage.baseline_state}</p><p className="mt-1 text-slate-500">{displayValue(Object.keys(lineage.before_baseline ?? {}).length ? lineage.before_baseline : lineage.parent_baseline)}</p></section>
      <section><h4 className="font-semibold text-slate-700">AI 判断</h4><p className="mt-1">{lineage.delta?.delta_type || '—'}</p><p className="mt-1 text-slate-500">{lineage.delta?.reasoning || '—'}</p></section>
      <section><h4 className="font-semibold text-slate-700">建议修改</h4><p className="mt-1">{displayValue(change.proposed)}</p><p className="mt-1 text-slate-500">字段来源：{displayValue(lineage.field_sources)}</p>{lineage.owner_edit_history?.length ? <p className="mt-1 text-amber-700">负责人编辑：{displayValue(lineage.owner_edit_history)}</p> : null}</section>
    </div>
  </details>
}

function ScheduleChangeList({ changes, selectedIds, isOwner, busy, onToggle }: { changes: ExecutionScheduleChange[]; selectedIds: Set<number>; isOwner: boolean; busy: boolean; onToggle: (change: ExecutionScheduleChange) => void }) {
  if (!changes.length) return <p className="rounded-xl border border-dashed border-slate-200 px-4 py-7 text-center text-sm text-slate-400">本次会议没有执行安排变更建议</p>
  return <div className="space-y-3">{changes.map((change) => {
    const blocked = change.validationState === 'blocked' || change.needsConfirmation || change.executionStatus === 'conflict'
    const isNewPlan = change.action === 'create_execution_schedule'
    return <article key={change.id} className={`rounded-xl border p-3 ${blocked ? 'border-rose-200 bg-rose-50/40' : 'border-slate-200 bg-slate-50/60'}`}>
      <div className="flex items-start gap-2.5">
        <input type="checkbox" checked={selectedIds.has(change.id)} onChange={() => onToggle(change)} disabled={!isOwner || busy || blocked} className="mt-1 h-4 w-4 rounded border-slate-300 text-sky-600" aria-label={`选择${isNewPlan ? '新增任务计划' : '变更任务计划'} ${change.id}`} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2"><span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${isNewPlan ? 'bg-emerald-100 text-emerald-700' : 'bg-sky-100 text-sky-700'}`}>{isNewPlan ? '新增任务计划建议' : '变更任务计划建议'}</span><h3 className="text-xs font-semibold text-slate-800">{change.title}</h3>{blocked && <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-semibold text-rose-700">{change.executionStatus === 'conflict' ? '数据已变化，不可回填' : change.needsConfirmation ? '待确认，不可回填' : '无法回填'}</span>}</div>
          <p className="mt-1 text-[11px] leading-5 text-slate-500">父工作流：{change.workstreamTitle || '未匹配'} · 关键任务：{change.keyTaskTitle || '未匹配'}</p>
          <div className="mt-2 grid gap-2 text-[11px] leading-5"><div className="rounded-lg border border-slate-200 bg-white p-2.5"><div className="font-semibold text-slate-500">{isNewPlan ? '新增计划不适用' : '当前执行安排'}</div><p className="mt-1 text-slate-600">{displayValue(change.before)}</p></div><div className="rounded-lg border border-sky-100 bg-sky-50/60 p-2.5"><div className="font-semibold text-sky-700">会议建议</div><p className="mt-1 text-slate-700">{displayValue(change.proposed)}</p></div></div>
          <EvidenceBlock evidence={change.evidence} />
          {change.validationErrors?.length ? <p className="mt-2 text-[11px] text-rose-600">{change.validationErrors.join('；')}</p> : null}
          {change.conflictReason?.length ? <p className="mt-2 text-[11px] text-rose-700">冲突原因：{change.conflictReason.join('；')}</p> : null}
          <LineageTrace change={change} />
        </div>
      </div>
    </article>
  })}</div>
}

function WordActionMappingTable({
  context, preview, changes, selectedIds,
}: {
  context: ProjectMeetingContext
  preview: ProjectMeetingWorkProgressPreview
  changes: ExecutionScheduleChange[]
  selectedIds: Set<number>
}) {
  const actions = preview.action_rows ?? []
  if (!actions.length) return null
  const proposalByFact = new Map<string, ExecutionScheduleChange>()
  for (const change of changes) {
    for (const factId of change.lineage?.source_fact_ids ?? []) proposalByFact.set(factId, change)
  }
  const linkedByFact = new Map<string, ExecutionScheduleChange>()
  for (const change of changes) {
    if (!change.lineage?.linked_key_task_id) continue
    for (const factId of change.lineage.source_fact_ids ?? []) linkedByFact.set(factId, change)
  }
  const matchedCount = actions.filter((action) => action.match_state === 'matched' || linkedByFact.has(action.fact_id)).length
  return <section aria-label="Word本周待办与关键任务对照" className="mt-4 overflow-hidden rounded-[18px] border border-[#dce5eb] bg-[#fffefa] shadow-[0_12px_32px_rgba(25,52,72,0.07)]">
    <div className="flex flex-wrap items-end justify-between gap-3 border-b border-[#dce5eb] bg-[#f8fbfa] px-5 py-4 sm:px-6">
      <div><span className="text-[10px] font-bold tracking-[0.16em] text-[#168ea9]">WORD 原始待办</span><h2 className="mt-1 text-lg font-semibold text-[#202f79]">本周待办与关键任务对照</h2><p className="mt-1 text-xs leading-5 text-slate-500">逐行保留 Word 的编号、内容、负责人、追踪人和期限。只有明确对应的待办才进入推进表建议；其他内容保留在纪要中。</p></div>
      <span className="rounded-full border border-[#cddfe4] bg-white px-3 py-1 text-xs font-medium text-[#385a70]">原文 {actions.length} 条 · 明确对应 {matchedCount} 条 · 待核对 {actions.length - matchedCount} 条</span>
    </div>
    <div className="overflow-x-auto"><table className="w-full min-w-[980px] border-collapse text-left text-xs leading-5">
      <thead className="bg-[#f3f7f8] text-[#526879]"><tr><th className="w-24 px-4 py-3 font-semibold">编号</th><th className="min-w-[330px] px-4 py-3 font-semibold">Word 待办原文</th><th className="w-40 px-4 py-3 font-semibold">负责人 / 追踪人</th><th className="w-28 px-4 py-3 font-semibold">期限</th><th className="min-w-[210px] px-4 py-3 font-semibold">对应关键任务</th><th className="w-28 px-4 py-3 font-semibold">审核状态</th></tr></thead>
      <tbody className="divide-y divide-[#e8eef1]">{actions.map((action, index) => {
        const proposal = proposalByFact.get(action.fact_id)
        const mergedProposal = changes.find((change) => change.id === proposal?.lineage?.merged_into_proposal_id)
        const syncProposal = proposal?.action === 'confirm_work_progress' ? proposal : mergedProposal
        const candidate = context.keyTasks.find((task) => task.id === action.suggested_key_task_id)
        const linkedTask = context.keyTasks.find((task) => task.id === linkedByFact.get(action.fact_id)?.lineage?.linked_key_task_id)
        const ready = syncProposal?.executionStatus === 'pending' && syncProposal.validationState === 'ready'
        const status = syncProposal?.executionStatus === 'executed' ? '已同步'
          : ready && syncProposal && selectedIds.has(syncProposal.id) ? '待同步'
            : action.match_state === 'matched' || proposal?.executionStatus === 'ignored' || linkedTask ? '仅留纪要' : '待核对归属'
        return <tr key={action.fact_id || `${action.code}-${index}`} className="align-top text-slate-700">
          <td className="px-4 py-3 font-semibold text-[#202f79]">{action.code || `第 ${index + 1} 项`}</td>
          <td className="px-4 py-3 whitespace-pre-wrap">{action.content}</td>
          <td className="px-4 py-3"><span className="block">{action.owner || '原文未注明'}</span><span className="mt-0.5 block text-slate-400">追踪：{action.tracker || '原文未注明'}</span></td>
          <td className="px-4 py-3">{action.due_date || '原文未注明'}</td>
          <td className="px-4 py-3">{linkedTask ? <span className="font-medium text-[#202f79]">人工关联：{linkedTask.title}</span> : action.match_state === 'matched' ? <span className="font-medium text-[#202f79]">{action.key_task_title}</span> : <span className="text-amber-700">{candidate ? `候选：${candidate.title}，需核对` : '未找到可靠对应任务'}</span>}</td>
          <td className="px-4 py-3"><span className={`inline-flex rounded-full px-2 py-0.5 font-semibold ${status === '已同步' ? 'bg-emerald-50 text-emerald-700' : status === '待同步' ? 'bg-sky-50 text-sky-700' : 'bg-amber-50 text-amber-700'}`}>{status}</span></td>
        </tr>
      })}</tbody>
    </table></div>
  </section>
}

function WorkProgressReviewTable({
  context, preview, proposals, selectedIds, isOwner, busy, onToggle,
}: {
  context: ProjectMeetingContext
  preview: ProjectMeetingWorkProgressPreview
  proposals: ExecutionScheduleChange[]
  selectedIds: Set<number>
  isOwner: boolean
  busy: boolean
  onToggle: (proposal: ExecutionScheduleChange) => void
}) {
  const previewByTask = new Map(preview.rows.map((row) => [row.key_task_id, row]))
  const proposalByTask = new Map(proposals.map((proposal) => [proposal.keyTaskId, proposal]))
  const affectedCount = new Set([...previewByTask.keys(), ...proposalByTask.keys()]).size
  return <section aria-label="工作推进表审核预览" className="mt-4 overflow-hidden rounded-[18px] border border-[#dce5eb] bg-[#fffefa] shadow-[0_12px_32px_rgba(25,52,72,0.07)]">
    <div className="flex flex-wrap items-end justify-between gap-3 border-b border-[#dce5eb] bg-[#f8fbfa] px-5 py-4 sm:px-6">
      <div><span className="text-[10px] font-bold tracking-[0.16em] text-[#168ea9]">WORD 导入 · 项目推进</span><h2 className="mt-1 text-lg font-semibold text-[#202f79]">工作推进表审核预览</h2><p className="mt-1 text-xs leading-5 text-slate-500">按现有重点工作与关键任务展示；勾选的建议将在审核通过后写入推进表。</p></div>
      <span className="rounded-full border border-[#cddfe4] bg-white px-3 py-1 text-xs font-medium text-[#385a70]">本次涉及 {affectedCount} 项 / 共 {context.keyTasks.length} 项关键任务</span>
    </div>
    <div className="space-y-5 p-4 sm:p-5">
      {context.workstreams.map((workstream) => {
        const tasks = context.keyTasks.filter((task) => task.workstreamId === workstream.id)
        if (!tasks.length) return null
        return <section key={workstream.id} className="overflow-hidden rounded-xl border border-[#e3e9ee] bg-white">
          <div className="border-b border-[#e3e9ee] bg-[#f3f8f8] px-4 py-2.5 text-sm font-semibold text-[#202f79]">{workstream.title}</div>
          <div className="divide-y divide-[#e9eef2]">
            {tasks.map((task) => {
              const row = previewByTask.get(task.id)
              const proposal = proposalByTask.get(task.id)
              const proposed = proposal?.proposed ?? row?.proposed ?? {}
              const relatedFacts = [...new Map(
                [...(row?.related_facts ?? []), ...(proposal?.lineage?.related_facts ?? [])]
                  .map((fact) => [fact.fact_id, fact] as const),
              ).values()]
              const ready = proposal?.executionStatus === 'pending' && proposal?.validationState === 'ready' && !proposal.needsConfirmation
              return <article key={task.id} className={`grid gap-3 px-4 py-4 lg:grid-cols-[minmax(155px,0.9fr)_minmax(190px,1fr)_minmax(270px,1.5fr)_94px] lg:gap-4 ${row ? 'bg-white' : 'bg-[#fbfcfc]'}`}>
                <div><strong className="block text-sm leading-5 text-slate-800">{task.title}</strong><span className="mt-1 block text-xs text-slate-500">{task.assignee || '未指定负责人'} · {task.status || '未设置状态'}</span></div>
                <div className="text-xs leading-5 text-slate-600"><span className="block text-[11px] font-semibold text-slate-400">当前推进</span><p className="mt-1 whitespace-pre-wrap">{task.currentProgress?.summary || '暂无已确认进展'}</p>{task.currentProgress?.nextStep && <p className="mt-1 text-slate-500">下一步：{task.currentProgress.nextStep}</p>}</div>
                <div className="text-xs leading-5"><span className="block text-[11px] font-semibold text-[#168ea9]">Word 建议</span>{typeof proposed.progress_summary === 'string' && proposed.progress_summary && <p className="mt-1 whitespace-pre-wrap text-slate-700"><span className="font-semibold">最新进展：</span>{proposed.progress_summary}</p>}{typeof proposed.next_step === 'string' && proposed.next_step && <p className="mt-1 whitespace-pre-wrap text-slate-700"><span className="font-semibold">下一步计划：</span>{proposed.next_step}</p>}{!proposed.progress_summary && !proposed.next_step && <p className="mt-1 text-slate-400">{row ? '会议提及，暂无可直接同步的字段' : '本次会议未提及'}</p>}{relatedFacts.length ? <div className="mt-2 border-l-2 border-[#c6dfe4] pl-2 text-[11px] text-slate-500">{relatedFacts.map((fact) => <p key={fact.fact_id} className="mt-1 whitespace-pre-wrap">{fact.content}</p>)}</div> : null}</div>
                <div className="lg:pt-5">{ready && proposal ? <label className="inline-flex cursor-pointer items-center gap-1.5 whitespace-nowrap text-xs font-medium text-[#202f79]"><input type="checkbox" checked={selectedIds.has(proposal.id)} onChange={() => onToggle(proposal)} disabled={!isOwner || busy} className="h-4 w-4 rounded border-slate-300 text-[#168ea9]" aria-label={`同步${task.title}的会议建议`} />同步此项</label> : proposal?.executionStatus === 'executed' ? <span className="text-xs font-semibold text-emerald-700">已同步</span> : proposal ? <span className="text-xs text-amber-700">需复核</span> : <span className="text-xs text-slate-400">仅展示</span>}</div>
              </article>
            })}
          </div>
        </section>
      })}
      {!context.keyTasks.length && <p className="rounded-lg border border-dashed border-[#dce5eb] px-4 py-7 text-center text-sm text-slate-500">项目尚无关键任务，会议事项暂时只能保留在纪要中。</p>}
    </div>
  </section>
}

export function ProjectMeetingReviewWorkspace({
  projectContext, meetingDraft, meetingInfoEvidence, summaryEvidence, openQuestions, workProgressPreview, workProgressStale = false, agentAudit, scheduleChanges,
  isOwner, busy = false, error = '', message = '', onSaveDraft, onPublish, onApproveAndApply, onReviewUnlinkedFacts, onApplyChanges, onReturn, onDownload,
}: ProjectMeetingReviewWorkspaceProps) {
  const [selectedScheduleChangeIds, setSelectedScheduleChangeIds] = useState<Set<number>>(() => new Set(
    scheduleChanges.filter((change) => change.action === 'confirm_work_progress' && change.executionStatus === 'pending' && change.validationState === 'ready').map((change) => change.id),
  ))
  const [returnReason, setReturnReason] = useState('')
  const [linkedTaskChoices, setLinkedTaskChoices] = useState<Record<number, string>>({})
  const [editableDraft, setEditableDraft] = useState<ProjectMeetingDraft>(meetingDraft)
  const [isEditing, setIsEditing] = useState(false)
  const isPublished = editableDraft.publish_status === 'published'
  const factFields = ['agendaItems', 'decisions', 'completedItems', 'nextStageWork', 'risks', 'priorActionTracking'] as const
  const metadataFields = ['title', 'meeting_type', 'meeting_date', 'location', 'host', 'participants', 'organizer', 'copied_to', 'summary'] as const
  const factValues = (items: ProjectMeetingAgentFact[]) => items.map(({ content, code, topic, owner, tracker, due_date, source_note, status, progress_note, human_edited }) => ({ content, code: code || '', topic: topic || '', owner: owner || '', tracker: tracker || '', due_date: due_date || '', source_note: source_note || '', status: status || '', progress_note: progress_note || '', human_edited: Boolean(human_edited) }))
  const hasUnsavedChanges = metadataFields.some((field) => editableDraft[field] !== meetingDraft[field])
    || factFields.some((field) => JSON.stringify(factValues(editableDraft[field])) !== JSON.stringify(factValues(meetingDraft[field])))
  const hasEmptyFact = factFields.some((field) => editableDraft[field].some((item) => !item.content.trim()))
  const visibleMeetingInfoEvidence = Object.fromEntries(Object.entries(meetingInfoEvidence).filter(([field]) =>
    !metadataFields.some((key) => key === field && editableDraft[key] !== meetingDraft[key]),
  )) as Record<string, ProjectMeetingEvidence>
  const visibleSummaryEvidence = editableDraft.summary === meetingDraft.summary ? summaryEvidence : undefined
  const hasPendingScheduleChanges = scheduleChanges.some((change) => change.action !== 'confirm_work_progress' && change.action !== 'review_unlinked_fact' && change.executionStatus === 'pending')
  const pendingScheduleChangeIds = scheduleChanges.filter((change) => change.executionStatus === 'pending').map((change) => change.id).join(',')
  const workProgressChanges = scheduleChanges.filter((change) => change.action === 'confirm_work_progress')
  const planChanges = scheduleChanges.filter((change) => change.action === 'create_execution_schedule' || change.action === 'update_execution_schedule')
  const unlinkedChanges = scheduleChanges.filter((change) => change.action === 'review_unlinked_fact')
  const pendingUnlinked = unlinkedChanges.filter((change) => change.executionStatus === 'pending')
  const defaultWorkProgressIds = workProgressChanges.filter((change) => change.executionStatus === 'pending' && change.validationState === 'ready').map((change) => change.id).join(',')

  useEffect(() => {
    setEditableDraft((current) => ({ ...current, publish_status: meetingDraft.publish_status }))
  }, [meetingDraft.publish_status])

  useEffect(() => {
    setEditableDraft(meetingDraft)
    setReturnReason('')
    setLinkedTaskChoices({})
    setIsEditing(false)
    setSelectedScheduleChangeIds(new Set(scheduleChanges.filter((change) => change.action === 'confirm_work_progress' && change.executionStatus === 'pending' && change.validationState === 'ready').map((change) => change.id)))
  }, [meetingDraft.id])

  useEffect(() => {
    setSelectedScheduleChangeIds((current) => new Set([...current, ...defaultWorkProgressIds.split(',').filter(Boolean).map(Number)]))
  }, [defaultWorkProgressIds])

  useEffect(() => {
    if (isPublished) setIsEditing(false)
  }, [isPublished])

  useEffect(() => {
    setEditableDraft(meetingDraft)
  }, [meetingDraft.agendaItems, meetingDraft.decisions, meetingDraft.completedItems, meetingDraft.nextStageWork, meetingDraft.risks, meetingDraft.priorActionTracking])

  useEffect(() => {
    setSelectedScheduleChangeIds((current) => new Set(
      [...current].filter((id) => scheduleChanges.some((change) => change.id === id && change.executionStatus === 'pending')),
    ))
  }, [pendingScheduleChangeIds])

  const toggleScheduleChange = (change: ExecutionScheduleChange) => {
    if (change.validationState === 'blocked' || change.needsConfirmation || change.executionStatus !== 'pending') return
    setSelectedScheduleChangeIds((current) => {
      const next = new Set(current)
      if (next.has(change.id)) next.delete(change.id)
      else next.add(change.id)
      return next
    })
  }

  const handlePublish = () => {
    if (!isOwner || busy) return
    void onPublish()
  }

  const handleApplyChanges = () => {
    const selectedPlanIds = planChanges.filter((change) => selectedScheduleChangeIds.has(change.id)).map((change) => change.id)
    if (!isOwner || busy || !selectedPlanIds.length) return
    void onApplyChanges(selectedPlanIds)
  }

  const handleApproveAndApply = () => {
    const selectedProgressIds = workProgressChanges.filter((change) => selectedScheduleChangeIds.has(change.id)).map((change) => change.id)
    if (!isOwner || busy || workProgressStale || hasUnsavedChanges || hasEmptyFact || !selectedProgressIds.length || !onApproveAndApply) return
    void onApproveAndApply(selectedProgressIds)
  }

  const handleReturn = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const reason = returnReason.trim()
    if (!isOwner || busy || !reason) return
    void onReturn(reason)
  }

  const agendaCount = editableDraft.agendaItems.length
  const actionCount = editableDraft.nextStageWork.length
  const pendingCount = pendingUnlinked.length + (unlinkedChanges.length ? 0 : openQuestions.length)
  const readyChangeCount = planChanges.filter((change) => change.executionStatus === 'pending' && change.validationState !== 'blocked' && !change.needsConfirmation).length

  return <section className="mx-auto w-full max-w-[1680px] bg-[#edf2f5] px-3 py-4 sm:px-5 lg:px-6" aria-label="项目会议纪要审核工作台">
    <header className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-4 border-b border-[#dfe7ef] bg-[#fffefa]/95 px-4 py-4 shadow-sm backdrop-blur sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <img className="h-9 w-[108px] object-contain object-left mix-blend-multiply" src="/moways-logo.png" alt="MOWAYS 博维咨询" />
        <div className="border-l border-[#d8dee9] pl-3"><strong className="block text-sm tracking-[0.05em] text-[#202f79]">会议纪要审核工作台</strong><span className="mt-0.5 block text-[11px] text-slate-500">AI 整理 · 人工核对 · 正式留档</span></div>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2">
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${isPublished ? 'border-[#b8dfd0] bg-[#eaf6f1] text-[#216d57]' : 'border-[#f1d59d] bg-[#fff4df] text-[#9b671f]'}`}><span className={`h-1.5 w-1.5 rounded-full ${isPublished ? 'bg-[#2b8467]' : 'bg-[#d99943]'}`} />{isPublished ? '已发布' : '待审核草稿'}</span>
        <button type="button" onClick={() => void onDownload()} disabled={busy} className="inline-flex min-h-9 items-center justify-center rounded-lg border border-[#dfe7ef] bg-white px-3.5 text-xs font-semibold text-[#172638] transition hover:-translate-y-px hover:border-[#9fc7d0] disabled:cursor-not-allowed disabled:opacity-50">下载 Word</button>
        {!isPublished && isOwner ? <button type="button" aria-pressed={isEditing} onClick={() => setIsEditing((current) => !current)} disabled={busy} className="inline-flex min-h-9 items-center justify-center rounded-lg border border-[#b8d9de] bg-white px-3.5 text-xs font-semibold text-[#168ea9] transition hover:border-[#168ea9] disabled:opacity-50">{isEditing ? '退出编辑' : hasUnsavedChanges ? '继续编辑' : '编辑纪要'}</button> : null}
      </div>
    </header>

    {message && <p className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>}
    {error && <p className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
    {workProgressStale && <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">待办内容已修改，当前任务匹配建议基于修改前的 Word，不能继续同步推进表。可以仅发布会议纪要；如需同步，请重新上传并分析修改后的 Word。</p>}

    {workProgressPreview && <WordActionMappingTable context={projectContext} preview={workProgressPreview} changes={scheduleChanges} selectedIds={selectedScheduleChangeIds} />}
    {workProgressPreview && <WorkProgressReviewTable context={projectContext} preview={workProgressPreview} proposals={workProgressChanges} selectedIds={selectedScheduleChangeIds} isOwner={isOwner} busy={busy} onToggle={toggleScheduleChange} />}

    {unlinkedChanges.length ? <section aria-label="未关联会议事项审核" className="mt-4 rounded-[18px] border border-[#e8dfcd] bg-[#fffefa] p-4 shadow-[0_8px_22px_rgba(25,52,72,0.05)] sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-base font-semibold text-[#202f79]">尚未对应关键任务的会议事项</h2><p className="mt-1 text-xs leading-5 text-slate-500">这些内容会保留在会议纪要中，不影响审核发布。如需同步某项进展，可先为它选择关键任务。</p></div><span className="rounded-full bg-[#fff1da] px-2.5 py-1 text-xs font-semibold text-[#915f21]">可选关联 {pendingUnlinked.length} 项</span></div>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">{unlinkedChanges.map((change) => {
        const fact = change.before
        const pending = change.executionStatus === 'pending'
        return <article key={change.id} className="rounded-xl border border-[#e7e9e4] bg-white p-3.5">
          <p className="text-sm font-medium leading-6 text-slate-800">{String(fact.content || change.title)}</p>
          <p className="mt-1.5 text-xs leading-5 text-[#806642]">AI 未自动关联：{String(fact.reason || change.reason || '现有任务中没有足够明确的对应项')}</p>
          {pending && isOwner && onReviewUnlinkedFacts ? <div className="mt-3 flex flex-wrap items-center gap-2">
            <div className="relative min-w-[170px] flex-1"><select aria-label={`为${String(fact.content || change.title)}选择关键任务`} value={linkedTaskChoices[change.id] || ''} onChange={(event) => setLinkedTaskChoices((current) => ({ ...current, [change.id]: event.target.value }))} disabled={busy} className="w-full appearance-none rounded-lg border border-[#d6e2e9] bg-white py-2 pl-3 pr-8 text-xs text-slate-700"><option value="">选择关键任务</option>{projectContext.keyTasks.map((task) => <option key={task.id} value={task.id}>{projectContext.workstreams.find((workstream) => workstream.id === task.workstreamId)?.title} / {task.title}</option>)}</select><span className="pointer-events-none absolute right-2.5 top-2.5 text-slate-500"><ChevronDownIcon /></span></div>
            <button type="button" onClick={() => void onReviewUnlinkedFacts({ decision: 'link_task', proposal_ids: [change.id], key_task_id: Number(linkedTaskChoices[change.id]) })} disabled={busy || workProgressStale || !linkedTaskChoices[change.id]} className="rounded-lg bg-[#168ea9] px-3 py-2 text-xs font-semibold text-white disabled:opacity-40">关联并生成建议</button>
            <button type="button" onClick={() => void onReviewUnlinkedFacts({ decision: 'minutes_only', proposal_ids: [change.id] })} disabled={busy} className="rounded-lg border border-[#d6e2e9] px-3 py-2 text-xs font-medium text-slate-600 disabled:opacity-40">标记为仅留纪要</button>
          </div> : <p className="mt-3 text-xs font-medium text-[#216d57]">{change.lineage?.merged_into_proposal_id ? '已关联关键任务，纳入推进表建议' : change.lineage?.linked_key_task_id ? '已关联关键任务，仅保留会议记录' : '已确认仅保留在会议纪要'}</p>}
        </article>
      })}</div>
      {pendingUnlinked.length > 1 && isOwner && onReviewUnlinkedFacts && <button type="button" onClick={() => void onReviewUnlinkedFacts({ decision: 'minutes_only', proposal_ids: pendingUnlinked.map((change) => change.id) })} disabled={busy} className="mt-3 rounded-lg border border-[#d6e2e9] bg-white px-3.5 py-2 text-xs font-medium text-slate-600 disabled:opacity-40">全部标记为仅留纪要</button>}
    </section> : null}

    <div className="mt-4 grid gap-4 min-[1700px]:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0">
        <section aria-label="会议纪要草稿">
          {(hasUnsavedChanges || hasEmptyFact) && <p className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">{hasEmptyFact ? '有空白事项，请填写或移除后保存。' : '当前修改尚未保存；保存后才能发布。'}</p>}
          <FormalProjectMeetingMinutes draft={editableDraft} meetingInfoEvidence={visibleMeetingInfoEvidence} summaryEvidence={visibleSummaryEvidence} editable={isEditing && !isPublished && isOwner} disabled={busy} onChange={(field, value) => setEditableDraft((current) => ({ ...current, [field]: value }))} onFactsChange={(field, items) => setEditableDraft((current) => ({ ...current, [field]: items }))} />
        </section>
      </div>

      <aside className="grid content-start gap-4 lg:grid-cols-2 min-[1700px]:grid-cols-1" aria-label="AI审核侧栏">
        <ReviewRailCard title="审核概览" description="核对 Word 纪要与勾选的推进表建议；未关联事项会保留在纪要中。">
          <div className="grid grid-cols-4 gap-1.5"><ReviewMetric value={agendaCount} label="议程" /><ReviewMetric value={actionCount} label="行动项" /><ReviewMetric value={pendingCount} label="未关联" /><ReviewMetric value={planChanges.length} label="计划建议" /></div>
          {pendingCount || planChanges.length ? <div className="mt-3 flex gap-2 rounded-lg border border-[#f2d4b1] bg-[#fff7ed] px-2.5 py-2.5 text-[11px] leading-5 text-[#8f5e30]"><span className="mt-0.5 text-sm" aria-hidden="true">!</span><span>{pendingCount ? `${pendingCount} 项未关联内容默认保留在纪要，可按需关联任务。` : ''}{planChanges.length ? ` ${readyChangeCount} 条计划建议可在发布后单独回填。` : ''}</span></div> : <p className="mt-3 rounded-lg bg-[#eaf6f1] px-2.5 py-2 text-[11px] leading-5 text-[#216d57]">当前没有需要额外处理的内容。</p>}
          {agentAudit ? <p className="mt-3 text-[10px] leading-4 text-slate-400">AI 已完成 {agentAudit.event_count} 个处理事件 · {agentAudit.tool_call_count} 次工具调用</p> : null}
        </ReviewRailCard>

        {!unlinkedChanges.length && openQuestions.length ? <ReviewRailCard title="未关联的会议事项" description="请结合会议原文核对这些事项的任务归属。">
          <FactSection title="尚未找到明确对应任务" items={openQuestions} />
        </ReviewRailCard> : null}

        {planChanges.length ? <ReviewRailCard title="项目变更建议" description="发布后可单独选择回填，不与发布纪要绑定。">
          <p className="mb-3 text-xs text-slate-500">已选 {planChanges.filter((change) => selectedScheduleChangeIds.has(change.id)).length} / {planChanges.length} 项</p>
          <ScheduleChangeList changes={planChanges} selectedIds={selectedScheduleChangeIds} isOwner={isOwner} busy={busy} onToggle={toggleScheduleChange} />
          {isPublished && hasPendingScheduleChanges ? <button type="button" onClick={handleApplyChanges} disabled={!isOwner || busy || !planChanges.some((change) => selectedScheduleChangeIds.has(change.id))} className="mt-3 w-full rounded-lg bg-[#168ea9] px-3 py-2.5 text-xs font-semibold text-white hover:bg-[#11798e] disabled:opacity-50">回填已选 {planChanges.filter((change) => selectedScheduleChangeIds.has(change.id)).length} 项变更</button> : null}
        </ReviewRailCard> : null}

        {!isPublished && <ReviewRailCard title="退回修改" description="如果纪要内容有误，填写原因后退回；内容无误时使用页面底部的审核按钮。">
          <form onSubmit={handleReturn}>
            <label htmlFor="project-meeting-return-reason" className="block text-xs font-semibold text-slate-700">退回原因<span className="text-rose-500">*</span></label>
            <textarea id="project-meeting-return-reason" aria-label="退回原因" value={returnReason} onChange={(event) => setReturnReason(event.target.value)} disabled={!isOwner || busy} rows={3} className="mt-2 w-full resize-y rounded-lg border border-slate-200 px-3 py-2 text-xs leading-5 text-slate-700 disabled:bg-slate-50" placeholder="请说明需要补充或修改的内容" />
            <button type="submit" disabled={!isOwner || busy || !returnReason.trim()} className="mt-2 w-full rounded-lg border border-rose-200 bg-white px-3 py-2 text-xs font-semibold text-rose-600 disabled:opacity-50">填写原因并退回</button>
          </form>
        </ReviewRailCard>}
      </aside>
    </div>

    {!isPublished && <footer className="sticky bottom-3 z-10 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[#172638]/95 px-4 py-3 text-white shadow-[0_-8px_28px_rgba(23,38,56,0.16)] backdrop-blur sm:px-5">
      <p className="m-0 text-xs text-[#cbd8e0]">核对 Word 纪要与勾选的推进表建议；未关联事项会保留在纪要中。修改后请先保存。</p>
      <div className="flex flex-wrap gap-2">
        {(isEditing || hasUnsavedChanges) ? <button type="button" onClick={() => void onSaveDraft(editableDraft)} disabled={!isOwner || busy || hasEmptyFact || !hasUnsavedChanges} className="rounded-lg border border-[#5f7789] bg-transparent px-3.5 py-2 text-xs font-semibold text-white disabled:opacity-50">保存修改</button> : null}
        {workProgressChanges.length && workProgressChanges.some((change) => selectedScheduleChangeIds.has(change.id)) && onApproveAndApply ? <button type="button" onClick={handleApproveAndApply} disabled={!isOwner || busy || workProgressStale || hasUnsavedChanges || hasEmptyFact} className="rounded-lg border border-[#f6ce8e] bg-[#f6ce8e] px-3.5 py-2 text-xs font-semibold text-[#202f79] disabled:opacity-50">审核通过并同步推进表</button> : null}
        <button type="button" onClick={handlePublish} disabled={!isOwner || busy || hasUnsavedChanges || hasEmptyFact} className="rounded-lg border border-[#5f7789] bg-transparent px-3.5 py-2 text-xs font-semibold text-white disabled:opacity-50">{workProgressChanges.length ? '仅发布会议纪要' : '发布会议纪要'}</button>
      </div>
    </footer>}
  </section>
}
