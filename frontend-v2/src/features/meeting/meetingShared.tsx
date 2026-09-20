import type { ReactNode } from 'react'
import { renderVal } from './meetingUtils'

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <div className="w-0.5 h-3.5 rounded-full" style={{ background: '#0369A1' }} />
      <span className="text-xs font-bold text-slate-700">{children}</span>
    </div>
  )
}

export function Field({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div>
      <label className="block text-xs font-semibold text-slate-500 mb-1">{label}</label>
      <input
        type="text"
        className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-300"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  )
}

export function JsonListSection({ label, value, onChange, dotColor }: { label: string; value: string; onChange: (v: string) => void; dotColor: string }) {
  let items: unknown[] = []
  try {
    items = JSON.parse(value)
  } catch {
    items = []
  }

  return (
    <div>
      <SectionTitle>{label}</SectionTitle>
      <div className="mt-2">
        {Array.isArray(items) && items.length > 0 ? (
          <div className="border border-slate-200 rounded-lg overflow-hidden mb-1">
            {items.map((item, i) => (
              <div key={i} className="flex items-start gap-2 px-3 py-2 border-b last:border-0 text-xs text-slate-600" style={{ borderColor: '#F1F5F9' }}>
                <span className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ background: dotColor }} />
                {renderVal(item)}
              </div>
            ))}
          </div>
        ) : (
          <div className="border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-400 mb-1">暂无 AI 结果</div>
        )}
        <textarea
          className="w-full border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-200 resize-none font-mono"
          rows={2}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder="JSON 数据"
        />
      </div>
    </div>
  )
}

export function ErrorBar({ msg }: { msg: string }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm text-red-600" style={{ background: '#FEF2F2' }}>
      <svg style={{ width: 14, height: 14, flexShrink: 0 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      {msg}
    </div>
  )
}

export function MeetingSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="py-4 border-b border-slate-50">
      <div className="flex items-center gap-2 mb-2.5">
        <div className="w-0.5 h-3.5 rounded-full" style={{ background: '#0369A1' }} />
        <h3 className="text-xs font-bold text-slate-800">{title}</h3>
      </div>
      {children}
    </div>
  )
}

export function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2 mb-1.5 text-xs">
      <span className="w-16 flex-shrink-0 text-slate-500 font-semibold">{label}</span>
      <span className="text-slate-800">{value}</span>
    </div>
  )
}

export function renderJsonList(json: string, dotColor: string) {
  try {
    const items = JSON.parse(json)
    if (!Array.isArray(items) || !items.length) return null
    return (
      <>
        {items.map((t: unknown, i: number) => (
          <div key={i} className="flex items-start gap-2 text-xs text-slate-600 mb-1">
            <span className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ background: dotColor }} />
            {renderVal(t)}
          </div>
        ))}
      </>
    )
  } catch {
    return null
  }
}
