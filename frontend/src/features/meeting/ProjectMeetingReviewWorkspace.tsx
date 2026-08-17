import { useEffect, useState, type FormEvent } from 'react'
import type { MeetingItem } from '../../types'
import type { ProjectMeetingAgentAudit, ProjectMeetingAgentFact, ProjectMeetingEvidence, ProjectMeetingEvidenceSpan, ProjectMeetingProposalLineage } from '../../api/meetings'
import { TYPE_STYLE, typeLabel } from './meetingUtils'

export type ProjectMeetingContext = {
  projectId: number
  projectName: string
  projectCode?: string
  members: Array<{ id?: number; name: string; role?: string }>
  workstreams: Array<{ id: number; title: string; status?: string }>
  keyTasks: Array<{ id: number; workstreamId: number; title: string; status?: string; progress?: string }>
}

export type ProjectMeetingDraft = Pick<
  MeetingItem,
  'id' | 'project_id' | 'title' | 'meeting_type' | 'meeting_date' | 'location' | 'host' | 'participants' | 'organizer' | 'copied_to' | 'summary' | 'publish_status'
> & {
  decisions: ProjectMeetingAgentFact[]
  actions: ProjectMeetingAgentFact[]
  risks: ProjectMeetingAgentFact[]
  sourceFilename?: string
}

export type ExecutionScheduleChange = {
  id: number
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
  executionStatus?: 'pending' | 'executed' | 'conflict'
  conflictReason?: string[]
  lineage?: ProjectMeetingProposalLineage
}

export type ProjectMeetingReviewWorkspaceProps = {
  projectContext: ProjectMeetingContext
  meetingDraft: ProjectMeetingDraft
  meetingInfoEvidence: Record<string, ProjectMeetingEvidence>
  summaryEvidence?: ProjectMeetingEvidence
  openQuestions: ProjectMeetingAgentFact[]
  agentAudit?: ProjectMeetingAgentAudit
  scheduleChanges: ExecutionScheduleChange[]
  isOwner: boolean
  busy?: boolean
  error?: string
  message?: string
  onSaveDraft: (draft: ProjectMeetingDraft) => void | Promise<void>
  onPublish: () => void | Promise<void>
  onApplyChanges: (selectedScheduleChangeIds: number[]) => void | Promise<void>
  onReturn: (reason: string) => void | Promise<void>
  onDownload: () => void | Promise<void>
}

const fieldLabels: Array<[keyof ProjectMeetingDraft, string]> = [
  ['meeting_date', '会议日期'], ['location', '会议地点'],
  ['host', '主持人'], ['participants', '参会人员'],
]

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
  const blocked = !Array.isArray(evidence) && evidence?.validation.state === 'blocked'
  if (!quotes.length) return null
  return <details className="mt-2 text-xs text-slate-500">
    <summary className="cursor-pointer font-medium text-sky-700">查看原文依据{blocked ? '（待核验）' : ''}</summary>
    <ul className="mt-2 space-y-1 rounded-lg border border-dashed border-slate-200 bg-slate-50 p-3 text-slate-600">{quotes.map((quote, index) => <li key={`${quote}-${index}`}>“{quote}”</li>)}</ul>
  </details>
}

