import { useState, useEffect, type ReactNode } from 'react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { useProject } from '../context/ProjectContext'
import { getPostLoginDestination, getProjectsLandingDestination } from '../domain/authFlow'
import { getWecomQrcodeUrl, getWecomSilentAuthUrl, bindWecomAccount } from '../api/auth'

export function CenterMessage({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-2">
      <div className="text-slate-700 font-semibold">{title}</div>
      {subtitle ? <div className="text-slate-400 text-sm">{subtitle}</div> : null}
    </div>
  )
}

function UserIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  )
}

function LockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="5" y="11" width="14" height="10" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  )
}

function EyeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function EyeOffIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  )
}

function AlertIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function InfoIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function WecomIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M12 2C6.48 2 2 5.94 2 10.8c0 2.77 1.46 5.24 3.74 6.86L5 21l3.6-1.98c1.04.29 2.14.45 3.4.45 5.52 0 10-3.94 10-8.67S17.52 2 12 2zm-3.2 9.6c-.66 0-1.2-.54-1.2-1.2s.54-1.2 1.2-1.2 1.2.54 1.2 1.2-.54 1.2-1.2 1.2zm6.4 0c-.66 0-1.2-.54-1.2-1.2s.54-1.2 1.2-1.2 1.2.54 1.2 1.2-.54 1.2-1.2 1.2z"
      />
    </svg>
  )
}

function LogoFallback() {
  return (
    <svg className="login-logo-fallback-svg" viewBox="0 0 240 64" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs>
        <linearGradient id="logo-o-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#0EA5E9" />
          <stop offset="100%" stopColor="#2563EB" />
        </linearGradient>
      </defs>
      <text x="0" y="34" className="login-logo-fallback-text">
        M
        <tspan fill="url(#logo-o-grad)">O</tspan>
        WAYS
      </text>
      <text x="2" y="56" className="login-logo-fallback-sub">博维咨询</text>
    </svg>
  )
}

