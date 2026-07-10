import { useState, type ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useProject } from '../context/ProjectContext'
import { getPostLoginDestination, getProjectsLandingDestination } from '../domain/authFlow'
import { SYSTEM_NAME_CN } from '../domain/displayNames'

export function CenterMessage({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-2">
      <div className="text-slate-700 font-semibold">{title}</div>
      {subtitle ? <div className="text-slate-400 text-sm">{subtitle}</div> : null}
    </div>
  )
}

function LoginPanel() {
  const { login, loading, error } = useProject()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    try {
      await login(username.trim(), password)
    } catch {
      // 错误已存入 context.error
    }
  }

  const handleLogoError = (e: React.SyntheticEvent<HTMLImageElement>) => {
    e.currentTarget.style.display = 'none'
  }

  return (
    <div className="login-page">
      <div className="login-bg" aria-hidden="true" />

      <header className="login-header">
        <div className="login-logo">
          <img
            src="/logo.png"
            alt="MOWAYS 博维咨询"
            className="login-logo-img"
            onError={handleLogoError}
          />
          <div className="login-logo-fallback">
            <span className="login-logo-text">MOWAYS</span>
            <span className="login-logo-sub">博维咨询</span>
          </div>
        </div>
      </header>

      <main className="login-body">
        <section className="login-brand-panel" aria-label="系统介绍">
          <h1 className="login-title-en">Moways-SOP</h1>
          <h2 className="login-title-cn">{SYSTEM_NAME_CN}</h2>
          <div className="login-title-divider" />
          <p className="login-subtitle">内部协同平台</p>
        </section>

        <section className="login-form-panel" aria-label="登录表单">
          <form onSubmit={handleSubmit} className="login-card">
            <h2 className="login-welcome">welcome</h2>
            <p className="login-card-desc">请输入您的系统账号与密码以访问管理平台。</p>

            <div className="login-field">
              <label className="login-field-label" htmlFor="login-username">
                系统账号
              </label>
              <input
                id="login-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                placeholder="请输入系统账号"
                className="login-input"
              />
            </div>

            <div className="login-field login-field-password">
              <div className="login-field-row">
                <label className="login-field-label" htmlFor="login-password">
                  密码
                </label>
                <a href="#" className="login-forgot" onClick={(e) => e.preventDefault()}>
                  忘记密码？
                </a>
              </div>
              <input
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                placeholder="请输入密码"
                className="login-input"
              />
            </div>

            {error && (
              <div className="login-error">
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !username || !password}
              className="login-submit"
            >
              {loading ? '进入中…' : '进入系统'}
            </button>

            <div className="login-card-footer">
              本系统仅供授权人员内部使用。
              <br />
              登录即表示您已同意 <a href="#">服务条款</a> 与 <a href="#">数据隐私协议</a>。
            </div>
          </form>
        </section>
      </main>
    </div>
  )
}

export function LoginRoute() {
  const { authState, currentUser, getPreferredProjectId, projects } = useProject()

  if (authState === 'authenticated') {
    return <Navigate to={getPostLoginDestination(currentUser, projects, getPreferredProjectId())} replace />
  }

  return <LoginPanel />
}

export function ProjectsLanding() {
  const { projects } = useProject()
  return <Navigate to={getProjectsLandingDestination(projects)} replace />
}

export function RootRedirect() {
  const { authState, currentUser, getPreferredProjectId, projects } = useProject()

  if (authState !== 'authenticated') {
    return <Navigate to="/login" replace />
  }

  const pid = getPreferredProjectId()
  return <Navigate to={getPostLoginDestination(currentUser, projects, pid)} replace />
}

// Kept for backward compatibility
export function AppLayout({ children }: { children: ReactNode; showSelector?: boolean }) {
  return <div className="min-h-screen" style={{ background: '#F1F5F9' }}>{children}</div>
}
