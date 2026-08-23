import { useState } from 'react'
import type { AppPage } from '../types'
import type { NavigationEntry } from '../domain/navigationModel'

type Props = { activePage: AppPage; entries: NavigationEntry[]; onNavigate: (page: AppPage) => void; onChangePassword: () => void; onLogout: () => void }
const primaryPages: AppPage[] = ['dashboard', 'table', 'confirm']
const icon: Record<string, string> = { home: '⌂', table: '☷', confirm: '✓', voice: '◉', meeting: '▤', archive: '□', issues: '!', org: '♧', projects: '▣', bell: '◌', settings: '⚙', mytasks: '✓' }

export function MobileAppNavigation({ activePage, entries, onNavigate, onChangePassword, onLogout }: Props) {
  const [moreOpen, setMoreOpen] = useState(false)
  const primaryEntries = primaryPages.map((page) => entries.find((entry) => entry.page === page)).filter(Boolean) as NavigationEntry[]
  for (const entry of entries) if (primaryEntries.length < 3 && !primaryEntries.some((item) => item.page === entry.page)) primaryEntries.push(entry)
  const moreEntries = entries.filter((entry) => !primaryEntries.some((item) => item.page === entry.page))
  const open = (page: AppPage) => { setMoreOpen(false); onNavigate(page) }
  return <>
    <nav className="fixed inset-x-0 bottom-0 z-40 flex h-[68px] items-center justify-around border-t border-slate-200 bg-white/95 px-2 pb-[env(safe-area-inset-bottom)] shadow-[0_-4px_16px_rgba(15,23,42,.06)] min-[800px]:hidden" aria-label="移动主导航">
      {primaryEntries.map((entry) => <button key={entry.page} type="button" onClick={() => open(entry.page)} className={`flex min-w-12 flex-col items-center gap-1 text-[11px] ${activePage === entry.page ? 'font-semibold text-sky-600' : 'text-slate-500'}`}><span className="text-lg leading-none">{icon[entry.icon]}</span>{entry.page === 'dashboard' ? '首页' : entry.page === 'table' ? '任务' : '确认'}</button>)}
      <button type="button" onClick={() => setMoreOpen(true)} className="flex min-w-12 flex-col items-center gap-1 text-[11px] text-slate-500"><span className="text-lg leading-none">☷</span>更多</button>
    </nav>
    {moreOpen && <div className="fixed inset-0 z-50 min-[800px]:hidden" role="dialog" aria-modal="true" aria-label="更多功能">
      <button type="button" aria-label="关闭更多功能" className="absolute inset-0 bg-slate-900/30" onClick={() => setMoreOpen(false)} />
      <section className="absolute inset-x-0 bottom-0 max-h-[78vh] overflow-y-auto rounded-t-3xl bg-white p-5 pb-8 shadow-2xl"><div className="mb-4 flex items-center justify-between"><h2 className="text-base font-semibold">更多功能</h2><button type="button" onClick={() => setMoreOpen(false)} className="text-sm text-slate-500">关闭</button></div><div className="grid grid-cols-4 gap-4">{moreEntries.map((entry) => <button key={entry.page} type="button" onClick={() => open(entry.page)} className="flex flex-col items-center gap-1 text-xs text-slate-600"><span className="grid h-10 w-10 place-items-center rounded-xl bg-slate-100 text-lg text-sky-600">{icon[entry.icon]}</span>{entry.label}</button>)}</div><div className="mt-6 flex gap-3 border-t pt-4"><button type="button" onClick={() => { setMoreOpen(false); onChangePassword() }} className="flex-1 rounded-xl bg-slate-100 py-3 text-sm text-slate-700">修改密码</button><button type="button" onClick={onLogout} className="flex-1 rounded-xl bg-rose-50 py-3 text-sm text-rose-600">退出登录</button></div></section>
    </div>}
  </>
}
