import { useNavigate } from 'react-router-dom'
import { useProject } from '../context/ProjectContext'

export function NoAccessPage() {
  const navigate = useNavigate()
  const { authDefaultRoute, logout } = useProject()

  const handleBack = () => {
    navigate(authDefaultRoute || '/home', { replace: true })
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6" style={{ background: '#F1F5F9' }}>
      <div className="w-full max-w-md rounded-3xl bg-white border border-slate-200 p-8 text-center shadow-sm">
        <div
          className="mx-auto mb-4 w-14 h-14 rounded-2xl flex items-center justify-center"
          style={{ background: '#EFF6FF', color: '#2563EB' }}
        >
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
          </svg>
        </div>
        <h1 className="text-xl font-bold text-slate-800">当前账号无权访问该功能</h1>
        <p className="mt-3 text-sm leading-6 text-slate-500">
          如需访问，请联系项目负责人或系统管理员。
        </p>
        <div className="mt-6 flex flex-col gap-3">
          <button
            type="button"
            onClick={handleBack}
            className="w-full rounded-xl px-4 py-3 text-sm font-semibold text-white"
            style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}
          >
            返回默认首页
          </button>
          <button
            type="button"
            onClick={logout}
            className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-600 hover:bg-slate-50"
          >
            退出登录
          </button>
        </div>
      </div>
    </div>
  )
}
