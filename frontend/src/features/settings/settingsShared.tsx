import type { ReactNode } from 'react'

export function Card({ children }: { children: ReactNode }) {
  return (
    <div className="bg-white rounded-2xl border p-6" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
      {children}
    </div>
  )
}

export function SectionTitle({ children, inline }: { children: ReactNode; inline?: boolean }) {
  return (
    <h2 className="text-sm font-bold text-slate-800 flex items-center gap-2" style={inline ? {} : { marginBottom: 20 }}>
      <span className="w-0.5 h-3.5 rounded-full flex-shrink-0" style={{ background: '#0369A1' }} />
      {children}
    </h2>
  )
}

export function Field({ label, desc, children, last }: { label: string; desc: string; children: ReactNode; last?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-6" style={{ padding: '16px 0', borderBottom: last ? 'none' : '1px solid #F1F5F9' }}>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-800">{label}</p>
        <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">{desc}</p>
      </div>
      <div className="flex-shrink-0">{children}</div>
    </div>
  )
}

export function Toggle({ checked, onChange, disabled }: { checked: boolean; onChange?: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange?.(!checked)}
      className="relative inline-flex items-center flex-shrink-0 rounded-full transition-colors"
      style={{ width: 42, height: 24, background: checked ? '#0369A1' : '#E2E8F0', opacity: disabled ? 0.6 : 1, cursor: disabled ? 'not-allowed' : 'pointer' }}
    >
      <span
        className="inline-block rounded-full bg-white transition-transform"
        style={{ width: 18, height: 18, boxShadow: '0 1px 3px rgba(0,0,0,0.2)', transform: checked ? 'translateX(21px)' : 'translateX(3px)' }}
      />
    </button>
  )
}
