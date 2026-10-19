import { useState } from 'react'
import type { MeetingItem } from '../../types'
import type { ProjectMeetingAgentFact, ProjectMeetingEvidence, ProjectMeetingEvidenceSpan } from '../../api/meetings'
import { DiscussionSections, MinutesItemTable } from './FormalMeetingSections'

type MeetingDraftFields = Pick<MeetingItem, 'meeting_date' | 'location' | 'host' | 'participants' | 'organizer' | 'copied_to' | 'summary'> & { title?: string; meeting_type?: string }

export type FormalProjectMeetingMinutesProps = {
  draft: MeetingDraftFields & {
    agendaItems: ProjectMeetingAgentFact[]
    decisions: ProjectMeetingAgentFact[]
    completedItems: ProjectMeetingAgentFact[]
    nextStageWork: ProjectMeetingAgentFact[]
    risks: ProjectMeetingAgentFact[]
    priorActionTracking?: ProjectMeetingAgentFact[]
  }
  meetingInfoEvidence: Record<string, ProjectMeetingEvidence>
  summaryEvidence?: ProjectMeetingEvidence
  editable: boolean
  disabled?: boolean
  onChange?: (field: keyof MeetingDraftFields, value: string) => void
  onFactsChange?: (field: 'agendaItems' | 'decisions' | 'completedItems' | 'nextStageWork' | 'risks' | 'priorActionTracking', items: ProjectMeetingAgentFact[]) => void
}

const editableMetaFields: Array<[keyof MeetingDraftFields, string]> = [
  ['meeting_date', '会议日期'], ['location', '会议地点'], ['meeting_type', '会议类型'], ['host', '主持人'], ['participants', '参会人员'],
]

function EvidenceBlock({ evidence }: { evidence?: ProjectMeetingEvidence | ProjectMeetingEvidenceSpan[] }) {
  const spans = Array.isArray(evidence) ? evidence : evidence?.evidence ?? []
  if (!spans.length) return null
  return <div aria-label="查看原文依据" className="mt-2 rounded-md border-l-2 border-slate-200 bg-white/80 px-3 py-2 text-xs text-slate-500">
    <div className="mb-1 font-semibold text-slate-600">查看原文依据</div>
    <ul className="space-y-1">{spans.map((item, index) => {
      const quote = typeof item === 'string' ? item : item.quote
      const locator = typeof item === 'string' ? '' : item.locator
      return <li key={`${locator || 'source'}-${index}`} className="whitespace-pre-wrap">{locator ? <span className="mr-1 font-medium text-slate-600">{locator}</span> : null}“{quote}”</li>
    })}</ul>
  </div>
}
function editedFact(item: ProjectMeetingAgentFact, patch: Partial<ProjectMeetingAgentFact>): ProjectMeetingAgentFact {
  return { ...item, ...patch, evidence: [], human_edited: true, needs_confirmation: false, validation: { state: 'ready', errors: [] } }
}

