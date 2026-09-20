export function ClientPortalPlaceholderPage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-6" style={{ background: '#F8FAFC' }}>
      <div className="w-full max-w-lg rounded-3xl bg-white border border-slate-200 p-8 text-center shadow-sm">
        <div
          className="mx-auto mb-4 w-14 h-14 rounded-2xl flex items-center justify-center"
          style={{ background: '#EEF2FF', color: '#4F46E5' }}
        >
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h10M4 18h16" />
          </svg>
        </div>
        <h1 className="text-xl font-bold text-slate-800">客户侧入口尚未开放</h1>
        <p className="mt-3 text-sm leading-6 text-slate-500">
          当前阶段仅保留客户视角的守卫结构，后续会接入客户项目总览和成果使用能力。
        </p>
      </div>
    </div>
  )
}
