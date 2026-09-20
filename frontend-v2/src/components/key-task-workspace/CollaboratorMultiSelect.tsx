import { useEffect, useRef, useState } from 'react'
import type { ProjectMember } from '../../types'

type Props = {
  members: ProjectMember[]
  excludedPersonId: number | null
  selectedIds: number[]
  disabled: boolean
  onChange: (ids: number[]) => void
}

const inputClass = 'w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-blue-500 disabled:cursor-not-allowed disabled:bg-slate-50'

export function CollaboratorMultiSelect({ members, excludedPersonId, selectedIds, disabled, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const candidates = members.filter((member, index, all) =>
    member.person_id !== excludedPersonId
    && all.findIndex((candidate) => candidate.person_id === member.person_id) === index,
  )
  const selectedNames = candidates.filter((member) => selectedIds.includes(member.person_id)).map((member) => member.person_name_snapshot)
  const displayValue = selectedNames.length === 0
    ? '请选择协助人'
    : selectedNames.length <= 2
      ? selectedNames.join('、')
      : `${selectedNames.slice(0, 2).join('、')}、+${selectedNames.length - 2}`

  useEffect(() => {
    if (!open) return
    const closeOnOutsideClick = (event: MouseEvent) => {
      const target = event.target as Node | null
      if (target && !rootRef.current?.contains(target)) setOpen(false)
    }
    document.addEventListener('mousedown', closeOnOutsideClick)
    return () => document.removeEventListener('mousedown', closeOnOutsideClick)
  }, [open])

  function toggleMember(personId: number) {
    onChange(selectedIds.includes(personId)
      ? selectedIds.filter((id) => id !== personId)
      : [...selectedIds, personId])
  }

  return <div ref={rootRef} className="relative text-xs font-medium text-slate-600">
    <span className="mb-1 block">协助人</span>
    <button type="button" disabled={disabled} aria-label="协助人" aria-expanded={open} onClick={() => setOpen((value) => !value)} title={selectedNames.join('、')} className={`${inputClass} flex h-[38px] items-center justify-between gap-2 text-left`}>
      <span className={selectedNames.length ? 'truncate text-slate-700' : 'truncate text-slate-400'}>{displayValue}</span>
      <svg className={`size-4 shrink-0 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" aria-hidden="true"><path strokeLinecap="round" strokeLinejoin="round" d="m6 9 6 6 6-6" /></svg>
    </button>
    {open && <div className="absolute left-0 right-0 top-full z-30 mt-1 overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg" role="listbox" aria-label="协助人候选">
      <div className="max-h-56 overflow-y-auto">{candidates.length ? candidates.map((member) => {
        const checked = selectedIds.includes(member.person_id)
        return <label key={member.person_id} className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
          <input type="checkbox" checked={checked} disabled={disabled} onChange={() => toggleMember(member.person_id)} className="size-4 rounded border-slate-300 accent-blue-600" />
          <span className="truncate">{member.person_name_snapshot}</span>
        </label>
      }) : <p className="px-3 py-3 text-sm text-slate-400">暂无可选协助人</p>}</div>
    </div>}
  </div>
}