function HeroIllustration() {
  return (
    <svg className="login-hero-illustration" viewBox="0 0 540 360" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs>
        <linearGradient id="platform-top" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#E0F2FE" />
          <stop offset="100%" stopColor="#BFDBFE" />
        </linearGradient>
        <linearGradient id="platform-side" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#60A5FA" />
          <stop offset="100%" stopColor="#2563EB" />
        </linearGradient>
        <linearGradient id="platform-front" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#3B82F6" />
          <stop offset="100%" stopColor="#1D4ED8" />
        </linearGradient>
        <linearGradient id="card-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.98" />
          <stop offset="100%" stopColor="#EFF6FF" stopOpacity="0.95" />
        </linearGradient>
        <filter id="soft-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="12" stdDeviation="14" floodColor="#1E40AF" floodOpacity="0.1" />
        </filter>
      </defs>

      {/* 远景城市剪影 */}
      <g fill="#DBEAFE" fillOpacity="0.35">
        <rect x="40" y="200" width="28" height="90" rx="2" />
        <rect x="76" y="170" width="36" height="120" rx="2" />
        <rect x="120" y="210" width="24" height="80" rx="2" />
        <rect x="380" y="190" width="32" height="100" rx="2" />
        <rect x="420" y="160" width="40" height="130" rx="2" />
        <rect x="470" y="205" width="26" height="85" rx="2" />
      </g>

      {/* 主平台 — 三层 */}
      <g filter="url(#soft-shadow)">
        {/* 底层 */}
        <path d="M140 260 L260 330 L380 260 L260 190 Z" fill="url(#platform-top)" />
        <path d="M140 260 L140 290 L260 360 L260 330 Z" fill="#1E40A8" />
        <path d="M380 260 L380 290 L260 360 L260 330 Z" fill="#1E3A8A" />

        {/* 中层 */}
        <path d="M170 230 L260 282 L350 230 L260 178 Z" fill="#BFDBFE" />
        <path d="M170 230 L170 255 L260 307 L260 282 Z" fill="#3B82F6" />
        <path d="M350 230 L350 255 L260 307 L260 282 Z" fill="#2563EB" />

        {/* 顶层 */}
        <path d="M200 200 L260 235 L320 200 L260 165 Z" fill="url(#platform-top)" />
        <path d="M200 200 L200 220 L260 255 L260 235 Z" fill="url(#platform-side)" />
        <path d="M320 200 L320 220 L260 255 L260 235 Z" fill="url(#platform-front)" />
      </g>

      {/* 连接线 */}
      <g stroke="#60A5FA" strokeWidth="2" strokeDasharray="4 4" strokeLinecap="round">
        <path d="M120 160 Q150 180 200 200">
          <animate attributeName="stroke-dashoffset" from="16" to="0" dur="2s" repeatCount="indefinite" />
        </path>
        <path d="M400 160 Q370 180 320 200">
          <animate attributeName="stroke-dashoffset" from="16" to="0" dur="2s" repeatCount="indefinite" />
        </path>
        <path d="M260 90 Q260 130 260 165">
          <animate attributeName="stroke-dashoffset" from="16" to="0" dur="2s" repeatCount="indefinite" />
        </path>
      </g>

      {/* 左侧浮动卡片：任务清单 */}
      <g transform="translate(70, 110)">
        <rect x="0" y="0" width="84" height="96" rx="14" fill="url(#card-grad)" stroke="#BFDBFE" strokeWidth="1.5" />
        <rect x="16" y="24" width="52" height="6" rx="3" fill="#3B82F6" />
        <rect x="16" y="40" width="36" height="5" rx="2.5" fill="#93C5FD" />
        <rect x="16" y="52" width="44" height="5" rx="2.5" fill="#93C5FD" />
        <rect x="16" y="64" width="28" height="5" rx="2.5" fill="#93C5FD" />
        <circle cx="24" cy="16" r="5" fill="#3B82F6" />
      </g>

      {/* 右侧浮动卡片：人物 */}
      <g transform="translate(370, 100)">
        <rect x="0" y="0" width="88" height="100" rx="14" fill="url(#card-grad)" stroke="#BFDBFE" strokeWidth="1.5" />
        <circle cx="44" cy="34" r="16" fill="#DBEAFE" />
        <circle cx="44" cy="30" r="7" fill="#3B82F6" />
        <path d="M30 56 Q44 44 58 56 V62 H30 Z" fill="#3B82F6" />
        <rect x="24" y="70" width="40" height="5" rx="2.5" fill="#93C5FD" />
      </g>

      {/* 上方浮动卡片：图表 */}
      <g transform="translate(210, 24)">
        <rect x="0" y="0" width="96" height="88" rx="14" fill="url(#card-grad)" stroke="#BFDBFE" strokeWidth="1.5" />
        <rect x="16" y="56" width="12" height="18" rx="3" fill="#3B82F6" />
        <rect x="34" y="42" width="12" height="32" rx="3" fill="#60A5FA" />
        <rect x="52" y="28" width="12" height="46" rx="3" fill="#93C5FD" />
        <rect x="70" y="36" width="12" height="38" rx="3" fill="#BFDBFE" />
      </g>
    </svg>
  )
}

function FeatureItem({ icon, title, desc }: { icon: ReactNode; title: string; desc: string }) {
  return (
    <div className="login-feature-item">
      <div className="login-feature-icon">{icon}</div>
      <div className="login-feature-text">
        <div className="login-feature-title">{title}</div>
        <div className="login-feature-desc">{desc}</div>
      </div>
    </div>
  )
}