function FactList({ items, emptyLabel, editable, disabled, structured = false, numbered = false, onChange }: { items: ProjectMeetingAgentFact[]; emptyLabel: string; editable: boolean; disabled: boolean; structured?: boolean; numbered?: boolean; onChange?: (items: ProjectMeetingAgentFact[]) => void }) {
  const [newItem, setNewItem] = useState('')
  const updateItem = (index: number, patch: Partial<ProjectMeetingAgentFact>) => onChange?.(items.map((item, itemIndex) => itemIndex === index ? editedFact(item, patch) : item))
  return <div className="mt-3">
    {items.length ? <ul className="space-y-3 text-sm leading-7 text-slate-700">{items.map((item, index) => <li key={index} className={`border-b border-dashed border-[#dfe7ef] pb-3 last:border-0 last:pb-0 ${numbered && !editable ? 'flex gap-3' : ''}`}>
      {numbered && !editable ? <span className="pt-0.5 text-xs font-bold tracking-wide text-[#168ea9]">{String(index + 1).padStart(2, '0')}</span> : null}
      {editable ? <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50/70 p-3">
        <div className="flex items-start gap-2"><textarea aria-label={`第${index + 1}项内容`} rows={2} value={item.content} disabled={disabled} onChange={(event) => updateItem(index, { content: event.target.value })} className="min-h-16 min-w-0 flex-1 resize-y rounded-md border border-slate-200 bg-white px-3 py-2 text-sm leading-6 outline-none focus:border-sky-400 disabled:bg-slate-100" /><button type="button" disabled={disabled} onClick={() => onChange?.(items.filter((_, itemIndex) => itemIndex !== index))} className="shrink-0 rounded-md px-2 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50 disabled:opacity-50">移除</button></div>
        {structured && <div className="grid gap-2 sm:grid-cols-3">{([['owner', '负责人'], ['tracker', '追踪人'], ['due_date', '完成时限']] as const).map(([field, label]) => <label key={field} className="text-xs text-slate-500">{label}<input value={item[field] || ''} disabled={disabled} onChange={(event) => updateItem(index, { [field]: event.target.value })} className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-sm text-slate-700 outline-none focus:border-sky-400 disabled:bg-slate-100" /></label>)}</div>}
        {item.human_edited ? <p className="text-xs text-amber-700">人工修改；原有 AI 引用已移除</p> : <EvidenceBlock evidence={item.evidence} />}
      </div> : <><div className="flex gap-2">{numbered ? null : <span className="text-sky-500">•</span>}<span className="min-w-0 flex-1 whitespace-pre-wrap">{item.content}</span>{item.needs_confirmation && <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold leading-5 text-amber-700">建议核对原文</span>}{item.human_edited && <span className="shrink-0 rounded-full bg-sky-50 px-2 py-0.5 text-[11px] text-sky-700">人工修改</span>}</div><EvidenceBlock evidence={item.evidence} /></>}
    </li>)}</ul> : <p className="text-sm text-slate-400">{emptyLabel}</p>}
    {editable && <div className="mt-3 flex gap-2"><input aria-label="补充会议事项" value={newItem} disabled={disabled} onChange={(event) => setNewItem(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && newItem.trim()) { onChange?.([...items, { content: newItem.trim(), evidence: [], validation: { state: 'ready', errors: [] }, human_edited: true }]); setNewItem('') } }} placeholder="补充一项会议事项" className="min-w-0 flex-1 rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-400 disabled:bg-slate-100" /><button type="button" disabled={disabled || !newItem.trim()} onClick={() => { onChange?.([...items, { content: newItem.trim(), evidence: [], validation: { state: 'ready', errors: [] }, human_edited: true }]); setNewItem('') }} className="rounded-md border border-sky-200 px-3 py-2 text-sm font-medium text-sky-700 hover:bg-sky-50 disabled:opacity-50">添加</button></div>}
  </div>
}

function MetaCell({ label, value, evidence, editable, disabled, className = '', onChange }: { label: string; value: string; evidence?: ProjectMeetingEvidence; editable: boolean; disabled: boolean; className?: string; onChange?: (value: string) => void }) {
  const isParticipants = label === '参会人员'
  const allowsMultipleLines = isParticipants || label === '会议类型' || label === '会议地点'
  return <div className={`border-b border-[#dfe7ef] px-3 py-2.5 sm:grid sm:grid-cols-[84px_minmax(0,1fr)] sm:gap-2.5 lg:px-3.5 ${className}`}>
    <dt className="text-[13px] text-slate-500">{label}</dt>
    <dd className="mt-1 min-w-0 text-[13px] leading-5 text-slate-800 sm:mt-0">{editable ? allowsMultipleLines ? <textarea aria-label={label} rows={Math.min(5, Math.max(isParticipants ? 2 : 1, Math.ceil(value.length / (isParticipants ? 48 : 24))))} value={value} onChange={(event) => onChange?.(event.target.value)} disabled={disabled} className="min-h-[38px] w-full resize-y rounded-md border border-slate-200 px-2.5 py-1.5 text-[13px] leading-5 text-slate-700 disabled:bg-slate-50" /> : <input aria-label={label} value={value} onChange={(event) => onChange?.(event.target.value)} disabled={disabled} className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-[13px] text-slate-700 disabled:bg-slate-50" /> : <span className="block break-words whitespace-pre-wrap">{value || '—'}</span>}<EvidenceBlock evidence={evidence} /></dd>
  </div>
}

export function FormalProjectMeetingMinutes({ draft, meetingInfoEvidence, summaryEvidence, editable, disabled = false, onChange, onFactsChange }: FormalProjectMeetingMinutesProps) {
  const formalTitle = draft.title?.includes('会议纪要') ? draft.title : `${draft.title || '项目'} 会议纪要`
  return <article className="overflow-hidden rounded-[18px] border border-[#e2e7e7] bg-[#fffefa] px-4 py-7 shadow-[0_18px_50px_rgba(25,52,72,0.10)] sm:px-7 lg:px-9 2xl:px-12" aria-label="正式会议纪要">
    <header className="border-b border-[#dfe7ef] pb-6 text-center">
      <div className="text-[10px] font-bold tracking-[0.18em] text-[#168ea9]">内部留档 · 项目会议纪要</div>
      {editable ? <input aria-label="会议纪要标题" value={draft.title ?? ''} disabled={disabled} onChange={(event) => onChange?.('title', event.target.value)} style={{ fontFamily: '"Songti SC", "SimSun", "STSong", serif' }} className="mx-auto mt-3 block w-full max-w-3xl rounded-md border border-slate-200 bg-white px-3 py-2 text-center text-2xl font-semibold leading-tight text-[#202f79] disabled:bg-slate-50" /> : <h2 style={{ fontFamily: '"Songti SC", "SimSun", "STSong", serif' }} className="mt-3 text-3xl font-semibold leading-tight text-[#202f79] lg:text-4xl">{formalTitle}</h2>}
      <p style={{ fontFamily: '"Songti SC", "SimSun", "STSong", serif' }} className="mt-2 text-xs text-slate-500">{draft.meeting_date || '原文未注明日期'}　|　{draft.meeting_type || '项目会议'}</p>
    </header>

    <dl className="mt-5 overflow-hidden rounded-xl border border-[#dfe7ef] bg-white sm:grid sm:grid-cols-2">
      {editableMetaFields.map(([field, label], index) => <MetaCell key={field} label={label} value={draft[field] ?? ''} evidence={meetingInfoEvidence[field]} editable={editable} disabled={disabled} className={field === 'participants' ? 'border-b-0 sm:col-span-2' : index % 2 === 0 ? 'sm:border-r sm:border-[#dfe7ef]' : ''} onChange={(value) => onChange?.(field, value)} />)}
    </dl>

    <section className="mt-7">
      <h3 className="flex items-center gap-2.5 text-lg font-semibold text-[#202f79]"><span className="h-5 w-1 rounded-full bg-[#168ea9]" />一、会议议程</h3>
      <FactList items={draft.agendaItems} emptyLabel="原文未识别出明确会议议程" editable={editable} disabled={disabled} numbered onChange={(items) => onFactsChange?.('agendaItems', items)} />
    </section>

    <section className="mt-7 border-t border-dashed border-[#dfe7ef] pt-5">
      <h3 className="flex items-center gap-2.5 text-lg font-semibold text-[#202f79]"><span className="h-5 w-1 rounded-full bg-[#168ea9]" />二、会议讨论与结论</h3>
      {editable ? <textarea value={draft.summary ?? ''} onChange={(event) => onChange?.('summary', event.target.value)} disabled={disabled} rows={3} className="mt-3 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm leading-7 text-slate-700 disabled:bg-slate-50" placeholder="会议概况（可选）" /> : draft.summary ? <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">{draft.summary}</p> : null}
      <EvidenceBlock evidence={summaryEvidence} />
      <DiscussionSections items={draft.decisions} editable={editable} disabled={disabled} onChange={(items) => onFactsChange?.('decisions', items)} />
      {draft.completedItems.length ? <section className="mt-5 border-t border-dashed border-[#dfe7ef] pt-4">
        <h4 className="font-semibold text-slate-800">本周已确认进展</h4>
        <FactList items={draft.completedItems} emptyLabel="" editable={editable} disabled={disabled} onChange={(items) => onFactsChange?.('completedItems', items)} />
      </section> : null}
    </section>

    <section className="mt-7 border-t border-dashed border-[#dfe7ef] pt-5">
      <h3 className="flex items-center gap-2.5 text-lg font-semibold text-[#202f79]"><span className="h-5 w-1 rounded-full bg-[#168ea9]" />三、会议行动项</h3>
      <h4 className="mt-4 font-semibold text-slate-800">（一）本周待办事项</h4>
      <MinutesItemTable items={draft.nextStageWork} editable={editable} disabled={disabled} onChange={(items) => onFactsChange?.('nextStageWork', items)} />
      {Boolean(draft.priorActionTracking?.length) && <section className="mt-7"><h4 className="font-semibold text-slate-800">（二）上周待办追踪</h4><MinutesItemTable items={draft.priorActionTracking ?? []} editable={editable} disabled={disabled} tracking onChange={(items) => onFactsChange?.('priorActionTracking', items)} /></section>}
    </section>

    {draft.risks.length || editable ? <section className="mt-5 border-t border-dashed border-[#dfe7ef] pt-4">
      <h4 className="font-semibold text-slate-800">风险与待确认</h4>
      <FactList items={draft.risks} emptyLabel="" editable={editable} disabled={disabled} onChange={(items) => onFactsChange?.('risks', items)} />
    </section> : null}

    <footer className="mt-7 grid gap-3 border-t border-[#dfe7ef] pt-4 text-sm leading-6 text-slate-600 sm:grid-cols-2"><p>整理人：{editable ? <input value={draft.organizer ?? ''} onChange={(event) => onChange?.('organizer', event.target.value)} disabled={disabled} className="ml-1 rounded border border-slate-200 px-2 py-1 text-sm disabled:bg-slate-50" /> : (draft.organizer || '—')}</p><p>抄送：{editable ? <input value={draft.copied_to ?? ''} onChange={(event) => onChange?.('copied_to', event.target.value)} disabled={disabled} className="ml-1 w-[min(100%,300px)] rounded border border-slate-200 px-2 py-1 text-sm disabled:bg-slate-50" /> : (draft.copied_to || '—')}</p></footer>
  </article>
}
