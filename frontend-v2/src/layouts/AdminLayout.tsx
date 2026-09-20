import { Outlet, useNavigate } from 'react-router-dom'
import { useProject } from '../context/ProjectContext'

export function AdminLayout() {
  const { currentUser, logout } = useProject()
  const navigate = useNavigate()

  return (
    <div className="min-h-screen" style={{ background: '#F1F5F9' }}>
      <header className="h-16 flex items-center px-6 gap-4 bg-white border-b" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate('/')}>
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#0EA5E9,#0369A1)' }}>
            <svg style={{ width: 18, height: 18, color: 'white' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <div>
            <div className="text-slate-800 text-sm font-bold">博维 AI</div>
            <div className="text-slate-400 text-xs">管理后台</div>
          </div>
        </div>
        <div className="flex-1"></div>
        <span className="text-sm text-slate-600 font-medium">{currentUser?.name ?? ''}</span>
        <button onClick={logout} className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-50 transition-colors">退出</button>
      </header>
      <div className="p-6">
        <Outlet />
      </div>
    </div>
  )
}
