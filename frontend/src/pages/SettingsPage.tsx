import { useEffect, useRef, useState } from 'react'
import { useProject } from '../context/ProjectContext'
import { getPlatformSettings, savePlatformSettings } from '../api/platformSettings'
import { Card, Field, SectionTitle, Toggle } from '../features/settings/settingsShared'
import { LLMConfigSection } from '../features/settings/LLMConfigSection'
import { AccountPeopleMgmtSection } from '../features/settings/AccountPeopleMgmtSection'
import { LogsSection } from '../features/settings/LogsSection'
import { PeopleBatchImportModal } from '../features/settings/PeopleBatchImportModal'

type Section = 'basic' | 'notify' | 'ai' | 'security' | 'integration' | 'data' | 'logs' | 'people-mgmt'

const SECTIONS: { key: Section; label: string; icon: React.ReactNode }[] = [
  { key: 'basic', label: '基础信息', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /> },
  { key: 'notify', label: '通知与提醒', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" /> },
  { key: 'ai', label: 'AI 能力配置', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /> },
  { key: 'security', label: '安全与权限', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /> },
  { key: 'integration', label: '集成与接口', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /> },
  { key: 'data', label: '数据与备份', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" /> },
  { key: 'logs', label: '操作日志', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /> },
  { key: 'people-mgmt', label: '人员管理', icon: <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" /> },
]

const THEME_COLORS = ['#0369A1', '#7C3AED', '#059669', '#DC2626', '#D97706', '#0F172A']

export function SettingsPage() {
  const { currentUser, reloadProjects } = useProject()
  const [activeSection, setActiveSection] = useState<Section>('basic')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null)

  // 基础信息
  const [logoUrl, setLogoUrl] = useState<string | null>(null)
  const logoInputRef = useRef<HTMLInputElement>(null)
  const [platformName, setPlatformName] = useState('博维AI升级项目驾驶舱')
  const [language, setLanguage] = useState<'zh' | 'en'>('zh')
  const [timezone, setTimezone] = useState('（GMT+08:00）北京、上海、香港')
  const [themeColor, setThemeColor] = useState('#0369A1')

  // 通知
  const [notifyDelay, setNotifyDelay] = useState(true)
  const [notifyAI, setNotifyAI] = useState(true)
  const [notifyDecision, setNotifyDecision] = useState(true)
  const [notifyWeekly, setNotifyWeekly] = useState(false)
  const [channels, setChannels] = useState<Set<string>>(new Set(['站内信', '企业微信']))

  // AI
  const [confidence, setConfidence] = useState(75)

  // 安全
  const [twoFA, setTwoFA] = useState(true)
  const [sessionTTL, setSessionTTL] = useState('8 小时')

  // ── 初始加载 ──
  useEffect(() => {
    getPlatformSettings()
      .then((d) => {
        if (d.logo_url) setLogoUrl(d.logo_url)
        setPlatformName(d.platform_name)
        setLanguage(d.language)
        setTimezone(d.timezone)
        setThemeColor(d.theme_color)
        setNotifyDelay(d.notify_delay)
        setNotifyAI(d.notify_ai)
        setNotifyDecision(d.notify_decision)
        setNotifyWeekly(d.notify_weekly)
        setChannels(new Set(d.notify_channels))
        setConfidence(d.confidence)
        setTwoFA(d.two_fa)
        setSessionTTL(d.session_ttl)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  // ── Logo 选图（转 base64 以便持久化）──
  function handleLogoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => setLogoUrl(reader.result as string)
    reader.readAsDataURL(file)
  }

  function toggleChannel(ch: string) {
    setChannels((prev) => {
      const next = new Set(prev)
      next.has(ch) ? next.delete(ch) : next.add(ch)
      return next
    })
  }

  function showToast(msg: string, ok = true) {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 2500)
  }

  // ── 保存 ──
  async function handleSave() {
    setSaving(true)
    try {
      await savePlatformSettings({
        logo_url: logoUrl,
        platform_name: platformName,
        language,
        timezone,
        theme_color: themeColor,
        notify_delay: notifyDelay,
        notify_ai: notifyAI,
        notify_decision: notifyDecision,
        notify_weekly: notifyWeekly,
        notify_channels: [...channels],
        confidence,
        two_fa: twoFA,
        session_ttl: sessionTTL,
      })
      showToast('设置已保存')
      setTimeout(() => window.location.reload(), 1200)
    } catch {
      showToast('保存失败，请重试', false)
    } finally {
      setSaving(false)
    }
  }

  if (!currentUser?.is_tech_admin) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 text-slate-400">
        <svg style={{ width: 48, height: 48, opacity: 0.3 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
        <p className="text-sm font-semibold">无权限访问</p>
        <p className="text-xs">仅超级管理员可访问系统设置</p>
      </div>
    )
  }

  const visibleSections = SECTIONS
  const effectiveSection: Section = activeSection

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Toast */}
      {toast && (
        <div
          className="fixed top-5 left-1/2 z-50 flex items-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold text-white shadow-lg"
          style={{
            transform: 'translateX(-50%)',
            background: toast.ok ? 'linear-gradient(135deg,#059669,#34D399)' : 'linear-gradient(135deg,#DC2626,#F87171)',
            boxShadow: toast.ok ? '0 4px 20px rgba(5,150,105,0.35)' : '0 4px 20px rgba(220,38,38,0.35)',
          }}
        >
          <svg style={{ width: 16, height: 16 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d={toast.ok ? 'M5 13l4 4L19 7' : 'M6 18L18 6M6 6l12 12'} />
          </svg>
          {toast.msg}
        </div>
      )}

      {/* Top Bar */}
      <header className="h-16 flex items-center px-6 gap-3 flex-shrink-0 bg-white border-b" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex-1">
          <h1 className="text-base font-bold text-slate-800">系统设置</h1>
        </div>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="cursor-pointer px-4 py-2 rounded-lg border border-slate-200 text-slate-500 text-sm font-semibold hover:bg-slate-50 transition-colors"
        >
          取消
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || loading}
          className="cursor-pointer flex items-center gap-2 px-4 py-2 rounded-lg text-white text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-60"
          style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)', boxShadow: '0 2px 8px rgba(3,105,161,0.25)' }}
        >
          <svg style={{ width: 14, height: 14 }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
          </svg>
          {saving ? '保存中…' : '保存更改'}
        </button>
      </header>

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-sm text-slate-400">加载中…</p>
        </div>
      ) : (
        <div className="flex-1 overflow-hidden flex">

          {/* Secondary nav */}
          <div className="w-52 flex-shrink-0 bg-white border-r overflow-y-auto p-3" style={{ borderColor: '#E9EFF6' }}>
            {visibleSections.map((s) => {
              const active = effectiveSection === s.key
              return (
                <button
                  key={s.key}
                  type="button"
                  onClick={() => setActiveSection(s.key)}
                  className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium transition-all text-left"
                  style={{ background: active ? '#EFF6FF' : 'transparent', color: active ? '#0369A1' : '#64748B', fontWeight: active ? 700 : 500 }}
                  onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = '#F1F5F9' }}
                  onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = 'transparent' }}
                >
                  <svg style={{ width: 16, height: 16, flexShrink: 0, color: active ? '#0369A1' : '#94A3B8' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    {s.icon}
                  </svg>
                  {s.label}
                </button>
              )
            })}
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6" style={{ background: '#F1F5F9' }}>
            <div className="max-w-3xl mx-auto space-y-5">

              {effectiveSection === 'basic' && (
                <Card>
                  <SectionTitle>平台基础信息</SectionTitle>

                  <Field label="平台标识" desc="显示在登录页和侧边栏顶部的 Logo 与名称">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: 'linear-gradient(135deg,#0EA5E9,#0369A1)' }}>
                        {logoUrl
                          ? <img src={logoUrl} alt="logo" style={{ width: 48, height: 48, objectFit: 'contain', borderRadius: 12 }} />
                          : <svg style={{ width: 24, height: 24, color: 'white' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                            </svg>
                        }
                      </div>
                      <input ref={logoInputRef} type="file" accept="image/*" className="hidden" onChange={handleLogoChange} />
                      <button type="button" onClick={() => logoInputRef.current?.click()}
                        className="cursor-pointer px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 text-xs font-semibold hover:bg-slate-50 transition-colors">
                        更换 Logo
                      </button>
                      {logoUrl && (
                        <button type="button" onClick={() => { setLogoUrl(null); if (logoInputRef.current) logoInputRef.current.value = '' }}
                          className="cursor-pointer px-3 py-1.5 rounded-lg border border-slate-200 text-red-500 text-xs font-semibold hover:bg-red-50 transition-colors">
                          重置
                        </button>
                      )}
                    </div>
                  </Field>

                  <Field label="平台名称" desc="展示在浏览器标题与系统各处">
                    <input type="text" value={platformName} onChange={(e) => setPlatformName(e.target.value)}
                      className="w-72 border border-slate-200 rounded-xl px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-400/30 focus:border-sky-400 transition" />
                  </Field>

                  <Field label="默认语言" desc="新成员加入时的默认界面语言">
                    <div className="flex bg-slate-100 rounded-xl p-1 gap-1">
                      {(['zh', 'en'] as const).map((lang) => (
                        <button key={lang} type="button" onClick={() => setLanguage(lang)}
                          className="px-4 py-1.5 rounded-lg text-xs font-semibold transition-all"
                          style={language === lang ? { background: '#fff', color: '#0369A1', boxShadow: '0 1px 3px rgba(15,23,42,0.1)' } : { color: '#64748B' }}>
                          {lang === 'zh' ? '简体中文' : 'English'}
                        </button>
                      ))}
                    </div>
                  </Field>

                  <Field label="时区" desc="影响所有时间戳与定时任务的执行时间">
                    <select value={timezone} onChange={(e) => setTimezone(e.target.value)}
                      className="w-72 border border-slate-200 rounded-xl px-3 py-2 text-sm text-slate-800 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-400/30 focus:border-sky-400 transition">
                      <option>（GMT+08:00）北京、上海、香港</option>
                      <option>（GMT+00:00）协调世界时 UTC</option>
                      <option>（GMT-08:00）太平洋时间</option>
                    </select>
                  </Field>

                  <Field label="主题色" desc="用于按钮、链接与高亮元素的品牌主色" last>
                    <div className="flex items-center gap-2.5">
                      {THEME_COLORS.map((color) => (
                        <button key={color} type="button" onClick={() => setThemeColor(color)}
                          className="w-8 h-8 rounded-xl transition-transform hover:scale-110 relative flex-shrink-0"
                          style={{ background: color, border: '2px solid transparent', outline: themeColor === color ? '2px solid #0369A1' : 'none', outlineOffset: 2 }}>
                          {themeColor === color && <span className="absolute inset-0 flex items-center justify-center text-white text-xs font-bold">✓</span>}
                        </button>
                      ))}
                    </div>
                  </Field>
                </Card>
              )}

              {effectiveSection === 'notify' && (
                <Card>
                  <SectionTitle>通知与提醒</SectionTitle>
                  <Field label="任务延期提醒" desc="任务临近或超过计划时间时，向负责人推送提醒">
                    <Toggle checked={notifyDelay} onChange={setNotifyDelay} />
                  </Field>
                  <Field label="AI 待确认提醒" desc="AI 提取结果待确认时，每日汇总推送至确认人">
                    <Toggle checked={notifyAI} onChange={setNotifyAI} />
                  </Field>
                  <Field label="需决策事项提醒" desc="出现需高层决策的问题时，即时通知决策人">
                    <Toggle checked={notifyDecision} onChange={setNotifyDecision} />
                  </Field>
                  <Field label="周报自动汇总" desc="每周五 18:00 自动生成项目周报并发送给管理层">
                    <Toggle checked={notifyWeekly} onChange={setNotifyWeekly} />
                  </Field>
                  <Field label="通知渠道" desc="选择接收系统通知的方式" last>
                    <div className="flex items-center gap-2 flex-wrap">
                      {['站内信', '企业微信', '邮件', '短信'].map((ch) => {
                        const on = channels.has(ch)
                        return (
                          <button key={ch} type="button" onClick={() => toggleChannel(ch)}
                            className="cursor-pointer px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5"
                            style={on ? { border: '2px solid #BFDBFE', background: '#EFF6FF', color: '#1D4ED8' } : { border: '1px solid #E2E8F0', background: '#fff', color: '#64748B' }}>
                            {on && <svg style={{ width: 12, height: 12 }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" /></svg>}
                            {ch}
                          </button>
                        )
                      })}
                    </div>
                  </Field>
                </Card>
              )}

              {effectiveSection === 'ai' && (
                <>
                  <Card>
                    <SectionTitle>AI 建议置信度</SectionTitle>
                    <Field label="置信度阈值" desc={`低于该值的 AI 提取结果将标记为"待人工复核"，需负责人手动确认后方可入库`} last>
                      <div className="flex items-center gap-3" style={{ width: 280 }}>
                        <input type="range" min={50} max={95} value={confidence} onChange={(e) => setConfidence(Number(e.target.value))}
                          className="flex-1 cursor-pointer" style={{ accentColor: '#0369A1' }} />
                        <span className="text-sm font-bold text-blue-700 w-10 text-right">{confidence}%</span>
                      </div>
                    </Field>
                  </Card>
                  <LLMConfigSection />
                </>
              )}

              {effectiveSection === 'security' && (
                <>
                  <Card>
                    <SectionTitle>安全与权限</SectionTitle>
                    <Field label="双因素认证（2FA）" desc="要求全员登录时进行二次身份验证">
                      <Toggle checked={twoFA} onChange={setTwoFA} />
                    </Field>
                    <Field label="登录会话有效期" desc="超过该时长未操作将自动登出">
                      <select value={sessionTTL} onChange={(e) => setSessionTTL(e.target.value)}
                        className="w-40 border border-slate-200 rounded-xl px-3 py-2 text-sm text-slate-800 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-400/30 focus:border-sky-400 transition">
                        <option>2 小时</option>
                        <option>8 小时</option>
                        <option>24 小时</option>
                      </select>
                    </Field>
                    <Field label="操作留痕审计" desc="记录所有数据修改、确认与删除操作（不可关闭）" last>
                      <Toggle checked disabled />
                    </Field>
                  </Card>
                  <div className="flex items-center justify-between p-4 rounded-xl" style={{ background: '#FEF2F2', border: '1px solid #FECACA' }}>
                    <div>
                      <p className="text-sm font-bold text-red-800">清空 AI 缓存数据</p>
                      <p className="text-xs text-red-500 mt-1">将清除所有未确认的 AI 提取暂存结果，此操作不可恢复</p>
                    </div>
                    <button className="cursor-pointer px-4 py-2 rounded-lg bg-white border-2 border-red-200 text-red-600 text-sm font-semibold hover:bg-red-50 transition-colors flex-shrink-0">
                      清空缓存
                    </button>
                  </div>
                </>
              )}

              {effectiveSection === 'people-mgmt' && <AccountPeopleMgmtSection />}

              {(['integration', 'data'] as Section[]).includes(effectiveSection) && (
                <Card>
                  <div className="py-12 flex flex-col items-center text-center">
                    <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4" style={{ background: '#EFF6FF' }}>
                      <svg style={{ width: 28, height: 28, color: '#2563EB' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                      </svg>
                    </div>
                    <p className="text-sm font-bold text-slate-700">
                      {{ integration: '集成与接口', data: '数据与备份' }[effectiveSection as 'integration' | 'data']}
                    </p>
                    <p className="text-xs text-slate-400 mt-1.5">该模块正在建设中，即将上线</p>
                  </div>
                </Card>
              )}
              {effectiveSection === 'logs' && <LogsSection />}

            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ── 子组件 ── */
