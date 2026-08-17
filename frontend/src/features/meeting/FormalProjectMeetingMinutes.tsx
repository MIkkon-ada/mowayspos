import type { MeetingItem } from '../../types'
import type { ProjectMeetingAgentFact, ProjectMeetingEvidence, ProjectMeetingEvidenceSpan } from '../../api/meetings'

type MeetingDraftFields = Pick<MeetingItem, 'meeting_date' | 'location' | 'host' | 'participants' | 'organizer' | 'copied_to' | 'summary'>

export type FormalProjectMeetingMinutesProps = {
  draft: MeetingDraftFields & {
    agendaItems: ProjectMeetingAgentFact[]
    decisions: ProjectMeetingAgentFact[]
    completedItems: ProjectMeetingAgentFact[]
    nextStageWork: ProjectMeetingAgentFact[]
    risks: ProjectMeetingAgentFact[]
  }
  meetingInfoEvidence: Record<string, ProjectMeetingEvidence>
  summaryEvidence?: ProjectMeetingEvidence
  editable: boolean
  disabled?: boolean
  onChange?: (field: keyof MeetingDraftFields, value: string) => void
}

const editableMetaFields: Array<[keyof MeetingDraftFields, string]> = [
  ['meeting_date', '会议日期'], ['location', '会议地点'], ['host', '主持人'], ['participants', '参会人员'],
]

function evidenceQuotes(evidence: Array<string | ProjectMeetingEvidenceSpan>): string[] {
  return evidence.map((item) => typeof item === 'string' ? item : item.quote).filter(Boolean)
}

function EvidenceBlock({ evidence }: { evidence?: ProjectMeetingEvidence | ProjectMeetingEvidenceSpan[] }) {
  const spans = Array.isArray(evidence) ? evidence : evidence?.evidence ?? []
  const quotes = evidenceQuotes(spans)
  const blocked = !Array.isArray(evidence) && evidence?.validation.state === 'blocked'
  if (!quotes.length) return null
  return <details className="mt-2 text-xs text-slate-500">
    <summary className="cursor-pointer font-medium text-sky-700">查看原文依据{blocked ? '（待核验）' : ''}</summary>
    <ul className="mt-2 space-y-1 rounded-lg border border-dashed border-slate-200 bg-slate-50 p-3 text-slate-600">{quotes.map((quote, index) => <li key={`${quote}-${index}`}>“{quote}”</li>)}</ul>
  </details>
}

