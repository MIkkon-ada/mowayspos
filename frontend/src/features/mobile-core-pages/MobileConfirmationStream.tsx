import { useState } from 'react'

type Card = Record<string, unknown>
type Props = {
  cards: Card[]
  activeIndex: number
  onSelect: (index: number) => void
  canAct: boolean
  acting: boolean
  onDecide: (action: 'confirm' | 'return' | 'transfer' | 'ceo', note?: string) => void
}

function titleOf(card: Card) { return String(card.title || (card.structure as Record<string, unknown> | undefined)?.subtaskName || (card.structure as Record<string, unknown> | undefined)?.keyTaskName || '待确认事项') }
function statusOf(card: Card) { return String(card.confirmationStatus || card.status || '待确认') }

export function MobileConfirmationStream({ cards, activeIndex, onSelect, canAct, acting, onDecide }: Props) {
  const [returning, setReturning] = useState(false)
  const [note, setNote] = useState('')
  if (!cards.length) return <div className="px-4 py-10 text-center text-sm text-slate-400">暂无待确认事项</div>
  const active = cards[activeIndex] ?? cards[0]
  return <section className="space-y-3 px-4 pb-24" aria-label="待确认事项">
    <div className="flex gap-2 overflow-x-auto pb-1">{cards.map((card, index) => <button type="button" key={String(card.id ?? index)} onClick={() => { setReturning(false); onSelect(index) }} className={`min-w-[150px] rounded-xl border px-3 py-2 text-left ${index === activeIndex ? 'border-blue-300 bg-blue-50' : 'border-slate-200 bg-white'}`}><span className="block truncate text-xs font-bold text-slate-700">{titleOf(card)}</span><span className="mt-1 block text-[10px] text-slate-400">{statusOf(card)}</span></button>)}</div>
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex items-start justify-between gap-3"><h2 className="text-base font-bold text-slate-800">{titleOf(active)}</h2><span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700">{statusOf(active)}</span></div><p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-600">{String(active.summary || active.description || '请查看任务证据后完成确认。')}</p></article>
    {canAct && <div className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm"><button type="button" disabled={acting} onClick={() => onDecide('confirm')} className="h-11 w-full rounded-xl bg-blue-600 text-sm font-bold text-white disabled:opacity-50">确认当前任务卡入库</button><button type="button" disabled={acting} onClick={() => setReturning((value) => !value)} className="mt-2 h-10 w-full rounded-xl border border-orange-200 text-sm font-semibold text-orange-600 disabled:opacity-50">退回当前任务卡</button>{returning && <div className="mt-3"><textarea value={note} onChange={(event) => setNote(event.target.value)} className="min-h-20 w-full rounded-xl border border-slate-200 p-3 text-sm" placeholder="请填写退回原因" /><button type="button" disabled={acting || !note.trim()} onClick={() => onDecide('return', note.trim())} className="mt-2 h-10 w-full rounded-xl bg-orange-500 text-sm font-bold text-white disabled:opacity-50">确认退回</button></div>}</div>}
  </section>
}
