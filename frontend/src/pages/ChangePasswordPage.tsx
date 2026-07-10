import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { changeMyPassword } from '../api/accounts'
import { useProject } from '../context/ProjectContext'

type Props = {
  forced?: boolean  // true = 首次登录强制改密模式
}

export function ChangePasswordPage({ forced = false }: Props) {
  const navigate = useNavigate()
  const { currentUser, refreshUser } = useProject()

  const [oldPwd, setOldPwd]   = useState('')
  const [newPwd, setNewPwd]   = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')
  const [done, setDone]       = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (newPwd !== confirm) { setError('两次密码不一致'); return }
    if (newPwd.length < 6)  { setError('新密码至少 6 位'); return }
    setLoading(true)
    try {
      await changeMyPassword(oldPwd, newPwd)
      setDone(true)
      await refreshUser?.()
      setTimeout(() => navigate(forced ? '/' : -1 as any), 1200)
    } catch (err: any) {
      setError(err?.message || '修改失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: '#F1F5F9' }}>
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div
            className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4"
            style={{ background: 'linear-gradient(135deg,#0EA5E9,#0369A1)' }}
          >
            <svg style={{ width: 26, height: 26, color: 'white' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-slate-800 tracking-tight">
            {forced ? '请先修改密码' : '修改密码'}
          </h1>
          {forced && (
            <p className="text-slate-500 text-sm mt-1 text-center">
              管理员已为你设置初始密码，<br />请立即修改后继续使用
            </p>
          )}
          {!forced && currentUser && (
            <p className="text-slate-500 text-sm mt-1">{currentUser.name}</p>
          )}
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-2xl p-8 space-y-5"
          style={{ border: '1px solid #E9EFF6', boxShadow: '0 4px 20px rgba(15,23,42,0.08)' }}
        >
          {done ? (
            <div className="flex flex-col items-center gap-3 py-4">
              <div className="w-12 h-12 rounded-full flex items-center justify-center" style={{ background: '#DCFCE7' }}>
                <svg style={{ width: 24, height: 24, color: '#16A34A' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <p className="text-slate-700 font-semibold">密码修改成功</p>
              <p className="text-slate-400 text-sm">即将跳转…</p>
            </div>
          ) : (
            <>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">原密码</label>
                <input
                  type="password"
                  value={oldPwd}
                  onChange={(e) => setOldPwd(e.target.value)}
                  placeholder="请输入原密码"
                  autoComplete="current-password"
                  className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:border-blue-400 transition"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">新密码</label>
                <input
                  type="password"
                  value={newPwd}
                  onChange={(e) => setNewPwd(e.target.value)}
                  placeholder="至少 6 位"
                  autoComplete="new-password"
                  className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:border-blue-400 transition"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">确认新密码</label>
                <input
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="再次输入新密码"
                  autoComplete="new-password"
                  className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:border-blue-400 transition"
                  required
                />
              </div>

              {error && (
                <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm" style={{ background: '#FEF2F2', border: '1px solid #FECACA', color: '#DC2626' }}>
                  <svg style={{ width: 14, height: 14, flexShrink: 0 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading || !oldPwd || !newPwd || !confirm}
                className="w-full py-3 rounded-xl text-white text-sm font-bold transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)', boxShadow: '0 2px 8px rgba(3,105,161,0.3)' }}
              >
                {loading ? '保存中…' : '确认修改'}
              </button>

              {!forced && (
                <button
                  type="button"
                  onClick={() => navigate(-1 as any)}
                  className="w-full py-2.5 rounded-xl text-slate-500 text-sm font-medium hover:bg-slate-50 transition"
                >
                  取消
                </button>
              )}
            </>
          )}
        </form>
      </div>
    </div>
  )
}