function LoginPanel() {
  const { login, loading, error } = useProject()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
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
  const [showBindPassword, setShowBindPassword] = useState(false)
  const [bindLoading, setBindLoading] = useState(false)
  const [bindError, setBindError] = useState('')

  // 检测企微环境，自动触发静默授权（免扫码登录）
  useEffect(() => {
    if (isWecomUnbound) return // 绑定页不触发
    const ua = navigator.userAgent.toLowerCase()
    const isWxWork = /wxwork/i.test(ua) || /microMessenger/i.test(ua)
    if (!isWxWork) return
    // 防重入：如果本次会话已尝试过静默授权，不再重复触发，避免死循环闪烁
    if (sessionStorage.getItem('wecom_silent_auth_attempted')) return
    sessionStorage.setItem('wecom_silent_auth_attempted', '1')
    getWecomSilentAuthUrl()
      .then(({ url }) => { if (url) window.location.href = url })
      .catch(() => {
        // 失败时清除标记，允许用户手动重试
        sessionStorage.removeItem('wecom_silent_auth_attempted')
      })
  }, [isWecomUnbound])

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

  return (
    <div className="login-page">
      <div className="login-bg" aria-hidden="true" />

      <main className="login-body">
          <section className="login-brand-panel" aria-label="系统介绍">
            <div className="login-brand-content">
              <div className="login-logo">
                <img
                  src="/moways-logo-transparent.png"
                  alt="MOWAYS 博维咨询"
                  className="login-logo-img"
                />
              </div>
              <div className="login-brand-text">
              <h1 className="login-title-cn">项目管理协同平台</h1>
              <p className="login-subtitle">高效协同 · 透明管理 · 价值驱动</p>
              <div className="login-title-line" aria-hidden="true" />
            </div>

            <div className="login-features">
              <FeatureItem
                icon={
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                    <path d="m9 12 2 2 4-4" />
                  </svg>
                }
                title="安全可靠"
                desc="多重安全防护"
              />
              <FeatureItem
                icon={
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2 2 7l10 5 10-5-10-5Z" />
                    <path d="m2 17 10 5 10-5" />
                    <path d="m2 12 10 5 10-5" />
                  </svg>
                }
                title="高效协同"
                desc="打通协作全流程"
              />
              <FeatureItem
                icon={
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 3v18h18" />
                    <path d="m18 17-4-4-3 3-3-3-2 2" />
                  </svg>
                }
                title="数据驱动"
                desc="智能分析与决策"
              />
            </div>
          </div>
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
                <div className="login-input-wrap">
                  <UserIcon className="login-input-icon" />
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
              </div>

              <div className="login-field login-field-password">
                <label className="login-field-label" htmlFor="bind-password">
                  密码
                </label>
                <div className="login-input-wrap">
                  <LockIcon className="login-input-icon" />
                  <input
                    id="bind-password"
                    type={showBindPassword ? 'text' : 'password'}
                    value={bindPassword}
                    onChange={(e) => setBindPassword(e.target.value)}
                    autoComplete="current-password"
                    placeholder="请输入密码"
                    className="login-input"
                  />
                  <button
                    type="button"
                    className="login-input-suffix"
                    onClick={() => setShowBindPassword((v) => !v)}
                    tabIndex={-1}
                    aria-label={showBindPassword ? '隐藏密码' : '显示密码'}
                  >
                    {showBindPassword ? <EyeOffIcon /> : <EyeIcon />}
                  </button>
                </div>
              </div>

              {bindError && (
                <div className="login-error">
                  <AlertIcon />
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
              <h2 className="login-welcome">欢迎登录</h2>
              <p className="login-card-desc">请输入您的系统账号与密码以访问管理平台</p>

              <div className="login-field">
                <label className="login-field-label" htmlFor="login-username">
                  系统账号
                </label>
                <div className="login-input-wrap">
                  <UserIcon className="login-input-icon" />
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
              </div>

              <div className="login-field login-field-password">
                <div className="login-field-row">
                  <label className="login-field-label" htmlFor="login-password">
                    密码
                  </label>
                  <button type="button" className="login-forgot" onClick={() => setShowWecomGuide((prev) => !prev)}>
                    忘记密码？
                  </button>
                </div>
                <div className="login-input-wrap">
                  <LockIcon className="login-input-icon" />
                  <input
                    id="login-password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                    placeholder="请输入密码"
                    className="login-input"
                  />
                  <button
                    type="button"
                    className="login-input-suffix"
                    onClick={() => setShowPassword((v) => !v)}
                    tabIndex={-1}
                    aria-label={showPassword ? '隐藏密码' : '显示密码'}
                  >
                    {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                  </button>
                </div>
              </div>

              {error && (
                <div className="login-error">
                  <AlertIcon />
                  <span>{error}</span>
                </div>
              )}

              {wecomError && !error && (
                <div className="login-error">
                  <AlertIcon />
                  <span>{wecomError}</span>
                </div>
              )}

              {showWecomGuide && (
                <div className="login-info">
                  <InfoIcon />
                  <span>忘记密码或账号被锁定？请使用下方<strong>企业微信扫码登录</strong>，登录后在侧边栏点击锁形图标即可修改密码。如企业微信未绑定，请联系管理员在账号管理页绑定。</span>
                </div>
              )}

              <button
                type="submit"
                disabled={loading || !username || !password}
                className="login-submit"
              >
                {loading ? '登录中…' : '登 录'}
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
                    <WecomIcon className="login-wecom-icon" />
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

  // 登录成功后清除静默授权防重入标记
  useEffect(() => {
    if (authState === 'authenticated') {
      sessionStorage.removeItem('wecom_silent_auth_attempted')
    }
  }, [authState])

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
