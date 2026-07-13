import { useEffect, useState } from 'react'
import { fmtDate } from '../utils/time'
import { getPending, ceoDecide } from '../api/confirmations'
import { useProject } from '../context/ProjectContext'
import type { ConfirmationItem } from '../types'

export function DecisionPage() {
  const { currentProjectId, currentUser, globalUserRoles } = useProject()
  const [items, setItems] = useState<ConfirmationItem[]>([])
  const [selected, setSelected] = useState<ConfirmationItem | null>(null)
  const [loading, setLoading] = useState(false)
  const [note, setNote] = useState('')
  const [acting, setActing] = useState(false)

  const isCEO = Boolean(currentUser?.is_tech_admin || globalUserRoles.includes('project_ceo'))

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getPending(null, 'ceo')
      .then((d) => { if (!cancelled) { setItems(d); if (d.length > 0) setSelected(d[0]) } })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])  // 企业教练决策中心跨全部项目，不依赖 currentProjectId

  async function handleDecide() {
    if (!selected || !currentUser || !note.trim()) return
    setActing(true)
    try {
      await ceoDecide(selected.id, note, currentUser.name)
      setItems((prev) => prev.filter((i) => i.id !== selected.id))
      setSelected(null)
      setNote('')
    } finally { setActing(false) }
  }

  // 非 CEO 用户无权访问
  if (!isCEO) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4" style={{ background: '#F1F5F9' }}>
        <div className="w-16 h-16 rounded-2xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#7C3AED,#A78BFA)' }}>
          <svg style={{ width: 32, height: 32, color: 'white' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <div className="text-center">
          <p className="text-slate-800 font-bold text-base">无访问权限</p>
          <p className="text-slate-400 text-sm mt-1">企业教练决策中心仅限企业教练角色访问</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <header className="h-16 flex items-center px-6 gap-3 flex-shrink-0 bg-white border-b" style={{ borderColor: '#E9EFF6' }}>
        <div className="flex-1">
          <h1 className="text-base font-bold text-slate-800">企业教练决策中心</h1>
          <p className="text-xs text-slate-400 mt-0.5">处理上报给企业教练的重大决策事项</p>
        </div>
      </header>

      <div className="flex-1 overflow-hidden flex p-6 gap-5" style={{ background: '#F1F5F9' }}>
        {/* List */}
        <div className="bg-white rounded-2xl border flex flex-col overflow-hidden" style={{ width: '50%', borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
          <div className="flex items-center justify-between px-5 py-3.5 border-b flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
            <h2 className="text-sm font-bold text-slate-800">待决策列表</h2>
            <span className="w-5 h-5 rounded-full bg-red-100 text-red-600 text-xs font-bold flex items-center justify-center">{items.length}</span>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="py-12 text-center text-slate-400 text-sm">加载中…</div>
            ) : items.length === 0 ? (
              <div className="py-12 text-center text-slate-400 text-sm">暂无待决策事项</div>
            ) : (
              <div className="divide-y" style={{ borderColor: '#F8FAFC' }}>
                {items.map((item) => {
                  const isSelected = selected?.id === item.id
                  return (
                    <div
                      key={item.id}
                      onClick={() => setSelected(item)}
                      className="px-5 py-4 cursor-pointer transition-colors"
                      style={{ background: isSelected ? '#EFF6FF' : 'white', borderLeft: isSelected ? '2px solid #0369A1' : '2px solid transparent' }}
                    >
                      <p className="text-sm font-semibold text-slate-800 leading-snug">{String((item as any).transcription_text ?? '决策事项').slice(0, 60)}…</p>
                      <div className="flex items-center gap-3 mt-2 text-xs text-slate-400">
                        <span>提交人：{item.submitter}</span>
                        <span>{fmtDate(item.created_at)}</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Decision panel */}
        <div className="bg-white rounded-2xl border flex flex-col overflow-hidden flex-1" style={{ borderColor: '#E9EFF6', boxShadow: '0 1px 4px rgba(15,23,42,0.06)' }}>
          {selected ? (
            <>
              <div className="px-5 py-3.5 border-b flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
                <h2 className="text-sm font-bold text-slate-800">决策详情</h2>
              </div>
              <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
                <div>
                  <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">原始内容</p>
                  <p className="text-sm text-slate-700 leading-relaxed p-3 rounded-xl" style={{ background: '#F8FAFC', border: '1px solid #E9EFF6' }}>{String((selected as any).transcription_text ?? '-')}</p>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1.5">企业教练决策意见（必填）</label>
                  <textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="请输入您的决策意见…"
                    className="w-full border border-slate-200 rounded-xl p-3 text-sm focus:outline-none resize-none"
                    style={{ height: 120 }}
                  />
                </div>
              </div>
              <div className="px-5 py-4 border-t flex gap-3 flex-shrink-0" style={{ borderColor: '#E9EFF6' }}>
                <button
                  onClick={handleDecide}
                  disabled={acting || !note.trim()}
                  className="flex-1 py-2.5 rounded-xl text-white text-sm font-bold hover:opacity-90 disabled:opacity-50"
                  style={{ background: 'linear-gradient(135deg,#0369A1,#0EA5E9)' }}
                >
                  提交决策
                </button>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">← 点击左侧选择待决策事项</div>
          )}
        </div>
      </div>
    </div>
  )
}
