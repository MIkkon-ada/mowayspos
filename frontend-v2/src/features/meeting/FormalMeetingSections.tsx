import type { ProjectMeetingAgentFact } from '../../api/meetings'

type SectionProps = {
  items: ProjectMeetingAgentFact[]
  editable: boolean
  disabled: boolean
  onChange?: (items: ProjectMeetingAgentFact[]) => void
}

function edited(item: ProjectMeetingAgentFact, patch: Partial<ProjectMeetingAgentFact>): ProjectMeetingAgentFact {
  return { ...item, ...patch, evidence: [], human_edited: true, needs_confirmation: false, validation: { state: 'ready', errors: [] } }
}

function Evidence({ item }: { item: ProjectMeetingAgentFact }) {
  if (item.human_edited) return <span className="text-xs text-amber-700">人工修改；原有 AI 引用已移除</span>
  if (!item.evidence?.length) return null
  return <span className="sr-only">{item.evidence.map((span) => `“${span.quote}”`).join('；')}</span>
}

export function DiscussionSections({ items, editable, disabled, onChange }: SectionProps) {
  const groups: Array<{ title: string; indexes: number[] }> = []
  items.forEach((item, index) => {
    const sourceTitle = item.topic?.trim()
    const title = sourceTitle && sourceTitle !== '会议讨论与结论' ? sourceTitle : '讨论要点'
    const group = groups[groups.length - 1]
    if (group?.title === title) group.indexes.push(index)
    else groups.push({ title, indexes: [index] })
  })
  const replace = (indexes: number[], replacement: ProjectMeetingAgentFact[]) => {
    const next = items.filter((_, index) => !indexes.includes(index))
    next.splice(indexes[0], 0, ...replacement)
    onChange?.(next)
  }
  return <div className="mt-4 space-y-4">
    {groups.length ? groups.map((group, groupIndex) => <section key={`${group.title}-${groupIndex}`} className="rounded-xl border border-[#dfe7ef] bg-[#f7faf9] p-4 sm:p-5">
      {editable ? <input aria-label={`第${groupIndex + 1}个议题标题`} value={group.title} disabled={disabled} onChange={(event) => replace(group.indexes, group.indexes.map((index) => edited(items[index], { topic: event.target.value })))} className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 font-semibold text-slate-800 disabled:bg-slate-50" /> : <h4 className="break-words font-semibold leading-6 text-[#202f79]">（{['一', '二', '三', '四', '五', '六', '七', '八', '九', '十'][groupIndex] ?? groupIndex + 1}）{group.title}</h4>}
      <ul className="mt-3 space-y-2.5">{group.indexes.map((itemIndex, pointIndex) => {
        const item = items[itemIndex]
        return <li key={itemIndex} className={editable ? 'border-t border-[#dfe7ef] pt-3 first:border-0 first:pt-0' : 'flex items-start gap-2 text-sm leading-7 text-slate-700'}>
          {editable ? <div className="flex gap-2"><textarea aria-label={`第${groupIndex + 1}个议题第${pointIndex + 1}条内容`} value={item.content} disabled={disabled} rows={2} onChange={(event) => onChange?.(items.map((row, index) => index === itemIndex ? edited(row, { content: event.target.value }) : row))} className="min-w-0 flex-1 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm disabled:bg-slate-100" /><button type="button" disabled={disabled} onClick={() => onChange?.(items.filter((_, index) => index !== itemIndex))} className="self-start px-2 py-1 text-xs text-rose-600 disabled:opacity-50">移除</button></div> : <><span className="shrink-0 font-bold text-[#168ea9]">·</span><span className="min-w-0 flex-1 whitespace-pre-wrap break-words">{item.content}</span></>}
          <Evidence item={item} />
        </li>
      })}</ul>
      {editable && <button type="button" disabled={disabled} onClick={() => replace(group.indexes, [...group.indexes.map((index) => items[index]), { content: '', topic: group.title, evidence: [], validation: { state: 'ready', errors: [] }, human_edited: true }])} className="mt-3 text-sm font-medium text-sky-700 disabled:opacity-50">添加讨论要点</button>}
    </section>) : <p className="text-sm text-slate-400">暂无明确会议讨论与结论</p>}
    {editable && <button type="button" disabled={disabled} onClick={() => onChange?.([...items, { content: '', topic: '新议题', evidence: [], validation: { state: 'ready', errors: [] }, human_edited: true }])} className="rounded-md border border-sky-200 px-3 py-2 text-sm font-medium text-sky-700 disabled:opacity-50">添加议题</button>}
  </div>
}

type Field = 'content' | 'owner' | 'tracker' | 'due_date' | 'source_note' | 'status' | 'progress_note'

export function MinutesItemTable({ items, editable, disabled, onChange, tracking = false }: SectionProps & { tracking?: boolean }) {
  const columns: Array<[Field, string]> = tracking
    ? [['content', '上周事项'], ['owner', '负责人'], ['status', '状态'], ['progress_note', '本周进展/说明']]
    : [['content', '会议安排事项'], ['owner', '负责人'], ['tracker', '追踪人'], ['due_date', '完成时限'], ['source_note', '来源/备注']]
  const update = (index: number, patch: Partial<ProjectMeetingAgentFact>) => onChange?.(items.map((item, itemIndex) => itemIndex === index ? edited(item, patch) : item))
  const widths = tracking
    ? editable ? ['10%', '32%', '12%', '12%', '29%', '5%'] : ['10%', '35%', '13%', '13%', '29%']
    : editable ? ['9%', '31%', '10%', '10%', '13%', '22%', '5%'] : ['9%', '33%', '11%', '11%', '14%', '22%']
  const fieldValue = (item: ProjectMeetingAgentFact, field: Field) => item[field] || ''
  return <div className="mt-4 space-y-3">
    <div className="meeting-minutes-table-wrap overflow-hidden rounded-xl border border-[#dfe7ef]"><table className="meeting-minutes-table w-full table-fixed border-collapse text-left text-[13px]">
      <colgroup>{widths.map((width, index) => <col key={index} style={{ width }} />)}</colgroup>
      <thead className="bg-[#202f79] text-xs font-semibold text-white"><tr><th scope="col" className="px-2.5 py-3">编号</th>{columns.map(([, label]) => <th scope="col" key={label} className="px-2.5 py-3">{label}</th>)}{editable && <th scope="col" className="px-2.5 py-3">操作</th>}</tr></thead>
      <tbody>{items.length ? items.map((item, index) => <tr key={index} className="border-t border-[#dfe7ef] align-top text-slate-700 odd:bg-white even:bg-[#fbfcfc]">
        <td data-label="编号" className="break-all px-2.5 py-3 font-semibold text-[#168ea9]">{editable ? <input aria-label={`第${index + 1}项编号`} value={item.code || ''} disabled={disabled} onChange={(event) => update(index, { code: event.target.value })} placeholder={`${tracking ? '追踪' : '本周'}-${String(index + 1).padStart(2, '0')}`} className="min-w-0 w-full rounded border border-slate-200 px-2 py-2 text-slate-700 disabled:bg-slate-50" /> : (item.code || `${tracking ? '追踪' : '本周'}-${String(index + 1).padStart(2, '0')}`)}</td>
        {columns.map(([field, label]) => <td key={field} data-label={label} data-wide={field === 'content' || field === 'progress_note' || field === 'source_note' ? 'true' : undefined} className="min-w-0 break-words px-2.5 py-2.5 leading-6 [overflow-wrap:anywhere]">{editable ? <textarea aria-label={`第${index + 1}项${label}`} value={fieldValue(item, field)} disabled={disabled} rows={Math.max(2, Math.ceil(fieldValue(item, field).length / (field === 'content' ? 24 : field === 'progress_note' || field === 'source_note' ? 16 : 8)))} onChange={(event) => update(index, { [field]: event.target.value })} placeholder="原文未注明" className="min-h-11 min-w-0 w-full resize-y rounded border border-slate-200 bg-white px-2 py-1.5 text-[13px] leading-5 disabled:bg-slate-50" /> : <span className={fieldValue(item, field) ? 'whitespace-pre-wrap' : 'text-amber-700'}>{fieldValue(item, field) || '原文未注明'}</span>}{field === 'content' && <Evidence item={item} />}</td>)}
        {editable && <td data-label="操作" className="px-2.5 py-3"><button type="button" disabled={disabled} onClick={() => onChange?.(items.filter((_, rowIndex) => rowIndex !== index))} className="text-xs text-rose-600 disabled:opacity-50">移除</button></td>}
      </tr>) : <tr><td colSpan={columns.length + (editable ? 2 : 1)} className="px-3 py-5 text-center text-slate-400">暂无明确{tracking ? '上期追踪' : '行动项'}</td></tr>}</tbody>
    </table></div>
    {editable && <button type="button" disabled={disabled} onClick={() => onChange?.([...items, { content: '', evidence: [], validation: { state: 'ready', errors: [] }, human_edited: true }])} className="rounded-md border border-sky-200 px-3 py-2 text-sm font-medium text-sky-700 disabled:opacity-50">添加{tracking ? '追踪事项' : '行动项'}</button>}
  </div>
}