function FactSection({ title, items, emptyLabel = '暂无内容' }: { title: string; items: ProjectMeetingAgentFact[]; emptyLabel?: string }) {
  return <section className="rounded-xl border border-slate-200 bg-white p-4">
    <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
    {items.length ? <ul className="mt-3 space-y-3 text-sm leading-6 text-slate-600">{items.map((item, index) => <li key={`${item.content}-${index}`} className="rounded-lg bg-slate-50 p-3">
      <div className="flex gap-2"><span className="text-sky-500">•</span><span>{item.content}</span>{item.needs_confirmation && <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700">待确认</span>}</div>
      <EvidenceBlock evidence={item.evidence} />
    </li>)}</ul> : <p className="mt-3 text-sm text-slate-400">{emptyLabel}</p>}
  </section>
}

function LineageTrace({ change }: { change: ExecutionScheduleChange }) {
  const lineage = change.lineage
  if (!lineage) return null
  const meetingQuotes = Object.values(lineage.meeting_evidence ?? {}).flatMap((spans) => spans.map((span) => span.quote)).filter(Boolean)
  return <details className="mt-3 rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600">
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

export function ProjectMeetingReviewWorkspace({
  meetingDraft, meetingInfoEvidence, summaryEvidence, openQuestions, scheduleChanges,
  isOwner, busy = false, error = '', message = '', onSaveDraft, onPublish, onApplyChanges, onReturn, onDownload,
}: ProjectMeetingReviewWorkspaceProps) {
  const [selectedScheduleChangeIds, setSelectedScheduleChangeIds] = useState<Set<number>>(new Set())
  const [returnReason, setReturnReason] = useState('')
  const [editableDraft, setEditableDraft] = useState<ProjectMeetingDraft>(meetingDraft)
  const meetingTypeLabel = typeLabel(editableDraft.meeting_type)
  const isPublished = editableDraft.publish_status === 'published'
  const hasPendingScheduleChanges = scheduleChanges.some((change) => change.executionStatus === 'pending')
  const pendingScheduleChangeIds = scheduleChanges.filter((change) => change.executionStatus === 'pending').map((change) => change.id).join(',')

  useEffect(() => {
    setEditableDraft((current) => ({ ...current, publish_status: meetingDraft.publish_status }))
  }, [meetingDraft.publish_status])

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
    if (!isOwner || busy || !selectedScheduleChangeIds.size) return
    void onApplyChanges([...selectedScheduleChangeIds])
  }

  const handleReturn = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const reason = returnReason.trim()
    if (!isOwner || busy || !reason) return
    void onReturn(reason)
  }

  return <section className="mx-auto w-full max-w-[1240px] space-y-5 rounded-2xl bg-[#F5F8FC] p-5" aria-label="项目会议纪要审核工作台">
    <header className="rounded-2xl border border-slate-200 bg-white px-6 py-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><div className="flex flex-wrap items-center gap-2"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${isPublished ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>{isPublished ? '已发布' : '待审核草稿'}</span>{editableDraft.meeting_type && <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${TYPE_STYLE[meetingTypeLabel] ?? 'bg-slate-100 text-slate-600'}`}>{meetingTypeLabel}</span>}</div><h1 className="mt-3 text-xl font-semibold text-slate-900">{editableDraft.title || '项目会议纪要'}</h1></div>
        <button type="button" onClick={() => void onDownload()} disabled={busy} className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-sky-300 hover:text-sky-700 disabled:cursor-not-allowed disabled:opacity-50">下载会议纪要</button>
      </div>
      {message && <p className="mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>}
      {error && <p className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
    </header>

    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-label="会议纪要草稿">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-base font-semibold text-slate-900">会议纪要草稿</h2><p className="mt-1 text-sm text-slate-500">核对纪要内容；如需核验，可展开每项的原文依据。</p></div><button type="button" onClick={() => void onSaveDraft(editableDraft)} disabled={!isOwner || busy} className="rounded-lg border border-sky-200 px-4 py-2 text-sm font-semibold text-sky-700 hover:bg-sky-50 disabled:opacity-50">保存修改</button></div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">{fieldLabels.map(([field, label]) => <label key={field} className="block text-sm font-medium text-slate-700">{label}<input value={String(editableDraft[field] ?? '')} onChange={(event) => setEditableDraft((current) => ({ ...current, [field]: event.target.value }))} disabled={!isOwner || busy} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal text-slate-700 disabled:bg-slate-50" /> <EvidenceBlock evidence={meetingInfoEvidence[String(field)]} /></label>)}</div>
      <label className="mt-4 block text-sm font-medium text-slate-700">会议总结<textarea value={editableDraft.summary || ''} onChange={(event) => setEditableDraft((current) => ({ ...current, summary: event.target.value }))} disabled={!isOwner || busy} rows={5} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-normal leading-6 text-slate-700 disabled:bg-slate-50" /><EvidenceBlock evidence={summaryEvidence} /></label>
      <div className="mt-5 grid gap-4 lg:grid-cols-3"><FactSection title="会议决定" items={editableDraft.decisions} /><FactSection title="本周已完成 / 行动项" items={editableDraft.actions} /><FactSection title="风险与待确认" items={editableDraft.risks} /></div>
    </section>

    {openQuestions.length ? <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-label="待确认问题"><h2 className="text-base font-semibold text-slate-900">待确认问题</h2><FactSection title="需要负责人确认后才能入库的事项" items={openQuestions} /></section> : null}

    {scheduleChanges.length ? <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-label="执行安排变更建议">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-base font-semibold text-slate-900">执行安排变更建议</h2><p className="mt-1 text-sm text-slate-500">只会回填负责人勾选且可核验的建议；待确认或受阻建议不可选择。</p></div><span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700">已选 {selectedScheduleChangeIds.size} / {scheduleChanges.length}</span></div>
      <div className="mt-4 space-y-3">{scheduleChanges.length ? scheduleChanges.map((change) => { const blocked = change.validationState === 'blocked' || change.needsConfirmation || change.executionStatus === 'conflict'; return <article key={change.id} className={`rounded-xl border p-4 ${blocked ? 'border-rose-200 bg-rose-50/40' : 'border-slate-200 bg-slate-50/60'}`}><div className="flex items-start gap-3"><input type="checkbox" checked={selectedScheduleChangeIds.has(change.id)} onChange={() => toggleScheduleChange(change)} disabled={!isOwner || busy || blocked} className="mt-1 h-4 w-4 rounded border-slate-300 text-sky-600" aria-label={`选择执行安排变更 ${change.id}`} /><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold text-slate-800">{change.title}</h3>{blocked && <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[11px] font-semibold text-rose-700">{change.executionStatus === 'conflict' ? '数据已变化，不可回填' : change.needsConfirmation ? '待确认，不可回填' : '无法回填'}</span>}</div><p className="mt-1 text-xs text-slate-500">父工作流：{change.workstreamTitle || '未匹配'} · 关键任务：{change.keyTaskTitle || '未匹配'} · 子计划 #{change.parentSubtaskId ?? change.keyTaskId}</p><div className="mt-3 grid gap-3 md:grid-cols-2 text-xs leading-5"><div className="rounded-lg border border-slate-200 bg-white p-3"><div className="font-semibold text-slate-500">当前执行安排</div><p className="mt-1 text-slate-600">{displayValue(change.before)}</p></div><div className="rounded-lg border border-sky-100 bg-sky-50/60 p-3"><div className="font-semibold text-sky-700">会议建议</div><p className="mt-1 text-slate-700">{displayValue(change.proposed)}</p></div></div><EvidenceBlock evidence={change.evidence} />{change.validationErrors?.length ? <p className="mt-2 text-xs text-rose-600">{change.validationErrors.join('；')}</p> : null}{change.conflictReason?.length ? <p className="mt-2 text-xs text-rose-700">冲突原因：{change.conflictReason.join('；')}</p> : null}<LineageTrace change={change} /></div></div></article> }) : <p className="rounded-xl border border-dashed border-slate-200 px-4 py-10 text-center text-sm text-slate-400">本次会议没有执行安排变更建议</p>}</div>
    </section> : null}

    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-label="负责人审核操作"><h2 className="text-base font-semibold text-slate-900">负责人审核</h2>{isPublished ? <><p className="mt-1 text-sm text-slate-500">会议纪要已发布。项目计划不会自动变化；如需同步，请勾选下方建议后单独回填。</p><div className="mt-4 flex flex-wrap gap-3">{hasPendingScheduleChanges ? <button type="button" onClick={handleApplyChanges} disabled={!isOwner || busy || !selectedScheduleChangeIds.size} className="rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-700 disabled:opacity-50">回填已选 {selectedScheduleChangeIds.size} 项变更</button> : null}<button type="button" onClick={() => void onDownload()} disabled={busy} className="rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:opacity-50">再次下载会议纪要</button></div></> : <><p className="mt-1 text-sm text-slate-500">发布仅发布会议纪要，不会修改工作推进表；项目计划变更需在发布后单独回填。</p><div className="mt-4 flex flex-wrap gap-3"><button type="button" onClick={handlePublish} disabled={!isOwner || busy} className="rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50">发布会议纪要</button><button type="button" onClick={() => void onDownload()} disabled={busy} className="rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 disabled:opacity-50">再次下载会议纪要</button></div><form className="mt-5 max-w-2xl" onSubmit={handleReturn}><label htmlFor="project-meeting-return-reason" className="block text-sm font-semibold text-slate-700">退回原因<span className="text-rose-500">*</span></label><textarea id="project-meeting-return-reason" aria-label="退回原因" value={returnReason} onChange={(event) => setReturnReason(event.target.value)} disabled={!isOwner || busy} rows={3} className="mt-2 w-full resize-y rounded-lg border border-slate-200 px-3 py-2.5 text-sm leading-6 text-slate-700 disabled:bg-slate-50" placeholder="请说明需要补充或修改的内容" /><button type="submit" disabled={!isOwner || busy || !returnReason.trim()} className="mt-3 rounded-lg border border-rose-200 bg-white px-4 py-2.5 text-sm font-semibold text-rose-600 disabled:opacity-50">填写原因并退回</button></form></>}</section>
  </section>
}
