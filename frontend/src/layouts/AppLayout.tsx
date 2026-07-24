import { useState, type ReactNode } from 'react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { useProject } from '../context/ProjectContext'
import { getPostLoginDestination, getProjectsLandingDestination } from '../domain/authFlow'
import { SYSTEM_NAME_CN } from '../domain/displayNames'
import { getWecomQrcodeUrl, bindWecomAccount } from '../api/auth'

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
  const [searchParams] = useSearchParams()
  const [wecomLoading, setWecomLoading] = useState(false)
  const [showWecomGuide, setShowWecomGuide] = useState(false)

  // 企业微信回调参数
  const wecomReason = searchParams.get('reason')
  const wecomUserid = searchParams.get('wecom_userid') || ''
  const isWecomUnbound = wecomReason === 'wecom_unbound' && !!wecomUserid

  // 自助绑定表单状态
  const [bindUsername, setBindUsername] = useState('')
  const [bindPassword, setBindPassword] = useState('')
  const [bindLoading, setBindLoading] = useState(false)
  const [bindError, setBindError] = useState('')

  const wecomMessages: Record<string, string> = {
    wecom_unbound: '该企业微信账号尚未绑定系统账号，请在下方输入账号密码完成绑定。',
    wecom_error: '企业微信登录失败，请重试或使用账号密码登录。',
    wecom_disabled: '企业微信登录未启用，请使用账号密码登录。',
    account_disabled: '该账号已被禁用，请联系管理员。',
  }
  const wecomError = wecomReason && !isWecomUnbound ? (wecomMessages[wecomReason] ?? '') : ''
  const wecomBindHint = isWecomUnbound ? wecomMessages['wecom_unbound'] : ''

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    try {
      await login(username.trim(), password)
    } catch {
      // 错误已存入 context.error
    }
  }

  const handleWecomLogin = async () => {
    setWecomLoading(true)
    try {
      const { url } = await getWecomQrcodeUrl()
      if (url) window.location.href = url
    } catch {
      setWecomLoading(false)
    }
  }

  const handleWecomBind = async (event: React.FormEvent) => {
    event.preventDefault()
    setBindError('')
    if (!bindUsername.trim() || !bindPassword) {
      setBindError('请输入账号和密码')
      return
    }
    setBindLoading(true)
    try {
      await bindWecomAccount(wecomUserid, bindUsername.trim(), bindPassword)
      // 绑定成功，后端已种 cookie，跳转首页
      window.location.replace('/home/dashboard')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '绑定失败，请检查账号密码'
      setBindError(msg)
    } finally {
      setBindLoading(false)
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
          {isWecomUnbound ? (
            <form onSubmit={handleWecomBind} className="login-card">
              <h2 className="login-welcome">绑定账号</h2>
              <p className="login-card-desc">{wecomBindHint}</p>

              <div className="login-field">
                <label className="login-field-label" htmlFor="bind-username">
                  系统账号
                </label>
                <input
                  id="bind-username"
                  type="text"
                  value={bindUsername}
                  onChange={(e) => setBindUsername(e.target.value)}
                  autoComplete="username"
                  placeholder="请输入系统账号"
                  className="login-input"
                />
              </div>

              <div className="login-field login-field-password">
                <label className="login-field-label" htmlFor="bind-password">
                  密码
                </label>
                <input
                  id="bind-password"
                  type="password"
                  value={bindPassword}
                  onChange={(e) => setBindPassword(e.target.value)}
                  autoComplete="current-password"
                  placeholder="请输入密码"
                  className="login-input"
                />
              </div>

              {bindError && (
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
                  <span>{bindError}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={bindLoading || !bindUsername || !bindPassword}
                className="login-submit"
              >
                {bindLoading ? '绑定中…' : '绑定并登录'}
              </button>

              <div className="login-divider">
                <span>或</span>
              </div>

              <button
                type="button"
                onClick={() => window.location.replace('/login')}
                className="login-wecom-btn"
              >
                使用账号密码登录
              </button>

              <div className="login-card-footer">
                绑定后，下次可直接使用企业微信扫码登录。
              </div>
            </form>
          ) : (
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
                  <button type="button" className="login-forgot" onClick={() => setShowWecomGuide(prev => !prev)}>
                    忘记密码？
                  </button>
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

              {wecomError && !error && (
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
                  <span>{wecomError}</span>
                </div>
              )}

              {showWecomGuide && (
                <div className="login-info">
                  <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path
                      d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <span>忘记密码或账号被锁定？请使用下方<strong>企业微信扫码登录</strong>，登录后在侧边栏点击锁形图标即可修改密码。如企业微信未绑定，请联系管理员在账号管理页绑定。</span>
                </div>
              )}

              <button
                type="submit"
                disabled={loading || !username || !password}
                className="login-submit"
              >
                {loading ? '进入中…' : '进入系统'}
              </button>

              <div className="login-divider">
                <span>或</span>
              </div>

              <button
                type="button"
                onClick={handleWecomLogin}
                disabled={wecomLoading}
                className="login-wecom-btn"
              >
                {wecomLoading ? (
                  '跳转中…'
                ) : (
                  <>
                    <svg viewBox="0 0 24 24" className="login-wecom-icon" aria-hidden="true">
                      <path
                        fill="currentColor"
                        d="M12 2C6.48 2 2 5.94 2 10.8c0 2.77 1.46 5.24 3.74 6.86L5 21l3.6-1.98c1.04.29 2.14.45 3.4.45 5.52 0 10-3.94 10-8.67S17.52 2 12 2zm-3.2 9.6c-.66 0-1.2-.54-1.2-1.2s.54-1.2 1.2-1.2 1.2.54 1.2 1.2-.54 1.2-1.2 1.2zm6.4 0c-.66 0-1.2-.54-1.2-1.2s.54-1.2 1.2-1.2 1.2.54 1.2 1.2-.54 1.2-1.2 1.2z"
                      />
                    </svg>
                    企业微信登录
                  </>
                )}
              </button>

              <div className="login-card-footer">
                本系统仅供授权人员内部使用。
                <br />
                登录即表示您已同意 <a href="#">服务条款</a> 与 <a href="#">数据隐私协议</a>。
              </div>
            </form>
          )}
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