function FactList({ items, emptyLabel }: { items: ProjectMeetingAgentFact[]; emptyLabel: string }) {
  if (!items.length) return <p className="mt-3 text-sm text-slate-400">{emptyLabel}</p>
  return <ul className="mt-3 space-y-3 text-sm leading-7 text-slate-700">{items.map((item, index) => <li key={`${item.content}-${index}`} className="border-b border-dashed border-slate-200 pb-3 last:border-0 last:pb-0"><div className="flex gap-2"><span className="text-sky-500">•</span><span>{item.content}</span>{item.needs_confirmation ? <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold leading-5 text-amber-700">待确认</span> : null}</div><EvidenceBlock evidence={item.evidence} /></li>)}</ul>
}

function MetaCell({ label, value, evidence, editable, disabled, onChange }: { label: string; value: string; evidence?: ProjectMeetingEvidence; editable: boolean; disabled: boolean; onChange?: (value: string) => void }) {
  return <div className="border-b border-slate-200 px-4 py-3 last:border-b-0 sm:grid sm:grid-cols-[96px_minmax(0,1fr)] sm:gap-3">
    <dt className="text-sm text-slate-500">{label}</dt>
    <dd className="mt-1 min-w-0 text-sm leading-6 text-slate-800 sm:mt-0">{editable ? <input value={value} onChange={(event) => onChange?.(event.target.value)} disabled={disabled} className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700 disabled:bg-slate-50" /> : (value || '—')}<EvidenceBlock evidence={evidence} /></dd>
  </div>
}

export function FormalProjectMeetingMinutes({ draft, meetingInfoEvidence, summaryEvidence, editable, disabled = false, onChange }: FormalProjectMeetingMinutesProps) {
  return <article className="rounded-2xl border border-slate-200 bg-white px-5 py-7 shadow-sm sm:px-8" aria-label="正式会议纪要">
    <header className="border-b border-slate-200 pb-5 text-center">
      <p className="text-xs tracking-[0.18em] text-slate-400">内部留档 · 项目会议纪要</p>
      <h2 className="mt-2 text-xl font-semibold text-slate-900">会议纪要</h2>
    </header>

    <dl className="mt-6 overflow-hidden rounded-lg border border-slate-200 sm:grid sm:grid-cols-2 sm:divide-x sm:divide-slate-200">
      {editableMetaFields.map(([field, label]) => <MetaCell key={field} label={label} value={draft[field] ?? ''} evidence={meetingInfoEvidence[field]} editable={editable} disabled={disabled} onChange={(value) => onChange?.(field, value)} />)}
    </dl>

    <section className="mt-8">
      <h3 className="text-base font-semibold text-slate-900">一、会议议程</h3>
      <FactList items={draft.agendaItems} emptyLabel="原文未识别出明确会议议程" />
    </section>

    <section className="mt-8 border-t border-dashed border-slate-200 pt-7">
      <h3 className="text-base font-semibold text-slate-900">二、会议小结与决议</h3>
      {editable ? <textarea value={draft.summary ?? ''} onChange={(event) => onChange?.('summary', event.target.value)} disabled={disabled} rows={5} className="mt-3 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm leading-7 text-slate-700 disabled:bg-slate-50" placeholder="填写会议小结" /> : <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">{draft.summary || '暂无会议小结'}</p>}
      <EvidenceBlock evidence={summaryEvidence} />
      <FactList items={draft.decisions} emptyLabel="暂无明确会议决议" />
    </section>

    {draft.completedItems.length ? <section className="mt-8 border-t border-dashed border-slate-200 pt-7">
      <h3 className="text-base font-semibold text-slate-900">本周已确认进展</h3>
      <FactList items={draft.completedItems} emptyLabel="" />
    </section> : null}

    <section className="mt-8 border-t border-dashed border-slate-200 pt-7">
      <h3 className="text-base font-semibold text-slate-900">三、待办事项跟踪</h3>
      {draft.nextStageWork.length ? <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200"><table className="min-w-[820px] w-full text-left text-sm"><thead className="bg-slate-50 text-xs font-medium text-slate-500"><tr>{['编号', '会议安排事项', '负责人', '追踪人', '完成时限', '来源/备注'].map((label) => <th key={label} className="whitespace-nowrap px-4 py-3">{label}</th>)}</tr></thead><tbody>{draft.nextStageWork.map((item, index) => <tr key={`${item.content}-${index}`} className="border-t border-slate-100 align-top text-slate-700"><td className="px-4 py-3">本周-{String(index + 1).padStart(2, '0')}</td><td className="min-w-[300px] px-4 py-3 leading-6">{item.content}<EvidenceBlock evidence={item.evidence} /></td><td className="px-4 py-3">—</td><td className="px-4 py-3">—</td><td className="px-4 py-3">—</td><td className="px-4 py-3">{item.needs_confirmation ? '待负责人确认' : '—'}</td></tr>)}</tbody></table></div> : <p className="mt-3 text-sm text-slate-400">暂无明确待办事项</p>}
    </section>

    {draft.risks.length ? <section className="mt-8 border-t border-dashed border-slate-200 pt-7">
      <h3 className="text-base font-semibold text-slate-900">四、风险与待确认</h3>
      <FactList items={draft.risks} emptyLabel="" />
    </section> : null}

    <footer className="mt-8 grid gap-3 border-t border-slate-200 pt-5 text-sm leading-6 text-slate-600 sm:grid-cols-2"><p>整理人：{editable ? <input value={draft.organizer ?? ''} onChange={(event) => onChange?.('organizer', event.target.value)} disabled={disabled} className="ml-1 rounded border border-slate-200 px-2 py-1 text-sm disabled:bg-slate-50" /> : (draft.organizer || '—')}</p><p>抄送：{editable ? <input value={draft.copied_to ?? ''} onChange={(event) => onChange?.('copied_to', event.target.value)} disabled={disabled} className="ml-1 w-[min(100%,300px)] rounded border border-slate-200 px-2 py-1 text-sm disabled:bg-slate-50" /> : (draft.copied_to || '—')}</p></footer>
  </article>
}
